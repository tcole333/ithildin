# Context Management Strategy
## Design Document v1.0

### 1. The Problem

Current agent architecture suffers from **context bloat** when using synchronous sub-agents:
- Each sub-agent returns full transcript (10-50MB)
- Parent agent accumulates all child contexts
- Single session hits 200MB+ and crashes
- Cannot scale to 4+ parallel sub-agents

### 2. The Solution: Queue-Based Report Submission

Instead of synchronous sub-agent calls with `TaskOutput`, agents:
1. Write structured reports to disk (unique workdir)
2. Submit report paths to job output
3. Downstream jobs read reports from disk
4. Context stays lean (2KB report vs 25MB transcript)

```
OLD PATTERN (Current):
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator Session                                            │
│                                                                 │
│ 1. Spawn Agent A (sync) ───────▶ [Agent A runs]                 │
│    ◄──────────────────────────── [Returns 25MB transcript]      │
│                                                                 │
│ 2. Spawn Agent B (sync) ───────▶ [Agent B runs]                 │
│    ◄──────────────────────────── [Returns 25MB transcript]      │
│                                                                 │
│ 3. Context now: ~50MB                                           │
│    (Cannot scale to 4+ agents)                                  │
└─────────────────────────────────────────────────────────────────┘

NEW PATTERN (Target):
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator Session                                            │
│                                                                 │
│ 1. Spawn Job A (async) ────────▶ [Job A runs]                   │
│    ├─ Writes report to /jobs/job-a/report.md                    │
│    └─ Completes job                                             │
│    (Orchestrator immediately continues)                         │
│                                                                 │
│ 2. Spawn Job B (async) ────────▶ [Job B runs]                   │
│    ├─ Writes report to /jobs/job-b/report.md                    │
│    └─ Completes job                                             │
│    (Orchestrator immediately continues)                         │
│                                                                 │
│ 3. Spawn Synthesis Job ────────▶ [Depends on A, B]              │
│    └─ Reads /jobs/job-a/report.md (2KB)                         │
│    └─ Reads /jobs/job-b/report.md (2KB)                         │
│    └─ Synthesizes                                               │
│                                                                 │
│ Context stays: ~5KB per session                                 │
│ (Can scale to unlimited parallel jobs)                          │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Work Directory Structure

Each job gets an isolated working directory:

```
/tmp/osint-jobs/
└── {job_id}/                    # UUID-based job directory
    ├── job.json                 # Job metadata and payload
    ├── report.md                # Main findings report
    ├── findings.json            # Structured findings for DB import
    ├── connections.json         # Connections to create
    ├── entities.json            # Entities discovered
    ├── output/                  # Tool output files
    │   ├── doj-search.json
    │   ├── lmsband-entities.json
    │   └── ...
    ├── evidence/                # Downloaded documents
    │   ├── EFTA02336502.pdf
    │   └── ...
    ├── logs/                    # Execution logs
    │   └── execution.log
    └── errors/                  # Error details if failed
        └── error.txt
```

### 4. Report Format Standards

#### 4.1 Investigation Report Template

```markdown
# Investigation Report: {target_name}
## Job ID: {job_id}
## Agent: {agent_persona}
## Executed: {timestamp}

## Summary
{1-2 paragraph executive summary}

## Findings Added
| ID | Type | Target | Summary | Confidence |
|----|------|--------|---------|------------|
| {id} | {type} | {target} | {summary} | {confidence} |

## Connections Added
| Person A | Person B | Type | Strength | Evidence |
|----------|----------|------|----------|----------|
| {a} | {b} | {type} | {strength} | {evidence} |

## Key Discoveries
1. {Significant finding with evidence}
2. {Significant finding with evidence}

## Negative Results
- Searched {source}: 0 results (investigatively significant)

## Source Gaps Identified
- {New data source discovered}

## Spawned Jobs
- {job_id}: {description}

## Evidence Files
- /jobs/{job_id}/output/{filename}

## Full Context
{Detailed investigation narrative}
```

#### 4.2 Structured Output Files

```json
// findings.json
{
  "job_id": "uuid",
  "findings": [
    {
      "target_name": "Kathy Ruemmler",
      "finding_type": "relationship",
      "summary": "Organized Bannon-Lajcak dinner June 2019",
      "detail": "...",
      "evidence": [
        {
          "evidence_type": "efta",
          "evidence_ref": "EFTA02336502",
          "source_quote": "Steve—I've arranged the dinner...",
          "claim_type": "direct_quote"
        }
      ],
      "confidence": "confirmed",
      "date_of_event": "2019-06-15"
    }
  ]
}
```

```json
// connections.json
{
  "connections": [
    {
      "person_a": "Kathy Ruemmler",
      "person_b": "Steve Bannon",
      "relationship_type": "social",
      "description": "Organized dinner meeting",
      "strength": "medium",
      "evidence": ["EFTA02336502"]
    }
  ]
}
```

### 5. Agent Implementation Pattern

```python
class InvestigationAgent:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.workdir = f"/tmp/osint-jobs/{job_id}"
        self.report_path = f"{self.workdir}/report.md"
        self.findings_path = f"{self.workdir}/findings.json"
        self.connections_path = f"{self.workdir}/connections.json"
        
        # Ensure workdir exists
        os.makedirs(self.workdir, exist_ok=True)
        os.makedirs(f"{self.workdir}/output", exist_ok=True)
    
    def execute(self, payload: dict) -> dict:
        """Execute investigation job."""
        
        try:
            # Load job context
            target = payload['target_name']
            context = payload.get('context', '')
            
            # Initialize report
            self.start_report(target, context)
            
            # Execute investigation
            findings = self.investigate(target, context)
            
            # Write structured outputs
            self.write_findings(findings)
            self.write_connections(findings)
            
            # Complete report
            self.complete_report(findings)
            
            # Return minimal output with paths
            return {
                'status': 'completed',
                'report_path': self.report_path,
                'findings_count': len(findings),
                'spawned_jobs': self.spawned_jobs
            }
            
        except Exception as e:
            self.handle_error(e)
            raise
    
    def start_report(self, target: str, context: str):
        """Initialize report file."""
        
        with open(self.report_path, 'w') as f:
            f.write(f"""# Investigation Report: {target}
## Job ID: {self.job_id}
## Agent: {self.persona}
## Executed: {datetime.now().isoformat()}

## Context
{context}

## Investigation Log

""")
    
    def log_section(self, title: str, content: str):
        """Append section to report."""
        
        with open(self.report_path, 'a') as f:
            f.write(f"\n### {title}\n\n{content}\n")
    
    def write_findings(self, findings: list):
        """Write structured findings to JSON."""
        
        with open(self.findings_path, 'w') as f:
            json.dump({
                'job_id': self.job_id,
                'findings': [f.to_dict() for f in findings]
            }, f, indent=2)
    
    def run_tool(self, tool: str, args: list, output_name: str) -> dict:
        """Run tool and save output to workdir."""
        
        output_path = f"{self.workdir}/output/{output_name}"
        
        cmd = ['uv', 'run', 'python', f'tools/{tool}.py'] + args + ['--output', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            with open(output_path) as f:
                return json.load(f)
        else:
            self.log_section(f"Tool Error: {tool}", result.stderr)
            return {}
```

### 6. Orchestrator Pattern

```python
class InvestigationOrchestrator:
    """Orchestrates multi-agent investigations via queue."""
    
    def deep_investigate(self, target: str, context: str = '') -> str:
        """
        Launch deep investigation with 4 parallel agents.
        Returns parent job ID (non-blocking).
        """
        
        # Create parent job
        parent_job = self.queue.create_job(
            job_type='deep_person',
            domain='investigation',
            payload={'target_name': target, 'context': context}
        )
        
        # Spawn 4 parallel child jobs
        child_jobs = []
        
        # Agent A: Document Corpus
        job_a = self.queue.create_job(
            job_type='document_mine',
            domain='investigation',
            payload={
                'target': target,
                'sources': ['doj', 'duggan', 'lmsband', 'unified'],
                'parent_job': parent_job.id
            },
            parent_job_id=parent_job.id
        )
        child_jobs.append(job_a.id)
        
        # Agent B: Corporate/Financial
        job_b = self.queue.create_job(
            job_type='trace_entity',
            domain='investigation',
            payload={
                'entity_name': target,
                'parent_job': parent_job.id
            },
            parent_job_id=parent_job.id
        )
        child_jobs.append(job_b.id)
        
        # Agent C: Legal/Court
        job_c = self.queue.create_job(
            job_type='document_mine',
            domain='investigation',
            payload={
                'target': target,
                'sources': ['courtlistener', 'fara', 'investigations'],
                'parent_job': parent_job.id
            },
            parent_job_id=parent_job.id
        )
        child_jobs.append(job_c.id)
        
        # Agent D: OSINT/Network
        job_d = self.queue.create_job(
            job_type='source_discovery',
            domain='investigation',
            payload={
                'target': target,
                'sources': ['littlesis', 'aleph', 'icij', 'gdelt'],
                'parent_job': parent_job.id
            },
            parent_job_id=parent_job.id
        )
        child_jobs.append(job_d.id)
        
        # Update parent job to track children
        self.queue.update_job(parent_job.id, {
            'child_jobs': child_jobs,
            'status': 'awaiting_children'
        })
        
        # Spawn synthesis job that depends on all children
        synthesis_job = self.queue.create_job(
            job_type='synthesis',
            domain='analysis',
            payload={
                'parent_job': parent_job.id,
                'child_jobs': child_jobs,
                'target': target
            },
            parent_job_id=parent_job.id,
            depends_on=child_jobs  # Won't start until all complete
        )
        
        # Return immediately (non-blocking)
        return parent_job.id
    
    def get_investigation_status(self, job_id: str) -> dict:
        """Check status of investigation without loading full context."""
        
        job = self.queue.get_job(job_id)
        
        if job.status == 'completed':
            # Load just the summary, not full report
            report_summary = self.load_report_summary(job.output['report_path'])
            return {
                'status': 'completed',
                'findings_count': report_summary['findings_count'],
                'key_discoveries': report_summary['key_discoveries'],
                'report_path': job.output['report_path']
            }
        
        elif job.status == 'awaiting_children':
            # Check child job statuses
            children = [self.queue.get_job(cid) for cid in job.child_jobs]
            return {
                'status': 'in_progress',
                'children_completed': sum(1 for c in children if c.status == 'completed'),
                'children_total': len(children),
                'child_statuses': {c.id: c.status for c in children}
            }
        
        else:
            return {'status': job.status}
```

### 7. Report Reading Pattern

```python
class ReportReader:
    """Read investigation reports efficiently."""
    
    def read_summary(self, report_path: str) -> dict:
        """Read just the summary section (fast)."""
        
        summary = {}
        in_summary = False
        
        with open(report_path) as f:
            for line in f:
                if line.startswith('## Summary'):
                    in_summary = True
                    continue
                if in_summary:
                    if line.startswith('## '):
                        break
                    summary['text'] = summary.get('text', '') + line
        
        return summary
    
    def read_findings(self, findings_path: str) -> list:
        """Read structured findings JSON."""
        
        with open(findings_path) as f:
            data = json.load(f)
            return data.get('findings', [])
    
    def read_section(self, report_path: str, section: str) -> str:
        """Read specific section from report."""
        
        content = []
        in_section = False
        
        with open(report_path) as f:
            for line in f:
                if line.startswith(f'## {section}'):
                    in_section = True
                    continue
                if in_section:
                    if line.startswith('## '):
                        break
                    content.append(line)
        
        return ''.join(content)
```

### 8. Synthesis Agent Implementation

```python
class SynthesisAgent:
    """Synthesizes results from multiple child investigation jobs."""
    
    def execute(self, payload: dict) -> dict:
        """Synthesize child job reports."""
        
        child_job_ids = payload['child_jobs']
        target = payload['target']
        
        # Read child reports (efficient - just the files, not full context)
        child_reports = []
        for job_id in child_job_ids:
            job = self.queue.get_job(job_id)
            
            # Read structured findings
            findings = self.read_findings(job.output['findings_path'])
            
            # Read report summary
            summary = self.read_report_summary(job.output['report_path'])
            
            child_reports.append({
                'job_id': job_id,
                'findings': findings,
                'summary': summary
            })
        
        # Perform synthesis
        synthesis = self.synthesize(child_reports, target)
        
        # Write synthesis report
        synthesis_report = self.write_synthesis_report(synthesis, child_reports)
        
        # Record synthesis findings
        self.record_findings(synthesis['findings'])
        
        # Spawn follow-up jobs if needed
        spawned = self.spawn_followups(synthesis)
        
        return {
            'status': 'completed',
            'synthesis_report_path': synthesis_report,
            'findings_added': len(synthesis['findings']),
            'spawned_jobs': spawned
        }
    
    def synthesize(self, reports: list, target: str) -> dict:
        """Identify corroboration, contradictions, and gaps."""
        
        all_findings = []
        for report in reports:
            all_findings.extend(report['findings'])
        
        # Find corroborating findings (same fact, different sources)
        corroboration = self.find_corroboration(all_findings)
        
        # Find contradictions
        contradictions = self.find_contradictions(all_findings)
        
        # Identify gaps
        gaps = self.identify_gaps(reports, target)
        
        # Generate synthesis findings
        synthesis_findings = []
        
        if corroboration:
            synthesis_findings.append({
                'target_name': target,
                'finding_type': 'synthesis',
                'summary': f"Multiple sources confirm: {corroboration['summary']}",
                'confidence': 'high',
                'evidence': corroboration['evidence']
            })
        
        return {
            'findings': synthesis_findings,
            'corroboration': corroboration,
            'contradictions': contradictions,
            'gaps': gaps
        }
```

### 9. Cleanup Strategy

```python
class WorkdirCleanup:
    """Manage workdir lifecycle."""
    
    def archive_completed_job(self, job_id: str):
        """Archive job workdir after completion."""
        
        workdir = f"/tmp/osint-jobs/{job_id}"
        archive_dir = f"research/job_archives/{job_id}"
        
        # Copy to persistent storage
        shutil.copytree(workdir, archive_dir)
        
        # Compress
        shutil.make_archive(archive_dir, 'gztar', archive_dir)
        
        # Remove uncompressed
        shutil.rmtree(archive_dir)
        
        # Remove from temp (keep for 7 days)
        # Actual removal handled by cron
    
    def cleanup_old_workdirs(self, max_age_days: int = 7):
        """Remove workdirs older than max_age."""
        
        cutoff = datetime.now() - timedelta(days=max_age_days)
        
        for job_dir in Path("/tmp/osint-jobs").iterdir():
            if not job_dir.is_dir():
                continue
            
            # Check if job is completed and old enough
            job_id = job_dir.name
            job = self.queue.get_job(job_id)
            
            if job and job.status == 'completed':
                if job.completed_at and job.completed_at < cutoff:
                    shutil.rmtree(job_dir)
```

### 10. Migration Path from Current System

```python
class MigrationHelper:
    """Migrate from sync sub-agents to queue-based."""
    
    def migrate_skill(self, skill_name: str):
        """
        Migrate a skill from sync to async pattern.
        
        OLD:
        - Skill spawns sub-agents with Task tool
        - Waits for TaskOutput
        - Reads full transcript
        
        NEW:
        - Skill creates orchestrator job
        - Orchestrator spawns child jobs
        - Returns job ID immediately
        - Status checked via job queue
        """
        
        pass  # Implementation per skill
    
    def backward_compatibility(self):
        """
        Keep existing skills working during transition:
        - Add --async flag to skills
        - Default to sync (existing behavior)
        - New code uses --async
        - Eventually remove sync path
        """
        pass
```

---

See next: `07-infra-integration.md` for integrating with existing infrastructure
