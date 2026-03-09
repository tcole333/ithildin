# Sanctions & Watchlists

## OpenSanctions (Local)

**Tool:** `tools/query_opensanctions.py`
**Access:** Local SQLite (bulk ingest)

### Protocol

```bash
uv run python tools/query_opensanctions.py search "TARGET" --limit 10 --output $WORKDIR/sanctions-search.json
# If match found:
uv run python tools/query_opensanctions.py entity ENTITY_ID --output $WORKDIR/sanctions-entity.json
```

### What To Look For

- **PEP status**: Politically exposed persons (government officials, their families)
- **Sanctions listings**: OFAC, EU, UN — which list and why?
- **Debarment/exclusion**: Government contractor blacklisting
- **Associated entities**: Companies linked to sanctioned individuals
- **Listing dates**: When were they added? (correlate with events)

## Findings

- Sanctions matches: `claim_type=direct_quote` (government lists are primary sources)
- `--sources opensanctions`
