# Document Corpora

Tools for searching document collections, email archives, entity databases, and PDF ingestion pipelines.

**When to read this module:** When running /deep-investigate (Agent A), /search-all-sources, /pursue-lead, or performing any full-text search across investigation documents.

## Tool Inventory

| Tool | Scope | Storage | Auth | Size |
|------|-------|---------|------|------|
| `ingest_kabasshouse.py` | **PRIMARY — most complete Epstein corpus** — DOJ DS1-12 + FBI + House, fully OCR'd + structured | Local SQLite (FTS5) | None | 1,424,673 document/page records (distinct file_keys), 10.6M entity mentions, 49.7K txns |
| `query_doj.py` | DOJ Vol 11 OCR'd pages (FALLBACK — strict subset of kabasshouse) | Local SQLite (FTS5) | None | 331K pages |
| `query_lmsband.py` | LMSBAND Epstein Files (text overlaps kabasshouse; unique structured financials) | Local SQLite (FTS5) | None | 591,286 files, 1,693,889 entity mentions, 110,334 co-occurrences |
| `query_unified.py` | Unified DB (emails + docs + entities) | Local SQLite (FTS5) | None | 70K docs, 56K entities |
| `query_documentcloud.py` | DocumentCloud journalism archive | Remote API | None (public) | Millions of docs |
| `query_muckrock.py` | MuckRock FOIA requests | Remote API v2 | MuckRock account | 119K+ requests |
| `query_investigations.py` | Ingested investigation PDF reports | Local SQLite (FTS5) | None | Varies |
| `ingest_pdf.py` | PDF text extraction pipeline | Local SQLite (FTS5) | None | N/A (ingestion) |
| `ingest_epstein_20k.py` | House Oversight 20K docs | Local SQLite (FTS5) | None | 25.8K docs |
| `ingest_fbi_files.py` | FBI release + named exhibits (Flight Log, Contact Book) | Local SQLite (FTS5) | None | 8,150 docs |
| `ingest_epstein_exposed.py` | EpsteinExposed.com corpus | Remote API + Local DB | None | 1.5M docs, 1.2K persons |
| `reporting_corpus.py` | Versioned Epstein reporting + attributed claim genealogy | Local SQLite (FTS5) + discovery adapters | Public feeds/GDELT; licensed exports optional | Grows continuously |
| `government_release_corpus.py` | DOJ and SEC official press releases | Local SQLite (FTS5) | None | DOJ API + SEC 1997-present online archive |

**NOTE:** The first four tools are investigation-specific corpora (configured per investigation profile). DocumentCloud and MuckRock are general-purpose. The `ingest_epstein_*` tools are Epstein-investigation-specific.

The reporting corpus is a secondary-source knowledge layer, not a primary corpus.
See `docs/modules/reporting.md`; do not count repeated reporting as independent
corroboration and do not promote a claim without quoted primary evidence.

## Subcommands & Examples

### ingest_kabasshouse.py -- Most complete Epstein corpus (kabasshouse/epstein-data)

**Preferred first stop for Epstein full-text search.** The current local snapshot
contains 1,424,673 OCR document/page records and 1,424,673 distinct `file_key`
values, spanning DOJ DataSets 1-12 + FBI Vault + House Oversight. Structured
layers the other corpora lack include 10.6M entity mentions, 49,770
credit-card/bank/flight transactions, 5,766 expert-curated "gold" docs, and
communication/investigative records. It adds ~790K text-searchable EFTA pages we
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
uv run python tools/query_doj.py download \
  "https://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf" \
  --output "$WORKDIR/EFTA00634292.pdf"
```

DB path: `/Users/travcole/projects/epstein-docs/output/documents.db`

Direct DOJ PDF requests return the age-verification HTML with HTTP 200. The
`download` command sends the public `justiceGovAgeVerified=true` cookie and
fails closed unless the response is an actual PDF, preventing HTML from being
stored and cited as an attachment.

### query_lmsband.py -- LMSBAND Epstein Files

Current local snapshot (2026-07-28): 591,286 files, 1,693,889 entity
mentions, 290,083 unique normalized-or-raw entities, and 110,334
co-occurrences. Run `stats` for live counts.

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

**Auth:** Anonymous works for public documents but is capped at **500 API calls
per IP per 24h** (returns HTTP 429 when exceeded — a large parallel sweep will hit
this). The tool now authenticates automatically when `MUCKROCK_USERNAME`/
`MUCKROCK_PASSWORD` are set: DocumentCloud, MuckRock, and Squarelet share one SSO,
so a Squarelet JWT minted from the MuckRock account lifts the anonymous cap. Tokens
are cached at `~/.cache/ithildin/documentcloud_tokens.json` (0600, outside the repo)
and refreshed transparently on 401. No creds → silent anonymous fallback. Rate
limit: 0.5s between paginated requests.

**Search strategy:** see the MuckRock + DocumentCloud search playbook below — DocumentCloud is the full-text layer over MuckRock's metadata-only search.

### query_muckrock.py -- MuckRock FOIA

Set a normal MuckRock account username and password in the repo-local `.env`.
The official `python-muckrock` wrapper exchanges them for API-v2 access and
refresh tokens automatically:

```dotenv
MUCKROCK_USERNAME=your_username
MUCKROCK_PASSWORD=your_password
```

```bash
uv run python tools/query_muckrock.py project                           # Default project
uv run python tools/query_muckrock.py project 507                       # Epstein project
uv run python tools/query_muckrock.py request 12345                     # FOIA request detail
uv run python tools/query_muckrock.py download 12345 --dir datasets/muckrock
uv run python tools/query_muckrock.py search "Jeffrey Epstein" --limit 25
uv run python tools/query_muckrock.py agencies "Federal Bureau"
uv run python tools/query_muckrock.py crawl-index --output "$WORKDIR/muckrock-crawl.json"
uv run python tools/query_muckrock.py index-stats --output "$WORKDIR/muckrock-stats.json"
uv run python tools/query_muckrock.py index-search "GEO Group" --without-documentcloud --responses-only --output "$WORKDIR/muckrock-index-search.json"
uv run python tools/query_muckrock.py unlinked-files "private prison" --limit 50 --output "$WORKDIR/muckrock-unlinked.json"
```

**Auth:** `MUCKROCK_USERNAME` + `MUCKROCK_PASSWORD`. A free MuckRock account is
sufficient for authentication. API-v2 rate limiting, retries, and token refresh
are handled by the official wrapper.

#### Local full-corpus index

`crawl-index` walks the unfiltered public API and builds
`datasets/muckrock_index.db`, a resumable SQLite/FTS5 catalog of requests,
communication bodies, files, agencies, jurisdictions, and communication-to-file
links. The live API counts on 2026-07-15 were approximately 119,705 requests,
1.396 million communications, and 1.071 million files. API pages are capped at
100 rows. Collections are interleaved and aggregate requests are held to the
official one-request-per-second average; a first full crawl is therefore a
long-running job. Interrupted crawls resume from the last committed page.

Local search does not require credentials once the database exists:

| Command | Purpose |
|---------|---------|
| `index-search [QUERY]` | Search request descriptions, communication bodies, and file metadata; return linked file records |
| `index-search --without-documentcloud` | Keep files with a blank MuckRock `doc_id` |
| `unlinked-files [QUERY]` | Convenience mode: blank `doc_id` **and** incoming agency-response attachments by default |
| `index-stats` | Show table counts, DocumentCloud linkage coverage, unresolved links, and resumable cursors |

`--max-pages N` bounds a test or incremental run per selected collection.
`--restart` resets selected cursors to page 1 while retaining and upserting the
existing rows. A blank `doc_id` means the MuckRock file has no direct
DocumentCloud linkage; call it **DocumentCloud-unlinked**, not proof that a
separately uploaded duplicate does not exist. These unlinked results include
ZIP, XLS/XLSX, images, and PDFs whose contents are otherwise absent from
DocumentCloud full-text search. Download and inspect/OCR only the promising
files after metadata and communication-body triage.

### MuckRock + DocumentCloud search playbook

Verified by live API probes 2026-07-15. Controls and worked examples:
`investigations/geo-group/reports/2026-07-15-muckrock-cross-investigation-sweep.md`.

**Governing fact:** MuckRock remote `search=` matches request titles/metadata only — never the
`requested_docs` body or released-file text (a distinctive phrase quoted from request
20166's own body returned 0). Matching is token-AND, not phrase-exact. DocumentCloud —
run by the same organization — is the full-text layer: MuckRock-published releases are
OCR'd and searchable there, alongside FOIA productions uploaded by hundreds of other
newsrooms and orgs. The local MuckRock index complements it by searching request bodies,
correspondence, and file metadata and by surfacing files with no direct DocumentCloud link.

**Six search structures, ranked by yield:**

1. **DocumentCloud full-text phrase sweep.** Distinctive quoted phrases; entity names,
   facility names, and contract/docket numbers beat bare person names. This is the direct
   answer to "MuckRock can't search released text."
2. **Local unlinked-file sweep.** Run `unlinked-files` against the local index. It searches
   request descriptions, communication bodies, and file metadata, then returns response
   attachments with blank `doc_id` values for selective download/OCR.
3. **Requester-portfolio pivot.** Every relevant request found → `user=<id>` → triage that
   filer's whole portfolio (beat reporters cluster topically). User 2116, filer of ISAP III
   request 20166 and the GEO NJ contracts request, has 5,455 requests (2,409 done).
4. **Agency-centric browse.** Invert "who do we care about" into "which agency's records
   mention them." Completed-request counts per agency are small enough to triage in one
   pass: agency 133 (ICE) has only 240 `done` requests; `agency=133` + `search="medical"` → 4.
5. **Ask-shaped queries, not answer-shaped.** The searchable text is what requesters wrote.
   Cross record-type phrases ("visitor logs", "calendars", "ODO Inspection", "correspondence
   with") with agencies. Subject-name search only works for subjects famous enough to be
   FOIA'd by name.
6. **Projects + tags.** Only 216 projects exist — enumerate once, cache, grep locally.
   `tags="private prisons"` → 18 requests. Sparse but curated.

**MuckRock filter axes** — the official wrapper passes any filter through
`client.requests.list(**params)`. All of the below work today even though the CLI only
exposes `search`; adding `user`/`agency`/`status`/`jurisdiction`/`tags`/`ordering` flags
to `tools/query_muckrock.py` is pending work.

| Param | Behavior (probed) |
|-------|-------------------|
| `search=` | Titles/metadata only, token-AND: `"GEO Group"` → 49 |
| `title=` | Substring (icontains) — distinctive strings only: `title="GEO"` → 1,231 incl. "Georgia" |
| `user=<id>` | Requester portfolio: `user=2116` → 5,455 (2,409 with `status=done`) |
| `agency=<id>` | Combines with `status`/`search`: ICE (133) + `status=done` → 240 |
| `jurisdiction=<id>` | Works, combines with search (Minnesota = 156) |
| `tags=` | Exact tag: `"private prisons"` → 18 |
| `ordering=-datetime_done` | Recently-completed monitor |

```bash
uv run python - <<'PY'
import os
from itertools import islice
from muckrock import MuckRock
from tools.env_loader import load_env_file
load_env_file()
client = MuckRock(username=os.environ["MUCKROCK_USERNAME"],
                  password=os.environ["MUCKROCK_PASSWORD"])
for r in islice(client.requests.list(agency=133, status="done"), 50):
    print(r.id, r.status, r.title)
PY
```

**MuckRock quirks (all probed):**

- **Projects endpoint ignores `search=`** (always returns all 216), but `title=` works:
  `title="Private Prison"` → project 8, "The Private Prison Project", 78 requests.
  Project 507 = the Epstein project (tool default).
- **Communications endpoint has no text search** (param silently ignored; ~1.4M rows).
  `crawl-index` downloads those bodies into local FTS5, where they are searchable.
- **API `page_size` is silently capped at 100.** The crawler uses the effective cap and
  commits a cursor after every page.
- **`users.retrieve(<other-id>)` → 404.** Other users' names are not resolvable via the
  API — read them off the request's web page. The `user=<id>` filter itself works.
- **`status=done` ≠ documents released.** A done request may hold zero files (e.g. 193740).
- **Statuses evolve over months.** An empty search today isn't empty forever — persist term
  lists and re-run them filtered by `ordering=-datetime_done` as a cheap monitor.
- **Escalation:** `requests.create` exists in the wrapper. Filing new FOIA requests is a
  human-decision item for the `human_actions` queue — never automate it.

**DocumentCloud as the full-text layer:**

- MuckRock-uploaded docs encode the request ID in the title: "MuckRock - MR152957" →
  MuckRock request 152957. That is the doc→request mapping.
- Hits from other orgs reveal troves: org 1004 (National Immigrant Justice Center) uploaded
  2007-2016 ICE ODO/ERO inspections of Northwest Detention Center obtained through
  NIJC v. DHS FOIA litigation (docs 6572745, 1813477-8, 804516, 2844562).
- Verified productive phrases where MuckRock metadata search returned nothing:
  `"Feeding Our Future"` (state-court transcript 22925376, Aimee Bock sentencing memos
  28140228/28139746); `"Liberty Strategic Capital"` (FARA informational materials
  25821431/25863862-3, POGO FOIA-suit complaint 21085560); `"Paul, Weiss"`
  (chairman Brad Karp's Apr-2025 signed letter to Congress on the firm's Trump-EO
  deal, doc 25950510; House Oversight probe letter 25920793). NOTE: bare firm-name
  hits are mostly counsel-of-record boilerplate — the earlier Puerto Rico FOMB
  cites (23325803/24219557) proved non-substantive, so constrain firm names with
  fee/engagement/investigation language.
- `organization:<slug>` fielded queries did NOT filter strictly in probes — treat as
  unverified. Unscoped phrase search is the workhorse.

```bash
uv run python tools/query_documentcloud.py search '"Liberty Strategic Capital"' --limit 25 --output "$WORKDIR/dc-lsc.json"
uv run python tools/query_documentcloud.py text 25821431 --page 1
```

**Operational rules:**

- Dedup: check `check_searched(query, source)` (`from tools.lead_tracker import
  check_searched`) before querying. `query_muckrock.py` logs its own searches;
  `query_documentcloud.py` does NOT — log manually with `log_search(query, "documentcloud", n)`.
- Always `--output FILE` into the session `$WORKDIR`.
- A request description is a lead, not evidence that responsive records exist. Mirrored
  productions of the same agency release are redundancy, not corroboration. Create findings
  only after quote-level page review. Canonical evidence format:
  `MUCKROCK:<request>:<file>:p<page>` (e.g. `MUCKROCK:20166:2015-ICFO-90401:p626`).

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
| `query_muckrock.py` | MuckRock account | `MUCKROCK_USERNAME`, `MUCKROCK_PASSWORD` |
| `query_investigations.py` | None (local DB) | -- |
| `ingest_pdf.py` | None (local) | -- |
| `ingest_epstein_20k.py` | None (HuggingFace public) | -- |
| `ingest_epstein_exposed.py` | None (public API) | -- |

## Known Quirks

- **query_unified.py has no `search` subcommand.** Use `emails` or `docs` instead. A bare `search` call will print help and exit.
- **query_lmsband.py FTS5 fallback.** If the FTS index is missing, it falls back to LIKE search (much slower). Run `ingest` to rebuild the index.
- **MuckRock search list results do not expand file metadata.** The `search`
  command reports `file_count: null`; use `request <id>` to expand communications
  and released-file metadata. Project mode uses the project's request IDs and
  counts each request's communication file references.
- **DugganUSA (`duggan_search.py`) was RETIRED 2026-06-29** — the `analytics.dugganusa.com` endpoint went permanently HTTP 403 (server-side access revoked). All 12 DOJ datasets it indexed remain reachable via DOJ Vol 11 / LMSBAND / Unified. `duggan` survives only as a historical source name on 42 existing findings.
- **ingest_epstein_20k.py uses CSV ingestion** with large field sizes. The `csv.field_size_limit` is set to `sys.maxsize`.
- **3 sources returning the same document is redundancy, not corroboration.** DOJ, LMSBAND, and Unified DB overlap heavily. Cross-check with independent primary sources.
- **All local tools use `--output FILE` for session isolation.** Use `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)` and write all output there.

## Skills That Use These Tools

- `/deep-investigate` (Agent A -- Document Corpus Search)
- `/search-all-sources` (fans out across all corpora)
- `/pursue-lead` (searches relevant corpora based on lead type)
