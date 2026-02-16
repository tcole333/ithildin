# Understanding Engine
## Design Document v1.1

### 1. Overview

The understanding engine transforms raw findings into multiple output modalities that collectively build a navigable, interlinked research tool. This is **not** a linear journalism pipeline — it produces reference material, explanatory writing, analytical depth, and visual output simultaneously, all served through a browsable web application.

**Output Modalities**:
1. **Wiki Dossiers** — Reference layer: entities, persons, organizations, mechanisms. Always current, auto-updated as new findings arrive. The foundation everything else links to.
2. **Mechanism Explainers** — How things work: trust structures, shell company layering, compliance failures, financial engineering. "Bits About Money" style — analytical, not biographical.
3. **Analytical Articles** — Why things happen: deep contextual pieces through specific lenses (financial forensics, geopolitics, legal enablement, intelligence tradecraft).
4. **Visual Outputs** — Network graphs, financial flow diagrams, timelines. Interactive where possible, static fallbacks for embedding.
5. **Cross-Thread Synthesis** — Connecting findings across the 6 investigation threads. Where Mega Group meets Deutsche Bank Pipeline meets Gulf State Operations.

**Broader Scope**: Content is organized around **themes and mechanisms**, not Epstein as biographical subject. Investigation threads are the primary navigation structure. Epstein is a well-documented central node in a systems investigation, not the subject of a profile.

### 2. Modality-Specific Flows

Each modality has its own trigger conditions, processing pipeline, and quality gates.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UNDERSTANDING ENGINE FLOWS                             │
└─────────────────────────────────────────────────────────────────────────────┘

WIKI DOSSIERS (continuous, event-driven)
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  New entity or  │────▶│ Dossier Writer  │────▶│  Fact Check     │
│  finding arrives│     │ (generate/update)│     │  (verify cites) │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────┐
                                                │  Publish to     │
                                                │  Web App        │
                                                └─────────────────┘

MECHANISM EXPLAINERS (pattern-triggered)
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Pattern detected│────▶│Explainer Writer │────▶│  Editor Review  │
│ or synthesis    │     │ (draft)         │     │  (clarity gate) │
│ milestone       │     └─────────────────┘     └────────┬────────┘
└─────────────────┘                                      │
                                               ┌────┬────┴────┐
                                               ▼    ▼         ▼
                                           APPROVE REVISE  REJECT

ANALYTICAL ARTICLES (milestone or request-triggered)
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Thread milestone│────▶│  Contextual     │────▶│  Editor Review  │
│ or user request │     │  Analyst (draft)│     │ (sourcing gate) │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                               ┌────┬────┴────┐
                                               ▼    ▼         ▼
                                           APPROVE REVISE  REJECT

VISUAL OUTPUTS (data-change-triggered)
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Graph/timeline  │────▶│  Export tool    │────▶│  Render + embed │
│ data changes    │     │  (structured)   │     │  in web app     │
└─────────────────┘     └─────────────────┘     └─────────────────┘

CROSS-THREAD SYNTHESIS (threshold-triggered)
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Finding burst   │────▶│  Synthesist     │────▶│  Route to       │
│ across threads  │     │  (cross-ref)    │     │  appropriate    │
└─────────────────┘     └─────────────────┘     │  modality       │
                                                └─────────────────┘
```

### 3. Stage Details

#### 3.1 Modality Triggers

Each modality activates under different conditions:

```python
class ModalityTriggers:
    """Determine when to generate each output type."""

    def on_finding_created(self, finding_id: int):
        finding = self.db.get_finding(finding_id)

        # Wiki dossiers: always update on new findings
        self.queue.spawn_job(
            job_type='wiki_dossier_update',
            domain='understanding',
            payload={
                'target_name': finding.target_name,
                'finding_id': finding_id,
                'update_type': 'incremental'
            },
            priority=4  # Background priority
        )

    def on_pattern_detected(self, pattern: dict):
        """Mechanism explainer trigger."""
        if pattern['type'] in ('structural', 'financial', 'operational'):
            if pattern['confidence'] >= 0.7:
                self.queue.spawn_job(
                    job_type='mechanism_explainer',
                    domain='understanding',
                    payload={
                        'pattern': pattern,
                        'mechanism_type': pattern['type'],
                        'supporting_findings': pattern['finding_ids']
                    },
                    priority=6
                )

    def on_thread_milestone(self, thread_id: int, milestone: dict):
        """Analytical article trigger."""
        self.queue.spawn_job(
            job_type='analytical_article',
            domain='understanding',
            payload={
                'thread_id': thread_id,
                'milestone': milestone,
                'lens': self.select_lens(thread_id, milestone)
            },
            priority=7
        )

    def on_graph_change(self, change: dict):
        """Visual output trigger."""
        if change['edges_added'] >= 10 or change['nodes_added'] >= 5:
            self.queue.spawn_job(
                job_type='visual_export',
                domain='understanding',
                payload={
                    'export_type': 'network_graph',
                    'scope': change.get('affected_subgraph', 'full'),
                    'format': 'interactive'
                },
                priority=3
            )

    def select_lens(self, thread_id: int, milestone: dict) -> str:
        """Pick analytical lens based on thread."""
        THREAD_LENSES = {
            1: 'operational',        # Core Network
            2: 'intelligence',       # Mega Group
            3: 'financial_forensics', # Deutsche Bank
            4: 'intelligence',       # Israeli Nexus
            5: 'financial_forensics', # Apollo/Black
            6: 'geopolitical'        # Gulf Operations
        }
        return THREAD_LENSES.get(thread_id, 'general')
```

#### 3.2 Wiki Dossier Pipeline

Dossiers are the **foundational reference layer**. Every entity, person, and organization gets a structured, interlinked page that stays current as findings accumulate.

**Job Specification**:

```json
{
  "job_type": "wiki_dossier_update",
  "domain": "understanding",
  "payload": {
    "target_name": "LSJE LLC",
    "target_type": "entity",
    "update_type": "incremental",
    "finding_id": 2345,
    "force_full_rebuild": false
  }
}
```

**Dossier Structure** (markdown with YAML frontmatter for web app):

```markdown
---
title: "LSJE LLC"
type: entity
entity_type: llc
jurisdiction: USVI
status: dissolved
thread_ids: [1, 5]
last_updated: 2026-02-16T14:30:00Z
finding_count: 47
connection_count: 23
related_entities:
  - name: "Little St. James Island"
    type: property
  - name: "Darren Indyke"
    type: person
  - name: "LSJE Holdings"
    type: entity
tags: [shell_company, usvi, property_holding]
---

# LSJE LLC

## Overview
Limited liability company registered in the US Virgin Islands. Primary holding
vehicle for Little St. James Island, the private island owned by Jeffrey Epstein.
Dissolved following Epstein's death in August 2019.

## Key Identifiers
- **Jurisdiction**: USVI
- **Registered Agent**: Darren Indyke (resigned 2019)
- **Officers**: Jeffrey Epstein, Darren Indyke
- **Address**: [address]

## Ownership Chain
```
LSJE LLC (USVI)
  └── LSJE Holdings (Delaware)
       └── Jeffrey Epstein (beneficial owner)
```

## Timeline
| Date | Event | Source |
|------|-------|--------|
| 2001-03-15 | Formation | USVI registry |
| 2018-12-06 | $330K sulfuric acid purchase | EFTA02336502 |
| 2019-08-10 | Dissolution proceedings begin | USVI filing |

## Financial Activity
- $330,000 sulfuric acid purchase (Dec 2018) [EFTA02336502]
- Property tax payments (USVI records)

## Connections
- **Darren Indyke**: Officer, registered agent [connection #234]
- **Richard Kahn**: Co-executor, related entity management [connection #235]
- **Little St. James Island**: Property held by this entity [connection #236]

## Sources
47 findings, 23 connections. Primary sources: USVI registry, DOJ EFTA documents.
Confidence: 12 confirmed, 25 high, 10 medium.
```

**Interlinking Logic**:

```python
class DossierInterlinker:
    def interlink(self, dossier_markdown: str) -> str:
        """Auto-link entity mentions to their dossier pages."""

        # Get all entities with dossier pages
        known_entities = self.db.get_all_entity_slugs()

        for entity_name, slug in known_entities:
            # Replace entity mentions with links (but not in frontmatter or headers)
            pattern = re.compile(
                rf'(?<!#\s)(?<!title:\s)(?<!\[)\b{re.escape(entity_name)}\b(?!\])',
                re.IGNORECASE
            )
            dossier_markdown = pattern.sub(
                f'[{entity_name}](/entities/{slug})',
                dossier_markdown,
                count=1  # Only link first mention per section
            )

        return dossier_markdown
```

**Freshness Tracking**:

```python
class DossierFreshness:
    def check_staleness(self, target_name: str) -> dict:
        """Check if dossier needs update."""

        dossier = self.get_dossier_metadata(target_name)
        if not dossier:
            return {'status': 'missing', 'action': 'full_build'}

        # Count findings since last update
        new_findings = self.db.query_one("""
            SELECT COUNT(*) as count FROM findings
            WHERE target_name = :target
              AND created_at > :last_updated
        """, {
            'target': target_name,
            'last_updated': dossier['last_updated']
        })

        if new_findings.count >= 5:
            return {'status': 'stale', 'action': 'incremental_update',
                    'new_findings': new_findings.count}
        elif new_findings.count > 0:
            return {'status': 'slightly_stale', 'action': 'queue_update',
                    'new_findings': new_findings.count}

        return {'status': 'current', 'action': 'none'}
```

#### 3.3 Mechanism Explainer Pipeline

Explainers describe **how structures work** — not who did what, but the mechanics of how money moves, how control is exercised, how compliance is circumvented.

**Job Specification**:

```json
{
  "job_type": "mechanism_explainer",
  "domain": "understanding",
  "payload": {
    "mechanism_type": "trust_structure",
    "title": "The Five-Tier Corporate Architecture",
    "pattern": {
      "description": "Recurring pattern of USVI LLC → DE holding → nominee officers → property",
      "finding_ids": [1234, 1567, 1890],
      "entities": ["LSJE LLC", "Maple Inc", "Nautilus LLC"]
    },
    "target_audience": "informed_general"
  }
}
```

**Explainer Structure**:

```markdown
---
title: "The Five-Tier Corporate Architecture"
type: explainer
mechanism: trust_structure
thread_ids: [1, 5]
related_dossiers: [lsje-llc, maple-inc, nautilus-llc]
last_updated: 2026-02-16T14:30:00Z
---

# The Five-Tier Corporate Architecture

## What This Is
[1-2 paragraph explanation of what mechanism this describes and why it matters]

## How It Works
[Step-by-step description of the mechanism, with diagrams where helpful]

### Layer 1: The Operating Entity
[Description with specific examples from findings]

### Layer 2: The Holding Company
[Description]

### Layer 3: The Trust Structure
[Description]

## Why It Matters
[What this mechanism enables — tax avoidance, asset protection, identity concealment]

## Where We See This
[Specific instances in the investigation where this pattern appears]

## What to Look For
[Investigative markers — what should trigger further investigation when seen]

## Sources
[All citations with EFTA IDs]
```

#### 3.4 Analytical Article Pipeline

Articles provide **deep contextual analysis** through a specific lens. Unlike dossiers (reference) or explainers (mechanism), articles argue a thesis supported by evidence.

**Analytical Lenses**:
| Lens | Focus | Example Article |
|------|-------|-----------------|
| `financial_forensics` | Money flows, transaction patterns, valuation anomalies | "The $158M Apollo Payment Stream" |
| `geopolitical` | State actor involvement, diplomatic leverage, intelligence ops | "Gulf State Three-Tier Access Structure" |
| `legal_enablement` | How legal professionals enabled the network | "The Compliance Failure Chain at Deutsche Bank" |
| `intelligence_tradecraft` | Recruitment patterns, control mechanisms, operational security | "Carbyne: Surveillance Tech as Network Infrastructure" |
| `operational` | Day-to-day logistics, scheduling, personnel management | "The Inner Circle: Groff-Indyke-Kahn Operating Triangle" |

**Context Assembly** (modality-aware):

```python
class ContextAssembler:
    def gather_for_modality(self, job_payload: dict) -> dict:
        """Assemble context appropriate to the output modality."""

        modality = job_payload.get('job_type')

        if modality == 'wiki_dossier_update':
            return self._gather_dossier_context(job_payload)
        elif modality == 'mechanism_explainer':
            return self._gather_explainer_context(job_payload)
        elif modality == 'analytical_article':
            return self._gather_article_context(job_payload)
        elif modality == 'visual_export':
            return self._gather_visual_context(job_payload)

    def _gather_dossier_context(self, payload: dict) -> dict:
        """All facts about a target — comprehensive, not selective."""
        target = payload['target_name']

        return {
            'findings': self.db.get_all_findings(target),
            'connections': self.db.get_connections(target),
            'entities': self.db.get_related_entities(target),
            'timeline': self.build_timeline(target),
            'existing_dossier': self.get_current_dossier(target)
        }

    def _gather_explainer_context(self, payload: dict) -> dict:
        """Mechanism examples + structural patterns — multiple instances."""
        pattern = payload['pattern']

        return {
            'pattern_instances': self.find_pattern_instances(pattern),
            'related_mechanisms': self.find_similar_mechanisms(pattern['type']),
            'supporting_findings': self.get_findings(pattern['finding_ids']),
            'structural_data': self.get_entity_structures(pattern['entities'])
        }

    def _gather_article_context(self, payload: dict) -> dict:
        """Thread-focused, lens-filtered context."""
        thread_id = payload['thread_id']
        lens = payload['lens']

        context = {
            'thread_findings': self.db.get_thread_findings(thread_id),
            'thread_connections': self.db.get_thread_connections(thread_id),
            'key_entities': self.db.get_thread_entities(thread_id)
        }

        # Lens-specific enrichment
        if lens == 'financial_forensics':
            context['financial_flows'] = self.get_financial_data(thread_id)
            context['transaction_timeline'] = self.build_financial_timeline(thread_id)
        elif lens == 'geopolitical':
            context['external_events'] = self.query_gdelt_for_thread(thread_id)
            context['state_actors'] = self.get_state_actor_connections(thread_id)

        return context
```

**Article Structure**:

```markdown
---
title: "The $158M Apollo Payment Stream"
type: article
lens: financial_forensics
thread_ids: [5]
related_dossiers: [leon-black, southern-trust-company, apollo-global]
last_updated: 2026-02-16T14:30:00Z
---

# The $158M Apollo Payment Stream

## Summary
[2-3 sentences: what this article argues and why it matters]

## The Structure
[How the financial arrangement worked — mechanics]

## The Evidence
[Chronological presentation of primary source evidence]

## The Context
[What else was happening — external events, legal proceedings]

## The Questions
[What remains unanswered — honest about gaps]

## Methodology
[How findings were verified, confidence levels, data sources]
```

#### 3.5 Visual Output Pipeline

Visual outputs are data exports rendered for the web application.

**Visual Types**:
| Type | Data Source | Rendering |
|------|-----------|-----------|
| Network graph | `graph_tools.py` exports | D3.js / Sigma.js (interactive) |
| Financial flow | DS10 + findings | Sankey diagram (D3) |
| Timeline | `event_timeline.py` exports | Timeline.js or custom |
| Entity tree | Registry data | Collapsible tree (D3) |
| Geographic map | Address/jurisdiction data | Leaflet.js |

**Export Job**:

```json
{
  "job_type": "visual_export",
  "domain": "understanding",
  "payload": {
    "export_type": "network_graph",
    "scope": "thread_5",
    "format": "interactive",
    "focus_entities": ["Leon Black", "Southern Trust Company", "Apollo Global"],
    "depth": 2,
    "output_format": "json"
  }
}
```

#### 3.6 Fact Checking (All Modalities)

Fact checking applies to all text modalities with modality-specific emphasis:

```python
class ModalityFactChecker:
    def check(self, content_path: str, modality: str) -> FactCheckReport:
        """Verify content with modality-appropriate rigor."""

        report = FactCheckReport()
        content = self.read_content(content_path)
        citations = self.extract_citations(content)

        # Core checks (all modalities)
        for citation in citations:
            result = self.verify_citation(citation)
            report.add_result(result)

        # Modality-specific checks
        if modality == 'wiki_dossier_update':
            report.completeness = self.check_completeness(content)
            report.link_integrity = self.check_links(content)

        elif modality == 'mechanism_explainer':
            report.mechanism_accuracy = self.verify_mechanism_description(content)
            report.clarity_score = self.assess_clarity(content)

        elif modality == 'analytical_article':
            report.source_proportions = self.calculate_proportions(citations)
            report.analytical_rigor = self.check_argument_structure(content)
            report.unsupported_claims = self.find_unsupported_claims(content, citations)

        return report
```

#### 3.7 Editor Review (Modality-Aware)

The Editor applies different quality dimensions per modality:

```python
class ModalityEditor:
    QUALITY_DIMENSIONS = {
        'wiki_dossier_update': {
            'factual_accuracy': 0.40,
            'completeness': 0.25,
            'link_integrity': 0.15,
            'currency': 0.10,
            'structure': 0.10
        },
        'mechanism_explainer': {
            'mechanism_accuracy': 0.30,
            'clarity': 0.30,
            'accessibility': 0.20,
            'sourcing': 0.10,
            'examples': 0.10
        },
        'analytical_article': {
            'sourcing_depth': 0.30,
            'analytical_rigor': 0.25,
            'factual_accuracy': 0.20,
            'novelty': 0.15,
            'coherence': 0.10
        }
    }

    def review(self, content_path: str, modality: str,
               fact_check: FactCheckReport) -> EditorDecision:
        """Quality control adapted per modality."""

        dimensions = self.QUALITY_DIMENSIONS[modality]
        scores = {}

        for dimension, weight in dimensions.items():
            scores[dimension] = self.score_dimension(
                content_path, dimension, fact_check
            )

        weighted_score = sum(
            scores[d] * dimensions[d] for d in dimensions
        )

        # Decision thresholds
        if weighted_score >= 8.0:
            return EditorDecision(decision='approve')
        elif weighted_score >= 5.5 and scores.get('factual_accuracy', 10) >= 7:
            return EditorDecision(
                decision='revise',
                notes=self.generate_revision_notes(scores, dimensions)
            )
        else:
            return EditorDecision(
                decision='reject',
                reason=self.explain_rejection(scores, dimensions)
            )
```

### 4. Web Application Integration

Each modality maps to the web application:

| Modality | Route Pattern | Update Frequency |
|----------|--------------|-----------------|
| Wiki dossiers | `/entities/{slug}` | On every finding |
| Mechanism explainers | `/explainers/{slug}` | When patterns detected |
| Analytical articles | `/analysis/{slug}` | On thread milestones |
| Visual outputs | `/graph`, `/timeline`, `/finances/{entity}` | On data changes |
| Thread overviews | `/threads/{id}` | Daily synthesis |

**Content Publishing Flow**:

```python
class WebPublisher:
    def publish(self, content_path: str, modality: str, metadata: dict):
        """Publish approved content to web application."""

        # Write to content directory (web app source)
        output_path = self.get_output_path(modality, metadata)

        # Apply interlinking
        content = self.read_content(content_path)
        content = self.interlinker.interlink(content)

        # Write with frontmatter
        self.write_content(output_path, content)

        # Update search index
        self.search_index.add(output_path, metadata)

        # Trigger web app rebuild (if static site)
        # or update database (if dynamic)
        self.trigger_rebuild()

    def get_output_path(self, modality: str, metadata: dict) -> str:
        MODALITY_DIRS = {
            'wiki_dossier_update': 'content/entities',
            'mechanism_explainer': 'content/explainers',
            'analytical_article': 'content/analysis',
            'visual_export': 'content/visuals'
        }
        directory = MODALITY_DIRS[modality]
        slug = metadata['slug']
        return f"{directory}/{slug}.md"
```

### 5. Content Metrics

Track output quality and coverage:

```python
class UnderstandingMetrics:
    def dashboard(self) -> dict:
        return {
            'dossiers': {
                'total': self.count_dossiers(),
                'stale': self.count_stale_dossiers(days=7),
                'avg_finding_count': self.avg_findings_per_dossier(),
                'coverage': self.entity_coverage_percentage()
            },
            'explainers': {
                'total': self.count_explainers(),
                'mechanisms_covered': self.list_covered_mechanisms(),
                'avg_clarity_score': self.avg_clarity()
            },
            'articles': {
                'total': self.count_articles(),
                'by_lens': self.count_by_lens(),
                'by_thread': self.count_by_thread(),
                'avg_sourcing_depth': self.avg_sourcing()
            },
            'visuals': {
                'graphs': self.count_graphs(),
                'timelines': self.count_timelines(),
                'last_updated': self.last_visual_update()
            },
            'web_app': {
                'total_pages': self.count_published_pages(),
                'internal_links': self.count_internal_links(),
                'search_index_size': self.search_index_size()
            }
        }
```

---

See next: `05-triage-dedupe-validation.md` for data quality systems
