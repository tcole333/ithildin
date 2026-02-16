# Queue System Design
## Design Document v1.0

### 1. Overview

The queue system is the central nervous system of Ithildin. All work is represented as jobs that flow through queues, are claimed by agents, executed, and completed. Jobs can spawn child jobs and depend on other jobs.

**Technology Choice**: PostgreSQL with advisory locks for job claiming. This provides:
- ACID guarantees for job state transitions
- JSONB for flexible job payloads
- Native NOTIFY/LISTEN for event-driven triggers
- No additional infrastructure (already using SQLite, upgrading to PostgreSQL)

**SQLite-first execution (Phase 0-7)**: Implement the same schema in SQLite for early rollout,
then cut over to PostgreSQL once the queue/worker pipeline is stable.

### 2. Database Schema

#### 2.1 Core Job Queue Table

```sql
-- Main job queue table
CREATE TABLE job_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Job classification
    job_type VARCHAR(64) NOT NULL,
    domain VARCHAR(32) NOT NULL CHECK (domain IN (
        'discovery', 'investigation', 'analysis', 'understanding',
        'curation', 'infrastructure', 'system'
    )),
    
    -- Priority and scheduling
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'claimed', 'in_progress', 'awaiting_review',
        'completed', 'failed', 'blocked', 'stale', 'cancelled'
    )),
    
    -- Job payload and output
    payload JSONB NOT NULL DEFAULT '{}',
    output JSONB DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    error_traceback TEXT DEFAULT NULL,
    
    -- Job relationships
    parent_job_id UUID REFERENCES job_queue(id) ON DELETE SET NULL,
    thread_id UUID REFERENCES job_queue(id) ON DELETE SET NULL,  -- Root job of thread
    
    -- Agent assignment
    claimed_by VARCHAR(128) DEFAULT NULL,  -- Agent instance ID
    claimed_at TIMESTAMP DEFAULT NULL,
    started_at TIMESTAMP DEFAULT NULL,
    completed_at TIMESTAMP DEFAULT NULL,
    
    -- Retry logic
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 300,  -- 5 min default
    
    -- Timeouts and staleness
    timeout_seconds INTEGER DEFAULT 1800,  -- 30 min default
    stale_after TIMESTAMP DEFAULT NULL,  -- When to consider stuck
    
    -- Scheduling
    scheduled_for TIMESTAMP DEFAULT NULL,  -- Delayed execution
    cron_expression VARCHAR(64) DEFAULT NULL,  -- Recurring jobs
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(128) DEFAULT NULL,  -- Human or agent
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Context isolation
    workdir_path VARCHAR(512) DEFAULT NULL,  -- Unique temp directory
    
    -- Source tracking for traceability
    source_trigger VARCHAR(64) DEFAULT NULL,  -- What spawned this
    source_finding_id INTEGER DEFAULT NULL,  -- Related finding
    source_lead_id INTEGER DEFAULT NULL,  -- Related lead
    
    -- Search log integration
    search_queries TEXT[] DEFAULT ARRAY[]::TEXT[],  -- Queries run during job
    
    -- Indexes
    CONSTRAINT valid_timeout CHECK (timeout_seconds > 0),
    CONSTRAINT valid_retry CHECK (attempts <= max_attempts)
);

-- Indexes for efficient querying
CREATE INDEX idx_job_queue_status_priority ON job_queue(status, priority DESC, created_at);
CREATE INDEX idx_job_queue_type_pending ON job_queue(job_type) WHERE status = 'pending';
CREATE INDEX idx_job_queue_domain_pending ON job_queue(domain) WHERE status = 'pending';
CREATE INDEX idx_job_queue_claimed ON job_queue(claimed_by) WHERE status = 'in_progress';
CREATE INDEX idx_job_queue_parent ON job_queue(parent_job_id);
CREATE INDEX idx_job_queue_thread ON job_queue(thread_id);
CREATE INDEX idx_job_queue_scheduled ON job_queue(scheduled_for) WHERE scheduled_for IS NOT NULL;
CREATE INDEX idx_job_queue_tags ON job_queue USING GIN(tags);
CREATE INDEX idx_job_queue_payload ON job_queue USING GIN(payload jsonb_path_ops);

-- Partial index for pending jobs (most queried)
CREATE INDEX idx_job_queue_pending ON job_queue(status, priority DESC, created_at) 
    WHERE status = 'pending';
```

#### 2.2 Job Dependencies

```sql
-- Track job dependencies (job A blocks on job B)
CREATE TABLE job_dependencies (
    job_id UUID NOT NULL REFERENCES job_queue(id) ON DELETE CASCADE,
    depends_on_job_id UUID NOT NULL REFERENCES job_queue(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id, depends_on_job_id)
);

-- Index for finding jobs that can now proceed
CREATE INDEX idx_job_dependencies_blocked ON job_dependencies(depends_on_job_id);
```

#### 2.3 Job Events (Audit Log)

```sql
-- All state changes and significant events
CREATE TABLE job_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES job_queue(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL CHECK (event_type IN (
        'created', 'claimed', 'started', 'progress', 'completed', 
        'failed', 'blocked', 'unblocked', 'stale', 'cancelled',
        'retry_scheduled', 'spawned_child', 'dependency_added'
    )),
    payload JSONB DEFAULT NULL,  -- Event-specific data
    agent_id VARCHAR(128) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_events_job ON job_events(job_id, created_at DESC);
CREATE INDEX idx_job_events_type ON job_events(event_type, created_at DESC);
```

#### 2.4 Agent Registry

```sql
-- Track active agent instances
CREATE TABLE agent_instances (
    id VARCHAR(128) PRIMARY KEY,  -- UUID or hostname+pid
    persona VARCHAR(64) NOT NULL,
    status VARCHAR(32) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'stopped')),
    current_job_id UUID REFERENCES job_queue(id) ON DELETE SET NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    jobs_completed INTEGER DEFAULT 0,
    jobs_failed INTEGER DEFAULT 0,
    capabilities TEXT[] DEFAULT ARRAY[]::TEXT[],  -- Job types this agent can handle
    version VARCHAR(32) DEFAULT '1.0.0'
);

CREATE INDEX idx_agent_instances_status ON agent_instances(status, last_heartbeat);
```

#### 2.5 Queue Statistics

```sql
-- For monitoring and auto-scaling decisions
CREATE TABLE queue_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sampled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Queue depth by status
    pending_count INTEGER DEFAULT 0,
    claimed_count INTEGER DEFAULT 0,
    in_progress_count INTEGER DEFAULT 0,
    awaiting_review_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    
    -- Queue depth by domain
    discovery_pending INTEGER DEFAULT 0,
    investigation_pending INTEGER DEFAULT 0,
    analysis_pending INTEGER DEFAULT 0,
    understanding_pending INTEGER DEFAULT 0,
    infrastructure_pending INTEGER DEFAULT 0,
    
    -- Processing metrics (last hour)
    jobs_completed_1h INTEGER DEFAULT 0,
    jobs_failed_1h INTEGER DEFAULT 0,
    avg_processing_time_seconds FLOAT DEFAULT 0,
    
    -- Agent metrics
    active_agents INTEGER DEFAULT 0,
    idle_agents INTEGER DEFAULT 0,
    
    -- Alert flags
    has_stuck_jobs BOOLEAN DEFAULT FALSE,
    has_failed_jobs BOOLEAN DEFAULT FALSE,
    queue_depth_critical BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_queue_metrics_time ON queue_metrics(sampled_at DESC);
```

### 3. Job Types Reference

#### 3.1 Discovery Domain

| Job Type | Description | Typical Payload | Output |
|----------|-------------|-----------------|--------|
| `source_scan` | Scan data source for new/updated records | `{"source": "doj_vol11", "scan_type": "incremental", "since": "2026-02-10T00:00:00Z"}` | List of new document IDs |
| `gap_analysis` | Identify coverage gaps in investigation | `{"target_types": ["person", "entity"], "min_findings_threshold": 5}` | Gap report with targets |
| `pattern_trigger` | Detect patterns suggesting investigation | `{"pattern_type": "temporal_clustering", "window_days": 7}` | Pattern matches with confidence |
| `lead_triage` | Process incoming leads from any source | `{"lead_source": "auto", "batch_size": 20}` | Triage decisions per lead |
| `dedupe_review` | Review potential duplicate findings | `{"finding_ids": [123, 456], "similarity_score": 0.92}` | Merge or keep separate decision |
| `coverage_audit` | Check investigation coverage density | `{"node_ids": [...], "min_connections": 3}` | Underinvestigated nodes list |

#### 3.2 Investigation Domain

| Job Type | Description | Typical Payload | Output |
|----------|-------------|-----------------|--------|
| `trace_entity` | Exhaustive corporate/financial tracing | `{"entity_name": "LSJE LLC", "jurisdictions": ["USVI", "DE"], "depth": 3}` | Entity report with ownership chain |
| `deep_person` | Comprehensive person investigation | `{"person_name": "Kathy Ruemmler", "context": "Goldman Sachs GC", "threads": ["financial", "political"]}` | Person dossier |
| `document_mine` | Mine specific document corpus | `{"query": "Churkin Russia", "sources": ["doj", "duggan"], "limit": 100}` | Relevant documents with extracts |
| `verify_finding` | Verify citation and accuracy | `{"finding_id": 789, "check_quote": true}` | Verification report |
| `source_discovery` | Find new data sources | `{"domain": "corporate_registry", "jurisdiction": "Cayman"}` | Source recommendations |
| `cross_reference` | Cross-check finding across sources | `{"finding_id": 789, "target_sources": ["lmsband", "unified"]}` | Corroboration or contradiction report |

#### 3.3 Analysis Domain

| Job Type | Description | Typical Payload | Output |
|----------|-------------|-----------------|--------|
| `network_analysis` | Graph-theoretic network analysis | `{"analysis_type": "centrality", "subgraph": "epstein_core"}` | Metrics report, visualizations |
| `timeline_correlation` | Find temporal patterns | `{"date_range": ["2018-01-01", "2019-07-01"], "granularity": "day"}` | Correlation events, suspicious timing |
| `hunch_generation` | Generate investigation hypotheses | `{"seed_findings": [123, 456, 789], "min_confidence": 0.6}` | Hypothesis list with evidence chains |
| `systemic_analysis` | Structural pattern recognition | `{"pattern_type": "jurisdiction_clustering", "min_entities": 5}` | Structural insights |
| `synthesis` | Cross-reference multiple findings | `{"finding_ids": [123, 456, 789], "synthesis_type": "narrative"}` | Combined insight |
| `contradiction_check` | Identify conflicting findings | `{"target": "Kathy Ruemmler", "time_window": "2018-2019"}` | Contradiction report |

#### 3.4 Understanding Domain

| Job Type | Description | Typical Payload | Output |
|----------|-------------|-----------------|--------|
| `wiki_dossier_update` | Generate/update wiki-style reference page | `{"target_name": "LSJE LLC", "target_type": "entity", "update_type": "incremental", "finding_id": 2345}` | Dossier markdown with frontmatter |
| `mechanism_explainer` | Explain how a structural mechanism works | `{"mechanism_type": "trust_structure", "title": "Five-Tier Corporate Architecture", "pattern": {...}}` | Explainer markdown |
| `analytical_article` | Deep contextual analysis through a lens | `{"thread_id": 5, "lens": "financial_forensics", "milestone": {...}}` | Article markdown with citations |
| `visual_export` | Export graph/timeline/flow for web app | `{"export_type": "network_graph", "scope": "thread_5", "format": "interactive"}` | Structured JSON for rendering |
| `editor_review` | Modality-aware quality control gate | `{"content_path": "/content/entities/lsje-llc.md", "modality": "wiki_dossier_update"}` | Review decision with dimension scores |
| `fact_check` | Verify citations across any modality | `{"content_path": "...", "modality": "analytical_article", "spot_check_count": 10}` | Fact check report |

#### 3.5 Curation Domain

| Job Type | Description | Typical Payload | Output |
|----------|-------------|-----------------|--------|
| `finding_audit` | Batch verify findings | `{"confidence_filter": "unverified", "batch_size": 50}` | Audit report |
| `connection_review` | Review connection strength | `{"connection_ids": [123, 456], "evidence_review": true}` | Connection validation |
| `entity_merge` | Merge duplicate entities | `{"entity_ids": [101, 102], "similarity_evidence": [...]}` | Merge report |
| `tag_propagation` | Auto-tag based on patterns | `{"pattern": "goldman_sachs", "auto_apply": false}` | Tag suggestions |
| `archive_stale` | Archive old low-value jobs | `{"older_than_days": 90, "status": "dead_end"}` | Archive count |

#### 3.6 Infrastructure Domain

| Job Type | Description | Typical Payload | Output |
|----------|-------------|-----------------|--------|
| `tool_build` | Build new tool/integration | `{"tool_type": "query", "target_source": "courtlistener_api"}` | Tool code + tests |
| `bug_fix` | Fix identified tool bug | `{"tool_name": "query_doj.py", "bug_description": "...", "error_logs": "..."}` | Fix commit |
| `source_ingest` | Ingest new data source | `{"source_type": "990_xml", "data_path": "/datasets/irs990/"}` | Ingest report |
| `registry_add` | Add corporate registry | `{"jurisdiction": "Delaware", "api_type": "web_scrape"}` | Registry integration |
| `index_optimize` | Optimize search indexes | `{"table": "findings", "index_type": "fts5"}` | Optimization report |

### 4. Job State Machine

```
                         ┌─────────────┐
                         │   PENDING   │◄─────────────────────────┐
                         │  (queued)   │                          │
                         └──────┬──────┘                          │
                                │ claim()                          │
                                ▼                                  │
                         ┌─────────────┐     timeout/heartbeat    │
         ┌──────────────▶│   CLAIMED   │──────────────────────────┤
         │               │ (reserved)  │     lost                 │
         │               └──────┬──────┘                          │
         │                      │ start()                          │
         │                      ▼                                  │
         │               ┌─────────────┐     exception             │
         │    ┌─────────│ IN_PROGRESS │─────────────────────┐     │
         │    │         │ (executing) │                     │     │
         │    │         └──────┬──────┘                     │     │
         │    │                │                           │     │
         │    │         ┌──────┴──────┐                   │     │
         │    │         │             │                   │     │
         │    │         ▼             ▼                   │     │
         │    │   ┌──────────┐  ┌──────────┐             │     │
         │    │   │ COMPLETE │  │  AWAIT   │             │     │
         │    │   │ (output) │  │ _REVIEW  │             │     │
         │    │   └────┬─────┘  └────┬─────┘             │     │
         │    │        │              │ approve/reject    │     │
         │    │        │              ▼                   │     │
         │    │        │         ┌──────────┐             │     │
         │    │        │         │ COMPLETE │─────────────┘     │
         │    │        │         │ or REJECT│                   │
         │    │        │         └──────────┘                   │
         │    │        │                                        │
         │    │        ▼                                        │
         │    │   ┌──────────┐                                  │
         │    └───│  FAILED  │◄─────────────────────────────────┘
         │        │(retryable)│  max_retries exceeded
         │        └────┬─────┘
         │             │ archive()
         │             ▼
         │        ┌──────────┐
         └───────│  STALE   │  manual review
                  │(archived)│
                  └──────────┘

Special states:
- BLOCKED: Has unresolved dependencies
  Transitions: BLOCKED → PENDING when dependencies complete
  
- CANCELLED: Manually cancelled or superseded
  Transitions: Any state → CANCELLED
```

### 5. Job Claiming Algorithm

```python
class JobQueue:
    def claim_next(self, agent_capabilities: List[str], timeout: int = 30) -> Optional[Job]:
        """
        Atomically claim next available job.
        Uses PostgreSQL advisory locks to prevent race conditions.
        """
        with self.db.transaction():
            # Find candidate job
            job = self.db.query_one("""
                SELECT id, job_type, payload, workdir_path
                FROM job_queue
                WHERE status = 'pending'
                  AND scheduled_for IS NULL OR scheduled_for <= NOW()
                  AND job_type = ANY(:capabilities)
                  AND NOT EXISTS (
                      SELECT 1 FROM job_dependencies 
                      WHERE job_id = job_queue.id
                  )
                ORDER BY priority DESC, created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """, {"capabilities": agent_capabilities})
            
            if not job:
                return None
            
            # Claim with advisory lock
            self.db.execute("""
                SELECT pg_advisory_lock(:job_id_int)
            """, {"job_id_int": job.id.int % 2**31})
            
            # Update status
            self.db.execute("""
                UPDATE job_queue
                SET status = 'claimed',
                    claimed_by = :agent_id,
                    claimed_at = NOW(),
                    workdir_path = COALESCE(workdir_path, :workdir)
                WHERE id = :job_id
            """, {
                "agent_id": self.agent_id,
                "job_id": job.id,
                "workdir": f"/tmp/osint-jobs/{job.id}"
            })
            
            return Job.from_row(job)
    
    def start_job(self, job_id: UUID):
        """Mark job as in progress."""
        self.db.execute("""
            UPDATE job_queue
            SET status = 'in_progress',
                started_at = NOW(),
                stale_after = NOW() + INTERVAL '1 second' * timeout_seconds
            WHERE id = :job_id
        """, {"job_id": job_id})
    
    def complete_job(self, job_id: UUID, output: dict):
        """Mark job complete and spawn dependent jobs."""
        with self.db.transaction():
            # Mark complete
            self.db.execute("""
                UPDATE job_queue
                SET status = 'completed',
                    completed_at = NOW(),
                    output = :output
                WHERE id = :job_id
            """, {"job_id": job_id, "output": json.dumps(output)})
            
            # Release advisory lock
            self.db.execute("""
                SELECT pg_advisory_unlock(:job_id_int)
            """, {"job_id_int": job_id.int % 2**31})
            
            # Check for jobs that were blocked on this one
            unblocked = self.db.query("""
                SELECT job_id FROM job_dependencies
                WHERE depends_on_job_id = :job_id
            """, {"job_id": job_id})
            
            for blocked_job in unblocked:
                # Check if all dependencies are now complete
                deps_remaining = self.db.query_one("""
                    SELECT COUNT(*) as remaining
                    FROM job_dependencies jd
                    JOIN job_queue jq ON jd.depends_on_job_id = jq.id
                    WHERE jd.job_id = :blocked_id
                      AND jq.status != 'completed'
                """, {"blocked_id": blocked_job.job_id})
                
                if deps_remaining.remaining == 0:
                    self.db.execute("""
                        UPDATE job_queue
                        SET status = 'pending'
                        WHERE id = :job_id AND status = 'blocked'
                    """, {"job_id": blocked_job.job_id})
                    
                    self.log_event(blocked_job.job_id, 'unblocked', 
                                 {"unblocked_by": job_id})
```

### 6. Job Spawning Patterns

#### 6.1 Parallel Investigation Pattern

```python
# Parent job spawns multiple parallel investigations
class ParallelInvestigationJob:
    def execute(self, payload):
        targets = payload["targets"]  # e.g., ["Ruemmler", "Zeitlin", "Daffey"]
        
        child_jobs = []
        for target in targets:
            child_job = self.queue.spawn_job(
                job_type="deep_person",
                domain="investigation",
                payload={"person_name": target, "context": payload["context"]},
                parent_job_id=self.job_id,
                priority=self.priority
            )
            child_jobs.append(child_job.id)
        
        # Spawn synthesis job that depends on all children
        synthesis_job = self.queue.spawn_job(
            job_type="synthesis",
            domain="analysis",
            payload={"synthesis_type": "narrative", "child_jobs": child_jobs},
            parent_job_id=self.job_id,
            depends_on=child_jobs,  # Won't start until all complete
            priority=self.priority
        )
        
        # Mark parent as awaiting children
        self.queue.update_status(self.job_id, 'awaiting_children')
        
        return {
            "spawned_jobs": [j.id for j in child_jobs] + [synthesis_job.id],
            "awaiting_completion": True
        }
```

#### 6.2 Retry with Backoff Pattern

```python
class RetryableJob:
    def fail_with_retry(self, job_id: UUID, error: str, traceback: str):
        job = self.queue.get_job(job_id)
        
        if job.attempts < job.max_attempts:
            # Exponential backoff: 5min, 25min, 125min
            delay = job.retry_delay_seconds * (5 ** job.attempts)
            scheduled_for = datetime.now() + timedelta(seconds=delay)
            
            self.db.execute("""
                UPDATE job_queue
                SET status = 'pending',
                    attempts = attempts + 1,
                    scheduled_for = :scheduled_for,
                    error_message = :error
                WHERE id = :job_id
            """, {
                "job_id": job_id,
                "scheduled_for": scheduled_for,
                "error": error[:1000]  # Truncate long errors
            })
            
            self.log_event(job_id, 'retry_scheduled', {
                "attempt": job.attempts + 1,
                "delay_seconds": delay,
                "scheduled_for": scheduled_for.isoformat()
            })
        else:
            # Max retries exceeded
            self.db.execute("""
                UPDATE job_queue
                SET status = 'failed',
                    error_message = :error,
                    error_traceback = :traceback
                WHERE id = :job_id
            """, {
                "job_id": job_id,
                "error": error[:1000],
                "traceback": traceback
            })
            
            self.log_event(job_id, 'failed_permanently', {
                "total_attempts": job.attempts + 1
            })
```

#### 6.3 Human Escalation Pattern

```python
class EscalatableJob:
    def escalate_to_human(self, job_id: UUID, reason: str, context: dict):
        """Move job to human review queue."""
        self.db.execute("""
            UPDATE job_queue
            SET status = 'awaiting_review',
                output = output || :escalation
            WHERE id = :job_id
        """, {
            "job_id": job_id,
            "escalation": json.dumps({
                "escalated_at": datetime.now().isoformat(),
                "reason": reason,
                "context": context,
                "review_url": f"/admin/jobs/{job_id}/review"
            })
        })
        
        # Also create human_action record for tracking
        self.db.execute("""
            INSERT INTO human_actions (action_type, description, related_job_id, status)
            VALUES ('job_review', :reason, :job_id, 'pending')
        """, {"reason": reason, "job_id": job_id})
        
        self.log_event(job_id, 'escalated_to_human', {"reason": reason})
```

#### 6.4 Recursion Limit Pattern

Prevent runaway job spawning with depth and breadth limits:

```python
class RecursionLimiter:
    """Enforce limits on job tree depth and breadth."""

    DEFAULT_MAX_DEPTH = 2       # Max levels of parent → child → grandchild
    DEFAULT_MAX_CHILDREN = 8    # Max child jobs per parent
    DEPENDENCY_TIMEOUT = 14400  # 4 hours

    def can_spawn_child(self, parent_job_id: UUID, proposed_type: str) -> bool:
        """Check if spawning another child is allowed."""

        parent = self.queue.get_job(parent_job_id)

        # Check depth
        depth = self.calculate_depth(parent_job_id)
        max_depth = parent.payload.get('max_depth', self.DEFAULT_MAX_DEPTH)
        if depth >= max_depth:
            self.log_event(parent_job_id, 'spawn_blocked', {
                'reason': 'max_depth_exceeded',
                'depth': depth,
                'max_depth': max_depth
            })
            return False

        # Check breadth
        children_count = self.count_children(parent_job_id)
        max_children = parent.payload.get('max_children', self.DEFAULT_MAX_CHILDREN)
        if children_count >= max_children:
            self.log_event(parent_job_id, 'spawn_blocked', {
                'reason': 'max_children_exceeded',
                'children': children_count,
                'max_children': max_children
            })
            return False

        return True

    def handle_child_failure(self, parent_job_id: UUID, child_job_id: UUID):
        """When a child fails after max retries, mark parent PARTIAL not BLOCKED."""

        failed_children = self.count_failed_children(parent_job_id)
        total_children = self.count_children(parent_job_id)

        if failed_children > 0 and failed_children < total_children:
            # Some children succeeded — mark parent as PARTIAL
            self.queue.update_job(parent_job_id, {
                'status': 'completed',
                'output': {'completion': 'partial',
                           'failed_children': failed_children}
            })
```

### 7. Event-Driven Job Creation

```python
class TriggerEngine:
    """Creates jobs based on events and thresholds."""
    
    def on_finding_created(self, finding_id: int):
        """Called when new finding is recorded."""
        finding = self.db.get_finding(finding_id)
        
        # Rule: New high-confidence relationship → verify
        if finding.finding_type == 'relationship' and finding.confidence == 'high':
            self.queue.spawn_job(
                job_type="verify_finding",
                domain="investigation",
                payload={"finding_id": finding_id, "check_quote": True},
                priority=6,
                source_finding_id=finding_id
            )
        
        # Rule: New person mentioned → investigate
        if 'person_mentioned' in finding.metadata:
            for person in finding.metadata['person_mentioned']:
                if not self.db.person_exists(person):
                    self.queue.spawn_job(
                        job_type="deep_person",
                        domain="investigation",
                        payload={"person_name": person, "context": "mentioned_in_finding"},
                        priority=5,
                        source_finding_id=finding_id
                    )
        
        # Check threshold triggers (with rate limiting)
        self.check_thresholds()

    # --- Trigger Rate Limiting ---
    TRIGGER_BUDGET_PER_HOUR = 10    # Max triggered jobs per hour
    TRIGGER_CHAIN_DEPTH_MAX = 3     # Max hops from original trigger

    def can_trigger(self, trigger_source: str, chain_depth: int = 0) -> bool:
        """Rate-limit trigger-spawned jobs."""

        if chain_depth >= self.TRIGGER_CHAIN_DEPTH_MAX:
            return False

        recent_triggered = self.db.query_one("""
            SELECT COUNT(*) as count FROM job_queue
            WHERE source_trigger IS NOT NULL
              AND created_at > NOW() - INTERVAL '1 hour'
        """)

        return recent_triggered.count < self.TRIGGER_BUDGET_PER_HOUR

    def check_thresholds(self):
        """Check if any threshold triggers fire."""
        recent_count = self.db.query_one("""
            SELECT COUNT(*) FROM findings 
            WHERE created_at > NOW() - INTERVAL '4 hours'
        """)
        
        if recent_count >= 20:
            # Check if synthesis job already queued
            existing = self.db.query_one("""
                SELECT id FROM job_queue
                WHERE job_type = 'synthesis'
                  AND status IN ('pending', 'claimed', 'in_progress')
                  AND created_at > NOW() - INTERVAL '4 hours'
            """)
            
            if not existing:
                self.queue.spawn_job(
                    job_type="synthesis",
                    domain="analysis",
                    payload={"trigger": "finding_burst", "count": recent_count},
                    priority=7
                )
```

### 8. Queue Monitoring

```python
class QueueMonitor:
    """Health monitoring and auto-scaling decisions."""
    
    def sample_metrics(self) -> QueueMetrics:
        """Record current queue state."""
        metrics = self.db.query_one("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'claimed') as claimed_count,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
                COUNT(*) FILTER (WHERE status = 'awaiting_review') as awaiting_review_count,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                COUNT(*) FILTER (WHERE status = 'pending' AND domain = 'discovery') as discovery_pending,
                COUNT(*) FILTER (WHERE status = 'pending' AND domain = 'investigation') as investigation_pending,
                COUNT(*) FILTER (WHERE status = 'pending' AND domain = 'analysis') as analysis_pending,
                COUNT(*) FILTER (WHERE status = 'pending' AND domain = 'content') as understanding_pending,
                COUNT(*) FILTER (WHERE stale_after < NOW() AND status = 'in_progress') as stuck_jobs
            FROM job_queue
        """)
        
        # Alert conditions
        metrics.has_stuck_jobs = metrics.stuck_jobs > 0
        metrics.queue_depth_critical = metrics.pending_count > 500
        
        # Save metrics
        self.db.execute("""
            INSERT INTO queue_metrics (...)
            VALUES (...)
        """)
        
        return metrics
    
    def auto_scale(self, metrics: QueueMetrics):
        """Make scaling decisions based on metrics."""
        if metrics.investigation_pending > 100:
            self.spawn_agents('investigator', count=2)
        
        if metrics.analysis_pending > 50:
            self.spawn_agents('analyst', count=1)
        
        if metrics.understanding_pending > 20:
            self.spawn_agents('dossier_writer', count=1)
        
        if metrics.has_stuck_jobs:
            self.alert_human(f"{metrics.stuck_jobs} stuck jobs detected")

        if metrics.queue_depth_critical:
            self.alert_human("Queue depth critical: {metrics.pending_count} pending jobs")


class SystemState:
    """Global system state including pause/halt controls."""

    def halt(self, reason: str):
        """Halt all job processing. Agents drain current job then stop."""
        self.db.execute("""
            INSERT INTO system_state (key, value, updated_at, updated_by)
            VALUES ('paused', 'true', NOW(), :reason)
            ON CONFLICT (key) DO UPDATE SET value = 'true', updated_at = NOW()
        """, {"reason": reason})
        self.log_event('system', 'halted', {"reason": reason})

    def resume(self):
        """Resume job processing."""
        self.db.execute("""
            UPDATE system_state SET value = 'false', updated_at = NOW()
            WHERE key = 'paused'
        """)

    def is_paused(self) -> bool:
        """Check if system is paused. Called by agents before claiming jobs."""
        result = self.db.query_one("""
            SELECT value FROM system_state WHERE key = 'paused'
        """)
        return result and result.value == 'true'
```

The `/halt` command sets `system_state.paused = true`. Every agent checks `is_paused()` before claiming new jobs. Currently-executing jobs finish gracefully — no new jobs are claimed until `resume()` is called.

```sql
-- System state table
CREATE TABLE system_state (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(256) DEFAULT NULL
);

INSERT INTO system_state (key, value) VALUES ('paused', 'false');
```

---

See next: `03-agent-personas.md` for detailed agent specifications
