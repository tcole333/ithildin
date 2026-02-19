---
name: add-registry
description: Add a new state/country corporate registry to the unified registry system
---

# /add-registry

Add a new state or country corporate registry as a data source, creating an ingester that feeds into the unified `registry.db` schema.

## Arguments

- Required: jurisdiction identifier (e.g., `/add-registry florida`, `/add-registry usvi`, `/add-registry bermuda`)

## Context

Corporate registries are primary sources for investigation — they show who controls entities, when they were created, who the officers are, and how structures changed over time. Each jurisdiction has its own access method:

- **Best case**: Bulk download via SFTP/FTP (Florida)
- **Good case**: Open data API (New York via Socrata)
- **Medium case**: Web portal with searchable forms (most states, USVI)
- **Hard case**: CAPTCHA-protected, pay-per-search (Delaware, BVI)

## Existing Registry Infrastructure

```bash
# Unified query tool (searches all ingested registries)
uv run python tools/query_registry.py search "Entity Name"
uv run python tools/query_registry.py officers "Person Name"
uv run python tools/query_registry.py address "457 Madison"
uv run python tools/query_registry.py stats

# Existing ingesters
uv run python tools/ingest_florida.py download && uv run python tools/ingest_florida.py ingest
uv run python tools/ingest_newyork.py search "Entity Name"
uv run python tools/ingest_newyork.py ingest-batch "Epstein" --with-filings
```

## Unified Schema (registry.db)

All registries feed into the same tables:

| Table | Purpose |
|-------|---------|
| `registry_entities` | One row per corporate entity (name, type, status, addresses, EIN, dates) |
| `registry_officers` | Officers/directors/managers with titles and addresses |
| `registry_agents` | Registered agents with addresses |
| `registry_filings` | Filing/event history (amendments, annual reports, name changes, dissolutions) |
| `registry_name_history` | Track entity name changes over time |
| `registry_ingest_log` | What was ingested and when |

Key fields for investigation:
- `source_jurisdiction` — two-letter code (fl, ny, vi, de, vg, bm, ky)
- `source_id` — original ID from the source registry
- Officer title codes: president, treasurer, director, secretary, VP, manager, member
- Filing history captures **changes** over time (director changes, address changes, name changes)

## Process

### 1. Research the Registry's Data Access

Before writing code, understand how the registry works:

```
Questions to answer:
- Does it have an API? (REST, SOAP, Socrata/SODA)
- Does it have bulk downloads? (FTP, SFTP, CSV, fixed-width)
- Is it a web portal that needs scraping? (Selenium/Playwright)
- What anti-scraping measures exist? (CAPTCHA, rate limiting, session tokens)
- What data fields are available? (name, officers, agent, addresses, filing history)
- What entity types are covered? (corp, LLC, LP, nonprofit, trust, foreign)
- Is officer/director information public? (not in Delaware)
- Are filing histories available? (with name changes, officer changes)
```

Use `WebSearch` and `WebFetch` to examine the registry portal, its API documentation, and any existing Python scrapers on GitHub.

### 2. Profile the API/Portal (MANDATORY — live discovery, not guessing)

**You MUST confirm working endpoints before writing the ingester tool.** Do not write code targeting speculative or guessed API URLs. The discovery process below is not optional.

**Step A: Probe for known API patterns**
```bash
# Test common endpoint patterns
curl -s "https://api.example.com/search?q=test" | python3 -m json.tool | head -40

# Check for Socrata/SODA
curl -s "https://data.state.gov/api/views" | head -20

# Check for FTP/SFTP
curl -s "ftp://ftp.state.gov/" --list-only
```

**Step B: Reverse-engineer web portals**
If the registry is a web portal with no documented API, inspect the page source to find the underlying API:
```python
# Use WebFetch to examine the portal's search page
# Look for: JavaScript API calls, form action URLs, XHR endpoints, Angular/React service URLs
```

Then systematically probe discovered endpoints:
```python
# Write a discovery script that tries each candidate endpoint
# Record: HTTP status, response content-type, response structure
# A 200 with JSON is a confirmed endpoint; a 404 means try another path
```

For SFTP/FTP bulk data:
```python
# Connect and LIST the actual directory tree before writing parsers
# Record: directory names, file names, file sizes, sample first lines
# Only write field parsers after examining the actual file format
```

**Step C: Document what you found**
Before proceeding to Step 3, you must have:
- The exact working endpoint URL (not a list of guesses)
- The required parameter names and formats (confirmed by a successful query)
- The response schema (from an actual response, not speculation)
- Rate limits and auth requirements (observed, not assumed)

If discovery fails (all endpoints return errors, CAPTCHA blocks access, etc.), report the failure clearly and create a human_action item. Do not write a tool that papers over the failure with try/except loops across speculative URLs.

### 3. Build the Ingester

Create `tools/ingest_<jurisdiction>.py` following the pattern:

```python
#!/usr/bin/env python3
"""
<State/Country> corporate registry ingester.
Feeds into registry.db via the unified schema.

Usage:
    uv run python tools/ingest_<jurisdiction>.py search "query"
    uv run python tools/ingest_<jurisdiction>.py ingest-entity <id>
    uv run python tools/ingest_<jurisdiction>.py ingest-batch "query"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from query_registry import get_db, _rebuild_fts

# ... implement search, ingest-entity, ingest-batch commands
# Map source fields to unified schema:
#   source_jurisdiction = "<two-letter-code>"
#   source_id = <registry's own entity ID>
#   entity_name, entity_type, status, formation_date, etc.
#   INSERT OR REPLACE INTO registry_entities (...)
#   INSERT OR IGNORE INTO registry_officers (...)
#   INSERT OR IGNORE INTO registry_agents (...)
#   INSERT OR IGNORE INTO registry_filings (...)
```

### 4. Map Fields to Unified Schema

Every registry has different field names. Create a mapping:

| Unified Field | Florida | New York | New Registry |
|--------------|---------|----------|-------------|
| entity_name | corp_name | current_entity_name | ? |
| entity_type | filing_type | entity_type | ? |
| status | status (A/I) | current_status | ? |
| formation_date | file_date | initial_dos_filing_date | ? |
| ein | fei_number | (not available) | ? |
| officer_name | officer block | chairman_name | ? |
| agent_name | ra_name | registered_agent_name | ? |

### 5. Test with Investigation Targets

After building, test against known Epstein-related entities:
```bash
# Pull current investigation targets dynamically
python3 -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('''
    SELECT DISTINCT target_name FROM findings
    WHERE finding_type IN ('financial', 'corporate')
    UNION
    SELECT name FROM entities
    LIMIT 20
''').fetchall()
for r in rows:
    print(r[0])
"
```

Also search known addresses:
- 9 East 71st St, New York
- 358 El Brillo Way, Palm Beach
- 457 Madison Ave, New York
- 6100 Red Hook Rd, St Thomas

### 6. Log and Update

```bash
# Verify the ingest
uv run python tools/query_registry.py stats
uv run python tools/query_registry.py jurisdictions

# Update CLAUDE.md data source inventory
# Update the search-all-sources skill to include registry queries
```

## Priority Jurisdictions for Investigation

| Jurisdiction | Code | Why | Access |
|-------------|------|-----|--------|
| **Florida** | `fl` | Palm Beach entities, bearer share LLCs | SFTP bulk (DONE) |
| **New York** | `ny` | 9 E 71st, 457 Madison, corporate HQ | SODA API (DONE) |
| **US Virgin Islands** | `vi` | Southern Trust, Little St. Jeff's, LSJE LLC | Web portal (Playwright) |
| **New Mexico** | `nm` | Zorro Ranch entities | REST API (DONE) |
| **Panama** | `pa` | Mossack Fonseca entities, offshore shells | Hybrid ICIJ+Aleph (DONE) |
| Delaware | `de` | Shell companies | CAPTCHA (hard) |
| British Virgin Islands | `vg` | Liquid Funding, offshore shells | Paid per-search |
| Bermuda | `bm` | Insurance vehicles | Limited access |
