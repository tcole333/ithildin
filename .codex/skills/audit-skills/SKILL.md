---
name: audit-skills
description: Audit one, several, changed, or all project skills for structural validity, trigger quality, command correctness, workflow gaps, safety boundaries, cross-skill overlap, Claude/Codex drift, and maintainability. Use when asked to review, lint, assess, compare, improve, repair, or propose fixes for SKILL.md packages or the project skill system. Default to a read-only prioritized audit; apply edits only when the user explicitly requests fixes.
---

# $audit-skills

Audit project skills with deterministic checks and evidence-backed semantic review. Separate verified defects from optional improvements and never edit audited skills during the default review mode.

Read [references/review-rubric.md](references/review-rubric.md) before judging workflow quality or assigning severity.

## Arguments and modes

- No arguments: audit every project-local skill in `.claude/skills` and `.codex/skills`.
- One or more names or paths: audit only those skills and their paired runtime variants.
- `--changed`: audit skill packages changed or untracked in Git.
- `--fix`: apply verified, in-scope fixes after auditing. Treat a later user approval of named findings as equivalent authorization.
- `--report PATH`: persist the final Markdown report. Otherwise return it in the response and keep intermediate files in the session workdir.

Combine selectors when useful, such as `$audit-skills --changed` or `$audit-skills review-article --fix`.

## Non-negotiable boundaries

- Treat audit mode as read-only. Do not modify skills, sync mirrors, update databases, or create durable reports unless requested.
- Preserve unrelated worktree changes. Inspect the current diff before suggesting or applying a change to a dirty skill.
- Do not report a suspected command or flag defect until checking the implementation or `--help` output.
- Do not treat a linter warning, Claude/Codex textual difference, short description, or stylistic preference as a defect without explaining its concrete effect.
- Do not weaken evidence, safety, authorization, or validation requirements to make a skill shorter or simpler.
- Keep facts, risks, and recommendations distinct. Label checks that could not be run.
- Use `uv run python` for all Python commands.
- Use an isolated workdir and `--output` for generated machine-readable data.

## 1. Establish scope

Create an isolated workdir and inspect the worktree:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
git status --short
```

Resolve requested names against both skill roots. Include a paired variant automatically when the same skill exists in both trees. In `--changed` mode, include the whole package when any file inside it changed.

Record:

- requested and resolved scope;
- excluded roots or variants;
- dirty files that overlap the audit;
- whether the run is audit or fix mode.

If no requested skill resolves, stop with the searched roots and closest matching names.

## 2. Run deterministic checks

Build a compact structural snapshot and delegate frontmatter, command-path, flag, and Python-invocation checks to the repository validator for only the resolved variants. Add `--changed` or repeat `--skill NAME` to match the requested scope.

```bash
uv run python .codex/skills/audit-skills/scripts/snapshot_skills.py \
  --workspace . \
  --run-repo-validator \
  --output "$WORKDIR/skill-snapshot.json"
```

The helper imports `scripts/validate_skills.py`; it does not duplicate the repository's CLI checks. A nonzero status is audit evidence, not a reason to stop reviewing. If the snapshot reports that the repository validator could not load, run the validator directly and disclose that its output covers the full roots:

```bash
uv run python scripts/validate_skills.py \
  --workspace . \
  --skills-dir .claude/skills \
  --skills-dir .codex/skills \
  --require-uv
```

Read the snapshot summary and issues first. Open full skill text only for the selected packages or to verify a reported cross-skill interaction. Do not paste every SKILL.md into context.

The snapshot checks directory/frontmatter agreement, unresolved local links, bundled-resource reachability, TODOs, length, runtime heading conventions, Codex UI metadata, paired-tree presence, and normalized Claude/Codex drift. Treat its severities as triage hints, not final judgment.

When normalized drift is reported and mirror intent is unclear, inspect the actual diff. Use the repository parity helper only as corroboration because it compares raw text and may include intentional runtime syntax differences:

```bash
uv run python scripts/audit_codex_skill_parity.py --show-diffs
```

## 3. Perform semantic review

Apply every applicable dimension in the rubric. For each candidate issue:

1. Cite an exact file and tight line number.
2. State the observable failure or realistic failure path.
3. Verify referenced commands, schemas, files, and policies from primary repository sources.
4. Check whether another skill, AGENTS.md, or a referenced file already supplies the missing instruction.
5. State the smallest useful correction and how to verify it.
6. Downgrade or discard the issue when the evidence does not support the claimed impact.

Look across skills as a system, not only as isolated documents:

- descriptions that collide or fail to trigger for natural user requests;
- contradictory ownership, mutation, approval, evidence, or profile rules;
- handoffs that name a missing or incompatible skill;
- duplicated long instructions that will drift;
- Claude/Codex variants whose differences exceed runtime syntax adaptation;
- orchestration skills whose subagent contracts permit gaps, duplicate work, lost artifacts, or concurrent edits.

Do not inflate the report with generic writing advice. Prefer a few verified, high-leverage findings.

## 4. Scale full audits with subagents

When more than eight skills are in scope and collaboration tools are available, use read-only subagents for independent semantic review. Keep deterministic checks and final adjudication in the parent.

1. Partition skills into non-overlapping batches of roughly 6–10 packages.
2. Give each reviewer the rubric, exact paths, snapshot path, dirty-file list, and a unique `$WORKDIR/report-skills-N.md` destination.
3. Tell reviewers not to edit files or databases and to return only line-cited, verified findings plus dismissed false positives.
4. Reserve one pass for cross-skill triggers, ownership, handoffs, and normalized mirror drift.
5. Re-open the cited source lines and independently verify every P0–P2 finding before including it.

For one to eight skills, review locally unless independent testing would materially reduce uncertainty.

## 5. Report the audit

Return a self-contained report with:

```markdown
# Skill audit

## Scope and checks
- Skills and variants reviewed: ...
- Deterministic checks: pass/fail/not run
- Limitations: ...

## Findings
### [P1] Short outcome-focused title
- ID: skill-name:category:slug
- Evidence: path:line and observed behavior
- Impact: concrete failure mode
- Recommendation: exact smallest change
- Verification: command or forward test

## Cross-skill observations
- Trigger collisions, ownership gaps, drift, or duplicated policy

## Suggested sequence
1. Blocking correctness and safety
2. Workflow and trigger reliability
3. Maintainability and context efficiency

## No-action notes
- Important warnings or suspected issues checked and dismissed
```

Order findings by severity, then confidence and breadth of impact. Use stable IDs so the user can approve specific fixes. If no actionable defect survives verification, say so plainly and list the checks performed.

## 6. Apply authorized fixes

Enter fix mode only through explicit `--fix` intent or approval of named findings.

For each authorized finding:

1. Re-read the target file and its current diff.
2. Reproduce the defect or establish the deterministic cause.
3. Apply the smallest root-cause patch with `apply_patch`.
4. Update both runtime variants only when they are intended mirrors; preserve deliberate runtime-specific syntax and metadata.
5. Regenerate `agents/openai.yaml` when SKILL.md changes make its interface metadata stale.
6. Run the narrow validation or forward test, then the repository skill validator.
7. Review the final diff for unrelated edits and weakened constraints.

Do not bulk-normalize prose, overwrite user changes, or fix unapproved adjacent findings. If a proposed correction expands into a broader redesign, stop and return the revised scope for approval.

## 7. Forward-test behavioral changes

Forward-test changes to triggers, orchestration, authorization, evidence handling, or complex workflows when subagents are available and the test is safe.

- Give the tester the revised skill and a realistic user request, not the diagnosis or expected answer.
- Use raw repository artifacts and a fresh workdir.
- Prevent production mutations; select dry-run or read-only scenarios.
- Check whether the skill chooses the right scope, commands, stop conditions, output, and handoffs.
- Clean up temporary artifacts and report what the test actually established.

Do not claim a semantic fix is verified solely because frontmatter validation passes.
