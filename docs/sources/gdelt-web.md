# GDELT & Web Search

## GDELT (Global News Monitoring)

**URL:** https://api.gdeltproject.org/
**Auth:** None
**Tool:** `tools/query_gdelt.py`
**Coverage:** 3-month rolling window of global news

### Protocol

```bash
uv run python tools/query_gdelt.py articles "TARGET" --limit 30 --output $WORKDIR/gdelt-articles.json
uv run python tools/query_gdelt.py context "TARGET" --limit 20 --output $WORKDIR/gdelt-context.json
```

### What To Look For

- **Media coverage volume**: Spike analysis — when did coverage increase?
- **Source geography**: Which countries' media cover this target?
- **Tone analysis**: Positive vs. negative coverage patterns
- **Co-mentioned entities**: Who appears alongside the target in news?

## Web Search & Fetch

Use WebSearch and WebFetch tools directly (not Bash).

### Protocol

```
WebSearch: "TARGET" — basic biography
WebSearch: "TARGET" {primary_subject} — known connections
WebSearch: "TARGET" lawsuit OR investigation OR scandal
WebSearch: "TARGET" site:opencorporates.com OR site:linkedin.com
```

For key pages found:
```
WebFetch: Wikipedia page (if exists)
WebFetch: Corporate/firm website about/team page
WebFetch: Key news articles for fact extraction
```

### What To Look For

- **Biographical data**: Current position, employer, education
- **Public reporting**: Existing investigative journalism on the target
- **LinkedIn/social**: Professional network, endorsements, career history
- **Wikipedia**: Structured biography (use as starting point, never as evidence)

**Source reliability**: Web sources are secondary. Always verify against primary sources. News articles may have planted or suppressed stories.

## Findings

- GDELT articles: `claim_type=paraphrase`, `--sources gdelt`
- Web sources: `claim_type=paraphrase`, `--sources web_search` (with URL as evidence)
- Wikipedia: Starting point only — **never cite as evidence**
