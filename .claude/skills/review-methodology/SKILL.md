---
name: review-methodology
description: Review operational learnings and propose methodology improvements
user_invocable: true
---

# /review-methodology

Analyze accumulated methodology observations from investigation agents. Detect patterns, cross-reference with infrastructure requests and methodology docs, and propose specific improvements. **Never auto-applies changes** — presents proposals for human review.

## Arguments

- No arguments: full review of all open observations
- `--category friction`: focus on a specific category

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Gather Current State

```bash
# Overall stats
uv run python tools/methodology_tracker.py stats

# All open observations
uv run python tools/methodology_tracker.py list --status open --limit 100 --output $WORKDIR/open-obs.json

# All acknowledged observations
uv run python tools/methodology_tracker.py list --status acknowledged --limit 100 --output $WORKDIR/ack-obs.json

# Detected patterns
uv run python tools/methodology_tracker.py patterns --min-count 2 --output $WORKDIR/patterns.json

# Related infra requests (open tool issues)
uv run python tools/infra_tracker.py list --status open --type tool_improvement --output $WORKDIR/infra-tools.json
uv run python tools/infra_tracker.py list --status open --type tool_fix --output $WORKDIR/infra-fixes.json
```

### 2. Read Context Documents

Read the files that observations may relate to:

```bash
# Current methodology doc
Read: research/INVESTIGATIVE_METHODOLOGY.md

# Tool reference (check for undocumented tools mentioned in friction)
Read: docs/TOOL_REFERENCE.md

# CLAUDE.md (check tool table completeness)
Read: CLAUDE.md
```

### 3. Analyze Observations

For each category of open observations:

**Friction** — Tool and source issues
- Group by tool name (extract from description)
- Cross-reference with open infra_requests — is there already a ticket?
- If no ticket exists for a recurring friction point, draft an infra request
- Check if the tool's documentation in TOOL_REFERENCE.md covers the workaround

**Surprise** — Unexpected findings
- Do any surprises suggest new investigation hypotheses?
- Are there surprises that contradict existing methodology assumptions?
- Should any be promoted to investigation leads?

**Methodology** — Process insights
- Does INVESTIGATIVE_METHODOLOGY.md already cover this insight?
- If not, draft a specific addition (exact text, exact section)
- Are insights consistent with each other or contradictory?

**Process gap** — Missing infrastructure
- Cross-reference with infra_tracker — is the gap already tracked?
- If not, draft an infra request with specifics
- Prioritize gaps that appear in multiple observations

**Source quality** — Data source notes
- Check source_reliability table for existing entries
- Draft source_reliability updates for new source assessments
- Note any sources that agents consistently flag as unreliable

### 3a. Map Documented Failures

Pull recent `corrections` rows and disputed or retracted findings. Map each incident to an entry in `research/KNOWN_FAILURE_MODES.md`; when none fits, propose a new catalog entry with the incident, named bias, corrective discipline, and reviewer question.

### 4. Draft Proposals

For each actionable pattern, draft a specific proposal:

#### Methodology Doc Changes
```
PROPOSAL: Add to INVESTIGATIVE_METHODOLOGY.md, Section X
---
[Exact text to add]
---
Justification: [N] observations from [skills] support this insight.
Observation IDs: [list]
```

#### Infrastructure Requests
```
PROPOSAL: Create infra request
Title: [specific title]
Type: tool_improvement | tool_fix | new_feature
Description: [details]
Priority: [level]
Related observations: [IDs]
```

#### Source Reliability Updates
```
PROPOSAL: Update source_reliability
Source: [name]
Assessment: [notes]
Related observations: [IDs]
```

#### Tool Documentation Updates
```
PROPOSAL: Update TOOL_REFERENCE.md
Section: [tool name]
Change: [what to add/modify]
Related observations: [IDs]
```

### 5. Present to Human

Format all proposals in a clear summary:

```markdown
## /review-methodology — Results

### Statistics
- Total open observations: X
- Patterns detected: Y
- Proposals drafted: Z

### Friction Patterns
[Group by tool/source with counts]

### Proposed Changes
1. **[Type]**: [Brief description]
   - Observations: #1, #2, #3
   - [Draft or summary]

2. **[Type]**: [Brief description]
   ...

### Observations to Dismiss
- #X: [reason — duplicate of #Y, or no longer relevant]

### Observations Needing Context
- #X: [what additional information would help resolve this]
```

### 6. Apply Approved Changes

**Only after human approval:**

For each approved proposal:
1. Make the change (edit doc, create infra request, update source_reliability)
2. Mark related observations as `addressed` with resolution text:
```bash
uv run python tools/methodology_tracker.py address <ID> --resolution "Added to INVESTIGATIVE_METHODOLOGY.md Section X"
```

For dismissed observations:
```bash
uv run python tools/methodology_tracker.py dismiss <ID> --reason "Duplicate of observation #Y"
```

## Notes

- **Never auto-apply changes.** All proposals require human approval.
- Friction observations about the same tool should be consolidated into a single infra request.
- Pattern detection uses word overlap — review the groupings for false clusters.
- Source quality observations should cite specific investigation contexts (which target, which search revealed the issue).
- Run this skill periodically (every 5-10 investigation waves) to keep methodology current.
