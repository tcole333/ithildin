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

## Protocol

1. Unified search across all ingested registries
2. Officer name search (finds entities where person serves)
3. Address search (finds entity clusters at shared addresses)
4. UCC filing search (liens, secured transactions)
5. For specific entities found, pull full details + filings from the state registry

```bash
uv run python tools/query_registry.py search "ENTITY" --output $WORKDIR/registry-search.json
uv run python tools/query_registry.py officers "PERSON" --output $WORKDIR/registry-officers.json
uv run python tools/query_registry.py address "ADDRESS" --output $WORKDIR/registry-addr.json
uv run python tools/query_registry.py ucc-search "TARGET" --output $WORKDIR/ucc-search.json
# State-specific deep dive:
uv run python tools/query_florida_corps.py ingest-search "ENTITY" --output $WORKDIR/registry-fl.json
uv run python tools/query_ny_corps.py search "ENTITY" --output $WORKDIR/registry-ny.json
```

## What To Look For

- **Officer networks**: Same person serving as officer across multiple entities
- **Address clusters**: Multiple entities at the same registered address (shell company indicators)
- **Registered agent patterns**: Shared agents link otherwise disconnected entities (filter mass-market agents like CT Corp, CSC)
- **Formation date clustering**: Entities formed the same week by the same agent
- **Status changes**: Active → Dissolved timing relative to investigation events
- **Jurisdiction shopping**: Why was THIS state chosen? (Delaware for liability shield, USVI for tax benefits, etc.)

## Output

`--output $WORKDIR/<prefix>-registry-*.json`

## Findings

- Registry filings: `claim_type=direct_quote` (government records are primary sources)
- Officer network analysis: `claim_type=inference`
- `--sources registry` (or `--sources fl_sunbiz ny_dos` for state-specific)
