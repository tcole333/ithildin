# Political & Regulatory Data

Tools for campaign finance, lobbying disclosures, foreign agent registrations, congressional records, and financial disclosures.

**When to read this module:** When investigating political connections, campaign donors, lobbying relationships, foreign influence, or government appointee finances.

## Tool Inventory

| Tool | Source | Auth | Rate Limit | Data |
|------|--------|------|------------|------|
| `query_fec.py` | FEC API (api.open.fec.gov) | FEC_API_KEY (free, falls back to DEMO_KEY) | Cursor-paginated, 100/page | Contributions, disbursements, independent expenditures, committees, candidates |
| `query_lobbying.py` | Senate LDA API (lda.senate.gov) | None | 25/page, generally responsive | Registrations, LD-2 activity reports, LD-203 contribution reports |
| `query_fara.py` | efile.fara.gov bulk CSV | None | 5 req/10 sec | Registrants, foreign principals, short forms, document URLs |
| `query_congress.py` | Congress.gov API (api.congress.gov) | CONGRESS_API_KEY (free) | 5,000/hour | Members, committees, nominations, committee reports, CRS |
| `query_govinfo.py` | GovInfo / GPO (api.govinfo.gov) | GOVINFO_API_KEY (free, falls back to DEMO_KEY) | ~1,000/hour (DEMO_KEY) | Hearings (CHRG), committee reports (CRPT), GAO reports, CRS, bills |
| `ingest_propublica_disclosures.py` | ProPublica Trump Team Disclosures | None (web scrape) | 1 req/sec (polite) | 1,573 appointees, 3,196 documents, 116,699 assets |

## Subcommands and Examples

### `query_fec.py` — FEC Campaign Finance

```bash
# Schedule A: Contributions/receipts
uv run python tools/query_fec.py donor "Leon Black" --limit 50
uv run python tools/query_fec.py donor "Black" --employer "Apollo" --limit 10
uv run python tools/query_fec.py donor "Epstein" --min-amount 1000
uv run python tools/query_fec.py employer "Gratitude America"
uv run python tools/query_fec.py address "10021" --name "Epstein"
uv run python tools/query_fec.py recipient C00580100 --cycle 2018

# Schedule B: Disbursements (where money went)
uv run python tools/query_fec.py disbursements C00916114 --limit 200
uv run python tools/query_fec.py disbursements C00916114 --recipient "Summit Ridge"
uv run python tools/query_fec.py disbursements C00916114 --min-amount 50000

# Schedule E: Independent expenditures (support/oppose ads)
uv run python tools/query_fec.py ie C00916114 --limit 200
uv run python tools/query_fec.py ie C00916114 --support-oppose S
uv run python tools/query_fec.py ie C00916114 --candidate P80001571

# Committee financial summary
uv run python tools/query_fec.py totals C00916114
uv run python tools/query_fec.py totals C00916114 --cycle 2024

# Lookups
uv run python tools/query_fec.py committee C00916114
uv run python tools/query_fec.py candidate "Gonzalez"
uv run python tools/query_fec.py batch-persons
```

### `query_lobbying.py` — Senate LDA Lobbying

```bash
# Search by client (who hired the lobbyist)
uv run python tools/query_lobbying.py client "International Peace Institute"

# Search by registrant (lobbying firm)
uv run python tools/query_lobbying.py registrant "Epstein"

# Search by individual lobbyist
uv run python tools/query_lobbying.py lobbyist "Weingarten"

# Detailed filing search (LD-2 activity reports)
uv run python tools/query_lobbying.py filings --client "International Peace Institute" --type ld2

# LD-203 contribution reports
uv run python tools/query_lobbying.py contributions "International Peace Institute"
```

### `query_fara.py` — Foreign Agent Registration

```bash
# First-time setup: download and ingest bulk CSVs
uv run python tools/query_fara.py download
uv run python tools/query_fara.py ingest

# Search registrants, foreign principals, short forms
uv run python tools/query_fara.py search "Epstein"
uv run python tools/query_fara.py search "International Peace"

# Filter by foreign principal country
uv run python tools/query_fara.py country "Norway"
uv run python tools/query_fara.py country "Israel"

# Registration detail
uv run python tools/query_fara.py detail 1234
```

### `query_congress.py` — Congress.gov

```bash
# Full-text search (delegates to GovInfo for bill text)
uv run python tools/query_congress.py search "corporate transparency"

# Member lookup
uv run python tools/query_congress.py member "Warren"

# Committee information
uv run python tools/query_congress.py committee SSGA

# Committee reports by congress and type
uv run python tools/query_congress.py committee-reports --congress 118 --report-type SRPT

# Presidential nominations
uv run python tools/query_congress.py nominations --congress 118 --limit 10

# CRS (Congressional Research Service) reports
uv run python tools/query_congress.py crs "beneficial ownership"
```

### `query_govinfo.py` — GovInfo / GPO

```bash
# Search within specific collections
uv run python tools/query_govinfo.py search "Deutsche Bank" --collection CHRG
uv run python tools/query_govinfo.py search "shell companies" --collection GAOREPORTS --limit 10
uv run python tools/query_govinfo.py search "beneficial ownership" --collection CRS

# Get document metadata
uv run python tools/query_govinfo.py document GOVPUB-Y4_J89_2-PURL-LPS113630

# Hearing detail (witness list, testimony text)
uv run python tools/query_govinfo.py hearing GOVPUB-Y4_J89_2-PURL-LPS113630

# Ingest document text into investigation.db
uv run python tools/query_govinfo.py ingest GOVPUB-Y4_J89_2-PURL-LPS113630

# Search + ingest in one step
uv run python tools/query_govinfo.py ingest-search "Epstein" --collection CHRG --limit 5
```

Available collections: `BILLS`, `CHRG` (hearings, 1997+), `CRPT` (committee reports), `GAOREPORTS`, `CPRT`, `CDOC`, `USCOURTS`.

### `ingest_propublica_disclosures.py` — Financial Disclosures

```bash
# Browse agencies with appointees
uv run python tools/ingest_propublica_disclosures.py agencies

# Search appointees and assets
uv run python tools/ingest_propublica_disclosures.py search "Palantir"

# Get specific appointee data
uv run python tools/ingest_propublica_disclosures.py appointee feinberg-stephen-andrew

# Ingest appointee into investigation.db
uv run python tools/ingest_propublica_disclosures.py ingest feinberg-stephen-andrew

# Scan for entities matching investigation targets
uv run python tools/ingest_propublica_disclosures.py scan-entities

# Database stats
uv run python tools/ingest_propublica_disclosures.py stats
```

## Auth Requirements

| Tool | Variable | How to Get |
|------|----------|-----------|
| `query_fec.py` | `FEC_API_KEY` | Free at [api.data.gov](https://api.data.gov/signup/). Falls back to `DEMO_KEY` (very limited). |
| `query_lobbying.py` | None | No auth required. |
| `query_fara.py` | None | Bulk CSV downloads, no auth. Rate limit: 5 req/10 sec. |
| `query_congress.py` | `CONGRESS_API_KEY` | Free at [api.congress.gov/sign-up](https://api.congress.gov/sign-up/). Required. |
| `query_govinfo.py` | `GOVINFO_API_KEY` | Free at [api.data.gov](https://api.data.gov/signup/). Falls back to `DEMO_KEY`. |
| `ingest_propublica_disclosures.py` | None | Web scraping of ProPublica's SvelteKit app. Rate: 1 req/sec. |

## Known Quirks

- **query_fec.py**: Multiple people share common names. Always cross-reference employer, address, and occupation to disambiguate. Pagination is cursor-based (last_indexes), not page numbers.
- **query_lobbying.py**: API migrating to LDA.gov by 06/30/2026. Current endpoint may break after that date. Responses sometimes gzip-compressed even when not requested.
- **query_fara.py**: Requires two-step setup (`download` then `ingest`). CSV files are ISO-8859-1 encoded, not UTF-8. Data stored locally in investigation.db after ingest.
- **query_congress.py**: Bill search and CRS search delegate to GovInfo (full-text search). Built-in 0.3s rate-limit delay between requests.
- **query_govinfo.py**: The `/search` endpoint requires POST with JSON body (not GET). Collection filtering uses query string syntax: `"Deutsche Bank collection:CHRG"`. Built-in 0.5s rate-limit delay.
- **ingest_propublica_disclosures.py**: Parses SvelteKit's compact `__data.json` format with pointer-based node references. Cache stored at `/tmp/propublica-cache`. Covers Trump administration appointees (1,573 people, 116K assets).

## Skills That Use These Tools

| Skill | How It Uses Political Data |
|-------|---------------------------|
| `/deep-investigate` | Agent B checks FEC contributions, lobbying registrations, and FARA filings for investigated persons. |
| `/investigate-person` | Pulls donor history, lobbying connections, congressional testimony mentions, and financial disclosures. |
| `/audit-contracts` | Cross-references contractor political donations (FEC) with contract awards; checks lobbying for contract-related issues. |

## Investigation Patterns

### Follow the Money
1. Start with `query_fec.py donor "Name"` to get contribution history
2. Check `employer` field to identify corporate affiliations
3. Use `recipient` to see which committees received money
4. Check `disbursements` on those committees to see where money went
5. Cross-reference with `query_lobbying.py` to find lobbying relationships

### Foreign Influence Trace
1. Search `query_fara.py` for person/organization name
2. Check `country` to see which foreign principals are involved
3. Use `query_lobbying.py` to find domestic lobbying by same registrants
4. Check `query_congress.py` for related hearings or legislation

### Appointee Asset Mapping
1. Use `ingest_propublica_disclosures.py search "Company"` to find appointees with ties
2. Get full asset list with `appointee <slug>`
3. Cross-reference assets with corporate registry data for ownership structures
