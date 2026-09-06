# Unit E — research skill modernization

Worktree: `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`.

Owned changes: paired `deep-investigate`, `pursue-lead`, `investigate-person`, `search-all-sources`, `trace-entity`, `investigate-infra`, and `landscape-scan` skill bodies; paired `deep-investigate/references/worker-contract.md`; paired `investigate-infra/references/passive-queries.md`; `tests/test_research_skill_commands.py`. No commits, production DB queries/writes, live source requests, headless jobs, new agents, or edits to shared contracts/metadata.

## Implemented behavior

- Deep-investigate now uses a compact source/worker plan and a single conditional worker/report contract, replacing four nearly identical inline templates. The parent selects independent tracks, inherits the configured model, continues useful research/reconciliation, steers active workers, checks native status/completion, and collects the actual expected reports. Codex names `spawn_agent`, `send_message`, `followup_task`, `list_agents`, and `wait_agent`; Claude names its native Agent tool and runtime messaging/status/completion capabilities.
- Every skill links the parent-owned research and execution contracts. Pinned context, accumulated source coverage, user steering, source artifacts, read coverage, next action, and worker identity survive interruptions/compaction. Nested skills inherit the current question/coverage instead of restarting a full checklist.
- Complete document artifacts and sufficient source reading replace quote-only bans. Full and long documents are supported; sequential chunks/sections record read coverage and continuation. A retrieved artifact or preview does not count as a completed source review.
- Fixed the truncated corpus example with `ingest_kabasshouse.py doc ... --output ...`, retaining all retrieved rows rather than the 2,000-character preview.
- Fixed preflight context by using `entity_tracker.py lookup` instead of inline SQLite opening `investigation.db`; entity detail uses the tracker too.
- Removed whole-database ACRIS expansion from single-target traces. The example is now a selected `party` query with evidence-selected further pivots.
- Replaced the obsolete California MCP prerequisite with its current self-contained Node/Chrome runtime check and bounded search.
- Source menus are adaptive and point to canonical module documentation; case-specific corpus hardcodes and stale global availability claims were removed. UK company/officer source expectations, ICIJ exact IDs/remote-first traversal, public-record capability planning, identity resolution, and explicit barrier states remain.
- Collection hypotheses and disconfirmation are supported without implying that interpretations can become unqualified facts. Assumption-heavy corporate/technical slogans became testable signals with ordinary alternatives. Source independence, confidence ceilings, quoted provenance, ambient facts, targeted lateral exploration, and meaningful completion criteria remain.
- Updated connection examples to supply their own exact quoted evidence, even when a finding ID is attached. Fixed relationship examples to current CLI choices (`employment`, not an unsupported `professional` type).
- Landscape breadth, source count, escalation count, and significance thresholds are explained defaults or evidence-sensitive decisions rather than hard quotas/tool-call limits.

SKILL.md bodies in one runtime fell from 3,124 to 997 lines. Added two conditional references in each runtime. This measures package simplification, not model-performance improvement.

## Verification

All commands ran with the parent-provided shared virtualenv, `UV_NO_SYNC=1`, the isolated UV cache, explicit owned-worktree cwd, and `/bin/bash` with `login:false`.

- `uv run python -m pytest -q tests/test_research_skill_commands.py`: **16 passed**.
- `uv run ruff check tests/test_research_skill_commands.py`: **passed**.
- `git diff --check` over all owned paths: **passed**.
- Scoped snapshot with `--run-repo-validator`: command/link checks passed. The initial result has seven errors solely for the legacy Claude `user_invocable` keys, which are reserved for the parent's global normalization, and one expected deep-investigate runtime-wording drift warning. Snapshot: `/tmp/osint-q8INnbtl/research-implementation-snapshot.json`.

The fixture tests execute the copyable corpus retrieval against text with decisive information after the normal preview; run the documented preflight lookup against a pinned database with a guarded SQLite open and conflicting alternate fixture; parse all ACRIS examples to require the selected target; and run every revised connection example through the actual tracker CLI parser with writes intercepted, validating a quote for every evidence ref. They touch neither production databases nor remote sources.

## Remaining integration work for parent

- Normalize seven Claude frontmatter keys with the other packages; no metadata changes were made locally in this unit.
- Ensure shared contracts keep the promised native supervision, selected context, long-document read coverage/continuation, evidence standards, and recovery semantics. The skill bodies link them and supply only task-specific steps.
- Independent forward tests should assess whether the skills choose useful source scopes, continue required long-source reading, reconcile failed/partial workers, and preserve the original objective after steering. Unit fixtures verify command/scope regressions, not semantic end-to-end model behavior or efficiency gains.
- Review and commit the 19 owned paths with the other coherent units. No further Unit E edits are pending.
