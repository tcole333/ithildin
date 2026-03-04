# SEC EDGAR

**URL:** https://efts.sec.gov/LATEST/ (full-text), https://www.sec.gov/cgi-bin/browse-edgar (filings)
**Jurisdiction:** United States
**Auth:** None (requires User-Agent header with email)
**Tool:** `tools/query_edgar.py`
**Citation prefix:** `SEC_EDGAR:ACCESSION`

## Access

- **Method:** REST API (EFTS full-text search + EDGAR filing browser)
- **Rate limits:** 10 requests/second (SEC fair access policy)
- **Cost:** Free
- **Coverage dates:** 1993 — present (full text); 1930s — present (filing metadata)

## Schema

| Field | Type | Description |
|-------|------|-------------|
| accession_number | string | Unique filing ID (e.g., `0001193125-21-123456`) |
| form_type | string | Filing type (10-K, 10-Q, 8-K, DEF 14A, etc.) |
| company_name | string | Filer name |
| cik | integer | Central Index Key (entity ID) |
| date_filed | date | Filing date |
| file_url | string | Primary document URL |

## Subcommands

```bash
uv run python tools/query_edgar.py search "QUERY" [--form-type 10-K] [--date-range START:END]
uv run python tools/query_edgar.py filing ACCESSION
uv run python tools/query_edgar.py company CIK [--form-type 10-K]
uv run python tools/query_edgar.py insider CIK
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| OpenSanctions | Company name / CIK | PEP/sanctions check on filers |
| FEC | Company name / officer names | Political donation mapping |
| LittleSis | Officer names | Power network connections |
| USAspending | Company name | Government contract relationships |
| CourtListener | Company name | Litigation involving filers |
| FDIC BankFind | Company name | Bank financial comparison |

## Known Issues

- EFTS full-text search requires User-Agent header: `"OSINT-Research osint-research@proton.me"`
- Accession numbers use dashes (`0001193125-21-123456`) in URLs but dashless in some API paths
- Rate limiting is IP-based; 429 errors mean slow down
- Some older filings lack full-text indexing
- Form type filter is exact match (use `10-K` not `10K`)

## Example Queries

```bash
# Full-text search across all filings
uv run python tools/query_edgar.py search "Jeffrey Epstein" --limit 20

# Get a specific filing
uv run python tools/query_edgar.py filing 0001193125-21-123456

# All 10-K filings for a company
uv run python tools/query_edgar.py company 1166559 --form-type 10-K
```
