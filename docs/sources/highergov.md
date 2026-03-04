# HigherGov

**URL:** https://www.highergov.com/
**Jurisdiction:** United States (federal)
**Auth:** Paid API key (`HIGHERGOV_API_KEY`)
**Tool:** `tools/query_highergov.py`
**Citation prefix:** `HIGHERGOV:AWARD_ID`

## Access

- **Method:** REST API
- **Rate limits:** 10 requests/second, 10,000 records/month
- **Cost:** Paid (2-week trial available)
- **Coverage dates:** Historical federal contract/grant data

## Schema

| Field | Type | Description |
|-------|------|-------------|
| award_id | string | Contract/grant award ID |
| awardee_key | integer | HigherGov entity ID |
| awardee_name | string | Recipient name |
| uei | string | Unique Entity Identifier |
| cage | string | CAGE code |
| vehicle_key | integer | Contract vehicle ID |
| naics | string | Industry classification |
| agency_key | integer | Awarding agency ID |
| amount | number | Award value ($) |

## Subcommands

```bash
uv run python tools/query_highergov.py contract --parent-award AWARD_ID
uv run python tools/query_highergov.py contract --awardee-uei UEI [--all-pages]
uv run python tools/query_highergov.py idv --vehicle-key KEY [--all-pages]
uv run python tools/query_highergov.py awardee --uei UEI
uv run python tools/query_highergov.py awardee --cage CAGE
uv run python tools/query_highergov.py subcontract --awardee-uei UEI
uv run python tools/query_highergov.py partnership --awardee-key KEY
uv run python tools/query_highergov.py vehicle --vehicle-key KEY
uv run python tools/query_highergov.py agency --agency-key KEY
uv run python tools/query_highergov.py opportunity --source-id "SOL_ID"
uv run python tools/query_highergov.py grant --awardee-uei UEI
uv run python tools/query_highergov.py people --email "name@agency.gov"
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| USAspending | Award ID, UEI | HigherGov adds vehicle/teaming data |
| SAM.gov | UEI, CAGE | Entity registration details |
| SEC EDGAR | Awardee name | Public company awardees |
| FEC | Awardee name / people | Political donation mapping |
| Corporate Registry | Awardee name | State registration details |
| OpenSanctions | Awardee name | Sanctions screening |

## Known Issues

- Paid API with monthly record limits (10K records/month) — budget queries carefully
- `--all-pages` can consume record quota quickly on large result sets
- Vehicle keys are HigherGov-specific IDs (e.g., WEXMAC 2.0 = 8751)
- People endpoint searches by email domain, useful for agency personnel mapping
- Partnership data reveals teaming arrangements not visible in USAspending

## Example Queries

```bash
# Look up a contractor by UEI
uv run python tools/query_highergov.py awardee --uei ZE2JVFS8ML75

# Find all contracts on a specific vehicle
uv run python tools/query_highergov.py idv --vehicle-key 8751 --all-pages

# Find subcontract relationships
uv run python tools/query_highergov.py subcontract --awardee-uei ZE2JVFS8ML75
```
