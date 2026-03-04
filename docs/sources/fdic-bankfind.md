# FDIC BankFind

**URL:** https://api.fdic.gov/banks/
**Jurisdiction:** United States (FDIC-insured institutions)
**Auth:** None
**Tool:** `tools/query_fdic.py`
**Citation prefix:** `FDIC:CERT`

## Access

- **Method:** REST API (Elasticsearch-backed)
- **Rate limits:** No published limit; be respectful
- **Cost:** Free
- **Coverage dates:** Active institutions (current); failures back to 1934; financials quarterly

## Endpoints

| Endpoint | Path | Records | Description |
|----------|------|---------|-------------|
| Institutions | `/institutions` | ~4,600 active | Core bank data |
| Locations | `/locations` | ~78K | Branch-level data |
| Financials | `/financials` | ~1.67M | Quarterly statements |
| History | `/history` | ~581K | Structure change events |
| Failures | `/failures` | ~4,114 | Failed bank details |
| Summary | `/summary` | ~8K | Aggregate statistics |
| SOD | `/sod` | Varies | Summary of Deposits |

## Schema (Institutions)

| Field | Type | Description |
|-------|------|-------------|
| CERT | integer | FDIC certificate number (primary key) |
| REPNM / NAME | string | Institution name |
| CITY, STALP | string | Location |
| BKCLASS | string | Bank class (N, NM, SM, SB, etc.) |
| ACTIVE | integer | 1 = active, 0 = inactive |
| ASSET | number | Total assets ($K) |
| DEP | number | Total deposits ($K) |
| NETINC | number | Net income ($K) |
| ESTYMD | string | Establishment date |
| REPDTE | string | Report date (YYYYMMDD) |
| RSSDID | integer | Federal Reserve RSSD ID |

## Schema (Financials)

| Field | Type | Description |
|-------|------|-------------|
| REPDTE | string | Report date (YYYYMMDD) |
| ASSET | number | Total assets ($K) |
| LIAB | number | Total liabilities ($K) |
| EQ | number | Equity ($K) |
| DEP | number | Total deposits ($K) |
| NETINC | number | Net income ($K) |
| ROA | number | Return on assets (%) |
| ROE | number | Return on equity (%) |
| NIM | number | Net interest margin (%) |
| NUMEMP | integer | Employee count |

## Schema (Failures)

| Field | Type | Description |
|-------|------|-------------|
| CERT | integer | FDIC certificate number |
| NAME | string | Failed institution name |
| FAILDATE | string | Failure date (MM/DD/YYYY) |
| QBFASSET | number | Assets at failure ($K) |
| QBFDEP | number | Deposits at failure ($K) |
| COST | number | Estimated loss ($K) |
| APTS / ACQUIRER | string | Acquiring institution |
| RESTYPE | string | Resolution type |

## Subcommands

```bash
uv run python tools/query_fdic.py search "Deutsche Bank"
uv run python tools/query_fdic.py institution 59017
uv run python tools/query_fdic.py failures [--state NY] [--year 2008]
uv run python tools/query_fdic.py locations 59017
uv run python tools/query_fdic.py financials 59017 [--date 20231231]
uv run python tools/query_fdic.py history 59017
uv run python tools/query_fdic.py ingest 59017
```

## Query Parameters

All endpoints support:
- `search=TEXT` — full-text search
- `filters=FIELD:VALUE` — Elasticsearch filter syntax (AND/OR supported)
- `limit=N` — records per page
- `offset=N` — pagination offset

Filter examples: `CERT:59017`, `STATE:NY`, `REPDTE:20231231`, `FAILYR:2008`

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| FinCEN Files | Bank name | Match SARs to specific institutions |
| SEC EDGAR | Institution name | Bank holding company filings |
| USAspending | Institution name | Government deposits/contracts |
| OpenSanctions | Institution name | Sanctions screening |
| Corporate Registry | Institution name / address | State registration details |
| Deutsche Bank SARs | CERT / name | Map specific DB branches to SAR activity |

## Known Issues

- `search` parameter may return zero results for multi-word queries — use `filters` for precision
- All monetary values are in thousands ($K) — multiply by 1,000 for actual amounts
- Date format is YYYYMMDD in filters (no dashes)
- Response is nested: actual data is in `data[].data`, not `data[]` directly
- No officer/executive data available through this API
- CERT numbers are not sequential and can be reused after failures

## Example Queries

```bash
# Search for Deutsche Bank branches
uv run python tools/query_fdic.py search "Deutsche Bank" --limit 10

# Get quarterly financials
uv run python tools/query_fdic.py financials 59017 --limit 4

# Bank failures during 2008 financial crisis
uv run python tools/query_fdic.py failures --year 2008 --limit 50

# Ingest a bank into investigation.db
uv run python tools/query_fdic.py ingest 59017
```
