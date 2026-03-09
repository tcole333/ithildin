# OCCRP Aleph & ICIJ Offshore Leaks

## OCCRP Aleph

**URL:** https://aleph.occrp.org/
**Auth:** Optional API key (ALEPH_API_KEY) for higher limits
**Tool:** `tools/query_aleph.py`

### Protocol

Search for Person and Company schemas separately. Expand entities found.

```bash
uv run python tools/query_aleph.py search "TARGET" --schema Person --output $WORKDIR/aleph-person.json
uv run python tools/query_aleph.py search "TARGET" --schema Company --output $WORKDIR/aleph-company.json
# If found:
uv run python tools/query_aleph.py expand ENTITY_ID --output $WORKDIR/aleph-expand.json
```

### What To Look For

- **Leaked documents**: Panama Papers, Paradise Papers, Pandora Papers entities
- **Corporate registry cross-references**: 200+ global datasets
- **Sanctions matches**: OFAC, EU, UN sanctions lists
- **Court records**: International court filings and judgments

## ICIJ Offshore Leaks

**URL:** (local Neo4j instance)
**Auth:** None (requires Neo4j running)
**Tool:** `tools/query_icij.py`

### Protocol

```bash
uv run python tools/query_icij.py search "TARGET" --output $WORKDIR/icij-search.json
uv run python tools/query_icij.py officers "TARGET" --output $WORKDIR/icij-officers.json
uv run python tools/query_icij.py connections "TARGET" --depth 2 --output $WORKDIR/icij-connections.json
```

Also available without Neo4j — reconciliation API:
```bash
uv run python tools/query_icij.py reconcile "TARGET" --output $WORKDIR/icij-reconcile.json
```

### What To Look For

- **Offshore entity ownership chains**: Who are the officers/directors/shareholders?
- **Intermediary patterns**: Which law firm/trust company set up the entity?
- **Jurisdiction patterns**: Why BVI? Why Panama? Each jurisdiction has specific advantages
- **Co-officer networks**: What other entities share the same officers?
- **Leak source**: Which leak (Panama, Paradise, Pandora, Bahamas) exposed this?

## Output

`--output $WORKDIR/<prefix>-aleph-*.json`, `$WORKDIR/<prefix>-icij-*.json`

## Findings

- Leaked document data: `claim_type=direct_quote`
- Cross-reference analysis: `claim_type=inference`
- `--sources aleph icij`
