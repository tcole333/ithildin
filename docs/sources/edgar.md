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

## Protocol

1. Full-text search with `--facets` to see entity/form-type distribution
2. Lookup the target's CIK if they're a filer
3. Search for the target paired with associated entities
4. Check insider transactions if CIK found
5. Read specific filings (proxy statements DEF 14A, 10-K, 8-K) for named individuals

```bash
uv run python tools/query_edgar.py search "TARGET" --size 20 --facets --output $WORKDIR/edgar-search.json
uv run python tools/query_edgar.py lookup "TARGET" --output $WORKDIR/edgar-lookup.json
uv run python tools/query_edgar.py search "TARGET" "ASSOCIATED_ENTITY" --size 10 --output $WORKDIR/edgar-cross.json
# If CIK found:
uv run python tools/query_edgar.py insider CIK --detail --limit 10 --output $WORKDIR/edgar-insider.json
uv run python tools/query_edgar.py filings CIK --form "DEF 14A" --output $WORKDIR/edgar-proxy.json
# Read a specific filing:
uv run python tools/query_edgar.py read "FILING_URL" --lines 200
```

## What To Look For

- **Named individuals**: Officers, directors, beneficial owners in proxy statements
- **Related party transactions**: Section in 10-K that reveals entity relationships
- **Insider transactions**: Form 4 filings show stock trades by insiders
- **SC 13D**: Beneficial ownership above 5% — reveals major stakeholders
- **8-K**: Material events — executive changes, acquisitions, legal proceedings
- **Enforcement actions**: SEC complaints and administrative proceedings

## Output

`--output $WORKDIR/<prefix>-edgar-*.json`

## Findings

- Filing text quotes: `claim_type=direct_quote`
- Filing summaries: `claim_type=paraphrase`
- `--sources edgar`
