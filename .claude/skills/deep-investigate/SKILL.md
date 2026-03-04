---
name: deep-investigate
description: Orchestrated multi-source investigation using parallel sub-agents
user_invocable: true
---

# /deep-investigate

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Sub-agents document what they find. They do not theorize, speculate, or apply analytical frameworks. If a pattern is noticed, record the raw data and move on — pattern recognition is for Layer 2 analysis agents (`/generate-hunches`, `/analyze-network`, `/timeline-analysis`, `/systemic-analysis`, `/discover-frameworks`).

Launch an orchestrated investigation of a person, entity, or topic using parallel sub-agents that each cover a dedicated source category. This ensures comprehensive coverage — no source gets skipped because the agent "found enough" in the corpus.

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
- **Record negative results.** "Searched CourtListener for X, zero cases found" is a finding. Absence from authoritative sources is investigatively significant.
- **Record mundane facts.** Officer names, registered agent addresses, formation dates, filing numbers, EINs — even when boring. These become critical during cross-referencing.
- **Record baseline comparisons.** "GEO Group's 695% profit increase" means nothing without "vs. industry average of X%." Always seek the denominator.
- **Check ALL required sources for the target type** — not just the ones most likely to return results. See tool checklists in each agent prompt below.

## Architecture

You are the **orchestrator**. You do NOT search sources yourself. Instead you:

1. Assess the target and determine what's already known
2. **Build a research plan** — identify which sources are relevant and assign them to agents
3. Write focused prompts for 4 parallel sub-agents with explicit source mandates
4. Launch all 4 sub-agents simultaneously using the Task tool
5. Wait for all to complete
6. Synthesize their results — identify corroboration, contradictions, and gaps
7. Record final findings and spawn follow-up leads

### Research Planning Protocol

**Before writing any agent prompts**, create a source assignment matrix. This prevents agents from defaulting to web searches and ensures every relevant tool gets used.

**Step 1: Identify all relevant sources for this target.** Consider the target type:

| Target Type | Critical Sources (must check) |
|-------------|-------------------------------|
| **Person** | CourtListener, FEC, 990s, EDGAR, LittleSis, registries (as officer), FARA, lobbying, OpenSanctions, GDELT |
| **Corporation** | State registries (DE/NY/FL/CA/TX + incorporation state), EDGAR (10-K, proxy), USASpending, SAM.gov, CourtListener, lobbying, FARA, GLEIF |
| **Nonprofit** | ProPublica 990 (grants, officers, compensation), EDGAR, state registries, CourtListener, FEC (PAC affiliates) |
| **Government actor** | FEC, lobbying (post-government), FARA, CourtListener, LittleSis, EDGAR (financial disclosures) |
| **Financial entity** | EDGAR, GLEIF, DS10, ACRIS, UCC, registries, CourtListener, USASpending |

**Step 2: Assign sources to agents.** The default 4-agent split (corpus, corporate/financial, legal, network/OSINT) works well for single targets. For custom multi-target plans, ensure each source appears in at least one agent's mandate. Create a table:

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
.venv/bin/python3 tools/findings_tracker.py search "<TARGET>"

# Existing leads
.venv/bin/python3 tools/lead_tracker.py search "<TARGET>"

# Existing entity records
.venv/bin/python3 -c "
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

### 2. Launch 4 Parallel Sub-Agents

Use the Task tool to launch ALL FOUR agents simultaneously in a single message. Each agent gets:
- The target briefing
- Its specific source mandate
- Instructions to record findings via the CLI tools
- The reminder: "Zero results is investigatively valuable — record negative searches too"
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
  .venv/bin/python3 tools/<corpus_tool>.py search "[TARGET]" --limit 20 --output [WORKDIR]/a-<tool-name>.json

For tools that support sub-commands (entities, cooccurrence, emails, docs, triples), run those additional queries as well.

For EVERY document found, read the full text:
.venv/bin/python3 tools/query_doj.py efta EFTA_ID --text

Extract: dates, names, financial amounts, relationships, exact quotes.

RECORD findings using:
.venv/bin/python3 tools/findings_tracker.py add --target "[TARGET]" --type TYPE \
  --summary "..." --evidence EFTA_ID --claim-type direct_quote \
  --source-quote "EFTA_ID:exact quote" --sources doj_vol11 --confidence LEVEL

Record connections using:
.venv/bin/python3 tools/findings_tracker.py connect --person-a "..." --person-b "..." \
  --type TYPE --detail "..." --evidence EFTA_ID --confidence LEVEL

If zero results: record a finding noting the search scope and negative result — absence of evidence IS evidence when the corpus has 331K pages.

PROACTIVE SOURCE DISCOVERY:
As you search, be curious. If documents reference data sources we don't have tools for, or mention databases/registries/archives that could be queried, note them. For example:
- A document mentions a filing in a court we don't cover → note the court and docket
- An email references a foreign corporate registry entry → note the registry and entity
- A record mentions a dataset or database we haven't ingested → note what it is and where to get it
At the end of your investigation, list any SOURCE GAPS you identified and create infrastructure requests for valuable ones:
uv run python tools/infra_tracker.py add --title "Integrate [SOURCE]" --type new_source --description "Found during [TARGET] investigation. [Details]. URL: [URL]. Access: [METHOD]." --source-name "[SOURCE]" --priority medium --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

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

Use .venv/bin/python3 for all commands.
```

#### Agent B: Corporate, Financial & Property Records

**Sources**: Corporate Registry (FL/NY/NM/PA/UK/USVI), SEC EDGAR, NYC ACRIS, FEC, ProPublica 990, UCC, FAA, LDA Lobbying, FARA, GLEIF, OpenSanctions, DS10 Financial

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT if applicable]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL corporate, financial, property, and regulatory databases for this target. You are looking for: corporate registrations, SEC filings, property records, political donations, lobbying activity, foreign agent registrations, nonprofit filings, UCC liens, and aircraft registrations.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

CORPUS BASELINE (do these FIRST — every agent searches the document corpus):
Search corpus tools listed in the investigation profile. For each corpus tool, run:
  .venv/bin/python3 tools/<corpus_tool>.py search "[TARGET]" --limit 20 --output [WORKDIR]/b-<tool-name>.json
For EVERY document found, read the full text to extract: dates, names, financial amounts, relationships, exact quotes.

REQUIRED SEARCHES (do ALL of these — use --output on every search):

CORPORATE REGISTRIES:
1. .venv/bin/python3 tools/query_registry.py search "[TARGET]" --output [WORKDIR]/b-registry.json
2. .venv/bin/python3 tools/query_registry.py officers "[TARGET]" --output [WORKDIR]/b-officers.json
3. .venv/bin/python3 tools/query_registry.py address "[KNOWN_ADDRESS]" --output [WORKDIR]/b-addr.json  (if applicable)

SEC EDGAR:
4. .venv/bin/python3 tools/query_edgar.py search "[TARGET]" --size 20 --facets --output [WORKDIR]/b-edgar.json
5. .venv/bin/python3 tools/query_edgar.py lookup "[TARGET]"
6. .venv/bin/python3 tools/query_edgar.py search "[TARGET]" "[ASSOCIATED_ENTITY]" --size 10 --output [WORKDIR]/b-edgar2.json  (if applicable)

PROPERTY (NYC):
7. .venv/bin/python3 tools/query_acris.py party "[TARGET]" --output [WORKDIR]/b-acris.json

CAMPAIGN FINANCE:
8. .venv/bin/python3 tools/query_fec.py donor "[TARGET]" --limit 20 --output [WORKDIR]/b-fec.json
9. .venv/bin/python3 tools/query_fec.py employer "[TARGET]" --output [WORKDIR]/b-fec-emp.json  (if entity)

NONPROFITS:
10. .venv/bin/python3 tools/query_990.py search "[TARGET]" --output [WORKDIR]/b-990.json

LOBBYING:
11. .venv/bin/python3 tools/query_lobbying.py client "[TARGET]" --output [WORKDIR]/b-lda-client.json
12. .venv/bin/python3 tools/query_lobbying.py registrant "[TARGET]" --output [WORKDIR]/b-lda-reg.json
13. .venv/bin/python3 tools/query_lobbying.py lobbyist "[TARGET]" --output [WORKDIR]/b-lda-lob.json

FOREIGN AGENTS:
14. .venv/bin/python3 tools/query_fara.py search "[TARGET]" --output [WORKDIR]/b-fara.json

UCC FILINGS:
15. .venv/bin/python3 tools/query_registry.py ucc-search "[TARGET]" --output [WORKDIR]/b-ucc.json

FAA AIRCRAFT:
16. .venv/bin/python3 tools/ingest_faa.py search "[TARGET]"

GLEIF (corporate hierarchy — financial entities):
17. .venv/bin/python3 tools/query_gleif.py search "[TARGET]" --limit 10 --output [WORKDIR]/b-gleif.json
18. If LEI found: .venv/bin/python3 tools/query_gleif.py hierarchy <LEI> --output [WORKDIR]/b-gleif-hier.json

UK COMPANIES HOUSE (if API key configured):
19. .venv/bin/python3 tools/ingest_uk_companies_house.py search "[TARGET]" --limit 10
20. If found: .venv/bin/python3 tools/ingest_uk_companies_house.py officers <COMPANY_NUMBER>
21. If found: .venv/bin/python3 tools/ingest_uk_companies_house.py psc <COMPANY_NUMBER>

OPENSANCTIONS (PEP/sanctions check — if ingested):
22. .venv/bin/python3 tools/query_opensanctions.py search "[TARGET]" --limit 10 --output [WORKDIR]/b-sanctions.json

USVI CORPORATE REGISTRY:
23. .venv/bin/python3 tools/ingest_usvi.py search "[TARGET]"

DS10 DEUTSCHE BANK FINANCIAL RECORDS:
24. .venv/bin/python3 tools/parse_ds10_financials.py query --entity "[TARGET]"

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

If you find a data source that would immediately help AND it has a free, accessible API — you may build the tool yourself. Probe the endpoint first, confirm it works, then write the integration. Update CLAUDE.md and /search-all-sources after.

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

Use .venv/bin/python3 for all commands.
```

#### Agent C: Legal & Court Records

**Sources**: CourtListener (dockets, opinions, parties, judges), FARA (detailed review), LDA Lobbying (detailed review)

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT if applicable]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL legal and court databases for this target. You are looking for: federal litigation (as party, witness, or mentioned), state court cases, judicial opinions, regulatory actions, enforcement proceedings, FARA registrations, and lobbying disclosures.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

CORPUS BASELINE (do these FIRST — every agent searches the document corpus):
Search corpus tools listed in the investigation profile. For each corpus tool, run:
  .venv/bin/python3 tools/<corpus_tool>.py search "[TARGET]" --limit 20 --output [WORKDIR]/c-<tool-name>.json
For EVERY document found, read the full text to extract: dates, names, financial amounts, relationships, exact quotes.

REQUIRED SEARCHES (use --output on all):

COURTLISTENER (federal courts):
1. .venv/bin/python3 tools/query_courtlistener.py search "[TARGET]" --output [WORKDIR]/c-cl-search.json
2. .venv/bin/python3 tools/query_courtlistener.py party "[TARGET]"
3. .venv/bin/python3 tools/query_courtlistener.py cases "[TARGET]"
4. .venv/bin/python3 tools/query_courtlistener.py opinions "[TARGET]" --limit 10
5. If any dockets found: .venv/bin/python3 tools/query_courtlistener.py docket <DOCKET_ID> --output [WORKDIR]/c-cl-docket.json

For each case found:
- What is the nature of the case?
- Who are the other parties?
- What is the timeline?
- Are any investigation-associated persons or entities involved?
- What do the opinions/rulings reveal?

FARA (deep check):
6. .venv/bin/python3 tools/query_fara.py search "[TARGET]" --output [WORKDIR]/c-fara.json
7. If found: .venv/bin/python3 tools/query_fara.py detail <REG_NUM> --output [WORKDIR]/c-fara-detail.json

LOBBYING (deep check):
8. .venv/bin/python3 tools/query_lobbying.py lobbyist "[TARGET]" --output [WORKDIR]/c-lda-lob.json
9. .venv/bin/python3 tools/query_lobbying.py client "[TARGET]" --output [WORKDIR]/c-lda-client.json
10. If filings found: .venv/bin/python3 tools/query_lobbying.py filings --client "[TARGET]" --output [WORKDIR]/c-lda-filings.json

INVESTIGATION REPORTS (ingested PDFs):
11. .venv/bin/python3 tools/query_investigations.py search "[TARGET]" --limit 10 --output [WORKDIR]/c-inv.json

RECORD all findings using the findings_tracker.py CLI. CRITICAL: Always include --sources with the data source name(s) (e.g., --sources courtlistener fara lobbying). Record connections between the target and any investigation-network persons discovered in litigation.

Zero court results for a person who should have them (e.g., a practicing attorney) is notable — record it.

PROACTIVE SOURCE DISCOVERY:
As you search court records, look for:
- Court systems we don't currently query (state courts, bankruptcy courts, immigration courts, foreign proceedings)
- Specific dockets referenced in documents that should be ingested (PACER dockets, SDNY exhibits)
- Legal databases that would help (state bar records, judicial disclosure databases, arbitration records)
- Government investigation reports or hearing transcripts not yet in our investigations.db
If you find a new court system or legal database with a public API, create an infrastructure request. If it's simple enough, build the tool:
uv run python tools/infra_tracker.py add --title "Integrate [COURT/DATABASE]" --type new_source --description "Discovered during [TARGET] investigation. [Details, URL, access method]." --source-name "[SOURCE]" --priority medium --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

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

Use .venv/bin/python3 for all commands.
```

#### Agent D: Network, OSINT & Open Web

**Sources**: LittleSis, ICIJ/Aleph, Shodan, crt.sh, Wayback Machine, URLScan.io, WebSearch, WebFetch, GDELT, plus any investigation-specific OSINT tools from the profile

**Prompt template**:
```
You are investigating [TARGET]. [THREAD CONTEXT if applicable]

TARGET BRIEFING: [2-3 sentences of context]

ALREADY KNOWN: [List existing findings or "None"]

YOUR MANDATE: Search ALL network mapping, offshore leak, and open web sources for this target. You are looking for: pre-mapped relationships, offshore entities, public reporting, news coverage, and biographical information that provides context.

IMPORTANT: Use --output on ALL search commands to keep context lean. Read the JSON files when you need details.

CORPUS BASELINE (do these FIRST — every agent searches the document corpus):
Search corpus tools listed in the investigation profile. For each corpus tool, run:
  .venv/bin/python3 tools/<corpus_tool>.py search "[TARGET]" --limit 20 --output [WORKDIR]/d-<tool-name>.json
For EVERY document found, read the full text to extract: dates, names, financial amounts, relationships, exact quotes.

REQUIRED SEARCHES (use --output on all):

LITTLESIS (relationship mapping):
1. .venv/bin/python3 tools/query_littlesis.py search "[TARGET]" --output [WORKDIR]/d-ls-search.json
2. If found: .venv/bin/python3 tools/query_littlesis.py entity <ID> --output [WORKDIR]/d-ls-entity.json
3. If found: .venv/bin/python3 tools/query_littlesis.py relationships <ID> --limit 50 --output [WORKDIR]/d-ls-rels.json

OCCRP ALEPH (corporate registries, leaks, sanctions):
4. .venv/bin/python3 tools/query_aleph.py search "[TARGET]" --schema Person --output [WORKDIR]/d-aleph-person.json
5. .venv/bin/python3 tools/query_aleph.py search "[TARGET]" --schema Company --output [WORKDIR]/d-aleph-company.json
6. If found: .venv/bin/python3 tools/query_aleph.py expand <ENTITY_ID> --output [WORKDIR]/d-aleph-expand.json

ICIJ OFFSHORE LEAKS (if Neo4j running):
7. .venv/bin/python3 tools/query_icij.py search "[TARGET]" --output [WORKDIR]/d-icij.json

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
14. .venv/bin/python3 tools/query_shodan.py domain "[TARGET_DOMAIN]" --output [WORKDIR]/d-shodan-domain.json  (if domain known)
15. .venv/bin/python3 tools/query_shodan.py search "ssl:[TARGET_DOMAIN]" --output [WORKDIR]/d-shodan-ssl.json  (if domain known)
16. .venv/bin/python3 tools/query_shodan.py host [TARGET_IP] --output [WORKDIR]/d-shodan-host.json  (if IP known)
17. .venv/bin/python3 tools/query_crtsh.py search "[TARGET_DOMAIN]" --output [WORKDIR]/d-crtsh.json  (cert transparency — subdomain enum)
18. .venv/bin/python3 tools/query_crtsh.py timeline "[TARGET_DOMAIN]" --output [WORKDIR]/d-crtsh-timeline.json
19. .venv/bin/python3 tools/query_wayback.py timeline "[TARGET_DOMAIN]" --output [WORKDIR]/d-wayback.json  (historical snapshots)
20. .venv/bin/python3 tools/query_wayback.py first "[TARGET_DOMAIN]" --output [WORKDIR]/d-wayback-first.json
21. .venv/bin/python3 tools/query_urlscan.py search "domain:[TARGET_DOMAIN]" --output [WORKDIR]/d-urlscan.json  (tech stack, linked domains)

GDELT (global news):
22. .venv/bin/python3 tools/query_gdelt.py articles "[TARGET]" --limit 30 --output [WORKDIR]/d-gdelt-art.json
23. .venv/bin/python3 tools/query_gdelt.py context "[TARGET]" --limit 20 --output [WORKDIR]/d-gdelt-ctx.json

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
3. If it's a free API with clear documentation, you may build the integration tool yourself — probe first, confirm it works, then write `tools/query_[source].py` or `tools/ingest_[source].py`

uv run python tools/infra_tracker.py add --title "Integrate [SOURCE]" --type new_source --description "Found during [TARGET] web research. URL: [URL]. Data: [WHAT]. Access: [HOW]. Value: [WHY]." --source-name "[SOURCE]" --source-url "[URL]" --priority [high/medium] --discovered-by "agent:deep-investigate" --discovered-during "[TARGET] investigation"

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

Use .venv/bin/python3 for all commands.
```

### 3. Wait for Agents and Read Reports

**DO NOT use TaskOutput to retrieve agent results.** Agent transcripts are 10-50MB and will bloat context.

Instead, agents write structured reports to `[WORKDIR]/report-agent-{a,b,c,d}.md`. Poll for completion, then read the reports:

```
# Launch all 4 agents with run_in_background=true
# Each agent's prompt instructs it to write [WORKDIR]/report-agent-{a,b,c,d}.md

# Poll for completion (check if report files exist)
Bash: ls -la [WORKDIR]/report-agent-*.md 2>/dev/null | wc -l
# Repeat every 30s until count = 4

# Once all reports exist, read them:
Read("[WORKDIR]/report-agent-a.md")
Read("[WORKDIR]/report-agent-b.md")
Read("[WORKDIR]/report-agent-c.md")
Read("[WORKDIR]/report-agent-d.md")
```

Each report is ~2KB (vs 25MB transcript). If you need deeper detail on a specific finding, read the agent's `--output` JSON files (e.g., `[WORKDIR]/a-doj.json`).

### 4. Synthesize Results

**Note: The orchestrator's synthesis step is the ONE place in this skill where limited Layer 2 thinking is appropriate.** Sub-agents (Layer 1) gathered facts. The orchestrator now identifies what the combined facts suggest — but keeps interpretation clearly labeled as `claim_type=synthesis` with `confidence=medium`.

After reading all 4 report files:

1. **Count findings**: How many did each agent produce?
2. **Identify corroboration**: Did multiple agents find the same facts from independent sources? (e.g., corpus email confirms a corporate filing)
3. **Identify contradictions**: Do any findings conflict?
4. **Identify gaps**: Did any agent return zero results from sources that should have data?
5. **Map the network**: Who does this target connect to? Draw the relationship map.
6. **Collect infrastructure recommendations**: What new data sources, tools, or tool improvements did agents identify? Consolidate into actionable items.
7. **Drill down selectively**: If a report mentions a critical finding, read the specific `--output` JSON for details. Do NOT read all JSON files — only the ones relevant to synthesis.
8. **Identify the Character Entry Point**: What aspect of this target's role illuminates the network's design? Every person is a lens onto a different part of the machine — what does THIS person make visible that would otherwise remain hidden? (e.g., a trust administrator reveals the USVI trust architecture; a compliance officer reveals the SAR waterfall)
9. **Note the Narrative Potential**: What's the most counterintuitive finding? What single fact would most surprise an intelligent person in finance/law/compliance? This is the seed for a future article hook. Record it in the synthesis finding.
10. **Flag Missing Documents**: What records should exist but don't? Missing SARs, absent emails in a timeline, corporate filings that should be present but aren't. Absence of expected records is itself evidence — record it as a finding.
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
.venv/bin/python3 tools/findings_tracker.py add --target "[TARGET]" --type intelligence \
  --summary "SYNTHESIS: [what the combined evidence shows]" \
  --evidence [ALL_EVIDENCE_REFS] --claim-type synthesis \
  --source-quote "[REF]:key supporting fact" --sources analysis_run --confidence medium
```

### 6. Spawn Follow-Up Leads

Create leads for:
- New persons discovered across multiple agents
- Entities that need their own `/deep-investigate`
- Financial trails requiring further tracing
- Sources that weren't available (e.g., ICIJ Neo4j wasn't running)
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

- Launch all 4 agents in a SINGLE message with 4 Task tool calls — this maximizes parallelism
- Each agent should be `subagent_type: "general-purpose"` with `run_in_background: true`
- The orchestrator does NOT search sources directly — that's the agents' job
- If the target is clearly only a person OR only an entity, you can still run all 4 agents — some will just return fewer results
- For very simple targets where you're confident only 1-2 source categories are relevant, you can skip agents that clearly won't help (e.g., FAA for a French lawyer). But err on the side of launching all 4.
- Agents MUST record their findings via the CLI tools, not just report them as text
- **Agents write reports to `[WORKDIR]/report-agent-{a,b,c,d}.md`** — orchestrator reads these, NOT TaskOutput
- **Agents should be curious and proactive.** Don't just execute the search checklist mechanically — follow unexpected threads, investigate surprises, and identify infrastructure improvements. If a search reveals a data source we don't have, note it. If a tool could be extended to answer a question better, say so. The investigation platform should get stronger with every wave.
- **Agents may build tools.** If an agent discovers a free, accessible data source during investigation and it would help answer the current question, the agent can build the integration tool (probe-before-code applies). Update CLAUDE.md and /search-all-sources after building.
