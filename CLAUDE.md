# Epstein Network OSINT Investigation Platform

Agent-scale network investigation rooted in the Epstein case but following evidence across connected structures — Mega Group, Deutsche Bank pipeline, Gulf state operations, Israeli intelligence nexus, Apollo/Black financial flows, and parallel networks. Multiple Claude Code sessions pursue leads in parallel, track findings, and build on each other's work.

**Design doc**: `PRD.md`
**Master narrative**: `research/master.md`
**Investigative methodology**: `research/INVESTIGATIVE_METHODOLOGY.md` — **read this before investigating**
**Tool reference**: `docs/TOOL_REFERENCE.md` — complete CLI examples for all 35+ tools
**Related investigations**: `research/RELATED_INVESTIGATIONS.md`
**OSINT resources**: `research/OSINT_RESOURCES.md`

## Quick Start

```bash
/dispatch                   # Queue depths — what needs attention
/pursue-lead                # Pick up next lead
/deep-investigate <name>    # 4 parallel sub-agents (preferred)
/triage-leads               # Process pending_triage leads (batch of 20)
/build-infra                # Build next infra request (or scan for gaps)
/search-all-sources <term>  # Fan-out search
/analyze-network            # Graph structure analysis — centrality, bridges, gaps
/generate-hunches           # Emerging theme recognition across findings
/timeline-analysis          # Temporal correlation with external events
/systemic-analysis          # Deep entity patterns beyond Epstein
/investigate-person <name>  # Single-agent deep-dive
/trace-entity <entity>      # Corporate entity trace
/status-report              # Investigation status
/ingest-source <source>     # Add new data source
/add-registry               # Add corporate registry

# Automated dispatcher (headless Claude Code)
uv run python scripts/dispatcher.py run       # One-shot: launch needed agents
uv run python scripts/dispatcher.py status    # Show running/recent agents
uv run python scripts/dispatcher.py daemon    # Poll loop (Ctrl-C to stop)
uv run python scripts/dispatcher.py stop      # Kill running agents
```

## Queue System (SQLite-first)

```bash
uv run python scripts/queue_tools.py status
uv run python scripts/queue_tools.py pause --by "human"
uv run python scripts/queue_tools.py resume --by "human"
uv run python scripts/queue_tools.py submit --type echo --domain system --payload '{"message":"hello"}'
uv run python scripts/agent_worker.py --persona echo
```

## Investigative Approach

**You are not a search engine.** Use your knowledge of geopolitics, finance, intelligence tradecraft, and human behavior.

1. **Hypothesize first, then search.** What would confirm or refute it?
2. **Simulate the person.** What role does this person play in the network? What are their incentives?
3. **Follow the money.** Financial flows reveal truth that words obscure.
4. **Check the timeline.** What else was happening on that date?
5. **Note what's missing.** Communication gaps and absent records are often more significant.
6. **Use multilingual knowledge.** Hebrew, Russian, Arabic, Norwegian sources.
7. **Distinguish fact from inference.** Label them differently.
8. **Follow the network, not the biography.** A lead is worth pursuing if it reveals how these systems work, even if Epstein isn't directly involved.

### API & Data Source Verification Rule
**Never ship a tool targeting an unverified endpoint.** Probe first, code second. If discovery fails, create a `human_action` item.

## Investigation Database

All state lives in **`investigation.db`** (SQLite, WAL mode). Schema: `leads`, `findings`, `connections`, `entities` + junction tables (`lead_notes`, `lead_evidence`, `finding_evidence`, `connection_evidence`, `entity_roles`, `entity_addresses`, `entity_relations`). Also: `infra_requests`, `infra_notes`, `human_actions`, `source_reliability`, `corrections`, `search_log`, `name_aliases`.

Lead lifecycle: `open → in_progress → completed | blocked | dead_end`
Auto-leads: `pending_triage → open` (via `/triage-leads`) or `→ dead_end` (duplicate)

### Python Convention
Always use `uv run` to invoke tools:
```bash
uv run python tools/query_doj.py search "bannon" -n 50 --output /tmp/doj-bannon.json
```

### Output Flag Convention
Always use `--output FILE` to keep context lean. **Session isolation**: every skill invocation creates a unique working directory via `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)` and uses `$WORKDIR/` for all `--output` paths. This prevents parallel agents from overwriting each other's temp files.

### Core CLI (full examples in docs/TOOL_REFERENCE.md)

| Tool | Key Commands |
|------|-------------|
| **Leads** | `lead_tracker.py {add,list,claim,complete,search,evidence,next,stats}` |
| **Findings** | `findings_tracker.py {add,connect,connections,search,timeline}` |
| **Audit** | `findings_tracker.py {unverified,provenance,verify,dispute,retract,correct,audit}` |
| **Infra** | `infra_tracker.py {add,list,show,claim,evaluate,complete,reject,search,next,stats,block-lead}` |
| **Source report** | `source_report.py` — live status of all data sources |
| **Auto-leads** | `auto_leads.py run` — creates `pending_triage` leads for `/triage-leads` |
| **Entity dedup** | `entity_dedup.py {add-alias,list-aliases,remove-alias,scan,apply,seed,merge,stats}` — name alias management |
| **Hypotheses** | `hypothesis_tracker.py {add,list,show,investigate,confirm,refute,supersede,evidence,search,stats}` |
| **Tags** | `tag_manager.py {tag,bulk-tag,find,list-values,record,remove,stats}` |
| **Event timeline** | `event_timeline.py {seed,add,window,near,list,stats}` |
| **Graph tools** | `graph_tools.py {centrality,components,bridges,paths,neighbors,holes,cliques,stats}` |
| **Analysis export** | `analysis_export.py {connections-graph,findings-dump,timeline-export,entity-network,coverage-matrix,thread-summary,analysis-state}` |

### Data Sources (37+ tools)

**Document corpus:** DugganUSA (204K), DOJ Vol 11 (331K), LMSBAND (60K/851K entities), Unified DB (70K), Epstein 20K (25.8K), Investigations DB (PDFs)

**Registries:** Corporate registry (CO/CY/DC/DE/FL/HK/MD/NY/NM/PA/VI/UK/CA/IL/CH), UCC filings (FL/NM), ICIJ (800K offshore), GLEIF LEI, UK Companies House, Israeli Corporations Authority (720K), Swiss Zefix (30K+ via SPARQL)

**Public records:** SEC EDGAR, CourtListener, ProPublica 990, IRS 990 XML (Schedule I/R grants+related), IRS 990 Bulk (all US nonprofit grants 2009-2024, ~6.9M filings), NYC ACRIS, FEC, Federal Lobbying (LDA), FARA, LittleSis, OCCRP Aleph

**External APIs:** GDELT (news), OpenSanctions (4.13M), EpsteinExposed (1.3K persons), MuckRock FOIA, DocumentCloud

**Financial:** DS10 (Deutsche Bank, 579 tx/$304M), FAA Registry (aircraft), FinCEN Files (4.5K tx/5.5K connections, 2000-2017 SARs), SWIFT BIC Directory (32K+ banks, BIC→LEI mappings)

**Raw data:** DDoSecrets EML (13K), Barak emails (1.4K), HF Parquet (4.3K emails), FBI Files Parquet (8.2K)

Run `uv run python tools/source_report.py` for live status. See `docs/TOOL_REFERENCE.md` for all CLI examples.

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
- `direct_quote` → can be `confirmed` (if primary source)
- `paraphrase` → max `high`
- `inference` → max `medium`
- `synthesis` → max `medium`
- `user_provided` → as specified

**Agents MUST NOT set confidence to `confirmed` for inferences or syntheses.**

Verification: findings start `unverified` → human reviews → `verify`, `dispute`, or `retract` (cascades to connections). All corrections tracked immutably in `corrections` table.

### Before Querying
Check search_log: `from tools.lead_tracker import check_searched`

## Multi-Instance Workflow (Waves)

Run **separate CC instances** for parallel wave execution instead of one orchestrator spawning all agents:

```
Terminal 1: claude → /pursue-lead    # Claims next high-priority lead
Terminal 2: claude → /pursue-lead    # Claims a different lead (DB prevents double-claim)
Terminal 3: claude → /deep-investigate "Target Name"
```

Why: A single session hitting 200MB+ crashes from agent transcript bloat. Separate instances each stay at 5-20MB.

Rules:
- All instances write to shared `investigation.db` (WAL mode handles concurrent writes)
- Each instance has its own context window — no compounding
- Post-wave: run `uv run python tools/auto_leads.py run` from any instance
- Each skill creates a unique `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)` — all temp files go there, preventing cross-instance overwrites
- Sub-agents within a session write reports to `$WORKDIR/report-*.md` — parent reads files, NOT TaskOutput
- Use `--output $WORKDIR/...` on ALL search commands in every context

## Environment

- **Always use `uv run python` to invoke tools** (not bare `python` or `.venv/bin/python3`)
- DOJ Vol 11 DB: `/Users/travcole/projects/epstein-docs/output/documents.db`
- Dehashed API: credits limited (468)
- Obsidian vault: `~/Documents/Mines of Moria/epstein research/`

## Key Identifiers

### Epstein Emails
jeevacation@gmail.com (primary inbox), jeeproject@yahoo.com (primary outgoing), jeffreyepsteinorg@gmail.com, jeffrey.epstein@centurytel.net, lsje_llc@outlook.com, zorroranch@aol.com, epstein@wanadoo.fr + 12 others

### Inner Circle
- Darren Indyke: dkiesq@aol.com, (212) 971-1314
- Richard Kahn: richardkahn12@gmail.com
- Lesley Groff: lesley.jee@gmail.com, lgroff@dkipllc.com
- Christina Galbraith: galbraith_christina@yahoo.com
- Karyna Shuliak: kari.shulia@gmail.com

### Key Addresses
9 E 71st St NYC, 358 El Brillo Way Palm Beach, 49 Zorro Ranch Rd Stanley NM, 6100 Red Hook Rd St Thomas USVI

### Top Correspondents
Wolff 303, Weingarten 245, Ruemmler 201, Summers 200, Thomas Jr 185, Bannon 160/526, Alrasheed 70, Lisa New 72, Chomsky 38, Schoen 34, Barak 28/444, Karp 17

## Priority Sources (Not Yet Integrated)

| Source | Value |
|--------|-------|
| Giuffre v. Maxwell docket (SDNY 15-cv-7433) | Civil depositions |
| USVI v. JPMorgan exhibits (SDNY 1:22-cv-10904) | Financial evidence |
| DE corporate registry | Next state to add via `/add-registry` (CA now integrated) |
| CBP/FBI Vault PDFs | Download + ingest |
| FinCEN Files | 200K+ transactions, Deutsche Bank SARs |

## Ethical Guidelines

Open-source intelligence using publicly released government documents, court filings, and public-domain datasets. Do not access non-public systems. Do not contact investigation subjects. Document provenance for all findings.
