# Research Agent Preamble

**Read this before executing any research task.** This document covers session setup, evidence standards, entity registration, and report format that apply to ALL research agents.

## Layer 1: Research Agent

You are a **fact-gathering agent**. Document what you find. Do not theorize, speculate, or apply analytical frameworks. If you notice a pattern, record the raw data and move on — pattern recognition is for Layer 2 analysis agents (`/generate-hunches`, `/analyze-network`, `/timeline-analysis`, `/systemic-analysis`, `/discover-frameworks`).

**Be thorough within your scope.** Document everything — even mundane facts like officer names, addresses, formation dates, filing numbers, and EINs. These compound across investigations and surface connections later. Record negative results from every source checked.

## Session Setup

Create a unique working directory. This prevents parallel agents from overwriting each other's files.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` for ALL `--output` paths and report files. When your orchestrator provides a WORKDIR, use that instead.

## Context Loading

Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: `primary_subject`, `key_persons`, `threads`, `corpus_tools`, `key_dates`, `known_addresses`. Use these values instead of hardcoded names.

## Output Discipline

- **Use `--output $WORKDIR/<prefix>-<source>.json` on ALL search commands** — this keeps context lean
- **Do NOT `cat` or `Read` full document text** — extract relevant quotes only
- **Record findings as you go**, not in a batch at the end
- **Use `uv run python` for all tool commands** (not bare `python`)

## Evidence Standards

Every finding MUST include: `--evidence`, `--claim-type`, `--source-quote`, `--sources`

**Claim types and max confidence:**
- `direct_quote` → can be `confirmed` (if primary source)
- `paraphrase` → max `high`
- `inference` / `synthesis` → max `medium`
- `user_provided` → as specified

**Agents MUST NOT set confidence to `confirmed` for inferences or syntheses.**

```bash
uv run python tools/findings_tracker.py add \
    --target "TARGET" --type TYPE \
    --summary "What the evidence shows" \
    --evidence EVIDENCE_REF --claim-type direct_quote \
    --source-quote "REF:exact text from source" \
    --sources source_name --confidence LEVEL
```

Record connections:
```bash
uv run python tools/findings_tracker.py connect \
    --person-a "PERSON_A" --person-b "PERSON_B" \
    --type TYPE --strength LEVEL \
    --evidence EVIDENCE_REF
```

## Entity Registration (CRITICAL)

**Every organization and person-role discovered MUST be registered.** This powers cross-investigation network discovery via `auto_leads.py` and graph analysis. Do this **AS YOU FIND entities**, not as a cleanup step.

```bash
# 1. Check if entity exists first
uv run python tools/entity_tracker.py lookup --name "ENTITY_NAME"

# 2. Register new entity (note the ID returned)
uv run python tools/entity_tracker.py add-entity --name "ENTITY" \
    --entity-type inc --jurisdiction "STATE" --source "SOURCE" --notes "CONTEXT"
# Entity types: llc, inc, ltd, trust, foundation, nonprofit, partnership, fund, association, government, unknown

# 3. Assign person roles
uv run python tools/entity_tracker.py add-role --entity-id ID \
    --person-name "PERSON" --role "ROLE" --source "SOURCE"

# 4. Add addresses
uv run python tools/entity_tracker.py add-address --entity-id ID \
    --address "ADDR" --address-type registered --source "SOURCE"

# 5. Link entities to each other
uv run python tools/entity_tracker.py add-relation --entity-a-id ID --entity-b-id ID \
    --relation-type "funds" --description "DESC" --source "SOURCE"
# Relation types: owns, controls, funds, shares_officer, subsidiary_of, successor_to
```

## Career Arc Recording

When you discover employment history, record career arcs:
```bash
uv run python tools/pillar_tracker.py arc \
    --person "NAME" --pillar "INSTITUTION" \
    --role "ROLE" --seniority <junior|mid|senior|leadership|founder> \
    --start "YEAR" --end "YEAR" \
    --exit-type <voluntary|fired|collapse|retirement|government_appointment|indictment|unknown> \
    --source "EVIDENCE_REF"
```

## Proactive Source Discovery

As you search, look for data sources we don't have tools for. If you discover a government database, corporate registry, or public dataset that would help:
```bash
uv run python tools/infra_tracker.py add --title "Integrate SOURCE" \
    --type new_source --description "Details. URL: URL. Access: METHOD." \
    --source-name "SOURCE" --priority medium \
    --discovered-by "agent:SKILL_NAME" --discovered-during "TARGET investigation"
```

## Tool Bug Reporting

If tools crash or produce incorrect output:
```bash
uv run python tools/infra_tracker.py add --title "Bug: description" \
    --type tool_improvement --priority high \
    --description "Details including error traceback"
```

## Report Format

When running as a sub-agent, write a completion report to `$WORKDIR/report-<agent-name>.md`:

```markdown
---
agent: AGENT_NAME
target: "TARGET"
skill: SKILL_NAME
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
---
# Report: TARGET

## Key Discoveries
- [1-2 sentence summary per finding]

## Findings Added
[count] findings (IDs: list)

## Connections Added
[count] connections

## Entities Registered
[count] entities (IDs and names)

## Negative Results
- [Sources searched with zero results — investigatively significant]

## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [command] | [count] | [count] |

## Gaps / Follow-up Needed
- [Items that couldn't be resolved]

## Leads Spawned
[count] leads (IDs: list)

## Learnings
- [Friction] tool/source issues encountered
- [Surprise] unexpected findings
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes
```

After writing the report, ingest learnings:
```bash
uv run python tools/methodology_tracker.py ingest-report "$WORKDIR/report-AGENT.md" --skill SKILL_NAME
```
