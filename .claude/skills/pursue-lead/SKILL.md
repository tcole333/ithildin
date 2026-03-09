---
name: pursue-lead
description: Pick up an open lead from investigation.db and investigate it to completion
user_invocable: true
---

# /pursue-lead

**LAYER 1: RESEARCH AGENT** — Read `docs/sources/_preamble.md` for evidence standards, entity registration, and report format.

Claim and investigate the next highest-priority open lead. Operates fully autonomously.

## Arguments

- Optional lead ID: `/pursue-lead 42` to pursue a specific lead
- No arguments: automatically picks the highest-priority open lead

### Context Loading
```bash
uv run python tools/investigation_context.py show
```

## Process

### 0. Session Setup
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Select Lead

```bash
# Auto-select and claim (prevents race conditions):
python tools/lead_tracker.py claim-next
# Or by category/thread:
python tools/lead_tracker.py claim-next --category person --thread-id 1
# Or specific lead:
python tools/lead_tracker.py claim <ID>
```

### 2. Classify Investigation Type

Read the lead's description and category:

- **person** → Run `/investigate-person` workflow
- **entity** → Run `/trace-entity` workflow
- **financial** → Focus on financial sources
- **document** → Focus on locating specific documents
- **digital** → Focus on digital footprint
- **connection** → Focus on tracing relationship between entities

### 3. Check Search Log

```python
from tools.lead_tracker import check_searched
prior = check_searched("target-name", "source_name")
```

### 4. Investigate Using Source Modules

**Reason about which sources are relevant for this lead type and target.** Don't mechanically check every source — think about what will answer the lead's question.

Read the relevant source modules for protocol:

| Lead Type | Primary Source Modules |
|-----------|----------------------|
| Person | `corpus.md`, `courtlistener.md`, `fec.md`, `990.md`, `edgar.md`, `littlesis.md`, `registry.md`, `lobbying.md`, `sanctions.md`, `gdelt-web.md` |
| Entity | `corpus.md`, `registry.md`, `edgar.md`, `990.md`, `usaspending.md`, `courtlistener.md`, `gleif-ds10.md`, `lobbying.md`, `sanctions.md` |
| Financial | `corpus.md`, `edgar.md`, `990.md`, `fec.md`, `usaspending.md`, `acris-ucc-property.md`, `gleif-ds10.md`, `courtlistener.md` |

**Do not skip sources because you "found enough" elsewhere.** Check every relevant source and record the result (including zero-result searches).

### 5. Record Findings

See `docs/sources/_preamble.md` for evidence standards, entity registration, and career arc recording.

**For each finding, note its narrative potential:**
- Infrastructure reveal? (Shows an invisible mechanism)
- Counterintuitive fact? (Contradicts assumptions)
- Missing document? (What should exist but doesn't)
- Concrete-first anchor? (Vivid instance for explaining a broader pattern)

**When completing a lead**, identify the single most article-worthy finding.

### 6. Spawn Follow-Up Leads

```bash
python tools/lead_tracker.py add \
    --title "Investigate newly discovered connection" \
    --category person --priority high \
    --source "agent:pursue-lead" --target "NAME" \
    --evidence EVIDENCE_REF --related PARENT_LEAD_ID
```

### 7. Complete the Lead

```bash
python tools/lead_tracker.py complete <ID> --findings "Summary"
# Or if dead end:
python tools/lead_tracker.py dead-end <ID> "Explanation"
# Or if blocked:
python tools/lead_tracker.py block <ID> "Reason"
```

## Investigative Mindset

**Read `research/INVESTIGATIVE_METHODOLOGY.md` if you haven't already.**

1. **Form hypotheses first.** What do you expect to find? What would confirm/refute?
2. **Simulate the person.** What role does this target play? What are their incentives?
3. **Check the timeline.** What else was happening when this event occurred?
4. **Think about what's missing.** Gaps may be more significant than what you find.
5. **Follow the incentive structure.** Money flows reveal truth.
6. **Try alternate search terms.** Transliterations, maiden names, coded language.

### Thread Awareness

- **Do NOT close a lead because you didn't find direct primary subject connections.** Follow the thread.
- If the lead has a `thread_id`, assign new findings to the same thread.
- If you discover something relevant to a different thread, create a new lead in that thread.

## Context Management

This skill runs as a **standalone command in its own CC instance**:
```
Terminal 1: claude → /pursue-lead
Terminal 2: claude → /pursue-lead
Terminal 3: claude → /pursue-lead
```
All instances share `investigation.db` (WAL mode).

### Report File (when running as sub-agent)

Write to `$WORKDIR/report-lead-<LEAD_ID>.md` using the format in `docs/sources/_preamble.md`.

After writing:
```bash
uv run python tools/methodology_tracker.py ingest-report "$WORKDIR/report-lead-<LEAD_ID>.md" --skill pursue-lead --lead-id <LEAD_ID>
```
