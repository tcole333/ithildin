# H runtime defaults and read-only status implementation

Worktree: `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`.
No commit made; parent owns integration. Changed only assigned paths:

- `scripts/dispatcher.py`: DEFAULT_CONFIG model now None; existing command construction omits --model and therefore inherits the Claude runtime's configuration.
- `scripts/dispatch_config.json`: model null. Explicit configured model still produces --model. Existing permissions, timeout/concurrency/budget controls are unchanged.
- `tools/extract_sec_enforcement_parties.py`: extraction/adjudication generation pins removed. Explicit --model wins; otherwise read only root model from `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`) and pass it explicitly. If no selection exists, omit --model. All ignore-user-config/ignore-rules/strict-config/read-only/sanitized-environment/disabled-feature controls remain. Invalid/malformed configuration fails without printing config contents.
- New `tools/investigation_status.py`.
- New dedicated `tests/test_runtime_model_defaults.py` and `tests/test_investigation_status.py`.

## Status interface

`uv run python tools/investigation_status.py --profile PROFILE --db ABS_DB --output FILE [--recent-days 7]`

Optional --profile and --db use the canonical `investigation_context.task_environment` resolver, preserving pinned environment and otherwise consulting only the selected database's default. Output always records absolute db_path and resolved profile_id. No profile switches occur. Output is JSON on stdout when --output is omitted; --output writes JSON and prints one compact confirmation. Exit 0 is an available or partially available snapshot; exit 2 is unavailable context/database, invalid window, or output aliasing the DB/sidecars.

JSON: `schema_version="investigation-status/1"`, `status="ok"|"partial"`, `generated_at`, `profile_id`, `profile_validation`, `db_path`, `recent_since`, `metrics`.

Every metric is either `{ "available": true, "value": ... }` or `{ "available": false, "reason": ... }`. Keys: lead_count, leads_by_status, findings_count, findings_by_confidence, recent_findings_count, latest_finding_at, analysis_runs_count, analysis_runs_by_status, latest_analysis_at. Group values are arrays of `{status|confidence, count}`. Recent findings use actual `created_at` and a bounded UTC window; latest timestamps normalize to SQLite UTC datetime text.

Each metric filters its table by profile_id. Missing tables/columns yield unavailable diagnostics instead of zero. Legacy analysis_runs without profile_id is unavailable. No global queue/source health metrics included. Opens SQLite mode=ro with query_only, uses a read transaction, never imports tracker initialization/reaping or runs migrations. Output cannot overwrite the selected DB or its WAL/SHM/journal via resolved paths or existing aliases. Editorial worker received this exact contract.

Profile membership is checked against canonical investigation_profiles.profile_id inside the same read transaction. An absent ID in an available catalog raises ValueError (CLI exit 2, no output file), distinguishing typo/unknown from registered-empty profiles that validly have zero counts. `profile_validation={available:true,registered:true}` confirms registration. If the catalog table or profile_id column is unavailable, membership remains explicitly unverified (`profile_validation.available=false` with reason), overall status is partial, and any available metric counts describe only their literal selected scope. No catalog reconciliation writes occur.

## Model provenance and limits

Extractor reports and persists `model_selection={requested_model,selected_model,selection_source,resolved_model:null}` under validation.execution_context. Selection source is explicit, user_config, or runtime_default. `model` continues to denote the requested selection, never a claimed observed runtime model. With no known selection, model is null and the NOT NULL legacy model_name column contains `runtime-default:unresolved`; reviewed exports render null rather than that sentinel. Existing records export legacy_record provenance with unresolved actual identity. Cache reuse is disabled only when the selected runtime model is unknown, preventing reuse across changed defaults; explicit/configured selection retains normal caching.

The root user configuration is the only inherited model setting. This isolated extractor does not inherit the current desktop task's ephemeral model, project-local configuration, alternate providers, or a named Codex config profile. Use explicit --model to carry one of those choices into this command. Loading all user configuration would weaken the extraction isolation boundary, so it remains disabled. This does not resolve a model alias to an actual deployed model ID; resolved_model is deliberately null.

## Validation

- 97 tests passed: existing extractor suite, existing dispatcher suite, and both new focused suites.
- Tests use temporary fixture SQLite databases and mocked model invocations only. Existing suites used a temporary CODEX_HOME containing `model="fixture-configured-model"`; no personal model configuration or actual model call required.
- Tests cover explicit/configured/unset selection, omitted/default command flags, retained isolation controls, persisted unknown/configured provenance, cache behavior, profile isolation, read-only DB bytes, selected database defaults, missing database noncreation, legacy schema unavailable status, recent date windows, CLI output, and DB hardlink protection.
- Independent H review found a typo profile could masquerade as a successful zero snapshot. Corrected with catalog validation, then added unknown-ID/CLI-no-output, registered-empty, absent-catalog, and legacy-catalog regressions. All 10 status tests pass, plus the full 97-test assigned-path suite.
- Ruff passed all changed Python files. `git diff --check` passed assigned paths. Both CLIs' --help executed successfully.

Command environment: `UV_PROJECT_ENVIRONMENT=/Users/travcole/projects/osint-research/.venv UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache`, using `uv run python` and bash login:false.

Validation command: `CODEX_HOME=/tmp/osint-q8INnbtl/test-codex-home UV_PROJECT_ENVIRONMENT=/Users/travcole/projects/osint-research/.venv UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache uv run python -m pytest tests/test_extract_sec_enforcement_parties.py tests/test_dispatcher.py tests/test_investigation_status.py tests/test_runtime_model_defaults.py -q`.
