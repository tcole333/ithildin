---
name: search-all-sources
description: Fan-out search across all local and remote datasets
user_invocable: true
---

# /search-all-sources

Search a term across every available data source in parallel. Deduplicates by EFTA ID where possible.

## Arguments

- Required: search term (e.g., `/search-all-sources churkin ambassador`)

## Process

### 0. Session Setup — Prevent File Collisions

Create a unique working directory for this session:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` instead of `/tmp/` for ALL `--output` paths and report files throughout this session. This prevents parallel searches from overwriting each other's files.

### 1. Run All Local Searches
Execute these in parallel where possible. **Use `--output` on all searches** to keep context lean:

```bash
# DugganUSA API (204K+ docs)
python tools/duggan_search.py "<QUERY>" -n 20 --output $WORKDIR/search-duggan.json

# DOJ Vol 11 (331K pages, FTS5)
python tools/query_doj.py search "<QUERY>" --limit 20 --output $WORKDIR/search-doj.json

# LMSBAND (60K files text search)
python tools/query_lmsband.py search "<QUERY>" --limit 20 --output $WORKDIR/search-lmsband.json

# LMSBAND entities
python tools/query_lmsband.py entities "<QUERY>" --output $WORKDIR/search-lmsband-ent.json

# Unified DB emails
python tools/query_unified.py emails "<QUERY>" --limit 20 --output $WORKDIR/search-unified-email.json

# Unified DB documents
python tools/query_unified.py docs "<QUERY>" --limit 20 --output $WORKDIR/search-unified-docs.json

# Unified DB entities
python tools/query_unified.py entities "<QUERY>" --output $WORKDIR/search-unified-ent.json
```

```bash
# Corporate Registry (FL, NY, more)
python tools/query_registry.py search "<QUERY>" --output $WORKDIR/search-registry.json
python tools/query_registry.py officers "<QUERY>" --output $WORKDIR/search-officers.json

# UCC Filings (secured transactions, liens)
python tools/query_registry.py ucc-search "<QUERY>" --output $WORKDIR/search-ucc.json

# OCCRP Aleph (corporate registries, leaks, sanctions)
python tools/query_aleph.py search "<QUERY>" --schema Person --output $WORKDIR/search-aleph-person.json
python tools/query_aleph.py search "<QUERY>" --schema Company --output $WORKDIR/search-aleph-company.json

# CourtListener (federal courts)
python tools/query_courtlistener.py search "<QUERY>" --output $WORKDIR/search-cl.json

# ProPublica 990 (nonprofit filings)
python tools/query_990.py search "<QUERY>" --output $WORKDIR/search-990.json

# GDELT (global news media — 3-month rolling window)
python tools/query_gdelt.py articles "<QUERY>" --limit 20 --output $WORKDIR/search-gdelt-art.json
python tools/query_gdelt.py context "<QUERY>" --timespan 1w --limit 20 --output $WORKDIR/search-gdelt-ctx.json
```

If ICIJ Neo4j is running:
```bash
python tools/query_icij.py search "<QUERY>"
```

### 1b. Web & External API Sources

```bash
# General web search
# WebSearch: "<QUERY>"
# WebSearch: "<QUERY> investigation"
# WebSearch: "<QUERY> court filing"

# Investigation reports (if investigations.db is populated)
python tools/query_investigations.py search "<QUERY>" --limit 10

# LittleSis relationship mapping
python tools/query_littlesis.py search "<QUERY>"

# SEC EDGAR full-text search (with aggregation facets for network mapping)
python tools/query_edgar.py search "<QUERY>" --size 10 --facets

# FAA Registry (if ingested — aviation-related queries)
python tools/ingest_faa.py search "<QUERY>"

# NYC ACRIS property records
python tools/query_acris.py party "<QUERY>"

# FEC campaign finance
python tools/query_fec.py donor "<QUERY>" --limit 20

# Federal lobbying disclosures
python tools/query_lobbying.py client "<QUERY>"

# FARA foreign agents
python tools/query_fara.py search "<QUERY>"

# GLEIF corporate hierarchy (LEI records — financial entities only)
python tools/query_gleif.py search "<QUERY>" --limit 10

# UK Companies House (if API key configured)
python tools/ingest_uk_companies_house.py search "<QUERY>" --limit 10

# OpenSanctions (PEP/sanctions check — if ingested)
python tools/query_opensanctions.py search "<QUERY>" --limit 10

# DS10 Deutsche Bank financial records (entity/counterparty search)
python tools/parse_ds10_financials.py query --entity "<QUERY>"

# USVI corporate registry (Catalyst web scraper — search only, no bulk)
python tools/ingest_usvi.py search "<QUERY>"

# DC DLCP (ArcGIS FeatureServer — 492K entities, no auth)
python tools/ingest_dc.py search "<QUERY>" --output $WORKDIR/search-dc.json

# California SoS bizfileonline (web API, up to 500 results, needs MCP Playwright Chrome)
python tools/query_california.py search "<QUERY>" --output $WORKDIR/search-ca-sos.json

# Texas Comptroller (franchise tax entities — no auth)
python tools/query_texas.py search "<QUERY>" --output $WORKDIR/search-tx.json

# Michigan LARA (business registry — Playwright browser helper, Cloudflare WAF)
python tools/query_michigan.py search "<QUERY>" --contains --output $WORKDIR/search-mi.json

# New Jersey Division of Revenue (business entity name search — no detail pages)
python tools/query_newjersey.py search "<QUERY>" --output $WORKDIR/search-nj.json

# Massachusetts Corporations Division (Playwright browser helper, Incapsula WAF)
python tools/query_massachusetts.py search "<QUERY>" --output $WORKDIR/search-ma.json

# Epstein Files 20K (House Oversight docs — HOUSE_OVERSIGHT IDs, not EFTA)
python tools/ingest_epstein_20k.py search "<QUERY>" --limit 10

# EpsteinExposed.com (persons, documents, flights)
python tools/ingest_epstein_exposed.py search "<QUERY>"

# MuckRock FOIA (21 Epstein FOIA requests — FBI, CBP, USMS, DOJ, BOP, SDNY, SDFL)
python tools/query_muckrock.py search "<QUERY>"

# DocumentCloud (6,613+ pages — Giuffre v. Maxwell, MCC records)
python tools/query_documentcloud.py search "<QUERY>" --limit 10

# OffshoreAlert (29K+ offshore court cases, articles, MLATs, regulatory actions)
python tools/offshorealert_search.py search "<QUERY>" -v --output $WORKDIR/search-offshorealert.json
```

### 2. Log Each Search
After each query, log it to prevent redundant future searches:
```python
from tools.lead_tracker import log_search
log_search("<QUERY>", "duggan", result_count)
log_search("<QUERY>", "doj_vol11", result_count)
log_search("<QUERY>", "lmsband", result_count)
log_search("<QUERY>", "gleif", result_count)
log_search("<QUERY>", "uk_companies_house", result_count)
log_search("<QUERY>", "opensanctions", result_count)
log_search("<QUERY>", "ds10_financial", result_count)
log_search("<QUERY>", "usvi", result_count)
log_search("<QUERY>", "epstein_20k", result_count)
log_search("<QUERY>", "epstein_exposed", result_count)
log_search("<QUERY>", "muckrock", result_count)
log_search("<QUERY>", "documentcloud", result_count)
log_search("<QUERY>", "dc_corp_registry", result_count)
log_search("<QUERY>", "ca_bizfile", result_count)
log_search("<QUERY>", "tx_comptroller", result_count)
log_search("<QUERY>", "mi_lara", result_count)
log_search("<QUERY>", "offshorealert", result_count)
# etc.
```

### 3. Deduplicate Results
- Group results by EFTA ID where available
- Note which sources returned each result
- Flag results found in 3+ sources as high-confidence corroboration
- Flag results from only 1 source as needing verification

### 4. Present Consolidated Results

Format:
```
SEARCH: "<QUERY>" across 7 sources

=== CORROBORATED (3+ sources) ===
EFTA02394403 — [DugganUSA, DOJ Vol 11, LMSBAND]
  Ambassador Churkin email to Epstein, May 2016

=== MULTI-SOURCE (2 sources) ===
EFTA02219298 — [DOJ Vol 11, Unified DB]
  Maxim Churkin appointment scheduling, Aug 2017

=== SINGLE-SOURCE ===
[LMSBAND file #12345] — Churkin mentioned in travel document
[Unified triple] — Epstein -> arranged meeting -> Churkin @ NYC, 2016-12

=== SOURCE COVERAGE ===
DugganUSA:    15 hits
DOJ Vol 11:   8 hits
LMSBAND:      3 hits
Unified:      5 hits
Registry:     2 hits (FL, NY)
Aleph:        4 hits
CourtListener: 1 hit
990:          0 hits
UCC:          0 hits
GDELT:        12 hits (articles), 8 hits (context)
ICIJ:         0 hits (not searched — Neo4j not running)
GLEIF:        2 hits (LEI records)
UK CH:        0 hits (not searched — no API key)
OpenSanctions: 1 hit (PEP match)
DS10:         0 hits (no matching transactions)
USVI:         0 hits
Epstein 20K:  3 hits (House Oversight docs)
EpsteinExposed: 1 hit (person match)
MuckRock:     0 hits (FOIA tags search)
DocumentCloud: 3 hits (full-text search)
DC DLCP:      0 hits (ArcGIS, 492K entities)
CA SoS:       0 hits (keyword search, top 150)
OffshoreAlert: 5 hits (offshore court cases, articles)
```

### 5. Analytical Assessment

Don't just present results — analyze them. Apply the investigative methodology from `research/INVESTIGATIVE_METHODOLOGY.md`:

- **What did you expect to find vs. what you found?** Surprises are intelligence. If you searched for a known Epstein associate and found zero DOJ documents, that absence is significant — it may mean concealment, document destruction, or that the relationship operated through channels the DOJ didn't capture.
- **Cross-bureaucratic correlation**: Results from independent sources (e.g., an EFTA email + an LMSBAND financial record + an ICIJ offshore entity) that converge on the same event or relationship are far more valuable than the same document appearing in 3 derivative databases.
- **New names and entities**: Flag any previously unknown persons, email addresses, phone numbers, or corporate entities that appear in results. Each is a potential new investigation thread.
- **Timeline patterns**: If results cluster around specific dates, note what was happening in the world then. A cluster of emails in May 2017 relates to Mueller's appointment. A cluster in June 2019 relates to the weeks before arrest.

### 6. Suggest Follow-Up
Based on results, suggest:
- Whether findings warrant creating a lead
- Which sources still need to be searched
- Cross-references to investigate (e.g., "Maxim Churkin appears — worth investigating separately")
- **Hypotheses generated by the search results** — what do these results suggest about the relationship or event?
- **What's conspicuously absent** — what you expected but didn't find

## Tool Bug Reporting
If you encounter bugs in CLI tools (crashes, incorrect output, missing features), submit them to the infra queue:
`uv run python tools/infra_tracker.py add --title "Bug: <description>" --type tool_improvement --priority high --description "<details including the error traceback>"`

## Context Management

- **All searches above already use `--output`** — this is critical for keeping context lean
- **Do NOT `cat` or `Read` the output JSON files unless you need specific details** for a finding
- If spawned as a sub-agent, write results to `$WORKDIR/report-search-<query-slug>.md` using the consolidated results format from section 4 above.
