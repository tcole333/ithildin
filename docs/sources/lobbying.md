# Federal Lobbying (LDA) & FARA

**URL:** https://lda.senate.gov/api/ (LDA), https://efile.fara.gov/ (FARA)
**Jurisdiction:** United States
**Auth:** None
**Tool:** `tools/query_lobbying.py` (LDA), `tools/query_fara.py` (FARA)

## Access

- **Method:** REST API (LDA), local SQLite (FARA after ingest)
- **Cost:** Free

## Protocol — LDA Lobbying

Search three dimensions: client, registrant (lobbying firm), and individual lobbyist.

```bash
uv run python tools/query_lobbying.py client "TARGET" --output $WORKDIR/lda-client.json
uv run python tools/query_lobbying.py registrant "TARGET" --output $WORKDIR/lda-registrant.json
uv run python tools/query_lobbying.py lobbyist "TARGET" --output $WORKDIR/lda-lobbyist.json
# If filings found:
uv run python tools/query_lobbying.py filings --client "TARGET" --output $WORKDIR/lda-filings.json
```

## Protocol — FARA

Search for foreign principal registrations, then pull detail.

```bash
uv run python tools/query_fara.py search "TARGET" --output $WORKDIR/fara-search.json
# If found:
uv run python tools/query_fara.py detail REG_NUM --output $WORKDIR/fara-detail.json
```

## What To Look For

- **Client-lobbyist relationships**: Who hired whom? What issues?
- **Revolving door**: Former government officials now lobbying (check career arcs)
- **Foreign principal registrations**: FARA reveals foreign government/entity influence
- **Issue areas**: What specific legislation or policy was targeted?
- **Spending amounts**: Large lobbying spend on narrow issues reveals high stakes
- **Covered official contacts**: Who in government was contacted?

## Output

`--output $WORKDIR/<prefix>-lda-*.json`, `$WORKDIR/<prefix>-fara-*.json`

## Findings

- Lobbying filings: `claim_type=direct_quote` (government filings)
- Influence pattern analysis: `claim_type=inference`
- `--sources lobbying fara`
