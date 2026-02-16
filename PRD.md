# PRD: Epstein OSINT Agent-Scale Investigation Platform

## Problem

The Epstein OSINT investigation has grown from a single-researcher markdown project into a multi-database operation spanning ~10GB across two projects (osint-research + offshore-leaks). The investigation has uncovered significant intelligence (Weingarten/Trump counsel nexus, Wolff PR operation, Landon Thomas/SoftBank quid pro quo, Rod-Larsen $18M financial flows, Churkin scheduling, Deripaska/Lilia recruitment), but the current workflow cannot scale:

- **Single markdown file** (2,400 lines) tracks all findings, leads, and methodology — difficult for agents to parse
- **~120 outstanding action items** buried in prose sections — no structured claiming/handoff
- **No deduplication** across sources — the same document appears in DugganUSA, LMSBAND, unified DB, and DOJ Vol 11 without cross-referencing
- **Two separate projects** (osint-research + offshore-leaks) with complementary data but no integration
- **No search logging** — agents repeat identical queries across sessions

The public data ecosystem is similarly fragmented. Nobody has published a clean, deduplicated dataset covering all source tranches, though EpsteinExposed.com has done significant entity resolution work (1,404 persons, 143K docs, 1,708 flights).

## Solution

Transform the investigation into an agent-scalable platform where multiple Claude Code sessions can pursue leads in parallel, track findings systematically, and build on each other's work — operating at a scale impossible for a human researcher. The investigation follows evidence wherever it leads, not just Epstein-centric threads: connected networks (Mega Group, Deutsche Bank pipeline, Gulf state operations, Israeli intelligence nexus) are investigated on their own terms through dedicated investigation threads.

### Core Architecture

**Single `investigation.db`** (SQLite) contains:
- **leads**: Investigation work items with priority, status, category
- **findings**: Confirmed intelligence with evidence chains and confidence levels
- **connections**: Relationship graph between persons/entities
- **sessions**: Audit trail for agent activity
- **search_log**: Prevents redundant queries across sessions
- **job_queue**: Queue-backed work items for autonomous agents
- **job_events**: Audit trail for queue state changes
- **job_dependencies**: Parent/child and blocking relationships
- **agent_instances**: Worker registry + health
- **system_state**: `/halt` and pause controls
- **Junction tables**: `lead_evidence`, `finding_evidence`, `connection_evidence`, `lead_relations` — proper indexed evidence references instead of JSON columns

**Tool wrappers** (`tools/`) provide consistent CLI interfaces for every data source:
- `lead_tracker.py` — Lead CRUD, claiming, completion, search log
- `findings_tracker.py` — Findings CRUD, connections graph, timeline
- `duggan_search.py` — DugganUSA API (204K+ docs)
- `query_doj.py` — DOJ Vol 11 FTS5 (331K OCR'd pages)
- `query_lmsband.py` — LMSBAND (60K files, 851K entities)
- `query_unified.py` — Unified DB (70K docs, 56K entities, 107K triples)
- `query_icij.py` — ICIJ Neo4j (800K offshore entities)
- `source_report.py` — Data source coverage dashboard

**Investigation skills** (slash commands) encode investigative methodology:
- `/pursue-lead` — Claim and investigate the next highest-priority lead
- `/search-all-sources` — Fan-out search across all datasets
- `/investigate-person` — Comprehensive person investigation
- `/trace-entity` — Corporate/financial entity tracing
- `/status-report` — Investigation dashboard
- `/ingest-source` — Onboard new data sources

### Operational Model

**Full agent autonomy.** Agents claim leads, investigate, record findings, and spawn follow-ups without human approval. Agents freely set priority levels. Human reviews via `/status-report` and adjusts as needed.

**Parallel sessions.** The SQLite WAL mode + structured lead claiming enables multiple investigation sessions to operate concurrently without conflicts.

**SQLite-first execution.** Queue tables live in SQLite during early phases; PostgreSQL cutover happens after the queue/worker pipeline is stable.

**Master narrative preserved.** The existing `epstein-email-osint.md` stays as-is in `research/master.md`. The structured databases are a parallel coordination system, not a replacement. The master narrative is for human consumption; the databases are for agent coordination. They will drift apart and that's fine.

## Data Sources

### Local (Available Now)

| Source | Records | Tool | DB Size |
|--------|---------|------|---------|
| DugganUSA API | 204K+ docs | duggan_search.py | Remote |
| DOJ Vol 11 | 331K pages | query_doj.py | 974 MB |
| LMSBAND | 60K files + 851K entities | query_lmsband.py | 834 MB |
| Unified DB | 70K docs + 56K entities | query_unified.py | 505 MB |
| ICIJ Offshore Leaks | ~800K entities | query_icij.py | Neo4j |
| HF Emails Parquet | 4,272 emails | pandas | 1 MB |
| FBI Files Parquet | 8,150 docs | pandas | 111 MB |
| DDoSecrets EML | 13K+ emails | search_emails.py | 1.6 GB |
| Barak Emails | 1,411 files | search_emails.py | 16 MB |
| Doc-Explorer | 25K docs, 107K triples | sqlite3 | 266 MB |

### Priority Additions

| Priority | Source | Value | Integration |
|----------|--------|-------|-------------|
| **High** | EpsteinExposed.com data (1,404 persons, 143K docs, 1,708 flights) | Pre-built entity resolution + cross-referencing | query_exposed.py |
| **High** | tensonaut/EPSTEIN_FILES_20K (25K OCR'd texts) | Clean RAG-ready text | Ingest to unified DB |
| **High** | Giuffre v. Maxwell docket (SDNY 15-cv-7433) | Civil depositions, distinct from DOJ corpus | query_civil_docket.py |
| **High** | USVI v. JPMorgan exhibits (SDNY 1:22-cv-10904) | Financial evidence from bank litigation | query_jpmorgan.py / civil docket tool |
| **Medium** | CourtListener API | Federal dockets, RECAP archive | courtlistener.py (scaffolded) |
| **Medium** | OpenCorporates | 204M companies globally | opencorporates.py |
| **Medium** | FinCEN Files transactions (ICIJ) | 200K+ transactions, Deutsche Bank SARs | Ingest to Neo4j |
| **Medium** | theelderemo/FULL_EPSTEIN_INDEX (living archive) | Already partially ingested; verify completeness | Update unified DB |
| **Low** | OpenSanctions | PEP/sanctions cross-reference | opensanctions/ (scaffolded) |
| **Low** | SEC EDGAR | Modern corporate filings | edgar/ (scaffolded) |
| **Track** | Bloomberg 18K emails (Sep 2025) | Not yet available as dataset | Monitor |

### Notable Gaps in Public Ecosystem
- No public structured flight passenger data post-2006 (EpsteinExposed has 1,708 flights but only 373 with passengers)
- 2013-2019 gap: 835 documented flights, zero passenger manifests
- Island visitor logbook: referenced in USVI filings, never released
- 40 seized computers, 70+ CDs, computerized database: FBI holds, not in EFTA
- Grand jury materials: unsealing denied Aug 2025, upheld Dec 2025

## Deduplication Strategy

Documents appear across multiple sources without cross-referencing. Key approach:

1. **EFTA IDs as canonical references.** When a document has an EFTA ID, always use it as the primary reference.
2. **Check before creating.** Agents must check existing findings before creating new ones — same document in 3 sources is redundancy, not corroboration.
3. **Source attribution.** Every finding records which datasets confirmed it (`source_datasets` field).
4. **Junction table queries.** `finding_evidence` table enables "give me everything connected to EFTA02336502" across all findings and leads.
5. **Future: Document ID normalization table.** Map DugganUSA IDs ↔ EFTA IDs ↔ LMSBAND file IDs for true cross-source dedup.

## Schema Overview

```sql
-- investigation.db (single database, all tables)

leads (id, title, description, category, priority, status, source, target_name, findings, ...)
lead_notes (id, lead_id, note, session_id, ...)
lead_evidence (lead_id, evidence_type, evidence_ref)  -- junction
lead_relations (lead_id, related_lead_id, relation_type)  -- junction

findings (id, target_name, finding_type, summary, detail, source_datasets, confidence, date_of_event, lead_id, ...)
finding_evidence (finding_id, evidence_type, evidence_ref)  -- junction

connections (id, person_a, person_b, relationship_type, description, strength, date_range, finding_id, ...)
connection_evidence (connection_id, evidence_type, evidence_ref)  -- junction

sessions (id, agent_id, skill_invoked, started_at, ended_at, summary)
search_log (id, query_text, source, result_count, session_id, searched_at, UNIQUE(query_text, source))

-- FTS5 virtual tables
leads_fts (title, description, findings, target_name)
findings_fts (target_name, summary, detail)
```

## Implementation Phases

### Phase A: Foundation (Done)
- [x] Create `tools/` directory structure
- [x] Build `investigation.db` schema with junction tables, FTS5, search_log, sessions
- [x] Build `lead_tracker.py` CLI (add/list/claim/note/complete/search/evidence/stats)
- [x] Build `findings_tracker.py` CLI (add/list/connect/connections/search/timeline/stats)
- [x] Copy existing tools (duggan_search.py, search_emails.py) to tools/

### Phase B: Merge offshore-leaks (Done)
- [x] Copy Neo4j infrastructure, start scripts
- [x] Copy sec_scraper modules (entity_resolver, courtlistener, opensanctions)
- [x] Copy research/investigations (ICIJ crossref, JPM analysis)
- [x] Build `query_icij.py` Neo4j wrapper

### Phase C: Tool wrappers (Done)
- [x] Build `query_doj.py` — DOJ Vol 11 FTS5
- [x] Build `query_lmsband.py` — LMSBAND text/entity/cooccurrence
- [x] Build `query_unified.py` — Unified DB emails/docs/entities/triples
- [x] Build `source_report.py` — Data source coverage dashboard

### Phase D: Skills (Done)
- [x] `/pursue-lead` — Autonomous lead investigation loop
- [x] `/search-all-sources` — Fan-out search
- [x] `/investigate-person` — Person investigation template
- [x] `/trace-entity` — Corporate/financial entity tracing
- [x] `/status-report` — Investigation dashboard
- [x] `/ingest-source` — New data source onboarding

### Phase E: Migration & Seeding (Next)
- [ ] Parse Outstanding Actions from epstein-email-osint.md → leads in investigation.db
- [ ] Migrate confirmed findings → findings in investigation.db
- [ ] Seed high-priority leads from DOJ Vol 11 deep mining results
- [ ] Move epstein-email-osint.md → research/master.md
- [ ] Create research/persons/ skeleton for major correspondents

### Phase F: CLAUDE.md Rewrite (Next)
- [ ] Rewrite as agent instruction manual
- [ ] Data source inventory with query commands
- [ ] Lead workflow documentation
- [ ] Evidence standards (EFTA citation format)
- [ ] Skill usage guide

### Phase G: Additional Data Sources (Incremental)
- [ ] EpsteinExposed.com data ingestion
- [ ] tensonaut/EPSTEIN_FILES_20K import
- [ ] Giuffre v. Maxwell docket tool
- [ ] USVI v. JPMorgan exhibits tool
- [ ] CourtListener API client
- [ ] OpenCorporates API client
- [ ] Document ID normalization table

## Success Metrics

After Phase F, the following should all work:
- `python tools/lead_tracker.py list --status open --priority high` returns seeded leads
- `python tools/lead_tracker.py search "rod-larsen"` finds relevant leads
- `python tools/duggan_search.py "churkin ambassador"` returns 300+ DOJ results
- `python tools/query_doj.py search "samantha stein"` returns DOJ Vol 11 results
- `python tools/query_lmsband.py entities "Rod-Larsen"` returns entity matches
- `/pursue-lead` — agent claims an open lead, investigates across sources, records findings, creates follow-ups
- `/search-all-sources churkin` returns deduplicated results from 5+ sources
- `/status-report` shows open leads by priority, recent findings, source coverage

## What This Enables

With this infrastructure, a Claude Code session can:
1. Run `/status-report` to see investigation state
2. Pick a high-priority lead via `/pursue-lead`
3. Autonomously search all local sources, record findings, spawn follow-ups
4. Next session starts from step 1, picks up next lead

At scale: dozens of leads investigated per session, cross-referenced across 800K+ offshore entities, 204K+ DOJ documents, 331K DOJ Vol 11 pages, 60K LMSBAND files, 14K emails, and 56K unified entities.
