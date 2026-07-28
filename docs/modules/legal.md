# Court Records & Legal

Tools for US federal/state court dockets, opinions, judge research, and European Court of Human Rights cases.

**When to read this module:** When running /analyze-case, /deep-investigate (Agent C), or researching litigation history, judicial conflicts of interest, or ECHR proceedings for any entity.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_state_courts.py` | Unified state/local-court router | Catalog-reviewed per source | `datasets/state_court_records.db` | Source-specific; local by default |
| `public_records_search_plan.py` | Cross-domain property/recorder/court planner | None | Reads catalog and investigation context | Local |
| `public_records_actions.py` | Formal-feed, account, paid, request, and physical-access work planner | Catalog route metadata | `human_actions` in `investigation.db` | Local |
| `public_records_store.py` | Normalized state/local-court evidence sidecar | None | `datasets/state_court_records.db` | Local |
| `ingest_state_court_records.py` | Adapter-neutral court-envelope ingester | None | `datasets/state_court_records.db` | Local |
| `query_courtlistener.py` | CourtListener/RECAP API (v4) | `COURTLISTENER_TOKEN` in .env | No | Reasonable (API token required) |
| `query_nyscef.py` | NYSCEF portal adapter | Catalog-selected route | No | Source-specific |
| `query_hudoc.py` | HUDOC REST API (undocumented) | None | No | 0.5s between requests |
| `query_military_corrections.py` | DoD Boards of Review Reading Room (boards.law.af.mil) | None | `.cache/military_corrections.db` (SQLite + FTS5) | 2.0s between requests (~0.5 req/sec) |
| `query_military_justice.py` | CAAF + ACCA + NMCCA + AFCCA + CGCCA (HTML/PDF scraping) | None | `datasets/military_justice_cache.db` (SQLite WAL) | 1 req/sec per host (configurable) |

## Unified state/local-court interface

`query_state_courts.py` searches normalized local observations by default and
reads the public-records catalog when a named live source is selected. The
result envelope keeps true zeroes, partial coverage, human actions, terms
blocks, unavailable sources, and later restrictions distinct.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
# Inspect cataloged coverage and reviewed access
uv run python tools/query_state_courts.py sources --jurisdiction 36 \
  --output "$WORKDIR/state-court-sources.json"

# Search the normalized local sidecar
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --output "$WORKDIR/state-court-search.json"
uv run python tools/query_state_courts.py case "2025-CV-000001" \
  --court-id example-circuit \
  --output "$WORKDIR/state-court-case.json"
uv run python tools/query_state_courts.py docket "2025-CV-000001" \
  --court-id example-circuit \
  --output "$WORKDIR/state-court-docket.json"
uv run python tools/query_state_courts.py documents "2025-CV-000001" \
  --court-id example-circuit \
  --output "$WORKDIR/state-court-documents.json"

# NYSCEF currently resolves to its catalogued human route
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --source us-ny-nyscef --jurisdiction 36 \
  --output "$WORKDIR/nyscef-human-action.json"
```

The router reports the current catalog state for each selected source. A
successful query with no matching cases is `no_results`; account, feed,
human-action, unavailable, and changed-source routes retain their own result
states instead of being collapsed into a false zero. The normalized court
sidecar preserves courts, cases, parties, attorneys and representations,
judicial assignments, docket entries, events, document artifacts, source
snapshots, and restriction events.

The court store keeps each source-native access, assertion, and restriction
label alongside its canonical category. Known variants such as
`made_nonpublic` and `destroyed` map to serving states, while unfamiliar values
remain queryable through `other` or `unknown` instead of aborting ingestion.

Local sidecar presence in one court or jurisdiction does not establish
coverage elsewhere. A miss in an observed scope is `partial`; a miss outside
observed scope is `unavailable`. Both carry machine-readable scope counts,
matching snapshot evidence, and catalog/action route guidance. An exact
source-query snapshot can support `no_results` when its source, jurisdiction or
court, selector, date filters, and completion state match the request. An exact
known case or document identifier with a non-public current access state
returns `restricted` plus a minimal restriction tombstone; case contents,
parties, docket text, document paths, and artifact bytes are not served in that
tombstone.

Canonical state/local-court citations use:

```text
STATECOURT:<source_id>/<court_id>/<case_number>/<record_kind>[/<native_id>]
```

Generic `STATECOURT:` references link to the official source landing page when
that source ID is registered. They do not invent a case-detail URL. Other
source IDs remain record-only. Later source restriction events update current
serving state while preserving the observation and audit history.

## Formal feeds and source actions

The catalog includes candidate formal court-data programs in Pennsylvania,
Maryland, Indiana, Wisconsin, Minnesota, North Carolina, Arizona, Oregon,
Washington, and Texas. It also includes targeted public-portal candidates for
Pennsylvania UJS, Maryland Case Search, Delaware CourtConnect, and DC Superior
Court eAccess. These are catalog/action routes, not implemented query adapters.
Their entries preserve the official program URL, advertised capabilities,
authentication or agreement route, fees, update model, and record-policy
metadata. Inspect those facts before deciding which route fits the
investigation:

```bash
uv run python tools/public_records_catalog.py list --domain court --json
uv run python tools/public_records_catalog.py show us-pa-ujs-public-dockets --json
uv run python tools/public_records_catalog.py show us-md-case-search --json
uv run python tools/public_records_catalog.py show us-in-iocs-bulk --json
uv run python tools/public_records_catalog.py show us-wi-wcca-rest --json
```

`public_records_actions.py` turns any catalog route into a reproducible plan.
`enqueue` adds the same structured request to `human_actions`, deduplicated by
its action fingerprint.

```bash
uv run python tools/public_records_actions.py plan us-in-iocs-bulk \
  --operation obtain_feed --selector "civil case metadata" \
  --requested-field case_number --requested-field party_name \
  --output "$WORKDIR/indiana-feed-plan.json"
uv run python tools/public_records_actions.py enqueue us-az-eaccess \
  --operation fetch_document --selector "CV2026-000042" \
  --court-or-office "Maricopa County Superior Court" \
  --output "$WORKDIR/arizona-document-action.json"
uv run python tools/public_records_actions.py plan us-pa-ujs-public-dockets \
  --operation fetch_docket_sheet --selector "CP-00-CR-0000042-2026" \
  --output "$WORKDIR/pennsylvania-docket-plan.json"
uv run python tools/public_records_actions.py plan us-md-aoc-court-data \
  --operation request_court_data --selector "civil judgments" \
  --output "$WORKDIR/maryland-court-data-plan.json"
uv run python tools/public_records_actions.py list --status pending \
  --output "$WORKDIR/pending-public-record-actions.json"
```

This keeps source-specific acquisition facts in the catalog and action record,
while query adapters remain focused on search and normalization.

## Court sidecar ingestion

Every valid `public-records-result/1.0` envelope can be retained as an immutable
source snapshot. `ok` and `partial` envelopes may also project canonical case
records into courts, cases, parties, attorneys, representations, judicial
assignments, docket entries, events, documents, and restriction events.
Barrier and zero-result envelopes remain useful source observations even when
there are no case rows to project.

```bash
uv run python tools/ingest_state_court_records.py ingest \
  "$WORKDIR/court-result.json" \
  --output "$WORKDIR/court-ingest.json"
```

Re-ingesting the same envelope is idempotent. The summary reports its snapshot
ID, source status, projected row counts, artifact hash, and canonical
`STATECOURT:` references.

## Cross-domain planning and document evidence

Build a reproducible search plan when litigation may be connected to a person,
entity, address, parcel, lender, recorder instrument, or legal description:

```bash
uv run python tools/public_records_search_plan.py "Example Holdings LLC" \
  --alias "Example Holdings" \
  --address "100 Main St, Albany, NY" \
  --jurisdiction 36 \
  --output "$WORKDIR/example-records-plan.json"
```

The plan inventories every cataloged property and court source and emits
dependency-aware query templates. It includes sources reached through APIs,
bulk files, accounts, formal feeds, requests, and physical offices; the source
entry carries the current route and capabilities.

For court filings, retain the source bytes in
`public_records_artifacts.py`, add OCR or parsed-text representations, and
ingest field-level extraction through `public_records_extract.py`. Evidence
rows can point to an artifact hash, representation, page, region, and exact
quote. Deterministic checks cover dates, amounts, identifiers, quoted text, and
the extraction schema; model or rule provenance stays attached to the derived
representation.

After court parties and property/instrument parties are in their sidecars,
`public_records_entity_candidates.py generate` produces explainable candidates
against investigation entities and aliases. Review its retained name, address,
and identifier signals, then use `decide --action accept|reject|reopen|undo`
to record the resolution history.

## query_courtlistener.py — CourtListener/RECAP

Comprehensive US court research: docket search, party/attorney/firm lookup, opinion text, RECAP document search and download, citation graphs, judge career timelines, financial disclosures, investment holdings, travel reimbursements, and FJC Integrated Database queries. Recently rebuilt with 17 commands.

**Auth:** Requires `COURTLISTENER_TOKEN` in `.env`. Free accounts available at courtlistener.com.

### Search Commands

```bash
# Generic search with field operators (type: r=RECAP, o=opinions, p=people)
uv run python tools/query_courtlistener.py search "Jeffrey Epstein" --type r --limit 20
uv run python tools/query_courtlistener.py search --party "Ghislaine Maxwell" --court nysd
uv run python tools/query_courtlistener.py search --attorney "David Boies" --type r
uv run python tools/query_courtlistener.py search --firm "Kirkland" --after 2020-01-01
uv run python tools/query_courtlistener.py search "fraud" --docket-number "1:23-cv-01234"
uv run python tools/query_courtlistener.py search "Epstein" --semantic --highlight

# RECAP docket search (shortcut for type=r with case-specific output)
uv run python tools/query_courtlistener.py cases "Epstein" --court nysd
uv run python tools/query_courtlistener.py cases "Maxwell" --after 2019-01-01 --before 2023-01-01

# Party search (returns parties, attorneys, firms)
uv run python tools/query_courtlistener.py party "Ghislaine Maxwell" --limit 20
uv run python tools/query_courtlistener.py party "Apollo Global" --court nysd

# Opinion search (with optional semantic search)
uv run python tools/query_courtlistener.py opinions "Epstein" --court ca2
uv run python tools/query_courtlistener.py opinions "qualified immunity" --semantic
```

### Docket & Document Commands

```bash
# Docket detail by ID
uv run python tools/query_courtlistener.py docket 16066603

# RECAP document search (filings, motions, exhibits)
uv run python tools/query_courtlistener.py recap-search "motion to dismiss" --court nysd

# Download RECAP document PDF
uv run python tools/query_courtlistener.py download "https://storage.courtlistener.com/..." /tmp/doc.pdf
uv run python tools/query_courtlistener.py download "recap/..." /tmp/doc.pdf --extract-text

# Full opinion text by opinion ID or cluster ID
uv run python tools/query_courtlistener.py opinion 12345678 --lines 500
# Auto mode checks the cluster endpoint first because cluster/opinion numeric IDs
# overlap. For a known raw opinion API ID, add: --id-type opinion

# Opinion cluster details (citation count, precedential status)
uv run python tools/query_courtlistener.py cluster 98765
```

### Citation & Reference Commands

```bash
# Citation graph (what this opinion cites and what cites it)
uv run python tools/query_courtlistener.py citations 98765 --limit 50

# Resolve citation text to CourtListener cluster IDs
uv run python tools/query_courtlistener.py resolve-cite "521 U.S. 702"
```

### Judge Research Commands

```bash
# Search judges by name
uv run python tools/query_courtlistener.py judge "Preska" --limit 10

# Full career timeline (positions, education, political affiliations)
uv run python tools/query_courtlistener.py career "Loretta Preska"

# Financial disclosures
uv run python tools/query_courtlistener.py disclosures --person-id 1234
uv run python tools/query_courtlistener.py disclosures --person-id 1234 --year 2022

# Investment holdings search (by company/description)
uv run python tools/query_courtlistener.py investments "Apollo Global" --limit 20
uv run python tools/query_courtlistener.py investments "JPMorgan" --person-id 1234

# Travel reimbursements (by source organization)
uv run python tools/query_courtlistener.py reimbursements "Federalist Society" --limit 20
uv run python tools/query_courtlistener.py reimbursements "Heritage Foundation" --person-id 1234
```

### FJC Integrated Database

```bash
# Federal case metadata (plaintiff, defendant, nature of suit, disposition)
uv run python tools/query_courtlistener.py fjc --plaintiff "United States" --nos 470 --after 2020-01-01
uv run python tools/query_courtlistener.py fjc --defendant "Epstein" --limit 50
```

FJC searches use one bounded request attempt because this upstream endpoint can
be much slower than the other CourtListener APIs. A timeout exits nonzero with
a concise diagnostic; narrow the party prefix or add a date range before retrying.

### Known Quirks

- The `opinion` command tries the opinion ID first, then falls back to treating it as a cluster ID (fetches first sub-opinion from the cluster).
- `download --extract-text` prefers PyMuPDF and automatically falls back to
  Poppler `pdftotext`. It exits nonzero if neither extractor works and warns
  when the resulting text density indicates that the PDF likely needs OCR.
- The `search` command supports field operators: `party:`, `firm:`, `attorney:`, `assignedTo:`, `docketNumber:` -- these can be combined with free text.
- `--semantic` enables vector-based semantic search (slower but finds conceptual matches).
- Court codes use CourtListener format: `nysd` (S.D.N.Y.), `ca2` (2nd Circuit), `scotus`, etc.
- The `career` command chains multiple API calls (person, positions, education, affiliations) -- budget for 4+ requests per invocation.

## query_nyscef.py — New York State Courts Electronic Filing

NYSCEF exposes a server-rendered guest portal rather than a public search API.
`query_nyscef.py` reads its route from the central source catalog. The current
review returns a structured `human_required` result with the requested criteria
and official URLs. Route facts can be updated centrally, and the same commands
consume them without a second environment-variable switch.

Canonical official pages:

- Guest search: <https://iapps.courts.state.ny.us/nyscef/CaseSearch>
- Terms of Use: <https://iappscontent.courts.state.ny.us/NYSCEF/live/termsOfUse.htm>
- FAQ: <https://iappscontent.courts.state.ny.us/nyscef/live/faq.htm>
- Court-record help: <https://www.nycourts.gov/help/representing-yourself-court/getting-court-records-case-information>

```bash
# Search using the current catalog route
uv run python tools/query_nyscef.py search "Jeffrey Epstein" \
  --county "New York" --after 2019-01-01 \
  --output "$WORKDIR/nyscef-human-action.json"

# Case and document routes
uv run python tools/query_nyscef.py case 156728/2019 \
  --output "$WORKDIR/nyscef-case-action.json"
uv run python tools/query_nyscef.py documents OPAQUE_DOCKET_ID \
  --output "$WORKDIR/nyscef-documents-action.json"
```

### Access notes

- Inspect the current decision with
  `uv run python tools/public_records_catalog.py show us-ny-nyscef --json`.
- Public search works by HTML form POST -> redirect -> server-side result pages. No public JSON endpoint was confirmed during discovery.
- Search results link into `DocumentList?docketId=...` pages, `CaseDetails?docketId=...` pages, and `ViewDocument?docIndex=...` PDF endpoints.
- Many cases and filings remain unavailable to guests; NYSCEF shows those as restricted rows rather than returning case detail.

## query_military_justice.py — Military Justice Appellate Courts

Unified scraper for the U.S. Court of Appeals for the Armed Forces (CAAF) and
the four service Courts of Criminal Appeals (ACCA, NMCCA, AFCCA, CGCCA). These
courts publish dockets and opinions on disparate static sites and are NOT in
CourtListener — Eddie Gallagher's 2019 court-martial, for example, has no
CourtListener record.

**Killer feature**: the `attorney` subcommand cross-searches all reachable
opinion PDFs for a civilian counsel name and returns every case where that
name appears with a context snippet.

### Subcommands

```bash
# Cross-court keyword search (uses cached indices)
uv run python tools/query_military_justice.py search "Bergdahl" --output /tmp/x.json
uv run python tools/query_military_justice.py search "Bergdahl" --courts CAAF,ACCA --output /tmp/x.json
uv run python tools/query_military_justice.py search "Edward Gallagher" --refresh --output /tmp/x.json

# CAAF October Term opinion index — single year or 'current'
uv run python tools/query_military_justice.py caaf-dockets 2024 --output /tmp/x.json
uv run python tools/query_military_justice.py caaf-dockets current --output /tmp/x.json

# CAAF opinion PDF — extracts counsel block, panel, decision date, disposition
uv run python tools/query_military_justice.py caaf-opinion 24-0156/AR --output /tmp/x.json
uv run python tools/query_military_justice.py caaf-opinion 24-0156/AR --full-text --output /tmp/x.json

# Service-court searches
uv run python tools/query_military_justice.py acca-search "Burke"   --output /tmp/x.json
uv run python tools/query_military_justice.py afcca-search "Smith"  --output /tmp/x.json
uv run python tools/query_military_justice.py nmcca-search "Gallagher" --output /tmp/x.json
uv run python tools/query_military_justice.py cgcca-search "Mieres" --output /tmp/x.json

# Killer feature — find every reachable opinion where <NAME> is counsel
uv run python tools/query_military_justice.py attorney "Conway" --pdf-limit 200 --output /tmp/x.json
uv run python tools/query_military_justice.py attorney "Parlatore" --skip-refresh --output /tmp/x.json

# One-docket detail
uv run python tools/query_military_justice.py case-detail "24-0156/AR" --output /tmp/x.json
```

### Court Coverage

| Court | Site | Coverage | Notes |
|-------|------|----------|-------|
| **CAAF** | armfor.uscourts.gov | Full | Term pages parsed (2018-2026 verified); Daily Journal monthly pages parsed for docket actions; opinion PDFs extracted via `pypdf` |
| **AFCCA** | afcca.law.af.mil | Full | Public opinion index parsed; docket page has no attorney info |
| **ACCA** | jagcnet.army.mil/ACCALibrary | Full | OC/MO/SFA/SD opinion lists parsed; URLs return PDFs despite not ending in `.pdf` |
| **NMCCA** | jag.navy.mil/.../nmcca/opinions/ | Limited | Server-rendered POST search form (Sitecore). Tool fetches index page only. Cross-court `attorney` finds NMCCA-origin cases via CAAF appeal records. |
| **CGCCA** | uscg.mil/.../CGCCA-Opinions/ | Limited | 403 from non-browser User-Agents (Akamai/CDN). Use `--user-agent` override or query FindLaw mirror at caselaw.findlaw.com |

### Caching & Rate Limiting

- All HTTP responses cached in `datasets/military_justice_cache.db` (SQLite WAL).
- Three tables: `pages` (raw HTTP), `pdf_text` (extracted PDF text), `docket_index` (parsed metadata).
- Default rate limit is 1 req/sec per host; configurable via `--rate-limit 0.5`.
- `--no-cache` bypasses caching for fresh fetches.

### Counsel Extraction

Opinions usually have a "For Appellant" / "For Appellee" block listing both
military counsel ("Captain Anthony J. Scarpati") and civilian counsel
("Daniel Conway, Esq."). The PDF-text extractor parses these blocks
heuristically and exposes them in the `counsel` field of `caaf-opinion`,
`case-detail`, and `attorney` outputs. Civilian names typically appear without
rank prefixes; military counsel names start with rank words (Captain, Major,
Colonel, Commander, etc.).

### Known Limitations

- NMCCA's search form is POST-only; full search requires Playwright. Documented in `--help` and `nmcca-search` output.
- CGCCA's CDN blocks bare-UA HTTP requests with 403. Documented in `--help` and `cgcca-search` output.
- Counsel-extraction heuristics may miss names embedded in continuous prose; the `attorney` command falls back to a substring check before reporting a hit.

## query_hudoc.py — ECHR Case Database

Searches European Court of Human Rights judgments, decisions, and communications (1959-present). ~20,000 judgments and ~100,000 decisions.

```bash
# Full-text search
uv run python tools/query_hudoc.py search "Ron Soffer"
uv run python tools/query_hudoc.py search "Soffer, avocat" --limit 20

# Case detail by item ID
uv run python tools/query_hudoc.py case 001-99808

# Lookup by application number
uv run python tools/query_hudoc.py appno "34868/03"

# Filter by respondent state
uv run python tools/query_hudoc.py respondent ROU --limit 50

# Full case text (HTML-to-text conversion)
uv run python tools/query_hudoc.py text 001-99808
```

### Known Quirks

- Uses an undocumented REST API at `hudoc.echr.coe.int/app/query/results`.
- Respondent codes are ISO 3166-1 alpha-3 (e.g., `ROU` for Romania, `GBR` for UK, `TUR` for Turkey).
- Rate limiting is polite (0.5s between requests) with retry on 429.
- Results include fields: `itemid`, `docname`, `respondent`, `extractedappno`, `conclusion`, `kpdate`.
- The `text` command fetches the HTML body and converts to plain text. Useful for searching specific language in judgments (e.g., counsel names that appear in the body but not metadata).

## query_military_corrections.py — DoD BCMR/BCNR Reading Room

Crawls the Department of Defense Boards of Review Reading Room (hosted by the Air Force at `boards.law.af.mil`) which mirrors decisional documents for all four service correction boards: AFBCMR (Air Force, 1984-present), ABCMR (Army, 1997-present), BCNR (Navy/Marines, 1998-present), and CGBCMR (Coast Guard, organized by topic). Decisions are redacted PDFs; petitioner counsel is sometimes named on the face of the PDF and sometimes redacted. Counsel is never exposed in index metadata, so a full-text scan over downloaded PDFs is the only way to identify a specific firm.

**Cache:** `.cache/military_corrections.db` (SQLite, WAL mode, FTS5). PDFs at `.cache/military_corrections/<service>/<bucket>/<filename>.pdf`. Reset with `--reset-cache`.

```bash
# Refresh the index of available decisions (no PDFs yet)
uv run python tools/query_military_corrections.py crawl-index --service all --output /tmp/mc-index.json
uv run python tools/query_military_corrections.py crawl-index --service afbcmr --year-from 2020 --year-to 2024

# Download a year's decisions for one service (or one CG topic folder)
uv run python tools/query_military_corrections.py download --service afbcmr --year-from 2024 --year-to 2024
uv run python tools/query_military_corrections.py download --service cgbcmr --bucket "Officer Promotion and DOR"
uv run python tools/query_military_corrections.py download --service bcnr --bucket CY2024 --limit 100

# Extract text into local SQLite
uv run python tools/query_military_corrections.py index-text --service all
uv run python tools/query_military_corrections.py index-text --service bcnr --reindex

# Killer feature: find decisions where a specific counsel appears
uv run python tools/query_military_corrections.py attorney "Parlatore" --output /tmp/parlatore.json
uv run python tools/query_military_corrections.py attorney "Parlatore Law Group" --service bcnr

# Topic search across the indexed corpus (FTS5 phrase search)
uv run python tools/query_military_corrections.py keyword "promotion list" --output /tmp/promo.json
uv run python tools/query_military_corrections.py keyword "selection board"
uv run python tools/query_military_corrections.py keyword "fitness report"

# One-decision lookup (works on docket OR fragment of the PDF filename)
uv run python tools/query_military_corrections.py decision afbcmr BC-2024-00035
uv run python tools/query_military_corrections.py decision bcnr NR20240000001

# Cache state
uv run python tools/query_military_corrections.py stats
```

### Service IDs and structure

| ID | Board | Bucket kind | Earliest | PDF naming |
|----|-------|-------------|----------|------------|
| `afbcmr` | Air Force BCMR | calendar year (`CY1984`–`CY2024`) | 1984 | `BC-YYYY-NNNNN BCYYYYNNNNN.pdf` |
| `abcmr` | Army BCMR | calendar year (`CY1997`–`CY2024`) | 1997 | `ARYYYYNNNNNNN_Redacted.pdf` |
| `bcnr` | Navy/Marines BCNR | calendar year (`CY1998`–`CY2024`) | 1998 | `NRYYYYNNNNNNN_Redacted.pdf` |
| `cgbcmr` | Coast Guard BCMR | topic categories (e.g. "Officer Promotion and DOR") | by topic | `<docket> <category>_Redacted.pdf` |

The Coast Guard board uniquely organizes by *topic* rather than year, so `--year-from`/`--year-to` are ignored and you select with `--bucket "<Category>"`. Categories include `Officer Promotion and DOR`, `Officer Performance and OERs`, `Discharge and Reenlistment Codes`, `NJP and Court-Martial`, `Discrimination and Retaliation`, etc.

### Volume estimates (single year of decisions)

Roughly 685 AFBCMR / 4,250 ABCMR / 3,510 BCNR decisions per recent year, plus ~2,700 CGBCMR decisions across all topic categories combined. A full historical crawl is well into the hundreds of thousands of PDFs — use `--year-from/--year-to` or `--bucket` to scope, and the tool's incremental cache (`local_path IS NULL` filter) means subsequent `download` runs only fetch missing files.

### Known Quirks

- The Reading Room is plain HTML directory listings (no API). The tool fetches the index pages, parses anchor tags, and persists the catalog into SQLite *before* downloading PDFs, so you can crawl the metadata cheaply, then download lazily.
- Default rate limit is 2.0s between requests (0.5 req/sec). Configurable via the global `--delay N` flag, which must precede the subcommand.
- `attorney` and `keyword` use SQLite FTS5 phrase search with porter+unicode61 tokenization, falling back to `LIKE` if FTS returns no rows. Both return up to 3 ~180-char excerpts per match.
- The tool pulls a docket identifier from the PDF filename via service-specific regex; falls back to the bare filename stem if the pattern misses.
- The Navy/SECNAV BCNR site (`secnav.navy.mil/mra/bcnr`) blocks automated requests behind an F5/BIG-IP defender; the Air Force-hosted mirror is the canonical machine-readable copy.
- ARBA (`arba.army.pentagon.mil`) and the Coast Guard Legal page (`uscg.mil/Resources/Legal/...`) are unreachable from automated fetchers (timeouts / 403). Again, the AF-hosted mirror is the workaround.
- PDF text extraction uses PyMuPDF when available. CourtListener downloads also
  support Poppler `pdftotext` as a fallback. Some redacted PDFs are scanned
  images with no useful text layer — those rows show `text_chars=0` and won't
  appear in keyword/attorney searches. OCR is out of scope for this tool.
- Before using `ocrmypdf --skip-text` on a mixed court exhibit, inspect each
  page's extracted text. A tiny footer or court page number makes an otherwise
  image-only page count as text-bearing and can skip the scanned body. For a
  bounded affected excerpt, use `--force-ocr` and verify the replacement text
  against the rendered pages.

## Skills Using These Tools

| Skill | Tools Used |
|-------|-----------|
| `/analyze-case` | `query_courtlistener.py` (docket, recap-search, opinion, citations, party), `query_state_courts.py` (case/docket/documents), `public_records_actions.py` (catalog routes), `query_military_justice.py` (case-detail, caaf-opinion) |
| `/deep-investigate` (Agent C) | `query_courtlistener.py`, `query_state_courts.py`, `public_records_search_plan.py`, `public_records_actions.py`, `query_military_justice.py` |
| `/investigate-person` | `public_records_search_plan.py`, `query_state_courts.py`, `query_courtlistener.py`, `query_hudoc.py`, `query_military_justice.py`, `public_records_entity_candidates.py` |
| `/systemic-analysis` | `query_courtlistener.py` (fjc, investments, reimbursements) |
| `/investigate-person` (mil. counsel) | `query_military_corrections.py attorney "<NAME>"` to surface BCMR/BCNR petitions where a target appears as petitioner counsel |
| `/deep-investigate` (mil. service members) | `query_military_corrections.py keyword`, `decision` for promotion-list challenges, OER/EER corrections, separation appeals |

## Common Investigation Patterns

### Litigation history for a person/entity
1. `party "Entity Name"` -- find all cases
2. `docket <ID>` -- get case details for interesting hits
3. `recap-search "Entity Name" --court nysd` -- find specific filings
4. `download <URL> --extract-text` -- get document text

### New York state-court search
1. `public_records_search_plan.py "Entity Name" --jurisdiction 36` -- build the property/recorder/court plan
2. `query_state_courts.py sources --jurisdiction 36` -- inspect the current catalog routes and capabilities
3. `query_state_courts.py search "Entity Name"` -- search normalized retained observations
4. `query_nyscef.py search "Entity Name"` -- return the current NYSCEF route with the requested criteria
5. `public_records_actions.py plan us-ny-nyscef --operation fetch_document --selector "<CASE/DOCUMENT>"` -- render the concrete source action

### Judicial conflict-of-interest check
1. `judge "Judge Name"` -- get person ID
2. `career "Judge Name"` -- positions, education, affiliations
3. `disclosures --person-id <ID>` -- financial disclosures
4. `investments "Company Name" --person-id <ID>` -- specific holdings
5. `reimbursements "Organization" --person-id <ID>` -- travel/gifts

### Military counsel / promotion-board practice mapping
1. `query_military_corrections.py crawl-index --service all` -- refresh the catalog
2. `query_military_corrections.py download --service bcnr --year-from 2018 --year-to 2024` -- pull recent Navy decisions (or a specific year/bucket of interest)
3. `query_military_corrections.py index-text --service all` -- extract text into FTS5
4. `query_military_corrections.py attorney "Parlatore"` -- find decisions where the firm appears as petitioner counsel
5. `query_military_corrections.py keyword "promotion list"` -- correlate counsel hits with promotion-list adjudications
6. `query_military_corrections.py decision <SVC> <DOCKET>` -- pull metadata + text excerpt for any hit

### Citation chain analysis
1. `opinions "topic" --court ca2` -- find relevant opinions
2. `cluster <ID>` -- get cluster details and sub-opinions
3. `citations <cluster_id>` -- see what it cites and what cites it
4. `resolve-cite "521 U.S. 702"` -- resolve a specific citation
