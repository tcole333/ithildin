---
name: dispatch
description: Show queue depths and suggest which agents to launch next
user_invocable: true
---

# /dispatch

**CONTROL PLANE** — Read-only queue depth reporter. Shows what needs attention and suggests which skills to run based on triage scheduler fields.

## Process

### 1. Query All Queue Depths

Run these queries against investigation.db:

```bash
uv run python -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('investigation.db')

# Lead triage queue
pending_triage = db.execute(\"SELECT COUNT(*) FROM leads WHERE status='pending_triage'\").fetchone()[0]

# Infra requests
infra_open = db.execute(\"SELECT COUNT(*) FROM infra_requests WHERE status='open'\").fetchone()[0]
infra_active = db.execute(\"SELECT COUNT(*) FROM infra_requests WHERE status IN ('evaluating','in_progress')\").fetchone()[0]

# Blocked leads
blocked_by_infra = db.execute(\"SELECT COUNT(*) FROM leads WHERE blocked_by_infra_id IS NOT NULL AND status='blocked'\").fetchone()[0]

# Unverified findings (>24h old)
unverified_aging = db.execute(\"SELECT COUNT(*) FROM findings WHERE verification_status='unverified' AND created_at < datetime('now','-1 day')\").fetchone()[0]

# General investigation health
leads_open = db.execute(\"SELECT COUNT(*) FROM leads WHERE status='open'\").fetchone()[0]
leads_in_progress = db.execute(\"SELECT COUNT(*) FROM leads WHERE status='in_progress'\").fetchone()[0]

# Open leads by priority
high_crit = db.execute(\"SELECT COUNT(*) FROM leads WHERE status='open' AND priority IN ('critical','high')\").fetchone()[0]

# Recent activity (7 days)
recent_completed = db.execute(\"SELECT COUNT(*) FROM leads WHERE completed_at > datetime('now','-7 days')\").fetchone()[0]
recent_findings = db.execute(\"SELECT COUNT(*) FROM findings WHERE created_at > datetime('now','-7 days')\").fetchone()[0]
recent_connections = db.execute(\"SELECT COUNT(*) FROM connections WHERE created_at > datetime('now','-7 days')\").fetchone()[0]

# Totals
total_findings = db.execute(\"SELECT COUNT(*) FROM findings\").fetchone()[0]
total_connections = db.execute(\"SELECT COUNT(*) FROM connections\").fetchone()[0]
total_entities = db.execute(\"SELECT COUNT(*) FROM entities\").fetchone()[0]
total_leads = db.execute(\"SELECT COUNT(*) FROM leads\").fetchone()[0]

# Print structured output
print(f'pending_triage={pending_triage}')
print(f'infra_open={infra_open}')
print(f'infra_active={infra_active}')
print(f'blocked_by_infra={blocked_by_infra}')
print(f'unverified_aging={unverified_aging}')
print(f'leads_open={leads_open}')
print(f'leads_in_progress={leads_in_progress}')
print(f'high_crit={high_crit}')
print(f'recent_completed={recent_completed}')
print(f'recent_findings={recent_findings}')
print(f'recent_connections={recent_connections}')
print(f'total_findings={total_findings}')
print(f'total_connections={total_connections}')
print(f'total_entities={total_entities}')
print(f'total_leads={total_leads}')
"
```

Then query tier distribution and scheduler recommendations:

```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')

# Depth tier distribution (from leads.depth_tier column)
tiers = db.execute(\"\"\"
    SELECT COALESCE(depth_tier, 'untiered') as tier, COUNT(*) as cnt
    FROM leads WHERE status IN ('open', 'in_progress')
    GROUP BY tier ORDER BY cnt DESC
\"\"\").fetchall()
for t in tiers:
    print(f'tier_{t[0]}={t[1]}')

# Scheduler recommendations (from triage)
recs = db.execute(\"\"\"
    SELECT recommended_skill, COUNT(*) as cnt,
           GROUP_CONCAT(SUBSTR(title, 1, 40), '; ') as examples
    FROM leads
    WHERE status='open' AND recommended_skill IS NOT NULL
    GROUP BY recommended_skill
    ORDER BY cnt DESC
\"\"\").fetchall()
for r in recs:
    print(f'recommended_{r[0]}={r[1]} (e.g. {r[2][:80]})')

# Source coverage (from search_log)
source_coverage = db.execute('SELECT source, COUNT(*) as cnt FROM search_log GROUP BY source ORDER BY cnt DESC LIMIT 10').fetchall()
for s in source_coverage:
    print(f'source_{s[0]}={s[1]}')
"
```

Then query analysis state:

```bash
uv run python tools/analysis_export.py analysis-state
```

### 2. Format Report

Present the queue status in this format:

```
Queue Status (<DATE>)
========================================

NEEDS ACTION:
  !! <N> leads pending triage           -> /triage-leads
  !  <N> infra requests open            -> /build-infra
  !  <N> high/critical leads ready      -> /pursue-lead or /deep-investigate

BLOCKED:
     <N> leads waiting on infra

IN PROGRESS:
     <N> infra requests being built
     <N> leads currently being investigated

HEALTH:
   <N> open leads (<M> high/critical)
   <N> unverified findings (aging >24h)

ANALYSIS:
   /analyze-network    +<N> findings since last run (threshold=50, cooldown=48h) [READY/wait]
   /generate-hunches   +<N> findings since last run (threshold=50, cooldown=72h) [READY/wait]
   /timeline-analysis  +<N> findings since last run (threshold=30, cooldown=72h) [READY/wait]
   /systemic-analysis  +<N> findings since last run (threshold=50, cooldown=168h) [READY/wait]
   Hypotheses: <N> proposed, <M> investigating

INVESTIGATION DEPTH:
   scan:        <N> leads
   standard:    <N> leads
   deep_dive:   <N> leads
   untiered:    <N> leads

SCHEDULER RECOMMENDATIONS:
   /deep-investigate:    <N> leads (e.g. ...)
   /investigate-person:  <N> leads (e.g. ...)
   /trace-entity:        <N> leads (e.g. ...)
   /pursue-lead:         <N> leads (e.g. ...)

SOURCE COVERAGE (search_log):
   <source>: <N> queries | <source>: <N> queries | ...

RECENT (7d):
   <N> leads completed
   <N> findings added
   <N> connections mapped

TOTALS:
   <N> findings | <N> connections | <N> entities | <N> leads
```

### 3. Suggest Actions

Based on queue depths, suggest which skills to run:

| Condition | Suggestion |
|-----------|-----------|
| pending_triage > 0 | "Run `/triage-leads` to process <N> pending leads" |
| infra_open > 0 | "Run `/build-infra` to work on <N> infra requests" |
| high_crit > 0 and leads_in_progress == 0 | "Run `/pursue-lead` — <N> high-priority leads waiting" |
| leads_open > 50 and pending_triage == 0 | "Run 2-3 `/pursue-lead` instances in parallel" |
| recent_findings == 0 | "Investigation stalled — no findings in 7 days" |
| blocked_by_infra > 3 | "Infra bottleneck — <N> leads blocked. Prioritize `/build-infra`" |
| analysis skill READY | "Run `/analyze-network` (or other ready skill) — <N> new findings to analyze" |
| proposed hypotheses > 5 | "Hypotheses accumulating — run `/pursue-lead` on hypothesis-linked leads" |

### 4. Optional: Show Top Leads

If there are open high/critical leads, list the top 5:

```bash
uv run python tools/lead_tracker.py list --status open --priority critical --limit 5
uv run python tools/lead_tracker.py list --status open --priority high --limit 5
```

### 5. Optional: Show Infra Queue

If there are open infra requests, list them:

```bash
uv run python tools/infra_tracker.py list --status open --limit 5
```

### 6. Optional: Show Hypothesis Queue

If there are proposed hypotheses:

```bash
uv run python tools/hypothesis_tracker.py list --status proposed --limit 5
```

## Notes

- This skill is **read-only** — it does not modify any data
- It's designed to be run at the start of a session to decide what to work on
- Automated dispatch: `uv run python scripts/dispatcher.py status` for running agents
- Analysis skills have cooldown periods (48-168h) to prevent running too frequently
- Priority: data gathering > triage > analysis > post-processing
- Multiple CC instances can each run `/dispatch` to see the same queue state
