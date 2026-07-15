# Epstein Investigation — Agent Context Addendum

Case-specific context for agents working on the Epstein investigation profile. This supplements the generic platform instructions in `AGENTS.md`.

## User Priorities
- **Financial & business mapping focus** — money flows, corporate structures, fund movements, entity traces over biographical/political threads
- Death circumstances / prison investigation deprioritized
- Query `investigation.db` for current counts rather than relying on snapshots

## Narrative Case File

`research/master.md` — the evolving narrative case file with structured analysis across all investigation threads.

## Document Corpora

| Corpus | Tool | Size | Notes |
|--------|------|------|-------|
| **Kabasshouse (PRIMARY)** | `ingest_kabasshouse.py` | 1.42M OCR'd docs | **First stop for all Epstein full-text search.** DOJ DS1-12 + FBI + House re-OCR'd, + structured layers: 10.6M entities, 49.7K financial txns, 5.8K curated gold docs. Source key: `kabass` |
| Unified DB | `query_unified.py` | 70K docs, 56K entities | 107K semantic triples + co-occurrence — relationship layer, not text-redundant |
| LMSBAND | `query_lmsband.py` | 60K files, 851K entities | Unique structured financials (flights, positions, balances); text search redundant with Kabasshouse |
| Epstein Files 20K | `ingest_epstein_20k.py` | 25,800 docs | House Oversight Committee release, distinct `HOUSE_OVERSIGHT_*` IDs |
| FBI Files | `ingest_fbi_files.py` | 8,150 docs | FBI release (Textract OCR, FTS5), EFTA IDs + named exhibits (Flight Log, Contact Book, Evidence List from US v. Maxwell). Source key: `fbi` |
| EpsteinExposed | `ingest_epstein_exposed.py` | Persons, docs, flights | Person profiles/aliases; orthogonal to document corpora |
| DOJ Vol 11 | `query_doj.py` | 331K OCR'd pages | FALLBACK — strict subset of Kabasshouse. DB at `~/projects/epstein-docs/output/documents.db` (external path) |
| Reporting knowledge layer | `reporting_corpus.py` | Continuously updated | Versioned reporting, atomic attributed claims, source lineage, and primary-evidence review. Secondary claims are not findings. |
| DOJ/SEC releases | `government_release_corpus.py` | DOJ API + SEC 1997-present | Versioned official press releases; primary evidence of agency statements, not automatic proof of allegations. |

**Same EFTA page in multiple corpora = one source re-OCR'd, NOT corroboration.** Cite the corpus you actually read (usually `kabass`).

**EFTA IDs are the canonical reference** for DOJ documents (e.g., `EFTA02336502`). Always cite EFTA IDs when available.

## Derived Data Sidecar (`datasets/epstein_derived.db`)

Normalized, **regenerable** analysis layer built from the corpora. Schema contract + shared helpers: `tools/epstein_derived.py` (single source of truth — do not CREATE TABLE elsewhere). Rebuild the whole thing: `uv run python scripts/build_derived.py --reset`. Principles: **kabass stays immutable; `investigation.db` owns canonical entities and the sidecar references them (never mints its own); corroboration is counted by `independence_group`** — the same released page re-OCR'd across kabass/LMSBAND/DOJ is ONE source, not three.

| Capability | Query tool | Examples |
|---|---|---|
| **Temporal** — "interactions within ±N days of date X" | `tools/query_events.py` | `near --date 2005-08-15 --window 21 [--type transaction,flight,meeting,call,filing] [--actor "Epstein"]`; `window --start --end`; `stats --by-type`. ~32.5K events, each with an EFTA `ref` + participants. |
| **Financial** — normalized ledger | `tools/query_fin.py` | `counterparty "Maxwell"`, `spend --group-by category`, `flows --from --to`, `balances --owner`, `positions`, `flights --passenger`, `near-date`, `review --outliers`. 53.1K txns as signed integer cents (OCR outliers quarantined, same-page dups collapsed). |
| **Entities** — nickname/alias resolution | `tools/person_resolution.py` | `lookup "Jeffrey Epstein"` (gathers the 532-string cluster; keeps Mark/Edward Epstein separate); `stats`; `reconcile --dry-run`. 83.7K canonical persons ← 155.8K raw strings. Candidate crosswalk to core in `entity_crosswalk` (never auto-promoted). |
| **Provenance** | sqlite (`epstein_derived.db`) | `evidence_item` (1.42M pages) / `evidence_representation` / `source_crosswalk` (591K LMSBAND EFTA edges). |

A derived fact becomes a curated finding ONLY via `findings_tracker.py add` (never a direct cross-DB write) — it then gets confidence caps, evidence, and a `finding_entities` link.

## Reporting Sidecar (`datasets/epstein_reporting.db`)

Use `tools/reporting_corpus.py` for historical backfill, current monitoring,
licensed RIS/CSV/JSONL imports, article versioning, claim genealogy, and primary
evidence gaps. Never treat multiple rewrites of one report as corroboration.
Use `recover-archives` for known vanished/paywalled URLs: Wayback and Common
Crawl are retrieval paths for the original outlet, not independent sources.
`promote` enforces a reviewed claim plus quoted primary evidence before creating
a finding. Source inventory: `reporting_sources.yaml`; workflow:
`docs/modules/reporting.md`.

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
| DE corporate registry | Next state for `$add-registry` |

## Reference Files

These files contain detailed investigation context. Read on demand, not every session.

| File | Contents |
|------|----------|
| `investigations/epstein/key-identifiers.md` | Epstein emails, inner circle contacts, addresses, correspondents, EINs |
| `investigations/epstein/wave-results.md` | Detailed wave findings (W1-W12 + K&E) |
| `investigations/epstein/investigation-context.md` | Wave summaries, critical intelligence, registry findings |
| `investigations/epstein/990-findings.md` | IRS 990 grant breakdowns (71 filings, 219 grants, $30.6M) |
