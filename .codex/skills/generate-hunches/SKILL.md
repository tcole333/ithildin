---
name: generate-hunches
description: Emerging theme recognition — spot unexpected patterns across findings that suggest deeper investigation
---

# /generate-hunches

Crawl through findings and entity data to spot emerging themes and recurring patterns that cross unexpected boundaries. NOT template-matching — genuine investigative intuition applied to accumulated data.

Quality bar: Better to generate 3 genuinely interesting hunches than 20 obvious ones.

## Arguments

- No arguments: full scan
- `--thread N`: focus on a specific thread

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Register Analysis Run

```bash
uv run uv run python -c "
from tools.analysis_export import start_analysis_run
run_id = start_analysis_run('generate-hunches')
print(f'Analysis run #{run_id}')
"
```

### 2. Export Data

```bash
uv run uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
uv run uv run python tools/analysis_export.py entity-network --output $WORKDIR/entities.json
uv run uv run python tools/analysis_export.py connections-graph --output $WORKDIR/connections.json
uv run uv run python tools/hypothesis_tracker.py list --limit 100 --output $WORKDIR/existing-hypotheses.json
uv run uv run python tools/tag_manager.py list-values --output $WORKDIR/existing-tags.json
```

### 3. Check Previous Analysis

Read existing hypotheses and tags to avoid rediscovering known patterns:
```bash
uv run uv run python tools/hypothesis_tracker.py list --limit 100
uv run uv run python tools/tag_manager.py list-values
```

### 4. Theme Detection Scans

Run these scans on the exported data. For each, read the relevant JSON files and look for:

**a) Recurring agents/attorneys across unrelated entities**
- Scan entity_roles for person_names appearing as agent/attorney across 3+ entities that aren't otherwise connected
- Example: "Same formation attorney for shell companies of three targets in different threads"

**b) Temporal clustering of entity formations**
- Scan entities for formation_dates within narrow windows (e.g., same month) across unrelated targets
- Example: "5 entities formed within 2 weeks in Dec 2002 across 3 different jurisdictions"

**c) Address convergence**
- Scan entity_addresses for shared addresses between entities belonging to different targets
- Example: "Three unrelated LLCs share a registered agent address in Delaware"

**d) Cross-thread keyword emergence**
- Scan findings across threads for recurring terms/names that appear in 3+ threads but aren't tracked as connections
- Example: "Law firm X appears in findings for threads 1, 3, and 5 but has no entity or connection record"

**e) Grant/donation overlap**
- Look for findings mentioning the same recipient organization from multiple sources
- Example: "Gratitude America and Black Family Foundation both fund Melanoma Research Alliance"

**f) Unexplained gaps**
- High-activity targets with sudden silence periods (no findings for 6+ months in an otherwise active timeline)
- Targets with many connections but zero entity registrations (or vice versa)

**g) Naming pattern analysis**
- Look for naming conventions in shell companies (sequential numbering, themed names, same word roots)
- Example: "Three 'trust' entities all use bird names (Falcon, Eagle, Hawk)"

**h) Alumni dispersal patterns**
- Run `uv run uv run python tools/pillar_tracker.py dispersal "INSTITUTION" --output $WORKDIR/dispersal.json` for dissolved institutions
- Look for coordinated movement: 3+ alumni landing at the same destination
- Example: "4 ex-Drexel people now at Apollo — not just Black/Harris/Rowan but also [unknown person]"

**i) Cross-pillar broker detection**
- Run `uv run uv run python tools/pillar_tracker.py score --top 20 --output $WORKDIR/scores.json`
- Look for unexpected names in orchestrator rankings — people who span banking + legal + government
- Flag anyone with revolving_door score > 0

**j) Missing pillar analysis**
- Run `uv run uv run python tools/pillar_tracker.py gaps --person "NAME"` for key actors
- If a known operator has no legal connections, that's suspicious — lawyers leave fewer traces
- Example: "Epstein has banking, operations, philanthropy arcs but no legal firm arcs (despite using many firms)"

### 5. Novelty Filter (Critical)

For each potential pattern found, apply these filters:

1. **Already known?** Check existing hypotheses and tags — skip if already captured
2. **Obviously connected?** Skip patterns between directly-connected actors — that's expected
3. **3+ independent contexts?** Require the pattern to appear in 3+ independent findings/entities, not just one finding's detail text
4. **Genuinely surprising?** Ask: "Would an investigator who knows the full case find this interesting?" If not, skip

### 6. Record Genuine Hunches

For each pattern that passes the novelty filter:

**Create hypothesis:**
```bash
uv run uv run python tools/hypothesis_tracker.py add \
    --title "EMERGING PATTERN" \
    --pattern-type emerging_theme \
    --description "WHAT: description. EVIDENCE: 3+ data points. WHY INTERESTING: what it implies." \
    --predicted-evidence "If this pattern is real, we should also find..." \
    --search-plan "1. Specific search command  2. Another specific search  3. Cross-reference check" \
    --originated-from "analysis:generate-hunches"
```

**Create lead (only if hypothesis suggests specific new research):**
```bash
uv run uv run python tools/lead_tracker.py add \
    --target "INVESTIGATION_TARGET" \
    --category connection \
    --priority medium \
    --description "Generated from hunch: PATTERN. Needs investigation of: SPECIFICS." \
    --source "analysis:generate-hunches"
```

**Tag involved findings:**
```bash
uv run uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2,ID3 \
    --type theme --value "THEME_NAME" --created-by "agent:generate-hunches"
```

### 7. Write Report

Write to `$WORKDIR/report-generate-hunches.md`:

```markdown
# Hunch Generation Report — [DATE]

## Run Context
- Analysis run #N
- Findings scanned: N
- Entities scanned: N
- Existing hypotheses checked: N

## Hunches Generated

### 1. [HUNCH TITLE]
**Pattern type:** emerging_theme / temporal / structural
**Evidence:** [3+ data points with finding IDs]
**Why interesting:** [What this implies about the network]
**Search plan:** [How to test this]
**Hypothesis ID:** #N
**Lead ID:** #M (if created)

### 2. [NEXT HUNCH]
...

## Patterns Checked But Filtered Out
- [Pattern] — filtered because: [already known / obviously connected / only 2 data points]

## Scan Statistics
- Scans performed: N
- Patterns found: N
- After novelty filter: M
- Hypotheses created: M
- Leads created: L
```

### 8. Complete Analysis Run

```bash
uv run uv run python -c "
from tools.analysis_export import complete_analysis_run
complete_analysis_run(RUN_ID, findings_created=0, hypotheses_created=N,
                      leads_created=M, tags_created=T,
                      report_path='$WORKDIR/report-generate-hunches.md')
"
```

## Notes

- This skill does NOT typically create findings — it creates hypotheses and leads for investigation
- A hunch without a testable search plan is not useful. Always include specific queries to run
- Quality over quantity. 3 genuine insights beats 20 obvious observations
- Build on previous runs: check existing tags and hypotheses before generating new ones
- All hypotheses: `pattern_type=emerging_theme`, status starts as `proposed`
