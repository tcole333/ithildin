---
name: orchestrate-investigation
description: Oversee a multi-step investigation in the current chat using native subagents, review their evidence, and complete the requested work. Also supports explicitly requested unattended staged jobs.
user-invocable: true
---

# /orchestrate-investigation

Use this for ongoing supervision of an investigation or a research wave. Use
/dispatch for a read-only status report, and /deep-investigate for a multi-source
investigation of one target.

Read [the execution contract](../../../docs/EXECUTION_CONTRACT.md) and
[the research workflow contract](../../../docs/RESEARCH_WORKFLOW_CONTRACT.md).
They own context pinning, source applicability, worker handoffs, persistence, and
evidence requirements. Resolve the requested profile/database once and create a
unique `WORKDIR` before scoped work.

## Plan and supervise in the current chat

1. Establish the user's outcome, existing authorization, scope, and any budget.
   Inspect relevant leads and retained artifacts. Define completion in terms of
   answered questions and source coverage, without a finding or worker quota.
2. Identify independent questions and assign each source/file scope one owner.
   Use native subagent tools when parallel work helps; inherit the chat's model
   and reasoning settings unless the user requests an override. Keep simple
   work local. Do not launch headless jobs as an interactive default or fallback.
3. Give workers the pinned context, evidence standard, expected output, report
   path, and write policy. Maintain an assignment/checkpoint file with worker
   IDs, expected reports, completed coverage, and next actions.
4. Continue useful parent work while workers run: verify evidence, investigate a
   separate question, inspect interim artifacts, or prepare integration. Coordinate
   overlap before querying an assigned source or editing another owner's file.
5. Use native messages and bounded waits to steer, collect results, and recover
   failed work. Propagate user corrections promptly. After interruption or
   compaction, read the checkpoint and reconcile workers before continuing.
6. Read every expected report or identify its missing scope. Check source
   identity, quotes, material full-document coverage, ordinary alternatives, and
   contradictions. Correct or follow up on weak evidence before synthesizing.
7. Persist authorized results through supported tracker APIs, reconcile lead
   dispositions, and report the requested outcome, artifact paths, unresolved
   coverage, and concrete next actions. New syntheses retain their confidence cap.
   Continue until completion or a dependency prevents further useful work.

If native subagents are unavailable, perform the work sequentially and explain
any material limitation. Do not create a new user-owned chat for a subtask.

## Explicit unattended jobs

Only select this path when the user requests unattended/background execution or
when operating a configured automation. Use the staged dispatcher workflow in
the execution contract, including review of actual bundle contents and
content-matching import. Resolve IDs from the selected database; never reuse an
example lead or run ID. Inherit the configured model unless explicitly overridden.

Inspect the command surface before operating it:

```bash
uv run python scripts/dispatcher.py --help
```

Dispatcher status can reconcile persisted process state; it is not the read-only
queue report supplied by /dispatch. Native chat reports have no dispatcher run
receipt. Preserve the unattended path's budgets, deadlines, and import checks.
