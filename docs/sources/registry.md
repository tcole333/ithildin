# Corporate Registry (Unified)

**URL:** Various state/country registries
**Jurisdiction:** FL, NY, CA, TX, MI, MA, NJ, NM, CO, DC, USVI, Panama, UK, France, CH, OpenCorporates (DE/HK/CY)
**Auth:** None for most; API keys for UK Companies House, OpenCorporates
**Tool:** `tools/query_registry.py` (unified), `tools/query_<state>_corps.py` (per-state)
**Citation prefix:** `REGISTRY:<STATE>:<ENTITY_ID>`

## Access

- **Method:** Mixed (web scrape, API, bulk download depending on state)
- **Rate limits:** Varies by state; be respectful (1-2 req/sec for scraped sources)
- **Cost:** Free for most; OpenCorporates is paid (500 calls/month, 200/day)
- **Coverage dates:** Varies; most states back to 1990s+

## Local Database

All ingested registry data lands in `registry.db` (SQLite):
- `registry_entities`: 86K+ entities (name, type, status, jurisdiction, filing date)
- `registry_officers`: 255K+ officers (name, title, address)
- `registry_filings`: 98K+ filings (annual reports, amendments)

## Schema (Unified)

| Field | Type | Description |
|-------|------|-------------|
| entity_id | string | State-specific entity ID |
| name | string | Entity legal name |
| entity_type | string | LLC, Corp, LP, etc. |
| status | string | Active, Inactive, Dissolved |
| jurisdiction | string | State/country code |
| formation_date | date | Date of formation/registration |
| registered_agent | string | Agent name + address |
| officers | array | Name, title, address |

## Subcommands

```bash
# Unified cross-registry search
uv run python tools/query_registry.py search "ENTITY NAME"
uv run python tools/query_registry.py officers "PERSON NAME"
uv run python tools/query_registry.py address "ADDRESS"

# Per-state (example: Florida)
uv run python tools/query_florida_corps.py search "ENTITY NAME"
uv run python tools/query_florida_corps.py entity FL_ID
uv run python tools/query_florida_corps.py ingest FL_ID
uv run python tools/query_florida_corps.py ingest-search "ENTITY NAME"
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| Entity Resolution | Officer names | Deduplicate across jurisdictions |
| OpenSanctions | Entity/officer names | Sanctions screening |
| SEC EDGAR | Entity name | Public company filing cross-ref |
| USAspending | Entity name / address | Government contractor check |
| FEC | Officer names | Political donation mapping |
| FDIC BankFind | Entity name | Bank institution verification |
| ACRIS | Entity name / address | NYC property ownership |

## Known Issues

- Scraping-based registries (FL, NY) may break on site changes
- Officer name formatting varies wildly between states
- Some states don't expose officer data via public search
- OpenCorporates has strict rate limits (500/month on basic tier)
- Panama registry returns Spanish-language results
- UK Companies House requires base64-encoded API key in Basic auth header

## Example Queries

```bash
# Search across all ingested registries
uv run python tools/query_registry.py search "Financial Trust Company"

# Find all entities with a specific officer
uv run python tools/query_registry.py officers "John Smith"

# Ingest a Florida entity into registry.db
uv run python tools/query_florida_corps.py ingest-search "Southern Trust"
```
