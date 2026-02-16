# Autonomous Research Platform - Design Documentation

This directory contains comprehensive design documentation for transforming the Epstein OSINT investigation into a **multi-modal understanding engine** that produces interlinked wiki dossiers, mechanism explainers, analytical articles, and interactive visualizations — delivered through a browsable web application.

## Documents

### Core Architecture
- **[01-architecture-overview.md](01-architecture-overview.md)** - System architecture, workflows, and design principles
- **[02-queue-system-design.md](02-queue-system-design.md)** - Job queue schema, job types, and state machines

### Agent Specifications
- **[03-agent-personas.md](03-agent-personas.md)** - Detailed specifications for 12 agent personas across 5 tiers

### Workflows
- **[04-content-pipeline.md](04-content-pipeline.md)** - Understanding engine: multi-modal output pipeline with quality gates
- **[05-triage-dedupe-validation.md](05-triage-dedupe-validation.md)** - Data quality systems

### Implementation
- **[06-context-management.md](06-context-management.md)** - Context isolation and report submission patterns
- **[07-infra-integration.md](07-infra-integration.md)** - Integration with existing infrastructure
- **[08-implementation-phases.md](08-implementation-phases.md)** - Phased rollout plan (8 phases, 4-6 weeks)
- **[09-web-application.md](09-web-application.md)** - Web application design: routes, search, graphs, deployment

## Diagrams

Located in `diagrams/` directory:

- **system-architecture.mmd** - High-level system architecture (12 personas, web app output layer)
- **job-lifecycle.mmd** - Job state machine
- **content-pipeline.mmd** - Multi-modal content generation workflow
- **understanding-engine.mmd** - Understanding engine modality flows
- **deep-investigation-flow.mmd** - Parallel investigation pattern
- **trigger-system.mmd** - Event-driven automation

Render these with [Mermaid Live Editor](https://mermaid.live/) or VS Code Mermaid extension.

## Quick Start

For reviewers, read in this order:
1. **01-architecture-overview.md** - Get the big picture
2. **03-agent-personas.md** - Understand the specialized workers
3. **08-implementation-phases.md** - See the rollout plan

Then dive into specific areas of interest.

## Key Design Decisions

### Queue-Based Architecture
- All work represented as jobs in a queue (SQLite first, PostgreSQL at cutover)
- Agents claim jobs, execute, submit results
- No synchronous sub-agent calls (solves context bloat)

### Stateless Agents
- Agents are stateless workers
- All state in database and queue
- Easy to scale horizontally

### 12 Agent Personas
- **Tier 1 (Discovery)**: Surveyor, Pattern Spotter, Lead Triage
- **Tier 2 (Investigation)**: Entity Tracer, Deep Investigator, Document Miner
- **Tier 3 (Analysis)**: Network Analyst, Timeline Analyst, Systemic Analyst, Synthesist
- **Tier 4 (Understanding)**: Dossier Writer, Explainer Writer, Contextual Analyst, Editor
- **Tier 5 (Infrastructure)**: Tool Builder, Source Integrator, Registry Adder

### Multi-Modal Output
Five output types, all delivered through the web application:
1. **Wiki dossiers**: Always-current entity/person reference pages
2. **Mechanism explainers**: How structures work (trust layers, compliance gaps, shell companies)
3. **Analytical articles**: Deep pieces through financial/geopolitical/legal/intelligence lenses
4. **Visual outputs**: Interactive network graphs, timelines, financial flow diagrams
5. **Cross-thread synthesis**: Connecting findings across investigation threads

### Web Application
Browsable, searchable research tool — not a static report. Entity mentions auto-link to dossier pages. Investigation threads provide primary navigation. Full-text search across all content.

### Self-Sustaining Triggers
- Scheduled (cron): Regular scans, daily analysis
- Threshold: Finding bursts, queue depth
- Event-driven: New entities, high-confidence findings
- Pattern: Temporal clustering, network bridges
- Rate-limited: Max 10 triggered jobs/hour, max 3-hop trigger chains

### Validation Gates
1. Deduplication: Prevent redundant findings
2. Citation verification: Ensure sources exist and match
3. Confidence calibration: Enforce claim type ceilings
4. Modality-aware editorial review: Quality dimensions per output type

### Safety Controls
- `/halt` command: Pause all processing, agents drain current job
- Recursion limits: Max depth 2, max children 8 per parent
- Trigger budgets: Prevent runaway job spawning
- Cost tracking: Token usage, API calls, monthly budget projection

## Vision

A **multi-modal understanding engine** that:
- Continuously investigates entities and discovers patterns
- Generates interlinked wiki dossiers, mechanism explainers, and analytical articles
- Delivers output through a browsable web application
- Maintains rigorous evidence standards
- Scales horizontally through queue-based processing
- Treats Epstein as a central node in a systems investigation of elite network structures

---

**Status**: Revised per design review feedback (v1.1)
**Next Step**: Implementation planning
