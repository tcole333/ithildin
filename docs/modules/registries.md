# Corporate Registries

Tools for corporate entity search, officer lookup, and ownership tracing across 25+ jurisdictions.

**When to read this module:** When running /trace-entity, investigating corporate structures, or tracing shell companies.

## Tool Inventory

| Tool | Jurisdiction | Method | Auth | Data |
|------|-------------|--------|------|------|
| `query_registry.py` | All ingested | Local SQLite (registry.db) | None | Unified search across all ingested entities, officers, agents, UCC filings |
| `ingest_florida.py` | FL | SFTP bulk (fixed-width) | Public creds | 3M+ entities, officers, agents, filings |
| `query_california.py` | CA | Web scraping (bizfileonline) | MCP Playwright | Entity search, detail, history (Imperva WAF) |
| `ingest_california.py` | CA | Azure APIM REST API | CA_SOS_API_KEY (free) | Keyword search, entity detail, ingest to registry.db |
| `ingest_newyork.py` | NY | Socrata SODA API (data.ny.gov) | None | 4.1M active corps, 20M filings, 17M addresses |
| `query_texas.py` | TX | Comptroller data-search proxy | None | Franchise tax entities, officers, agents |
| `query_michigan.py` | MI | LARA portal API (Cloudflare WAF) | Node.js browser helper | Entities, officers via browser bypass |
| `query_newjersey.py` | NJ | HTML form scraping | None | Name/ID search only (no officers in free portal) |
| `query_massachusetts.py` | MA | ASP.NET WebForms (Imperva WAF) | Node.js browser helper | Entity, officers, agent, name changes |
| `query_nevada.py` | NV | SilverFlume portal (Incapsula WAF) | Node.js browser helper | Officers, agents, stock info, filing history |
| `query_wyoming.py` | WY | WyoBiz ASP.NET (F5 WAF + CAPTCHA) | Node.js browser helper | Key crypto-LLC state; parties, agents, filings |
| `query_tennessee_corps.py` | TN | TNCaB portal (Cloudflare Turnstile) | Node.js browser helper | Officers, agents, filings, standing |
| `query_puertorico.py` | PR | REST API (rceapi.estado.pr.gov) | None | Act 60 entities; officers, agents, articles, filings |
| `ingest_newmexico.py` | NM | REST API (enterprise.sos.nm.gov) | None | Entity search/detail/history (Azure WAF, 3-5s delays) |
| `ingest_dc.py` | DC | ArcGIS FeatureServer + CorpOnline API | None | 492K entities; principals, directors, NAICS |
| `ingest_colorado.py` | CO | Socrata SODA API (data.colorado.gov) | None | 1.3M+ entities since 1864 |
| `ingest_maryland.py` | MD | Web scraping (egov.maryland.gov) | MCP Playwright + manual CAPTCHA | Officers, agent, addresses (reCAPTCHA v2) |
| `ingest_ohio.py` | OH | SOS Business Search API (Cloudflare) | cf_clearance cookie | Entity, agent, organizer search; filing history |
| `ingest_usvi.py` | USVI | Catalyst portal scraping | None | No officers without paid cert request |
| `ingest_panama.py` | PA | ICIJ + OCCRP Aleph + PANADATA | PANADATA optional ($0.50/lookup) | ~800K entities across 3 sources |
| `query_delaware.py` | DE | OpenCorporates API | OPENCORPORATES_API_KEY | Search, entity, filings, batch |
| `query_hongkong.py` | HK | OpenCorporates API (ICRIS) | OPENCORPORATES_API_KEY | Search, entity, filings, batch |
| `query_cyprus.py` | CY | OpenCorporates API | OPENCORPORATES_API_KEY | Offshore hub; search, entity, filings |
| `query_opencorporates.py` | 160+ | OpenCorporates API | OPENCORPORATES_API_KEY | Global search, officers, addresses, filings, statements |
| `query_france.py` | FR | SIRENE API (gouv.fr) | None | SIREN/SIRET, dirigeants, activity codes |
| `query_israel.py` | IL | data.gov.il CKAN API | None | 720K+ companies (Hebrew + English) |
| `query_zefix.py` | CH | SPARQL (lindas.admin.ch) | None | All Swiss companies, foundations, associations |
| `ingest_uk_companies_house.py` | UK | REST API | COMPANIES_HOUSE_API_KEY (free) | Officers, PSC, filings, officer-search |
| `ingest_ucc_florida.py` | FL (UCC) | SFTP bulk (fixed-width) | Public creds | Federal tax liens (~99% IRS); NOT commercial UCC |
| `ingest_ucc_newmexico.py` | NM (UCC) | REST API (enterprise.sos.nm.gov) | None | Debtor/secured party search, filing detail |

## Unified Interface: `query_registry.py`

Prefer this tool over jurisdiction-specific tools. Searches all previously ingested data in `registry.db`.

### Subcommands

```bash
# Entity search (FTS5 full-text search across all jurisdictions)
uv run python tools/query_registry.py search "Financial Trust" --jurisdiction fl --limit 20
uv run python tools/query_registry.py search "LSJE" --exact

# Entity detail (by registry.db internal ID)
uv run python tools/query_registry.py entity 42

# Officer search (cross-jurisdiction)
uv run python tools/query_registry.py officers "Darren Indyke" --limit 20

# Address search (principal + mailing addresses)
uv run python tools/query_registry.py address "457 Madison" --limit 20

# Registered agent search
uv run python tools/query_registry.py agent "CT Corporation" --limit 20

# Filing history for an entity
uv run python tools/query_registry.py filings 42 --limit 50

# UCC filing search (debtors + secured parties)
uv run python tools/query_registry.py ucc-search "Epstein" --jurisdiction fl --role debtor
uv run python tools/query_registry.py ucc-filing 123
uv run python tools/query_registry.py ucc-collateral "aircraft"
uv run python tools/query_registry.py ucc-party "Wells Fargo" --role secured

# Stats and metadata
uv run python tools/query_registry.py stats
uv run python tools/query_registry.py jurisdictions
uv run python tools/query_registry.py ucc-stats
```

## When to Use State-Specific Tools

Use jurisdiction-specific tools when you need to:
1. **Ingest new data** into registry.db (`ingest-entity`, `ingest-batch`, `ingest-search`)
2. **Access live/fresh data** not yet in registry.db
3. **Use jurisdiction-specific features** (e.g., PR articles of incorporation, NY address datasets, NV stock info)

### Common Patterns Across State Tools

Most state tools share these subcommands:
```bash
search "QUERY"                 # Search by entity name
entity <ID>                    # Get entity detail
ingest <ID>                    # Ingest single entity into registry.db
ingest-search "QUERY"         # Search + ingest all results
ingest-batch "QUERY"          # Same as ingest-search (naming varies)
```

## Auth Requirements Summary

| Requirement | Tools |
|------------|-------|
| **None** | query_registry, query_texas, query_newjersey, query_puertorico, ingest_newyork, ingest_colorado, ingest_newmexico, ingest_dc, query_france, query_israel, query_zefix |
| **Free API key** | ingest_california (CA_SOS_API_KEY), ingest_uk_companies_house (COMPANIES_HOUSE_API_KEY) |
| **Paid API key** | query_opencorporates, query_delaware, query_hongkong, query_cyprus (OPENCORPORATES_API_KEY — basic 500/mo, 200/day) |
| **Node.js browser helper** | query_michigan, query_massachusetts, query_nevada, query_wyoming, query_tennessee_corps |
| **MCP Playwright** | query_california (WAF bypass), ingest_maryland (CAPTCHA) |
| **Manual CAPTCHA** | ingest_maryland (reCAPTCHA v2 on first search), ingest_ohio (cf_clearance cookie) |

## Known Quirks

- **query_california.py** (web scraper): Imperva WAF blocks after first request per session. Unreliable for batch ops. Prefer `ingest_california.py` with API key.
- **ingest_florida.py**: Fixed-width COBOL-era format (1440 chars/record). SFTP creds are public: `Public / PubAccess1845!`
- **ingest_newyork.py**: Three separate Socrata datasets. Officer names are in the filings dataset, not the main entity dataset.
- **query_newjersey.py**: Free portal exposes only 5 fields (name, ID, city, type, date). No officers/agents. Paid portal has more but requires account.
- **ingest_usvi.py**: Officers/directors are NOT available without paying for a certificate request. Only basic entity info is public.
- **ingest_panama.py**: Combines 3 sources (ICIJ ~200K, OCCRP ~600K, PANADATA live). Direct registry scraping impossible (Blazor WebSocket).
- **query_opencorporates.py**: Basic tier has 500 calls/month, 200/day max. Use `account-status` to check remaining credits.
- **ingest_ucc_florida.py**: Despite the name, this is federal lien data (IRS), NOT commercial UCC Article 9. Commercial UCC is at floridaucc.com (separate system).
- **ingest_ohio.py**: Requires manually obtaining a cf_clearance cookie from Chrome DevTools. Cookie expires frequently.
- **ingest_newmexico.py / ingest_ucc_newmexico.py**: Azure WAF requires 3-5 second delays between requests.
- **query_wyoming.py**: Requires `warmup` subcommand before first search to establish session through F5 WAF.

## Skills That Use These Tools

| Skill | How It Uses Registries |
|-------|----------------------|
| `/trace-entity` | Primary consumer. Searches unified registry, then fans out to jurisdiction-specific tools for live data and ingest. |
| `/deep-investigate` | Agent B traces corporate structures. Uses query_registry for known entities, state tools for new ingests. |
| `/landscape-scan` | Broad entity search across multiple jurisdictions to map organizational footprints. |

## Investigation Patterns

### Shell Company Tracing
1. Start with `query_registry.py search "Entity Name"` to check all ingested jurisdictions
2. Use `officers` to find who controls the entity
3. Search those officer names back through `officers` to find other entities they control
4. Use `agent` to find shared registered agents (common shell pattern: same agent across dozens of entities)
5. Use `address` to find entities sharing a principal address

### Cross-Jurisdiction Mapping
1. Search unified registry to see where an entity is registered
2. For each jurisdiction hit, use the state-specific tool to get live data and ingest it
3. Check `query_opencorporates.py` for jurisdictions not yet ingested locally
4. Use `query_opencorporates.py officers "Person Name"` for global officer search

### Offshore Structure Identification
1. Check USVI (`ingest_usvi.py`) for VI-registered entities
2. Search Panama (`ingest_panama.py`) across ICIJ and OCCRP datasets
3. Check Cyprus (`query_cyprus.py`) for Russian-linked structures
4. Check Hong Kong (`query_hongkong.py`) for Asia-Pacific structures
5. Use UK Companies House (`ingest_uk_companies_house.py`) PSC endpoint for persons of significant control

### UCC/Lien Research
1. Search unified UCC: `query_registry.py ucc-search "Entity" --role debtor`
2. Check collateral descriptions: `ucc-collateral "aircraft"` or `"all assets"`
3. For Florida: note that `ingest_ucc_florida.py` covers federal liens (IRS), NOT commercial UCC
4. For New Mexico: `ingest_ucc_newmexico.py` covers both debtor and secured party search

## Database Schema

All state tools ingest into a shared `registry.db` with unified tables:
- `registry_entities` — one row per corporate entity (name, type, status, addresses, EIN)
- `registry_officers` — officers/directors/managers with addresses and dates
- `registry_agents` — registered agents with address history
- `registry_filings` — filing/event history (annual reports, amendments, dissolutions)
- `registry_name_history` — tracks name changes over time
- `ucc_filings` / `ucc_debtors` / `ucc_secured_parties` / `ucc_collateral` — UCC/lien data

FTS5 full-text search indexes cover entity names, officer names, agent names, and addresses for fast cross-jurisdiction queries via `query_registry.py`.
