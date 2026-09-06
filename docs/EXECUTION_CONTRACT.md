# Execution contract

Read this when selecting an execution path, writing a worker, reviewing staged
output, or recovering interrupted work. This describes the current implementations
and their boundaries. Source planning and evidence handoffs belong to the
[research workflow contract](RESEARCH_WORKFLOW_CONTRACT.md).

## Choose the path and pin its context

| Path | Entry point and state | Completion means |
|---|---|---|
| Supervised chat research (interactive default) | Current chat and native subagent tools; task workdir with assignments, checkpoints, and reports | The parent verifies expected reports, evidence and coverage, persists authorized results, and resolves the question or reports the concrete blocker. |
| Unattended staged LLM research (explicit selection) | `scripts/dispatcher.py launch --review-required` or configured automatic research dispatch; `dispatch_runs` and `dispatch_staging`; currently a headless Claude backend | Process output is ready for review. Canonical import requires approval of the current bundle. |
| Deterministic queue work | `scripts/queue_tools.py`, `scripts/queue_dispatcher.py`, `scripts/agent_worker.py`; `job_queue`, `job_events`, `agent_instances` | The selected Python worker finished its operation or produced material awaiting review. Persona names do not imply an LLM investigation. |
| Direct skill or API work | Interactive agent plus source tools and tracker APIs | The task owner checks the evidence, persists it through supported writers, and explicitly resolves the research question. No dispatcher receipt is created automatically. |

Before importing tracker modules or launching children, set `ITHILDIN_PROFILE` to
the resolved investigation and `ITHILDIN_DB_PATH` to the selected database's
absolute path. The shared active profile is an interactive default, not a routing
mechanism for concurrent work. Pin both values in each task and propagate them to
children. For fixture runs, select a temporary database explicitly.

## Supervise native subagents in the current chat

Use the host's native spawn, message, wait, and follow-up tools when a task has
useful independent work. Keep a simple task local. Inherit the chat's configured
model and reasoning settings; specify a model only when the user requests one.
Do not translate an interactive investigation into `claude -p`, `codex exec`, a
dispatcher launch, or a new user-owned chat. Headless execution is an optional
unattended mode, not a fallback for unavailable native tools.

Give each worker the objective, factual question, pinned profile/database,
applicable source or file scope, write ownership, completion criteria, and unique
report path. State whether it may persist findings or only propose them.
Delegate independent questions rather than duplicate searches; concurrency
follows task complexity and rate limits, without a fixed worker quota. The
parent retains integration ownership and does useful work while children run:
source verification, a separate research question, artifact review, or synthesis
preparation. It may query sources directly, coordinating overlapping ownership.

Track expected reports and worker IDs in the task workdir. Use bounded native
waits and messages to obtain actual status; file size, silence, process exit, and
a successful tool call do not prove research completion. Inspect interim
artifacts when useful, steer or reassign failed work, and reconcile conflicts.
Collect every expected report or identify its incomplete scope before synthesis.
Propagate user corrections to affected workers and update the plan.

For long work, keep a checkpoint with the user's objective and constraints,
resolved profile/database, assignments and worker IDs, completed coverage,
artifact paths, evidence IDs, decisions, unresolved questions, and next actions.
Refresh it at meaningful handoffs or before context compaction. After compaction
or interruption, read the checkpoint and current artifacts, reconcile active
workers, and continue unfinished authorized work. Document length, elapsed time,
a fixed number of findings, or compaction is not itself a stopping condition.
Stop when the outcome is complete or a concrete dependency prevents further
useful authorized work; report partial coverage honestly. Preserve user budgets,
scope, deadlines, and cancellation.

Native workers have no automatic `dispatch_runs` or queue receipt. Reports and
supported tracker writes form their handoff. Do not invent dispatcher IDs or
treat deterministic queue completion as semantic review. The research workflow
contract owns source-reading and coverage requirements.

## Optional unattended and deterministic workers

Select these paths when the user requests unattended/background execution or
when operating an explicitly configured automation. Their process deadlines,
budgets, staging, review, and import controls remain applicable; they do not set
the depth or persistence of interactive chat work.

Queue CLIs also accept `--profile` and `--db-path`; their global options precede
the subcommand. Enqueue persists `payload.profile_id` and absolute `payload.db_path`
for research domains: discovery, investigation, analysis, understanding, and
curation. Explicit payload context wins; children otherwise inherit their parent's
pin. New root jobs may resolve the producer's environment or the selected queue
database's active profile. Children without a pin fail instead of adopting an
ambient profile. A payload database must match the queue database.

Workers execute the persisted context; legacy research jobs without a profile
must be deliberately re-enqueued. System/infrastructure jobs remain global unless
explicitly pinned or inheriting a parent pin. A global worker clears ambient
profile context. `queue_tools submit` checks a supplied payload profile against
`--profile`; `agent_worker` validates an explicit profile before opening its database.

The staged dispatcher captures the profile in `TaskContract` before preflight
and propagates the actual connection's database path. Scoped launches require a
profile; import rejects cross-profile scoped records and checks the source lead's
profile. Entities remain shared. Automatic research/analysis dispatch defaults to
staged review; `job_defaults.review_required` can explicitly opt out. Automatic
triage, infrastructure work, and deterministic `auto_leads` remain direct operations.

## Canonical writes and staged review

New findings require claim type, registered source names, evidence references, and
an exact source quote for every reference. Unverified status is a review state,
not permission to omit provenance. Unsourced questions belong in leads or
hypotheses. Use `findings_tracker.add_finding` for a normal write or
`add_finding_to_db` inside a caller-owned transaction. Staged finding imports use
that same writer, preserving confidence caps, normalized dates, entity links, and
evidence rows. This is a shared **finding** writer; the dispatcher still has
separate import routines for entities, leads, and connections. Legacy incomplete
records need audited repair; they are not evidence that new incomplete findings
meet the contract.

A staged bundle contains `report.md`, `run.json`, and required
`candidate_findings.jsonl`, `candidate_leads.jsonl`, and
`candidate_entities.jsonl` files, including empty ones. Connections are optional.
`run.json` declares research status, source coverage, exact candidate counts,
notes, and an explicit `lead_disposition`; consult `build_staging_instruction`
in the dispatcher for the current field contract.

Review the actual report, evidence, alternatives, and proposed disposition.
Structural readiness alone does not establish factual correctness. Approval stores
a fingerprint of every bundle file, including the absence of the optional file.
Import reads and hashes the bytes it will use, rejects edits or additions since
approval, and imports those parsed records. It holds one `BEGIN IMMEDIATE`
transaction across eligibility, canonical writes, raw-record archival, lead
disposition, and the import receipt. Invalid records roll back the bundle.
Concurrent/repeated imports of the **same run** return its receipt without another
write. `--force` cannot bypass approval or content matching. Files remain writable;
the guarantee is detection of changed reviewed contents, not filesystem immutability.

Unattended operation examples below assume that path was selected, context is pinned, and
`LEAD_ID`/`RUN_ID` identify existing rows in that database:

```bash
uv run python scripts/dispatcher.py launch pursue_lead "$LEAD_ID" \
  --lead-id "$LEAD_ID" --review-required
uv run python scripts/dispatcher.py review --run-id "$RUN_ID"
# After examining this bundle and its proposed outcome:
uv run python scripts/dispatcher.py review --approve "$RUN_ID" --reviewer analyst
uv run python scripts/dispatcher.py import --run-id "$RUN_ID" --actor analyst

uv run python scripts/queue_tools.py --profile "$ITHILDIN_PROFILE" \
  --db-path "$ITHILDIN_DB_PATH" enqueue-lead "$LEAD_ID"
uv run python scripts/queue_dispatcher.py --profile "$ITHILDIN_PROFILE" \
  --db-path "$ITHILDIN_DB_PATH" --dry-run run
uv run python scripts/trigger_engine.py --profile "$ITHILDIN_PROFILE" \
  --db-path "$ITHILDIN_DB_PATH" --dry-run run
```

## Acquisition, liveness, and recovery

`DeepPersonWorker` returns source artifacts and `awaiting_review`, with partial
coverage visible. Successful collection keeps/reopens its lead; incomplete
collection blocks it; all source failures fail the attempt. Collection does not
complete the research question. A staged import applies only the reviewed
`lead_disposition`; `completed` requires research status `completed`, and a source
lead that moved to a terminal state cannot be overwritten by that disposition.

Staged launches reserve their run and PID under `BEGIN IMMEDIATE`, with a duplicate
check for the same running prompt hash. A supervisor waits for that reservation
to commit before starting the worker. Its atomic exit receipt binds the actual
exit code to the run and supervisor PID. Finalization requires a matching successful
receipt, nonempty non-error output JSON, and valid required staging artifacts.
Stop/timeout cleanup signals the process group with TERM, then bounded KILL if
needed, including surviving descendants. A process exit does not approve its bundle.
Existing runs without the new exit receipt fail closed when reaped; parseable old
output cannot establish success. A late finalizer cannot overwrite a stopped run.

Queue dispatchers reserve capacity transactionally before spawning. Failed spawns
release reservations; expired worker identities are retired. Worker transitions
carry both agent ID and attempt number, so old attempts cannot overwrite terminal
or newer work. Heartbeats prove ownership while work runs without extending its
fixed deadline. `_run_process` supervises its subprocess group and kills that
group on timeout/cancellation. In-process Python work is cooperative: cancellation
is checked around execution and tool calls, not at every database/file write.

Pause stops new queue claims; it does not cancel running jobs. Administrative
`JobQueue.set_status(job_id, "cancelled")` revokes job ownership, which the worker
detects through its heartbeat. Use `queue_tools.py mark-stale` for expired claims
or executions. Retries are new attempts and may repeat side effects: each worker
must make its own external writes/retrievals replay-safe. Generic `create_job`
creates a new job per submission; it has no universal semantic deduplication key.

Trigger engines require receipts and jobs in the same database. Due checks,
cooldown/budget accounting, job creation, receipt insertion, and threshold state
updates share one transaction; a receipt failure rolls back its jobs. Their
dry-run does not consume cooldowns. These guarantees apply within that database.
An engine captures its default profile at startup for its whole lifetime; an
explicit trigger payload profile overrides it. Research thresholds count only
that profile's pending triage/findings, with separate findings-delta baselines.
Queue metrics, pool capacity, trigger cooldowns, and hourly budgets remain shared
across profiles. Work selection is profile-scoped; scheduling capacity is global.

## Remaining boundaries and verification scope

- Staged isolation is an instruction, not a database/OS sandbox: the headless
  worker still receives the canonical database path and tool access. Use the
  staged artifact-only workflow; enforcing isolation needs a restricted worker
  environment. `--no-review-required` and configured automatic opt-outs remove the
  staged review guarantee. Recorded cost caps are soft controls.
- `EditorReviewWorker` performs deterministic content checks. Its approval or a
  completed queue job is not semantic editorial review or a publication receipt.
  Use the [dossier review workflow](../.codex/skills/review-dossiers/SKILL.md) and
  [content-bound receipt validation](../scripts/review_dossier_checks.py) for that
  separate gate.

`tests/test_orchestration_hardening.py`, `tests/test_queue_lifecycle_hardening.py`,
`tests/test_staged_process_lifecycle.py`, `tests/test_queue_profile_pinning.py`, and
`tests/test_finding_mutation_invariants.py` cover fixture imports, mutation rejection,
rollback/replay, explicit lead outcomes, concurrent triggers/reservations, attempt
ownership, deadlines, subprocess status/group cleanup, context propagation, and
finding provenance. They do not establish universal worker idempotence,
adversarial worker isolation, semantic evidence correctness, or end-to-end
descendant cancellation for every execution path.
