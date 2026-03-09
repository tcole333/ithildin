# CourtListener / RECAP

**URL:** https://www.courtlistener.com/
**Jurisdiction:** United States (federal courts)
**Auth:** Free API key (token-based)
**Tool:** `tools/query_courtlistener.py`
**Citation prefix:** `CL:DOCKET_ID`

## Access

- **Method:** REST API
- **Rate limits:** 5,000 requests/day (authenticated)
- **Cost:** Free (register at courtlistener.com)
- **Coverage dates:** Varies by court; federal district courts 2000s — present; some appellate back to 1990s

## Schema

| Field | Type | Description |
|-------|------|-------------|
| docket_id | integer | Docket identifier |
| case_name | string | Case caption |
| court | string | Court identifier (e.g., `nyed`, `casd`) |
| date_filed | date | Filing date |
| date_terminated | date | Termination date (if closed) |
| parties | array | Party names and roles |
| docket_entries | array | Individual filings with descriptions |
| nature_of_suit | string | Case type classification |

## Subcommands

```bash
uv run python tools/query_courtlistener.py search "QUERY" [--court COURT] [--limit N]
uv run python tools/query_courtlistener.py docket DOCKET_ID
uv run python tools/query_courtlistener.py parties DOCKET_ID
uv run python tools/query_courtlistener.py opinions "QUERY"
```

## Cross-Reference Potential

| Target Source | Join Field | Notes |
|---------------|-----------|-------|
| SEC EDGAR | Party name | Company litigation → SEC filings |
| Corporate Registry | Party name | Identify corporate entities in cases |
| LittleSis | Party/attorney name | Power network legal connections |
| OpenSanctions | Party name | Sanctions-related cases |
| FEC | Party/attorney name | Political connections of litigants |

## Known Issues

- Auth token required: `COURTLISTENER_TOKEN` env var
- RECAP archive has best coverage for major federal cases; smaller courts may have gaps
- Party name extraction varies in quality across courts
- Docket entry descriptions may be cryptic (court-specific abbreviations)
- Rate limit is per-day, not per-second — burst queries are fine within daily limit

## Protocol

1. Search with `search` AND `party` AND `cases` (different indices return different results)
2. Search for `opinions` mentioning the target
3. Pull full `docket` for each case found
4. Extract: parties, timeline, related persons, nature of suit
5. Log each search: `log_search("QUERY", "courtlistener", count)`

```bash
uv run python tools/query_courtlistener.py search "TARGET" --output $WORKDIR/cl-search.json
uv run python tools/query_courtlistener.py party "TARGET" --output $WORKDIR/cl-party.json
uv run python tools/query_courtlistener.py cases "TARGET" --output $WORKDIR/cl-cases.json
uv run python tools/query_courtlistener.py opinions "TARGET" --limit 10 --output $WORKDIR/cl-opinions.json
# For each docket found:
uv run python tools/query_courtlistener.py docket DOCKET_ID --output $WORKDIR/cl-docket-ID.json
```

## What To Look For

- **Litigation patterns**: Repeated plaintiff/defendant roles, jurisdiction clustering
- **Co-parties**: Who appears alongside the target in cases?
- **Sealed filings**: Docket entries marked sealed or under protective order
- **Settlement patterns**: Cases terminated quickly after filing may indicate settlement
- **Regulatory actions**: SEC enforcement, FTC complaints, DOJ civil actions
- **Zero results is notable**: A practicing attorney with no CourtListener cases warrants investigation — it may mean state-level practice only or name variants

## Output

`--output $WORKDIR/<prefix>-cl-*.json`

## Findings

- Court opinions: `claim_type=direct_quote` (judicial statements)
- Docket summaries: `claim_type=paraphrase`
- `--sources courtlistener`
