# Ithildin OSINT Investigation Platform

General-purpose agent-scale network investigation platform. Investigate any public figure or organization through publicly available data — corporate registries, court filings, financial disclosures, government records, and document corpora. Multiple Codex tasks and subagents can pursue leads in parallel.

**Design doc**: `PRD.md` | **Methodology**: `research/INVESTIGATIVE_METHODOLOGY.md`
**Tool reference**: `docs/TOOL_REFERENCE.md` (complete CLI for all 37+ tools) | **OSINT resources**: `research/OSINT_RESOURCES.md`

## Investigation Profiles

Investigations are configured via YAML profiles at `investigations/<name>/config.yaml`. Each profile defines: `primary_subject`, `key_persons`, `known_addresses`, `threads`, `corpus_tools`, `key_dates`, `seed_pillars`.

```bash
uv run python tools/investigation_context.py show          # Active profile details
uv run python tools/investigation_context.py list          # All available profiles
uv run python tools/investigation_context.py set <name>    # Switch active profile
```

Template for new investigations: `investigations/_template/config.yaml`
Case-specific context: `investigations/<name>/AGENTS.md` (if exists)

All skills load the active profile at startup. Entities are shared across investigations; leads/findings/connections are profile-scoped via `profile_id`.

## Quick Start

```bash
$dispatch                   # Queue depths — what needs attention
$pursue-lead                # Pick up next lead
$deep-investigate <name>    # Parallel sub-agents (preferred)
$triage-leads               # Process pending_triage leads (batch of 20)
$build-infra                # Build next infra request (or scan for gaps)
$search-all-sources <term>  # Fan-out search
$analyze-network            # Graph structure analysis
$generate-hunches           # Emerging theme recognition
$timeline-analysis          # Temporal correlation with external events
$systemic-analysis          # Deep entity patterns beyond the primary subject
$investigate-person <name>  # Single-agent deep-dive
$trace-entity <entity>      # Corporate entity trace
$investigate-infra <target> # Passive digital infrastructure recon
$analyze-filing <CIK>      # Deep SEC filing analysis (10-K, proxy, 13D)
$analyze-contract <award>   # Government contract forensics (subawards, payments, vehicles)
$analyze-case <docket>      # Court case deep analysis (opinions, parties, allegations)
$screen-targets <tickers>   # Financial red flag screening (Tier 0, 5-20 companies)
$compare-peers <company>    # Industry peer benchmarking (Tier 2, outlier detection)
$trace-grants <org>         # Dark money grant flow network tracing (Tier 2)
$audit-contracts <companies> # Comparative procurement analysis (Tier 2)
$status-report              # Investigation status
$discover-frameworks        # Evolve analytical framework inventory
$review-methodology         # Operational learning review
$fix-papercuts              # Resolve accumulated repository friction
$ingest-source <source>     # Add new data source
$add-registry               # Add corporate registry
```

## Log and Fix Papercuts

When a small repository friction occurs, do not silently work around it. Examples include a misleading error, a dead command, stale documentation, a missing validation check, a tool invocation that predictably needs a retry, or an undocumented shell/configuration trap.

Log it immediately while the reproduction context is fresh:

```bash
uv run python tools/papercut.py "Short description of what got in the way" \
  --command "the command or tool call, if useful" \
  --expected "what should have happened" \
  --context "minimal reproduction detail" \
  --skill <current-skill>
```

Papercuts are stored as `friction` observations in `investigation.db`; they are not a separate issue system. Logging is required even when the current task can continue.

If the root cause is clear, the fix is small, safe, testable, and within the current task's scope, fix it directly and then close the item:

```bash
uv run python tools/papercut.py --resolve <ID> --resolution "What changed and how it was verified"
```

Otherwise leave it open for a focused cleanup pass (`uv run python tools/papercut.py --list`). Do not include secrets, tokens, or sensitive local data in the entry. Do not hide the problem with silent exception handling, unbounded retries, duplicated implementations, hard-coded special cases, or documentation of an avoidable workaround. Larger fixes still belong in `infra_requests`; a papercut may be promoted there during methodology review.

When asked to "fix the papercuts," invoke `$fix-papercuts` and process the open list as follows:

1. Reproduce or inspect each item; do not assume the suggested cause is correct.
2. Fix the smallest root cause that improves the repository for future agents.
3. Add or update a proportionate regression test or validation check.
4. Run the relevant checks, then resolve the item with the change and verification result.
5. Leave items open when evidence is insufficient or the change is no longer small; promote substantial work to an `infra_request` rather than building it during cleanup.

Papercut cleanup does not authorize unrelated refactors, external changes, or weakening tests and safety checks merely to make the complaint disappear.

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

All state in **`investigation.db`** (SQLite, WAL mode). Schema: `leads`, `findings`, `connections`, `entities` + junction tables (incl. `finding_entities` linking findings→canonical entities, `finding_relations` for contradicts/corroborates/supersedes). Also: `infra_requests`, `human_actions`, `source_reliability`, `corrections`, `search_log`, `name_aliases`, `investigation_profiles`. Findings carry raw `date_of_event` + normalized `event_date_iso`/`date_precision` (`tools/date_normalize.py`).

Epstein corpus-derived facts (temporal events, normalized financials, entity resolution) live in the regenerable sidecar **`datasets/epstein_derived.db`** — see `investigations/epstein/AGENTS.md` and `tools/epstein_derived.py`.

Epstein reporting lives in **`datasets/epstein_reporting.db`** and is queried with
`tools/reporting_corpus.py`. It stores versioned articles and attributed claims;
reporting is not primary corroboration. Promote only reviewed claims with quoted
primary evidence. See `docs/modules/reporting.md`.

DOJ and SEC press releases live in **`datasets/government_releases.db`** and are
queried with `tools/government_release_corpus.py`. They are primary government
statements, not independent proof of the allegations they announce. Preserve
allegation/charge/conviction language exactly. See `docs/modules/government-releases.md`.

Lead lifecycle: `open -> in_progress -> completed | blocked | dead_end`
Auto-leads: `pending_triage -> open` (via `$triage-leads`) or `-> dead_end`

### Conventions
- Always use `uv run python` to invoke tools (not bare `python`)
- Lint changed Python files with `uv run ruff check <files>`; the full legacy tree is not yet lint-clean.
- Always use `--output FILE` for search results. **Session isolation**: `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`, all temp files in `$WORKDIR/`
- **Shell-safe evidence text**: zsh expands dollar-prefixed values inside double-quoted arguments before Python sees them. For tracker summaries, details, quotes, and notes containing currency, use a structured file/input mode when available or a properly escaped single-quoted argument; verify the persisted text before continuing.
- In zsh, `status` is a reserved read-only parameter. Capture command results with a different name such as `exit_code=$?`.
- Check search_log before querying: `from tools.lead_tracker import check_searched`. When calling `log_search`, omit `session_id` unless it is the integer ID of an existing `sessions` row; lead IDs, workdir names, and agent labels are not session IDs.

### Core CLI (full examples in docs/TOOL_REFERENCE.md)

| Tool | Key Commands |
|------|-------------|
| **Leads** | `lead_tracker.py {add,list,claim,complete,search,evidence,next,stats}` |
| **Findings** | `findings_tracker.py {add,connect,connections,search,timeline}` |
| **Audit** | `findings_tracker.py {unverified,provenance,verify,dispute,retract,correct,audit}` |
| **Infra** | `infra_tracker.py {add,list,show,claim,evaluate,complete,reject,search,next,stats}` |
| **Analysis** | `hypothesis_tracker.py`, `tag_manager.py`, `event_timeline.py`, `graph_tools.py`, `analysis_export.py`, `methodology_tracker.py` |
| **Pillars** | `pillar_tracker.py {register,list,show,seed,arc,career,event,events,bootstrap,alumni,cohort,dispersal,overlap,timeline,score,gaps,cross-pillar,pillar-network,stats}` |
| **Profile** | `investigation_context.py {show,list,set}` |

**90+ data source tools** organized by category. Read the relevant module when you need tool-specific commands:

| Module | Tools | Reference |
|--------|-------|-----------|
| **Financial** | EDGAR, ratios, market data, SEC enforcement, 990 nonprofits, FDIC, FINRA | `docs/modules/financial.md` |
| **Registries** | Unified registry + 20+ state/international corporate registries | `docs/modules/registries.md` |
| **Government** | USASpending, HigherGov, SAM, Medicare/Medicaid, CMS Open Payments, PPP | `docs/modules/government.md` |
| **Legal** | CourtListener, NYSCEF, HUDOC, BCMR/BCNR Reading Room, MilJustice (CAAF + service CCAs) | `docs/modules/legal.md` |
| **Political** | FEC, lobbying, FARA, Congress, GovInfo, Senate Finance archives | `docs/modules/political.md` |
| **OSINT/Infra** | crt.sh, Wayback, Shodan, URLScan, Maigret, FAA | `docs/modules/osint-infra.md` |
| **Corpora** | DOJ, LMSBAND, Unified, DugganUSA, DocumentCloud, MuckRock | `docs/modules/corpora.md` |
| **Blockchain** | Etherscan, Solscan, Dune | `docs/modules/blockchain.md` |
| **Network/Sanctions** | LittleSis, ICIJ, OpenCorporates, OpenSanctions, GLEIF, FinCEN | `docs/modules/network-sanctions.md` |
| **Patents/IP** | USPTO PatentsView, Assignment API | `docs/modules/patents.md` |
| **Peru-specific** | El Peruano gazette, SUNARP, SUNAT, Infogob, OEFA, SEACE, Contraloría | (see below) |

**Peru-specific tools**

- `query_elperuano.py {search,document,daily}` — Diario Oficial El Peruano gazette (https://busquedas.elperuano.pe/). Search normative documents (Decretos Supremos, Resoluciones Supremas/Ministeriales) by full-text, date range, type, or fetch a specific dispositivo id (e.g., `2493140-1`). Pulls full text via `/api/visor_html/{op}` and the PDF via metadata `urlPDF`. Uses GraphQL endpoint `POST /api/graphql?op=Generic` (the `?op=Generic` query string is required — bare `/api/graphql` returns 404).
- `ingest_elperuano.py` — Persists fetched gazette documents to `datasets/elperuano/<TIPO>-<NUMERO>.json` and optionally creates a finding via `findings_tracker.py` with `--sources elperuano --claim-type direct_quote --confidence confirmed` (the sumilla is verbatim from the primary source).

Run `uv run python tools/source_report.py` for live tool health status.

**Citation types** for new data sources: add one entry to `CITATION_REGISTRY` in `web/src/lib/citations.ts`. See `docs/CITATION_SYSTEM.md` for the registry pattern and example. For one-off URLs without a structured pattern, add the citation key → URL mapping to `web/src/data/source-urls.json`.

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

For investigation-specific source reliability overrides, see `investigations/<active_profile>/AGENTS.md`.

### Audit Sourcing (CRITICAL)

Every finding MUST provide: `--evidence`, `--claim-type`, `--source-quote`

**Claim types and max confidence:**
- `direct_quote` -> can be `confirmed` (if primary source)
- `paraphrase` -> max `high`
- `inference` / `synthesis` -> max `medium`
- `user_provided` -> as specified

**Agents MUST NOT set confidence to `confirmed` for inferences or syntheses.**

## Parallel Execution

Orchestrate work from a single Codex task using collaboration tools. Skills like `$deep-investigate` and `$pursue-lead` dispatch parallel subagents when their workflows benefit from independent research tracks.

- `investigation.db` uses WAL mode for safe concurrent subagent writes
- Each skill creates a unique `WORKDIR` — prevents cross-agent file collisions
- Subagents write `$WORKDIR/report-*.md` — the parent reads report files rather than full agent transcripts
- Default parallelism: ~6 subagents. Scale up or down based on task complexity and API rate limits — this is soft guidance, not a hard cap.
- Post-wave: run `uv run python tools/auto_leads.py run`

## Environment

- **Always use `uv run python`** to invoke tools
- Dehashed API: v2 requires an ACTIVE search subscription (not just credits) — query via `tools/query_dehashed.py`; `tools/selector_pivot.py` fans a selector across aggregators (Dehashed/IntelX gated behind `--enable-paid`)
- OpenCorporates API: basic tier (500 calls/month, 200/day max)
- Key identifiers (emails, addresses, contacts): see `memory/key-identifiers.md`

## Ethical Guidelines

Open-source intelligence using publicly released government documents, court filings, and public-domain datasets. Do not access non-public systems. Do not contact investigation subjects. Document provenance for all findings.
