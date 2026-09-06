# Independent final review: unit B

Reviewer scope: scripts/cli_contract.py, scripts/validate_skills.py delta, scripts/skill_distribution.py, tools/tool_catalog.py, and their fixture tests. Worktree: `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`.

No repository edits, production databases, network/source probes, actual application imports, or model invocations. Temporary reproductions only. Core B was confirmed stable by its owner before inspection. Owner subsequently resumed fixes for findings below.

## Findings reproduced

1. **P2 — Non-destructive skill inventory can overwrite personal skill content.** `skill_distribution.main` writes the requested --output path without checking whether it belongs to the personal skills being inventoried/backed up. In a temporary fixture, `inventory --personal-root PERSONAL --output PERSONAL/example/SKILL.md` replaces the user's edited skill with report JSON. This contradicts the command's preservation contract. Protect personal-root outputs, symlink/hardlink aliases, and backup contents from report writes, before backup side effects.
2. **P2 — Unsupported parser control flow is silently called complete.** `Inspector.statements` has no fallback for try/with/other unsupported statement kinds containing declarations. A parser with `try: p.add_argument('--needed')` returns a contract containing only --help with no limitations; tool_catalog labels it declarative_argparse. Unsupported parser-bearing flow must cause a partial/unavailable result, not a successful omitted interface. Also avoid scanning arbitrarily nested parse_args calls as though they were a direct parse boundary.
3. **P2 — Linter invents CLI options/subcommands from help prose.** `read_help_options` reconstructs option names and subcommand sets by regex over format_help, although real action objects are available. A positional `format` with choices json/csv becomes fake subcommands; --child-only mentioned in a help description becomes an accepted global option. Derive option strings, arity, and actual subparser choices from argparse actions.

Reproduction script: `/tmp/osint-q8INnbtl/review_b_probe.py`. It creates only temporary files. Output before fixes:

```text
try_contract: inspection=declarative_argparse; global_arguments=[--help]; limitations=[]
choice_help: options={--help,--real,--child-only}; subcommands={json,csv}; error=None
personal_overwritten: True
```

All three were sent promptly to parent and review_architecture. Owner accepted and corrected the findings with regression tests. They are resolved in the reviewed implementation.

## Positive findings and limits

- No path to application execution was identified in the AST interpreter. It reads application/imported-constant source as text, builds only standard argparse objects, refuses custom callbacks, and never invokes runtime argument parsing. Tool_catalog imports the owned interpreter, not query tools.
- Actual tracked discovery link is `.agents/skills -> ../.codex/skills` and resolves to the canonical repository skills.
- Backup uses exclusive new destination creation, copies symlinks as symlinks, verifies original/copy manifests, and does not remove originals. The report-output hole above is the material exception requiring correction.
- Catalog argument rendering uses action metadata and separates root global arguments from child command arguments; the misattribution finding is in linter help extraction.
- Static contracts cannot establish runtime dependency health or custom validation semantics; the tool clearly documents that limitation. The unsupported-flow hole above needs correction to make incomplete-contract labeling reliable.

## Follow-up validation

Owner's fixes were read and the original independent fixture rerun. Results after correction:

```text
try_contract: inspection=partial; limitations=[line 4: unsupported declaration statement Try]
choice_help: options={--real,--help}; subcommands=set(); error=None
inventory_exit_code: 2
personal_overwritten: False
```

The distribution preflight now rejects output within personal/managed roots and the backup destination, and creates output exclusively so existing file/symlink/hardlink aliases cannot be overwritten. Rejection occurs before backup creation. The interpreter marks unsupported parser-containing statements partial and limits parse-boundary recognition to expression/assignment/return statements. Linter option metadata comes directly from argparse actions.

Independently ran `uv run python -m pytest tests/test_validate_skills.py tests/test_skill_architecture.py tests/test_tool_catalog.py tests/test_analysis_skill_commands.py --offline -q`: **54 passed**. This includes fixture checks for import/type callback nonexecution, control-flow limitations, positional-choice/prose-flag separation, original personal file preservation, symlink/hardlink output protection, and rejecting destructive report paths before backups.

**Final assessment: no outstanding material finding in the reviewed B scope after these corrections.** This is source/fixture review, not proof of arbitrary-Python interpretation completeness or runtime CLI availability. Intentional partial-contract warnings remain necessary.
