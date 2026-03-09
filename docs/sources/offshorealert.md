# OffshoreAlert

**URL:** https://www.offshorealert.com/
**Jurisdiction:** Bahamas, Bermuda, BVI, Cayman Islands, international
**Auth:** Credentials required (OFFSHOREALERT_EMAIL, OFFSHOREALERT_PASSWORD in .env)
**Tool:** `tools/offshorealert_search.py`

## Access

- **Method:** Web scraping (cloudscraper) + WP REST API
- **Coverage:** 29K+ offshore court cases, 4,500+ articles, 1,400+ MLATs, regulatory actions
- **Note:** Individual article pages gated behind reCAPTCHA. Search and API bypass this.

## Protocol

```bash
# Full search (court cases, articles, MLATs, regulatory)
uv run python tools/offshorealert_search.py search "TARGET" -v --output $WORKDIR/oa-search.json

# Articles only
uv run python tools/offshorealert_search.py search "TARGET" -a --output $WORKDIR/oa-articles.json

# WP REST API search (structured, no scraping)
uv run python tools/offshorealert_search.py api-search "TARGET" --output $WORKDIR/oa-api.json

# Entity extraction from search results
uv run python tools/offshorealert_search.py entities "TARGET" --output $WORKDIR/oa-entities.json
```

## What To Look For

- **Offshore court filings**: Liquidation proceedings, fraud cases, asset recovery
- **Regulatory actions**: Financial authority enforcement in offshore jurisdictions
- **MLAT requests**: Mutual Legal Assistance Treaty activity (cross-border cooperation)
- **Entity involvement patterns**: Same entity appearing across multiple offshore jurisdictions
- **Timeline of offshore activity**: Filing dates relative to onshore events

## Output

`--output $WORKDIR/<prefix>-oa-*.json`

## Findings

- Court filings: `claim_type=direct_quote` (legal records)
- Article summaries: `claim_type=paraphrase`
- `--sources offshorealert`
