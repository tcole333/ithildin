# GLEIF (LEI) & DS10 Financial Records

## GLEIF — Global Legal Entity Identifiers

**URL:** https://api.gleif.org/
**Auth:** None
**Tool:** `tools/query_gleif.py`

### Protocol

```bash
uv run python tools/query_gleif.py search "TARGET" --limit 10 --output $WORKDIR/gleif-search.json
# If LEI found:
uv run python tools/query_gleif.py hierarchy LEI --output $WORKDIR/gleif-hierarchy.json
uv run python tools/query_gleif.py relationships LEI --output $WORKDIR/gleif-rels.json
```

### What To Look For

- **Corporate hierarchy**: Parent-child entity ownership chains
- **Fund manager relationships**: Who manages which funds?
- **LEI status**: Active vs. lapsed — lapsed LEIs may indicate dissolved entities
- **Registered address**: Legal vs. headquarters address discrepancies
- **Ultimate parent**: Follow the chain to the top-level beneficial owner

## DS10 Deutsche Bank Financial Records

**Tool:** `tools/parse_ds10_financials.py`
**Access:** Local dataset (investigation-specific)

### Protocol

```bash
uv run python tools/parse_ds10_financials.py query --entity "TARGET" --output $WORKDIR/ds10-entity.json
uv run python tools/parse_ds10_financials.py query --counterparty "TARGET" --output $WORKDIR/ds10-counter.json
```

### What To Look For

- **Transaction flows**: Who is sending/receiving money?
- **Counterparty networks**: Same counterparties across multiple transactions
- **Amount patterns**: Round numbers, just-below-threshold amounts ($9,999)
- **Currency/jurisdiction**: Cross-border transactions, unusual currency pairs

## Findings

- LEI records: `claim_type=direct_quote`, `--sources gleif`
- DS10 records: `claim_type=direct_quote`, `--sources ds10_financial`
- Financial analysis: `claim_type=inference`
