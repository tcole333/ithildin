# Government Spending & Contracts

Tools for federal spending analysis, contract intelligence, SAM.gov entity registration, healthcare provider spending, and PPP loan research.

**When to read this module:** When running /analyze-contract, /audit-contracts, /landscape-scan, or investigating government funding flows, contractor relationships, or healthcare billing anomalies.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_usaspending.py` | USAspending.gov API | None | No | ~10 req/sec |
| `query_fpds.py` | FPDS-NG ATOM feed | None | No | 1 req/sec self-imposed |
| `query_highergov.py` | HigherGov API | `HIGHERGOV_API_KEY` in .env | No | 10 req/sec, 10K records/month |
| `query_sam.py` | SAM.gov API | `SAM_API_KEY` (free) | No | 10 req/day (basic); 1K/day (SAM role) |
| `ingest_sam.py` | SAM.gov bulk extracts | None | `datasets/sam.db` (874K entities, 167K exclusions) | N/A (local) |
| `query_medicare.py` | CMS Data API | None | No | ~10 req/sec |
| `query_openpayments.py` | CMS Open Payments DKAN API | None | No | 5 req/sec self-imposed |
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
uv run python tools/query_usaspending.py award 70CDCR26FR0000002                 # Plain PIID is resolved first
uv run python tools/query_usaspending.py subawards "Shield AI" --limit 25        # Subcontractor search
uv run python tools/query_usaspending.py transactions "Anduril" --agency "Department of Defense"
uv run python tools/query_usaspending.py transactions --uei JMLKZZ1NL2Z6 \
    --agency "U.S. Immigration and Customs Enforcement" --agency-tier subtier --output /tmp/transactions.json
uv run python tools/query_usaspending.py covid "recipient name" --limit 20       # COVID relief awards
uv run python tools/query_usaspending.py loans "recipient name"                  # Loan awards
uv run python tools/query_usaspending.py geography "Palantir" --scope place_of_performance --geo-layer state
uv run python tools/query_usaspending.py timeline "Palantir" --group fiscal_year
uv run python tools/query_usaspending.py top-recipients --agency "Department of Homeland Security" --limit 20
uv run python tools/query_usaspending.py agencies --limit 20                     # Agency spending summary
uv run python tools/query_usaspending.py transactions-keyword "skip tracing" --all-pages
uv run python tools/query_usaspending.py transactions-keyword "wellness check" --naics 561611 --psc R799 \
    --agency "U.S. Immigration and Customs Enforcement" --agency-tier subtier --output /tmp/hits.json
```

**Known quirks:**
- All USAspending JSON outputs contain `results`, `status`, `errors`, `query`, and `retrieval`. Former bare-list outputs now put their rows under `results`; award-detail and recipient fields also remain at the top level. Check acquisition errors and `retrieval.complete` before treating an empty result as evidence. Failed acquisition writes the requested artifact and exits 1; partially acquired records are retained with `status: partial`.
- `transactions-keyword --all-pages` stops after 50 pages with an explicit partial result and `pagination.next_page`. Resume with `--page N --all-pages`. A successful page does not by itself establish complete coverage, and unknown pagination coverage stays `null`.
- Award type groups cannot be mixed in a single request (API returns 422). The tool separates contracts (A/B/C/D), grants (02-05), and loans (07-08) automatically.
- The `--grants` flag switches from contract to grant award types.
- `award` accepts either a generated USAspending identifier or a plain PIID. A plain PIID is exact-matched across contract and IDV award groups first; ambiguous matches fail closed and list the generated identifiers.
- Advanced transaction searches enforce the API's 1-100 page-size range locally. Use `--page` to continue.
- Agency filters default to `toptier` department names. Pass `--agency-tier subtier` for a component such as U.S. Immigration and Customs Enforcement.
- Transaction JSON is an envelope containing `results`, preserved pagination, and returned recipient identities. A parent UEI can expand to affiliated recipients; check `recipient_scope_expansion_observed` and `returned_recipients` before combining separate UEI queries. An absent API total remains `null` rather than being inferred from the current page length.
- `top-recipients --naics` sends the current `{"require": [...], "exclude": []}` filter object; that endpoint rejects the older list-of-objects form.
- SSL context uses certifi; set `OSINT_INSECURE_SSL=true` if cert issues arise.
- `transactions-keyword` searches **transaction** descriptions, so it sees scope added by modification — award-level search does not. Use it whenever asking "when did this agency first buy X?"
- That endpoint's `naics_codes`/`psc_codes` filters take bare code strings (`["561611"]`); the object form used by the award endpoints returns HTTP 422 there.

## query_fpds.py — FPDS-NG Contract Actions

The only source for contract-action **workflow fields** — `createdBy`, `lastModifiedBy`, `approvedBy` and
their timestamps. USAspending omits them; HigherGov exposes the columns but returns null. Use these to test
separation of duties (did one user create *and* approve an award?).

```bash
uv run python tools/query_fpds.py piid 70CDCR26FR0000014 --output /tmp/actions.json
uv run python tools/query_fpds.py search 'VENDOR_UEI:D13LLJJZYH64' --max-pages 5 --output /tmp/vendor.json
uv run python tools/query_fpds.py piid 70CDCR26FR0000014 --from-file saved-feed.xml   # offline parse
uv run python tools/query_fpds.py search 'VENDOR_UEI:D13LLJJZYH64' --with-metadata --output /tmp/v.json
```

**Known quirks:**
- One `<entry>` per contract action, so a base award and each modification are separate rows; filter on
  `modification_number` to isolate the base action.
- The feed has **two payload roots**, reported as `record_type`. `award` is a dated contract action;
  `IDV` is the indefinite-delivery vehicle those actions are placed against. Roughly 10% of rows in a
  DHS vendor slice are IDVs, and for some vendors the IDV *is* the flagship instrument — the $1.596B UAC
  IDIQ `70CDCR26D00000045` is an IDV row. Treating "no dated action" as "no contracting history" will
  call an incumbent a first-time entrant; screen on `record_type` instead.
- IDVs carry no parent vehicle and no completion dates, so `referenced_idv_piid`, `transaction_number`,
  `current_completion_date` and `ultimate_completion_date` are null on those rows. Their period bound is
  `lastDateToOrder`, which is deliberately not aliased into a completion-date field. An IDV's ceiling
  reads from `base_and_all_options_value`; its `action_obligation` is usually `0`.
- A `record_type` of `null` means FPDS used a payload root this tool does not know. The CLI warns on
  stderr; treat those rows as unparsed rather than empty.
- **Paging truncates silently at the source.** A fetch stopping at `--max-pages` while the feed still
  offers a next page returns a partial set — at the default of 10 that is 100 rows. The tool now warns on
  stderr, exits 2, and sets `truncated`/`next_url`/`pages_fetched` under `--with-metadata`. Never derive
  an earliest-action or first-seen date from a truncated fetch; raise `--max-pages` until it exits 0.
- Parsed keys are mixed case: snake_case for most fields but **camelCase for the workflow fields**
  (`createdBy`, `lastModifiedBy`, `approvedBy`). Reading them with snake_case names silently yields `None`,
  which looks identical to missing data.
- Query syntax is FPDS's own: `PIID:"..."`, `VENDOR_UEI:"..."`, `REF_IDV_PIID:"..."`, `AGENCY_CODE:"..."`.
- Cite findings from this tool with source token `fpds` — not `usaspending` or `sam_gov`.
- Records the data-entry workflow, which is not identical to the FAR contracting-officer approval chain.
  Say what the field shows, not more.

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

## query_openpayments.py — CMS Open Payments

Primary-source payment and ownership disclosures reported by drug and medical-device
companies. The tool uses CMS's current DKAN catalog and bounded datastore API; no API
key is required. Find the covered-recipient profile first, then query reporting-entity
and nature-of-payment summaries by CMS profile ID.

```bash
uv run python tools/query_openpayments.py datasets --query "2025 General" --output /tmp/op-datasets.json
uv run python tools/query_openpayments.py search MERKIN --first-name MICHAEL --state NY --output /tmp/op-profiles.json
uv run python tools/query_openpayments.py search 1952494221 --output /tmp/op-npi.json
uv run python tools/query_openpayments.py payments 704135 --year all --output /tmp/op-payments.json
uv run python tools/query_openpayments.py payments 704135 --year 2025 --output /tmp/op-2025.json
uv run python tools/query_openpayments.py query DATASET_UUID \
  --where covered_recipient_profile_id=704135 --limit 25 --output /tmp/op-query.json
```

**Known quirks:** Profile searches are exact matches; last and first names are normalized
to uppercase. `payments --year all` covers the detailed search era beginning in 2019 and
returns two summary types: payments grouped by reporting entity and payments grouped by
nature. Results include CMS counts and a `truncated` flag, and every call is capped at
500 rows per dataset. The `datasets` command exposes official `download.cms.gov` CSV
URLs, but the tool never downloads them automatically because detailed annual files can
be very large. Use program year rather than publication year (`2025` data was published
June 30, 2026). Cite a covered-recipient profile as `OPENPAYMENTS:<profile_id>`; for
example, `OPENPAYMENTS:704135` resolves to the official CMS physician page.

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
