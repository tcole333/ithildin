# Patents & Intellectual Property

Tools for patent search, inventor tracing, ownership chain analysis, and patent portfolio mapping.

This module also covers trademark-register research for mark ownership and claimed goods and services.

**When to read this module:** When investigating patent holdings, IP transfers, inventor connections, or technology-related financial activity for any entity.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_patents.py` | USPTO Open Data Portal (ODP) API | `USPTO_API_KEY` in .env | Cache in `datasets/patents.db` | 60 req/min (peak), 120 off-peak |
| `query_trademarks.py` | USPTO Trademark Search register | None | None; supports saved JSON responses | ~1 request/sec |

Patents and trademarks are **different USPTO registers with different source tokens**. They are not
interchangeable: cite patent findings as `patents` and trademark-register findings as `trademarks`.

## query_patents.py — USPTO Patents

Searches patents via the USPTO Open Data Portal API (`api.uspto.gov`), traces ownership chains via the ODP assignment endpoint, and caches all results in a local SQLite database.

### Subcommands

```bash
# Full-text patent search
uv run python tools/query_patents.py search "machine learning fraud" --limit 10
uv run python tools/query_patents.py search "blockchain" --start 2020-01-01 --end 2024-01-01
uv run python tools/query_patents.py search "network security" --type Utility

# Find patents by inventor name
uv run python tools/query_patents.py inventor "Tim Draper"
uv run python tools/query_patents.py inventor "Jeffrey Epstein" --limit 50

# Find patents by assignee/company
uv run python tools/query_patents.py assignee "Apollo Global" --limit 50
uv run python tools/query_patents.py assignee "L Brands"

# Get detail for a specific patent
uv run python tools/query_patents.py patent 11234567
uv run python tools/query_patents.py patent US-11234567-B2

# Trace ownership chain (ODP assignment endpoint)
uv run python tools/query_patents.py assignments 11234567
uv run python tools/query_patents.py assignments 11234567 --since 2020-01-01

# Full patent portfolio for a company
uv run python tools/query_patents.py portfolio "L Brands" --limit 200
uv run python tools/query_patents.py portfolio "Apollo Global" --skip-assignments  # Faster

# Patent continuity (parent/child relationships)
uv run python tools/query_patents.py citations 11234567

# Match investigation entities against patent data
uv run python tools/query_patents.py enrich --dry-run
uv run python tools/query_patents.py enrich --threshold 85
```

All subcommands support `--output FILE` (JSON) and `--json` (stdout) flags.
Use `--force-refresh` to bypass the 30-day cache.

### Investigative Use Cases

- **Inventor tracing**: Find if persons of interest hold patents (indicates technical expertise, potential IP monetization schemes)
- **Ownership chains**: Track patent assignments to reveal shell company structures, IP warehousing, patent trolling activity
- **Portfolio analysis**: Map a company's technology footprint, identify divestitures that correlate with financial events
- **Security interests**: SECURITY INTEREST conveyances in assignment records indicate patents used as loan collateral -- investigatively significant
- **Continuity tracing**: Parent/child application relationships reveal continuation and divisional filing strategies
- **Entity enrichment**: Automatically match investigation entities against patent databases, discover unexpected IP holdings

### Data Source

**USPTO Open Data Portal API** (`api.uspto.gov/api/v1`):
- Unified API replacing the former PatentsView and Assignment APIs (both migrated March 2026)
- Application-centric: data organized by application number, not patent number
- The tool automatically resolves patent grant numbers to application numbers for detail/assignment lookups
- Patent search, inventor lookup, assignment history, continuity data
- 60 requests/minute (peak hours), 120 off-peak (10pm-5am EST)
- API key required: register at https://data.uspto.gov/myodp (requires ID.me verification)

### Local Database

Results are cached in `datasets/patents.db` (SQLite, WAL mode) with tables:
- `patents` -- patent detail (title, abstract, dates, CPC codes, application number)
- `inventors` -- inventor names and addresses per patent
- `assignees` -- assignee organizations per patent
- `assignments` -- ownership transfer chain records (reel/frame, assignor, assignee, conveyance type)
- `citations` -- patent-to-patent citation data

Cache TTL is 30 days. Use `--force-refresh` to re-fetch.

### Known Quirks

- ODP is **application-centric** -- the tool automatically resolves patent grant numbers to application numbers (adds 1 API call per lookup)
- Patent number formats vary widely; the tool normalizes automatically (strips US prefix, kind codes, commas)
- Portfolio `--skip-assignments` is recommended for companies with 50+ patents to avoid long assignment sweeps
- Assignment API response format can be inconsistent; the tool handles multiple response shapes
- `citations` subcommand returns continuity data (parent/child apps), not prior-art citations -- prior-art citations require bulk PatentsView data (not yet available via ODP API)
- ODP only covers applications filed on or after January 1, 2001
- Env var: accepts both `USPTO_API_KEY` and `PATENTSVIEW_API_KEY` (legacy)

## query_trademarks.py — USPTO Trademarks

Searches the public USPTO trademark register for exact wordmarks, owner blocks, serial numbers, and
goods-and-services claims. Unlike the patent ODP API, this source requires no API key and does not use
the patents cache. Use source token **`trademarks`** when creating a finding.

### Subcommands

```bash
# Exact-phrase wordmark search (the default)
uv run python tools/query_trademarks.py mark "HC STANDARD"
uv run python tools/query_trademarks.py mark "HC STANDARD" --include-pseudo

# Opt in to the trademark site's broad OR-style word search
uv run python tools/query_trademarks.py mark "HC STANDARD" --loose

# Find marks associated with an owner, including historical owner blocks
uv run python tools/query_trademarks.py owner "Global Emergency Resources"

# Fetch by serial number or search claimed capabilities
uv run python tools/query_trademarks.py serial 85877492
uv run python tools/query_trademarks.py goods "asset tracking" --live-only --class 042

# Parse a saved API response without making a request
uv run python tools/query_trademarks.py mark "HC STANDARD" --from-file saved-response.json
```

All subcommands support `--limit`, `--all-pages` (capped at 20 pages), `--live-only` / `--dead-only`,
`--class`, `--output FILE`, `--json`, and `--from-file PATH`. Live paging is limited to about one
request per second.

### Investigative Use and Query Behavior

- **Ownership transfers**: The tool preserves and prints every `ownerFullText` entry. A record may
  contain both `(REGISTRANT)` and `(LAST LISTED OWNER)` lines; retaining both is essential for tracing
  an assignment or ownership chain.
- **Owner portfolios**: `owner` phrase-matches the full owner block to answer which marks a company
  owns or previously owned.
- **Capability claims**: `goods` phrase-matches goods-and-services text to identify entities claiming
  a product or service capability.
- **Null findings**: A valid empty response prints `0 results.` and exits successfully.

The site's default loose query OR-matches words. A bare multi-word search can therefore return tens of
thousands of irrelevant hits. `query_trademarks.py mark` instead defaults to `match_phrase` on the
wordmark field; use `--loose` only when that broader matching is intentional.

### Data Source and Known Quirks

- Endpoint: `POST https://tmsearch.uspto.gov/prod-v1-0-0/tmsearch`, with raw Elasticsearch DSL
- Response records are under `hits.hits[].source`, not Elasticsearch's usual `_source`
- `id` is the trademark serial number; `registrationId` is the registration number
- `alive` distinguishes live from dead or abandoned marks
- `internationalClass` values are formatted like `IC 042`
- The endpoint may return HTML when a request is blocked; the tool reports that condition rather than
  trying to parse it as JSON
