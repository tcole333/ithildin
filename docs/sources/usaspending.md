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

## Protocol

1. Search for contracts and grants separately
2. Check subawards (reveals subcontractor relationships)
3. Timeline view to see spending patterns over years
4. Cross-reference with SAM.gov for entity registration details

```bash
uv run python tools/query_usaspending.py awards "TARGET" --output $WORKDIR/usa-contracts.json
uv run python tools/query_usaspending.py awards "TARGET" --grants --output $WORKDIR/usa-grants.json
uv run python tools/query_usaspending.py subawards "TARGET" --output $WORKDIR/usa-subs.json
uv run python tools/query_usaspending.py timeline "TARGET" --group fiscal_year --output $WORKDIR/usa-timeline.json
# For specific awards:
uv run python tools/query_usaspending.py award AWARD_ID --output $WORKDIR/usa-award.json
```

Also search SAM.gov and SAM Bulk:
```bash
uv run python tools/query_sam.py entity "TARGET" --output $WORKDIR/sam-entity.json
uv run python tools/query_sam.py exclusions "TARGET" --output $WORKDIR/sam-exclusions.json
uv run python tools/ingest_sam.py search "TARGET" --output $WORKDIR/sam-bulk.json
```

For richer data (vehicle tracking, teaming data):
```bash
uv run python tools/query_highergov.py contract --awardee-uei UEI --output $WORKDIR/hg-contracts.json
uv run python tools/query_highergov.py partnership --awardee-key KEY --output $WORKDIR/hg-partners.json
```

## What To Look For

- **Award concentration**: Few large contracts vs. many small ones
- **Agency relationships**: Which agencies fund this entity?
- **Subaward chains**: Who are the subcontractors? (Often more revealing than prime)
- **Geographic patterns**: Place of performance vs. entity registration
- **Exclusions/debarments**: SAM.gov exclusion = government blacklist
- **Spending timeline**: Sudden spikes or drops correlate with policy changes or events

## Output

`--output $WORKDIR/<prefix>-usa-*.json`, `$WORKDIR/<prefix>-sam-*.json`, `$WORKDIR/<prefix>-hg-*.json`

## Findings

- Award records: `claim_type=direct_quote` (government records)
- Spending pattern analysis: `claim_type=inference`
- `--sources usaspending sam highergov`
