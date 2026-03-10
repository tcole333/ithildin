# Epstein Investigation — Agent Context Addendum

Case-specific context for agents working on the Epstein investigation profile. This supplements the generic platform instructions in `CLAUDE.md`.

## User Priorities
- **Financial & business mapping focus** — money flows, corporate structures, fund movements, entity traces over biographical/political threads
- Death circumstances / prison investigation deprioritized
- Query `investigation.db` for current counts rather than relying on snapshots

## Narrative Case File

`research/master.md` — the evolving narrative case file with structured analysis across all investigation threads.

## Document Corpora

| Corpus | Tool | Size | Notes |
|--------|------|------|-------|
| DOJ Vol 11 | `query_doj.py` | 331K OCR'd pages | FTS5 search, EFTA IDs. DB at `~/projects/epstein-docs/output/documents.db` |
| DugganUSA | `duggan_search.py` | 204K+ docs | All 12 DOJ datasets |
| LMSBAND | `query_lmsband.py` | 60K files, 851K entities | |
| Unified DB | `query_unified.py` | 70K docs, 56K entities | 107K triples |
| Epstein Files 20K | `ingest_epstein_20k.py` | 25,800 docs | House Oversight Committee release |
| EpsteinExposed | `ingest_epstein_exposed.py` | Persons, docs, flights | |

**EFTA IDs are the canonical reference** for DOJ documents (e.g., `EFTA02336502`). Always cite EFTA IDs when available.

## Source Reliability Overrides

- **NYT / Landon Thomas Jr.**: Extreme caution. Thomas was acting as deal broker (not just reporter) while covering Epstein.
- **Michael Wolff**: 303 emails with Epstein — not a source relationship but an operational one. Treat claims in his books as potentially coordinated narrative.
- **Miami Herald / Julie K. Brown**: Generally reliable investigative work. Verify specific claims against primary sources.

## Environment Paths

- DOJ Vol 11 DB: `~/projects/epstein-docs/output/documents.db`
- Obsidian vault: `~/Documents/Mines of Moria/epstein research/`

## Priority Sources (Not Yet Integrated)

| Source | Value |
|--------|-------|
| Giuffre v. Maxwell docket (SDNY 15-cv-7433) | Civil depositions |
| USVI v. JPMorgan exhibits (SDNY 1:22-cv-10904) | Financial evidence |
| DE corporate registry | Next state for `/add-registry` |

## Reference Files

These files contain detailed investigation context. Read on demand, not every session.

| File | Contents |
|------|----------|
| `investigations/epstein/key-identifiers.md` | Epstein emails, inner circle contacts, addresses, correspondents, EINs |
| `investigations/epstein/wave-results.md` | Detailed wave findings (W1-W12 + K&E) |
| `investigations/epstein/investigation-context.md` | Wave summaries, critical intelligence, registry findings |
| `investigations/epstein/990-findings.md` | IRS 990 grant breakdowns (71 filings, 219 grants, $30.6M) |
