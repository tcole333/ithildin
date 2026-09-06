---
name: generate-hunches
description: Emerging theme recognition — spot unexpected patterns across findings that suggest deeper investigation
user_invocable: true
---

# /generate-hunches

**LAYER 2: ANALYSIS AGENT** — This is a theory-building skill. Your job is to speculate, hypothesize, and identify patterns — but every theory MUST produce a testable prediction that gets queued as a research lead for Layer 1 agents (`/pursue-lead`, `/deep-investigate`). Theories without falsification criteria or testable predictions are not useful. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline` for framework usage rules.

Crawl through findings and entity data to spot emerging themes and recurring patterns that cross unexpected boundaries. NOT template-matching — genuine investigative intuition applied to accumulated data.

Quality bar: Better to generate 3 genuinely interesting hunches than 20 obvious ones.

## Arguments

- No arguments: full scan
- `--thread N`: focus on a specific thread

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
run_id = start_analysis_run('generate-hunches')
print(f'Analysis run #{run_id}')
"
```

### 2. Export Data

```bash
uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
uv run python tools/analysis_export.py entity-network --output $WORKDIR/entities.json
uv run python tools/analysis_export.py connections-graph --output $WORKDIR/connections.json
uv run python tools/hypothesis_tracker.py list --limit 100 --output $WORKDIR/existing-hypotheses.json
uv run python tools/tag_manager.py list-values --output $WORKDIR/existing-tags.json
```

### 3. Check Previous Analysis

Read existing hypotheses and tags to avoid rediscovering known patterns:
```bash
uv run python tools/hypothesis_tracker.py list --limit 100
uv run python tools/tag_manager.py list-values
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
- Gaps of six or more months in collected findings: measure source coverage and collection effort before treating them as inactivity
- Targets with many connections but zero entity registrations (or vice versa)

**g) Naming pattern analysis**
- Look for naming conventions in shell companies (sequential numbering, themed names, same word roots)
- Example: "Three 'trust' entities all use bird names (Falcon, Eagle, Hawk)"

**h) Alumni dispersal patterns**
- Run `uv run python tools/pillar_tracker.py dispersal "INSTITUTION" --output $WORKDIR/dispersal.json` for dissolved institutions
- Compare shared destinations for 3+ alumni with normal hiring channels, industry concentration, and institution size
- Example: "4 alumni from a dissolved institution all landed at the same firm — known names plus an unexpected fourth person"

**i) Cross-pillar broker detection**
- Run `uv run python tools/pillar_tracker.py score --top 20 --output $WORKDIR/scores.json`
- Look for unexpected names in orchestrator rankings — people who span banking + legal + government
- Inspect nonzero revolving_door scores as candidate transitions; assess role relevance and the background transition rate

**j) Nonprofit funding network concentration**
- Identify nonprofits mentioned in 3+ investigation threads via findings search
- For each, run `uv run python tools/query_990.py flow <EIN> --depth 1 --output $WORKDIR/hunch-990-flow-<EIN>.json` to see their funding constellation
- Look for: same funders backing recipients across threads; compare shared mission, grant eligibility, and donor concentration before testing coordination
- Look for: circular flows between investigation-linked nonprofits (A funds B which funds A back)
- Look for: shared officers across investigation-linked nonprofits via `uv run python tools/query_990.py shared-officers <EIN1> <EIN2> ... --output $WORKDIR/hunch-990-shared.json`
- Example: "Donors Trust, Bradley Foundation, and Koch Foundation all fund 4 investigation-linked orgs across threads 2, 4, and 7 — overlapping grant recipients; test common eligibility and shared strategy as alternatives"

**k) Missing pillar analysis**
- Run `uv run python tools/pillar_tracker.py gaps --person "NAME"` for key actors
- Missing legal connections describe a collection gap; check expected record coverage, naming, and disclosure requirements before inferring an undisclosed relationship
- Example: "A key actor has banking, operations, philanthropy arcs but no legal firm arcs (despite using many firms)"

**l) Procurement acceleration clustering**
- Query USASpending timeline for companies with 3+ contract-related findings in the investigation
- Run `uv run python tools/query_usaspending.py timeline "<COMPANY>" --output $WORKDIR/hunch-usa-<slug>.json` for each
- Flag companies with >50% YoY contract growth in the most recent fiscal year
- Cross-reference with lobbying data: `uv run python tools/query_lobbying.py client "<COMPANY>" --output $WORKDIR/hunch-lobby-<slug>.json`
- Check for partnership overlaps: do accelerating companies team together on the same contract vehicles?
- Example: "Palantir and Anduril both show >50% contract growth and both lobby on DEF/HOM issues — simultaneous growth; compare agency budgets, sector growth, acquisitions, and shared procurement decisions"

### 5. Novelty Filter (Critical)

For each potential pattern found, apply these filters:

1. **Already known?** Check existing hypotheses and tags — skip if already captured
2. **Obviously connected?** Skip patterns between directly-connected actors — that's expected
3. **3+ independent contexts?** Require the pattern to appear in 3+ independent findings/entities, not just one finding's detail text
4. **Coverage and base rate?** Check whether the pattern survives collection gaps, shared exposure, and a relevant comparison group. Record a discriminating test rather than treating overlap as coordination.
5. **Genuinely surprising?** Ask: "Would an investigator who knows the full case find this interesting?" If not, skip

### 6. Record Genuine Hunches

For each pattern that passes the novelty filter:

**ACH discipline (required competing set):** Choose a short slug naming the phenomenon. Register both the working hypothesis and its best innocent explanation as first-class competitors; each needs its own falsification criterion.
```bash
uv run python tools/hypothesis_tracker.py add \
    --title "EMERGING PATTERN" \
    --pattern-type emerging_theme \
    --competition-group "short-phenomenon-slug" \
    --description "WHAT: description. EVIDENCE: 3+ data points. WHY INTERESTING: what it implies. FALSIFICATION: What evidence would disprove this?" \
    --predicted-evidence "If this pattern is real, we should also find..." \
    --search-plan "1. Specific search command  2. Another specific search  3. Cross-reference check" \
    --originated-from "analysis:generate-hunches"

uv run python tools/hypothesis_tracker.py add \
    --title "INNOCENT EXPLANATION" --as-null \
    --pattern-type emerging_theme --competition-group "short-phenomenon-slug" \
    --description "Best innocent explanation. FALSIFICATION: What evidence would disprove this explanation?" \
    --predicted-evidence "If innocent, expect..." --search-plan "Specific tests of H0" \
    --originated-from "analysis:generate-hunches"

# For every cited supporting or contradicting finding M, score it against EVERY hypothesis N in the group:
uv run python tools/hypothesis_tracker.py evaluate --hypothesis-id N --finding-id M \
    --assessment consistent|inconsistent|neutral|not_applicable --assessed-by "agent:generate-hunches"
uv run python tools/hypothesis_tracker.py compete --competition-group "short-phenomenon-slug"
```

Include the competition output in the report. Describe its verdict as **least evidence against**, never "most evidence for." If you cannot articulate what would disprove either hypothesis, do not record the set.

**Create lead (only if hypothesis suggests specific new research):**
```bash
uv run python tools/lead_tracker.py add \
    --title "Hunch: PATTERN — investigate SPECIFICS" \
    --target "INVESTIGATION_TARGET" \
    --category connection \
    --priority medium \
    --description "Generated from hunch: PATTERN. Needs investigation of: SPECIFICS." \
    --source "analysis:generate-hunches"
```

**Tag involved findings:**
```bash
uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2,ID3 \
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
uv run python -c "
from tools.analysis_export import complete_analysis_run
complete_analysis_run(RUN_ID, findings_created=0, hypotheses_created=N,
                      leads_created=M, tags_created=T,
                      report_path='$WORKDIR/report-generate-hunches.md')
"
```

## Theory → Research Loop

This is the core feedback mechanism between Layer 2 (analysis) and Layer 1 (research):

1. **This skill generates hypotheses** — each with a testable prediction and falsification criteria
2. **Each hypothesis queues a research lead** — with specific tool commands to run, not vague "investigate further"
3. **Layer 1 agents pursue those leads** — gathering facts, not testing theories
4. **Results feed back into the next analysis cycle** — new findings either support, complicate, or refute the hypothesis

Every hypothesis MUST produce at least one lead with a concrete search plan. A hypothesis that doesn't generate actionable research is theoretical overhead, not insight.

## Notes

- This skill does NOT typically create findings — it creates hypotheses and leads for investigation
- A hunch without a testable search plan is not useful. Always include specific queries to run
- Quality over quantity. 3 genuine insights beats 20 obvious observations
- Build on previous runs: check existing tags and hypotheses before generating new ones
- All hypotheses: `pattern_type=emerging_theme`, status starts as `proposed`
