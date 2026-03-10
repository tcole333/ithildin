---
name: deep-investigate
description: Orchestrated multi-source investigation using parallel sub-agents
user_invocable: true
---

# /deep-investigate

Adaptive multi-wave investigation using parallel sub-agents. The orchestrator reasons about agent allocation based on actual data volume, investigation context, and target type — no fixed templates.

## Arguments

- Required: target name or topic (e.g., `/deep-investigate Ron Soffer`, `/deep-investigate Barkmere Group Ltd`)
- Optional context after the name: `/deep-investigate Ron Soffer — French/Israeli lawyer referenced in SoftBank caper`

## Architecture: 5 Phases

```
Phase 0: Recon Probe (~30 seconds)
    ↓ source heat map + existing knowledge
Phase 1: Planning & Agent Design (orchestrator reasons about strategy)
    ↓ agent plan with specific scopes + rationale
Phase 2: Research Wave 1 (focused Sonnet agents, each with narrow scope)
    ↓ reports + findings + entity registrations
Phase 3: Adaptive Wave 2+ (designed from Wave 1 findings)
    ↓ reports + findings
Phase 4: Synthesis (read all reports, record synthesis, auto_leads, graph)
```

## Phase 0: Recon

### 0a. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 0b. Load Investigation Context

```bash
uv run python tools/investigation_context.py show
```

### 0c. Run Recon Probe

```bash
uv run python tools/recon_probe.py probe "TARGET" --output $WORKDIR/recon.json
```

Read the output. This shows which sources have data and how much.

### 0d. Check Existing Knowledge

```bash
uv run python tools/findings_tracker.py search "TARGET" --output $WORKDIR/existing-findings.json
uv run python tools/lead_tracker.py search "TARGET" --output $WORKDIR/existing-leads.json
uv run python tools/entity_tracker.py lookup --name "TARGET"
```

## Phase 1: Planning & Agent Design

**This is where the orchestrator thinks.** You have the recon heat map, existing knowledge, and investigation context. Now reason about:

### Investigation Type

Different strategies for different targets:

- **Person deep-dive**: Career, finances, legal, network. Sources depend on role — government official (FEC, lobbying, ProPublica), corporate exec (EDGAR, registries, SAM), nonprofit figure (990s, grants).
- **Entity trace**: Corporate chain, officers, addresses, filings. Heavy on registries, EDGAR, SAM, GLEIF.
- **Theory/connection investigation**: Multiple targets, need to establish links. Separate agents per target with synthesis looking for overlap.
- **Financial thread**: Follow money — FEC, 990s, USASpending, EDGAR, ACRIS, lobbying.
- **Geographic/jurisdictional**: Registry traces in specific jurisdictions, international tools, infrastructure recon.

### Tool Relevance

Reason about which sources make sense for THIS target:

- What is this person/entity known for? (determines which sources are high-priority)
- What does the recon heat map show? (focus on rich sources, skip zero-hit sources)
- Are there investigation-specific corpus tools that apply?
- Is infrastructure recon relevant? (only if there's a domain/digital footprint)
- What investigation are we in? (the active profile shapes which tools matter)

### Agent Design

Based on the data volume and diversity, decide:

- **How many agents** — more agents for more diverse data; fewer for concentrated sources
- **Each agent's narrow scope** — a clear, bounded mandate
- **Which source modules each agent reads** — reference `docs/sources/<module>.md`
- **Specific queries to run** — informed by recon counts so agents know what to expect
- **Batching** — if a single source has very high volume, dedicate an agent to it

**Write the plan** to `$WORKDIR/agent-plan.md` before launching agents.

### Agent Count Guidelines (reasoning inputs, not rules)

- 2-3 sources with data → 2 agents may suffice
- 5-10 sources with data across different categories → 3-5 agents
- 15+ sources with data → 5-7 agents, each owning 2-3 related sources
- A single source with 50+ results → may deserve its own agent
- Corpus tools always get at least one agent if they have hits

## Phase 2: Launch Wave 1 Agents

Each agent gets a prompt that includes:

1. **Preamble reference**: "Read `docs/sources/_preamble.md` for evidence standards, entity registration, and report format."
2. **Target briefing**: 2-3 sentences of context from the orchestrator's assessment
3. **Existing knowledge**: What's already in the DB (avoid duplication)
4. **Narrow scope assignment**: Exactly which sources to search and what to look for
5. **Source module references**: "Read `docs/sources/courtlistener.md` for protocol, then execute."
6. **Recon counts**: "CourtListener has ~12 cases for this target" — agents know what to expect
7. **WORKDIR and output prefix**: `$WORKDIR` path and file naming convention
8. **Report file path**: `$WORKDIR/report-wave1-<agent-name>.md`

### Agent Prompt Template

```
Read docs/sources/_preamble.md for evidence standards, entity registration, and report format.

TARGET: [NAME]
BRIEFING: [2-3 sentences of context]
EXISTING KNOWLEDGE: [summary or "None"]
INVESTIGATION PROFILE: [key details from profile]

YOUR SCOPE: [precise description of what this agent investigates]

SOURCE MODULES (read these for protocol):
- docs/sources/[module1].md
- docs/sources/[module2].md

EXPECTED DATA VOLUME (from recon):
- [source1]: ~[count] results
- [source2]: ~[count] results

WORKDIR: [actual path]
OUTPUT PREFIX: [e.g., "w1a" for wave 1, agent a]
REPORT: Write to [WORKDIR]/report-wave1-[agent-name].md

CRITICAL: Be thorough within your scope. Document everything. Register every
entity and person-role. Record negative results. Your job is to build the
knowledge graph comprehensively within your assigned sources.
```

### Launch

Launch all Wave 1 agents simultaneously:
- `subagent_type: "general-purpose"`
- `model: "sonnet"` — research agents have well-scoped tasks with precise source module instructions
- `run_in_background: true`

### Wait for Completion

**DO NOT use TaskOutput to retrieve agent results.** Transcripts are 10-50MB.

Agents write reports to `$WORKDIR/report-wave1-*.md`. Poll for completion:
```bash
ls -la $WORKDIR/report-wave1-*.md 2>/dev/null | wc -l
```

Once all reports exist, read them with the Read tool. Each report is ~2KB.

**Liveness checks**: If an agent has no report after 5 minutes, check `TaskOutput` with `block=false`. If still active (output growing), let it continue. If hung, stop it and note the gap.

## Phase 3: Decision Point & Wave 2+

The orchestrator reads all Wave 1 reports and reasons about what to do next:

- What new persons/entities were discovered that need their own investigation?
- What contradictions need resolution?
- What sources turned out richer than expected and need deeper reading?
- What cross-references between Wave 1 findings suggest new lines of inquiry?
- Are there specific documents (EDGAR filings, court dockets, 990 schedules) that need detailed reading?

**Design Wave 2 agents from this analysis.** Wave 2 agents are typically more targeted:
- "Read these 5 specific EDGAR filings and extract officer names"
- "Trace this newly discovered company through 3 state registries"
- "Cross-reference this lobbyist against all corpus tools"

Additional waves if needed — iterate until diminishing returns.

Wave 2+ agents also use `model: "sonnet"` unless the task requires heavy reasoning.

## Phase 4: Synthesis

The orchestrator (Opus) handles synthesis:

### 4a. Read All Reports

Read all `$WORKDIR/report-*.md` files across all waves.

### 4b. Analyze

1. **Count findings**: How many did each agent produce?
2. **Corroboration**: Multiple agents finding the same facts from independent sources
3. **Contradictions**: Conflicting findings that need resolution
4. **Gaps**: Sources that should have data but returned zero results
5. **Network map**: Who does this target connect to?
6. **Character entry point**: What aspect of this target illuminates the network's design?
7. **Narrative potential**: Most counterintuitive finding — the seed for a future article
8. **Missing documents**: Records that should exist but don't (absent SARs, email gaps)
9. **Tool coverage check**: Did agents actually use their full source list?

### 4c. Record Synthesis Finding

If the combined evidence tells a larger story:
```bash
uv run python tools/findings_tracker.py add --target "TARGET" --type intelligence \
  --summary "SYNTHESIS: [what the combined evidence shows]" \
  --evidence [ALL_EVIDENCE_REFS] --claim-type synthesis \
  --source-quote "[REF]:key supporting fact" --sources analysis_run --confidence medium
```

### 4d. Run Auto-Leads

```bash
uv run python tools/auto_leads.py run
```

### 4e. Graph Analysis

```bash
uv run python tools/graph_tools.py neighborhood "TARGET" --depth 2
```

### 4f. Ingest Agent Learnings

```bash
for report in $WORKDIR/report-*.md; do
    uv run python tools/methodology_tracker.py ingest-report "$report" --skill deep-investigate
done
```

### 4g. Complete the Originating Lead

If this investigation was launched from a lead:
```bash
uv run python tools/lead_tracker.py complete LEAD_ID --findings "Summary of what was found"
```

### 4h. Spawn Follow-Up Leads

Create leads for:
- New persons discovered across multiple agents
- Entities that need their own investigation
- Financial trails requiring tracing
- Sources that weren't available (e.g., ICIJ Neo4j wasn't running)
- Hypotheses generated by synthesis
- Infrastructure requests: `uv run python tools/infra_tracker.py add ...`

## Present Summary to User

```
## /deep-investigate [TARGET] — Results

### Target Profile
[1-2 sentences]

### Recon Summary
[Sources probed, data distribution]

### Agent Deployment
| Wave | Agent | Scope | Findings | Entities |
|------|-------|-------|----------|----------|
| 1 | [name] | [scope] | [count] | [count] |
| ... | ... | ... | ... | ... |

### Key Findings
1. [Most significant]
2. [Second most significant]
...

### Corroboration
- [Fact confirmed by 2+ independent source types]

### Gaps & Negative Results
- [What was NOT found that you expected]

### Follow-Up Leads Spawned
- Lead #X: [description]

### Infrastructure Recommendations
- [New data sources discovered]
```

## Context Management (CRITICAL)

1. **Never call TaskOutput on completed agents.** Read report files instead.
2. **Always use `run_in_background=true`** when launching agents.
3. **All searches use `--output $WORKDIR/...`** — keeps both agent and orchestrator context lean.
4. **Report files are disposable** — they live in `/tmp/` and don't persist.

## Notes

- Launch Wave 1 agents in a SINGLE message with multiple Task tool calls
- Each agent: `subagent_type: "general-purpose"`, `model: "sonnet"`, `run_in_background: true`
- The orchestrator does NOT search sources directly — that's the agents' job
- Agents MUST record findings via CLI tools, not just report text
- **Agents write reports to `$WORKDIR/report-wave1-*.md`** — orchestrator reads these
- Agents may build tools if they discover a free accessible data source (probe-before-code applies)
