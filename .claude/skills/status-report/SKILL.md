---
name: status-report
description: Generate investigation status summary — open leads, recent findings, source coverage
user_invocable: true
---

# /status-report

Generate a comprehensive status report of the investigation.

## Process

1. Run `python tools/lead_tracker.py stats` to get lead statistics
2. Run `python tools/findings_tracker.py stats` to get finding statistics
3. Run `python tools/source_report.py` to check data source availability
4. Run `python tools/lead_tracker.py list --status open --priority critical --limit 10` for critical leads
5. Run `python tools/lead_tracker.py list --status open --priority high --limit 10` for high-priority leads
6. Run `python tools/lead_tracker.py list --status in_progress --limit 10` for in-progress leads
7. Run `python tools/findings_tracker.py list --limit 10 -v` for recent findings
8. Run `python tools/lead_tracker.py list --status open --limit 5` to show newly created leads needing triage

## Output Format

Present a structured report with:

### Investigation Dashboard
- Total leads (open / in_progress / completed / blocked / dead_end)
- Total findings and connections
- Total sessions and searches logged

### Critical & High Priority Leads
- List all open critical and high-priority leads with descriptions

### In Progress
- List all leads currently being investigated

### Recent Findings (Last 7 Days)
- List recent findings with confidence levels and evidence

### Needs Triage
- Any agent-created leads that haven't been reviewed by a human

### Data Source Status
- Which sources are available and which need setup (Neo4j, etc.)

### Recommendations
- Suggest which leads to investigate next based on priority and available sources
- Note any source coverage gaps (e.g., "Rod-Larsen hasn't been searched in ICIJ yet")
