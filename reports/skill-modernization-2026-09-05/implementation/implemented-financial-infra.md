# Unit F implementation handoff

Worktree: /Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905
Ownership: paired financial/source integration skills, their Codex starter prompts, paired source-integration references, tools/query_990.py, and a dedicated test file. No commits or production database/source jobs were performed.

## Result

All five audited defect groups are addressed:

1. **FI-1 quote parsing/persistence:** audit-contracts now uses matching `USASPENDING:<SCOPE_REF>` evidence and `REF:exact rows` source quote syntax. Method/query/period/artifact context lives in detail. Both runtime examples execute against isolated tracker fixtures and retain exact quote, profile, synthesis type and medium confidence.
2. **FI-2 positive revolving-door results:** replaced tuple-based inline SQL with profile-scoped `findings_tracker.py search` and structured jq output. Both examples are tested on positive matches plus another profile containing matching text.
3. **FI-3 pinned database/thread routing:** removed unscoped checkout SQLite snippets from all seven skills. Audit-contracts and screen-targets map profile-local thread IDs through the profile artifact before using the tracker, tested with local 3 mapped to global 73 and a foreign global 3. Missing mappings stop before any tracker/DB creation. `query_990 cross-ref` resolves `ITHILDIN_DB_PATH` at invocation, opens the selected DB read-only, never falls back from a missing pin, and writes an empty artifact for an empty entity set. Canonical entities remain deliberately shared.
4. **FI-4 repeat registry ingest:** add-registry now shows an executable stable-ID `ON CONFLICT ... DO UPDATE ... RETURNING id` scaffold. Tests use the actual unified schema in memory and confirm repeat ingestion preserves entity ID, officers, source URL and FK integrity while another jurisdiction retains separate identity.
5. **FI-5 fiscal-year scope:** audit-contracts labels the existing recipient agency data as **all available periods**, requires verified date-filtered evidence for an annual alternative, and separates partial from complete fiscal years. A mocked actual USASpending command verifies its default payload contains recipient/award-type filters only and the skill uses that scope.

## Modernization delivered

- Financial scores, growth thresholds, cohort sizes and top-N selections are explained starting defaults rather than automatic findings/lead quotas.
- Peer comparisons explicitly inspect `latest_periods`, statement units/currencies, missing values, complete periods and the reported small-cohort score method.
- Screen/peer statement examples now use the evidence agent's settled `sections <CIK> --accession <SELECTED_ACCESSION>` CLI for all three statements and verify returned accession, form, periods and statement_type before ratios. Full-text fallback is explicitly distinguished from financial statements.
- Grant tracing describes odd/even alternating traversal, per-node caps, requested versus effective depth, missing-EIN exclusions, reverse-flow expansion and per-row amount thresholds. Hydration repeats the same threshold and reconciles source counts/sums before promotion.
- All seven skills support native chat supervision, inherited model choice, evidence-driven reading depth and resumable long work. No headless job or new agent was launched.
- Source onboarding now shares a paired `build-infra/references/source-integration.md` contract for observed endpoints, source grain, truthful output/failure states, pinned context, repeat ingestion, fixture tests, provenance, dependencies and canonical discoverability.
- Removed the stale registry country priority table, copied schema/CLI menus, generic pip installation, unconditional core-target searches, and the requirement to copy every new source into every skill.
- Updated meaningful trigger descriptions and concrete Codex starter prompts. Corrected native Claude `user-invocable` metadata in the seven owned files.
- Preserved exact quoted evidence, source independence, confidence caps, identity/tenure checks, falsification and innocent explanations, public-source rules, and useful paid/account/human access routes.

## Changed paths (25)

For each of `screen-targets`, `compare-peers`, `trace-grants`, `audit-contracts`, `build-infra`, `add-registry`, `ingest-source`:

- `.claude/skills/<name>/SKILL.md`
- `.codex/skills/<name>/SKILL.md`
- `.codex/skills/<name>/agents/openai.yaml`

Additional paths:

- `.claude/skills/build-infra/references/source-integration.md`
- `.codex/skills/build-infra/references/source-integration.md`
- `tools/query_990.py`
- `tests/test_financial_source_skill_contracts.py`

## Validation

Environment for commands:
`UV_PROJECT_ENVIRONMENT=/Users/travcole/projects/osint-research/.venv UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache`.

- `uv run python -m pytest tests/test_financial_source_skill_contracts.py tests/test_query_990_lookup_flow.py tests/test_query_990_lookup_failures.py tests/test_query_990_shared_officers.py --offline -q`: **22 passed** (16 new skill/context checks plus 6 existing 990 checks).
- After refining the selected path check from exists() to is_file(), reran the three 990 context regressions: **3 passed**.
- `uv run ruff check tools/query_990.py tests/test_financial_source_skill_contracts.py`: **passed**.
- Owned-path `git diff --check`: **passed**.
- Selected skill snapshot + repository command validator: **7 skills / 14 variants; 0 errors, 0 warnings, 0 info**. All pairs are equivalent after native runtime normalization.
- Snapshot artifact: /tmp/osint-q8INnbtl/financial-implemented-snapshot.json

The initial selected snapshot correctly rejected the seven inherited `user_invocable` spellings after unit B's validator change; corrected these owned files and reran successfully. No weakening or bypass of validation was used.

## Scope and limitations

The source-onboarding contract now explains what command/output contracts should provide; it does not retrofit every existing data-source wrapper in this repository. Grant-flow traversal itself is unchanged and still does not emit a complete machine-readable frontier/truncation certificate, so skills must report bounded observed scope rather than claim exhaustion. No empirical claim about cross-provider token/latency/quality gains was made; parent-owned independent forward tests and integration checks remain the final review.

Root/shared documentation was not edited. All other agents' changes were preserved. Parent owns commits and integration.
