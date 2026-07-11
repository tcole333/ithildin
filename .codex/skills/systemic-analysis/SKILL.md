---
name: systemic-analysis
description: Deep entity patterns beyond the primary subject — shared boards, co-investments, common counsel, jurisdiction clustering
---

# $systemic-analysis

**LAYER 2: ANALYSIS AGENT** — This is a theory-building skill. You identify systemic patterns and generate hypotheses, but every hypothesis MUST produce a testable prediction queued as a research lead for Layer 1 agents. Shared attributes (same jurisdiction, same industry, same donor pool) are often coincidental at baseline — always ask "what's the base rate?" before calling something a pattern. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

Analyze a group of actors as a SYSTEM — shared board memberships, co-investments, common counsel, jurisdiction clustering, coordinated donations, common grant recipients. Focus on what connects them to each other independent of the primary investigation subject.

## Arguments

- `--thread N`: analyze actors in a specific investigation thread
- `--person "Name"`: analyze the system around a specific person
- `--cluster "label"`: analyze a tagged cluster from previous analysis

Without arguments: analyzes the highest-priority thread or the largest tagged cluster.

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Register Analysis Run

```bash
uv run python -c "
from tools.analysis_export import start_analysis_run
run_id = start_analysis_run('systemic-analysis')
print(f'Analysis run #{run_id}')
"
```

### 2. Identify Target Group (5-15 actors)

Depending on the argument:

**For `--thread N`:**
```bash
uv run python tools/analysis_export.py findings-dump --thread-id N --output $WORKDIR/thread-findings.json
```
Select the top 10-15 actors by finding count in the thread.

**For `--person "Name"`:**
```bash
uv run python tools/graph_tools.py neighbors "Name" --depth 2 --output $WORKDIR/ego.json
```
Select the person plus their top 10-15 connections by degree.

**For `--cluster "label"`:**
```bash
uv run python tools/tag_manager.py find --type cluster --value "label" --output $WORKDIR/cluster.json
```
Extract the distinct target_names from the tagged findings.

### 3. Gather External Data

For each member of the target group, search external sources. Use `--output $WORKDIR/...` on all searches:

**a) LittleSis — Relationship mapping**
```bash
uv run python tools/query_littlesis.py search "MEMBER_NAME" --output $WORKDIR/littlesis-MEMBER.json
# If found, get full relationships:
uv run python tools/query_littlesis.py relationships ENTITY_ID --output $WORKDIR/littlesis-rels-MEMBER.json
```

**b) SEC EDGAR — Board and financial connections**
```bash
uv run python tools/query_edgar.py search "MEMBER_NAME" --output $WORKDIR/edgar-MEMBER.json
uv run python tools/query_edgar.py company CIK_NUMBER --output $WORKDIR/edgar-co-MEMBER.json
```

**c) IRS 990 — Nonprofit board overlap**
```bash
uv run python tools/query_990.py search "MEMBER_NAME" --output $WORKDIR/990-MEMBER.json
uv run python tools/query_990.py officer-search "MEMBER_NAME" --output $WORKDIR/990-officer-MEMBER.json
```

**d) FEC — Political donation patterns**
```bash
uv run python tools/query_fec.py donor "MEMBER_NAME" --output $WORKDIR/fec-MEMBER.json
```

**e) OpenSanctions — Sanctions/PEP status**
```bash
uv run python tools/query_opensanctions.py search "MEMBER_NAME" --output $WORKDIR/sanctions-MEMBER.json
```

### 4. Build Comparison Matrix

From gathered data, build a matrix showing which patterns are shared:

| Pattern | Member A | Member B | Member C | ... |
|---------|----------|----------|----------|-----|
| Board: Company X | Yes | Yes | | |
| Donor: PAC Y | | Yes | Yes | |
| Attorney: Firm Z | Yes | | Yes | |
| Jurisdiction: USVI | Yes | Yes | Yes | |
| Grant: Charity W | | Yes | Yes | |

Focus on patterns shared by 3+ members — these indicate systemic behavior, not coincidence.

### 5. Look Beyond Investigation Context

For each member, investigate their activities INDEPENDENT of the primary subject:
- What boards do they sit on together (without the primary subject)?
- What deals have they co-invested in?
- What political causes do they jointly support?
- What counsel/advisors do they share?
- What jurisdictions do they cluster in?

This reveals the SYSTEM — the pre-existing or parallel structure that the primary subject operated within.

### 6. Record Systemic Findings

For each systemic pattern:

```bash
uv run python tools/findings_tracker.py add \
    --target "SYSTEM_NAME (e.g., 'philanthropy network' or 'board overlap cluster')" \
    --type relationship \
    --summary "SYSTEMIC PATTERN: N members share X" \
    --detail "Members: A, B, C. Pattern: DESCRIPTION. Significance: IMPLICATION." \
    --confidence medium \
    --claim-type synthesis \
    --evidence "analysis-run-{RUN_ID}; littlesis:ID1; edgar:CIK" \
    --source-quote "SPECIFIC DATA POINTS from external sources"
```

### 7. Tag with Systemic Labels

```bash
uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2,ID3 \
    --type systemic --value "GROUP_NAME" --created-by "agent:systemic-analysis"
```

### 8. Generate Hypotheses — ACH Discipline

For each system-level pattern, choose a short phenomenon slug. Register the working theory and best innocent explanation as a competing set; each must have its own falsification criterion and Layer 1 search plan.

```bash
uv run python tools/hypothesis_tracker.py add \
    --title "SYSTEMIC HYPOTHESIS" \
    --pattern-type operational \
    --competition-group "short-phenomenon-slug" \
    --description "SYSTEM PATTERN: N actors share X, suggesting Y. FALSIFICATION: [what would disprove this]." \
    --predicted-evidence "If coordinated, expect shared Z" \
    --search-plan "1. Check registry for shared agents  2. Search emails for inter-member communication  3. Cross-ref financial flows" \
    --originated-from "analysis:systemic-analysis"

uv run python tools/hypothesis_tracker.py add \
    --title "INNOCENT EXPLANATION" --as-null --pattern-type operational \
    --competition-group "short-phenomenon-slug" \
    --description "Best non-coordination explanation. FALSIFICATION: [what would disprove H0]." \
    --predicted-evidence "If innocent, expect..." --search-plan "Specific tests of H0" \
    --originated-from "analysis:systemic-analysis"

# Score every supporting or contradicting finding M against EVERY hypothesis N in the group:
uv run python tools/hypothesis_tracker.py evaluate --hypothesis-id N --finding-id M \
    --assessment consistent|inconsistent|neutral|not_applicable --assessed-by "agent:systemic-analysis"
uv run python tools/hypothesis_tracker.py compete --competition-group "short-phenomenon-slug"
```

Include the competition output in the report. The verdict is **least evidence against**, never "most evidence for."

### 9. Create Leads

For unexplored system nodes (e.g., the shared attorney, the common board, the co-investment vehicle):

```bash
uv run python tools/lead_tracker.py add \
    --title "Systemic node: SYSTEM_NODE_NAME — shared by N members of GROUP" \
    --target "SYSTEM_NODE_NAME" \
    --category connection \
    --priority medium \
    --description "Systemic node: shared by N members of GROUP. Roles: DESCRIPTION." \
    --source "analysis:systemic-analysis" \
    --thread-id THREAD_ID
```

### 10. Map Connections

Create connections between system members that aren't already recorded:

```bash
uv run python tools/findings_tracker.py connect \
    --person-a "MEMBER_A" \
    --person-b "MEMBER_B" \
    --type corporate \
    --description "Both serve on BOARD_NAME" \
    --finding-id FINDING_ID
```

**Register every system member as a structured entity — a connection alone is not enough.** `connect` auto-creates a bare `entity_type='unknown'` row for any endpoint not already registered (so no connection is ever orphaned), but that stub carries no type, jurisdiction, roles, or addresses — exactly the attributes systemic patterns (shared boards, common counsel, jurisdiction clustering) are built from. For each company, fund, or person in the system, register the real entity and its structure so those patterns surface in graph analysis:

```bash
uv run python tools/entity_tracker.py add-entity --name "MEMBER_A" --entity-type <person|inc|llc|fund|...> --jurisdiction <JUR> --source "<SOURCE>"
uv run python tools/entity_tracker.py add-role --entity-id <ID> --person-name "PERSON" --role "<director|officer|counsel|...>" --source "<SOURCE>"
uv run python tools/entity_tracker.py add-relation --entity-a-id <A> --entity-b-id <B> --relation-type "<shares_officer|co_investor|...>" --source "<SOURCE>"
```

### 11. Write Report

Write to `$WORKDIR/report-systemic-analysis.md`:

```markdown
# Systemic Analysis Report — [DATE]

## Target Group
- Scope: [thread/person/cluster]
- Members (N): [list]

## System Patterns Found

### 1. [PATTERN NAME]
**Members involved:** A, B, C, D
**Evidence:** [external source data]
**Significance:** [what it implies]

### 2. [NEXT PATTERN]
...

## Comparison Matrix
[Table of shared patterns]

## Non-Subject System Structure
[What connects these actors to each other independent of the primary subject]

## Systemic Hypotheses
[Generated hypotheses with IDs]

## New Leads
[Leads for unexplored system nodes]

## Connections Mapped
[New connections created]
```

### 12. Complete Analysis Run

```bash
uv run python -c "
from tools.analysis_export import complete_analysis_run
complete_analysis_run(RUN_ID, findings_created=N, hypotheses_created=M,
                      leads_created=L, tags_created=T,
                      report_path='$WORKDIR/report-systemic-analysis.md')
"
```

## Notes

- This skill is about the SYSTEM, not individuals. A finding about one person's board membership is not systemic. 3+ people on the same board IS systemic.
- All findings: `claim_type=synthesis`, max confidence `medium`
- Use LittleSis as primary system-mapping source (pre-built relationship data)
- The comparison matrix is the core deliverable — it reveals shared infrastructure
- Most valuable insight: what connects network members to each other WITHOUT going through the primary subject
- Rate-limit external API calls. LittleSis retries on 503. EDGAR needs User-Agent. FEC needs API key.
