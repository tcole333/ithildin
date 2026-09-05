# Orchestration and staging review

Reviewed the current working tree on 2026-09-05. No production files were edited, no workers were launched, no external source queries were made, and no live investigation rows/jobs were changed. Fixtures use temporary SQLite databases built from the repository schema. The 24 existing tests in `tests/test_queue_system.py`, `tests/test_queue_dispatcher.py`, and `tests/test_dispatcher.py` pass; the isolated repros below expose invariants those tests do not cover.

There are two distinct execution paths. `scripts/dispatcher.py` launches Claude CLI workers and imports reviewed JSONL bundles. `scripts/queue_dispatcher.py` launches `scripts/agent_worker.py`, whose Python persona implementations consume `job_queue`. They explicitly operate independently; a fix in one will not repair the other. TriggerEngine feeds the latter queue. Current `scripts/trigger_config.json` disables every trigger, so the trigger defect is latent until enabled. I did not inspect live process/job frequency and do not claim all these paths are in active use.

## Ranked findings

### 1. [P1] Staged findings bypass the platform's evidence and confidence rules

**Location:** `/Users/travcole/projects/osint-research/scripts/dispatcher.py:2043` (mapping through 2065); canonical comparison `/Users/travcole/projects/osint-research/tools/findings_tracker.py:1002` and `:1082`.

`import_findings` implements a second raw INSERT writer. It passes through the worker's confidence and claim type, omits `evidence_ids`/`source_quotes`, and maps `source_quote`/`source_url` as if they were findings columns. `sanitize_insert_payload` drops columns absent from the schema. There is no insertion into `finding_evidence`, no canonical entity linkage, no date normalization, and no confidence cap. The staged worker example at `scripts/dispatcher.py:613` also does not teach the canonical evidence fields.

**Verified:** An approved fixture with `claim_type=inference`, `confidence=confirmed`, a supplied evidence reference/quote, and date `2025` imports successfully. Persisted confidence remains `confirmed`; `finding_evidence` has zero rows; `event_date_iso`/`date_precision` remain NULL. Raw JSON archival preserves a copy of the input, but the canonical evidence graph and reader/audit queries do not receive it.

**Impact:** The review/import path undermines the platform's central evidence promise even for workers that supply evidence. Imported conclusions can appear more certain than the canonical tracker allows, and imported dates disappear from normalized timeline queries.

**Smallest sound remedy:** Extract transaction-aware canonical finding validation/insertion from `findings_tracker.add_finding` and call it from both CLI and importer using the importer's connection. Define one staged finding schema matching that function, including evidence refs/quotes; reject invalid records before any canonical mutation. Do not simply call the current public tracker function inside the import transaction: it opens its own connection and would introduce the same locking pattern as finding 6.

### 2. [P1] Incomplete staged bundles can be approved, imported, and close the source lead

**Location:** `/Users/travcole/projects/osint-research/scripts/dispatcher.py:2890`, `:2547`, `:2637`; readiness is computed separately at `:1046`.

Inspection correctly reports `ready=False` when required candidate files are absent, but approval and import check only `validation_error`. Missing JSONL files deserialize to an empty list (`load_jsonl`, line 768); an empty JSON object satisfies the only `run.json` check. On import, the source lead is completed regardless of the worker's reported status, missing artifacts, skipped/invalid candidate rows, or completion assessment.

**Verified:** A fixture containing only `report.md` and `run.json` with `{}` had all three required candidate files missing and `ready=False, validation_error=None`. `cmd_review --approve` accepted it; `import_staged_run` reported zero imported records and changed the source lead from `open` to `completed`.

**Impact:** A partial/crashed worker can remove an unresolved lead from the queue under the appearance of successful reviewed work. Legitimate zero-findings investigations also need explicit outcome semantics; record count alone is not a safe completion rule.

**Smallest remedy:** Require `inspection.ready`, a completed worker/run state, and a validated `run.json` outcome before approval/import. Treat lead disposition as an explicit reviewed value (`completed`, `blocked`, `dead_end`, leave open), not an automatic effect of importing artifacts. Freeze or hash the approved bundle so files changed after review require review again; currently review approval is attached to a mutable directory, not its contents.

### 3. [P1] Queue triage discards distinct leads solely because they share a subject, including across profiles

**Location:** `/Users/travcole/projects/osint-research/queue_system/worker.py:299`, `:328`, `:359`.

`LeadTriageWorker` reads pending leads from every profile. Its first duplicate check considers any non-pending lead with the same target name a duplicate, without comparing the investigative question or profile. The resulting live path calls `dead_end_lead`.

**Verified in dry-run fixture:** A completed `profile-a` lead titled “Trace corporation ownership” and a new `profile-b` lead titled “Inspect independent court testimony” with the same target caused the new lead to be returned in `duplicates`. Supplying `payload.profile_id='profile-b'` has no effect because this worker does not read it.

**Impact:** The platform intentionally supports multiple leads and investigations per entity. This rule systematically destroys useful follow-ups and cross-investigation work; it is not merely an imperfect fuzzy matcher.

**Smallest remedy:** Require and enforce the job's profile throughout selection and updates. Same target should be a candidate for duplicate review, not proof; use a shared conservative question/title comparison with explicit lead relationship creation. Add fixtures for distinct questions, distinct profiles, and same-question follow-ups after completion.

### 4. [P1] Failed source queries still complete the investigation and its lead

**Location:** `/Users/travcole/projects/osint-research/queue_system/worker.py:179`, `:515`, `:525`, `:67`.

`_run_tool` returns nonzero exit codes as ordinary data. `DeepPersonWorker` writes their errors to a report, unconditionally calls `lead_tracker.complete_lead`, and returns no failing `job_status`. The base loop defaults that result to queue `completed`. Therefore normal source outages, invalid CLI arguments, and other tool errors bypass the queue's retry mechanism and still close the lead.

**Verified:** With both configured tools mocked to return exit code 1 (“Source unavailable”), the worker called `complete_lead(..., "Deep investigation completed ...")` and returned the base loop's default completed status.

**Impact:** Failed collection looks like completed research and triggers downstream work. This is especially misleading because this persona collects search results and emits a tool-result report; it does not itself inspect the documents or produce evidence-backed findings.

**Smallest remedy:** Establish a shared typed tool-result policy distinguishing success, partial collection, and retryable failure. On total failure, raise or return a failure outcome; on partial coverage, preserve the lead as open/blocked or awaiting review. A successfully written report should not determine research completion. Audit other Python persona wrappers against the same rule rather than adding isolated per-persona checks.

### 5. [P2] Concurrent imports can import the same approved run twice

**Location:** `/Users/travcole/projects/osint-research/scripts/dispatcher.py:2539`, `:2550`, `:2602`, `:2621`.

The `already imported` guard runs before the import transaction, and inspection commits before file loading. Two CLI/task processes can both pass the guard; each then writes its own transaction. Neither the later UPDATE nor raw-record archive enforces exclusive ownership or a uniqueness key. Findings are inserted without duplicate protection.

**Verified:** A barrier-controlled test using two independent SQLite connections let both importers finish the eligibility check before either inserted. Both returned `{findings: 1, ...}`; one staged finding became two canonical findings and two archived raw records. This proves an actual race rather than relying on a hypothetical interleaving.

**Smallest remedy:** Load/validate the approved immutable bundle, then acquire `BEGIN IMMEDIATE` and recheck/transition import state inside the same transaction before inserting. Add uniqueness on import provenance (run, artifact, record index/hash) and preserve the final state across duplicate requests. Related code-only issue: `cmd_import` at line 2988 catches “already imported” and overwrites `import_status='failed'`, so even a sequential repeated CLI import corrupts the terminal marker.

### 6. [P2] Two due triggers self-deadlock and lose their scheduling history

**Location:** `/Users/travcole/projects/osint-research/queue_system/triggers.py:257`–264 and `:303`–314, with `_create_job` at `:201`.

The engine creates a job through JobQueue's separate connection (which commits), then records the trigger through its own connection but keeps that write transaction open until the end of the loop. On the next due trigger, JobQueue tries to write while the engine holds SQLite's writer lock. Increasing busy timeout does not solve a same-thread wait on its own uncommitted connection.

**Verified:** In both scheduled and threshold mode, two enabled due fixture triggers produce `sqlite3.OperationalError: database is locked`. One job remains committed but zero `trigger_runs` rows remain, because the exception closes/rolls back the engine connection. A future run can enqueue that first trigger again without any cooldown history.

**Scope caveat:** Shipped triggers are currently disabled, lowering immediate exposure; enabling multiple ordinary triggers exercises the defect.

**Smallest remedy:** Provide transaction-aware queue creation and atomically insert each job plus its trigger receipt/state on the same SQLite connection. Merely committing the receipt before the next loop iteration avoids the deadlock but retains a crash window and concurrent duplicate enqueue risk. Add a two-due-trigger test (existing single-trigger tests cannot catch this).

### 7. [P2] A worker doing useful work for 90 seconds is treated as dead and replaced

**Location:** `/Users/travcole/projects/osint-research/queue_system/worker.py:50` and `:67`; `/Users/travcole/projects/osint-research/scripts/queue_dispatcher.py:50` and `:82`.

Heartbeats occur only at the top of the synchronous execution loop. During `execute`, including network subprocesses, no heartbeat is sent. Dispatcher counts only agents with a recent heartbeat (90 seconds by default). With more pending jobs, a long-running worker disappears from the active count and another worker is spawned, even with `max_workers=1`. The old process is still running and eventually returns to polling; there is no scale-down path to remove the extra process.

**Verified:** One `in_progress` worker with heartbeat 91 seconds old plus one pending job produced an empty active-agent count and a spawn=1 action under max_workers=1. No actual worker processes were launched.

**Impact:** The documented worker cap does not bound concurrent load during normal slow searches. Repetition with a backlog can accumulate live processes, increase source pressure, and worsen SQLite contention.

**Smallest remedy:** Move heartbeats into a supervisor that remains responsive during subprocess execution, maintain process/job identity, and explicitly reconcile expired workers before replacement. Pair this with guarded job state transitions. The queue currently permits a late `complete_job` to overwrite `cancelled` or `stale` because the UPDATE checks only the job ID (`queue.py:590`); the fixture demonstrated cancelled→completed.

## Smaller verified/code-path observations

- **Custom database selection stops at the dispatcher:** `queue_dispatcher.cmd_run` reads `args.db_path` at line 114, but `spawn_workers` at line 96 passes no DB path; `scripts/agent_worker.py:34` always constructs `JobQueue()` for the default live DB. Using a separate dispatch DB can therefore spawn workers against the wrong queue. No processes were started to demonstrate this; the complete command path is directly visible. Pass the same validated DB path end to end, including tracker operations invoked by a worker.
- **Unbounded subprocess calls compound liveness defects:** `_run_tool`/`_run_script` use `subprocess.run` without timeout. Job `timeout_seconds` does not cancel these subprocesses. `mark_stale_jobs` is a manual CLI action and marks only DB state. It is not an execution deadline.

## Proportionate simplification direction

The most useful simplification is to remove duplicate semantic implementations, not replace SQLite or rewrite the platform.

1. **One canonical mutation service.** Keep the existing tracker CLIs, but move their validated database writes into connection-aware functions. Make staging import and queue workers call those functions. This directly fixes evidence divergence, date normalization omissions, and transaction composition problems without changing the storage model.
2. **One explicit task contract.** Require profile, target/lead, expected outputs, outcome, deadline, and reviewed lead disposition. “A process exited,” “a report exists,” “search collection succeeded,” and “the lead is resolved” should be separate fields, with a small documented transition table. Collapse the overlapping `status`, `health_status`, `review_status`, and `import_status` assumptions by assigning each one a specific responsibility.
3. **Choose the supported orchestration path before expanding personas.** The staged Claude dispatcher and Python persona queue implement many similarly named operations with very different capabilities. Keep source collection/export as Python jobs and use an actual agent backend for investigation/verification; make the two meet at the same artifact/validation contract. Alternatively, if the generic persona path has no active users, deprecate its research personas and retain only deterministic jobs. This needs usage evidence, not a sweeping replacement.
4. **Centralize lifecycle mechanics.** A small supervisor should own child-process launch, heartbeat, deadline, cancellation, and terminal-state reconciliation. Reuse that for both execution adapters. Keep SQLite/WAL, but use a single connection for each atomic unit and conditional transitions/uniqueness for concurrency.
5. **Test invariant boundaries.** The present 24 tests pass while all seven repros fail the intended behavior. Add compact tests around concurrent import, missing required artifacts, explicit blocked outcomes, canonical evidence round-trip, cross-profile same-subject leads, total source failure, and multiple due triggers. Avoid multiplying happy-path tests of persona report strings.

## Reproduction artifacts and commands

- Script: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/repro-orchestration.py.txt`
- Results: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/orchestration-results.json`
- Worker semantics script: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/repro-worker-semantics.py.txt`
- Results: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/worker-semantics-results.json`

From repository root, using bash without login startup:

```bash
PYTHONPATH="$PWD" uv run python /Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/repro-orchestration.py.txt
PYTHONPATH="$PWD" uv run python /Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/repro-worker-semantics.py.txt
uv run python -m pytest tests/test_queue_system.py tests/test_queue_dispatcher.py tests/test_dispatcher.py -q
```

The scripts create fresh temp databases on each run. The first fixture harness iteration attempted to query a `finding_entities` table absent from the minimal `_ensure_schema` fixture; that assertion was removed, and entity-link omission is supported by the import call path rather than that runtime result. No unrelated shell/tooling papercut occurred during this review.
