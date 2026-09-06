---
name: dispatch
description: Report the selected investigation’s queue, coverage, and analysis state without mutations, and recommend the next useful skill. Use for queue depths or what needs attention.
user-invocable: true
---

# /dispatch

Resolve the requested profile and database under
[the research workflow contract](../../../docs/RESEARCH_WORKFLOW_CONTRACT.md),
then create an isolated `WORKDIR`. This is a read-only assessment; use
/orchestrate-investigation when the user asks to act on recommendations.

```bash
uv run python tools/investigation_status.py --profile "$ITHILDIN_PROFILE" \
  --db "$ITHILDIN_DB_PATH" --output "$WORKDIR/status.json"
```

Read the complete snapshot and report its selected profile, absolute database,
capture time, scoped lead/finding activity, and available analysis state. Keep
global infrastructure, capacity, and source-health metrics explicitly separate.
An unavailable table or field is unknown, not zero. Search-log counts describe
recorded queries, not source coverage or independent evidence. Do not call a
dispatcher status/reaper or a tracker initializer to obtain a read-only report.

Recommend actions that advance the user's question:

- Pending leads may need /triage-leads; prioritize high-value open questions with
  /pursue-lead, /investigate-person, or /deep-investigate as appropriate.
- An actual access/tool blocker may justify /build-infra; distinguish a global
  request from one blocking this investigation.
- New evidence, a disputed claim, or an unresolved pattern may justify analysis
  or verification. Finding-count scheduler thresholds are operational defaults,
  not proof that analysis is or is not useful.
- Few recent findings do not establish a stalled investigation. Check known
  ongoing work, useful negative results, and coverage before drawing that conclusion.

Summarize the most important actions with their evidence and skill. Do not launch
workers, write findings, change leads, or generate follow-up leads in this mode.
