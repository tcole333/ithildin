# Ithildin: Architecture Overview
## Design Document v1.1

### 1. Vision

Transform the Epstein OSINT investigation into a **multi-modal understanding engine** that:

- Continuously investigates entities, discovers patterns, and generates insights
- Produces interlinked wiki dossiers, mechanism explainers, analytical articles, and interactive visualizations
- Delivers output through a **browsable web application** — a shareable research tool, not a static report
- Maintains rigorous evidence standards through automated validation
- Scales horizontally through queue-based async job processing
- Treats Epstein as a well-documented central node in a **systems investigation** of elite network structures — not a biographical subject

### 2. Core Design Principles

#### 2.1 Queue-Centric Architecture
All work is represented as jobs in a queue. Agents claim jobs, execute them, and submit outputs back to the queue. No synchronous sub-agent calls.

#### 2.2 Stateless Agents
Agents are stateless workers that process jobs idempotently. All state lives in the database and queue system.

#### 2.3 Event-Driven Triggers
The system responds to events (new findings, queue depth thresholds, scheduled times) by spawning new jobs autonomously.

#### 2.4 Validation Gates
All outputs pass through validation layers: deduplication, citation verification, and editorial review.

#### 2.5 Context Isolation
Each job execution is isolated with its own working directory and context window. Reports are written to disk and submitted to queues, not returned in conversation.

### 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL INTERFACES                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Human CLI  │  │  Web Hook   │  │  Scheduler  │  │  Data Source Ingest │ │
│  │  (commands) │  │  (external) │  │  (cron)     │  │  (new documents)    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JOB QUEUE LAYER                                │
│                     (PostgreSQL with job_queue schema)                      │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │  DISCOVERY  │  │INVESTIGATION│  │   ANALYSIS  │  │  UNDERSTANDING  │   │
│   │    Queue    │  │    Queue    │  │    Queue    │  │     Queue       │   │
│   │             │  │             │  │             │  │                 │   │
│   │ • source_   │  │ • trace_    │  │ • network_  │  │ • wiki_dossier_ │   │
│   │   scan      │  │   entity    │  │   analysis  │  │   update        │   │
│   │ • gap_      │  │ • deep_     │  │ • timeline_ │  │ • mechanism_    │   │
│   │   analysis  │  │   person    │  │   correlation│  │   explainer    │   │
│   │ • pattern_  │  │ • document_ │  │ • hunch_    │  │ • analytical_  │   │
│   │   trigger   │  │   mine      │  │   generation│  │   article      │   │
│   │ • lead_     │  │ • verify_   │  │ • systemic_ │  │ • visual_      │   │
│   │   triage    │  │   finding   │  │   analysis  │  │   export       │   │
│   │ • dedupe_   │  │             │  │ • synthesis │  │ • editor_review│   │
│   │   review    │  │             │  │             │  │                 │   │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     INFRASTRUCTURE QUEUE                            │   │
│   │  • tool_build  • bug_fix  • source_integration  • registry_add      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENT WORKER POOL                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         DISCOVERY AGENTS                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │    │
│  │  │  Surveyor   │  │   Pattern   │  │ Lead Triage │                 │    │
│  │  │ (scan +     │  │   Spotter   │  │ (route +    │                 │    │
│  │  │  sources)   │  │ (detect     │  │  dedupe)    │                 │    │
│  │  │             │  │  patterns)  │  │             │                 │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      INVESTIGATION AGENTS                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │    │
│  │  │   Entity    │  │    Deep     │  │  Document   │                 │    │
│  │  │   Tracer    │  │ Investigator│  │   Miner     │                 │    │
│  │  │ (financial  │  │ (person     │  │ (corpus     │                 │    │
│  │  │  structures)│  │  profiles)  │  │  search)    │                 │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        ANALYSIS AGENTS                              │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │    │
│  │  │  Network    │  │   Timeline  │  │   Systemic  │  │  Synthesist│ │    │
│  │  │  Analyst    │  │   Analyst   │  │   Analyst   │  │            │ │    │
│  │  │ (graph      │  │ (temporal   │  │ (structural │  │ (cross-ref │ │    │
│  │  │  theory)    │  │  patterns)  │  │  patterns)  │  │  findings) │ │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      UNDERSTANDING AGENTS                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │    │
│  │  │  Dossier    │  │  Explainer  │  │ Contextual  │  │   Editor   │ │    │
│  │  │  Writer     │  │  Writer     │  │  Analyst    │  │ (quality   │ │    │
│  │  │ (wiki       │  │ (mechanisms)│  │ (deep       │  │  gate,     │ │    │
│  │  │  pages)     │  │             │  │  analysis)  │  │  all modes)│ │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      INFRASTRUCTURE AGENTS                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │   Tool      │  │   Source    │  │   Registry  │                  │    │
│  │  │   Builder   │  │   Integrator│  │   Adder     │                  │    │
│  │  │             │  │             │  │             │                  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                     │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │investigation│  │   Source    │  │    Graph    │  │   Content       │   │
│   │     db      │  │    DBs      │  │   Store     │  │   Store         │   │
│   │             │  │             │  │             │  │                 │   │
│   │• leads      │  │• DOJ Vol 11 │  │• Neo4j     │  │• entities/      │   │
│   │• findings   │  │• LMSBAND    │  │• NetworkX  │  │• explainers/    │   │
│   │• connections│  │• ICIJ       │  │   exports   │  │• analysis/      │   │
│   │• entities   │  │• etc.       │  │             │  │• visuals/       │   │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WEB APPLICATION                                   │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │  /entities  │  │ /explainers │  │  /analysis  │  │  /graph         │   │
│   │  Wiki       │  │  Mechanism  │  │  Deep       │  │  /timeline      │   │
│   │  Dossiers   │  │  Explainers │  │  Articles   │  │  /finances      │   │
│   │             │  │             │  │             │  │  Interactives   │   │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
│                                                                             │
│   Search (full-text) │ Thread Navigation │ Entity Interlinking              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4. Job Lifecycle

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  PENDING │────▶│ CLAIMED  │────▶│ IN_PROG  │────▶│ COMPLETE │────▶│ ARCHIVED │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
      │                │               │                │
      │                │               │                │
      ▼                ▼               ▼                ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  STALE   │     │  FAILED  │     │  BLOCKED │     │ AWAITING │
│(timeout) │     │(retry?)  │     │(deps)    │     │  REVIEW  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### 5. Key Workflows

#### 5.1 Discovery → Investigation Pipeline

```
Scheduled Trigger (every 6h)
         │
         ▼
┌─────────────────┐
│  Surveyor Agent │
│  (scan sources) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  New entities   │────▶│  Lead Triage    │
│  detected?      │     │  (dedupe,       │
└─────────────────┘     │  prioritize)    │
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │  DISCARD  │ │   OPEN    │ │  DEFER    │
            │ (duplicate)│  │ (investigate)│ │ (low prio) │
            └───────────┘ └─────┬─────┘ └───────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │ Spawn jobs:   │
                        │ • trace_entity│
                        │ • deep_person │
                        └───────────────┘
```

#### 5.2 Investigation → Analysis Pipeline

```
Investigation Job Complete
         │
         ▼
┌─────────────────┐
│ Pattern Spotter │
│ (scan findings) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Threshold check:                    │
│ • 10+ new findings in 4h?           │
│ • New high-centrality node?         │
│ • Temporal clustering detected?     │
└─────────────────────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────────┐
│  No   │ │   Yes     │
└───────┘ └─────┬─────┘
                │
                ▼
    ┌───────────────────────┐
    │ Spawn analysis jobs:  │
    │ • network_analysis    │
    │ • timeline_correlation│
    │ • hunch_generation    │
    │ • synthesis           │
    └───────────────────────┘
```

#### 5.3 Analysis → Understanding Pipeline

```
Analysis/Synthesis Complete
         │
         ▼
┌─────────────────────────────────────┐
│ Route to modality by trigger type:  │
│                                     │
│ • New finding/entity → Dossier      │
│ • Structural pattern → Explainer    │
│ • Thread milestone  → Article       │
│ • Graph change      → Visual        │
└──────────┬──────────────────────────┘
           │
    ┌──────┼──────┬──────┐
    ▼      ▼      ▼      ▼
┌───────┐┌───────┐┌───────┐┌───────┐
│Dossier││Explain││Article││Visual │
│Writer ││Writer ││Analyst││Export │
└───┬───┘└───┬───┘└───┬───┘└───┬───┘
    │        │        │        │
    ▼        ▼        ▼        ▼
┌───────────────────────────────────┐
│     Editor Review (per modality)  │
│  Dossiers: accuracy + completeness│
│  Explainers: clarity + accuracy   │
│  Articles: sourcing + rigor       │
│  Visuals: data integrity          │
└──────────────┬────────────────────┘
               │
    ┌────┬─────┴─────┐
    ▼    ▼           ▼
APPROVE REVISE    REJECT
    │    │           │
    ▼    ▼           ▼
Publish  Return to   Archive
to Web   writer
App
```

### 6. Context Management Strategy

The key insight: **Sub-agents write reports to disk, submit to queue, orchestrator reads reports from disk.**

```
Old Pattern (Current):
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator                                                    │
│  1. Spawn Agent A ────────────────────────────┐                 │
│  2. Wait for completion ◄─────────────────────┘ (blocking)      │
│  3. Read TaskOutput (25MB context bloat)                        │
│  4. Spawn Agent B based on results                              │
│  5. Wait...                                                     │
└─────────────────────────────────────────────────────────────────┘

New Pattern (Target):
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator                                                    │
│  1. Create job: investigation_job_X                            │
│  2. Spawn Agent A with job_id=X (non-blocking)                  │
│  3. Agent A writes report to /jobs/X/report.md                  │
│  4. Agent A completes job, submits findings to queue            │
│  5. Orchestrator moves on immediately                           │
│                                                                 │
│ Later: Analysis agent claims completed job X                    │
│  - Reads /jobs/X/report.md (2KB, not 25MB)                      │
│  - Performs synthesis                                           │
│  - Submits new job to understanding queue                       │
└─────────────────────────────────────────────────────────────────┘
```

### 7. Validation & Quality Gates

```
All findings pass through:

┌─────────────────────────────────────────────────────────────┐
│ 1. DEDUPLICATION GATE                                       │
│    • Check finding_evidence junction table                  │
│    • Fuzzy match on target_name + summary                   │
│    • Reject if similarity > 0.85                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼ (if new)
┌─────────────────────────────────────────────────────────────┐
│ 2. CITATION VERIFICATION GATE                               │
│    • Evidence ref must exist in source DB                   │
│    • Source quote must match document text                  │
│    • Claim type must match confidence ceiling               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼ (if valid)
┌─────────────────────────────────────────────────────────────┐
│ 3. CONFIDENCE CALIBRATION GATE                              │
│    • direct_quote + primary_source → confirmed              │
│    • paraphrase → max high                                  │
│    • inference/synthesis → max medium                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼ (if passes)
┌─────────────────────────────────────────────────────────────┐
│ 4. EDITORIAL GATE (modality-specific)                       │
│    Dossiers: factual accuracy, completeness, link integrity │
│    Explainers: mechanism accuracy, clarity, accessibility   │
│    Articles: sourcing depth, analytical rigor, novelty      │
│    Visuals: data integrity, readability, entity resolution  │
└─────────────────────────────────────────────────────────────┘
```

### 8. Scaling Strategy

```
Horizontal Scaling:
┌─────────────────────────────────────────────────────────────┐
│  Agent Worker Pool                                          │
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │Agent-1  │ │Agent-2  │ │Agent-3  │ │Agent-N  │          │
│  │(persona│ │(persona│ │(persona│ │(persona│          │
│  │:tracer)│ │:tracer)│ │:miner) │ │:editor)│          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘          │
│       └───────────┴───────────┴───────────┘                │
│                   │                                         │
│                   ▼                                         │
│           ┌──────────────┐                                 │
│           │  Job Queue   │                                 │
│           │  (PostgreSQL)│                                 │
│           └──────────────┘                                 │
└─────────────────────────────────────────────────────────────┘

Auto-scaling rules:
- Queue depth > 100 → spawn 2 additional agents
- Queue depth > 500 → spawn 5 additional agents + alert human
- Processing latency > 5 min → check for stuck jobs
- Agent failure rate > 10% → pause queue, alert human
```

### 9. Integration Points

#### 9.1 Existing Infrastructure
- **investigation.db**: Extended with job_queue tables, remains source of truth for findings/entities
- **Existing tools**: Wrapped as job processors, CLI interfaces maintained for human use
- **Skills**: Converted to job definitions, slash commands become job submission interfaces

#### 9.2 External Systems
- **Neo4j**: Network analysis reads from/writes to graph store
- **Document databases**: DOJ, LMSBAND, etc. remain as read-only sources
- **Web Application**: Dossiers, explainers, articles, and visuals published to browsable web app (see `09-web-application.md`)

### 10. Failure Modes & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Agent crash | Heartbeat timeout | Requeue job, restart agent |
| Database unavailable | Connection error | Retry with backoff, alert human |
| Source API down | HTTP error in job | Mark source degraded, requeue with delay |
| Stuck job (infinite loop) | Timeout threshold | Kill agent, mark failed, alert human |
| Citation verification fail | Mismatched quote | Reject finding, notify originating agent |
| Duplicate finding | Similarity detection | Merge or discard, update originating agent |
| Runaway job spawning | Recursion depth exceeded | Mark parent PARTIAL, stop spawning |
| Budget overrun | Token/API tracking | Priority-based throttling, alert human |
| **System halt** | Human `/halt` command | `system_state.paused = true`, agents drain current job then stop |

---

## Next Steps

1. Review this architecture overview
2. Read detailed design documents for each subsystem
3. Approve/modify/reject architectural decisions
4. Proceed to implementation phase planning

See: `02-queue-system-design.md` for queue schema and job types
