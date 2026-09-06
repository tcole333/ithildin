# B — validation, distribution, and offline CLI discovery

Worktree: `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`. No commits, skill-body changes, root/shared-doc changes, personal HOME mutations, production DB writes, source queries, headless jobs, or subagents.

## Implemented behavior

- Repository discovery is wired through the tracked relative symlink `.agents/skills -> ../.codex/skills`. Canonical skill bodies remain version controlled in `.codex/skills`.
- `scripts/sync_codex_skills.sh` is a compatibility entrypoint for a **read-only repository discovery check**, not a HOME copy operation. `inventory --personal-root PATH [--output FILE]` lists collisions and file hashes without reading unrelated bodies or changing anything. `backup --personal-root PATH --destination NEW_DIR` copies only collisions into an exclusive new backup, preserves symlinks, verifies original/copy hashes, and keeps originals/unrelated skills untouched. Different content is labeled `different_preserve`, because it could be a user edit. There is no remove/overwrite/install command.
- The linter's default scope is repository Claude and current Codex discovery roots, with legacy `.codex` fallback. Personal roots require explicit `--skills-dir`. Missing explicitly selected directories now become real warnings and fail strict mode. Linked Markdown references are checked alongside SKILL.md, so progressive disclosure does not hide command errors.
- Metadata validation is runtime-specific. Claude recognizes documented `user-invocable`, `disable-model-invocation`, `when_to_use`, `argument-hint`, `arguments`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, and `shell`, plus shared Agent Skills fields. It rejects the old `user_invocable` spelling. Codex/shared packaging does not silently accept Claude-only controls. Runtime detection uses the nearest actual `RUNTIME/skills` pair, which works inside `.claude/worktrees/.../.codex/skills`.
- Parity and snapshot now share runtime normalization. Invocation syntax, standard root document naming, and adapter metadata are separated from shared instructions. Shared bundled references/scripts/assets are compared too; a missing evidence sentence/resource still fails. Three deliberate Codex-only packages are explicit; ordinary metadata differences no longer create 32 spurious drift results. Runtime-specific body wording still appears for review instead of being suppressed by whole-skill exemptions.
- `tools/tool_catalog.py list --domain legal --query court --limit 3 --json` discovers compact, paginated entries from actual CLI source files, source_report's declared query-tool links, and existing module documentation. `describe query_courtlistener search --json` gives current static argument declarations, source labels, documentation sections, and the explicit help command. Discovery does not probe health or read credentials/data stores. Runtime health remains a separate explicit `source_report.py check` operation.

## CLI introspection safety and exact validation boundary

Final implementation does **not run tool subprocesses, runtime --help, or application imports**. Initial development checked only `--help` under a temporary tracker DB; final code review correctly identified that import-time side effects make that insufficient. That approach was replaced before handoff.

`scripts/cli_contract.py` reads AST and reconstructs only declarative argparse setup using literals, built-in parser configuration, bounded literal loops, local declaration helpers, and literal constants read from repository source. It reads the owned output helper's declarations without importing it. It never evaluates an application callback, custom argument type/action, network/client initializer, command handler, or application import. It stops at the parse boundary. No `eval`/`exec` is used.

The linter verifies script existence, known subcommands and option names against that reconstructed contract. It handles global flag values before subcommands, quoted shell operators inside evidence, explicit environment prefixes, and wrapper `--` boundaries/child CLIs. Original line numbers survive multiline shell examples.

A missing parser, custom/dynamic declaration, or other incomplete contract is explicitly **unverified** and remains a warning (strict mode fails it). The tool does not silently downgrade an unknown to success. Actual dependency availability, runtime help success, all custom value validators, and end-to-end behavior are **not** established by static lint. Safe parser-backed tool tests and separately requested health checks cover those boundaries.

## Owned paths for parent staging/review

1. `.agents/skills` (symlink)
2. `scripts/cli_contract.py` (new)
3. `scripts/skill_metadata.py` (new)
4. `scripts/skill_distribution.py` (new)
5. `scripts/validate_skills.py`
6. `scripts/audit_codex_skill_parity.py`
7. `scripts/sync_codex_skills.sh`
8. `scripts/lint_agent_docs.sh`
9. `tools/tool_catalog.py` (new)
10. `tests/test_validate_skills.py`
11. `tests/test_skill_architecture.py` (new)
12. `tests/test_tool_catalog.py` (new)
13. `.codex/skills/audit-skills/scripts/snapshot_skills.py`

## Validation

All commands used explicit worktree cwd and:

```bash
UV_PROJECT_ENVIRONMENT=/Users/travcole/projects/osint-research/.venv
UV_NO_SYNC=1
UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache
```

- `uv run python -m pytest tests/test_validate_skills.py tests/test_skill_architecture.py tests/test_tool_catalog.py tests/test_analysis_skill_commands.py --offline -q`: **54 passed**. Dedicated B tests comprise 48; the additional six preserve actual analysis finding-CLI semantics. An earlier combined selector included `tests/test_triage_leads_skill.py`, but A removed/replaced it during concurrent implementation; that run collected nothing and was immediately rerun against existing paths.
- Ruff check on every changed/new B Python file: **passed**.
- B-owned `git diff --check`: **passed**.
- Default compatibility sync/check: **ok**, 36 repository skills resolve through the discovery symlink; no personal directory read or mutated by this check.
- Real offline catalog list smoke: **ok**, legal/court filter currently finds 68 CLI entries, returns requested three and a next offset. This is a tool-entry count, not independent source count.
- Real offline catalog describe smoke: **ok**, CourtListener search has `inspection: declarative_argparse` and no inspection limitations.
- Full snapshot with `--run-repo-validator`: **36 skills / 69 variants, 0 errors, 34 warnings, 3 info**. Artifact: `/tmp/osint-q8INnbtl/implemented-skill-snapshot.json`. This is not a claim of strict clean lint.
- Standalone normalized parity artifact: `/tmp/osint-q8INnbtl/implemented-parity.txt` (final result: 0 shared instruction/resource drift).

Tests demonstrate correct native metadata acceptance/rejection, nested-worktree runtime resolution, invalid/missing/uninspectable commands, no execution of import-time markers or custom type callbacks, reading imported literal choices without executing their module, quote-aware shell splitting, global-option/subcommand handling, wrapper child-flag ownership, multiline locations, bundled-reference lint, evidence-sensitive parity, resource parity, discovery-link resolution, and preservation/verification of edited, unrelated and symlinked personal files in a temporary backup fixture.

## Current actionable integration results

Snapshot's 34 warnings comprise:

- **34 repo-validator warnings**: 17 occurrences per runtime for six CLIs with explicitly partial static contracts: `query_usaspending.py` custom types; `query_sam.py` custom types; `ingest_uk_companies_house.py` action-default adjustment loop; `query_property.py` custom parser/conditional declarations; `query_state_courts.py` dynamic choices/custom actions; `query_california.py` dynamic choices. Preserve these unknowns. The appropriate follow-up is parser-focused tests/schema extraction for these custom portions, not executing production actions during lint or weakening strict mode. See `/tmp/osint-q8INnbtl/architecture-codex-static-validation.txt` for locations.
- **Shared-body parity is now clean (0 drift)** after parent reconciled the paired wording. No whole-skill exemption was added.
- **Runtime-syntax warnings are now 0**: parent fixed the Claude dispatch heading. Snapshot skips fenced JSON/YAML data generically when checking runtime invocations, because `/trace-entity` there is a persisted routing value. Shared normalization likewise preserves those values, so an accidental persisted `/skill` to `$skill` change cannot be hidden as invocation syntax. This behavior is fixture-tested for JSON, YAML and YML.
- **3 informational unpaired packages**: audit-skills, discover-investigations, fix-papercuts. Generated `__pycache__`/`.pyc` artifacts no longer produce bundled-resource findings.

Personal installed-copy retirement remains a separately reviewed migration after integration. This branch neither destroys old copies nor claims they have disappeared from an already-running session's catalog. No cross-model quality/latency gains have been claimed without runtime evaluations.

## Independent final review

The parent assigned a separate read-only review of B. It found and reproduced three material edge cases: silently omitted declarations in unsupported try/with blocks; report output paths that could overwrite personal/managed skills or backup copies; and help prose/positional choices incorrectly interpreted as real flags/subcommands. All three were fixed with generic regression fixtures. The independent reviewer reran its original probes, inspected the corrections, and independently ran all 54 targeted tests offline. Final result: no outstanding material B finding. Review artifact: `/tmp/osint-q8INnbtl/review-unit-b.md`.

Report outputs now require a new path outside personal and managed skill roots and outside the backup destination. Validation happens before backup copying, and exclusive file creation also rejects existing external symlink/hardlink aliases. Unsupported parser declaration control flow stays explicitly partial; option/subcommand metadata comes directly from reconstructed argparse actions, never rendered help prose.
