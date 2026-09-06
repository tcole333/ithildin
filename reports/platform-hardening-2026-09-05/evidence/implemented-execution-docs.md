# O7 execution contract documentation audit

Owned files: `docs/EXECUTION_CONTRACT.md` and `docs/TOOL_REFERENCE.md`. No code or Git changes were made by this worker. The new contract distinguishes staged LLM research, deterministic queue operations, and direct skill/API work; covers context pinning, canonical finding insertion, reviewed bundle import, acquisition versus research completion, liveness/cancellation, retries, and trigger atomicity.

The tool reference links to the contract and fixes the invalid `queue_dispatcher.py run --dry-run` example to `queue_dispatcher.py --dry-run run`. The old form was reproduced as parser exit 2 with a temporary DB path; the corrected full argument order was checked with a stubbed handler, so no work was dispatched.

## Initial checks

- `tests/test_orchestration_hardening.py` and `tests/test_queue_lifecycle_hardening.py`: **50 passed in 3.33 seconds**, offline, fixture databases. Log: `/tmp/osint-CUTDyZF1/execution-hardening-docs-tests.txt`.
- Ten actual CLI `--help` invocations: dispatcher top-level/launch/review/approve/import/stop, queue enqueue and stale handling, queue dispatcher, agent worker. All passed under `ITHILDIN_PROFILE=epstein` and an explicit task-local `ITHILDIN_DB_PATH`; the operational database file was not created.
- Exact corrected queue dispatcher global-option order parsed with its run handler stubbed. Detailed results: `/tmp/osint-CUTDyZF1/execution-docs-checks.json`.
- Relative document links resolve, code fences balance, and the stale dry-run command is absent from the tool reference.
- Papercut **#1** logged and resolved only in `/tmp/osint-CUTDyZF1/execution-papercuts.db`; no production papercut DB writes.

## Findings sent to implementation owners

1. **Canonical finding provenance mismatch:** `findings_tracker._validate_finding_candidate(publication=False)` intentionally allowed missing evidence/quotes for non-direct drafts, whereas staged ingestion required complete quoted refs. Its docstring and `tests/test_finding_evidence_crud.py::_add_draft`, `test_http_refs_are_urls_and_canonical_slash_refs_are_not_files`, and the evidence-repair tests support that implementation behavior. `AGENTS.md` and `RESEARCH_WORKFLOW_CONTRACT.md` authorize no exception for new findings. The six pure-validator acceptances recorded in the checks JSON establish the original mismatch without writes. Recommendation sent to root: enforce complete provenance on new canonical insertion; preserve legacy read/audit/repair; keep unsourced ideas as leads/hypotheses. Root assigned `finding_insert_integration`.
2. **Staged process lifecycle:** finalization inferred success from parseable JSON instead of actual OS status; stop/timeout signaled the parent PID; launch duplicate checks lacked atomic reservation. Automatic dispatch also omitted the resolved profile from its contract and used legacy direct mode. Root assigned `staged_process_hardening`.
3. **Trigger enqueue context:** trigger creation copied an unpinned payload; bundled research triggers were disabled and lacked a profile. Work would inherit the eventual worker's environment instead of an enqueue-time context. Root assigned `queue_profile_pinning`. Scheduling capacity/budget scope must be distinguished from investigation work selection.

## Trust boundaries retained

- Staged artifact-only work is a prompt contract; workers still have tool access and the selected canonical DB path. It is not an adversarial isolation boundary.
- Generic queue jobs and worker retries do not provide universal semantic deduplication or exactly-once side effects.
- In-process Python worker mutations are not preempted/rolled back at every cancellation point.
- Queue `EditorReviewWorker` heuristics and a completed job do not substitute for semantic editorial review or content-bound release receipts.
- The shared canonical writer described is the finding writer; dispatcher entity/lead/connection import routines remain separate.

## Integration status

**Finding insertion verified.** Inspected the new `add_finding_to_db` boundary: every ref requires a quote, nontext quotes fail, and `publication=True` on candidate validation requires nonempty refs for every claim type while the inserted status remains `unverified`. The permissive lower-level validator remains available for legacy correction/repair. Independently ran `tests/test_finding_mutation_invariants.py` with `--offline` and an explicitly pinned task-local profile/DB: **49 passed in 7.21 seconds**, including complete-provenance rejection cases and read/correct/repair/verify of a legacy SQL fixture. Log: `/tmp/osint-CUTDyZF1/execution-insert-verification.txt`. The document's insertion gap is removed.

**Process/profile code inspected and documented.** The staged supervisor now waits for the committed run/PID reservation, writes an atomic actual-exit receipt, rejects missing/foreign/error receipts and output, terminates process groups, and preserves prior terminal outcomes. Auto research/analysis uses staged review by default; maintenance operations remain direct and configured review opt-outs are explicit. Existing runs without a receipt fail closed. The process owner reports **62 passed** across its new lifecycle, dispatcher, and orchestration suite, with Ruff clean.

Queue enqueue persists `profile_id` and absolute `db_path`; explicit job context wins, children inherit a persisted parent, and new root research jobs alone can capture producer/default context. Legacy unpinned research execution and unpinned research children fail. Triggers capture a lifetime profile, allow explicit per-trigger profiles, and scope research metrics/delta baselines while budgets, cooldowns, and pool capacity remain shared. Inspected the queue owner's final handoff: **120 combined tests passed in 4.62 seconds**, including 24 new pinning cases; Ruff clean. Report: `/tmp/osint-CUTDyZF1/implemented-queue-profile-pinning.md`.

The new trigger CLI passed actual `--help` plus exact example argv parsing with its handler stubbed. No operational DB was created. Relative links/fences and the corrected old example passed again. Results: `/tmp/osint-CUTDyZF1/execution-docs-final-checks.json`.

**Independent integration check caught and verified a further cleanup fix.** The first run of the two new process/context modules returned **1 failed, 48 passed in 1.99 seconds**. `test_failed_launch_transaction_cannot_leave_a_worker_executing` hit `PermissionError` at the post-TERM `os.killpg(pid, 0)` probe while handling an injected PID registration failure, masking the intended launch failure record. Initial log: `/tmp/osint-CUTDyZF1/execution-context-process-verification.txt`.

The process owner reproduced a transient macOS dying-child signal-0 denial (5/30 samples before reaping), added transient and persistent-denial regressions, and now treats denied probes as unknown while retaining bounded grace and the final KILL/error path. I inspected the fix and independently reran the final process/profile modules: **54 passed in 1.89 seconds** with `--offline` and explicit task-local profile/DB. Final log: `/tmp/osint-CUTDyZF1/execution-context-process-final.txt`. Task-local papercut #2 is resolved. No skipped failing gate or weakened permission-error outcome was used.

## Final outcome

Both owned documents are complete. The contract describes verified current mechanisms and separately states remaining trust boundaries. CLI examples were checked through help/parser execution without dispatching workers or creating an operational database. No production code, Git state, live findings, review verdicts, or shared profile settings were changed by this documentation subtask.
