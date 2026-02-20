# Ithildin OSINT Investigation Platform

Agent-scale network investigation rooted in the Epstein case, following evidence across connected structures — Mega Group, Deutsche Bank, Gulf states, Israeli intelligence, Apollo/Black financial flows, and parallel networks. Multiple Claude Code sessions pursue leads in parallel.

**Design doc**: `PRD.md` | **Narrative**: `research/master.md` | **Methodology**: `research/INVESTIGATIVE_METHODOLOGY.md`
**Tool reference**: `docs/TOOL_REFERENCE.md` (complete CLI for all 37+ tools) | **OSINT resources**: `research/OSINT_RESOURCES.md`

## Quick Start

```bash
/dispatch                   # Queue depths — what needs attention
/pursue-lead                # Pick up next lead
/deep-investigate <name>    # 4 parallel sub-agents (preferred)
/triage-leads               # Process pending_triage leads (batch of 20)
/build-infra                # Build next infra request (or scan for gaps)
/search-all-sources <term>  # Fan-out search
/analyze-network            # Graph structure analysis
/generate-hunches           # Emerging theme recognition
/timeline-analysis          # Temporal correlation with external events
/systemic-analysis          # Deep entity patterns beyond Epstein
/investigate-person <name>  # Single-agent deep-dive
/trace-entity <entity>      # Corporate entity trace
/status-report              # Investigation status
/discover-frameworks         # Evolve analytical framework inventory
/review-methodology         # Operational learning review
/ingest-source <source>     # Add new data source
/add-registry               # Add corporate registry
```

Queue system: `scripts/queue_tools.py {status,pause,resume,submit,enqueue-triage,enqueue-lead,agents,metrics}`. Workers: `scripts/agent_worker.py --persona <name>`. See `docs/TOOL_REFERENCE.md` for full persona list and dispatcher commands.

## Investigative Approach

**You are not a search engine.** Use your knowledge of geopolitics, finance, intelligence tradecraft, and human behavior.

1. **Hypothesize first, then search.** What would confirm or refute it?
2. **Simulate the person.** What role do they play? What are their incentives?
3. **Follow the money.** Financial flows reveal truth that words obscure.
4. **Check the timeline.** What else was happening on that date?
5. **Note what's missing.** Communication gaps and absent records are often more significant.
6. **Use multilingual knowledge.** Hebrew, Russian, Arabic, Norwegian sources.
7. **Distinguish fact from inference.** Label them differently.
8. **Follow the network, not the biography.** Worth pursuing if it reveals how systems work.

**Never ship a tool targeting an unverified endpoint.** Probe first, code second.

## Investigation Database

All state in **`investigation.db`** (SQLite, WAL mode). Schema: `leads`, `findings`, `connections`, `entities` + junction tables. Also: `infra_requests`, `human_actions`, `source_reliability`, `corrections`, `search_log`, `name_aliases`.

Lead lifecycle: `open -> in_progress -> completed | blocked | dead_end`
Auto-leads: `pending_triage -> open` (via `/triage-leads`) or `-> dead_end`

### Conventions
- Always use `uv run python` to invoke tools (not bare `python`)
- Always use `--output FILE` for search results. **Session isolation**: `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`, all temp files in `$WORKDIR/`
- Check search_log before querying: `from tools.lead_tracker import check_searched`

### Core CLI (full examples in docs/TOOL_REFERENCE.md)

| Tool | Key Commands |
|------|-------------|
| **Leads** | `lead_tracker.py {add,list,claim,complete,search,evidence,next,stats}` |
| **Findings** | `findings_tracker.py {add,connect,connections,search,timeline}` |
| **Audit** | `findings_tracker.py {unverified,provenance,verify,dispute,retract,correct,audit}` |
| **Infra** | `infra_tracker.py {add,list,show,claim,evaluate,complete,reject,search,next,stats}` |
| **Analysis** | `hypothesis_tracker.py`, `tag_manager.py`, `event_timeline.py`, `graph_tools.py`, `analysis_export.py`, `methodology_tracker.py` |
| **Pillars** | `pillar_tracker.py {register,list,show,seed,arc,career,event,events,bootstrap,alumni,cohort,dispersal,overlap,timeline,score,gaps,cross-pillar,pillar-network,stats}` |

**39+ data source tools** covering document corpora, corporate registries (15 jurisdictions), public records, financial data, and external APIs. Run `uv run python tools/source_report.py` for live status.

**Citation types** for new data sources: add one entry to `CITATION_REGISTRY` in `web/src/lib/citations.ts`. See `docs/CITATION_SYSTEM.md` for the registry pattern and example. For one-off URLs without a structured pattern, add the citation key → URL mapping to `web/src/data/source-urls.json`.

**New international tools:**
- `query_france.py`: French company registry (SIRENE) — `search`, `company <SIREN>`, `naf <CODE>`, `address` — free, no auth
- `query_hudoc.py`: ECHR case database (HUDOC) — `search`, `case <ID>`, `appno <NUM>`, `text <ID>`, `respondent <STATE>` — free, no auth

**CA SoS bizfileonline** (`query_california.py`): Drives bizfileonline.sos.ca.gov Angular UI via CDP to bypass Imperva WAF. Up to 500 results, filing history, PDF links. Requires MCP Playwright Chrome running.
- `search "PARAFI CAPITAL" --status active` | `entity 726332 --history` | `history 726332`
- `ingest 726332` | `ingest-search "Epstein" --limit 50` — ingests to registry.db with filing history
- No auth needed, entity numbers: strip "C" prefix (search tips say "remove C from number")

**NY DOS Public Inquiry** (`query_nydos.py`): Direct REST API to NY Division of Corporations (4.1M+ entities). Complements SODA-based `ingest_newyork.py` with entity detail pages, filing/name history, CEO/agent info. Key for Medicaid provider corporate structure analysis.
- `search "HOME CARE" --status Active` | `entity <DOS_ID> --filings --names` | `filings <DOS_ID>` | `names <DOS_ID>`
- `ingest <DOS_ID>` | `ingest-search "query" --status Active --limit 50` — ingests to registry.db
- Free, no auth, rate-limited to 1 req/sec

**TX Comptroller** (`query_texas.py`): Franchise tax entity search via comptroller.texas.gov data-search proxy. Returns entity name, DBA, EIN, mailing address, officers with addresses, registered agent, SoS file number.
- `search "EPSTEIN"` | `search --taxpayer-id 32044352170` | `search --file-number 0801432227`
- `entity <TAXPAYER_ID>` | `ingest <TAXPAYER_ID>` | `ingest-search "query"` — ingests to registry.db
- Free, no auth, rate-limited to 1 req/sec

**MI LARA Business Registry** (`query_michigan.py`): MI Division of Corporations portal API via Playwright browser helper (Cloudflare WAF). Covers domestic/foreign corps, LLCs, LPs, LLPs, nonprofits.
- `search "EPSTEIN" --contains` | `entity <INTERNAL_ID> <FILING_NUMBER>`
- `ingest <INTERNAL_ID> <FILING_NUMBER>` | `ingest-search "query"` — ingests to registry.db
- Free, no auth. Requires `_mi_browser_helper.js` (Playwright + Chrome). First run may need manual Cloudflare solve.

**NJ Division of Revenue** (`query_newjersey.py`): NJ business entity name search via njportal.com. Returns entity name, ID, city, type, formation date. No detail pages (officers/agents require paid Business Records Service).
- `search "EPSTEIN"` | `entity <ENTITY_ID>` | `keywords "HOME CARE"`
- `ingest <ENTITY_ID>` | `ingest-search "query"` — ingests to registry.db
- Free, no auth. Limited data (name, type, city, formation date only).

**MA Corporations Division** (`query_massachusetts.py`): MA Secretary of the Commonwealth corporate registry via Playwright browser helper (Incapsula WAF). Rich data: entity name/type/status, officers, registered agent, name changes, fiscal date.
- `search "EPSTEIN" --type B` | `entity <ID_NUMBER>` (B=begins, M=exact, F=full text, S=soundex)
- `ingest <ID_NUMBER>` | `ingest-search "query"` — ingests to registry.db
- Free, no auth. Requires `_ma_browser_helper.js` (Playwright + Chrome). First run may need manual Incapsula solve.

**Medicaid Provider Analysis** (T-MSIS 2018-2024, 227M rows, $1.09T):
- `query_medicaid.py`: DuckDB-backed spending analysis — `stats`, `top-billers`, `top-codes`, `provider <NPI>`, `code <HCPCS>`, `network <NPI>`, `anomalies`, `sql`
- `trace_provider.py`: Corporate trace pipeline — NPI → NPPES → state registry → officer network
  - `trace <NPI>` | `batch --top-anomalies N` | `excluded` | `officer-network` | `agent-network` | `pipeline --top-anomalies N`
  - Live NY DOS lookup: auto-ingests entities to registry.db when tracing NY providers
- Data in `data/`: medicaid_spending.parquet (2.9GB), billing/servicing_providers.parquet (NPPES), leie_exclusions.csv (OIG)

## Evidence Standards

### Canonical References
- **Always use EFTA IDs** when available (e.g., EFTA02336502)
- Non-EFTA: use `LMSBAND:12345`, `DOJ11:EFTA02663759`, or file paths
- **3 sources returning the same document is redundancy, not corroboration**

### Source Reliability
**Prioritize primary sources.** Media was involved (NYT/Landon Thomas, Wolff) and may have planted/suppressed stories.

| Tier | Examples | Trust |
|------|----------|-------|
| **Primary** | DOJ EFTA, FBI files, court filings, 990s, KPMG review, actual emails | Highest |
| **Secondary** | Miami Herald, Bloomberg (verify against primary); NYT/Wolff (**extreme caution**) |
| **Tertiary** | Wikipedia, social media | Starting point only — never cite as evidence |

### Audit Sourcing (CRITICAL)

Every finding MUST provide: `--evidence`, `--claim-type`, `--source-quote`

**Claim types and max confidence:**
- `direct_quote` -> can be `confirmed` (if primary source)
- `paraphrase` -> max `high`
- `inference` / `synthesis` -> max `medium`
- `user_provided` -> as specified

**Agents MUST NOT set confidence to `confirmed` for inferences or syntheses.**

## Multi-Instance Workflow

Run **separate CC instances** — NOT one orchestrator spawning all agents:

```
Terminal 1: claude -> /pursue-lead    # Claims next high-priority lead
Terminal 2: claude -> /pursue-lead    # Claims different lead (DB prevents double-claim)
Terminal 3: claude -> /deep-investigate "Target Name"
```

- All instances share `investigation.db` (WAL mode handles concurrent writes)
- Each skill creates unique `WORKDIR` — prevents cross-instance overwrites
- Sub-agents write `$WORKDIR/report-*.md` — parent reads files, NOT TaskOutput
- Post-wave: run `uv run python tools/auto_leads.py run`

## Environment

- **Always use `uv run python`** to invoke tools
- DOJ Vol 11 DB: `/Users/travcole/projects/epstein-docs/output/documents.db`
- Dehashed API: credits limited (468)
- Obsidian vault: `~/Documents/Mines of Moria/epstein research/`
- Key identifiers (emails, addresses, contacts): see `memory/key-identifiers.md`

## Priority Sources (Not Yet Integrated)

| Source | Value |
|--------|-------|
| Giuffre v. Maxwell docket (SDNY 15-cv-7433) | Civil depositions |
| USVI v. JPMorgan exhibits (SDNY 1:22-cv-10904) | Financial evidence |
| DE corporate registry | Next state for `/add-registry` |

## Ethical Guidelines

Open-source intelligence using publicly released government documents, court filings, and public-domain datasets. Do not access non-public systems. Do not contact investigation subjects. Document provenance for all findings.
