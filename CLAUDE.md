# Ithildin OSINT Investigation Platform

General-purpose agent-scale network investigation platform. Investigate any public figure or organization through publicly available data — corporate registries, court filings, financial disclosures, government records, and document corpora. Multiple Claude Code sessions pursue leads in parallel.

**Design doc**: `PRD.md` | **Methodology**: `research/INVESTIGATIVE_METHODOLOGY.md`
**Tool reference**: `docs/TOOL_REFERENCE.md` (complete CLI for all 37+ tools) | **Source modules**: `docs/sources/` (agent instructions per source)
**OSINT resources**: `research/OSINT_RESOURCES.md`

## Config Hierarchy

1. `~/.claude/CLAUDE.md` — Personal preferences (all projects)
2. `CLAUDE.md` (this file) — Platform instructions
3. `investigations/<name>/config.yaml` — Active investigation profile (key_persons, threads, corpus_tools, etc.)
4. `investigations/<name>/CLAUDE-ADDENDUM.md` — Investigation-specific context (if exists)
5. `.claude/skills/<name>/SKILL.md` — On-demand skill files (loaded when invoked)
6. `docs/sources/_preamble.md` — Shared research agent boilerplate (evidence standards, entity registration, report format)
7. `docs/sources/*.md` — Per-source agent instruction modules (protocols, what to look for)
8. `memory/*.md` — Shared topic files (api-notes, infrastructure)
9. `docs/TOOL_REFERENCE.md` — Complete CLI reference for all 37+ tools

## Investigation Profiles

Investigations are configured via YAML profiles at `investigations/<name>/config.yaml`. Each profile defines: `primary_subject`, `key_persons`, `known_addresses`, `threads`, `corpus_tools`, `key_dates`, `seed_pillars`.

```bash
uv run python tools/investigation_context.py show          # Active profile details
uv run python tools/investigation_context.py list          # All available profiles
uv run python tools/investigation_context.py set <name>    # Switch active profile
```

Template for new investigations: `investigations/_template/config.yaml`
Case-specific context: `investigations/<name>/CLAUDE-ADDENDUM.md` (if exists)

All skills load the active profile at startup. Entities are shared across investigations; leads/findings/connections are profile-scoped via `profile_id`.

## Quick Start

```bash
/dispatch                   # Queue depths — what needs attention
/pursue-lead                # Pick up next lead
/deep-investigate <name>    # Adaptive multi-wave investigation (preferred)
/triage-leads               # Process pending_triage leads (batch of 20)
/build-infra                # Build next infra request (or scan for gaps)
/search-all-sources <term>  # Fan-out search
/analyze-network            # Graph structure analysis
/generate-hunches           # Emerging theme recognition
/timeline-analysis          # Temporal correlation with external events
/systemic-analysis          # Deep entity patterns beyond the primary subject
/investigate-person <name>  # Single-agent deep-dive
/trace-entity <entity>      # Corporate entity trace
/investigate-infra <target> # Passive digital infrastructure recon
/status-report              # Investigation status
/discover-frameworks        # Evolve analytical framework inventory
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
6. **Use multilingual knowledge.** Sources in relevant languages for the investigation.
7. **Distinguish fact from inference.** Label them differently.
8. **Follow the network, not the biography.** Worth pursuing if it reveals how systems work.
9. **Document aggressively.** Store everything found — officer names, addresses, corporate relationships, financial figures — even if not obviously relevant to the current hypothesis. It may surface connections later.

**Never ship a tool targeting an unverified endpoint.** Probe first, code second.

## Investigation Database

All state in **`investigation.db`** (SQLite, WAL mode). Schema: `leads`, `findings`, `connections`, `entities` + junction tables. Also: `infra_requests`, `human_actions`, `source_reliability`, `corrections`, `search_log`, `name_aliases`.

Lead lifecycle: `open -> in_progress -> completed | blocked | dead_end`
Auto-leads: `pending_triage -> open` (via `/triage-leads`) or `-> dead_end`

### Conventions
- Always use `uv run python` to invoke tools (not bare `python`)
- Always use `--output FILE` for search results. **Session isolation**: `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`, all temp files in `$WORKDIR/`
- Check search_log before querying: `from tools.lead_tracker import check_searched`

### Entity Registration (CRITICAL)
**Every organization and person discovered MUST be registered** in the entity system. This is what enables cross-investigation network discovery — without it, `auto_leads.py` generates nothing and graph analysis misses nodes.

```bash
# 1. Check if entity exists first
uv run python tools/entity_tracker.py lookup --name "ENTITY_NAME"
# 2. Register new organizations (entity types: llc, inc, ltd, trust, foundation, nonprofit, partnership, fund, association, government, unknown)
uv run python tools/entity_tracker.py add-entity --name "ENTITY" --entity-type inc --jurisdiction "STATE" --source "SOURCE" --notes "CONTEXT"
# 3. Assign person roles (returns entity_id from step 2)
uv run python tools/entity_tracker.py add-role --entity-id ID --person-name "PERSON" --role "CEO" --source "SOURCE"
# 4. Link entities to each other (relation types: owns, controls, funds, shares_officer, subsidiary_of, successor_to)
uv run python tools/entity_tracker.py add-relation --entity-a-id ID --entity-b-id ID --relation-type "funds" --description "DESC"
```

Do this AS YOU FIND entities, not as a cleanup step. If a finding mentions an organization, register it immediately.

### Core CLI (full examples in docs/TOOL_REFERENCE.md)

| Tool | Key Commands |
|------|-------------|
| **Leads** | `lead_tracker.py {add,list,claim,complete,search,evidence,next,stats}` |
| **Findings** | `findings_tracker.py {add,connect,connections,search,timeline}` |
| **Entities** | `entity_tracker.py {lookup,show,add-entity,add-role,add-address,add-relation}` |
| **Audit** | `findings_tracker.py {unverified,provenance,verify,dispute,retract,correct,audit}` |
| **Infra** | `infra_tracker.py {add,list,show,claim,evaluate,complete,reject,search,next,stats}` |
| **Analysis** | `hypothesis_tracker.py`, `tag_manager.py`, `event_timeline.py`, `graph_tools.py`, `analysis_export.py`, `methodology_tracker.py` |
| **Pillars** | `pillar_tracker.py {register,list,show,seed,arc,career,event,events,bootstrap,alumni,cohort,dispersal,overlap,timeline,score,gaps,cross-pillar,pillar-network,stats}` |
| **Recon** | `recon_probe.py probe "TARGET" [--type person|entity]` — fast parallel count-only queries across all sources, returns heat map |
| **Profile** | `investigation_context.py {show,list,set}` |

Pillar system (`pillar_tracker.py`) tracks institutional pillars, career arcs, and alumni dynamics. Orchestrator scores measure documentation completeness (not true importance) — gaps are often the most interesting output.

**39+ data source tools** covering document corpora, corporate registries (15 jurisdictions), public records, financial data, and external APIs. Run `uv run python tools/source_report.py` for live status.

**Citation types** for new data sources: add one entry to `CITATION_REGISTRY` in `web/src/lib/citations.ts`. See `docs/CITATION_SYSTEM.md` for the registry pattern and example. For one-off URLs without a structured pattern, add the citation key → URL mapping to `web/src/data/source-urls.json`.

**Government spending & contracts:**
- `query_usaspending.py`: Federal spending — `search`, `awards`, `award`, `recipient`, `subawards`, `transactions`, `geography`, `timeline`, `top-recipients`, `agencies` — free, no auth
- `query_sam.py`: SAM.gov API — `entity`, `exclusions`, `contracts`, `opportunities` — free API key (SAM_API_KEY)
- `ingest_sam.py`: SAM.gov Bulk (874K entities, 167K exclusions) — `search`, `entity`, `exclusion`, `entity-by-uei`, `entity-by-cage`, `naics`, `address`, `stats` — local SQLite, no auth
- `query_medicare.py`: Medicare provider spending — `search`, `provider` — free, no auth

**International tools:**
- `query_france.py`: French company registry (SIRENE) — `search`, `company <SIREN>`, `naf <CODE>`, `address` — free, no auth
- `query_hudoc.py`: ECHR case database (HUDOC) — `search`, `case <ID>`, `appno <NUM>`, `text <ID>`, `respondent <STATE>` — free, no auth

**Infrastructure recon tools:**
- `query_crtsh.py`: Certificate Transparency via crt.sh — `search`, `subdomains`, `timeline`, `cert` — free, no auth
- `query_wayback.py`: Wayback Machine CDX — `snapshots`, `timeline`, `first`, `diff`, `fetch` — free, no auth
- `query_urlscan.py`: URLScan.io passive scans — `search`, `result`, `technologies`, `links` — free (search), API key for submit

**Corporate registries** (15 jurisdictions): FL, NY, CA, TX, MI, MA, NJ, NM, CO, DC, USVI, Panama, UK, France, OpenCorporates (DE/HK/CY). See `docs/TOOL_REFERENCE.md` for per-registry CLI. Common patterns:
- `search "QUERY"` | `entity <ID>` | `ingest <ID>` | `ingest-search "QUERY"`
- Unified query: `query_registry.py search "QUERY"` | `officers "NAME"` | `address "ADDR"`

**HigherGov** (`query_highergov.py`): Federal contract, grant, awardee, IDV, subcontract, vehicle, and partnership intelligence. Richer than USASpending with nested relationships, named vehicle tracking, and teaming data.
- `contract --parent-award N0002325D0075` | `contract --awardee-uei ZE2JVFS8ML75` | `contract --vehicle-key 8751 --all-pages`
- `idv --vehicle-key 8751 --all-pages` | `idv --naics 561611` | `idv --award-id N0002325D0075`
- `awardee --uei ZE2JVFS8ML75` | `awardee --cage 9MFB2` | `subcontract --awardee-uei ZE2JVFS8ML75`
- `partnership --awardee-key 509623647` | `vehicle --vehicle-key 8751` | `agency --agency-key 904`
- `opportunity --source-id "26-SOL-DCR01"` | `grant --awardee-uei ZE2JVFS8ML75` | `people --email "name@dhs.gov"`
- Key vehicle IDs: WEXMAC 2.0 = 8751. 2-week trial. Auth: HIGHERGOV_API_KEY in .env. Rate: 10 req/sec, 10K records/month.

**Shodan** (`query_shodan.py`): Internet-connected device search, DNS enumeration, SSL cert discovery. Paid plan (99 query credits). Auth: SHODAN_API_KEY in .env.

**Medicaid Provider Analysis** (T-MSIS 2018-2024, 227M rows, $1.09T):
- `query_medicaid.py`: DuckDB-backed spending analysis — `stats`, `top-billers`, `top-codes`, `provider <NPI>`, `code <HCPCS>`, `network <NPI>`, `anomalies`, `sql`
- `trace_provider.py`: Corporate trace pipeline — NPI → NPPES → state registry → officer network

## Evidence Standards

### Canonical References
- Use the canonical document ID system from the active investigation's corpus tools
- For EFTA-based corpora: `EFTA02336502`. For others: `SOURCE:ID` format (e.g., `LMSBAND:12345`)
- **3 sources returning the same document is redundancy, not corroboration**

### Source Reliability
**Prioritize primary sources.** Media may have planted or suppressed stories — always verify against primary evidence.

| Tier | Examples | Trust |
|------|----------|-------|
| **Primary** | Government records, court filings, corporate registries, 990s, regulatory filings, auditor reports, actual emails | Highest |
| **Secondary** | Investigative journalism (verify against primary); opinion media (**extreme caution**) |
| **Tertiary** | Wikipedia, social media | Starting point only — never cite as evidence |

For investigation-specific source reliability overrides, see `investigations/<active_profile>/CLAUDE-ADDENDUM.md`.

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
- Never call TaskOutput on completed agents — transcript is 10-50MB, report is 2KB
- Agents aim < 50 tool calls per session
- Post-wave: run `uv run python tools/auto_leads.py run`

## Environment

- **Always use `uv run python`** to invoke tools
- Dehashed API: credits limited (468)
- OpenCorporates API: basic tier (500 calls/month, 200/day max)
- Key identifiers (emails, addresses, contacts): see `investigations/<active_profile>/key-identifiers.md`

## Ethical Guidelines

Open-source intelligence using publicly released government documents, court filings, and public-domain datasets. Do not access non-public systems. Do not contact investigation subjects. Document provenance for all findings.
