---
name: discover-frameworks
description: Discover, evaluate, and adopt analytical frameworks that deepen agent cognition and reader understanding
user-invocable: true
---

# /discover-frameworks

**LAYER 2: ANALYSIS AGENT** — This is a theory-building skill. Use frameworks to propose testable patterns and explanations; state their assumptions and distinguish applicability from mere resemblance. Every framework MUST include falsification criteria and boundary conditions. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

Identify candidate analytical frameworks through training knowledge, academic/practitioner literature, and investigation data review. Evaluate candidates against the investigation's findings and adopt them at the appropriate tier.

Load the current inventory rather than assuming a fixed model count. Seek frameworks that improve discriminating questions, evidence collection, and understanding of observed patterns.

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
- `--update-detector`: verify the detector's runtime-loaded keywords for newly adopted lenses

### Context and execution

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` before source planning and pin the resolved profile/database. Use official or original scholarly/practitioner sources to verify candidate definitions and boundary conditions; training knowledge proposes candidates rather than verifying them. Preserve URLs and quoted passages in the run artifacts.

When independent literature or candidate reviews help, use native subagents supervised in the current task, inheriting the configured model. Assign factual questions, pinned context, distinct candidate/source scopes and report paths. Collect every report and reconcile disagreements before adopting a framework. Review mode reports proposed changes unless the user also authorized applying them.

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

# Relevant findings (add --thread-id N to both exports when requested)
uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
uv run python tools/analysis_export.py thread-summary --output $WORKDIR/threads.json

# Current analytical models document
cat research/craft-research/analytical-models.md
```

### 2. Identify Gaps (Bottom-Up)

Scan findings for questions or patterns the current models do not address:

**a) Run gap detection on recent findings**
```bash
# Select relevant findings through the detector
# Look for findings with no model match
uv run python tools/model_detector.py gaps --finding-id FINDING_ID --output "$WORKDIR/gaps-FINDING_ID.json"
```

Choose findings relevant to the requested scope, including counterexamples and ordinary cases. A sample of 30-50 can be a starting point for a broad scan; record selection and coverage, and expand when unresolved questions justify it. A missing keyword match is a candidate inspection task, not proof of an explanatory gap.

**b) Review framework_candidate hypotheses**
Read the candidates exported in step 1. These are patterns agents noticed during investigation that didn't fit existing models.

**c) Identify thread-level analytical gaps**
For each thread, ask: Which current models apply to this thread's findings? Which threads have thin analytical coverage? What patterns repeat within the thread that don't have a framework name?

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
4. Does this framework explain something the current core models miss, or is it a variant of an existing model?

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
- Grounding findings with canonical evidence, independence, and diagnostic value; a count alone does not establish applicability
- What it explains that existing models don't
- **Boundary conditions** (when does this framework NOT apply? What would it look like if this pattern were absent?)
- **Overfit risk** (how might this framework cause agents to see false positives? What innocent scenarios could be misread as instances of this pattern?)
- Limitations (when it misleads or doesn't apply)
- Related models (which core models or other lenses connect)

### 4. Evaluate Candidates

Evaluate each candidate using these criteria:

| Criterion | Question |
|-----------|----------|
| **Explanatory power** | Does it propose a testable mechanism? |
| **Novelty** | What useful distinction does it add to the current models? |
| **Transferability** | Where could it apply beyond this investigation, and where would it fail? |
| **Detectability** | Which markers support useful searches, and which ordinary cases would also match? |
| **Evidence grounding** | Do independent records distinguish it from baseline and rival explanations? |
| **Predictive value** | What discriminating evidence should be sought next? |
| **Falsifiability** | What would disprove applicability, and what baseline comparison is available? |

**Evaluation decision:** Use the criteria as prompts for judgment, not an additive score. Adopt a Tier 2 lens only when its boundaries, diagnostic evidence, and discriminating tests are adequate for the stated use; explain the decision and unresolved limitations. Keep promising but untested candidates evaluated, and use Tier 3 for useful background that is not yet operational. Reject candidates that add no useful distinction. No number of weak matches substitutes for grounding or falsifiability.

**Novelty check (critical):** A candidate that's really just a sub-case of an existing model should be noted as a variant, not a new lens. E.g., "regulatory arbitrage through trust structures" is just Jurisdictional Arbitrage applied to trusts — not a new framework. But "regulatory capture" is genuinely distinct from the current inventory when its mechanism and boundary conditions differ.

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
created: YYYY-MM-DD
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

**Record hypotheses for follow-up:** Each explanatory hypothesis needs falsification criteria and a concrete research lead. Apply the methodology's competing-set/ACH requirements when the claim concerns coordination or intent, or two or more live rivals exist. Mere keyword matches and descriptive observations do not require invented explanatory hypotheses.
```bash
uv run python tools/hypothesis_tracker.py add \
    --title "FRAMEWORK suggests PATTERN in THREAD" \
    --pattern-type structural \
    --description "The [FRAMEWORK] suggests [PATTERN] in thread [N]. Prediction: [WHAT TO LOOK FOR]. Falsification: [WHAT WOULD DISPROVE IT]. Baseline or rival: [ALTERNATIVE]." \
    --predicted-evidence "If this framework applies, we should find: [SPECIFIC EVIDENCE]" \
    --search-plan "1. [QUERY]  2. [QUERY]  3. [CROSS-REFERENCE]" \
    --originated-from "analysis:discover-frameworks" \
    --thread-id N
```

**Generate leads for unexplored areas:**
```bash
# Pick the closest --category: person, entity, financial, document, digital,
# connection, legal, intelligence, filing, contract, case
uv run python tools/lead_tracker.py add \
    --title "Framework [NAME]: investigate [WHAT]" \
    --target "INVESTIGATION_TARGET" \
    --category financial \
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

Write to `$WORKDIR/report-discover-frameworks.md`, including verified source citations, evidence independence, candidate decisions and rationale, counterexamples, unresolved tests, and any partial work with the next resumable step. Finding no useful new framework is a valid outcome:


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
4. Reassess tier using evidence independence, diagnosticity, boundary tests, and demonstrated usefulness. Article use can inform usability; it is not independent validation or an automatic promotion threshold.
5. Flag unsupported or contradicted lenses and obsolete source assumptions. Lack of new findings over an arbitrary time period alone does not make an established framework stale
6. Report on framework health

## Quality Standards

- **Depth over breadth.** 3 well-grounded frameworks with detection markers beat 10 vague suggestions.
- **Explain incremental value.** A new label needs a useful distinction; refinements to an existing model can be recorded there.
- **Evidence grounds adoption.** Assess source independence, counterexamples, diagnostic value, and boundary conditions. Fewer strong records can justify a candidate; many superficial matches do not validate one. Training knowledge proposes; evidence tests applicability.
- **Detection markers must be specific.** "Look for financial irregularities" is useless. "Look for compliance override by revenue-generating relationship managers" is useful.
- **Limitations prevent overuse.** Every framework should include clear boundaries — when does it NOT apply?
