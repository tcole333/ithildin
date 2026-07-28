---
name: search-all-sources
description: Targeted multi-source lookup across local and remote datasets
---

# $search-all-sources

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Report what each source returns. Do not interpret or apply frameworks.

Targeted multi-source lookup: search a specific name, entity, address, or term across relevant data sources. Use this as an **infrastructure primitive** when you need to quickly check what's available about a specific target — not as a default investigation strategy. For systematic investigation, use `$pursue-lead` or `$deep-investigate` instead.

## Arguments

- Required: search term (e.g., `$search-all-sources churkin ambassador`)

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
# Kabasshouse (PRIMARY Epstein corpus: 1.42M docs, FTS5) — search this FIRST
uv run python tools/ingest_kabasshouse.py search "<QUERY>" --limit 20 --json > $WORKDIR/search-kabass.json

# Kabasshouse entity mentions (10.6M typed NER rows)
uv run python tools/ingest_kabasshouse.py entity "<QUERY>" > $WORKDIR/search-kabass-ent.txt

# Unified DB emails (parsed emails — complementary, not text-redundant)
uv run python tools/query_unified.py emails "<QUERY>" --limit 20 --output $WORKDIR/search-unified-email.json

# Unified DB entities + triples (relationship extraction)
uv run python tools/query_unified.py entities "<QUERY>" --output $WORKDIR/search-unified-ent.json

# LMSBAND entities (complementary structured layers; text overlaps kabasshouse)
uv run python tools/query_lmsband.py entities "<QUERY>" --output $WORKDIR/search-lmsband-ent.json

# DOJ Vol 11 (FALLBACK — strict subset of kabasshouse; cross-check only)
# uv run python tools/query_doj.py search "<QUERY>" --limit 20 --output $WORKDIR/search-doj.json
```

**Kabasshouse is the primary Epstein full-text corpus.** DOJ Vol 11 / LMSBAND text search cover the same EFTA pages at lower OCR quality — hits there are redundant, not corroborating. (DugganUSA retired 2026-06-29; do not call `duggan_search.py`.)

```bash
# Corporate Registry (FL, NY, more)
uv run python tools/query_registry.py search "<QUERY>" --output $WORKDIR/search-registry.json
uv run python tools/query_registry.py officers "<QUERY>" --output $WORKDIR/search-officers.json

# UCC Filings (secured transactions, liens)
uv run python tools/query_registry.py ucc-search "<QUERY>" --output $WORKDIR/search-ucc.json

# DEPRECATED (March 2026): OCCRP removed free tier in 2026. Tool returns 0 results without paid API key. Skip Aleph queries until access is restored.
# OCCRP Aleph (corporate registries, leaks, sanctions)
uv run python tools/query_aleph.py search "<QUERY>" --schema Person --output $WORKDIR/search-aleph-person.json
uv run python tools/query_aleph.py search "<QUERY>" --schema Company --output $WORKDIR/search-aleph-company.json

# CourtListener (federal courts)
uv run python tools/query_courtlistener.py search "<QUERY>" --output $WORKDIR/search-cl.json

# IRS 990 Nonprofit Database (grants, officers, financials)
uv run python tools/query_990.py search "<QUERY>" --output $WORKDIR/search-990.json
# 990 officer positions (find person on nonprofit boards)
uv run python tools/query_990.py officer-search "<QUERY>" --output $WORKDIR/search-990-officers.json
uv run python tools/query_990.py financials <EIN> --output $WORKDIR/search-990-financials.json  # if EIN known

# DEPRECATED (March 2026): 3-month rolling window + unreliable API (frequent timeouts). Use WebSearch for news coverage instead.
# GDELT (global news media — 3-month rolling window)
uv run python tools/query_gdelt.py articles "<QUERY>" --limit 20 --output $WORKDIR/search-gdelt-art.json
uv run python tools/query_gdelt.py context "<QUERY>" --timespan 1w --limit 20 --output $WORKDIR/search-gdelt-ctx.json
```

Search the official ICIJ remote service; local Neo4j is only needed for graph
depth greater than one:

```bash
uv run python tools/query_icij.py search "<QUERY>" \
  --output "$WORKDIR/search-icij.json"
```

### 1b. Web & External API Sources

```bash
# General web search
# WebSearch: "<QUERY>"
# WebSearch: "<QUERY> investigation"
# WebSearch: "<QUERY> court filing"

# Investigation reports (if investigations.db is populated)
uv run python tools/query_investigations.py search "<QUERY>" --limit 10 --output "$WORKDIR/search-investigations.json"

# MuckRock local request/communication/file index (if datasets/muckrock_index.db exists)
# Prioritize agency-response attachments with no direct DocumentCloud linkage.
uv run python tools/query_muckrock.py unlinked-files "<QUERY>" --limit 20 --output "$WORKDIR/search-muckrock-unlinked.json"
# Broader local search, including DocumentCloud-linked files and outbound attachments:
uv run python tools/query_muckrock.py index-search "<QUERY>" --limit 20 --output "$WORKDIR/search-muckrock-index.json"

# Versioned reporting knowledge layer (attributed secondary claims)
uv run python tools/reporting_corpus.py search "<QUERY>" --limit 20 --output $WORKDIR/search-reporting.json
uv run python tools/reporting_corpus.py claims "<QUERY>" --limit 20 --output $WORKDIR/search-reporting-claims.json

# Primary DOJ/SEC government statements (not automatic proof of allegations)
uv run python tools/government_release_corpus.py search "<QUERY>" --limit 20 --output $WORKDIR/search-government-releases.json

# LittleSis relationship mapping
uv run python tools/query_littlesis.py search "<QUERY>" --output "$WORKDIR/search-littlesis.json"

# SEC EDGAR full-text search (with aggregation facets for network mapping)
uv run python tools/query_edgar.py search "<QUERY>" --size 10 --facets --output "$WORKDIR/search-edgar.json"

# FAA Registry (if ingested — aviation-related queries)
uv run python tools/ingest_faa.py search "<QUERY>" --output "$WORKDIR/search-faa.json"

# Build the property -> recorder -> court plan from the target, active profile,
# known addresses, aliases, and every cataloged source capability.
uv run python tools/public_records_search_plan.py "<QUERY>" \
  --output "$WORKDIR/search-public-record-plan.json"

# Unified property records (normalized local observations by default)
uv run python tools/query_property.py owner "<QUERY>" --output "$WORKDIR/search-property.json"
uv run python tools/query_property.py sources \
  --output "$WORKDIR/search-property-sources.json"

# Unified state/local court records and source inventory
uv run python tools/query_state_courts.py search "<QUERY>" --output "$WORKDIR/search-state-courts.json"
uv run python tools/query_state_courts.py sources \
  --output "$WORKDIR/search-state-court-sources.json"

# If the plan selects a catalog route such as an account, formal feed, paid
# product, request, or physical office, render the concrete acquisition action.
uv run python tools/public_records_actions.py plan <SOURCE_ID> \
  --operation <OPERATION> --selector "<QUERY>" \
  --output "$WORKDIR/search-public-record-action.json"

# FEC campaign finance
uv run python tools/query_fec.py donor "<QUERY>" --limit 20 --output "$WORKDIR/search-fec.json"

# Federal lobbying disclosures
uv run python tools/query_lobbying.py client "<QUERY>" --output "$WORKDIR/search-lobbying.json"

# FARA foreign agents
uv run python tools/query_fara.py search "<QUERY>" --output "$WORKDIR/search-fara.json"

# GLEIF corporate hierarchy (LEI records — financial entities only)
uv run python tools/query_gleif.py search "<QUERY>" --limit 10 --output "$WORKDIR/search-gleif.json"

# UK Companies House (if API key configured)
uv run python tools/ingest_uk_companies_house.py search "<QUERY>" --limit 10 --output "$WORKDIR/search-uk-companies.json"
uv run python tools/ingest_uk_companies_house.py officer-search "<QUERY>" --limit 10 --output "$WORKDIR/search-uk-officers.json"

# OpenSanctions (PEP/sanctions check — if ingested)
uv run python tools/query_opensanctions.py search "<QUERY>" --limit 10 --output "$WORKDIR/search-opensanctions.json"

# SEC Enforcement Actions (litigation releases, admin proceedings, AAERs)
uv run python tools/query_sec_enforcement.py search "<QUERY>" --limit 10 --output "$WORKDIR/search-sec-enforcement.json"

# DS10 Deutsche Bank financial records (entity/counterparty search)
uv run python tools/parse_ds10_financials.py query --entity "<QUERY>" > "$WORKDIR/search-ds10.txt"

# USVI corporate registry (Catalyst web scraper — search only, no bulk)
uv run python tools/ingest_usvi.py search "<QUERY>" > "$WORKDIR/search-usvi.txt"

# DC DLCP (ArcGIS FeatureServer — 492K entities, no auth)
uv run python tools/ingest_dc.py search "<QUERY>" --output $WORKDIR/search-dc.json

# California SoS bizfileonline (web API, up to 500 results, needs MCP Playwright Chrome)
uv run python tools/query_california.py search "<QUERY>" --output $WORKDIR/search-ca-sos.json

# Texas Comptroller (franchise tax entities — no auth)
uv run python tools/query_texas.py search "<QUERY>" --output $WORKDIR/search-tx.json

# Michigan LARA (business registry — Playwright browser helper, Cloudflare WAF)
uv run python tools/query_michigan.py search "<QUERY>" --contains --output $WORKDIR/search-mi.json

# New Jersey Division of Revenue (business entity name search — no detail pages)
uv run python tools/query_newjersey.py search "<QUERY>" --output $WORKDIR/search-nj.json

# Massachusetts Corporations Division (Playwright browser helper, Incapsula WAF)
uv run python tools/query_massachusetts.py search "<QUERY>" --output $WORKDIR/search-ma.json

# Shodan (infrastructure recon — DNS, SSL certs, hosting, org footprint — paid plan)
uv run python tools/query_shodan.py search "ssl:<QUERY>" --output $WORKDIR/search-shodan-ssl.json
uv run python tools/query_shodan.py domain "<QUERY>" --output $WORKDIR/search-shodan-domain.json

# crt.sh Certificate Transparency (subdomain enum, cert timeline — free, no auth)
uv run python tools/query_crtsh.py search "<QUERY>" --output $WORKDIR/search-crtsh.json

# Wayback Machine (historical web snapshots — free, no auth)
uv run python tools/query_wayback.py timeline "<QUERY>" --output $WORKDIR/search-wayback.json

# URLScan.io (passive web scans — tech stacks, linked domains — free)
uv run python tools/query_urlscan.py search "domain:<QUERY>" --output $WORKDIR/search-urlscan.json

# OffshoreAlert (29K+ offshore court cases, articles, MLATs, regulatory actions)
uv run python tools/offshorealert_search.py search "<QUERY>" -v --output $WORKDIR/search-offshorealert.json

# USAspending (federal contracts, grants, loans — no auth)
uv run python tools/query_usaspending.py awards "<QUERY>" --output $WORKDIR/search-usaspending-contracts.json
uv run python tools/query_usaspending.py awards "<QUERY>" --grants --output $WORKDIR/search-usaspending-grants.json
uv run python tools/query_usaspending.py subawards "<QUERY>" --output $WORKDIR/search-usaspending-subs.json

# SAM.gov API (entity registrations, exclusions/debarments — requires SAM_API_KEY)
uv run python tools/query_sam.py entity "<QUERY>" --output $WORKDIR/search-sam-entity.json
uv run python tools/query_sam.py exclusions "<QUERY>" --output $WORKDIR/search-sam-exclusions.json
uv run python tools/query_sam.py contracts "<QUERY>" --output $WORKDIR/search-sam-contracts.json

# SAM.gov Bulk (874K entities, 167K exclusions — local SQLite, no API limit)
uv run python tools/ingest_sam.py search "<QUERY>" --output $WORKDIR/search-sam-bulk.json
```

Use the public-record plan's dependency order and capability labels to choose
direct adapters for addresses, parcels, recorder parties, case numbers, docket
entries, and documents. If an acquisition action should be tracked in the
investigation, rerun the rendered action with
`public_records_actions.py enqueue`. Preserve each result's source ID, status,
coverage, continuation, and warnings; a non-query route or unavailable source
is source coverage information, not a zero-result search.

### 1c. Investigation Corpus Tools (from profile)

Search any investigation-specific corpus tools listed in `corpus_tools` from the investigation profile. These are data sources tied to the active investigation (e.g., specialized document corpora, FOIA collections, case-specific databases). Run each tool listed in the profile that hasn't already been searched:

```bash
# Example — the actual tools depend on the investigation profile's corpus_tools list:
# uv run python tools/<corpus_tool>.py search "<QUERY>" --limit 10 --output $WORKDIR/search-<source>.json
```

Log each corpus tool search the same way as generic sources.

### 1d. Selector Pivot & Breach Data (selectors, not just names)

When the target is a **selector** (email, username, phone, domain, IP) rather than a person/entity name, fan it out in one call instead of querying sources individually:

```bash
# One selector -> linked selectors + candidate entities across aggregators (auto-logs to search_log)
uv run python tools/selector_pivot.py run "<SELECTOR>" --output $WORKDIR/pivot.json
# Include gated breach/leak adapters (Dehashed; consumes credits):
uv run python tools/selector_pivot.py run "<EMAIL>" --type email --enable-paid --output $WORKDIR/pivot.json
```

Free adapters (opensanctions, gleif, icij, littlesis, crt.sh, maigret) run by default; `--enable-paid` adds Dehashed (breach/credential records, fires only on the seed selector) and IntelX. Emits `pending_triage` leads — **leak-sourced links cap at `medium` confidence; corroborate against a primary record before promotion.**

Direct breach lookup (one selector, raw records):
```bash
uv run python tools/query_dehashed.py search --email "<EMAIL>" --output $WORKDIR/dehashed.json
uv run python tools/query_dehashed.py balance   # remaining credits
```

### 2. Log Each Search
After each query, log it to prevent redundant future searches:
```python
from tools.lead_tracker import log_search
log_search("<QUERY>", "kabass", result_count)
log_search("<QUERY>", "doj_vol11", result_count)
log_search("<QUERY>", "lmsband", result_count)
log_search("<QUERY>", "gleif", result_count)
log_search("<QUERY>", "uk_companies_house", result_count)
log_search("<QUERY>", "opensanctions", result_count)
log_search("<QUERY>", "sec_enforcement", result_count)
log_search("<QUERY>", "reporting", result_count)
log_search("<QUERY>", "government_releases", result_count)
log_search("<QUERY>", "property_records", result_count)
log_search("<QUERY>", "state_court_records", result_count)
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
- Group results by canonical evidence ID or underlying record before counting sources
- Treat mirrors, re-OCRs, and multiple indexes of the same document as redundant coverage, not corroboration
- Note which sources returned each deduplicated result
- Flag a claim as corroborated only when 2+ independent underlying records support it
- Flag results from only 1 source as needing verification

### 4. Present Consolidated Results

Format:
```
SEARCH: "<QUERY>" across 7 sources

=== CORROBORATED (2+ independent records) ===
<CLAIM_1> — [Independent record A, Independent record B]
  Description of corroborated finding

=== REDUNDANT / MULTI-INDEX COVERAGE ===
<DOC_ID_2> — [Index A, mirror B, re-OCR C]
  One underlying document; useful cross-check, not corroboration

=== SINGLE-SOURCE ===
[Source file #12345] — <QUERY> mentioned in document
[Unified triple] — Subject -> arranged meeting -> Target @ Location, date

=== SOURCE COVERAGE ===
Kabasshouse:  15 hits
DOJ Vol 11:   8 hits (cross-check only — same EFTA pages as Kabasshouse)
LMSBAND:      3 hits
Unified:      5 hits
Registry:     2 hits (FL, NY)
Aleph:        4 hits
CourtListener: 1 hit
Property records: 2 hits (list source IDs and jurisdictions)
State/local courts: 1 hit (or report human_required/terms_blocked/unavailable)
990:          0 hits
UCC:          0 hits
GDELT:        12 hits (articles), 8 hits (context)
ICIJ:         0 hits (official remote search completed)
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

- **All searches above use `--output` or explicit `$WORKDIR` redirection** — this is critical for keeping context lean
- **Do NOT `cat` or `Read` the output JSON files unless you need specific details** for a finding
- If spawned as a sub-agent, write results to `$WORKDIR/report-search-<query-slug>.md` using the consolidated results format from section 4 above.
