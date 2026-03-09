# Property & UCC Records

## NYC ACRIS (Property Transactions)

**URL:** NYC Open Data (SODA API)
**Auth:** None
**Tool:** `tools/query_acris.py`

### Protocol

```bash
uv run python tools/query_acris.py party "TARGET" --output $WORKDIR/acris-party.json
uv run python tools/query_acris.py batch-entities  # Cross-ref all investigation entities
```

### What To Look For

- **Property transactions**: Deeds, mortgages, liens — reveals real estate holdings
- **Entity-property links**: Shell companies used for real estate purchases
- **Transaction timing**: Property transfers before/after legal events
- **Counterparties**: Who is on the other side of the transaction?

## UCC Filings (Secured Transactions)

UCC filings are searched through the unified registry tool.

### Protocol

```bash
uv run python tools/query_registry.py ucc-search "TARGET" --output $WORKDIR/ucc-search.json
uv run python tools/query_registry.py ucc-party "TARGET" --role debtor --output $WORKDIR/ucc-debtor.json
uv run python tools/query_registry.py ucc-party "TARGET" --role secured --output $WORKDIR/ucc-secured.json
uv run python tools/query_registry.py ucc-collateral "aircraft" --output $WORKDIR/ucc-collateral.json
```

### What To Look For

- **Secured creditor relationships**: Who holds liens against the target?
- **Collateral types**: Aircraft, vehicles, accounts, inventory — reveals asset structure
- **Filing dates**: UCC filings before bankruptcy or dissolution
- **Blanket liens**: Creditor claiming "all assets" — distress signal

## FAA Aircraft Registry

**Tool:** `tools/ingest_faa.py`

```bash
uv run python tools/ingest_faa.py search "TARGET" --output $WORKDIR/faa-search.json
```

## Findings

- Property records: `claim_type=direct_quote`, `--sources acris`
- UCC filings: `claim_type=direct_quote`, `--sources ucc_filings`
- FAA records: `claim_type=direct_quote`, `--sources faa`
