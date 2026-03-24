---
name: search-all-sources
description: Targeted multi-source lookup across local and remote datasets
user_invocable: true
---

# /search-all-sources

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Report what each source returns. Do not interpret or apply frameworks.

Targeted multi-source lookup: search a specific name, entity, address, or term across relevant data sources. Use this as an **infrastructure primitive** when you need to quickly check what's available about a specific target — not as a default investigation strategy. For systematic investigation, use `/pursue-lead` or `/deep-investigate` instead.

## Arguments

- Required: search term (e.g., `/search-all-sources churkin ambassador`)

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill. The `corpus_tools` field lists investigation-specific data sources to search in addition to the generic sources below.

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

# DEPRECATED (March 2026): OCCRP removed free tier in 2026. Tool returns 0 results without paid API key. Skip Aleph queries until access is restored.
# OCCRP Aleph (corporate registries, leaks, sanctions)
python tools/query_aleph.py search "<QUERY>" --schema Person --output $WORKDIR/search-aleph-person.json
python tools/query_aleph.py search "<QUERY>" --schema Company --output $WORKDIR/search-aleph-company.json

# CourtListener (federal courts)
python tools/query_courtlistener.py search "<QUERY>" --output $WORKDIR/search-cl.json

# IRS 990 Nonprofit Database (grants, officers, financials)
python tools/query_990.py search "<QUERY>" --output $WORKDIR/search-990.json
# 990 officer positions (find person on nonprofit boards)
python tools/query_990.py officer-search "<QUERY>" --output $WORKDIR/search-990-officers.json
python tools/query_990.py financials <EIN> --output $WORKDIR/search-990-financials.json  # if EIN known

# DEPRECATED (March 2026): 3-month rolling window + unreliable API (frequent timeouts). Use WebSearch for news coverage instead.
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

# SEC Enforcement Actions (litigation releases, admin proceedings, AAERs)
python tools/query_sec_enforcement.py search "<QUERY>" --limit 10

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

# Shodan (infrastructure recon — DNS, SSL certs, hosting, org footprint — paid plan)
python tools/query_shodan.py search "ssl:<QUERY>" --output $WORKDIR/search-shodan-ssl.json
python tools/query_shodan.py domain "<QUERY>" --output $WORKDIR/search-shodan-domain.json

# crt.sh Certificate Transparency (subdomain enum, cert timeline — free, no auth)
python tools/query_crtsh.py search "<QUERY>" --output $WORKDIR/search-crtsh.json

# Wayback Machine (historical web snapshots — free, no auth)
python tools/query_wayback.py timeline "<QUERY>" --output $WORKDIR/search-wayback.json

# URLScan.io (passive web scans — tech stacks, linked domains — free)
python tools/query_urlscan.py search "domain:<QUERY>" --output $WORKDIR/search-urlscan.json

# OffshoreAlert (29K+ offshore court cases, articles, MLATs, regulatory actions)
python tools/offshorealert_search.py search "<QUERY>" -v --output $WORKDIR/search-offshorealert.json

# USAspending (federal contracts, grants, loans — no auth)
python tools/query_usaspending.py awards "<QUERY>" --output $WORKDIR/search-usaspending-contracts.json
python tools/query_usaspending.py awards "<QUERY>" --grants --output $WORKDIR/search-usaspending-grants.json
python tools/query_usaspending.py subawards "<QUERY>" --output $WORKDIR/search-usaspending-subs.json

# SAM.gov API (entity registrations, exclusions/debarments — requires SAM_API_KEY)
python tools/query_sam.py entity "<QUERY>" --output $WORKDIR/search-sam-entity.json
python tools/query_sam.py exclusions "<QUERY>" --output $WORKDIR/search-sam-exclusions.json
python tools/query_sam.py contracts "<QUERY>" --output $WORKDIR/search-sam-contracts.json

# SAM.gov Bulk (874K entities, 167K exclusions — local SQLite, no API limit)
python tools/ingest_sam.py search "<QUERY>" --output $WORKDIR/search-sam-bulk.json
```

### 1c. Investigation Corpus Tools (from profile)

Search any investigation-specific corpus tools listed in `corpus_tools` from the investigation profile. These are data sources tied to the active investigation (e.g., specialized document corpora, FOIA collections, case-specific databases). Run each tool listed in the profile that hasn't already been searched:

```bash
# Example — the actual tools depend on the investigation profile's corpus_tools list:
# python tools/<corpus_tool>.py search "<QUERY>" --limit 10 --output $WORKDIR/search-<source>.json
```

Log each corpus tool search the same way as generic sources.

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
log_search("<QUERY>", "sec_enforcement", result_count)
log_search("<QUERY>", "ds10_financial", result_count)
log_search("<QUERY>", "usvi", result_count)
log_search("<QUERY>", "dc_corp_registry", result_count)
# Also log any corpus_tools searches from the investigation profile:
log_search("<QUERY>", "ca_bizfile", result_count)
log_search("<QUERY>", "tx_comptroller", result_count)
log_search("<QUERY>", "mi_lara", result_count)
log_search("<QUERY>", "offshorealert", result_count)
log_search("<QUERY>", "shodan", result_count)
log_search("<QUERY>", "crtsh", result_count)
log_search("<QUERY>", "wayback", result_count)
log_search("<QUERY>", "urlscan", result_count)
log_search("<QUERY>", "usaspending_contracts", result_count)
log_search("<QUERY>", "usaspending_grants", result_count)
log_search("<QUERY>", "sam_entity", result_count)
log_search("<QUERY>", "sam_exclusions", result_count)
log_search("<QUERY>", "sam_contracts", result_count)
log_search("<QUERY>", "sam_bulk", result_count)
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
<DOC_ID_1> — [Source A, Source B, Source C]
  Description of corroborated finding

=== MULTI-SOURCE (2 sources) ===
<DOC_ID_2> — [Source A, Source D]
  Description of multi-source finding

=== SINGLE-SOURCE ===
[Source file #12345] — <QUERY> mentioned in document
[Unified triple] — Subject -> arranged meeting -> Target @ Location, date

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
DC DLCP:      0 hits (ArcGIS, 492K entities)
[Corpus tools from investigation profile — list each with hit count]
CA SoS:       0 hits (keyword search, top 150)
OffshoreAlert: 5 hits (offshore court cases, articles)
USAspending:  8 hits (contracts), 2 hits (grants), 1 hit (subawards)
SAM.gov API:  3 hits (entities), 0 hits (exclusions), 5 hits (contracts)
SAM.gov Bulk: 12 hits (874K entities + 167K exclusions, local SQLite)
Shodan:       3 hits (SSL certs, DNS records)
crt.sh:       5 hits (certificate transparency)
Wayback:      12 hits (historical snapshots)
URLScan:      2 hits (passive web scans)
```

### 5. Observations

Flag factual observations from the results, keeping interpretation minimal:

- **Corroboration**: Results found in 2+ independent source types. Note which sources agree.
- **Contradictions**: Results from different sources that conflict. Note the specific discrepancy.
- **Gaps**: Sources that returned zero results where you expected hits. Record the negative result.
- **New names/entities**: Previously unknown persons, email addresses, or corporate entities. Flag each as a potential follow-up lead.
- **Temporal clusters**: If results cluster around specific dates, note the date range and count. Do NOT interpret why — that's for Layer 2.

### 6. Suggest Follow-Up
Based on results, suggest:
- Whether findings warrant creating a lead
- Which sources still need to be searched
- Cross-references to investigate (e.g., "Maxim Churkin appears — worth investigating separately")
- **What's conspicuously absent** — what you expected but didn't find

## Tool Bug Reporting
If you encounter bugs in CLI tools (crashes, incorrect output, missing features), submit them to the infra queue:
`uv run python tools/infra_tracker.py add --title "Bug: <description>" --type tool_improvement --priority high --description "<details including the error traceback>"`

## Context Management

- **All searches above already use `--output`** — this is critical for keeping context lean
- **Do NOT `cat` or `Read` the output JSON files unless you need specific details** for a finding
- If spawned as a sub-agent, write results to `$WORKDIR/report-search-<query-slug>.md` using the consolidated results format from section 4 above.
