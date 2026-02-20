# Domain Lenses (Tier 2 Analytical Frameworks)

Structured but lightweight analytical frameworks that help research agents extract deeper insights from findings. Each lens is a named pattern with detection markers and grounding evidence from the investigation.

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
---

## Definition
2-3 paragraphs: what the framework is, how it applies to this investigation.

## Detection Markers
- Bulleted list of what agents should look for

## Limitations
- When this framework misleads or doesn't apply
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
