# Queue profile and database capture

Implemented the D6 enqueue/trigger gap without changing the shared active profile or touching the live database.

## Result

- `JobQueue.create_job` records `payload.db_path` as the canonical absolute queue DB path. An explicit conflicting database fails instead of being silently overridden; this queue/worker architecture uses one database for jobs and investigation rows.
- Discovery, investigation, analysis, understanding, and curation jobs must have a profile before insertion. Precedence is explicit payload profile, persisted parent context, producer `ITHILDIN_PROFILE`, then the active default read only from the selected queue database. Invalid explicit pins never fall back.
- A research child without an explicit or inherited parent profile fails. Parent pins are read inside the enqueue transaction; queue retries and caller-owned transactions retain atomic job/event behavior.
- System and infrastructure domains remain global unless their payload or parent explicitly carries a profile. Global queue metrics, capacity, cooldowns, and hourly trigger budgets remain shared.
- TriggerEngine captures its default profile at construction, so daemon iterations cannot switch investigations when another task changes the interactive default. Per-trigger payload profiles win. CLI global `--profile` selects that captured default; global `--db-path` now honors `ITHILDIN_DB_PATH` by default.
- `pending_triage`, `findings_total`, and `findings_delta` trigger metrics filter by the effective trigger profile. Delta counters use a profile-specific state key. Trigger cooldowns and hourly budgets deliberately remain global.
- Workers use only the queued profile and queue DB for subprocess context. Legacy unpinned research jobs fail their attempt before execution; they require deliberate re-enqueueing with a chosen profile. Worker execution no longer mutates process-global `os.environ`, preventing simultaneous workers from changing each other's ambient profile.
- Four review/freshness enqueue sites now set `parent_job_id`, allowing canonical context inheritance and preserving actual lineage: mechanism explainer, analytical article, dossier update review, and freshness-requested dossier update.
- DossierFreshnessWorker filters findings and connection timestamps by profile, uses exact JSON target/profile matching for pending update deduplication, and accepts a dossier as a freshness baseline only when its `profile_ids` includes that profile. A same-named subject or pending update in another investigation cannot suppress or generate this profile's work.

## Owned changes

- `queue_system/queue.py`
- `queue_system/triggers.py`
- `scripts/trigger_engine.py`
- `queue_system/worker.py`: execution context, four parent links, and authorized dossier freshness follow-up only; existing unrelated changes preserved.
- `tests/test_queue_profile_pinning.py`: 24 focused test cases including parametrizations, delayed defaults, parallel children/workers, no-live-DB fallback, invalid pins, conflicting DBs, global jobs, legacy rejection, scoped thresholds, daemon capture, CLI context, freshness isolation, and review lineage.
- Synthetic profile fixture updates in `tests/test_queue_orchestration.py`, `tests/test_queue_analysis_persona_workers.py`, `tests/test_queue_understanding_persona_workers.py`, `tests/test_content_pipeline_workers.py`, and `tests/test_queue_dispatcher.py`.

## Verification

The combined queue, trigger, worker, dispatcher, orchestration-hardening, content-worker, and CLI integration selection passed: **120 tests in 4.62 seconds**. Full output: `/tmp/osint-CUTDyZF1/queue-profile-tests.txt`.

Ruff passed for all ten changed Python paths. `git diff --check` passed for the owned paths.

Command:

```bash
uv run pytest tests/test_queue_profile_pinning.py tests/test_queue_lifecycle_hardening.py tests/test_orchestration_hardening.py tests/test_trigger_engine.py tests/test_queue_system.py tests/test_queue_workers.py tests/test_queue_orchestration.py tests/test_queue_analysis_persona_workers.py tests/test_queue_understanding_persona_workers.py tests/test_content_pipeline_workers.py tests/test_queue_persona_workers.py tests/test_queue_validation_infra_workers.py tests/test_queue_dispatcher.py tests/integration/test_trigger_engine_cli_integration.py tests/integration/test_queue_cli_integration.py -q -p no:cacheprovider
```

No Git mutations or live investigation DB operations were performed. The parent was asked to log the newly reproduced missing-parent-lineage papercut because this subtask explicitly prohibited live DB writes. Execution documentation is coordinated with workflows_review.
