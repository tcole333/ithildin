# Investigation Reports (Ingested PDFs)

**DB:** `datasets/investigations.db` (FTS5 full-text search)
**Auth:** None (local SQLite)
**Tool:** `tools/query_investigations.py`

## Protocol

Search ingested investigation reports (Congressional reports, GAO audits, IG reports, enforcement actions, etc.).

```bash
# Full-text search
uv run python tools/query_investigations.py search "TARGET" --limit 20 --output $WORKDIR/investigations-search.json

# Filter by category (enforcement, congressional, gao, ig, judicial, regulatory)
uv run python tools/query_investigations.py search "TARGET" --category enforcement --output $WORKDIR/investigations-cat.json

# Read specific document pages
uv run python tools/query_investigations.py read <DOC_ID> --pages 5-10

# List all ingested documents
uv run python tools/query_investigations.py list

# Database stats
uv run python tools/query_investigations.py stats
```

## What To Look For

- **Named mentions**: Target appearing in government investigation reports
- **Context of mentions**: Are they a subject, witness, or incidental reference?
- **Co-mentions**: Who else appears in the same reports?
- **Category patterns**: Enforcement actions vs. congressional hearings tell different stories
- **Page-level detail**: Read surrounding pages for full context of any mention

## Output

`--output $WORKDIR/<prefix>-investigations-*.json`

## Findings

- Direct quotes from reports: `claim_type=direct_quote` (primary government source)
- Summarized findings: `claim_type=paraphrase`
- `--sources investigations`
