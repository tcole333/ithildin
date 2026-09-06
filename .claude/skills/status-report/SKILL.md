---
name: status-report
user-invocable: true
description: Report the selected investigation's lead queues, recent findings, analysis activity and source availability. Use for investigation progress/status questions, not to launch research or triage leads.
---

# /status-report

Give a truthful, bounded status report for the requested investigation.

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the profile/database. Create an isolated `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`. Use the read-only snapshot tool:

```bash
uv run python tools/investigation_status.py --recent-days 7 \
  --output "$WORKDIR/investigation-status.json"
```

Honor an explicit `--profile`/`--db` or the pinned environment. The snapshot does not mutate queues or initialize a DB. Report the resolved profile, database, as-of time and recent-period boundary. Each metric declares availability; unavailable is not zero. Inspect `profile_validation`: an unverified legacy profile is not the same as a registered empty profile with zero activity. Distinguish profile-scoped research activity from global tool/dispatcher health.

For useful detail, retrieve bounded samples:

```bash
uv run python tools/lead_tracker.py list --status open --priority critical --limit 10 --output "$WORKDIR/critical.json"
uv run python tools/lead_tracker.py list --status open --priority high --limit 10 --output "$WORKDIR/high.json"
uv run python tools/lead_tracker.py list --status in_progress --limit 10 --output "$WORKDIR/in-progress.json"
uv run python tools/lead_tracker.py list --status pending_triage --limit 10 --output "$WORKDIR/needs-triage.json"
uv run python tools/findings_tracker.py list --limit 10 --output "$WORKDIR/latest-findings.json"
```

Label these as top/latest samples and use snapshot totals to disclose truncation. The findings list is undated: label it “Latest findings,” or filter its timestamps and explicitly state that it is a sample within the recent period. Do not describe its ten items as the complete last-seven-days result. Needs-triage means `pending_triage`, not open leads or presumed lack of human review.

When source availability matters, run `uv run python tools/source_report.py report` and report it separately as platform source health. Use actual coverage artifacts for coverage gaps; tool availability does not establish that a target was searched.

Present the profile, lead counts by lifecycle state, findings and recent counts, active work and triage samples, relevant source limitations and a small set of suggested next steps. Separate fact from inference. Do not launch jobs, change the active profile, or begin the recommended investigations merely to produce a status report.
