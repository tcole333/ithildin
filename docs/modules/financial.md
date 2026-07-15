# Financial Analysis Tools

Tools for SEC filings, financial ratios, market data, nonprofit analysis, and enforcement actions.

**When to read this module:** When running /analyze-filing, /screen-targets, /compare-peers, /trace-grants, or investigating financial data for any entity.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_edgar.py` | SEC EDGAR EFTS + submissions API | None (User-Agent with contact required) | No | 10 req/sec |
| `financial_ratios.py` | Offline computation | None | Reads JSON from query_edgar | N/A |
| `query_market.py` | yfinance (Yahoo Finance) | None | No | Be polite (0.5s between multi-ticker) |
| `query_sec_enforcement.py` | Local SQLite (`datasets/sec_enforcement.db`) | None | Yes | N/A |
| `ingest_sec_enforcement.py` | SEC enforcement index pages | None | Writes `datasets/sec_enforcement.db` | Polite scraping |
| `query_990.py` | Local SQLite (`datasets/irs990_grants.db`) + ProPublica API | None | 22M+ grants, 5M+ officers, 600K+ financials | N/A (local); ProPublica is free |
| `query_fdic.py` | FDIC BankFind API | None | No | Reasonable |
| `query_finra.py` | FINRA BrokerCheck API | None | No | Reasonable |

## query_edgar.py — SEC EDGAR

Full-text search across all SEC filings via the EFTS index, plus company submissions, insider transactions, and filing content extraction.

**Critical quirk:** SEC returns 403 if User-Agent header lacks contact info. The tool sets `OSINT-Research osint-research@proton.me` automatically.

### Subcommands

```bash
# Full-text search (supports multi-term, date range, form filter, facets)
uv run python tools/query_edgar.py search "jeffrey epstein" --size 20
uv run python tools/query_edgar.py search "leon black" "gratitude america" --forms "10-K,DEF 14A"
uv run python tools/query_edgar.py search "enhanced education" --start 2010-01-01 --end 2020-01-01
uv run python tools/query_edgar.py search "wexner" --facets

# Company/person name to CIK resolution
uv run python tools/query_edgar.py lookup "apollo global"
uv run python tools/query_edgar.py lookup "leon black"

# Company info by CIK
uv run python tools/query_edgar.py company 0001411494

# Filing list (filtered by form type)
uv run python tools/query_edgar.py filings 0001411494 --form 10-K
uv run python tools/query_edgar.py filings 0001411494 --form "DEF 14A"

# Insider transactions (Forms 3/4/5)
uv run python tools/query_edgar.py insider 0001411494 --limit 30

# Fetch and read filing content (table-aware HTML extraction)
uv run python tools/query_edgar.py read "https://www.sec.gov/Archives/edgar/data/..."
uv run python tools/query_edgar.py read "https://www.sec.gov/Archives/edgar/data/..." --lines 200
uv run python tools/query_edgar.py read "https://www.sec.gov/Archives/edgar/data/..." --find "Malcolm Scott Macintyre" --context 3
uv run python tools/query_edgar.py read "https://www.sec.gov/Archives/edgar/data/..." --output "$WORKDIR/filing.json"

# Extract structured sections from 10-K/10-Q (uses edgartools)
uv run python tools/query_edgar.py sections PLTR --section mda
uv run python tools/query_edgar.py sections PLTR --section risk
uv run python tools/query_edgar.py sections PLTR --form 10-Q --section balance
```

**Sections aliases:** `business`/`item1`, `risk`/`risk_factors`/`item1a`, `mda`/`item7`, `legal`/`item3`, `balance`/`balance_sheet`, `income`/`income_statement`, `cash_flow`/`cashflow_statement`.

**Known quirks:**
- EFTS search ignores the `size` param server-side (returns up to 100); the tool slices client-side.
- `--sort date` and `--sort date-asc` are client-side sorts on the returned results.
- `sections` command requires the `edgartools` package.
- `read` previews 500 lines by default. Use repeatable `--find` for late-file matches or `--output` for the complete extracted text, including table footnotes.
- `filings` follows the SEC submissions metadata into older history segments, newest first, only until it reaches `--limit`. Date filters skip segments whose published date range cannot match, and each submissions response is capped at 25 MB.
- Direct filing retrieval uses declared SEC identity headers, bounded retries, and a 25 MB response limit. If an individual official Archive document returns 403, the tool makes one bounded attempt to extract that document from the accession's official complete-submission `.txt` file. It never uses this fallback for 429 rate-control responses or non-SEC hosts.

## financial_ratios.py — Ratio Analysis

Offline computation of profitability, liquidity, efficiency, solvency, and earnings quality ratios from JSON financial statements extracted by `query_edgar.py sections`.

```bash
# Analyze income + balance sheet
uv run python tools/financial_ratios.py analyze $WORKDIR/income.json $WORKDIR/balance.json

# With cash flow for quality metrics
uv run python tools/financial_ratios.py analyze income.json balance.json --cashflow cashflow.json

# Write the ratio analysis (including its anomaly flags) to a file
uv run python tools/financial_ratios.py analyze income.json balance.json --cashflow cf.json --output ratios.json
```

**Known quirks:** Matches XBRL concepts by suffix (e.g., `_AssetsCurrent`). Falls back to label substring matching if XBRL concepts are non-standard.

## query_market.py — Market Data

Stock prices, company profiles, insider transactions, and event correlation via yfinance.

```bash
uv run python tools/query_market.py price PLTR --period 6mo
uv run python tools/query_market.py history SMCI --start 2024-01-01 --end 2024-12-31
uv run python tools/query_market.py profile PLTR
uv run python tools/query_market.py insider SMCI --limit 30
uv run python tools/query_market.py correlate SMCI --events events.json --window 5
```

**Known quirks:** `yfinance` must be installed (`uv add yfinance`). The `correlate` command takes a JSON file of dated events and measures price movement within `--window` trading days.

## query_sec_enforcement.py — SEC Enforcement Actions

Query the local enforcement database for litigation releases, admin proceedings, and AAERs. Supports defendant search, co-defendant networks, repeat offender detection, and cross-referencing against `investigation.db` and `registry.db`.

```bash
uv run python tools/query_sec_enforcement.py search "insider trading"
uv run python tools/query_sec_enforcement.py search "Epstein" --source litigation
uv run python tools/query_sec_enforcement.py defendant "Leon Black" --fuzzy --threshold 80
uv run python tools/query_sec_enforcement.py action LR-26503
uv run python tools/query_sec_enforcement.py co-defendants LR-26489
uv run python tools/query_sec_enforcement.py network "Joseph Lewis" --depth 2
uv run python tools/query_sec_enforcement.py repeat-offenders --min-actions 2
uv run python tools/query_sec_enforcement.py stats --by-year
uv run python tools/query_sec_enforcement.py cross-ref --auto-leads --dry-run
```

**Prerequisite:** Run `uv run python tools/ingest_sec_enforcement.py ingest` first to build the database.

## ingest_sec_enforcement.py — SEC Enforcement Ingest

Scrapes SEC enforcement index pages and parses defendant names into `datasets/sec_enforcement.db`.

```bash
uv run python tools/ingest_sec_enforcement.py ingest                     # All sources, all pages
uv run python tools/ingest_sec_enforcement.py ingest --source litigation  # One source type
uv run python tools/ingest_sec_enforcement.py ingest --pages 3            # First 3 pages only
uv run python tools/ingest_sec_enforcement.py ingest --incremental        # Stop at existing entries
uv run python tools/ingest_sec_enforcement.py stats                       # Summary counts
uv run python tools/ingest_sec_enforcement.py reparse                     # Re-run defendant parsing
```

## query_990.py — IRS 990 Nonprofits

Unified local bulk DB (22M+ grants, 5M+ officers) plus ProPublica API enrichment for org metadata, NTEE codes, and filing PDFs.

```bash
uv run python tools/query_990.py search "Epstein"
uv run python tools/query_990.py lookup 660789697            # Comprehensive EIN view
uv run python tools/query_990.py filer 660789697
uv run python tools/query_990.py recipient "Gratitude"
uv run python tools/query_990.py recipient-ein 030213226
uv run python tools/query_990.py network 660789697 --depth 2
uv run python tools/query_990.py co-grantors "MELANOMA RESEARCH ALLIANCE"
uv run python tools/query_990.py cross-ref                   # Cross-ref against investigation.db
uv run python tools/query_990.py top --by amount --limit 20
uv run python tools/query_990.py officers 660789697
uv run python tools/query_990.py officer-search "John Smith"
uv run python tools/query_990.py financials 660789697
uv run python tools/query_990.py filings 660789697           # Filing list + PDF links
uv run python tools/query_990.py red-flags 660789697         # Schedule J/L, checklist flags
uv run python tools/query_990.py top-compensated --min-comp 500000
uv run python tools/query_990.py flow 660789697              # Grant flow analysis
uv run python tools/query_990.py shared-officers 660789697   # Officers shared with other orgs
```

**Known quirks:**
- FTS5 tables may not exist if bulk ingest was incomplete; falls back to LIKE queries automatically.
- ProPublica enrichment is optional and degrades gracefully if the module is unavailable.
- `cross-ref` matches 990 entities against `investigation.db` entities.

## query_fdic.py — FDIC Bank Data

Bank institutions, failures, financials, branches, and history from the FDIC BankFind API.

```bash
uv run python tools/query_fdic.py search "Deutsche Bank"
uv run python tools/query_fdic.py institution 59017
uv run python tools/query_fdic.py failures --state NY --year 2008
uv run python tools/query_fdic.py locations 59017
uv run python tools/query_fdic.py financials 59017 --date 20231231
uv run python tools/query_fdic.py history 59017
uv run python tools/query_fdic.py ingest 59017              # Save to investigation.db
```

**Known quirks:** FDIC uses Elasticsearch internally. Multi-word search uses first-word wildcard only (API does not support phrase wildcards). Agent-side filtering may be needed.

## query_finra.py — FINRA BrokerCheck

Broker/dealer registrations, employment history, disciplinary actions, and firm details.

```bash
uv run python tools/query_finra.py search "Leon Black" --limit 10
uv run python tools/query_finra.py search "Bear Stearns" --type firm
uv run python tools/query_finra.py detail 1234567            # Individual by CRD
uv run python tools/query_finra.py detail 1234567 --type firm
uv run python tools/query_finra.py disclosures 1234567
uv run python tools/query_finra.py employment 1234567
```

**Known quirks:** Detail responses contain a JSON-encoded `content` field inside the search hit `_source`; the tool auto-parses this. The API can be slow for large firm histories (60s timeout set).

## Skills Using These Tools

| Skill | Tools Used |
|-------|-----------|
| `/analyze-filing` | `query_edgar.py` (sections, filings, read), `financial_ratios.py` |
| `/screen-targets` | `query_edgar.py` (search, lookup), `query_finra.py`, `query_sec_enforcement.py` |
| `/compare-peers` | `query_edgar.py` (sections), `financial_ratios.py`, `query_market.py` |
| `/trace-grants` | `query_990.py` (network, flow, shared-officers, cross-ref) |
| `/deep-investigate` | `query_edgar.py`, `query_990.py`, `query_sec_enforcement.py`, `query_finra.py` |
