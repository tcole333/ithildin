---
name: discover-frameworks
description: Discover, evaluate, and adopt analytical frameworks that deepen agent cognition and reader understanding
user_invocable: true
---

# /discover-frameworks

Identify candidate analytical frameworks through training knowledge, academic/practitioner literature, and investigation data review. Evaluate candidates against the investigation's findings and adopt them at the appropriate tier.

The current 8 core models (Bridge Tax, Manufactured Dependency, etc.) were seeded once. This skill evolves the framework inventory by finding new lenses that explain patterns the existing models miss.

## Three-Tier System

| Tier | What | Where | Used By |
|------|------|-------|---------|
| **1: Core Models** | Full JSON spec, web page, article callouts | `content/models/*.json` | Articles, dossiers, model_detector.py |
| **2: Domain Lenses** | Markdown + YAML frontmatter, detection keywords | `research/craft-research/frameworks/*.md` | Agent prompts, model_detector.py (when adopted) |
| **3: Reference Frameworks** | Citation + 1-2 sentence relevance note | `research/craft-research/framework-references.md` | Theoretical grounding in analysis/articles |

## Arguments

- No arguments: full discovery cycle (bottom-up gap scan + top-down brainstorm)
- `--thread N`: focus on findings from a specific investigation thread
- `--domain X`: focus on a specific academic domain (financial-crime, org-theory, intelligence, network-science, behavioral, legal-regulatory, economic)
- `--review`: review existing lenses rather than discover new ones (reassess tier, check evidence growth)
- `--update-detector`: after run, add detection rules to `model_detector.py` for any newly adopted lenses

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Gather Context

Load current inventory and investigation state:

```bash
# Current core models
uv run python tools/model_detector.py list --output $WORKDIR/current-models.json

# Current framework candidates from agents
uv run python tools/hypothesis_tracker.py list --pattern-type framework_candidate --output $WORKDIR/candidates.json

# Existing lenses (read the frameworks directory)
ls research/craft-research/frameworks/*.md 2>/dev/null || echo "No lenses yet"

# Existing reference frameworks
cat research/craft-research/framework-references.md

# Recent findings (thread-scoped if --thread N)
uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
uv run python tools/analysis_export.py thread-summary --output $WORKDIR/threads.json

# Current analytical models document
cat research/craft-research/analytical-models.md
```

### 2. Identify Gaps (Bottom-Up)

Scan findings for patterns the current 8 models don't explain well:

**a) Run gap detection on recent findings**
```bash
# Sample 50 recent findings through the detector
# Look for findings with no model match
uv run python tools/model_detector.py gaps --finding-id FINDING_ID
```

Pick 30-50 recent or high-impact findings and run `gaps` on each. Track which findings match no model.

**b) Review framework_candidate hypotheses**
Read the candidates exported in step 1. These are patterns agents noticed during investigation that didn't fit existing models.

**c) Identify thread-level analytical gaps**
For each thread, ask: Which of the 8 models apply to this thread's findings? Which threads have thin analytical coverage? What patterns repeat within the thread that don't have a framework name?

**d) Review connection patterns**
```bash
uv run python tools/analysis_export.py connections-graph --output $WORKDIR/connections.json
```
Look at relationship types and patterns that existing models don't address. Are there recurring structural patterns (e.g., regulatory capture, principal-agent inversion) that appear across multiple connections?

### 3. Brainstorm Candidates (Top-Down)

This is the core intellectual work. Draw on training knowledge across relevant domains to identify frameworks that would explain the gaps found in Phase 2.

**Approach: For each unexplained pattern, ask:**
1. What academic field studies this type of phenomenon?
2. What named concepts from that field would apply?
3. What are the detection markers — how would an agent recognize this pattern?
4. Does this framework explain something the 8 core models genuinely miss, or is it a variant of an existing model?

**Domain checklist** (focus on --domain if specified, otherwise scan broadly):

- **Financial crime:** FATF typologies, layering mechanics, trade-based ML, mirror trading, correspondent banking exploitation, beneficial ownership opacity, structuring patterns
- **Organizational theory:** Regulatory capture (Stigler), principal-agent inversion, institutional isomorphism (DiMaggio/Powell), normalization of deviance (Vaughan), moral hazard, information asymmetry (Akerlof)
- **Intelligence studies:** Cutouts and deniability chains, dual-use infrastructure, kompromat economics, covert action doctrine, structured analytic techniques (Heuer/Pherson)
- **Legal/regulatory:** Prosecutorial selection theory, DPA dynamics, legal privilege as OpSec, forum shopping, compliance theater
- **Behavioral/cognitive:** Diffusion of responsibility, moral disengagement (Bandura), willful blindness (Heffernan), bounded rationality (Simon), groupthink (Janis)
- **Economic:** Rent-seeking (Tullock), club goods (Buchanan), transaction cost economics (Williamson), regulatory arbitrage theory
- **Historical parallels:** BCCI, Nugan Hand, Madoff, Enron, Panama Papers, 1MDB — what frameworks explain those cases?

**For each candidate, produce:**
- Name (memorable, descriptive)
- Source (academic citation or practitioner origin)
- Domain tag
- Definition (2-3 paragraphs: what it is, how it applies here)
- Detection markers (what agents should look for)
- Grounding findings (3+ findings from the investigation that instantiate it)
- What it explains that existing models don't
- Limitations (when it misleads or doesn't apply)
- Related models (which core models or other lenses connect)

### 4. Evaluate Candidates

Score each candidate on these criteria:

| Criterion | Question | Weight |
|-----------|----------|--------|
| **Explanatory power** | Does it reveal mechanism, not just describe outcomes? | High |
| **Novelty** | Does it explain something the current 8 models don't cover? | High |
| **Transferability** | Can a reader apply this concept beyond this investigation? | Medium |
| **Detectability** | Can we define keyword markers agents can search for? | Medium |
| **Evidence grounding** | Do we have 3+ independent findings that instantiate it? | High |
| **Predictive value** | Does it suggest where to look next? | Medium |

**Evaluation rubric:**
- 5+ criteria met strongly → **Tier 2 Lens (adopted)**
- 3-4 criteria met → **Tier 2 Lens (evaluated)** — needs more evidence before adoption
- 1-2 criteria met → **Tier 3 Reference** — useful for grounding but not operationalizable yet
- 0 criteria → Skip

**Novelty check (critical):** A candidate that's really just a sub-case of an existing model should be noted as a variant, not a new lens. E.g., "regulatory arbitrage through trust structures" is just Jurisdictional Arbitrage applied to trusts — not a new framework. But "regulatory capture" is genuinely distinct from any of the 8.

### 5. Record Results

**For Tier 2 Lenses (adopted or evaluated):**

Write a markdown file to `research/craft-research/frameworks/`:

```bash
# Example: research/craft-research/frameworks/regulatory-capture.md
```

File format (YAML frontmatter + markdown body):
```yaml
---
name: Framework Name
slug: framework-slug
domain: org-theory
source: "Author, 'Work Title' (Year)"
status: adopted  # or evaluated or candidate
created: 2026-MM-DD
grounding_findings: [1234, 2345, 3456]
related_models: [private-order, enabler-gradient]
detection_keywords:
  - ["revolving door", "former regulator", "former official"]
  - ["compliance capture", "compliance deferred", "revenue priority"]
  - ["industry-drafted", "regulatory language", "lobbying"]
  - ["enforcement pattern", "leniency", "connected entities"]
---

## Definition

2-3 paragraphs explaining the framework and its application to this investigation.

## Detection Markers

- Human-readable detection markers for agents
- More detailed than keyword lists
- Include specific things to look for in findings

## Limitations

- When this framework misleads or doesn't apply
- Distinguish from adjacent concepts
```

**For Tier 3 References:**

Add entries to `research/craft-research/framework-references.md` in the appropriate domain table.

**Record hypotheses for follow-up:**
```bash
uv run python tools/hypothesis_tracker.py add \
    --title "FRAMEWORK suggests PATTERN in THREAD" \
    --pattern-type structural \
    --description "The [FRAMEWORK] lens suggests we should find [PATTERN] in thread [N]. Specific prediction: [WHAT TO LOOK FOR]." \
    --predicted-evidence "If this framework applies, we should find: [SPECIFIC EVIDENCE]" \
    --search-plan "1. [QUERY]  2. [QUERY]  3. [CROSS-REFERENCE]" \
    --originated-from "analysis:discover-frameworks" \
    --thread-id N
```

**Generate leads for unexplored areas:**
```bash
uv run python tools/lead_tracker.py add \
    --target "INVESTIGATION_TARGET" \
    --category analysis \
    --priority medium \
    --description "Framework [NAME] suggests investigating [WHAT]. Detection markers: [MARKERS]." \
    --source "analysis:discover-frameworks" \
    --thread-id N
```

### 6. Update Detector (if --update-detector)

For adopted lenses with `detection_keywords` in their YAML frontmatter, `model_detector.py` will automatically load them at runtime. Verify:

```bash
uv run python tools/model_detector.py list
# Should show core models AND adopted lenses
uv run python tools/model_detector.py detect --text "TEST TEXT MATCHING NEW LENS"
# Should detect the new lens
```

### 7. Write Report

Write to `$WORKDIR/report-discover-frameworks.md`:

```markdown
# Framework Discovery Report — [DATE]

## Context
- Findings scanned: N
- Threads analyzed: [list]
- Framework candidates from agents: N
- Existing lenses reviewed: N

## Gap Analysis
- Findings with no model match: N/M scanned (X%)
- Threads with thin analytical coverage: [list]
- Recurring unexplained patterns: [list with finding counts]

## Frameworks Evaluated

### [NAME] — Tier 2 Lens (adopted/evaluated)
**Domain:** [domain]
**Source:** [citation]
**What it explains:** [1-2 sentences]
**Grounding findings:** [finding IDs]
**Detection keywords:** [N groups]
**Leads generated:** [N]

### [NAME] — Tier 3 Reference
**Domain:** [domain]
**Source:** [citation]
**Why included:** [1-2 sentences]

## Candidates Rejected
- [NAME] — rejected because: [variant of existing model / insufficient evidence / not operationalizable]

## Recommendations
- Frameworks to pilot in next article: [list]
- Investigation areas to deepen for framework grounding: [list]
- Existing models that could be refined: [list with rationale]
```

## Review Mode (--review)

When `--review` is specified, skip discovery and instead:

1. Load all existing Tier 2 lenses from `research/craft-research/frameworks/`
2. For each lens, count grounding findings (have more appeared since adoption?)
3. Check if any lens has been referenced in articles (search content/articles/ for the slug)
4. Reassess tier: candidate with strong evidence → promote to evaluated. Evaluated with article use → promote to adopted. Adopted with 3+ articles → recommend promotion to Tier 1 core model.
5. Flag stale lenses: adopted but no new grounding findings in 30+ days
6. Report on framework health

## Quality Standards

- **Depth over breadth.** 3 well-grounded frameworks with detection markers beat 10 vague suggestions.
- **Novelty is mandatory.** If it's really just an existing model with different vocabulary, note the connection and move on.
- **Evidence grounds everything.** No framework without 3+ findings that instantiate it. Training knowledge proposes; investigation data validates.
- **Detection markers must be specific.** "Look for financial irregularities" is useless. "Look for compliance override by revenue-generating relationship managers" is useful.
- **Limitations prevent overuse.** Every framework should include clear boundaries — when does it NOT apply?
