# Network Mapping & Sanctions

Tools for relationship mapping, offshore entity tracing, sanctions screening, corporate hierarchy resolution, and cross-system entity interop.

**When to read this module:** When running /trace-entity, /systemic-analysis, /deep-investigate (Agent D), or investigating international networks, sanctions compliance, and corporate ownership chains.

## Tool Inventory

| Tool | Data Source | Auth | Size |
|------|-----------|------|------|
| `query_littlesis.py` | LittleSis power network | None | 500K+ relationships |
| `query_icij.py` | ICIJ Offshore Leaks (official reconciliation API + node pages) | None | 810K+ records; local Neo4j optional for deeper traversal |
| `query_opencorporates.py` | OpenCorporates global registry | `OPENCORPORATES_API_KEY` | 200M+ companies |
| `query_opensanctions.py` | OpenSanctions bulk data | None (local DB) | 4.1M entities |
| `query_gleif.py` | GLEIF Legal Entity Identifiers | None | 2M+ LEIs |
| `query_fincen.py` | FinCEN Files (ICIJ release) | None (local CSV) | 4.5K transactions, 5.5K connections |
| `ftm_bridge.py` | FollowTheMoney schema interop | None (local) | N/A (bridge) |
| `ingest_bic.py` | SWIFT BIC directory | None (local DB) | 32K+ BIC codes |

## Subcommands & Examples

### query_littlesis.py -- Power Network Mapping

LittleSis maps who-knows-who at the heights of business and government. JSON:API 2.0 format.

```bash
uv run python tools/query_littlesis.py search "Jeffrey Epstein"
uv run python tools/query_littlesis.py entity 36043                         # Epstein = 36043
uv run python tools/query_littlesis.py relationships 36043                  # All relationships
uv run python tools/query_littlesis.py relationships 36043 --category 5     # Donations only
uv run python tools/query_littlesis.py relationships 36043 --sort amount    # By dollar amount
uv run python tools/query_littlesis.py connections 36043 --category 1       # Position connections
uv run python tools/query_littlesis.py batch 36043,12345,67890              # Batch entity fetch
```

Category IDs: 1=Position, 2=Education, 3=Membership, 4=Family, 5=Donation, 6=Transaction, 7=Lobby, 8=Social, 9=Professional, 10=Ownership, 11=Hierarchy, 12=Generic.

**Auth:** None required. Retry with backoff on 503 (LittleSis is aggressive with rate limiting -- 3s, 6s, 9s waits).

### query_icij.py -- ICIJ Offshore Leaks

Official remote access to more than 810,000 offshore records from the Panama
Papers, Paradise Papers, Pandora Papers, Bahamas Leaks, and Offshore Leaks.
Bounded name matching uses ICIJ's reconciliation API; entity properties and
first-hop relationships come from the graph embedded in the public node page.

```bash
# Default: official remote API/public node pages (no local service)
uv run python tools/query_icij.py search "Jeffrey Epstein"
uv run python tools/query_icij.py search "Liquid Funding" --type Entity
uv run python tools/query_icij.py entity 82004676
uv run python tools/query_icij.py connections 82004676
uv run python tools/query_icij.py officers 82004676

# Explicit reconciliation and batch matching
uv run python tools/query_icij.py reconcile "Financial Trust Company"
uv run python tools/query_icij.py reconcile-all --threshold 85
uv run python tools/query_icij.py reconcile-all --create-leads --threshold 85

# Optional local Neo4j only for deeper/bulk traversal
./scripts/start_icij_db.sh
uv run python tools/query_icij.py connections 82004676 --depth 2 --local
```

| Subcommand | Requires Neo4j | Description |
|------------|---------------|-------------|
| `search` | No | Reconcile by name across Entity, Officer, Intermediary types |
| `entity` | No | Get a numeric node ID's properties from its public page |
| `connections` | No for depth 1 | First-hop graph; `--local` required for deeper traversal |
| `officers` | No | Officers/directors in a numeric or exact-name entity's first hop |
| `reconcile` | No | Match a single name against ICIJ Reconciliation API |
| `reconcile-all` | No | Batch reconcile all investigation.db entities |

**Auth:** None. Remote queries are bounded: reconciliation returns at most 25
candidates and node pages are capped at 5 MB. Connections refuse unconfirmed
fuzzy-name traversal; review `search` output and pass a numeric node ID. Local
Neo4j at `bolt://localhost:7689` is optional and only needed with `--local`.

### query_opencorporates.py -- Global Corporate Registry

Searches 200M+ companies across 160+ jurisdictions. API v0.4.

```bash
uv run python tools/query_opencorporates.py search "Excession LLC"
uv run python tools/query_opencorporates.py search "Excession LLC" --jurisdiction us_tx
uv run python tools/query_opencorporates.py search "Excession LLC" --country us
uv run python tools/query_opencorporates.py officers "Elon Musk"
uv run python tools/query_opencorporates.py officers "Jared Birchall" --jurisdiction us_tx
uv run python tools/query_opencorporates.py address "865 FM 1209, Bastrop"
uv run python tools/query_opencorporates.py entity us_tx 0804842786
uv run python tools/query_opencorporates.py filings us_tx 0804842786
uv run python tools/query_opencorporates.py statements us_de 12345678
uv run python tools/query_opencorporates.py account-status
```

| Subcommand | Description |
|------------|-------------|
| `search` | Company name search with jurisdiction/country/address filters |
| `officers` | Officer/director name search with jurisdiction filter |
| `address` | Search by registered address (loose match) |
| `entity` | Full company details by jurisdiction + company number |
| `filings` | Corporate filings for a company |
| `statements` | Data statements for a company |
| `account-status` | Check API quota remaining |

**Auth:** Requires `OPENCORPORATES_API_KEY` in `.env`. Basic tier: 500 calls/month, 200/day max. Rate limit: 0.5s between requests. Some endpoints require paid plans (403 error).

### query_opensanctions.py -- Sanctions, PEPs & Debarment

Bulk NDJSON ingested into local SQLite with FTS5. Covers OFAC, EU, UN sanctions; PEP databases (200+ countries); crime and terrorism lists.

```bash
# Setup (one-time)
uv run python tools/query_opensanctions.py download                     # Default dataset
uv run python tools/query_opensanctions.py download --dataset sanctions  # Sanctions only
uv run python tools/query_opensanctions.py download --dataset peps       # PEPs only
uv run python tools/query_opensanctions.py ingest

# Search
uv run python tools/query_opensanctions.py search "Oleg Deripaska"
uv run python tools/query_opensanctions.py search "Deripaska" --schema Person --topic sanction
uv run python tools/query_opensanctions.py search "DP World" --schema Company --country ae
uv run python tools/query_opensanctions.py entity ofac-12345
uv run python tools/query_opensanctions.py pep-check "Ehud Barak"

# Cross-reference with investigation
uv run python tools/query_opensanctions.py match-entities
uv run python tools/query_opensanctions.py stats
```

Schemas: `Person`, `Company`, `Organization`, `LegalEntity`, `Vessel`, `Aircraft`, `CryptoWallet`, `Security`.
Topics: `sanction`, `debarment`, `crime`, `pep`, `poi`.

**Auth:** None (uses bulk download). DB path: `datasets/opensanctions.db`.

### query_gleif.py -- Legal Entity Identifiers

Maps corporate parent-subsidiary hierarchies for regulated financial entities. No auth required.

```bash
uv run python tools/query_gleif.py search "Apollo Global"
uv run python tools/query_gleif.py search "JPMorgan" --country US --limit 10
uv run python tools/query_gleif.py entity 54930054P2G7ZJB0KM79          # Apollo
uv run python tools/query_gleif.py parents 54930054P2G7ZJB0KM79         # Direct parents
uv run python tools/query_gleif.py children 54930054P2G7ZJB0KM79        # Direct subsidiaries
uv run python tools/query_gleif.py hierarchy 54930054P2G7ZJB0KM79       # Full ownership tree
uv run python tools/query_gleif.py cross-ref                             # Cross-ref with investigation CIKs
```

| Subcommand | Description |
|------------|-------------|
| `search` | Search entities by name, optionally filtered by country |
| `entity` | Full LEI record details |
| `parents` | Direct parent entities (ultimate and direct) |
| `children` | Direct child/subsidiary entities |
| `hierarchy` | Full ownership tree traversal |
| `cross-ref` | Match investigation.db entities against GLEIF records |

**Auth:** None. Rate limit: 60 req/min (1 req/sec enforced). API uses JSON:API format (`Accept: application/vnd.api+json`).

### query_fincen.py -- FinCEN Files

ICIJ's public release of metadata from ~2,100 Suspicious Activity Reports. Two CSV datasets covering $35B+ in flagged transactions (2000-2017).

**IMPORTANT: This dataset contains only INSTITUTIONAL names (banks, financial firms). Individual person names are NOT searchable here.** Searching for "John Smith" will return 0 results -- this is correct behavior, not a bug.

```bash
uv run python tools/query_fincen.py download                           # Download and cache
uv run python tools/query_fincen.py search "Deutsche Bank"             # Search both datasets
uv run python tools/query_fincen.py search-tx "Deutsche Bank"          # Transactions only
uv run python tools/query_fincen.py search-connections "Deutsche Bank"  # Bank connections only
uv run python tools/query_fincen.py filer "Deutsche Bank"              # Filter by filing bank
uv run python tools/query_fincen.py country "SGP"                      # Filter by country ISO
uv run python tools/query_fincen.py sar 3297                           # Specific SAR by ID
uv run python tools/query_fincen.py stats
```

**Auth:** None (public dataset). Data cached at `datasets/fincen_files/`. Auto-downloads on first query.

### ftm_bridge.py -- FollowTheMoney Interop

Export/import investigation.db entities as FollowTheMoney JSON stream for interop with Aleph, OpenSanctions, investigraph, and nomenklatura.

```bash
uv run python tools/ftm_bridge.py export                               # Export to stdout
uv run python tools/ftm_bridge.py export --output entities.ftm.json
uv run python tools/ftm_bridge.py import --input entities.ftm.json
uv run python tools/ftm_bridge.py import --input entities.ftm.json --dry-run
uv run python tools/ftm_bridge.py reconcile --input entities.ftm.json --threshold 85 --limit 50
```

Maps investigation entity types to FtM schemas (person->Person, llc->Company, trust->LegalEntity, government->PublicBody) and relationship types (financial->UnknownLink, familial->Family, etc.). Optionally uses the `followthemoney` Python package for schema validation if installed.

### ingest_bic.py -- SWIFT BIC Directory

Index SWIFT Business Identifier Codes for bank/wire routing analysis. Sources from OpenSanctions BIC dataset (32K+) and GLEIF BIC-to-LEI mapping.

```bash
uv run python tools/ingest_bic.py download                             # Download BIC datasets
uv run python tools/ingest_bic.py ingest                               # Ingest into bic.db
uv run python tools/ingest_bic.py search "CHASE"                       # Search by bank name
uv run python tools/ingest_bic.py bic CHASUS33                         # Lookup by BIC code
uv run python tools/ingest_bic.py country US                           # List all BICs for country
uv run python tools/ingest_bic.py lei 8I5DZWZKVSZI1NUHU748            # BIC-to-LEI cross-reference
uv run python tools/ingest_bic.py stats
```

**Auth:** None. DB path: `datasets/bic.db`. Uses FTS5 for search.

## Auth Requirements Summary

| Tool | Auth | Env Variable | Tier/Limits |
|------|------|-------------|-------------|
| `query_littlesis.py` | None | -- | Aggressive 503s; built-in retry |
| `query_icij.py` | None (official remote API/pages) | -- | Local Neo4j optional for depth > 1 |
| `query_opencorporates.py` | API key required | `OPENCORPORATES_API_KEY` | 500/month, 200/day (basic) |
| `query_opensanctions.py` | None (bulk download) | -- | One-time download + ingest |
| `query_gleif.py` | None | -- | 60 req/min |
| `query_fincen.py` | None (public CSV) | -- | Auto-downloads on first use |
| `ftm_bridge.py` | None (local) | -- | Optional: `followthemoney` pip package |
| `ingest_bic.py` | None (bulk download) | -- | One-time download + ingest |

## Known Quirks

- **ICIJ node REST view is currently unreliable.** The advertised `/api/v1/rest/nodes/{id}` endpoint returned HTTP 500 in July 2026, so bounded detail/first-hop queries parse `document.body.nodeData` from the official public node page. Use `--local` only for deeper graph traversal.
- **OpenCorporates quota burns fast.** 500 calls/month on basic tier. Use `account-status` to check remaining calls. Prefer jurisdiction-scoped queries over global searches to get better results per call.
- **OpenSanctions requires download + ingest.** The `search` command will fail until you run `download` then `ingest`. The ingest builds FTS5 indexes locally for fast search.
- **FinCEN contains ONLY bank names.** No individual person names. If a search returns 0 results for a person, this is expected. Cross-reference SAR IDs against published ICIJ reporting for person-level connections.
- **Aleph (`query_aleph.py`) is DEPRECATED** as of March 2026. OCCRP removed the free tier. Use OpenCorporates, ICIJ, and OpenSanctions as alternatives.
- **LittleSis 503 errors are common.** The tool retries with increasing waits (3s, 6s, 9s). If all 4 retries fail, the server is likely under heavy load.
- **GLEIF uses JSON:API format** (`application/vnd.api+json`). Entity data is nested under `attributes.entity` in responses.
- **ftm_bridge.py generates deterministic IDs** from entity properties using UUID5. Re-exporting produces the same IDs, enabling stable cross-referencing.
- **BIC-to-LEI mapping** enables chaining: find a bank's BIC, resolve to LEI, then use GLEIF to trace the ownership hierarchy.

## Selector-Pivot Orchestrator

`tools/selector_pivot.py` fans a single selector (email/username/phone/domain/IP/name/company) across the free aggregator set, normalizes results into a selector graph, and emits candidate entities + `pending_triage` leads.

```bash
uv run python tools/selector_pivot.py run "Gazprom" --type company --output $WORKDIR/p.json
uv run python tools/selector_pivot.py run "acme.com" --type domain --dry-run --output $WORKDIR/p.json
uv run python tools/selector_pivot.py adapters --type name   # routing + availability
```

- **Posture: aggregators-only** — queries index layers, never downloads raw dumps.
- **Free adapters (default fan-out):** opensanctions (local), gleif, icij-reconcile, littlesis, crtsh, maigret. **Gated behind `--enable-paid`:** intelx (needs `INTELX_API_KEY`; phonebook paywalled), dehashed (needs an ACTIVE v2 search subscription, not just credits).
- **Provenance is per-adapter.** Legitimate sources carry their own name; leak/breach adapters (dehashed/intelx) stamp `leak_aggregator` and cap any derived finding at `medium` (corroborate against a primary record before promotion).
- Emits entities via `resolve_or_create_entity` + `pending_triage` leads via `auto_leads.create_lead`; the full selector graph lives in the `--output` artifact. Entity↔entity `connections` edges (for graph_tools bridge detection) are a planned phase-2 add.

## Skills That Use These Tools

- `/deep-investigate` (Agent D -- Network & Sanctions Screening)
- `/trace-entity` (corporate entity tracing through registries and offshore leaks)
- `/investigate-person` (sanctions/PEP checks, relationship mapping)
- `/systemic-analysis` (deep entity patterns, ownership chains)
- selector-pivot orchestrator (`tools/selector_pivot.py`) — one selector → linked selectors + entities across aggregators
