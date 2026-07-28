---
name: deep-investigate
description: Orchestrated multi-source investigation using parallel sub-agents
user_invocable: true
---

# /deep-investigate

**CONTROL PLANE ORCHESTRATOR** — You are a planner, dispatcher, and coverage checker. You do NOT investigate directly. You assign source categories to parallel sub-agents, monitor their progress, synthesize their reports for corroboration/contradiction/gaps, and spawn follow-up leads. Sub-agents are Layer 1 research agents — they document facts, not theories.

Launch an orchestrated investigation of a person, entity, or topic using four parallel sub-agents that each own a dedicated source category. This ensures comprehensive coverage — no source gets skipped because the agent "found enough" in the corpus. Use the four-agent report contract below; for a smaller target, omit an unnecessary track and update the expected report set before launch.

## Arguments

- Required: target name or topic (e.g., `/deep-investigate Ron Soffer`, `/deep-investigate Barkmere Group Ltd`)
- Optional context after the name: `/deep-investigate Ron Soffer — French/Israeli lawyer referenced in SoftBank caper, Weingarten considering deploying him Jan 2019`

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

### Ambient Documentation
**Document everything, not just what's relevant to your current hypothesis.**
When you encounter information during investigation — officer names, addresses,
corporate relationships, financial figures, dates, professional affiliations —
record it even if it doesn't obviously connect to the current lead. Use
`entity_tracker.py` to register entities, roles, and addresses. Use
`findings_tracker.py` with `--type background` for contextual facts that don't
directly answer the current question but are worth preserving. These ambient
findings compound across investigations and surface connections later.

### Documentation Thoroughness
Sub-agents MUST:
- **Record scoped negative results.** Put every zero-result query, filter, date
  range, source, and coverage limitation in `search_log` and the agent report.
  Create a durable negative finding only when the source is authoritative for
  the question, identity resolution is sound, the searched scope is bounded,
  and the result artifact supplies the required evidence and source quote. A
  zero is never proof that the underlying fact or relationship does not exist.
- **Record mundane facts.** Officer names, registered agent addresses, formation dates, filing numbers, EINs — even when boring. These become critical during cross-referencing.
- **Record baseline comparisons.** "GEO Group's 695% profit increase" means nothing without "vs. industry average of X%." Always seek the denominator.
- **Check ALL required sources for the target type** — not just the ones most likely to return results. See tool checklists in each agent prompt below.

## Architecture

You are the **orchestrator**. You do NOT search sources yourself. Instead you:

1. Assess the target and determine what's already known
2. **Build a research plan** — identify which sources are relevant and assign them to agents
3. Write focused prompts for four parallel sub-agents with explicit source mandates
4. Launch all sub-agents simultaneously using the Agent tool
5. Wait for all to complete
6. Synthesize their results — identify corroboration, contradictions, and gaps
7. Record final findings and spawn follow-up leads

### Research Planning Protocol

**Before writing any agent prompts**, create a source assignment matrix. This prevents agents from defaulting to web searches and ensures every relevant tool gets used.

**Step 1: Identify all relevant sources for this target.** Consider the target type:

| Target Type | Critical Sources (must check) |
|-------------|-------------------------------|
| **Person** | CourtListener, state/local court catalog, property/recorder catalog, FEC, 990s, EDGAR, LittleSis, registries (as officer), FARA, lobbying, OpenSanctions |
| **Corporation** | State registries, property/recorder catalog, federal and state/local court sources, EDGAR (10-K, proxy), USASpending, SAM.gov, lobbying, FARA, GLEIF |
| **Nonprofit** | IRS 990 (lookup, grants, officers, financials, red-flags), EDGAR, state registries, CourtListener, FEC (PAC affiliates) |
| **Government actor** | FEC, lobbying (post-government), FARA, CourtListener, LittleSis, EDGAR (financial disclosures) |
| **Financial entity** | EDGAR, GLEIF, DS10, ACRIS, UCC, registries, CourtListener, USASpending |

**Nonprofit network analysis:** For nonprofit targets, Agent B should also run:
- `uv run python tools/query_990.py lookup <EIN> --output $WORKDIR/990-lookup.json`
- `uv run python tools/query_990.py flow <EIN> --depth 1 --output $WORKDIR/990-flow.json`
- `uv run python tools/query_990.py officer-search "<NAME>" --output $WORKDIR/990-officers.json`

If the flow output shows circular flows or 10+ network nodes, recommend `/trace-grants` for full network analysis as a parallel process.

**Step 2: Assign sources to agents.** The 4-agent split (corpus, corporate/financial, legal, network/OSINT) works well for single targets. Give each source category one persistence owner: other agents may flag cross-category records in their reports, but they do not repeat that owner's searches or create duplicate findings. For custom multi-target plans, ensure each source appears in exactly one primary mandate. Create a table:

```
| Source | Agent |
|--------|-------|
| CourtListener | Agent C (legal) |
| 990s | Agent B (corporate) |
| FEC | Agent B (corporate) |
| Registries | Agent B (corporate) |
| EDGAR | Agent B (corporate) |
| LittleSis | Agent D (network) |
| ... | ... |
```

**Step 3: Include the source list in each agent's prompt.** Don't just say "search relevant sources" — list the specific tools each agent must run. Agents skip sources they aren't explicitly told to check.

### Custom Multi-Target Research Plans

When investigating a new area with multiple targets, use the **Investigation Depth Tiers** from `research/INVESTIGATIVE_METHODOLOGY.md`:

1. **Landscape scan first** — Don't jump to deep dives. Run a light pass over 10-30 targets using WebSearch + 2-3 key sources. Map who's involved and how they relate. Create leads, not findings, for most targets.

2. **Triage and prioritize** — Which targets are structurally important? Which have records to find? Which are central to the investigation's questions? Flag 2-4 targets for deep dives.

3. **Deep dives on selected targets** — Run `/deep-investigate` (this skill, full 4-agent treatment) only on the highest-value targets.

4. **Standard investigation for the rest** — Medium-priority targets get `/pursue-lead` (single-agent, full source checklist). Low-priority targets stay as open leads for later.

When running the deep dives, choose between:

**Option A: Run /deep-investigate per target** (preferred for 2-3 targets)
- Each target gets the full 4-agent treatment with dedicated source coverage
- Best source coverage, but uses more agents

**Option B: Organize by topic with source mandates** (for 4+ related targets)
- Topical agents (e.g., "GEO Group agent", "Miller network agent") are fine
- BUT each agent's prompt MUST include an explicit source checklist from the matrix above
- Include this in every topical agent prompt: "You MUST check ALL of these sources, not just web search: [LIST]. Record negative results from each source."
- After topical agents complete, run a **coverage check**: which sources in the matrix were NOT used? Spawn follow-up agents to fill gaps.

## Process

### 0. Session Setup — Prevent File Collisions

Create a unique working directory for this investigation. This prevents parallel `/deep-investigate` runs from overwriting each other's temp files.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Store this path. ALL `--output` paths and report file paths in this session use this directory instead of `/tmp/`. When writing sub-agent prompts below, substitute the actual `WORKDIR` path everywhere you see `[WORKDIR]`.

### 1. Pre-Flight: Assess the Target

Before launching agents, gather what's already known:

```bash
# Existing findings
uv run python tools/findings_tracker.py search "<TARGET>"

# Existing leads
uv run python tools/lead_tracker.py search "<TARGET>"

# Existing entity records
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
for r in db.execute('SELECT id, name FROM entities WHERE name LIKE ?', ('%TARGET%',)).fetchall():
    print(r)
for r in db.execute('SELECT id, person_name, role FROM entity_roles WHERE person_name LIKE ?', ('%TARGET%',)).fetchall():
    print(r)
"
```

Determine:
- Is this a **person** or **entity**?
- What's the investigative context? (Why are we looking at this target?)
- What's already known? (Avoid duplicating existing findings)
- What hypotheses should the agents test?

Write a **target briefing** — a 2-3 sentence summary of who/what this is and why it matters. Every sub-agent gets this briefing.

### 2. Launch Parallel Sub-Agents

Use the Agent tool to launch the four independent sub-agents simultaneously in a single message. If the plan intentionally uses fewer tracks, define that exact expected report set before launch. Each agent gets:
- The target briefing
- Its specific source mandate
- Instructions to record findings via the CLI tools
- The reminder: "Record zero-result searches with their exact scope and limitations; create a finding only when the bounded negative meets the evidence standard"
- **CRITICAL: Use `--output [WORKDIR]/<agent>-<query>.json` on ALL search commands** to keep context lean. Read the JSON files only when you need specific details.

#### Agent A: Document Corpus

**Sources**: All corpus tools listed in the active investigation profile (loaded via `investigation_context.py`).

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT — use the thread name from the investigation profile if applicable, e.g. "This is part of the [THREAD_NAME] investigation thread."]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL local document databases exhaustively for any mention of this target. Use alternate spellings, name variants, and associated terms.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

REQUIRED SEARCHES:
For each tool listed in the investigation profile's corpus_tools, run a search against "[TARGET]" and any name variants. Use --output [WORKDIR]/a-<tool-name>.json for each. Example pattern:
  uv run python tools/<corpus_tool>.py search "[TARGET]" --limit 20 --output [WORKDIR]/a-<tool-name>.json

For tools that support sub-commands (entities, cooccurrence, emails, docs, triples), run those additional queries as well.

For EVERY document found, read the full text (kabasshouse holds the highest-quality OCR for any EFTA id):
uv run python tools/ingest_kabasshouse.py doc EFTA_ID

Extract: dates, names, financial amounts, relationships, exact quotes.

RECORD findings using:
uv run python tools/findings_tracker.py add --target "[TARGET]" --type TYPE \
  --summary "..." --evidence EFTA_ID --claim-type direct_quote \
  --source-quote "EFTA_ID:exact quote" --sources kabass --confidence LEVEL

NOTE: the same EFTA page appearing in kabasshouse AND doj_vol11/lmsband is ONE source re-OCR'd, not corroboration — cite the source you actually read (usually kabass).

Record connections using:
uv run python tools/findings_tracker.py connect --person-a "..." --person-b "..." \
  --type TYPE --description "..." --evidence EFTA_ID \
  --source-quote "EFTA_ID:exact quote" --strength STRENGTH

If zero results: record the exact corpus, query, filters, and covered scope as a
bounded negative observation. No hit in a large corpus is not proof that the
underlying fact or relationship does not exist.

PROACTIVE SOURCE DISCOVERY:
As you search, be curious. If documents reference data sources we don't have tools for, or mention databases/registries/archives that could be queried, note them. For example:
- A document mentions a filing in a court we don't cover → note the court and docket
- An email references a foreign corporate registry entry → note the registry and entity
- A record mentions a dataset or database we haven't ingested → note what it is and where to get it
At the end of your investigation, list any SOURCE GAPS you identified and create infrastructure requests for valuable ones:
uv run python tools/infra_tracker.py add --title "Integrate [SOURCE]" --type new_source --description "Found during [TARGET] investigation. [Details]. URL: [URL]. Access: [METHOD]." --source-name "[SOURCE]" --priority medium --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

BEFORE WRITING YOUR REPORT: Verify that EVERY factual discovery has been recorded via findings_tracker.py add and every new entity via entity_tracker.py. The report file is a SUMMARY of what you already persisted to the database. Do not put new information only in the report — the report file is temporary and will be deleted.

FINAL STEP — MANDATORY: When done, write your report to [WORKDIR]/report-agent-a.md using this format:
---
agent: agent-a
target: "[TARGET]"
skill: deep-investigate
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
---
# Agent A Report: [TARGET]
## Key Discoveries
- [1-2 sentence summary of each significant finding]
## Findings Added
[count] findings (IDs: list them)
## Connections Added
[count] connections
## Negative Results
- [Sources searched with zero results — investigatively significant]
## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [tool command used] | [count] | [count] |
## Source Gaps Identified
- [New data sources discovered during investigation]
## Follow-Up Leads Created
- Lead #X: [description]
## Learnings
- [Friction] any tool/source issues encountered
- [Surprise] unexpected findings worth noting
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes

Use uv run python for all commands.
```

#### Agent B: Corporate, Financial & Property Records

**Sources**: Corporate registries, the property/recorder source catalog and adapters, SEC EDGAR, FEC, IRS 990, UCC, FAA, LDA Lobbying, FARA, GLEIF, OpenSanctions, DS10 Financial

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT if applicable]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL corporate, financial, property, and regulatory databases for this target. You are looking for: corporate registrations, SEC filings, property records, political donations, lobbying activity, foreign agent registrations, nonprofit filings, UCC liens, and aircraft registrations.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

CORPUS OWNERSHIP:
Agent A owns corpus searches and corpus-derived findings. Do not repeat Agent
A's corpus baseline or persist a second finding from the same corpus evidence.
If a structured record points to a potentially new corpus document, put the
reference and question in this report for parent reconciliation.

REQUIRED SEARCHES (do ALL of these — use --output on every search):

CORPORATE REGISTRIES:
1. uv run python tools/query_registry.py search "[TARGET]" --output [WORKDIR]/b-registry.json
2. uv run python tools/query_registry.py officers "[TARGET]" --output [WORKDIR]/b-officers.json
3. uv run python tools/query_registry.py address "[KNOWN_ADDRESS]" --output [WORKDIR]/b-addr.json  (if applicable)

SEC EDGAR:
4. uv run python tools/query_edgar.py search "[TARGET]" --size 20 --facets --output [WORKDIR]/b-edgar.json
5. uv run python tools/query_edgar.py lookup "[TARGET]" --output [WORKDIR]/b-edgar-lookup.json
6. uv run python tools/query_edgar.py search "[TARGET]" "[ASSOCIATED_ENTITY]" --size 10 --output [WORKDIR]/b-edgar2.json  (if applicable)

PROPERTY AND RECORDER RECORDS:
7. uv run python tools/public_records_search_plan.py "[TARGET]" --output [WORKDIR]/b-public-record-plan.json
8. uv run python tools/query_property.py owner "[TARGET]" --output [WORKDIR]/b-property-owner.json
9. uv run python tools/query_property.py sources --output [WORKDIR]/b-property-sources.json
10. If an address is known:
    uv run python tools/query_property.py address "[KNOWN_ADDRESS]" --output [WORKDIR]/b-property-address.json
11. Follow source IDs and operations from the plan with `query_property.py --source`
    for direct adapters or `public_records_actions.py plan` for account, request,
    purchase, formal-feed, or physical-office routes.

CAMPAIGN FINANCE:
8. uv run python tools/query_fec.py donor "[TARGET]" --limit 20 --output [WORKDIR]/b-fec.json
9. uv run python tools/query_fec.py employer "[TARGET]" --output [WORKDIR]/b-fec-emp.json  (if entity)

NONPROFITS:
10. uv run python tools/query_990.py search "[TARGET]" --output [WORKDIR]/b-990.json
10a. uv run python tools/query_990.py lookup <EIN> --output [WORKDIR]/b-990-lookup.json  (if EIN known — comprehensive view)
10b. uv run python tools/query_990.py officers <EIN> --output [WORKDIR]/b-990-officers.json  (board + staff)
10c. uv run python tools/query_990.py financials <EIN> --output [WORKDIR]/b-990-financials.json  (revenue/expense trends)

LOBBYING:
11. uv run python tools/query_lobbying.py client "[TARGET]" --output [WORKDIR]/b-lda-client.json
12. uv run python tools/query_lobbying.py registrant "[TARGET]" --output [WORKDIR]/b-lda-reg.json
13. uv run python tools/query_lobbying.py lobbyist "[TARGET]" --output [WORKDIR]/b-lda-lob.json

FOREIGN AGENTS:
14. uv run python tools/query_fara.py search "[TARGET]" --output [WORKDIR]/b-fara.json

UCC FILINGS:
15. uv run python tools/query_registry.py ucc-search "[TARGET]" --output [WORKDIR]/b-ucc.json

FAA AIRCRAFT:
16. uv run python tools/ingest_faa.py search "[TARGET]" --output [WORKDIR]/b-faa.json

GLEIF (corporate hierarchy — financial entities):
17. uv run python tools/query_gleif.py search "[TARGET]" --limit 10 --output [WORKDIR]/b-gleif.json
18. If LEI found: uv run python tools/query_gleif.py hierarchy <LEI> --output [WORKDIR]/b-gleif-hier.json

UK COMPANIES HOUSE (if API key configured):
19. uv run python tools/ingest_uk_companies_house.py search "[TARGET]" --limit 10 --output [WORKDIR]/b-uk-companies.json
20. If found: uv run python tools/ingest_uk_companies_house.py officers <COMPANY_NUMBER> --output [WORKDIR]/b-uk-officers.json
21. If found: uv run python tools/ingest_uk_companies_house.py psc <COMPANY_NUMBER> --output [WORKDIR]/b-uk-psc.json

OPENSANCTIONS (PEP/sanctions check — if ingested):
22. uv run python tools/query_opensanctions.py search "[TARGET]" --limit 10 --output [WORKDIR]/b-sanctions.json

USVI CORPORATE REGISTRY:
23. uv run python tools/ingest_usvi.py search "[TARGET]"

DS10 DEUTSCHE BANK FINANCIAL RECORDS:
24. uv run python tools/parse_ds10_financials.py query --entity "[TARGET]"

For each hit, investigate further (e.g., read SEC filings, pull 990 details, check filing histories).

Register entities, roles, and addresses in investigation.db as you find them.

RECORD findings using the findings_tracker.py CLI. CRITICAL: Always include --sources with the data source name(s) that produced each finding (e.g., --sources registry edgar fec). Even if a search returns zero results, note that in your final summary — negative results from authoritative sources are investigatively significant.

PROACTIVE SOURCE DISCOVERY:
As you search, be curious about data sources we're missing. If you discover:
- A corporate registry in a jurisdiction we don't cover (e.g., Cayman, BVI, Liechtenstein, Luxembourg, Jersey, Delaware) → note the registry URL/API and create an infrastructure lead
- A specialized financial database or regulatory filing system → note how to access it
- A nonprofit, foundation, or entity registered somewhere we can't currently search → note the gap
- An SEC filing type or EDGAR feature we're not using → note the enhancement
At the end of your investigation, list SOURCE GAPS and create infrastructure requests:
uv run python tools/infra_tracker.py add --title "Add [JURISDICTION] registry" --type new_registry --description "Found during [TARGET] investigation. [Details]. URL: [URL]. Access: [METHOD]." --source-name "[REGISTRY]" --priority medium --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

If you find a data source that would immediately help, probe only enough to
verify the public endpoint and create the infrastructure request above. Do not
implement it during this research wave; `/build-infra` owns the claimed build,
tests, documentation, citations, source-health update, and completion.

BEFORE WRITING YOUR REPORT: Verify that EVERY factual discovery has been recorded via findings_tracker.py add and every new entity via entity_tracker.py. The report file is a SUMMARY of what you already persisted to the database. Do not put new information only in the report — the report file is temporary and will be deleted.

FINAL STEP — MANDATORY: When done, write your report to [WORKDIR]/report-agent-b.md using this format:
---
agent: agent-b
target: "[TARGET]"
skill: deep-investigate
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
---
# Agent B Report: [TARGET]
## Key Discoveries
- [1-2 sentence summary of each significant finding]
## Findings Added
[count] findings (IDs: list them)
## Connections Added
[count] connections
## Entities Registered
[count] entities (IDs and names)
## Negative Results
- [Sources searched with zero results — investigatively significant]
## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [tool command used] | [count] | [count] |
## Source Gaps Identified
- [New data sources/registries discovered]
## Follow-Up Leads Created
- Lead #X: [description]
## Learnings
- [Friction] any tool/source issues encountered
- [Surprise] unexpected findings worth noting
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes

Use uv run python for all commands.
```

#### Agent C: Legal & Court Records

**Sources**: CourtListener (dockets, opinions, parties, judges), the state/local court source catalog and normalized sidecar, FARA (detailed review), LDA Lobbying (detailed review)

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT if applicable]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL legal and court databases for this target. You are looking for: federal litigation (as party, witness, or mentioned), state court cases, judicial opinions, regulatory actions, enforcement proceedings, FARA registrations, and lobbying disclosures.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

CORPUS OWNERSHIP:
Agent A owns corpus searches and corpus-derived findings. Do not repeat Agent
A's corpus baseline or persist a second finding from the same corpus evidence.
If a legal record points to a potentially new corpus document, put the
reference and question in this report for parent reconciliation.

REQUIRED SEARCHES (use --output on all):

COURTLISTENER (federal courts — use --output on ALL):
1. uv run python tools/query_courtlistener.py search --party "[TARGET]" --output [WORKDIR]/c-cl-party.json
2. uv run python tools/query_courtlistener.py cases "[TARGET]" --output [WORKDIR]/c-cl-cases.json
3. uv run python tools/query_courtlistener.py search "[TARGET]" --type o --output [WORKDIR]/c-cl-opinions.json
4. If any dockets found: uv run python tools/query_courtlistener.py docket <DOCKET_ID> --output [WORKDIR]/c-cl-docket.json
5. For important opinions: uv run python tools/query_courtlistener.py opinion <OPINION_ID> --lines 500 --output [WORKDIR]/c-cl-opinion-<OPINION_ID>.json
6. For citation graph: uv run python tools/query_courtlistener.py citations <OPINION_ID> --output [WORKDIR]/c-cl-citations.json
7. RECAP documents: uv run python tools/query_courtlistener.py recap-search "[TARGET]" --output [WORKDIR]/c-cl-recap.json
8. FJC database: uv run python tools/query_courtlistener.py fjc --defendant "[TARGET]" --output [WORKDIR]/c-cl-fjc.json

STATE AND LOCAL COURTS:
9. uv run python tools/public_records_search_plan.py "[TARGET]" --output [WORKDIR]/c-public-record-plan.json
10. uv run python tools/query_state_courts.py search "[TARGET]" --output [WORKDIR]/c-state-courts.json
11. uv run python tools/query_state_courts.py sources --output [WORKDIR]/c-state-court-sources.json
12. Follow source IDs and operations from the plan with
    `query_state_courts.py --source` when a direct route exists, or render the
    catalog-backed work with `public_records_actions.py plan`.

For each case found:
- What is the nature of the case?
- Who are the other parties? (embedded in search results as party/attorney/firm arrays)
- What is the timeline?
- Are any investigation-associated persons or entities involved?
- What do the opinions/rulings reveal? (read full text with `opinion` command)
- What RECAP documents are available? (download key filings with `download` command)

FARA (deep check):
6. uv run python tools/query_fara.py search "[TARGET]" --output [WORKDIR]/c-fara.json
7. If found: uv run python tools/query_fara.py detail <REG_NUM> --output [WORKDIR]/c-fara-detail.json

LOBBYING (deep check):
8. uv run python tools/query_lobbying.py lobbyist "[TARGET]" --output [WORKDIR]/c-lda-lob.json
9. uv run python tools/query_lobbying.py client "[TARGET]" --output [WORKDIR]/c-lda-client.json
10. If filings found: uv run python tools/query_lobbying.py filings --client "[TARGET]" --output [WORKDIR]/c-lda-filings.json

INVESTIGATION REPORTS (ingested PDFs):
11. uv run python tools/query_investigations.py search "[TARGET]" --limit 10 --output [WORKDIR]/c-inv.json

RECORD all findings using the findings_tracker.py CLI. CRITICAL: Always include --sources with the data source name(s) (e.g., --sources courtlistener fara lobbying). Record connections between the target and any investigation-network persons discovered in litigation.

A court zero is notable only when the selected CourtListener field matches the
person's expected role, identity resolution is sound, and the query/date/court
scope is recorded. Put ordinary zeroes in `search_log` and this report; create
a finding only when the bounded result meets the evidence standard.

PROACTIVE SOURCE DISCOVERY:
As you search court records, look for:
- Court systems we don't currently query (state courts, bankruptcy courts, immigration courts, foreign proceedings)
- Specific dockets referenced in documents that should be ingested (PACER dockets, SDNY exhibits)
- Legal databases that would help (state bar records, judicial disclosure databases, arbitration records)
- Government investigation reports or hearing transcripts not yet in our investigations.db
If you find a new court system or legal database with a public API, verify the endpoint and create an infrastructure request. Do not build it during this research wave; `/build-infra` owns implementation:
uv run python tools/infra_tracker.py add --title "Integrate [COURT/DATABASE]" --type new_source --description "Discovered during [TARGET] investigation. [Details, URL, access method]." --source-name "[SOURCE]" --priority medium --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

BEFORE WRITING YOUR REPORT: Verify that EVERY factual discovery has been recorded via findings_tracker.py add and every new entity via entity_tracker.py. The report file is a SUMMARY of what you already persisted to the database. Do not put new information only in the report — the report file is temporary and will be deleted.

FINAL STEP — MANDATORY: When done, write your report to [WORKDIR]/report-agent-c.md using this format:
---
agent: agent-c
target: "[TARGET]"
skill: deep-investigate
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
---
# Agent C Report: [TARGET]
## Key Discoveries
- [1-2 sentence summary of each significant finding]
## Findings Added
[count] findings (IDs: list them)
## Connections Added
[count] connections
## Negative Results
- [Sources searched with zero results — investigatively significant]
## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [tool command used] | [count] | [count] |
## Source Gaps Identified
- [New courts/legal databases discovered]
## Follow-Up Leads Created
- Lead #X: [description]
## Learnings
- [Friction] any tool/source issues encountered
- [Surprise] unexpected findings worth noting
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes

Use uv run python for all commands.
```

#### Agent D: Network, OSINT & Open Web

**Sources**: LittleSis, ICIJ/~~Aleph~~, Shodan, crt.sh, Wayback Machine, URLScan.io, WebSearch, WebFetch, ~~GDELT~~, plus any investigation-specific OSINT tools from the profile
> DEPRECATED (March 2026): Aleph — OCCRP removed free tier in 2026. Tool returns 0 results without paid API key. Skip Aleph queries until access is restored.
> DEPRECATED (March 2026): GDELT — 3-month rolling window + unreliable API (frequent timeouts). Use WebSearch for news coverage instead.

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT if applicable]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL network mapping, offshore leak, and open web sources for this target. You are looking for: pre-mapped relationships, offshore entities, public reporting, news coverage, and biographical information that provides context.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

CORPUS OWNERSHIP:
Agent A owns corpus searches and corpus-derived findings. Do not repeat Agent
A's corpus baseline or persist a second finding from the same corpus evidence.
If a network or web record points to a potentially new corpus document, put
the reference and question in this report for parent reconciliation.

REQUIRED SEARCHES (use --output on all):

LITTLESIS (relationship mapping):
1. uv run python tools/query_littlesis.py search "[TARGET]" --output [WORKDIR]/d-ls-search.json
2. If found: uv run python tools/query_littlesis.py entity <ID> --output [WORKDIR]/d-ls-entity.json
3. If found: uv run python tools/query_littlesis.py relationships <ID> --limit 50 --output [WORKDIR]/d-ls-rels.json

OCCRP ALEPH (corporate registries, leaks, sanctions):
# DEPRECATED (March 2026): OCCRP removed free tier in 2026. Tool returns 0 results without paid API key. Skip Aleph queries until access is restored.
4. uv run python tools/query_aleph.py search "[TARGET]" --schema Person --output [WORKDIR]/d-aleph-person.json
5. uv run python tools/query_aleph.py search "[TARGET]" --schema Company --output [WORKDIR]/d-aleph-company.json
6. If found: uv run python tools/query_aleph.py expand <ENTITY_ID> --output [WORKDIR]/d-aleph-expand.json

ICIJ OFFSHORE LEAKS (official remote service; no local database required):
7. uv run python tools/query_icij.py search "[TARGET]" --output [WORKDIR]/d-icij.json

WEB SEARCH (use WebSearch tool directly — NOT bash):
8. "[TARGET]" — basic biography
9. "[TARGET]" {primary_subject} — known connections (use primary_subject from investigation profile)
10. "[TARGET]" lawsuit OR investigation OR scandal
11. "[TARGET]" [ASSOCIATED_CONTEXT] — e.g., "Ron Soffer lawyer Paris SoftBank"
12. "[TARGET]" site:opencorporates.com OR site:linkedin.com

WEB FETCH (use WebFetch tool for key pages):
- If Wikipedia page exists, fetch it
- If company/firm website found, fetch the about/team page
- If relevant news articles found, fetch and extract key facts

INVESTIGATION-SPECIFIC OSINT (search any investigation-specific tools from the profile):
13. Run any investigation-specific OSINT tools listed in the profile's corpus_tools that Agent A didn't cover.

INFRASTRUCTURE RECON (DNS, SSL certs, hosting, historical web):
14. uv run python tools/query_shodan.py domain "[TARGET_DOMAIN]" --output [WORKDIR]/d-shodan-domain.json  (if domain known)
15. uv run python tools/query_shodan.py search "ssl:[TARGET_DOMAIN]" --output [WORKDIR]/d-shodan-ssl.json  (if domain known)
16. uv run python tools/query_shodan.py host [TARGET_IP] --output [WORKDIR]/d-shodan-host.json  (if IP known)
17. uv run python tools/query_crtsh.py search "[TARGET_DOMAIN]" --output [WORKDIR]/d-crtsh.json  (cert transparency — subdomain enum)
18. uv run python tools/query_crtsh.py timeline "[TARGET_DOMAIN]" --output [WORKDIR]/d-crtsh-timeline.json
19. uv run python tools/query_wayback.py timeline "[TARGET_DOMAIN]" --output [WORKDIR]/d-wayback.json  (historical snapshots)
20. uv run python tools/query_wayback.py first "[TARGET_DOMAIN]" --output [WORKDIR]/d-wayback-first.json
21. uv run python tools/query_urlscan.py search "domain:[TARGET_DOMAIN]" --output [WORKDIR]/d-urlscan.json  (tech stack, linked domains)

GDELT (global news):
22. uv run python tools/query_gdelt.py articles "[TARGET]" --limit 30 --output [WORKDIR]/d-gdelt-art.json
23. uv run python tools/query_gdelt.py context "[TARGET]" --limit 20 --output [WORKDIR]/d-gdelt-ctx.json

RECORD all findings using the findings_tracker.py CLI. CRITICAL: Always include --sources with the data source name(s) (e.g., --sources web_search littlesis gdelt). Web sources should use claim-type "paraphrase" with the URL as evidence and --sources web_search. Record connections to any network-connected persons identified in the investigation profile or discovered during research.

For web research: prioritize PRIMARY sources (court filings, government records, corporate registries) over secondary (news articles, Wikipedia). Note source reliability.

PROACTIVE SOURCE DISCOVERY (CRITICAL — this is your strongest mandate):
You have the widest view of any agent because you search the open web. As you research, actively look for:
- **New data sources**: Government databases, public registries, FOIA libraries, leaked document archives, investigation reports, congressional hearing transcripts that we haven't ingested
- **Foreign registries**: If the target has connections to specific countries, search for that country's corporate registry, court system, or financial authority database. Note the URL, access method (API? bulk download? web scrape?), and authentication requirements.
- **Specialized databases**: Import/export records (ImportGenius, Panjiva), shipping registries (MarineTraffic, IMO), patent databases (USPTO, EPO), academic affiliations (ORCID), sanctions lists beyond OpenSanctions, beneficial ownership registries (UK PSC, EU BORIS)
- **Downloadable datasets**: HuggingFace, data.gov, archive.org, specific investigation archives that could be bulk-ingested
- **Existing tool improvements**: If you use a web search to answer something that one of our tools SHOULD be able to answer, note the gap

For each new source discovered:
1. Note: name, URL, data type, access method, relevance to investigation
2. Create an infrastructure lead if it has broad investigative value
3. If it has a plausible public endpoint, probe only enough to verify access and include those probe results in the infrastructure request. Do not implement it during this research wave; `/build-infra` owns implementation and validation.

uv run python tools/infra_tracker.py add --title "Integrate [SOURCE]" --type new_source --description "Found during [TARGET] web research. URL: [URL]. Data: [WHAT]. Access: [HOW]. Value: [WHY]." --source-name "[SOURCE]" --source-url "[URL]" --priority [high/medium] --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

BEFORE WRITING YOUR REPORT: Verify that EVERY factual discovery has been recorded via findings_tracker.py add and every new entity via entity_tracker.py. The report file is a SUMMARY of what you already persisted to the database. Do not put new information only in the report — the report file is temporary and will be deleted.

FINAL STEP — MANDATORY: When done, write your report to [WORKDIR]/report-agent-d.md using this format:
---
agent: agent-d
target: "[TARGET]"
skill: deep-investigate
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
---
# Agent D Report: [TARGET]
## Key Discoveries
- [1-2 sentence summary of each significant finding]
## Findings Added
[count] findings (IDs: list them)
## Connections Added
[count] connections
## Negative Results
- [Sources searched with zero results]
## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [tool command used] | [count] | [count] |
## Source Gaps Identified
- [New data sources discovered, with URL and access method]
## Follow-Up Leads Created
- Lead #X: [description]
## Learnings
- [Friction] any tool/source issues encountered
- [Surprise] unexpected findings worth noting
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes

Use uv run python for all commands.
```

### 3. Wait for Agents and Read Reports

**DO NOT use TaskOutput to retrieve agent results.** Agent transcripts are 10-50MB and will bloat context.

Instead, agents write structured reports to `[WORKDIR]/report-agent-{a,b,c,d}.md`. Poll for completion, then read the reports.

**CRITICAL: DB-first, report-second.** Sub-agents MUST write every factual discovery to `findings_tracker.py add` and every entity to `entity_tracker.py` BEFORE writing the report file. The report is a summary of what was already persisted to the database, NOT the primary record. If an agent discovers something and only writes it to the report file without recording it via the CLI tools, that information is lost when the tmp directory is cleaned up. The database is permanent; the report is ephemeral.

```
# Launch all 4 agents with run_in_background=true
# Each agent's prompt instructs it to write [WORKDIR]/report-agent-{a,b,c,d}.md

# Poll for completion (check if report files exist)
Bash: ls -la [WORKDIR]/report-agent-*.md 2>/dev/null | wc -l
# Repeat every 30s until count = 4 OR timeout reached (see below)

# Once all reports exist, read them:
Read("[WORKDIR]/report-agent-a.md")
Read("[WORKDIR]/report-agent-b.md")
Read("[WORKDIR]/report-agent-c.md")
Read("[WORKDIR]/report-agent-d.md")
```

**Polling with Liveness Checks:**
- Poll every 30 seconds for report files
- If an agent has no report after 5 minutes, check its output tail (`TaskOutput` with `block=false`) to see if it's still actively working (making tool calls, writing output)
- If the agent is still active (output growing), let it continue — complex targets take time
- If the agent appears hung or crashed (no output change across 2+ checks), stop it and create a follow-up lead covering its assigned scope
- Synthesize from whatever reports exist once all agents have either completed or been declared hung
- An actively working agent should never be cut off prematurely

Each report is ~2KB (vs 25MB transcript). If you need deeper detail on a specific finding, read the agent's `--output` JSON files (e.g., `[WORKDIR]/a-doj.json`).

### 4. Synthesize Results

**Note: The orchestrator's synthesis step identifies corroboration, contradictions, and gaps across agents. It does NOT assess narrative potential, article-worthiness, or character entry points — those are editorial concerns. Label any cross-agent inference as `claim_type=synthesis` with `confidence=medium`.**

After reading all 4 report files:

1. **Count findings**: How many did each agent produce?
2. **Identify corroboration**: Did multiple agents find the same facts from independent sources? (e.g., corpus email confirms a corporate filing)
3. **Identify contradictions**: Do any findings conflict?
4. **Identify gaps**: Did any agent return zero results from sources that should have data?
5. **Map the network**: Who does this target connect to? Draw the relationship map.
6. **Collect infrastructure recommendations**: What new data sources, tools, or tool improvements did agents identify? Consolidate into actionable items.
7. **Drill down selectively**: If a report mentions a critical finding, read the specific `--output` JSON for details. Do NOT read all JSON files — only the ones relevant to synthesis.
8. **Flag gaps and anomalies**: What records should exist but don't? What contradictions appeared between agents' results? What factual questions remain unanswered? Put unresolved gaps in the report and spawn research leads. Create a negative synthesis finding only when the missing record expectation, identity resolution, exact searched scope, and evidence artifact satisfy the bounded-negative standard; use `claim_type=synthesis` and `confidence=medium`.
9. **Run ACH competition**: Check `uv run python tools/hypothesis_tracker.py list`. When two or more hypotheses touch the target, run `matrix --competition-group <slug>` and `compete --competition-group <slug>` for each relevant competition group. Fold the rankings into the synthesis report as the hypotheses with **least evidence against**, never the most evidence for.
11. **Check tool coverage**: Did agents actually use the full source list, or did they skip tools? Flag any sources that should have been checked but weren't, and note it in the summary.

### 4b. Ingest Agent Learnings

After reading all reports, ingest their Learnings sections into the methodology observation system:

```bash
for report in $WORKDIR/report-agent-*.md; do
    uv run python tools/methodology_tracker.py ingest-report "$report" --skill deep-investigate
done
```

This captures tool friction, surprise findings, and process insights for later `/review-methodology` analysis.

### 5. Record Synthesis Findings

If the sub-agents' individual findings combine to tell a larger story, record a synthesis finding:

```bash
uv run python tools/findings_tracker.py add --target "[TARGET]" --type intelligence \
  --summary "SYNTHESIS: [what the combined evidence shows]" \
  --evidence [ALL_EVIDENCE_REFS] --claim-type synthesis \
  --source-quote "[REF]:key supporting fact" --sources analysis_run --confidence medium
```

### 6. Spawn Follow-Up Leads

Create leads for:
- New persons discovered across multiple agents
- Entities that need their own `/deep-investigate`
- Financial trails requiring further tracing
- Sources that were unavailable or need deeper local access (e.g., the ICIJ remote service failed or depth > 1 requires local Neo4j)
- Hypotheses generated by the synthesis
- **Infrastructure requests**: New data sources to integrate, tools to build, existing tools to extend. Use `infra_tracker.py add` (not lead_tracker) and include URL, access method, and investigative value.

### 7. Present Summary to User

Format:
```
## /deep-investigate [TARGET] — Results

### Target Profile
[1-2 sentences]

### Agent Results
| Agent | Findings | Connections | Key Discovery |
|-------|----------|-------------|---------------|
| Corpus | X | Y | ... |
| Corporate/Financial | X | Y | ... |
| Legal/Court | X | Y | ... |
| Network/OSINT | X | Y | ... |

### Key Findings
1. [Most significant finding]
2. [Second most significant]
...

### Corroboration
- [Fact confirmed by 2+ independent source types]

### Gaps & Negative Results
- [What was NOT found that you expected]

### Follow-Up Leads Spawned
- Lead #X: [description]
...

### Infrastructure Recommendations
- [New data source discovered, with URL and access method]
- [Existing tool improvement identified]
- [New jurisdiction/registry to add]
```

## Context Management (CRITICAL)

**The #1 cause of session crashes is agent transcript bloat.** Follow these rules:

1. **Never call TaskOutput on completed agents.** Read their report files instead.
2. **Always use `run_in_background=true`** when launching agents.
3. **All searches use `--output [WORKDIR]/...`** — this keeps both the agent's AND your context lean.
4. **Never `cat` or `Read` full document text** unless you need a specific quote. Read the `--output` JSON selectively.
5. **Report files are disposable** — they live in `/tmp/` and don't persist across sessions.

## Tool Bug Reporting
If you encounter bugs in CLI tools (crashes, incorrect output, missing features), submit them to the infra queue:
`uv run python tools/infra_tracker.py add --title "Bug: <description>" --type tool_improvement --priority high --description "<details including the error traceback>"`

## Notes

- Launch all agents in a SINGLE message with multiple Agent tool calls — this maximizes parallelism
- Each agent should be `subagent_type: "general-purpose"` with `run_in_background: true`
- The orchestrator does NOT search sources directly — that's the agents' job
- Use the four-agent report contract by default. For simple targets, use fewer agents only after defining the exact expected report set.
- For complex targets, create follow-up waves rather than adding uncollected agents to the current four-report wave.
- Agents MUST record their findings via the CLI tools, not just report them as text
- **Agents write reports to `[WORKDIR]/report-agent-{a,b,c,d}.md`** — orchestrator reads these, NOT TaskOutput
- **Agents should be curious and proactive.** Don't just execute the search checklist mechanically — follow unexpected threads, investigate surprises, and identify infrastructure improvements. If a search reveals a data source we don't have, note it. If a tool could be extended to answer a question better, say so. The investigation platform should get stronger with every wave.
- **Agents do not build tools during the research wave.** They may verify a public endpoint and create a detailed infrastructure request; `/build-infra` is the single implementation owner.
