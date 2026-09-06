# Strict agent-docs CI follow-up

Files ready for the task owner to commit in `/tmp/osint-SUw5NK21/merge-worktree`, branch `codex/editorial-audit-20260905`:

- `scripts/validate_skills.py`
- `tests/test_validate_skills_commands.py` (new)
- `docs/TOOL_REFERENCE.md`

The full exact CI validator initially completed with **0 errors / 3 warnings** across 291 Markdown files and exit 1. Two warnings were false positives for flags on Lincoln PropertyWeb's `document appraisal-card` nested command; the third identified a stale Florida ingestion example.

The validator now follows only the selected child commands explicitly advertised by parent help, caching each complete command path separately. Sibling-only flags and misspellings remain warnings. Florida's example now uses `--archive FILE --type nal`, matching the real parser. The valid Lincoln command remains unchanged. The patch also removes one pre-existing unused import so changed-file Ruff passes.

Verification:

- `uv run pytest tests/test_validate_skills.py tests/test_validate_skills_commands.py --offline -q -p no:cacheprovider --basetemp /tmp/osint-SUw5NK21/pytest-docs-ci-fix-rerun` — **22 passed**.
- `uv run ruff check scripts/validate_skills.py tests/test_validate_skills_commands.py` — passed.
- Changed-path `git diff --check` — passed.
- Extracted the two actual affected commands from the current tool reference into `/tmp/osint-SUw5NK21/doc-lint-targets/docs/current-examples.md`; invoked `validate_skills.py` with the integration checkout as workspace, that docs directory, an empty skill directory, and `--strict` — **No issues found**, exit 0. Log: `/tmp/osint-SUw5NK21/pr12-docs-lint-targeted.log`.
- The test also parses the actual Florida example with its real argument parser; it does not run ingestion.

The focused tests cover nested leaf flags, repeated-help cache reuse, deeper command hierarchies, rejection of sibling flags and misspellings, and both real documented examples. No validation gate was weakened. No full long-running docs rerun is claimed.

Canonical papercuts **#2786** and **#2787** were logged and resolved with this evidence. **#2788 remains open**: the older shell-segment splitter mishandles quoted semicolons and may skip the affected command. The root task explicitly kept that separate lexer issue out of this focused follow-up; no regression test claims it has been fixed.

No source acquisition, commit, push, or merge was performed by this subtask. The task owner controls integration.
