# Patents & Intellectual Property

Tools for patent search, inventor tracing, ownership chain analysis, and patent portfolio mapping.

**When to read this module:** When investigating patent holdings, IP transfers, inventor connections, or technology-related financial activity for any entity.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_patents.py` | USPTO Open Data Portal (ODP) API | `USPTO_API_KEY` in .env | Cache in `datasets/patents.db` | 60 req/min (peak), 120 off-peak |

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
