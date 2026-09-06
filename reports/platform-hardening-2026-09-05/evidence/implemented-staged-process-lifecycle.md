# Staged subprocess lifecycle integration

Owned edits: `scripts/dispatcher.py`, new `tests/test_staged_process_lifecycle.py`, and the authorized auto-dispatch regression update in `tests/test_dispatcher.py`. No Git changes, canonical database writes, backend/API calls, or live worker launches were performed. All spawned processes were local fixture Python commands and all test databases were temporary.

## Changes

- `launch_job` resolves the interactive profile once before hashing/preflight and pins it in the task JSON and child environment. The child database path comes from the actual SQLite connection, avoiding divergence from a module default. Scoped workers without a resolved profile fail before launch; global `build_infra` remains supported.
- Auto-dispatch contracts capture the profile selected when choosing work and the selected lead ID. Research/analysis follows `job_defaults.review_required`, defaulting to staged review. An explicit `False` remains an opt-out. Auto triage, build_infra, and auto_leads retain direct maintenance behavior.
- Launch reservation uses a short `BEGIN IMMEDIATE` transaction around the authoritative duplicate check, run insertion, subprocess launch, and PID registration. Preflight/prompt preparation is outside the lock. Two concurrent launchers of an identical contract can launch only one worker.
- A detached local supervisor waits for its matching run ID/PID to become visible as a committed running reservation before starting the worker. A rolled-back or cancelled launch cannot leave an unregistered research worker running. Failure while registering the PID terminates the supervisor and records a failed launch.
- The supervisor captures the worker's actual return code and atomically writes `raw_output.json.exit.json`, bound to the run ID and supervisor PID. A later dispatcher invocation can finalize without access to the original `Popen` object. Each attempt gets a unique output/staging directory, preventing same-second result collisions.
- Finalization requires a valid matching process receipt, nonempty object-shaped output, no backend error payload, and (for staged runs) valid required artifacts. Nonzero exits remain failed even with parseable JSON; zero exits with backend errors, empty/malformed output, or missing artifacts fail. The database stores the actual process exit code separately from workflow success. A missing status stays unknown (`NULL`), not an invented successful or failed process code.
- Finalization uses a terminal compare-and-set guard, preserving a concurrent manual stop/timeout.
- Stop, timeout, and dead-leader cleanup use process-group TERM followed by a bounded KILL escalation. Descendants are terminated even if the original leader has died. Own supervisor zombies are reaped instead of being mistaken for active work.

## Validation

```
uv run ruff check scripts/dispatcher.py tests/test_staged_process_lifecycle.py tests/test_dispatcher.py
uv run pytest tests/test_staged_process_lifecycle.py tests/test_dispatcher.py tests/test_orchestration_hardening.py -q --offline -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-staged-final2
```

Ruff clean. **62 passed in 4.13s**, including 30 new staged lifecycle regressions. `git diff --check` clean for owned paths.

Tests include actual local subprocess exit 0 and 7, restart-style finalization through another connection, missing/mismatched receipts, error payloads, invalid artifacts, profile changes during preflight, missing profile refusal, a forced concurrent-launch race, cancelled/uncommitted reservation refusal, an injected database failure after supervisor spawn, TERM-resistant descendant cleanup, all supervision routes, late finalization after manual stop, and explicit maintenance/research mode settings.

An earlier broader run including queue lifecycle/dispatcher tests had **84 passed, 1 failed**. The failure was `tests/test_queue_dispatcher.py::test_get_pending_by_type_counts_pending`, which creates a discovery `source_scan` job without a profile under concurrent queue-context changes. This was reported to root for the queue-context owner; no unrelated queue paths were edited here.

## Rollout and remaining boundaries

- Pre-upgrade active runs do not have exit receipts. Reaping them now fails closed with an explicit unavailable-status diagnostic. Their output remains intact for inspection. Do not infer their subprocess success from JSON.
- The launch supervisor is a process-lifecycle mechanism, not an isolation boundary: the worker still receives broad permissions and the canonical DB environment under a staged prompt contract. Budget caps remain soft. `docs/EXECUTION_CONTRACT.md` owner has the exact mechanisms and limitations.
- Group termination covers descendants that remain in the launch process group. Programs that intentionally detach into another session are outside that lifecycle group.
- The three existing O7 papercut observations should be associated/resolved by the task owner; this worker honored the explicit no-live-database constraint.

## Independent verification follow-up

The documentation owner caught an intermittent macOS `PermissionError` in the process-group signal-0 probe after TERM. A dedicated local reproduction observed EPERM in 5 of 30 samples while the dying child had not yet been reaped; after reaping, probes returned ESRCH. The liveness probe now treats EPERM as unknown/present and continues the existing bounded grace period. It still escalates to KILL, and an actual denied KILL propagates an error rather than claiming cleanup succeeded. Two focused regressions cover both outcomes. The corrected full focused suite passed as recorded above, and 30 further real local cleanup probes all succeeded (`/tmp/osint-CUTDyZF1/staged-group-cleanup-probe.json`). The documentation owner logged this as isolated papercut #2 in `/tmp/osint-CUTDyZF1/execution-papercuts.db` and is independently verifying before resolving it.
