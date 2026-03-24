# Investigation Refactor Plan

## Purpose

This document captures a proposed refactor of the investigation system so the repo more cleanly supports:

1. **Tier 0 landscape scan** for fast terrain mapping
2. **Tier 1 evidence collection** for exhaustive, narrow fact-gathering
3. **Tier 2 analysis** for hunches, frameworks, and network interpretation
4. **Editorial outputs** built on top of a cleaner evidence and analysis stack

The goal is to turn the current system from a smart but somewhat overlapping toolkit into a more explicit operating system with stronger boundaries, better queueing, and more enforceable evidence discipline.

---

## Executive Summary

The current methodology is mostly right. The main problems are:

* Research, analysis, and editorial thinking still bleed into one another inside individual skills.
* Triage behaves more like a procedural checklist than a real scheduler.
* `/search-all-sources` is too broad to remain a first-class investigation skill in its current form.
* `lead_tracker.py` and `findings_tracker.py` contain useful machinery, but too much policy still lives in prose rather than code.
* Frameworks and craft principles are stronger than average, but they need tighter governance and more operational trigger conditions.

The proposed refactor keeps the overall philosophy but makes role boundaries, artifacts, and queueing decisions much more explicit.

---

## Target Architecture

### 1. Control Plane

Owns:

* investigation initialization
* landscape scanning
* lead triage and scheduling
* escalation / de-escalation
* dispatching Tier 1 and Tier 2 work
* queue balancing across threads

Primary idea:

* **Breadth-first map the terrain**
* then run **bounded depth-first investigation sprints** on the most informative leads
* then re-rank the queue after analysis

### 2. Research Plane (Tier 1)

Owns:

* factual collection
* source checklist execution
* ambient documentation
* negative-result recording
* entity / role / address registration
* missing-document identification
* new lead spawning

Must not own:

* narrative framing
* article hook selection
* framework application
* system-level interpretation

### 3. Analysis Plane (Tier 2)

Owns:

* hypothesis generation
* network analysis
* timeline reasoning
* framework evaluation
* innocent explanations / falsification criteria
* re-prioritization inputs for triage

Must not own:

* pretending hypotheses are findings
* silently upgrading weak patterns into architectures

### 4. Editorial Plane

Owns:

* dossiers
* articles
* model pages
* visualizations
* review / verification

Depends on:

* trustworthy evidence packets
* explicit thesis boundaries
* structured analysis outputs

---

## Core Design Principles

### Separate responsibilities hard, not softly

The same skill should not try to be a researcher, analyst, and editor.

### Make phases produce structured artifacts

Every major stage should emit machine-readable outputs in addition to markdown summaries.

Suggested canonical outputs:

* `scan_report.json`
* `triage_decisions.json`
* `evidence_packet.json`
* `analysis_memo.json`
* `article_plan.json`
* `verification_report.json`

### Make policy enforceable in code where possible

The most important evidence rules should live in tracker code, not only in skill prose.

### Prefer bounded DFS over open-ended rabbit holes

A lead should be pursued deeply, but with explicit stop conditions.

### Let frameworks detect patterns, not drive collection

Frameworks should be usable only after evidence exists and should have trigger conditions, anti-patterns, and worked examples.

---

## Diagnosis of the Current System

### A. Methodology is ahead of the skills

The methodology describes a good architecture:

* Tier 0 scan
* Tier 1 standard investigation
* Tier 2 deep dive
* Layer 1 / Layer 2 feedback loop

But several skills still mix these roles in practice.

### B. Tier 1 skills still carry analysis/editorial residue

Examples of things that should be removed from Tier 1 workers:

* narrative potential
* article-worthy finding selection
* character entry points
* system-level framing

Tier 1 should return evidence packets, not proto-articles.

### C. Triage is too weak as a scheduler

Current triage mostly:

* deduplicates
* tweaks priority
* promotes to open

But it should also assign:

* `depth_tier`
* `recommended_next_skill`
* `triage_rationale`
* `blocked_reason` when applicable

### D. `/search-all-sources` is too broad

As currently framed, it encourages “search everything” as a normal move. That is useful as infrastructure, but not as default investigator behavior.

### E. Trackers are strong but overloaded

`lead_tracker.py` already contains a lot of useful machinery:

* claims / leases
* stale recovery
* tier tagging
* threads
* evidence references
* dispatch metadata

But too much logic is still centralized in a single file and not consistently used by the skills.

### F. Framework governance is good in principle but inconsistent in practice

The README and methodology say frameworks are pattern detectors with boundary conditions. Some framework files already behave that way; others still need stronger trigger thresholds and anti-pattern discipline.

---

## Proposed Refactor Roadmap

## Phase 1 — Clarify Operating Boundaries

### 1.1 Rewrite skill responsibilities around planes

Reclassify skills explicitly:

**Control plane**

* `init-investigation`
* `landscape-scan`
* `triage-leads`
* `deep-investigate` (as dispatcher/orchestrator, not “just research”)

**Research plane**

* `pursue-lead`
* `investigate-person`
* `trace-entity`
* `investigate-infra`
* other narrow Tier 1 workers

**Analysis plane**

* `generate-hunches`
* `analyze-network`
* `timeline-analysis`
* `systemic-analysis`
* `discover-frameworks`

**Editorial plane**

* dossier/article/review skills

### 1.2 Strip analysis/editorial prompts out of Tier 1 skills

Remove from Tier 1 outputs:

* narrative potential
* article-worthy fact selection
* hook language
* “what this reveals” framing

Replace with a standard output contract:

```json
{
  "coverage_report": {},
  "findings": [],
  "negative_results": [],
  "entities_added": [],
  "connections_added": [],
  "missing_docs": [],
  "new_leads": [],
  "confidence_notes": []
}
```

### 1.3 Convert `deep-investigate` into explicit orchestration

Keep its source-assignment matrix and multi-agent structure, but redefine it as:

* planner
* dispatcher
* coverage checker
* synthesis coordinator

Not as a generic Layer 1 worker.

---

## Phase 2 — Strengthen Triage and Queueing

### 2.1 Turn triage into a real scheduler

Each triaged lead should receive:

* `priority`
* `depth_tier` (`scan`, `standard`, `deep_dive`)
* `recommended_next_skill`
* `thread_id`
* `triage_rationale`
* `blocked_reason` if relevant

### 2.2 Use existing lease/claim mechanics consistently

`triage-leads` should use the same atomic claim logic already present in `lead_tracker.py` rather than ad hoc batch selection.

### 2.3 Introduce a ranking model closer to the methodology

Priority score should incorporate more than title/category heuristics. Suggested dimensions:

* structural importance / bridge potential
* information richness / document availability
* cross-thread relevance
* missing-document potential
* relationship to current Tier 2 hypotheses
* novelty
* investigation thread coverage balance

### 2.4 Add bounded DFS stop conditions

A lead sprint should stop when one of these is true:

* mandatory sources are exhausted with sufficient corroboration
* mandatory sources are exhausted with consistent negative results
* recent searches are yielding no new edges/entities/documents
* a hard access barrier is reached and the next move is infrastructural

---

## Phase 3 — Refactor the Tracker Layer

### 3.1 Split `lead_tracker.py`

Proposed split:

* `lead_schema.py` or migrations module
* `lead_queue.py` for claims, next, stale recovery, tiering
* `lead_relations.py` for related leads / graph edges
* `lead_reporting.py` for stats, audits, summaries

### 3.2 Strengthen `findings_tracker.py`

Move key policy into code:

* enforce claim-type / confidence caps
* require provenance for relevant finding classes
* support first-class negative-result records
* validate evidence references more consistently
* preserve correction / dispute flows

### 3.3 Improve search logging

Keep both:

* a cache key / recent-search helper
* a historical search run log

Do not let dedupe erase audit history.

### 3.4 Add queue/state fields if missing

Likely additions:

* `recommended_next_skill`
* `triage_rationale`
* `blocked_reason`
* `stop_reason`
* `sprint_id`
* `analysis_status`

---

## Phase 4 — Tighten Framework Governance

### 4.1 Refactor craft principles into layers

Split current craft guidance into:

* editorial constitution
* mode-specific playbooks
* implementation handbook

### 4.2 Add required metadata to each framework

Every framework file should have:

* `minimum_trigger`
* `anti_pattern`
* `canonical_example`
* `grounding_findings`
* `status`

### 4.3 Add claim ladder discipline

Introduce a common ladder:

* fact
* pattern
* mechanism
* coordination
* intent
* motive

Each rung should specify:

* evidence threshold
* allowed language
* common failure mode

---

## Phase 5 — Clean Up Editorial Workflows

### 5.1 Move article/dossier expectations into shared standards

Create canonical shared specs such as:

* `editorial-standards/articles.md`
* `editorial-standards/dossiers.md`
* `editorial-standards/citation-support.md`

### 5.2 Make article generation artifact-driven

Have `/write-article` generate structured artifacts at each phase:

* research dossier JSON
* article structure JSON
* review JSON
* publication checklist JSON

Markdown reports can remain as human-facing renderings.

### 5.3 Keep article voice, but tighten claim boundaries

Articles should remain interpretive and opinionated, but the thesis boundary, strongest skeptical alternative, and evidence limits should be explicit before drafting begins.

---

## File-Level Refactor Targets

### Immediate high-priority

* `research/INVESTIGATIVE_METHODOLOGY.md`
* `research/craft-principles.md`
* `tools/lead_tracker.py`
* `tools/findings_tracker.py`
* `skills/triage-leads`
* `skills/pursue-lead`
* `skills/deep-investigate`
* `skills/search-all-sources`

### Secondary

* `tools/auto_leads.py`
* `tools/investigation_context.py`
* `tools/entity_tracker.py`
* `tools/model_detector.py`
* article and dossier review scripts

---

## Concrete Skill Changes

### `landscape-scan`

Keep and promote as the default entry point for new domains.

Should output:

* major actors
* key entities
* preliminary relationships
* candidate threads
* leads to create
* recommended escalations

### `search-all-sources`

Demote from front-line skill to infrastructure primitive or limited scan helper.

Potential replacement modes:

* `person`
* `entity`
* `address`
* `domain`
* `instrument`

### `pursue-lead`

Make the canonical Tier 1 worker.

Should focus on:

* atomic lead claim
* source checklist completion
* ambient documentation
* negative results
* evidence packet output

### `deep-investigate`

Keep only if it is clearly framed as:

* control-plane orchestration
* source assignment matrix
* parallel dispatch
* coverage synthesis
* follow-up queue generation

### `triage-leads`

Upgrade into:

* deduper
* scheduler
* tier assigner
* queue balancer
* blocker detector

---

## Open Design Questions

1. Should `deep-investigate` dispatch only Tier 1 workers, or also allow Tier 2 follow-on passes in the same workflow?
2. Should negative results be stored as ordinary findings with a special type, or as a separate first-class table?
3. What should the exact stop conditions be for a “bounded DFS sprint”?
4. How aggressive should automatic escalation to `deep_dive` be?
5. Which parts of framework detection should be automated versus explicitly human-reviewed?

---

## Suggested Implementation Sequence

1. **Refactor the plan and responsibility docs first**

   * methodology
   * craft principles
   * framework metadata contract

2. **Refactor scheduler + trackers next**

   * triage
   * lead queue
   * findings validation

3. **Then refactor Tier 1 skills**

   * remove narrative residue
   * standardize output schema

4. **Then refactor Tier 2 and editorial flows**

   * analysis memo schema
   * article planning artifacts
   * shared standards

5. **Only then optimize discovery / source fan-out infrastructure**

   * search helper modes
   * infra improvements
   * auto lead generation tuning

---

## Definition of Done

The refactor is successful when:

* a new investigation naturally starts with a scan, not a deep dive
* triage reliably decides what should happen next
* Tier 1 workers return evidence packets, not proto-essays
* Tier 2 workers produce hypotheses with falsification criteria
* frameworks are applied sparingly and with explicit triggers
* writing can rely on stronger evidence contracts and clearer upstream artifacts
* queue behavior is visible and auditable

---

## Next Steps

1. Turn this plan into a concrete checklist with owners and file-by-file tasks.
2. Draft the v2 contracts for:

   * `triage-leads`
   * `pursue-lead`
   * `deep-investigate`
   * `lead_tracker.py`
   * `findings_tracker.py`
3. Decide whether to prototype the scheduler first or the Tier 1 contract first.

My recommendation: start with **scheduler + Tier 1 contract**, because that is where the architecture becomes enforceable rather than aspirational.
