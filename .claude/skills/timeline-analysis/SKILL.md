---
name: timeline-analysis
description: Temporal correlation — activity clusters, suspicious timing, silence periods, coordinated action windows
user_invocable: true
---

# /timeline-analysis

**LAYER 2: ANALYSIS AGENT** — This is a theory-building skill. You identify temporal patterns and generate hypotheses, but every hypothesis MUST produce a testable prediction queued as a research lead for Layer 1 agents. Temporal proximity is suggestive, not conclusive — always distinguish "these events happened near each other" (fact) from "these events were coordinated" (theory). See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

Analyze findings and external events on a timeline to find activity clusters, suspicious timing, silence periods, coordinated action windows, and "before the raid" patterns.

## Arguments

- No arguments: full timeline analysis
- `--thread N`: focus on a specific thread
- `--window YYYY-MM-DD YYYY-MM-DD`: analyze a specific date range

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
run_id = start_analysis_run('timeline-analysis')
print(f'Analysis run #{run_id}')
"
```

### 2. Export Timeline Data

```bash
uv run python tools/analysis_export.py timeline-export --output $WORKDIR/timeline.json
uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
uv run python tools/event_timeline.py list --limit 200 -v --output $WORKDIR/events.json
```

### 3. Date Extraction

Many findings have NULL `date_of_event` but mention dates in their summary/detail text. Scan findings for date patterns:

- "in 2013", "March 2019", "2019-07-06", "between 2011 and 2015"
- "days before", "weeks after", "the same month"

For each finding with an extractable date, note it for analysis. Optionally backfill `date_of_event`:

```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('UPDATE findings SET date_of_event = ? WHERE id = ?', ('YYYY-MM-DD', FINDING_ID))
db.commit()
"
```

Only backfill when extraction is high confidence (exact date mentioned, not inferred).

### 4. Temporal Clustering Analysis

**a) Activity bursts**
Find clusters where 3+ findings occur within a 14-day window:
- Group all dated findings by 2-week windows
- Windows with unusually high activity indicate coordinated events or investigative focus

**b) Cross-reference with events**
For each activity cluster, check the event timeline:
```bash
uv run python tools/event_timeline.py window --start YYYY-MM-DD --end YYYY-MM-DD
```
What external events coincide? Arrests, filings, media reports, elections?

**c) Pre-event activity**
Look for activity spikes in the 30 days BEFORE major events (arrests, lawsuits, media exposure):
- Entity formations before arrests
- Financial transfers before regulatory actions
- Agent resignations before indictments
Use key_dates from the investigation profile (loaded via `uv run python tools/investigation_context.py show --json`) to identify the critical dates to check.

**d) Silence periods**
For active targets (10+ findings), find gaps of 30+ days with no findings. Compare against:
- Was the target genuinely inactive?
- Were records destroyed or sealed during this period?
- Do other targets show the same silence window?

**e) Coordinated action windows**
Find weeks where 2+ unrelated targets show activity simultaneously:
- Same week entity formations
- Parallel financial transfers
- Concurrent legal filings

### 5. Key Time Periods to Analyze

Load key dates and time periods from the active investigation profile:

```bash
uv run python tools/investigation_context.py show --json
```

The profile's `key_dates` field contains investigatively significant periods and events. For each period, check for patterns including:
- Coordinated corporate setup (entity formations in the same window)
- Evidence destruction or witness coordination around legal milestones
- Legal coordination and financial movements around plea deals or indictments
- Peak financial transfer periods
- Operational adjustments before/after media exposure
- Financial restructuring before arrests
- Emergency actions during crisis windows
- Post-event estate actions, evidence requests, account closures

### 6. Record Findings

For temporal patterns discovered:

```bash
uv run python tools/findings_tracker.py add \
    --target "TARGET_NAME" \
    --type financial \
    --summary "TEMPORAL PATTERN" \
    --detail "DETAIL with dates and cross-references" \
    --confidence medium \
    --claim-type synthesis \
    --evidence "analysis-run-{RUN_ID}" \
    --source-quote "timeline analysis: N events in WINDOW"
```

### 7. Tag Temporal Patterns

```bash
uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2 \
    --type temporal --value "PATTERN_NAME" --created-by "agent:timeline-analysis"
```

### 8. Generate Hypotheses

For unexplained timing correlations. Every hypothesis MUST include:
1. A **falsification criterion** — what evidence would disprove this?
2. The **best innocent explanation** — what's the most plausible non-coordination reason?
3. A **search plan** that would test the hypothesis via Layer 1 research

```bash
uv run python tools/hypothesis_tracker.py add \
    --title "TEMPORAL HYPOTHESIS" \
    --pattern-type temporal \
    --description "PATTERN observed in WINDOW. Involves: TARGETS. Correlation with: EVENT. INNOCENT EXPLANATION: [best alternative]. FALSIFICATION: [what would disprove this]." \
    --predicted-evidence "If coordinated, expect shared communication or intermediary" \
    --search-plan "1. Check email corpus for TARGETS in WINDOW  2. Check entity formations  3. Cross-ref financial records" \
    --originated-from "analysis:timeline-analysis"
```

### 8b. Create Research Leads from Hypotheses

Each hypothesis should spawn at least one Layer 1 research lead to test it:

```bash
uv run python tools/lead_tracker.py add \
    --title "Test temporal hypothesis: [BRIEF DESCRIPTION]" \
    --category connection \
    --priority medium \
    --source "agent:timeline-analysis" \
    --description "Hypothesis: [DESCRIPTION]. Search plan: [PLAN]. Falsification: [CRITERION]."
```

### 9. Add Missing Events

If analysis reveals important external events not in the timeline, add them:

```bash
uv run python tools/event_timeline.py add \
    --date YYYY-MM-DD \
    --name "EVENT_NAME" \
    --category legal \
    --description "DESCRIPTION" \
    --relevance "WHY IT MATTERS"
```

### 10. Write Report

Write to `$WORKDIR/report-timeline-analysis.md`:

```markdown
# Timeline Analysis Report — [DATE]

## Activity Clusters
[List clusters with dates, finding counts, coinciding events]

## Pre-Event Activity Patterns
[Activity spikes before major events]

## Silence Periods
[Gaps in activity for active targets]

## Coordinated Action Windows
[Multiple targets active in same window]

## Key Period Analysis
[Analysis of each significant time period]

## Temporal Hypotheses Generated
[List hypotheses with IDs]

## Events Added to Timeline
[New events discovered during analysis]
```

### 11. Complete Analysis Run

```bash
uv run python -c "
from tools.analysis_export import complete_analysis_run
complete_analysis_run(RUN_ID, findings_created=N, hypotheses_created=M,
                      leads_created=L, tags_created=T,
                      report_path='$WORKDIR/report-timeline-analysis.md')
"
```

## Notes

- Many findings lack `date_of_event` — extract dates from text where possible
- Temporal proximity is suggestive, not conclusive. Always note this in findings (claim_type=synthesis)
- The most valuable patterns are BEFORE major events (proactive/planning behavior)
- Silence periods can be as significant as activity bursts
- Cross-thread temporal correlation is especially interesting (unrelated targets acting simultaneously)
