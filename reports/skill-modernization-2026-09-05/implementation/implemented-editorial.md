# Unit D — Editorial verification implementation

Implemented in `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`; no commits. No production DB operations, live model calls, headless jobs or new subagents were used. The unattended wrapper was tested only in dry-run with a stub model command that must not be called.

## Result

- **E1 current target coverage:** `report-support-coverage.mjs` accepts repeated `--file` targets, handles new/modified/unchanged content independently of Git, verifies the target exists and was actually processed, hashes current raw bytes, and resolves its code root from the script location. It honors `ITHILDIN_CONTENT_DIR` consistently with the finding catalog, including invocation from an unrelated cwd. Skills use `npm --silent` so redirected artifacts are actual JSON. Existing changed-content behavior remains available.
- **E2 scoped evidence audit:** `scripts/evidence_audit.py` now opens the selected DB in SQLite read-only mode and reads findings/evidence in one transaction. It honors pinned profile/database, or explicit `--profile`/`--db`; global scope requires `--all-profiles`. `--article` selects cited IDs/exact references and records the current content hash; `--finding-id` is repeatable. Missing/out-of-profile IDs and unresolved citation variants are explicit. Text checks compare the full normalized quote, using explicitly supplied local EFTA corpus or a generic ref-to-text-artifact manifest. Missing sources/OCR/quotes become unknown. Shared documents create overlap candidates, not an invented duplicate gate. Complete JSON preserves status and limitations. Output may not overwrite source/database/article inputs. Existing subcommand names remain, now using the scoped report engine.
- **E3 batch handoffs:** dossier `batch --packet-dir DIR` writes actual `automated-<slug>.json` packets with the checked hash. Batch inventories actual curated files, including newly written unindexed dossiers; the index supplies optional ranking only. Automated packet generation rejects concurrent content changes rather than attaching a later hash to earlier checks.
- **E4 truthful status:** paired status skills consume the new read-only `tools/investigation_status.py` from the parent/status owner, distinguish unavailable metrics and unverified profile membership from zeros, use `pending_triage`, label bounded priority/latest samples honestly and separate global source health from profile activity.
- **E5 selected discovery DB:** snapshot exporter defaults to `ITHILDIN_DB_PATH`, normalizes the selected path, reads one SQLite transaction and refuses output over the DB. Skill no longer passes an overriding root `investigation.db` and tells the parent to verify context equality across exports/run metadata.

## Skill changes

Rewrote paired writer/article-review/dossier-review skills around inputs, evidence responsibilities, real tooling, output contracts and completion. Removed mandatory cast/source-count/evidence-count/word-count/surprise-hook/style-pattern rituals while retaining explanatory craft as guidance. Preserved claim types, confidence ceilings, full-source context where necessary, allegations, causal/intent distinctions, competing explanations, provenance/deception review and sentence-local citation requirements.

Dossier deterministic corrections happen before the semantic review of final bytes; valid unchanged evidence work/receipts can be reused. The exact raw-dossier hash requirement and independent release/static blockers remain. Review-only requests stay review-only, and already-authorized changes may proceed. Newer language explicitly uses chat-native bounded delegation with inherited models, engaged parent ownership and resumable artifact/progress notes. Curator changes are narrower: current-target coverage, useful rather than numeric link/question counts, legitimate cautious language, selective context expansion, context pinning and dry-run scaffolding in temporary copies.

`discover-investigations` retains its documentary/commissioning gates, independent review and honest coverage boundaries. Packet sizing can follow the question rather than a hard character limit, sparse runs need not invent candidate counts, and existing promotion authorization carries forward without a redundant confirmation.

## Explicit unattended compatibility wrapper

`scripts/batch_review_dossiers.sh` now requires `--unattended` (or `--dry-run`), a selected slug file, and pinned profile/absolute DB. Each unique slug gets a unique workdir/log/prompt. Workers follow the current `/review-dossiers --fix` skill and return actual final-content review JSON; the shell coordinator serially ingests supplied reviews, writes receipts and validates them. Missing/failed/stale/non-PASS reviews require attention. It does not infer success merely from a changed Git file. Existing Claude allowed-tools flags remain unchanged; no model name is pinned. Interactive skills do not route here by default.

## Owned files

- `scripts/evidence_audit.py`
- `scripts/review_dossier_checks.py`
- `scripts/batch_review_dossiers.sh`
- `.codex/skills/discover-investigations/scripts/export_snapshot.py`
- `.codex/skills/discover-investigations/SKILL.md`
- Paired `.claude/skills/` and `.codex/skills/` `SKILL.md` for: `write-article`, `review-article`, `curate-dossier`, `review-dossiers`, `status-report`
- `web/scripts/report-support-coverage.mjs`
- `web/scripts/support-coverage-scope.mjs` (new)
- `web/scripts/test-support-coverage-targets.mjs` (new)
- `web/package.json` (wires the focused target test into `test:changed-content`)
- `tests/test_editorial_verification_scope.py` (new)

Other owners changed `agents/openai.yaml` metadata and implemented the status tool; those are not this unit's edits. An ignored `web/node_modules` symlink points to `/Users/travcole/projects/osint-research/web/node_modules` solely to use existing local dependencies for fixture validation.

## Validation

Commands used the specified `UV_PROJECT_ENVIRONMENT`, `UV_NO_SYNC=1` and workdir-specific UV cache:

- `uv run python -m pytest tests/test_editorial_verification_scope.py tests/test_dossier_review_receipts.py tests/test_review_dossier_checks.py -q` — **43 passed**.
- `npm --silent --prefix web run test:changed-content` — existing changed-content tests plus pure selector and full coverage CLI fixtures passed.
- `uv run ruff check scripts/evidence_audit.py scripts/review_dossier_checks.py .codex/skills/discover-investigations/scripts/export_snapshot.py tests/test_editorial_verification_scope.py` — passed.
- `bash -n scripts/batch_review_dossiers.sh` — passed.
- `git diff --check` — passed.

Fixtures cover two profiles, selected alternate DB, full-quote mismatch (old prefix-only match would have passed), unavailable corpus without DB creation, non-EFTA text artifacts, out-of-profile IDs, unmapped numeric/mixed-case/hyphenated citation variants, harmless shared-source overlap, DB byte preservation/output protection, unindexed dossier batch packets, concurrent-change rejection, and unique wrapper dry-runs with no model invocation. Existing tests preserve actual semantic-review requirements and stale-content receipt rejection.

The independent reviewer additionally forward-tested the full coverage CLI on new/modified/unchanged fixture articles from an unrelated cwd and confirmed current hashes and missing-target failure. Their findings drove the conservative citation extractor, actual-file batch inventory, npm `--silent`, and precise hash-schema wording corrections. Parent review also prompted explicit protection for SQLite `-wal`/`-shm`/`-journal` and existing hardlink aliases of protected DB/article/source inputs, with focused no-overwrite fixtures; the snapshot exporter applies equivalent database/sidecar protection.

## Limits

- Evidence text matching is a diagnostic, not semantic verification or a publication receipt. Quote authenticity, primary-source truth, independence, OCR ambiguities and actual claim support still need reviewer judgment. Unknown checks remain explicit.
- Citation joins are deliberately exact. Aliases and ordinary non-link bracket text may appear as unmapped instead of silently being ignored; a reviewer must resolve/assess them. Sources without local text remain unknown until obtained and reviewed.
- Runtime source checks use supplied local artifacts only; no live evidence endpoint or model comparison was run. Efficiency gains from shorter skills are not asserted without repeated model evaluations.
- The compatibility wrapper's actual headless execution was not run; fixture validation covers only syntax, explicit dispatch boundary, prompt/output contract and dry-run isolation. Parent integration should retain existing headless safety flags and repository release gates.
- Publication/build on real content was not run, because this implementation validation uses fixtures and leaves production investigation state alone.
