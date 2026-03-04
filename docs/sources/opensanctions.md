# OpenSanctions

**URL:** https://www.opensanctions.org/
**Jurisdiction:** Global
**Auth:** None (bulk download, local SQLite)
**Tool:** `tools/query_opensanctions.py`
**Citation prefix:** `OPENSANCTIONS:ENTITY_ID`

## Access

- **Method:** Bulk download → local SQLite (`datasets/opensanctions.db`)
- **Rate limits:** N/A (local queries)
- **Cost:** Free (data is CC-BY licensed)
- **Coverage dates:** Continuously updated; sanctions records from 1990s — present

## Schema

| Field | Type | Description |
|-------|------|-------------|
| entity_id | string | OpenSanctions entity ID |
| schema | string | Entity type (Person, Company, LegalEntity, etc.) |
| name | string | Primary name |
| aliases | array | Known aliases |
| birth_date | date | For persons |
| countries | array | Associated countries |
| datasets | array | Source sanction lists (OFAC SDN, EU, UN, etc.) |
| topics | array | Classification (sanction, debarment, PEP, crime, etc.) |
| addresses | array | Known addresses |
| identifiers | array | Passport numbers, national IDs, etc. |

## Subcommands

```bash
uv run python tools/query_opensanctions.py search "NAME" [--limit N]
uv run python tools/query_opensanctions.py entity ENTITY_ID
uv run python tools/query_opensanctions.py dataset DATASET_NAME
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| Corporate Registry | Entity/person name | Screen registered agents/officers |
| SEC EDGAR | Company/person name | Flag sanctioned entities in filings |
| USAspending | Recipient name | Identify sanctioned contractors |
| FEC | Contributor name | Flag sanctioned donors |
| FDIC BankFind | Institution name | Sanctioned bank check |
| CourtListener | Party name | Sanctions-related litigation |

## Known Issues

- Name matching requires fuzzy search — sanctions lists use transliterated names
- Some entities appear in multiple datasets with slightly different records
- Local DB requires periodic refresh (bulk download) for current data
- PEP (Politically Exposed Person) records may have stale office dates
- OFAC SDN is the most reliable for US sanctions; other lists vary in quality

## Example Queries

```bash
# Search for a sanctioned entity
uv run python tools/query_opensanctions.py search "Deripaska" --limit 10

# Get full entity details
uv run python tools/query_opensanctions.py entity Q123456
```
