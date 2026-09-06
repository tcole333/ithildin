---
name: timeline-analysis
description: Temporal correlation — activity clusters, suspicious timing, silence periods, coordinated action windows
user-invocable: true
---

# /timeline-analysis

**LAYER 2: ANALYSIS AGENT** — This is a theory-building skill. You identify temporal patterns and generate hypotheses, but every hypothesis MUST produce a testable prediction queued as a research lead for Layer 1 agents. Temporal proximity is suggestive, not conclusive — always distinguish "these events happened near each other" (fact) from "these events were coordinated" (theory). See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

Analyze findings and external events on a timeline to find activity clusters, suspicious timing, silence periods, coordinated action windows, and "before the raid" patterns.

## Arguments

- No arguments: full timeline analysis
- `--thread N`: focus on a specific thread
- `--window YYYY-MM-DD YYYY-MM-DD`: analyze a specific date range

### Context Loading
Before scoped work, read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the
resolved task profile with `ITHILDIN_PROFILE`. Preserve/pass the selected
`ITHILDIN_DB_PATH` to workers. Load `investigation_context.py show` under that
environment for corpus tools, dates, threads, people, and jurisdictions; use
those values throughout this skill. Do not change the shared active profile.

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

Honor `--window` with `timeline-export --start <START> --end <END>`. For `--thread N`, use `findings-dump --thread-id N` and restrict the finding-based analysis to that set; keep external events labeled as contextual. Record the requested scope and any broader comparison data separately.

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
uv run python tools/findings_tracker.py correct <FINDING_ID> \
    --field date_of_event --value "YYYY-MM-DD" \
    --reason "Exact event date documented in <EVIDENCE_REF>"
```

Only backfill an exact documented event date. The tracker synchronizes the normalized date/precision and records the correction; retain the source reference in the reason.

### 4. Temporal Clustering Analysis

**a) Activity bursts**
Use a starting screen such as 3 findings in 14 days, then choose windows suited to the event cadence, date precision, and collection density. Record the parameters and test whether nearby reasonable choices change the result:
- Group dated findings using the selected windows; preserve uncertain or interval dates
- Check whether dense windows reflect source availability, collection effort, or actual activity before testing coordination

**b) Cross-reference with events**
For each activity cluster, check the event timeline:
```bash
uv run python tools/event_timeline.py window --start YYYY-MM-DD --end YYYY-MM-DD
```
What external events coincide? Arrests, filings, media reports, elections?

**c) Pre-event activity**
Choose before/after windows appropriate to the event cadence; 30 days can be a starting comparison. Examples to assess around major events (arrests, lawsuits, media exposure):
- Entity formations before arrests
- Financial transfers before regulatory actions
- Agent resignations before indictments
Use key_dates from the investigation profile (loaded via `uv run python tools/investigation_context.py show --json`) to identify the critical dates to check.

**d) Silence periods**
Choose a baseline period and a gap length meaningful for each target's record cadence. Ten findings and a 30-day gap can be an initial screen, not proof of inactivity. Compare against:
- Source availability, collection effort, and expected reporting schedules
- Evidence of actual activity or documented record restrictions
- Shared gaps across targets, including common collection failures

**e) Coordinated action windows**
Screen for overlapping activity among targets using a justified time window. Count and timing alone do not establish coordination. Examples to assess:
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
    --evidence "SOURCE:ID_A" "SOURCE:ID_B" \
    --source-quote "SOURCE:ID_A:Exact supporting source excerpt" \
    --source-quote "SOURCE:ID_B:Exact supporting source excerpt" \
    --sources analysis_run
```

Replace placeholders with the underlying canonical evidence and matching exact
quotes. Include the preserved calculation/report artifact when the claim depends
on computed results; `analysis_run` identifies the analysis provenance, and add
the actual underlying source tokens. An analysis-run label alone is not evidence.


### 7. Tag Temporal Patterns

```bash
uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2 \
    --type temporal --value "PATTERN_NAME" --created-by "agent:timeline-analysis"
```

### 8. Generate Hypotheses — ACH Discipline

Record supported timing observations without inventing an explanation. Explanatory hypotheses need falsification criteria and concrete research leads. Apply ACH when a claim concerns coordination or intent, or when two or more live explanations compete: register the rivals, including the best innocent explanation, and evaluate the relevant evidence against each.

```bash
uv run python tools/hypothesis_tracker.py add \
    --title "TEMPORAL HYPOTHESIS" \
    --pattern-type temporal \
    --competition-group "short-phenomenon-slug" \
    --description "PATTERN observed in WINDOW. Involves: TARGETS. Correlation with: EVENT. FALSIFICATION: [what would disprove this]." \
    --predicted-evidence "If coordinated, expect shared communication or intermediary" \
    --search-plan "1. Check email corpus for TARGETS in WINDOW  2. Check entity formations  3. Cross-ref financial records" \
    --originated-from "analysis:timeline-analysis"

uv run python tools/hypothesis_tracker.py add \
    --title "INNOCENT EXPLANATION" --as-null --pattern-type temporal \
    --competition-group "short-phenomenon-slug" \
    --description "Best non-coordination explanation. FALSIFICATION: [what would disprove H0]." \
    --predicted-evidence "If innocent, expect..." --search-plan "Specific tests of H0" \
    --originated-from "analysis:timeline-analysis"

# Score every supporting or contradicting finding M against EVERY hypothesis N in the group:
uv run python tools/hypothesis_tracker.py evaluate --hypothesis-id N --finding-id M \
    --assessment consistent|inconsistent|neutral|not_applicable --assessed-by "agent:timeline-analysis"
uv run python tools/hypothesis_tracker.py compete --competition-group "short-phenomenon-slug"
```

When ACH applies, include the competition output and unresolved rivals. The verdict is **least evidence against**, never "most evidence for."

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

Write to `$WORKDIR/report-timeline-analysis.md`, including selected windows and thresholds, date precision, source/collection limits, evidence and calculation artifacts, and unresolved questions. No actionable timing pattern is a valid outcome; preserve partial work and the next step when resuming is necessary:


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
- Compare before and after windows with a relevant baseline; pre-event timing alone does not establish planning
- Treat gaps in collected records separately from evidenced inactivity
- Cross-thread temporal correlation is especially interesting (unrelated targets acting simultaneously)
