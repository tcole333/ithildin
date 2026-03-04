# USAspending

**URL:** https://api.usaspending.gov/
**Jurisdiction:** United States (federal)
**Auth:** None
**Tool:** `tools/query_usaspending.py`
**Citation prefix:** `USASPENDING:AWARD_ID`

## Access

- **Method:** REST API (POST for search, GET for lookups)
- **Rate limits:** No published limit; be respectful
- **Cost:** Free
- **Coverage dates:** FY2001 — present

## Schema

| Field | Type | Description |
|-------|------|-------------|
| Award ID | string | Unique award identifier (e.g., `CONT_AWD_...`) |
| Recipient | object | Name, UEI, DUNS, address |
| Awarding Agency | object | Agency name, subtier |
| Award Amount | number | Total obligation ($) |
| Period of Performance | date range | Start/end dates |
| NAICS | string | Industry classification code |
| PSC | string | Product/service code |
| Place of Performance | object | City, state, country, congressional district |
| Subawards | array | Sub-recipient details |
| Transactions | array | Individual transaction modifications |

## Subcommands

```bash
uv run python tools/query_usaspending.py search "QUERY" [--limit N]
uv run python tools/query_usaspending.py awards --recipient "NAME" [--type contracts|grants]
uv run python tools/query_usaspending.py award AWARD_ID
uv run python tools/query_usaspending.py recipient UEI
uv run python tools/query_usaspending.py subawards --award AWARD_ID
uv run python tools/query_usaspending.py transactions --award AWARD_ID
uv run python tools/query_usaspending.py geography --recipient "NAME"
uv run python tools/query_usaspending.py timeline --recipient "NAME"
uv run python tools/query_usaspending.py top-recipients --agency "AGENCY" [--fiscal-year YYYY]
uv run python tools/query_usaspending.py agencies
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| SAM.gov | UEI / DUNS | Entity registration details |
| HigherGov | Award ID, UEI | Richer contract/vehicle data |
| FPDS | Award ID | Raw procurement data |
| FEC | Recipient name | Contractor → political donations |
| SEC EDGAR | Recipient name | Public company filings |
| OpenSanctions | Recipient name | Sanctions/debarment check |
| FDIC BankFind | Recipient name | Bank institution lookup |

## Known Issues

- Search endpoint is POST-based with JSON body (not typical REST GET)
- Recipient name matching is approximate — try UEI for precision
- Subaward data may lag primary awards by 1-2 quarters
- Very large result sets (>10K) require pagination with `page` parameter
- Agency name formats vary between endpoints

## Example Queries

```bash
# Search for a contractor
uv run python tools/query_usaspending.py search "Booz Allen Hamilton" --limit 10

# Get all awards for a specific UEI
uv run python tools/query_usaspending.py awards --recipient-uei ZE2JVFS8ML75

# Timeline of spending to a recipient
uv run python tools/query_usaspending.py timeline --recipient "Palantir"
```
