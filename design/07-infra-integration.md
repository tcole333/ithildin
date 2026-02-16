# Infrastructure Integration
## Design Document v1.0

### 1. Overview

This document describes how the new queue-based architecture integrates with existing infrastructure:
- **investigation.db**: Extended with queue tables
- **Existing tools**: Wrapped as job processors
- **Skills**: Converted to job submission interfaces
- **Human actions**: Integrated with review gates

### 2. Database Integration

#### 2.1 Migration Strategy

```sql
-- Add queue tables to existing investigation.db
-- (Or migrate to PostgreSQL for production)

-- Step 1: Create new tables (no impact on existing)
CREATE TABLE job_queue (...);
CREATE TABLE job_dependencies (...);
CREATE TABLE job_events (...);
CREATE TABLE agent_instances (...);

-- Step 2: Migrate existing leads to job_queue
INSERT INTO job_queue (
    job_type, domain, payload, status, priority
)
SELECT 
    'deep_person' as job_type,
    'investigation' as domain,
    jsonb_build_object(
        'target_name', target_name,
        'description', description,
        'source_lead_id', id
    ) as payload,
    CASE 
        WHEN status = 'open' THEN 'pending'
        WHEN status = 'in_progress' THEN 'claimed'
        ELSE status
    END as status,
    CASE priority
        WHEN 'critical' THEN 10
        WHEN 'high' THEN 7
        WHEN 'medium' THEN 5
        ELSE 3
    END as priority
FROM leads
WHERE status IN ('open', 'in_progress');

-- Step 3: Dual-write period
-- Write to both leads and job_queue
-- Eventually deprecate leads table

-- Step 4: Eventually remove old leads table
-- After all code migrated to queue-based
```

#### 2.2 Backward Compatibility

```python
class DualWriteAdapter:
    """Write to both old and new systems during transition."""
    
    def add_lead(self, lead_data: dict):
        """Add lead to both systems."""
        
        # Write to old leads table
        lead_id = self.db.insert('leads', lead_data)
        
        # Also create job
        job_id = self.queue.create_job(
            job_type='deep_person',
            domain='investigation',
            payload={
                'target_name': lead_data['target_name'],
                'source_lead_id': lead_id
            },
            priority=self.convert_priority(lead_data['priority'])
        )
        
        return {'lead_id': lead_id, 'job_id': job_id}
```

#### 2.3 Web Application Database

Published content for the web application can be served from the same PostgreSQL instance:

```sql
-- Published content metadata (web app reads from this)
CREATE TABLE published_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(256) NOT NULL UNIQUE,
    modality VARCHAR(64) NOT NULL CHECK (modality IN (
        'wiki_dossier', 'mechanism_explainer', 'analytical_article', 'visual_export'
    )),
    title TEXT NOT NULL,
    thread_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    content_path VARCHAR(512) NOT NULL,  -- Path to markdown/json file
    frontmatter JSONB DEFAULT '{}',
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finding_count INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    editor_job_id UUID REFERENCES job_queue(id)
);

CREATE INDEX idx_published_modality ON published_content(modality);
CREATE INDEX idx_published_threads ON published_content USING GIN(thread_ids);
CREATE INDEX idx_published_slug ON published_content(slug);

-- Full-text search across all published content
CREATE INDEX idx_published_search ON published_content
    USING GIN(to_tsvector('english', title));
```

For higher traffic or public deployment, a read replica can serve the web app while the primary handles queue operations.

### 3. Tool Integration

#### 3.1 Tool Wrapper Pattern

```python
class ToolJobAdapter:
    """Wrap existing CLI tools as job processors."""
    
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.tool_path = f"tools/{tool_name}.py"
    
    def execute(self, job_payload: dict) -> dict:
        """Execute tool as job."""
        
        # Convert job payload to CLI args
        args = self.payload_to_args(job_payload)
        
        # Run tool
        cmd = ['uv', 'run', 'python', self.tool_path] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=job_payload.get('timeout', 1800)
        )
        
        if result.returncode != 0:
            raise ToolExecutionError(result.stderr)
        
        # Parse output
        if '--output' in args:
            output_file = args[args.index('--output') + 1]
            with open(output_file) as f:
                output = json.load(f)
        else:
            output = {'stdout': result.stdout}
        
        return output
    
    def payload_to_args(self, payload: dict) -> list:
        """Convert job payload to CLI arguments."""
        
        args = []
        
        # Common conversions
        if 'query' in payload:
            args.append(payload['query'])
        
        if 'limit' in payload:
            args.extend(['--limit', str(payload['limit'])])
        
        if 'output_path' in payload:
            args.extend(['--output', payload['output_path']])
        
        return args
```

#### 3.2 Tool Registry

```python
TOOL_REGISTRY = {
    'query_doj': {
        'adapter': 'DocumentQueryAdapter',
        'job_types': ['document_mine'],
        'timeout': 300,
        'output_format': 'json'
    },
    'duggan_search': {
        'adapter': 'DugganSearchAdapter',
        'job_types': ['document_mine', 'deep_person'],
        'timeout': 600,
        'output_format': 'json'
    },
    'query_lmsband': {
        'adapter': 'LMSBANDAdapter',
        'job_types': ['document_mine'],
        'timeout': 300,
        'output_format': 'json'
    },
    'query_registry': {
        'adapter': 'RegistryAdapter',
        'job_types': ['trace_entity'],
        'timeout': 600,
        'output_format': 'json'
    },
    # ... etc
}
```

### 4. Skill Migration

#### 4.1 Skill to Job Mapping

| Current Skill | New Job Type(s) | Notes |
|---------------|-----------------|-------|
| `/pursue-lead` | `claim_and_investigate` | Single job that claims next lead |
| `/deep-investigate` | `deep_person` + child jobs | Orchestrator spawns parallel jobs |
| `/search-all-sources` | `document_mine` | Single job with multiple sources |
| `/trace-entity` | `trace_entity` | Direct mapping |
| `/investigate-person` | `deep_person` | Direct mapping |
| `/triage-leads` | `lead_triage` | Batch processing |
| `/analyze-network` | `network_analysis` | Direct mapping |
| `/generate-hunches` | `hunch_generation` | Direct mapping |
| `/timeline-analysis` | `timeline_correlation` | Direct mapping |
| `/systemic-analysis` | `systemic_analysis` | Direct mapping |
| `/write-article` | `article_draft` | Direct mapping |
| `/review-article` | `editor_review` | Direct mapping |
| `/build-infra` | `tool_build` | Direct mapping |
| `/add-registry` | `registry_add` | Direct mapping |

#### 4.2 Skill Implementation Migration

```python
# OLD: /deep-investigate as sync skill
@skill('/deep-investigate')
def deep_investigate(target: str, context: str = ''):
    # Spawn 4 sub-agents
    agent_a = spawn_agent('document_corpus', target)
    agent_b = spawn_agent('corporate', target)
    agent_c = spawn_agent('legal', target)
    agent_d = spawn_agent('osint', target)
    
    # Wait for all (blocking, context bloat)
    results = wait_for_all([agent_a, agent_b, agent_c, agent_d])
    
    # Synthesize
    return synthesize(results)

# NEW: /deep-investigate as job submission
@skill('/deep-investigate')
def deep_investigate(target: str, context: str = ''):
    # Create orchestrator job (returns immediately)
    job_id = queue.create_job(
        job_type='deep_person',
        domain='investigation',
        payload={'target_name': target, 'context': context}
    )
    
    return {
        'status': 'submitted',
        'job_id': job_id,
        'check_status': f'/job-status {job_id}'
    }

# Status check skill
@skill('/job-status')
def job_status(job_id: str):
    job = queue.get_job(job_id)
    
    if job.status == 'completed':
        # Load just the summary
        summary = load_report_summary(job.output['report_path'])
        return {
            'status': 'completed',
            'findings_count': summary['findings_count'],
            'key_discoveries': summary['key_discoveries'],
            'report_path': job.output['report_path']
        }
    
    return {'status': job.status, 'progress': job.progress}
```

### 5. Human Action Integration

#### 5.1 Review Gates

```python
class HumanReviewGate:
    """Integrate human review into job pipeline."""
    
    def submit_for_review(self, job_id: str, review_type: str):
        """Submit job output for human review."""
        
        # Create human action
        action_id = self.db.insert('human_actions', {
            'action_type': review_type,
            'related_job_id': job_id,
            'status': 'pending',
            'description': f'Review required for job {job_id}'
        })
        
        # Update job status
        self.queue.update_job(job_id, {
            'status': 'awaiting_review',
            'human_action_id': action_id
        })
        
        # Notify (if notification system exists)
        self.notify_human(action_id)
        
        return action_id
    
    def complete_review(self, action_id: str, decision: str, notes: str = ''):
        """Human completes review."""
        
        # Update human action
        self.db.update('human_actions', action_id, {
            'status': 'completed',
            'decision': decision,
            'notes': notes,
            'completed_at': datetime.now()
        })
        
        # Get related job
        action = self.db.get('human_actions', action_id)
        job_id = action['related_job_id']
        
        # Resume job based on decision
        if decision == 'approve':
            self.queue.update_job(job_id, {'status': 'completed'})
        elif decision == 'revise':
            # Spawn revision job
            self.queue.spawn_revision_job(job_id, notes)
        elif decision == 'reject':
            self.queue.update_job(job_id, {'status': 'rejected'})
```

#### 5.2 System Halt Command

The `/halt` command provides emergency stop capability:

```python
class HaltCommand:
    """Implementation of /halt for the CLI."""

    def execute(self, reason: str = 'manual halt'):
        """Halt all job processing."""

        # Set pause flag
        self.db.execute("""
            INSERT INTO system_state (key, value, updated_at, updated_by)
            VALUES ('paused', 'true', NOW(), :reason)
            ON CONFLICT (key) DO UPDATE
                SET value = 'true', updated_at = NOW(), updated_by = :reason
        """, {"reason": reason})

        # Count currently running jobs (these will finish)
        in_progress = self.db.query_one("""
            SELECT COUNT(*) as count FROM job_queue
            WHERE status = 'in_progress'
        """)

        return {
            'status': 'halted',
            'draining_jobs': in_progress.count,
            'message': f'System halted. {in_progress.count} jobs will finish, '
                       f'no new jobs will be claimed. Use /resume to restart.'
        }

    def resume(self):
        """Resume job processing."""
        self.db.execute("""
            UPDATE system_state SET value = 'false', updated_at = NOW()
            WHERE key = 'paused'
        """)
        return {'status': 'resumed'}
```

Every agent's `claim_next` call checks `system_state` before acquiring a job:

```python
# In JobQueue.claim_next():
if self.system_state.is_paused():
    return None  # Agent idles instead of claiming
```

#### 5.3 Human Escalation Triggers

```python
ESCALATION_RULES = {
    'citation_verification_failed': {
        'threshold': 3,  # 3+ failed citations
        'action': 'escalate_to_human'
    },
    'confidence_mismatch': {
        'condition': 'claim_type == inference AND confidence == confirmed',
        'action': 'flag_for_review'
    },
    'high_impact_finding': {
        'condition': 'target in high_centrality_nodes AND finding_type == relationship',
        'action': 'notify_human'
    },
    'contradiction_detected': {
        'action': 'escalate_to_human'
    }
}
```

### 6. Existing Infrastructure Queue Integration

#### 6.1 Infra Request → Job Conversion

```python
class InfraQueueIntegration:
    """Bridge existing infra_requests table to job queue."""
    
    def sync_infra_to_jobs(self):
        """Convert pending infra requests to jobs."""
        
        pending = self.db.query("""
            SELECT * FROM infra_requests
            WHERE status = 'open'
            AND NOT EXISTS (
                SELECT 1 FROM job_queue
                WHERE payload->>'infra_request_id' = infra_requests.id::text
            )
        """)
        
        for request in pending:
            job_type = self.map_infra_type_to_job(request['type'])
            
            job_id = self.queue.create_job(
                job_type=job_type,
                domain='infrastructure',
                payload={
                    'infra_request_id': request['id'],
                    'title': request['title'],
                    'description': request['description'],
                    'source_url': request.get('source_url')
                },
                priority=self.map_priority(request['priority'])
            )
            
            # Link infra request to job
            self.db.execute("""
                UPDATE infra_requests
                SET job_id = :job_id
                WHERE id = :request_id
            """, {'job_id': job_id, 'request_id': request['id']})
    
    def map_infra_type_to_job(self, infra_type: str) -> str:
        """Map infra request type to job type."""
        
        mapping = {
            'new_source': 'source_ingest',
            'new_registry': 'registry_add',
            'tool_improvement': 'tool_build',
            'bug_fix': 'bug_fix',
            'new_tool': 'tool_build'
        }
        
        return mapping.get(infra_type, 'tool_build')
```

#### 6.2 Tool Builder Agent

```python
class ToolBuilderAgent:
    """Agent that processes infrastructure jobs."""
    
    def execute(self, payload: dict) -> dict:
        """Build tool from infra request."""
        
        infra_id = payload['infra_request_id']
        request = self.db.get('infra_requests', infra_id)
        
        # Determine tool type and approach
        if request['type'] == 'new_source':
            result = self.build_source_integration(request)
        elif request['type'] == 'new_registry':
            result = self.build_registry_tool(request)
        elif request['type'] == 'bug_fix':
            result = self.fix_bug(request)
        else:
            result = self.build_tool(request)
        
        # Update infra request
        self.db.update('infra_requests', infra_id, {
            'status': 'completed' if result['success'] else 'failed',
            'completed_at': datetime.now(),
            'result_notes': result.get('notes', '')
        })
        
        return result
```

### 7. Dispatcher Integration

#### 7.1 Existing Dispatcher → Queue Bridge

```python
class DispatcherQueueBridge:
    """Integrate existing dispatcher with job queue."""
    
    def __init__(self):
        self.dispatcher_config = self.load_config('scripts/dispatch_config.json')
        self.queue = JobQueue()
    
    def dispatch_cycle(self):
        """One cycle of dispatch decisions based on queue state."""
        
        metrics = self.queue.get_metrics()
        
        # Check triggers
        if metrics['investigation_pending'] > self.dispatcher_config['triggers']['pursue_lead']['min_high_critical']:
            self.spawn_investigator_agents(2)
        
        if metrics['discovery_pending'] > 0:
            self.spawn_surveyor_agents(1)
        
        if metrics['understanding_pending'] > 10:
            self.spawn_dossier_writer_agents(1)
        
        # Check for stuck jobs
        if metrics['stuck_jobs'] > 0:
            self.handle_stuck_jobs(metrics['stuck_jobs'])
    
    def spawn_investigator_agents(self, count: int):
        """Spawn investigator agent instances."""
        
        for i in range(count):
            agent_id = f"investigator-{uuid4().hex[:8]}"
            
            # Register agent
            self.queue.register_agent(agent_id, 'investigator')
            
            # Launch process (or container in production)
            self.launch_agent_process(agent_id, 'investigator')
```

#### 7.2 Agent Worker Process

```python
#!/usr/bin/env python3
"""
Agent Worker Process
Claims jobs from queue and executes them.
"""

import os
import sys
import time
import signal
from typing import Optional

class AgentWorker:
    def __init__(self, agent_id: str, persona: str):
        self.agent_id = agent_id
        self.persona = persona
        self.queue = JobQueue()
        self.running = True
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
    
    def run(self):
        """Main loop: claim and execute jobs."""
        
        self.register()
        
        while self.running:
            try:
                # Claim next job
                job = self.queue.claim_next(
                    capabilities=self.get_capabilities(),
                    agent_id=self.agent_id,
                    timeout=30
                )
                
                if job:
                    self.execute_job(job)
                else:
                    # No jobs available, idle behavior
                    self.on_idle()
                    
            except Exception as e:
                self.log_error(f"Error in main loop: {e}")
                time.sleep(5)
        
        self.unregister()
    
    def execute_job(self, job: Job):
        """Execute claimed job."""
        
        try:
            # Get agent implementation
            agent_class = AGENT_REGISTRY[self.persona]
            agent = agent_class(job.id)
            
            # Execute
            result = agent.execute(job.payload)
            
            # Complete job
            self.queue.complete_job(job.id, result)
            
        except Exception as e:
            # Fail job
            self.queue.fail_job(job.id, str(e))
    
    def on_idle(self):
        """Called when no jobs available."""
        time.sleep(5)  # Brief pause before retry
    
    def shutdown(self, signum, frame):
        """Graceful shutdown."""
        self.running = False
    
    def register(self):
        """Register with queue."""
        self.queue.register_agent(self.agent_id, self.persona)
    
    def unregister(self):
        """Unregister from queue."""
        self.queue.unregister_agent(self.agent_id)

if __name__ == '__main__':
    agent_id = sys.argv[1]
    persona = sys.argv[2]
    
    worker = AgentWorker(agent_id, persona)
    worker.run()
```

### 8. Monitoring and Observability

#### 8.1 Queue Metrics Dashboard

```python
class QueueDashboard:
    """Generate queue status dashboard."""
    
    def generate(self) -> dict:
        """Generate comprehensive queue status."""
        
        return {
            'overview': {
                'total_jobs': self.queue.count_jobs(),
                'pending': self.queue.count_by_status('pending'),
                'in_progress': self.queue.count_by_status('in_progress'),
                'completed_24h': self.queue.count_completed_since(hours=24),
                'failed_24h': self.queue.count_failed_since(hours=24)
            },
            'by_domain': {
                'discovery': self.queue.count_by_domain('discovery'),
                'investigation': self.queue.count_by_domain('investigation'),
                'analysis': self.queue.count_by_domain('analysis'),
                'content': self.queue.count_by_domain('content'),
                'infrastructure': self.queue.count_by_domain('infrastructure')
            },
            'by_priority': {
                'critical': self.queue.count_by_priority(10),
                'high': self.queue.count_by_priority(range(7, 10)),
                'medium': self.queue.count_by_priority(range(4, 7)),
                'low': self.queue.count_by_priority(range(1, 4))
            },
            'agents': {
                'active': self.queue.count_active_agents(),
                'idle': self.queue.count_idle_agents(),
                'by_persona': self.queue.count_agents_by_persona()
            },
            'alerts': self.get_alerts()
        }
    
    def get_alerts(self) -> list:
        """Generate alerts for anomalous conditions."""
        
        alerts = []
        
        # Stuck jobs
        stuck = self.queue.get_stuck_jobs()
        if stuck:
            alerts.append({
                'severity': 'warning',
                'type': 'stuck_jobs',
                'count': len(stuck),
                'jobs': [j.id for j in stuck[:5]]  # Sample
            })
        
        # High failure rate
        failure_rate = self.queue.get_failure_rate(hours=1)
        if failure_rate > 0.1:  # 10%
            alerts.append({
                'severity': 'critical',
                'type': 'high_failure_rate',
                'rate': failure_rate
            })
        
        # Queue depth
        pending = self.queue.count_by_status('pending')
        if pending > 1000:
            alerts.append({
                'severity': 'warning',
                'type': 'queue_depth',
                'count': pending
            })
        
        return alerts
```

### 9. Cost Tracking

Track resource consumption for budget management:

```python
class CostTracker:
    """Track token usage and API costs per job."""

    def record_job_cost(self, job_id: UUID, costs: dict):
        """Record costs for a completed job."""
        self.db.execute("""
            INSERT INTO job_costs (job_id, token_input, token_output,
                                   api_calls, api_source, estimated_cost_usd)
            VALUES (:job_id, :input, :output, :api_calls, :source, :cost)
        """, {
            "job_id": job_id,
            "input": costs.get("token_input", 0),
            "output": costs.get("token_output", 0),
            "api_calls": costs.get("api_calls", 0),
            "source": costs.get("api_source", "claude"),
            "cost": costs.get("estimated_cost_usd", 0.0)
        })

    def monthly_projection(self) -> dict:
        """Project monthly costs from recent usage."""
        recent = self.db.query_one("""
            SELECT
                SUM(estimated_cost_usd) as cost_7d,
                SUM(token_input + token_output) as tokens_7d,
                SUM(api_calls) as calls_7d,
                COUNT(*) as jobs_7d
            FROM job_costs
            WHERE created_at > NOW() - INTERVAL '7 days'
        """)

        return {
            'last_7_days': recent.cost_7d,
            'projected_monthly': recent.cost_7d * 4.3,
            'tokens_7d': recent.tokens_7d,
            'api_calls_7d': recent.calls_7d,
            'jobs_7d': recent.jobs_7d,
            'avg_cost_per_job': recent.cost_7d / max(recent.jobs_7d, 1)
        }

    def throttle_if_needed(self, budget_monthly_usd: float):
        """Throttle low-priority jobs if budget is tight."""
        projection = self.monthly_projection()

        if projection['projected_monthly'] > budget_monthly_usd * 0.9:
            # Pause low-priority jobs (priority < 5)
            self.db.execute("""
                UPDATE job_queue
                SET status = 'blocked'
                WHERE status = 'pending' AND priority < 5
            """)
            return {'action': 'throttled', 'reason': 'approaching budget limit'}

        return {'action': 'none'}
```

```sql
CREATE TABLE job_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES job_queue(id),
    token_input INTEGER DEFAULT 0,
    token_output INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    api_source VARCHAR(64) DEFAULT 'claude',
    estimated_cost_usd FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_costs_job ON job_costs(job_id);
CREATE INDEX idx_job_costs_time ON job_costs(created_at DESC);
```

---

See next: `08-implementation-phases.md` for rollout plan
