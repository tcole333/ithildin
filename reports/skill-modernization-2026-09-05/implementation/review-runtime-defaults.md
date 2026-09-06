# Independent runtime-defaults review

Reviewed worktree: /Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905

Scope: the model-default changes in scripts/dispatcher.py and scripts/dispatch_config.json; the model selection, execution/provenance and export delta in tools/extract_sec_enforcement_parties.py; new tools/investigation_status.py; relevant fixture tests and the task_environment context resolver. No source files, production databases or model jobs were changed or run by this reviewer.

## Outcome

No remaining material findings in the reviewed current code. One P2 false-zero status issue was identified, reported promptly, fixed by the status owner, and independently rechecked.

## Finding discovered and resolved

**P2 — A nonexistent selected profile was reported as an empty successful investigation.**

The original collect_status implementation accepted the syntactically valid identifier returned by task_environment and immediately aggregated profile_id-filtered rows. Schema completeness alone produced status=ok, so a typo such as alhpa returned available=true/value=0 for every counter even when the canonical investigation_profiles catalog contained alpha and alpha had activity.

The independent canonical reproduction used a temporary database with investigation_profiles(profile_id TEXT PRIMARY KEY, display_name TEXT), registered alpha, and complete leads/findings/analysis_runs tables populated for alpha. Before the fix, collect_status('alhpa', fixture, environ={}) returned status=ok and lead_count=0. An initial legacy id/name catalog fixture exhibited the same false-success behavior.

The status owner added read-only catalog validation in [investigation_status.py](/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905/tools/investigation_status.py:37):

- A usable canonical catalog that lacks the requested profile raises ValueError; the CLI exits 2 without creating its output.
- A registered empty profile remains a valid zero-count result.
- Missing/legacy catalogs expose profile_validation.available=false and an explicit unverified-membership reason, making the whole snapshot partial.
- Schema-available scoped counts in legacy databases remain descriptive rather than being mistaken for proof that the requested investigation exists.

Independent post-fix reproduction returned:
- unknown profile: ValueError “Unknown investigation profile 'alhpa' in selected database”;
- registered empty: status=ok, profile_validation.available=true, lead_count=0;
- database unchanged: True.

The updated 10-test status suite passes, including typo, registered-empty, missing/legacy catalog and nonmutation cases.

## Model inheritance and isolation review

### Dispatcher

The only behavior change is replacing the implicit sonnet selection with null in the default/configured dispatcher model. [ClaudeBackend.build_command](/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905/scripts/dispatcher.py:386) already appends --model only for an explicit nonempty override. Consequently the compatibility dispatcher now leaves model selection to its configured Claude runtime while preserving allowed tools, permission mode, no-session-persistence, budget, timeout and staging behavior. Explicit model overrides remain intact.

No new launch or authority path was introduced by this delta. It does not imply that a separate Claude process inherits a Codex chat's in-memory model choice; this is the explicitly selected unattended compatibility path.

### SEC party extractor

[resolve_model_selection](/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905/tools/extract_sec_enforcement_parties.py:2816) resolves an explicit override first, then only the root user's model field from CODEX_HOME/config.toml, otherwise an unresolved runtime default. It validates the value as a model token and suppresses raw malformed TOML contents in its public error.

This reads only the model selection; it does not re-enable user hooks, tools, rules, plugins, profiles or custom providers. The execution boundary retains --ignore-user-config, --ignore-rules, --strict-config, --ephemeral, read-only sandbox, disabled agentic features, schema-constrained output, stdin evidence, and the credential/environment allowlist. Existing tests cover exact ChatGPT-auth requirements and removal of provider credentials.

The selected model is passed as --model only when known. run_extractions records requested/selected model and selection_source separately from resolved_model=None. An unresolved choice uses an internal non-model sentinel only for persisted identity/request hashing, never as a CLI model argument; it disables cache reuse when the runtime default is unknown. Configured/explicit choices retain the existing requested-model cache semantics. Reviewed exports map the sentinel to model=null and preserve model_selection; legacy records receive explicitly labeled legacy provenance.

No weakened quarantine boundary, silent API-key fallback, inferred runtime identity, or dropped extraction attempt provenance was found.

## Status scope/nonmutation review

After the profile fix, the snapshot:
- resolves profile and database once;
- opens the selected DB with mode=ro and query_only;
- uses a read transaction for its aggregate snapshot;
- requires live profile_id and metric-specific columns;
- marks absent schema unavailable instead of fabricating zero;
- scopes all research counters to the selected profile;
- computes the recent window using parsed timestamps and an as-of upper bound;
- protects output from overwriting the selected DB, its sidecars and existing aliases.

The tests cover mixed timestamp formats, future rows, explicit versus inherited context, legacy schema, missing DB creation, hardlinked output aliases, invalid recent windows, and unchanged DB bytes. No production DB was opened during review.

## Verification performed

With the assigned isolated runtime environment:

- uv run python -m pytest tests/test_runtime_model_defaults.py tests/test_investigation_status.py tests/test_extract_sec_enforcement_parties.py --offline -q: **84 passed** before the status catalog fix.
- Following that fix, independently reread the changed status code/tests and ran uv run python -m pytest tests/test_investigation_status.py --offline -q: **10 passed**.
- Independently reproduced the canonical unknown-profile and registered-empty cases against the fixed implementation and confirmed unchanged DB bytes.

No live Claude/Codex model command, source query or production mutation was used. CLI argument construction and execution effects were inspected or exercised through fixtures/mocks.

## Explicit limits

The extractor does not observe the runtime-resolved model and correctly records that limitation. Named model profiles or an interactive session's in-memory selection require an explicit --model, as documented by the resolver; this review does not claim broader runtime state inheritance. Tests establish the isolated command/provenance contract, not successful access to any particular currently available model.
