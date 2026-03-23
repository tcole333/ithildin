# Court Records & Legal

Tools for US federal/state court dockets, opinions, judge research, and European Court of Human Rights cases.

**When to read this module:** When running /analyze-case, /deep-investigate (Agent C), or researching litigation history, judicial conflicts of interest, or ECHR proceedings for any entity.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_courtlistener.py` | CourtListener/RECAP API (v4) | `COURTLISTENER_TOKEN` in .env | No | Reasonable (API token required) |
| `query_hudoc.py` | HUDOC REST API (undocumented) | None | No | 0.5s between requests |

## query_courtlistener.py — CourtListener/RECAP

Comprehensive US court research: docket search, party/attorney/firm lookup, opinion text, RECAP document search and download, citation graphs, judge career timelines, financial disclosures, investment holdings, travel reimbursements, and FJC Integrated Database queries. Recently rebuilt with 17 commands.

**Auth:** Requires `COURTLISTENER_TOKEN` in `.env`. Free accounts available at courtlistener.com.

### Search Commands

```bash
# Generic search with field operators (type: r=RECAP, o=opinions, p=people)
uv run python tools/query_courtlistener.py search "Jeffrey Epstein" --type r --limit 20
uv run python tools/query_courtlistener.py search --party "Ghislaine Maxwell" --court nysd
uv run python tools/query_courtlistener.py search --attorney "David Boies" --type r
uv run python tools/query_courtlistener.py search --firm "Kirkland" --after 2020-01-01
uv run python tools/query_courtlistener.py search "fraud" --docket-number "1:23-cv-01234"
uv run python tools/query_courtlistener.py search "Epstein" --semantic --highlight

# RECAP docket search (shortcut for type=r with case-specific output)
uv run python tools/query_courtlistener.py cases "Epstein" --court nysd
uv run python tools/query_courtlistener.py cases "Maxwell" --after 2019-01-01 --before 2023-01-01

# Party search (returns parties, attorneys, firms)
uv run python tools/query_courtlistener.py party "Ghislaine Maxwell" --limit 20
uv run python tools/query_courtlistener.py party "Apollo Global" --court nysd

# Opinion search (with optional semantic search)
uv run python tools/query_courtlistener.py opinions "Epstein" --court ca2
uv run python tools/query_courtlistener.py opinions "qualified immunity" --semantic
```

### Docket & Document Commands

```bash
# Docket detail by ID
uv run python tools/query_courtlistener.py docket 16066603

# RECAP document search (filings, motions, exhibits)
uv run python tools/query_courtlistener.py recap-search "motion to dismiss" --court nysd

# Download RECAP document PDF
uv run python tools/query_courtlistener.py download "https://storage.courtlistener.com/..." --output-file /tmp/doc.pdf
uv run python tools/query_courtlistener.py download "recap/..." --output-file /tmp/doc.pdf --extract-text

# Full opinion text by opinion ID or cluster ID
uv run python tools/query_courtlistener.py opinion 12345678 --lines 500

# Opinion cluster details (citation count, precedential status)
uv run python tools/query_courtlistener.py cluster 98765
```

### Citation & Reference Commands

```bash
# Citation graph (what this opinion cites and what cites it)
uv run python tools/query_courtlistener.py citations 98765 --limit 50

# Resolve citation text to CourtListener cluster IDs
uv run python tools/query_courtlistener.py resolve-cite "521 U.S. 702"
```

### Judge Research Commands

```bash
# Search judges by name
uv run python tools/query_courtlistener.py judge "Preska" --limit 10

# Full career timeline (positions, education, political affiliations)
uv run python tools/query_courtlistener.py career "Loretta Preska"

# Financial disclosures
uv run python tools/query_courtlistener.py disclosures --person-id 1234
uv run python tools/query_courtlistener.py disclosures --person-id 1234 --year 2022

# Investment holdings search (by company/description)
uv run python tools/query_courtlistener.py investments "Apollo Global" --limit 20
uv run python tools/query_courtlistener.py investments "JPMorgan" --person-id 1234

# Travel reimbursements (by source organization)
uv run python tools/query_courtlistener.py reimbursements "Federalist Society" --limit 20
uv run python tools/query_courtlistener.py reimbursements "Heritage Foundation" --person-id 1234
```

### FJC Integrated Database

```bash
# Federal case metadata (plaintiff, defendant, nature of suit, disposition)
uv run python tools/query_courtlistener.py fjc --plaintiff "United States" --nos 470 --after 2020-01-01
uv run python tools/query_courtlistener.py fjc --defendant "Epstein" --limit 50
```

### Known Quirks

- The `opinion` command tries the opinion ID first, then falls back to treating it as a cluster ID (fetches first sub-opinion from the cluster).
- `download` with `--extract-text` requires `pymupdf` (`uv add pymupdf`).
- The `search` command supports field operators: `party:`, `firm:`, `attorney:`, `assignedTo:`, `docketNumber:` -- these can be combined with free text.
- `--semantic` enables vector-based semantic search (slower but finds conceptual matches).
- Court codes use CourtListener format: `nysd` (S.D.N.Y.), `ca2` (2nd Circuit), `scotus`, etc.
- The `career` command chains multiple API calls (person, positions, education, affiliations) -- budget for 4+ requests per invocation.

## query_hudoc.py — ECHR Case Database

Searches European Court of Human Rights judgments, decisions, and communications (1959-present). ~20,000 judgments and ~100,000 decisions.

```bash
# Full-text search
uv run python tools/query_hudoc.py search "Ron Soffer"
uv run python tools/query_hudoc.py search "Soffer, avocat" --limit 20

# Case detail by item ID
uv run python tools/query_hudoc.py case 001-99808

# Lookup by application number
uv run python tools/query_hudoc.py appno "34868/03"

# Filter by respondent state
uv run python tools/query_hudoc.py respondent ROU --limit 50

# Full case text (HTML-to-text conversion)
uv run python tools/query_hudoc.py text 001-99808
```

### Known Quirks

- Uses an undocumented REST API at `hudoc.echr.coe.int/app/query/results`.
- Respondent codes are ISO 3166-1 alpha-3 (e.g., `ROU` for Romania, `GBR` for UK, `TUR` for Turkey).
- Rate limiting is polite (0.5s between requests) with retry on 429.
- Results include fields: `itemid`, `docname`, `respondent`, `extractedappno`, `conclusion`, `kpdate`.
- The `text` command fetches the HTML body and converts to plain text. Useful for searching specific language in judgments (e.g., counsel names that appear in the body but not metadata).

## Skills Using These Tools

| Skill | Tools Used |
|-------|-----------|
| `/analyze-case` | `query_courtlistener.py` (docket, recap-search, opinion, citations, party) |
| `/deep-investigate` (Agent C) | `query_courtlistener.py` (search, cases, party, opinions, judge, disclosures, investments) |
| `/investigate-person` | `query_courtlistener.py` (party, search), `query_hudoc.py` (search) |
| `/systemic-analysis` | `query_courtlistener.py` (fjc, investments, reimbursements) |

## Common Investigation Patterns

### Litigation history for a person/entity
1. `party "Entity Name"` -- find all cases
2. `docket <ID>` -- get case details for interesting hits
3. `recap-search "Entity Name" --court nysd` -- find specific filings
4. `download <URL> --extract-text` -- get document text

### Judicial conflict-of-interest check
1. `judge "Judge Name"` -- get person ID
2. `career "Judge Name"` -- positions, education, affiliations
3. `disclosures --person-id <ID>` -- financial disclosures
4. `investments "Company Name" --person-id <ID>` -- specific holdings
5. `reimbursements "Organization" --person-id <ID>` -- travel/gifts

### Citation chain analysis
1. `opinions "topic" --court ca2` -- find relevant opinions
2. `cluster <ID>` -- get cluster details and sub-opinions
3. `citations <cluster_id>` -- see what it cites and what cites it
4. `resolve-cite "521 U.S. 702"` -- resolve a specific citation
