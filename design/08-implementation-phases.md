# Implementation Phases
## Design Document v1.1

### 1. Overview

This document outlines the phased implementation of the autonomous research platform. Each phase builds on the previous, with working functionality at every step.

**Principles**:
- Always have a working system
- Migrate incrementally, not big-bang
- Maintain backward compatibility during transition
- Validate each phase before proceeding

### 2. Phase Summary

| Phase | Duration | Focus | Key Deliverable |
|-------|----------|-------|-----------------|
| 0 | 1-2 days | Foundation | SQLite queue prototype + migration readiness |
| 1 | 3-5 days | Core Queue + Monitoring | Job queue, workers, /halt, basic dashboard |
| 2 | 5-7 days | Agent Workers | 4 core personas (Triage, Investigator, Tracer, Synthesist) |
| 3 | 5-7 days | Investigation Pipeline | Deep investigate via queue |
| 4 | 5-7 days | Wiki Dossier Layer | Auto-generated reference pages + web app scaffold |
| 5 | 3-5 days | Triggers + Rate Limiting | Self-sustaining behavior with safety controls |
| 6 | 3-5 days | Validation Gates | Dedupe, citation verification, confidence calibration |
| 7 | 5-7 days | Analytical Content + Web App | Explainers, articles, editor gate, web frontend |
| 8 | 2-4 days | PostgreSQL Cutover | Queue migration + final switch |

**Total Duration**: 4-7 weeks

#### Execution Strategy (SQLite-first, Postgres later)
- Phases 0-7 run on SQLite (`investigation.db`) to validate the job model with minimal infra.
- PostgreSQL cutover happens in Phase 8 once queue workers and web pipeline are stable.
- Existing CLI tools keep writing to SQLite until the cutover checklist is complete.

### 3. Phase 0: SQLite Foundation (Short-Term)

**Goal**: SQLite-based queue prototype and migration readiness

**Tasks**:
```
□ Add queue schema to investigation.db (SQLite)
  □ job_queue table
  □ job_dependencies table
  □ job_events table
  □ agent_instances table
  □ queue_metrics table
  □ system_state table

□ SQLite hardening
  □ WAL mode + busy_timeout default
  □ Retry wrapper for "database is locked"
  □ Periodic checkpoint / VACUUM plan

□ Create queue management library (SQLite backend)
  □ JobQueue class (claim, complete, fail)
  □ Job creation helpers
  □ Metrics collection

□ Postgres migration readiness
  □ Schema compatibility notes (JSONB, UUIDs, FTS)
  □ Export/import scaffolds (pgloader or custom)

□ Test infrastructure
  □ Unit tests for queue operations
  □ Integration tests (single worker + dispatcher)
```

**Validation**:
```python
# Test script
from queue_system import JobQueue

queue = JobQueue()

# Create job
job = queue.create_job(
    job_type='test',
    domain='system',
    payload={'test': True}
)

# Claim job
claimed = queue.claim_next(capabilities=['test'])
assert claimed.id == job.id

# Complete job
queue.complete_job(job.id, {'result': 'success'})

# Verify
completed = queue.get_job(job.id)
assert completed.status == 'completed'

print("✓ Phase 0 complete")
```

**Backward Compatibility**:
- SQLite `investigation.db` remains the system of record
- No dual-write until Phase 8 cutover
- Existing CLI tools keep writing to SQLite

---

### 4. Phase 1: Core Queue + Monitoring

**Goal**: Basic job queue with worker framework, monitoring, and halt controls

**Tasks**:
```
□ Implement job state machine
  □ PENDING → CLAIMED → IN_PROGRESS → COMPLETED
  □ FAILURE handling with retry
  □ BLOCKED → PENDING (dependency resolution)

□ Build agent worker framework
  □ AgentWorker base class
  □ Job claiming with capabilities
  □ Heartbeat mechanism
  □ Graceful shutdown
  □ system_state pause check in claim loop

□ Create 2 simple test personas
  □ EchoAgent (for testing)
  □ SurveyorAgent (basic implementation)

□ Build dispatcher
  □ Poll queue for work
  □ Spawn agent workers
  □ Monitor agent health

□ Create CLI tools
  □ submit-job (manual job submission)
  □ queue-status (view queue state)
  □ agent-status (view active agents)
  □ /halt and /resume commands

□ Basic monitoring
  □ Queue metrics sampling
  □ system_state table
  □ Stuck job detection
```

**Validation**:
```bash
# Submit test job
$ python -m queue_tools submit --type echo --payload '{"message": "hello"}'
Job submitted: uuid-1234

# Check queue
$ python -m queue_tools status
Pending: 1
In Progress: 0
Completed: 0

# Start agent
$ python -m agent_worker --persona echo --id test-agent-1 &

# Verify completion
$ python -m queue_tools status
Pending: 0
In Progress: 0
Completed: 1

$ python -m queue_tools show-job uuid-1234
Status: completed
Output: {"echo": "hello"}
```

---

### 5. Phase 2: Agent Workers

**Goal**: 4 core agent personas (the minimum set to run investigations autonomously)

**Tasks**:
```
□ Lead Triage Agent (includes dedupe)
  □ Priority scoring
  □ Duplicate detection (findings + leads)
  □ Routing decisions

□ Entity Tracer Agent
  □ Corporate registry traversal
  □ Financial flow tracing
  □ Recursive entity discovery

□ Deep Investigator Agent
  □ Multi-source investigation
  □ Report generation
  □ Child job spawning

□ Synthesist Agent
  □ Cross-reference findings
  □ Corroboration detection
  □ Insight generation
```

Remaining personas (Surveyor, Pattern Spotter, Network/Timeline/Systemic Analysts) are added in Phase 5 alongside triggers.

**Validation**:
```bash
# Submit entity trace job
$ python -m queue_tools submit \
    --type trace_entity \
    --payload '{"entity_name": "LSJE LLC"}'

# Submit lead triage job
$ python -m queue_tools submit \
    --type lead_triage \
    --payload '{"batch_size": 20}'

# Monitor progress
$ watch -n 5 'python -m queue_tools status --domain investigation'
```

---

### 6. Phase 3: Investigation Pipeline

**Goal**: Deep investigation via queue with parallel sub-agents

**Tasks**:
```
□ Refactor /deep-investigate skill
  □ Create orchestrator job
  □ Spawn 4 parallel child jobs
  □ Handle dependencies
  □ Synthesize results

□ Context isolation implementation
  □ Work directory creation
  □ Report generation
  □ Structured output files

□ Report reading utilities
  □ Summary extraction
  □ Section reading
  □ Finding loading

□ Synthesis job implementation
  □ Read child reports
  □ Identify corroboration
  □ Generate synthesis findings
  □ Spawn follow-up jobs

□ Test full pipeline
  □ Submit deep investigate job
  □ Verify 4 children spawned
  □ Verify synthesis runs after children complete
  □ Verify findings recorded
```

**Validation**:
```python
# Submit deep investigation
job_id = queue.create_job(
    job_type='deep_person',
    domain='investigation',
    payload={'target_name': 'Kathy Ruemmler'}
)

# Wait for completion (poll)
while True:
    status = queue.get_job_status(job_id)
    if status['status'] == 'completed':
        break
    time.sleep(10)

# Verify results
assert status['findings_count'] > 0
assert status['child_jobs_completed'] == 4
assert status['synthesis_completed']

print("✓ Phase 3 complete")
```

---

### 7. Phase 4: Wiki Dossier Layer

**Goal**: Auto-generated reference pages with web app scaffolding

This is the **foundational output layer**. Dossiers are the reference material that explainers and articles link to. Getting this right first means everything built later has a solid base to reference.

**Tasks**:
```
□ Dossier Writer Agent
  □ Generate wiki-style pages from entities + findings
  □ YAML frontmatter for web app metadata
  □ Incremental updates (add new findings without full rebuild)

□ Interlinking Logic
  □ Auto-link entity mentions to their dossier pages
  □ Related dossier discovery (shared officers, addresses, threads)

□ Freshness Tracking
  □ Track last_updated per dossier
  □ Flag when new findings available
  □ Scheduled freshness audit job

□ Editor Gate (dossier mode)
  □ Factual accuracy check (citations match)
  □ Completeness check (all findings incorporated)
  □ Link integrity check

□ Web App Scaffold
  □ Static site generator setup (Astro or Next.js)
  □ /entities/{slug} route for dossier pages
  □ Basic navigation and search
  □ Content build pipeline (markdown → HTML)

□ Initial Dossier Generation
  □ Generate dossiers for top 50 entities by finding count
  □ Verify interlinking works
  □ Serve locally for review
```

**Validation**:
```bash
# Submit dossier generation for high-value entity
$ python -m queue_tools submit --type wiki_dossier_update \
    --payload '{"target_name": "LSJE LLC", "update_type": "full"}'

# Verify dossier created
$ ls content/entities/
lsje-llc.md

# Verify interlinks resolve
$ grep -c '/entities/' content/entities/lsje-llc.md
5  # At least several internal links

# Verify web app serves
$ npm run dev  # Or equivalent
# Open http://localhost:3000/entities/lsje-llc
```

---

### 8. Phase 5: Triggers + Rate Limiting + Additional Agents

**Goal**: Self-sustaining behavior with safety controls

**Tasks**:
```
□ Trigger Engine
  □ Scheduled triggers (cron)
  □ Threshold triggers (finding bursts, queue depth)
  □ Event-driven triggers (new entities, patterns)
  □ Trigger rate limiting (10/hour budget, 3-hop chain max)

□ Additional Agent Personas
  □ Surveyor (source scanning + discovery)
  □ Pattern Spotter (weak signal detection)
  □ Network Analyst (graph analysis)
  □ Timeline Analyst (temporal patterns)
  □ Systemic Analyst (structural patterns)

□ Recursion Limits
  □ max_depth (default 2) on job trees
  □ max_children (default 8) per parent
  □ PARTIAL completion for partially-failed trees

□ Cost Tracking
  □ Token usage per job type
  □ API call counts per data source
  □ Monthly budget projection
  □ Priority-based throttling when budget tight

□ Auto-Scaling Rules
  □ Queue depth monitoring
  □ Agent pool scaling decisions
  □ Alert thresholds
```

**Validation**:
```bash
# Verify scheduled jobs
$ python -m trigger_engine run-scheduled
Created job: source_scan (scheduled)

# Verify trigger rate limiting
$ python -m trigger_engine check-thresholds
Trigger fired: finding_burst
Budget used: 3/10 this hour

# Verify recursion limits
$ python -m queue_tools show-job-tree <parent_id>
Depth: 2 (max 2), Children: 5 (max 8)
```

---

### 9. Phase 6: Validation Gates

**Goal**: Robust deduplication and citation verification

**Tasks**:
```
□ Duplicate Detection System
  □ Similarity scoring algorithm
  □ Finding comparison
  □ Merge decision logic
  □ Batch dedupe jobs

□ Citation Verification
  □ Document retrieval for verification
  □ Quote matching (exact + fuzzy for OCR)
  □ Page verification
  □ Verification report generation

□ Confidence Calibration
  □ Claim type rules enforcement
  □ Source tier classification
  □ Auto-adjust confidence ceilings

□ Automated Audit Jobs
  □ Daily citation spot checks
  □ Weekly dedupe reviews
  □ Monthly full audits
  □ Daily dossier freshness audit
```

**Validation**:
```python
# Test dedupe
similar = dedupe.find_similar_findings(threshold=0.85)
assert len(similar) > 0

# Test citation verification
result = verifier.verify_citation({
    'evidence_ref': 'EFTA02336502',
    'source_quote': 'Steve—I\'ve arranged the dinner'
})
assert result.status == 'verified'

print("Phase 6 complete")
```

---

### 10. Phase 7: Analytical Content + Web App

**Goal**: Full understanding engine with web application frontend

**Tasks**:
```
□ Explainer Writer Agent
  □ Mechanism detection triggers
  □ "Bits About Money" style output
  □ Concrete examples from investigation findings

□ Contextual Analyst Agent
  □ Lens-based analysis (financial, geopolitical, legal, intelligence)
  □ Thread milestone triggers
  □ 70%+ primary source requirement

□ Editor Gate (multi-modal)
  □ Modality-aware quality dimensions
  □ Different thresholds per output type
  □ Revision workflow

□ Web Application Frontend
  □ /entities/{slug} — wiki dossier pages
  □ /explainers/{slug} — mechanism explainers
  □ /analysis/{slug} — analytical articles
  □ /threads/{id} — investigation thread overviews
  □ /graph — interactive network visualization (D3.js/Sigma.js)
  □ /timeline — interactive timeline
  □ /finances/{entity} — financial flow diagrams

□ Web App Features
  □ Full-text search across all content
  □ Entity mention auto-linking
  □ Thread-based navigation
  □ Responsive design

□ Visual Output Rendering
  □ Network graph export → interactive D3/Sigma
  □ Timeline export → Timeline.js
  □ Financial flow export → Sankey diagrams

□ Production Polish
  □ Dashboard with queue + content metrics
  □ Alerting (stuck jobs, high failure rate, budget)
  □ Documentation
  □ Performance optimization
```

**Validation**:
```bash
# Submit explainer
$ python -m queue_tools submit --type mechanism_explainer \
    --payload '{"mechanism_type": "trust_structure"}'

# Submit analytical article
$ python -m queue_tools submit --type analytical_article \
    --payload '{"thread_id": 5, "lens": "financial_forensics"}'

# Verify editor review triggered
$ python -m queue_tools list-jobs --type editor_review --status pending

# Verify web app
$ npm run build && npm run preview
# Open http://localhost:3000
# Navigate entity pages, search, view graph

print("Phase 7 complete - Platform production ready")
```

---

### 11. Phase 8: PostgreSQL Cutover (Later Phase)

**Goal**: Move queue + workers to PostgreSQL without losing content or research

**Tasks**:
```
□ Provision PostgreSQL
  □ Create database 'osint_platform'
  □ Apply queue schema + supporting tables

□ Migrate data from SQLite
  □ leads, findings, connections, entities, notes, evidence
  □ job_queue, job_events, job_dependencies, agent_instances
  □ infra_requests, analysis_runs, sessions, search_log

□ Validate migration
  □ Row counts match (per-table)
  □ Spot-check critical leads/findings
  □ Search/index rebuilds verified

□ Switch application config
  □ Queue workers point to Postgres
  □ CLI tools read/write Postgres (or dual-write during burn-in)
  □ Dispatcher targets Postgres queue

□ Burn-in period
  □ Monitor errors, latency, queue depth
  □ Compare throughput against SQLite baseline
```

**Validation**:
```bash
# Smoke test
$ queue_tools submit --type echo --payload '{"message": "hello"}'
$ queue_tools status
# Verify job completes and appears in Postgres
```

---

### 12. Cutover Checklist (SQLite -> PostgreSQL Queue)

**Pre-cutover (T-1 to T-0):**
```
□ Schedule cutover window (no new jobs during window)
□ Stop dispatcher and any running agents
□ Ensure system_state.paused = true (no new claims)
□ Confirm queue is empty or all jobs are completed
□ Checkpoint SQLite WAL and close DB connections
□ Backup investigation.db (include -wal and -shm files)
□ Export SQLite dump (sqlite3 .dump) for reproducibility
□ Snapshot content and research directories:
  □ site/content/
  □ research/
  □ design/
  □ scripts/ and .claude/skills/
□ Record baseline counts and key metrics:
  □ leads, findings, connections, entities, job_queue
  □ infra_requests, analysis_runs, sessions, search_log
```

**Migration (T-0):**
```
□ Provision Postgres and apply schema migrations
□ Import SQLite data into Postgres (pgloader or custom)
□ Rebuild search indexes (Postgres FTS equivalents)
□ Run integrity checks (foreign keys, not-null, constraints)
□ Validate row counts against baseline snapshot
□ Spot-check 10-20 high-value findings for correctness
```

**Switch (T+0):**
```
□ Update config/env to point queue + tools to Postgres
□ Start queue workers with system_state.paused = true
□ Submit a test job and confirm end-to-end completion
□ Unpause system_state (resume job claiming)
□ Start dispatcher and monitor first wave
```

**Post-cutover (T+1 to T+3 days):**
```
□ Monitor error rates, latency, and queue depth
□ Compare throughput and failure rates to baseline
□ Verify web content pipeline still renders with existing content
□ Keep SQLite snapshot read-only for rollback window
```

**Content safety checks:**
```
□ Confirm site/content file counts match baseline
□ Rebuild backlinks/network exports and compare counts
□ Validate top dossiers still render (index + sample pages)
```

---

### 13. Rollback Plan

If issues arise, rollback to previous phase:

```bash
# Phase 8 → Phase 7
# Switch DB back to SQLite and restart dispatcher/workers
$ python -m config set DB_BACKEND=sqlite
$ python -m dispatcher stop && python -m dispatcher run

# Phase 6 → Phase 5
# Disable auto-triggers
$ python -m trigger_engine disable-all

# Phase 5 → Phase 4
# Disable validation gates
$ python -m config set VALIDATION_GATES=false

# Phase 4 → Phase 3
# Disable content pipeline
$ python -m config set CONTENT_PIPELINE=false

# Phase 3 → Phase 2
# Fall back to sync /deep-investigate
$ python -m config set ASYNC_INVESTIGATION=false

# Emergency: Full rollback to SQLite (restore from backup)
$ python -m migration rollback-to-sqlite
```

---

### 14. Success Criteria

#### Phase 0
- [ ] SQLite queue tables created in investigation.db
- [ ] WAL + busy_timeout defaults set
- [ ] Queue operations working in SQLite

#### Phase 1
- [ ] Jobs can be submitted and claimed
- [ ] Agent workers process jobs
- [ ] /halt pauses system, /resume restarts
- [ ] Basic queue metrics visible

#### Phase 2
- [ ] 4 core personas functional (Triage, Investigator, Tracer, Synthesist)
- [ ] Jobs complete successfully
- [ ] Findings recorded in DB

#### Phase 3
- [ ] Deep investigation via queue works
- [ ] 4 parallel sub-agents spawn correctly
- [ ] Synthesis produces insights

#### Phase 4
- [ ] Wiki dossiers auto-generated for top entities
- [ ] Interlinking works (entity mentions → dossier pages)
- [ ] Web app serves dossier pages locally
- [ ] Freshness tracking flags stale dossiers

#### Phase 5
- [ ] Triggers spawn jobs automatically with rate limiting
- [ ] Recursion limits prevent runaway spawning
- [ ] Cost tracking operational
- [ ] Additional analysis agents functional

#### Phase 6
- [ ] Duplicates detected and merged
- [ ] Citations verified
- [ ] Confidence calibrated
- [ ] Automated audits running on schedule

#### Phase 7
- [ ] Explainers and analytical articles generated
- [ ] Editor gate reviews all modalities
- [ ] Web app fully functional (search, graphs, threads)
- [ ] Platform stable for production

#### Phase 8
- [ ] Postgres queue schema applied
- [ ] Data migration verified vs baseline snapshot
- [ ] Workers running on Postgres without errors

---

### 15. Post-Implementation

After all phases complete:

```
□ Monitor for 1 week
  □ Daily queue metrics review
  □ Agent performance analysis
  □ Content output quality

□ Optimization pass
  □ Slow query identification
  □ Agent efficiency tuning
  □ Trigger threshold adjustment

□ Expand agent personas
  □ Additional analytical lenses
  □ Specialized investigators
  □ New analysis types

□ Add data sources
  □ Process infra queue backlog
  □ Integrate new registries
  □ Expand document corpus

□ Documentation
  □ User guide
  □ Agent development guide
  □ API documentation
```

---

## Appendix: File Structure

```
osint-research/
├── design/                      # Design documents (this directory)
│   ├── 01-architecture-overview.md
│   ├── 02-queue-system-design.md
│   ├── 03-agent-personas.md
│   ├── 04-content-pipeline.md   # Understanding Engine
│   ├── 05-triage-dedupe-validation.md
│   ├── 06-context-management.md
│   ├── 07-infra-integration.md
│   ├── 08-implementation-phases.md
│   ├── 09-web-application.md    # Web app design
│   └── diagrams/               # Architecture diagrams
│
├── queue_system/               # New queue infrastructure
│   ├── __init__.py
│   ├── models.py              # Job, Agent models
│   ├── queue.py               # JobQueue class
│   ├── triggers.py            # Trigger engine
│   ├── metrics.py             # Dashboard metrics
│   ├── costs.py               # Cost tracking
│   └── migrations/            # Database migrations
│
├── agents/                     # Agent implementations
│   ├── __init__.py
│   ├── base.py                # AgentWorker base class
│   ├── discovery/             # Discovery agents
│   │   ├── surveyor.py        # Includes source discovery
│   │   ├── pattern_spotter.py
│   │   └── lead_triage.py     # Includes dedupe
│   ├── investigation/         # Investigation agents
│   │   ├── tracer.py
│   │   ├── investigator.py
│   │   └── document_miner.py
│   ├── analysis/              # Analysis agents
│   │   ├── network_analyst.py
│   │   ├── timeline_analyst.py
│   │   ├── systemic_analyst.py
│   │   └── synthesist.py
│   ├── understanding/         # Understanding agents
│   │   ├── dossier_writer.py
│   │   ├── explainer_writer.py
│   │   ├── contextual_analyst.py
│   │   └── editor.py
│   └── infrastructure/        # Infrastructure agents
│       ├── tool_builder.py
│       ├── source_integrator.py
│       └── registry_adder.py
│
├── web/                        # Web application
│   ├── src/
│   │   ├── pages/             # Route pages
│   │   │   ├── entities/      # /entities/{slug}
│   │   │   ├── explainers/    # /explainers/{slug}
│   │   │   ├── analysis/      # /analysis/{slug}
│   │   │   ├── threads/       # /threads/{id}
│   │   │   └── graph.astro    # /graph (interactive)
│   │   ├── components/        # Shared UI components
│   │   └── layouts/           # Page layouts
│   ├── content/               # Published content (markdown)
│   │   ├── entities/
│   │   ├── explainers/
│   │   ├── analysis/
│   │   └── visuals/
│   └── public/                # Static assets
│
├── scripts/                    # Operational scripts
│   ├── dispatcher.py          # Main dispatcher
│   ├── agent_worker.py        # Agent worker entry point
│   ├── trigger_engine.py      # Trigger engine daemon
│   └── monitor.py             # Monitoring daemon
│
├── cli/                        # Command line tools
│   ├── queue_tools.py         # Queue management CLI
│   ├── agent_tools.py         # Agent management CLI
│   └── dashboard.py           # Dashboard CLI
│
└── tests/                      # Test suite
    ├── unit/                  # Unit tests
    ├── integration/           # Integration tests
    └── e2e/                   # End-to-end tests
```

---

## Ready for Review

This completes the design documentation. The next step is your review and feedback on:

1. **Architecture decisions** - Queue-based approach, SQLite-first with Postgres cutover
2. **Agent personas** - Which to prioritize, any missing
3. **Job types** - Sufficient coverage of workflows
4. **Implementation phases** - Duration estimates, sequencing
5. **Risk areas** - What could go wrong, mitigation strategies

Please review and provide feedback before we proceed to implementation.
