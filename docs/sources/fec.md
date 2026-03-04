# FEC Campaign Finance

**URL:** https://api.open.fec.gov/
**Jurisdiction:** United States (federal elections)
**Auth:** Free API key (DEMO_KEY works with low limits)
**Tool:** `tools/query_fec.py`
**Citation prefix:** `FEC:COMMITTEE_ID` or `FEC:CANDIDATE_ID`

## Access

- **Method:** REST API
- **Rate limits:** 1,000/hour with API key; 20/hour with DEMO_KEY
- **Cost:** Free (register at https://api.open.fec.gov/developers/)
- **Coverage dates:** 1979 — present

## Schema

| Field | Type | Description |
|-------|------|-------------|
| committee_id | string | Committee ID (e.g., `C00431445`) |
| candidate_id | string | Candidate ID (e.g., `P80001571`) |
| contributor_name | string | Individual/organization donor name |
| contribution_receipt_amount | number | Donation amount ($) |
| contribution_receipt_date | date | Donation date |
| contributor_employer | string | Donor's employer |
| contributor_occupation | string | Donor's occupation |
| contributor_city/state/zip | string | Donor address |

## Subcommands

```bash
uv run python tools/query_fec.py search "DONOR NAME" [--limit N]
uv run python tools/query_fec.py committee COMMITTEE_ID
uv run python tools/query_fec.py candidate CANDIDATE_ID
uv run python tools/query_fec.py donors --employer "COMPANY" [--min-amount 1000]
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| SEC EDGAR | Contributor employer / name | Executive donors → company filings |
| LittleSis | Contributor name | Power network mapping |
| USAspending | Contributor employer | Contractor → political donation links |
| OpenSanctions | Contributor name | PEP/sanctions check |
| Federal Lobbying | Committee / employer | Lobbying ↔ donation correlation |

## Known Issues

- DEMO_KEY rate limit is very low (20/hour) — register for a key
- Contributor name matching is fuzzy (same person may appear with variations)
- Employer field is self-reported and inconsistent
- Very large donors may have thousands of itemized contributions
- Schedule A (contributions) has different endpoints from Schedule B (disbursements)

## Example Queries

```bash
# Search for individual donor contributions
uv run python tools/query_fec.py search "Leslie Wexner" --limit 20

# Look up a specific committee
uv run python tools/query_fec.py committee C00431445

# Find all donors from a specific employer
uv run python tools/query_fec.py donors --employer "Apollo Global" --min-amount 5000
```
