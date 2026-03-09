# LittleSis

**URL:** https://littlesis.org/
**Jurisdiction:** United States (primarily)
**Auth:** None
**Tool:** `tools/query_littlesis.py`

## Access

- **Method:** REST API
- **Cost:** Free
- **Coverage:** Curated power network relationships — board seats, donations, lobbying

## Protocol

1. Search for the target entity/person
2. If found, pull the entity profile
3. Pull all relationships (limit 50)
4. Pull relationships by category for focused analysis

```bash
uv run python tools/query_littlesis.py search "TARGET" --output $WORKDIR/ls-search.json
# If found (note entity ID):
uv run python tools/query_littlesis.py entity ID --output $WORKDIR/ls-entity.json
uv run python tools/query_littlesis.py relationships ID --limit 50 --output $WORKDIR/ls-rels.json
uv run python tools/query_littlesis.py relationships ID --category 5 --output $WORKDIR/ls-donations.json
uv run python tools/query_littlesis.py relationships ID --category 1 --output $WORKDIR/ls-positions.json
uv run python tools/query_littlesis.py connections ID --output $WORKDIR/ls-connections.json
```

**Relationship categories:** 1=Position, 2=Education, 3=Membership, 4=Family, 5=Donation, 6=Transaction, 7=Lobbying, 8=Social, 9=Professional, 10=Ownership, 11=Hierarchy, 12=Generic

## What To Look For

- **Pre-mapped network**: LittleSis is curated — its relationships are human-verified
- **Board interlocks**: Shared board memberships across organizations
- **Donation networks**: Who donates to whom (amounts, dates)
- **Position history**: Career timeline with organizations
- **Connections depth**: Who is 1-2 hops away in the power network?

## Output

`--output $WORKDIR/<prefix>-ls-*.json`

## Findings

- LittleSis relationships: `claim_type=paraphrase` (curated secondary source)
- `--sources littlesis`
