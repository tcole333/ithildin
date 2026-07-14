# Government Spending & Contracts

Tools for federal spending analysis, contract intelligence, SAM.gov entity registration, healthcare provider spending, and PPP loan research.

**When to read this module:** When running /analyze-contract, /audit-contracts, /landscape-scan, or investigating government funding flows, contractor relationships, or healthcare billing anomalies.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_usaspending.py` | USAspending.gov API | None | No | ~10 req/sec |
| `query_highergov.py` | HigherGov API | `HIGHERGOV_API_KEY` in .env | No | 10 req/sec, 10K records/month |
| `query_sam.py` | SAM.gov API | `SAM_API_KEY` (free) | No | 10 req/day (basic); 1K/day (SAM role) |
| `ingest_sam.py` | SAM.gov bulk extracts | None | `datasets/sam.db` (874K entities, 167K exclusions) | N/A (local) |
| `query_medicare.py` | CMS Data API | None | No | ~10 req/sec |
| `query_medicaid.py` | Local DuckDB over Parquet | None | 227M rows, $1.09T (T-MSIS 2018-2024) | N/A (local) |
| `query_ppp.py` | Local DuckDB over Parquet | None | ~11M PPP loan records | N/A (local) |
| `query_federal_register.py` | Federal Register API | None | 7-day local response cache (`datasets/fr_cache.db`) | ~1 req/sec self-imposed |
| `trace_provider.py` | Composite (DuckDB + NPPES + state registries) | None | Uses `data/` parquets + `registry.db` | N/A |

## query_usaspending.py — Federal Spending

The primary tool for federal contract and grant research. Searches recipients, awards, subawards, transactions, and geographic spending patterns.

```bash
uv run python tools/query_usaspending.py search "Palantir"                       # Recipient autocomplete
uv run python tools/query_usaspending.py awards "PALANTIR TECHNOLOGIES INC."     # Awards by name
uv run python tools/query_usaspending.py awards --uei "RN99S3S7N977" --agency "Department of Defense"
uv run python tools/query_usaspending.py awards "Booz Allen" --grants            # Grant awards
uv run python tools/query_usaspending.py recipient "Palantir Technologies"       # Spending by agency
uv run python tools/query_usaspending.py award CONT_AWD_12345                    # Single award detail
uv run python tools/query_usaspending.py subawards "Shield AI" --limit 25        # Subcontractor search
uv run python tools/query_usaspending.py transactions "Anduril" --agency "Department of Defense"
uv run python tools/query_usaspending.py covid "recipient name" --limit 20       # COVID relief awards
uv run python tools/query_usaspending.py loans "recipient name"                  # Loan awards
uv run python tools/query_usaspending.py geography "Palantir" --scope place_of_performance --geo-layer state
uv run python tools/query_usaspending.py timeline "Palantir" --group fiscal_year
uv run python tools/query_usaspending.py top-recipients --agency "Department of Homeland Security" --limit 20
uv run python tools/query_usaspending.py agencies --limit 20                     # Agency spending summary
```

**Known quirks:**
- Award type groups cannot be mixed in a single request (API returns 422). The tool separates contracts (A/B/C/D), grants (02-05), and loans (07-08) automatically.
- The `--grants` flag switches from contract to grant award types.
- SSL context uses certifi; set `OSINT_INSECURE_SSL=true` if cert issues arise.

## query_highergov.py — HigherGov Contract Intelligence

Richer than USAspending for contract relationships: named vehicle tracking, teaming/partnership data, subcontracts, people search, and IDV hierarchies.

```bash
uv run python tools/query_highergov.py contract --award-id "N0002325D0075-70CDCR26FR0000040"
uv run python tools/query_highergov.py contract --parent-award "N0002325D0075" --page-size 50
uv run python tools/query_highergov.py contract --vehicle-key 8751 --page-size 100
uv run python tools/query_highergov.py contract --awardee-uei ZE2JVFS8ML75
uv run python tools/query_highergov.py idv --vehicle-key 8751              # Indefinite Delivery Vehicles
uv run python tools/query_highergov.py awardee --uei ZE2JVFS8ML75         # Awardee profile (use --cage CODE as an alternative)
uv run python tools/query_highergov.py subcontract --awardee-uei ZE2JVFS8ML75
uv run python tools/query_highergov.py partnership --awardee-key 509623647 # Teaming data
uv run python tools/query_highergov.py vehicle --vehicle-key 8751          # Named vehicle details
uv run python tools/query_highergov.py agency --agency-key 904
uv run python tools/query_highergov.py grant --awardee-uei ZE2JVFS8ML75
uv run python tools/query_highergov.py people --email "john.doe@ice.dhs.gov"
uv run python tools/query_highergov.py opportunity --source-id "26-SOL-DCR01"
```

**Auth:** Requires `HIGHERGOV_API_KEY` in `.env` (or `--key` flag). 2-week trial available.

**Known quirks:**
- Pagination is automatic with `paginate_all()` up to 50 pages.
- Key vehicle IDs to remember: WEXMAC 2.0 = vehicle key 8751.
- 10K records/month cap on base plan -- budget queries carefully.

## query_sam.py — SAM.gov API

Entity registration, exclusions (debarments/suspensions), contract awards, and solicitations.

```bash
# Entity registration search
uv run python tools/query_sam.py entity "Palantir"
uv run python tools/query_sam.py entity "Palantir" --status A --sections all

# Exclusion search (debarments, suspensions)
uv run python tools/query_sam.py exclusions "QUERY" --classification Firm
uv run python tools/query_sam.py exclusions "QUERY" --type "Ineligible (Proceedings Completed)"

# Contract awards (replaces FPDS, decommissioned Feb 2026)
uv run python tools/query_sam.py contracts "RECIPIENT" --limit 25
uv run python tools/query_sam.py contracts --piid PIID --date-signed-from 2025-09-01 --date-signed-to 2026-02-01

# Opportunity/solicitation search
uv run python tools/query_sam.py opportunities "surveillance" --posted-from 01/01/2025
```

**Auth:** Requires `SAM_API_KEY` (free at sam.gov -> Account Details -> API Key). Basic non-federal tier: 10 req/day. Request SAM role for 1,000/day.

**Known quirks:** Extremely low rate limit on the basic non-federal personal tier (10/day). A SAM role raises the default to 1,000/day. Contract date flags accept ISO `YYYY-MM-DD` and convert it to the API's required `MM/DD/YYYY` format. Use `ingest_sam.py` for bulk entity and exclusion queries instead.

## ingest_sam.py — SAM.gov Bulk Data

Local SQLite database built from SAM.gov public extract files. Unlimited queries, no API rate limits.

```bash
uv run python tools/ingest_sam.py ingest-exclusions                        # Ingest bulk files
uv run python tools/ingest_sam.py ingest-entities
uv run python tools/ingest_sam.py search "Palantir"                        # Search both tables
uv run python tools/ingest_sam.py entity "Booz Allen"                      # Entity lookup
uv run python tools/ingest_sam.py entity-by-uei "C111ATT311C8"
uv run python tools/ingest_sam.py entity-by-cage "53YC5"
uv run python tools/ingest_sam.py exclusion "fraud"                        # Debarment search
uv run python tools/ingest_sam.py naics "541511" --limit 20                # By NAICS code
uv run python tools/ingest_sam.py address "1600 Pennsylvania" --limit 20   # By address
uv run python tools/ingest_sam.py stats
```

**Data source:** Download from sam.gov -> Data Access -> Public Extracts. Entity file (~500MB pipe-delimited), exclusions (~66MB CSV).

## query_medicare.py — Medicare Provider Spending

CMS Physician & Other Practitioners spending data. Searches by provider name or NPI.

```bash
uv run python tools/query_medicare.py search "Enkeshafi"
uv run python tools/query_medicare.py provider 1003000126
uv run python tools/query_medicare.py stats
```

**Known quirks:** CMS API filtering is often exact-match or prefix-based. Last name searches must be uppercase. NPI searches are numeric-only. Default dataset is 2023.

## query_medicaid.py — Medicaid T-MSIS (DuckDB)

227M rows of provider-level Medicaid spending (2018-2024) over DuckDB/Parquet. Supports anomaly detection, recoupment tracking, and provider network analysis.

```bash
uv run python tools/query_medicaid.py stats
uv run python tools/query_medicaid.py top-billers --limit 20
uv run python tools/query_medicaid.py top-codes --limit 20
uv run python tools/query_medicaid.py provider 1376609297
uv run python tools/query_medicaid.py provider 1376609297 --timeline
uv run python tools/query_medicaid.py code T1019 --limit 20
uv run python tools/query_medicaid.py network 1376609297
uv run python tools/query_medicaid.py recoupments --limit 20
uv run python tools/query_medicaid.py yearly                      # Year-over-year summary
uv run python tools/query_medicaid.py anomalies --limit 50 --min-paid 10000000
uv run python tools/query_medicaid.py sql "SELECT billing_npi, sum(paid) FROM m GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
```

**Known quirks:** Requires `duckdb` package and parquet files in `data/` directory. Views are registered as `m` (spending), `bp` (billing providers), `sp` (servicing providers), `hcpcs` (codes). The `anomalies` command flags statistically unusual billing patterns.

## query_ppp.py — PPP/EIDL Loans (DuckDB)

~11M PPP loan records from the SBA FOIA bulk download. Includes borrower, lender, NAICS, jobs, forgiveness.

```bash
uv run python tools/query_ppp.py stats
uv run python tools/query_ppp.py search "Acme Corp"
uv run python tools/query_ppp.py borrower "EXACT BORROWER NAME"
uv run python tools/query_ppp.py address "123 Main St"
uv run python tools/query_ppp.py lender "JPMorgan Chase"
uv run python tools/query_ppp.py naics 541511
uv run python tools/query_ppp.py enrich                            # Cross-ref against investigation.db
uv run python tools/query_ppp.py sql "SELECT * FROM ppp WHERE currentapprovalamount > 1000000 LIMIT 10"
```

**Data source:** Download CSV from https://data.sba.gov/dataset/ppp-foia, then convert: `python scripts/convert_ppp_csv.py data/public_*.csv`.

## query_federal_register.py — Federal Register

Searches Federal Register documents from 1994 onward via the free public API. No auth required. Useful for verifying claims about Senate-confirmed appointments, military commissions/promotion lists (O-6+ requiring confirmation), executive orders, proclamations, and DoD/agency notices against the primary published source rather than secondary news reporting.

```bash
# Full-text search with filters
uv run python tools/query_federal_register.py search "Navy Reserve commission" \
    --start-date 2025-01-01 --end-date 2025-06-30 --output /tmp/fr.json
uv run python tools/query_federal_register.py search "officer appointment" \
    --agency defense-department --doc-type NOTICE --output /tmp/fr.json

# Term search (matches the FR `term` condition — phrase/keyword search)
uv run python tools/query_federal_register.py term "Parlatore" --limit 50 --output /tmp/fr.json

# All documents from a specific agency (slug, not name)
uv run python tools/query_federal_register.py agency navy-department \
    --start-date 2025-01-01 --output /tmp/fr.json
uv run python tools/query_federal_register.py list-agencies | grep -i navy

# Presidential documents only (proclamations, EOs, memoranda, determinations)
uv run python tools/query_federal_register.py presidential \
    --start-date 2025-03-01 --end-date 2025-04-15 --output /tmp/fr.json
uv run python tools/query_federal_register.py presidential --type executive_order \
    --start-date 2025-01-20

# Fetch a single document (and optionally its full text)
uv run python tools/query_federal_register.py document 2025-06461
uv run python tools/query_federal_register.py document 2025-06461 --full-text --output /tmp/fr.json
```

**Known quirks:**
- `--agency` requires the exact slug (`navy-department`, not `NAVY` or `DOD`). Use `list-agencies` to discover slugs.
- The `/articles` and `/documents` endpoints are aliases — the tool uses `/documents`.
- The Federal Register does NOT publish O-5 (and below) reserve military commissions issued under 10 USC 12203 (President-alone authority). Only O-6+ promotions (Senate-confirmed) appear as published promotion lists. Senior Executive Service career-reserve lists do appear (e.g., document 2025-08853).
- Cached responses live in `datasets/fr_cache.db` for 7 days. Set `FR_NO_CACHE=1` to bypass.

**Citation token:** `[FR:2025-06461]` -> linked Federal Register document URL.

## trace_provider.py — Healthcare Provider Tracing

Composite pipeline: NPI -> NPPES enrichment -> state corporate registry -> officer/agent network. Connects Medicaid billing entities to their corporate structures.

```bash
# Trace a single NPI
uv run python tools/trace_provider.py trace 1376609297 --output /tmp/trace.json

# Batch trace (top anomalous providers or from file)
uv run python tools/trace_provider.py batch --top-anomalies 20 --output /tmp/batch.json
uv run python tools/trace_provider.py batch --file /tmp/npis.txt --output /tmp/batch.json

# Officer network (people across multiple billing entities)
uv run python tools/trace_provider.py officer-network --min-entities 2 --output /tmp/officers.json

# Shared registered agents across billing entities
uv run python tools/trace_provider.py agent-network --min-entities 3 --output /tmp/agents.json

# Cross-reference billing NPIs against OIG exclusion list
uv run python tools/trace_provider.py excluded --output /tmp/excluded.json

# Full pipeline: anomalies -> trace -> officer network -> report
uv run python tools/trace_provider.py pipeline --top-anomalies 50 --output /tmp/pipeline.json
```

**Known quirks:** Uses NY DOS live lookup if `query_nydos.py` is available. Requires `duckdb` and parquet files for Medicaid data. The `pipeline` command chains anomaly detection, tracing, and officer network analysis into a single run.

## Skills Using These Tools

| Skill | Tools Used |
|-------|-----------|
| `/analyze-contract` | `query_usaspending.py` (award, subawards, transactions), `query_highergov.py` (contract, idv, subcontract) |
| `/audit-contracts` | `query_usaspending.py`, `query_highergov.py`, `query_sam.py`, `ingest_sam.py` |
| `/landscape-scan` | `query_usaspending.py` (top-recipients, agencies, timeline), `query_highergov.py` (vehicle, partnership) |
| `/deep-investigate` | `query_usaspending.py`, `query_ppp.py`, `query_medicare.py` |
