# Git workflow and repository ownership

Use this policy when starting work, sharing a checkout, staging/committing changes, reorganizing files, or integrating a completed branch.

## Start from an owned branch

1. Inspect `git status --short`, the current branch, and any existing task instructions. Identify pre-existing edits before changing files.
2. Use `codex/<workstream>` for a new agent branch, unless the user requested a different name. Keep one independently reviewable objective per branch. Work directly on a shared checkout only when its file ownership is coordinated; concurrent unrelated tasks use separate Git worktrees.
3. Start new worktrees from the intended base branch. Explicitly select whether existing uncommitted work is part of the task; a worktree from HEAD does not include it.
4. Record a short task plan for substantial work, including owned paths, validation commands, and unresolved dependencies. Parallel agents share file ownership and leave commits to the task owner.

Example for a clean checkout:

```bash
git switch -c codex/evidence-corrections
```

For independent parallel work, create an ignored local worktree after checking the base ref:

```bash
git worktree add .claude/worktrees/evidence-corrections -b codex/evidence-corrections main
```

Treat `main` as an integration branch. Complete validation and review on the workstream branch. A push, merge, publication, history rewrite, or deletion of another task's work requires authorization for that action; a local commit within an authorized implementation task does not require a repeated permission question. Follow the user's explicit instructions when they differ from the defaults here.

## Commit completed units while working

Commit after a coherent behavior change is implemented, its relevant tests/checks pass, and its staged diff has been reviewed. Do not wait until several unrelated workstreams have accumulated. A large task can have several focused commits: schema fix, consumer integration, tests, and documentation may be one commit when they are necessary together.

Stage explicit paths or reviewed hunks. In a shared/dirty checkout, avoid `git add .`, `git add -A`, and `git commit -a`: they can absorb another task's research or unfinished code. Before every commit inspect both the index and remaining working-tree changes:

```bash
git diff --check
git diff --cached --stat
git diff --cached
uv run python scripts/repository_hygiene.py check --staged
git status --short
```

Use `type(scope): concrete result` for the subject, at most 100 characters. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, `ci`, `data`, `research`. Describe the observable outcome. The body records relevant validation and any material limitation. Examples:

```text
fix(evidence): invalidate verification after claim edits
refactor(records): call county adapters through their Python API
research(epstein): preserve court record provenance
```

Do not label an untested snapshot as a finished fix. When preserving inherited accumulated work, first create a local archive and manifest, inspect paths for credentials/raw data, and make explicitly labeled recovery commits if useful. Document the source state and known validation gaps. Keep those checkpoints distinct from verified implementation commits; this is a recovery operation, not the normal cadence.

Before finishing an implementation task, account for every task-owned change: committed, deliberately local/ignored with its retention path documented, or explicitly unfinished. A clean `git status` produced by hiding unfinished source files is not completion. Do not silently leave all completed work uncommitted.

## Keep source, publication, research, and acquisition artifacts distinct

| Material | Location / treatment |
|---|---|
| Platform code, tests, fixture generators | `tools/`, `scripts/`, `pipeline/`, `queue_system/`, `tests/`; commit with relevant tests |
| Reviewed static publication content | `content/`, deliberate `web/public/` artifacts; use the publication validation path |
| Investigation configuration and authored research | `investigations/<profile>/`, `research/`, `reports/`; commit narrative, reproducible scripts, and manifests |
| Primary document downloads, bulk responses, media, OCR/render intermediates | Local `datasets/` or a documented ignored acquisition directory; preserve source URL/ID, retrieval time when known, relative path, size, and checksum in a tracked manifest |
| Runtime databases, backups, credentials, caches | Local and ignored; database schema/migrations and small deliberate fixtures are tracked |
| Temporary scripts/results | Unique `/tmp/osint-*` workdir; promote reusable code or final reports into their owning directories |
| UI/design reference images | Deliberate `design/assets/` or `design/archive/`; keep repository root free of session screenshots |

An evidence file being ignored is not permission to delete it. Retain it at the manifest location or update references and the manifest when moving it. Preserve raw evidence while investigating source/identity corruption; repairs must keep provenance. Disposable output can be removed only after confirming it is regenerable and not the sole copy of evidence.

The index check rejects credentials, local data/cache/build paths, root-level media dumps, runtime databases, and blobs over 5 MiB. A required large public artifact may have an exact SHA-256 exception with a reason in `config/repository_policy.json`; changes to its contents require a new reviewed exception. Small SQLite test fixtures are allowed under `tests/fixtures/`. Secret detection reports the file and rule, never the credential value. The pattern check is a focused safeguard, not proof that a file contains no sensitive data; inspect staged research content deliberately.

## Install and use the checks

The repository supplies `.githooks/pre-commit` and `.githooks/commit-msg`. Before enabling them, inspect any existing `core.hooksPath`; preserve an existing hook setup by integrating the checks instead of silently replacing it.

```bash
git config --get core.hooksPath
git config --local core.hooksPath .githooks
```

The hook reads the **index**, not unstaged file contents. Run the relevant Python/JS tests separately; the hook intentionally does not launch a large test suite for every commit. CI checks the actual changed commit blobs independently of local hooks. A failed guard should be fixed at the source; use an explicit narrow reviewed artifact exception when appropriate rather than disabling the guard for a whole category.

## Integrate and retire workstreams

Review the final branch diff and run the required component/integration checks. Keep publication review separate from code correctness: a code change can pass while production publication correctly waits for a content-bound semantic review. Use the shared release command for both local and CI publication.

When authorized, integrate a focused branch through a reviewed PR, normally squash-merging a single-purpose change. Keep logical commits when their separate history helps review. Never force-push a shared branch or rewrite another task's commits as routine cleanup. Delete a worktree or branch only after its work is integrated or otherwise preserved and the task owner has authorized removal.
