# Unit A: scoped lead review operations

Implemented in `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905` on the shared `codex/skill-modernization-20260905` worktree. No commits, production database writes, headless jobs, or new subagents were created.

## Behavior delivered

- `lead_tracker.py triage-export --limit N --profile NAME --output FILE` creates a read-only packet bound to the resolved database and profile. Lead snapshots include the full row, all notes, evidence references, and a revision. Optional repeatable `--reference-lead-id ID` includes an external duplicate keeper's reviewed snapshot.
- `triage-apply --batch-file FILE --decisions-file FILE [--dry-run] --output FILE` validates the entire packet and all decisions before applying them atomically. It rejects wrong database/profile, missing/foreign IDs, incomplete or duplicate membership, invalid action/fields, stale rows/notes/evidence, altered packet bodies, missing/stale external keeper snapshots, dead-ended keepers, foreign threads, and invalid relations. It records triage fields and audit notes; rationale is JSON data, so currency and shell-sensitive characters are preserved.
- `lead_dedup.py` consistently resolves `ITHILDIN_DB_PATH` and pinned/default profile for fill, scan, export, apply, stats, show, and verification. Read-only operations and dry runs do not initialize/migrate a database. Target previews expose the proposed names; fills affect only missing targets in the selected profile.
- Dedup export packets bind context and full snapshots. Apply now requires the original `--batch-file`; every decision must match one exported group with valid keeper/member IDs. Full validation precedes mutation, stale work is rejected, and identical already-applied decisions are idempotent. Conflicting prior decisions fail visibly.
- Consolidation copies full descriptions, all source notes with provenance, and evidence references onto the keeper; source rows remain linked and recoverable.
- `triage_policy.py` returns scoped overlap candidates and suggestions. Same-target/depth or ten existing findings never automatically dead-end another question. Unknown categories use a general research route rather than accidentally inheriting the first person-specific dictionary entry. Entity-role counts remain deliberately global and are labeled as shared records.
- Both runtime variants of triage/dedup now use native chat supervision, configurable batches/workers, inherited models, explicit packet handoffs, and user-intent-based continuation. Arbitrary finding-count/depth bans and expected merge percentages were removed. Dedup waves reset offsets after applying the preceding wave.

## Files changed

- `tools/lead_tracker.py`: review helpers and triage export/apply APIs/CLI.
- `tools/lead_dedup.py`: scoped operations, bound export/apply packets, complete consolidation, structured CLI output.
- `tools/triage_policy.py`: scoped assessment, candidate overlap semantics, explicit profile metadata loading, corrected generic routing.
- `.claude/skills/triage-leads/SKILL.md` and `.codex/skills/triage-leads/SKILL.md`.
- `.claude/skills/dedup-leads/SKILL.md` and `.codex/skills/dedup-leads/SKILL.md`.
- Added `tests/test_lead_review_workflows.py` with actual SQLite/CLI fixture regressions.
- Removed `tests/test_triage_leads_skill.py`, which only asserted exact command strings and missed the unsafe write path.
- Updated only the triage policy subsection of `tests/test_enforcement.py` for explicit profile scope and reviewed overlap instead of automatic closure.
- Updated only the profile metadata loader test in `tests/test_profile_analysis_papercuts.py`, including an assertion that the requested profile is actually loaded.

The Codex skill bodies are now 87 lines for triage and 103 for dedup. Parent-owned runtime metadata normalization may change those counts.

## Verification

Environment used for every run:

```bash
UV_PROJECT_ENVIRONMENT=/Users/travcole/projects/osint-research/.venv
UV_NO_SYNC=1
UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache
```

Final test command, run with that environment from the owned worktree:

```bash
uv run python -m pytest \
  tests/test_lead_review_workflows.py \
  tests/test_enforcement.py \
  tests/test_profile_analysis_papercuts.py \
  tests/test_lead_tracker_related_validation.py \
  tests/test_lead_tracker_schema_cache.py \
  tests/test_lead_tracker_fk_migration.py \
  --offline -q
```

Result: **101 passed in 6.25 seconds**.

```bash
uv run ruff check tools/lead_tracker.py tools/lead_dedup.py tools/triage_policy.py \
  tests/test_lead_review_workflows.py tests/test_enforcement.py \
  tests/test_profile_analysis_papercuts.py
git diff --check
```

Both passed.

Regressions cover two databases with colliding numeric IDs, two profiles, actual CLI environment resolution, foreign keeper/related/thread IDs, incomplete packets, atomic rollback, stale statuses, unchanged-timestamp title edits, new notes/evidence, dry-run immutability, malformed memberships, complete consolidation, idempotency, and 90 groups processed through two shrinking-queue waves. Distinct same-target legal/ownership questions survive triage even with ten existing findings and higher-depth overlaps.

An independent review by the existing evidence unit found two additional fixture cases: tampered packet descriptions carrying an unchanged revision, and external keeper questions changing after export. Both were fixed and now have behavioral regressions; the reviewer confirmed the fixes as designed.

## Integration notes / limits

- Dedup `apply` intentionally requires `--batch-file`; existing unbound decision files must be re-exported/reviewed. Scan/export outputs are structured objects with scope and groups, not the old bare group array. No repository Python consumers of the removed `cmd_*` wrappers were found.
- The parent owns `docs/TOOL_REFERENCE.md` and other shared docs. Relevant new commands/flags above should be reflected there if the global reference lists dedup/triage examples.
- Legacy dedup log rows are not rewritten. Scoped history can attribute them when their recorded lead IDs establish the profile; older empty-ID history cannot be safely assigned to a profile. New records store the profile and exact decision JSON.
- Verification uses disposable fixtures and offline CLI runs. Production migrations, real investigation edits, and headless workers were deliberately not exercised. The structural name-grouping algorithm remains the existing candidate generator; models still must resolve identity and question equivalence before applying decisions.
- Dry-run dedup reports proposed target fills separately; unknown/missing-target rows remain outside candidate grouping until targets are established. The skills require reporting these gaps rather than claiming the queue is fully reviewed.
- No cross-model cost/quality benchmark was attempted. These changes establish correctness and workflow behavior, not a measured model-generation efficiency claim.

All task-owned changes are uncommitted for the parent to review and commit explicitly.
