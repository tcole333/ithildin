# Domain Lenses (Tier 2 Analytical Frameworks)

Structured but lightweight analytical frameworks that help agents recognize recurring patterns. Each lens is a named pattern with detection markers and grounding evidence.

**These frameworks are reference material, not analytical mandates.** They help you recognize patterns you might otherwise miss. They should never drive an investigation or filter what you see. If you find yourself forcing evidence into a framework, step back. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline` for the full policy.

Key principles:
- Evidence first, frameworks second — document what you find, then check if a pattern matches
- Actively seek counter-evidence and innocent explanations for any pattern you identify
- A framework that applies everywhere is too loose to be useful
- Never populate a "framework × subject" matrix — incomplete is honest, complete is suspicious
- Every framework application should include boundary conditions (when does it NOT apply?)

## Tier System

- **Tier 1 (Core Models):** Full spec in `content/models/*.json` with web pages, detection rules in `model_detector.py`, article callout blocks. See `analytical-models.md`.
- **Tier 2 (Domain Lenses):** Markdown files in this directory with YAML frontmatter. Used by agents for deeper analysis. Loaded by `model_detector.py` for detection.
- **Tier 3 (Reference Frameworks):** Curated citation list in `framework-references.md`. Academic/practitioner grounding agents can cite.

## Lens File Format

```yaml
---
name: Framework Name
slug: framework-slug
domain: financial-crime | org-theory | intelligence | network-science | behavioral | legal-regulatory | economic
source: "Author, 'Work Title' (Year)"
status: candidate | evaluated | adopted
created: YYYY-MM-DD
grounding_findings: [finding_id, finding_id, ...]
related_models: [model-slug, model-slug, ...]
# Governance fields (optional, added incrementally)
minimum_trigger: "Minimum evidence threshold before applying this framework"
anti_pattern: "What looks like this pattern but isn't — common false positives"
canonical_example: "Finding ID or brief description of the clearest known instance"
---

## Definition
2-3 paragraphs: what the framework is, how it applies to this investigation.

## Detection Markers
- Bulleted list of what agents should look for

## Boundary Conditions
- When does this framework NOT apply?
- What innocent scenarios look similar but aren't instances of this pattern?
- What baseline comparison makes instances notable? (e.g., "revolving door rate of X% vs. government-wide average of Y%")

## Limitations
- When this framework misleads or overreaches
- What confirmation bias risks does it create?
```

## Lifecycle

1. **Candidate:** Proposed by `/discover-frameworks` or agent `framework_candidate` hypotheses
2. **Evaluated:** Tested against 10+ findings — adds explanatory value existing models don't
3. **Adopted:** Detection markers added to `model_detector.py`, agents reference in analysis
4. **Promoted (rare):** Earns full Tier 1 treatment — JSON spec, web page, article callouts

## Domains

| Domain | Covers |
|--------|--------|
| `financial-crime` | AML typologies, laundering mechanics, structuring, beneficial ownership |
| `org-theory` | Regulatory capture, principal-agent, institutional isomorphism, deviance normalization |
| `intelligence` | Cutouts, dual-use infrastructure, kompromat, covert action |
| `network-science` | Advanced network metrics beyond current graph_tools.py |
| `behavioral` | Cognitive biases, moral disengagement, willful blindness |
| `legal-regulatory` | Prosecutorial discretion, DPA dynamics, privilege weaponization |
| `economic` | Rent-seeking, club goods, transaction costs, regulatory arbitrage theory |
