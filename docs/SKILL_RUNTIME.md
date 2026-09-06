# Skill runtime and distribution

The version-controlled Codex packages live in `.codex/skills`. The tracked
`.agents/skills -> ../.codex/skills` link makes that same content discoverable by
current Codex repository discovery. Claude packages live in `.claude/skills`.
Paired packages share substantive behavior, with runtime-specific metadata and
native tool names where required. The configured host model is inherited;
domain skills do not select a generation or tier.

```bash
bash scripts/sync_codex_skills.sh
uv run python scripts/audit_codex_skill_parity.py --show-diffs
bash scripts/lint_agent_docs.sh
```

The historically named sync script now checks repository discovery by default.
It does not copy packages into HOME or overwrite personal edits. Current hosts
may also discover personal skills; duplicate names are not a reliable override
or merge mechanism. Older project copies remain a migration concern until their
differences are reviewed and they are retired from the active personal search path.

For an explicitly selected personal skill directory:

```bash
bash scripts/sync_codex_skills.sh inventory --personal-root "<personal-skill-root>" \
  --output "$WORKDIR/personal-skill-inventory.json"
bash scripts/sync_codex_skills.sh backup --personal-root "<personal-skill-root>" \
  --destination "$WORKDIR/personal-skill-backup" \
  --output "$WORKDIR/personal-skill-backup.json"
```

Inventory compares only names managed by this repository and preserves unrelated
skills. Backup requires a new destination, preserves original paths and symlinks,
and verifies manifests. Review differing content before any deliberate retirement;
do not install a temporary worktree link as a permanent personal dependency.
The implementation task changed repository discovery and tools, and left existing
personal installations intact. Use the updated repository branch for the revised
packages; an already-running chat may retain its earlier skill inventory.

Claude frontmatter uses documented native fields such as `user-invocable`.
`allowed-tools` grants permissions in Claude and is not an availability sandbox.
Codex UI text and invocation policy belong in `agents/openai.yaml`. Preserve
runtime-specific controls when intentional; do not add blanket invocation or
tool restrictions without a concrete behavioral reason.

The validator and catalog inspect CLI contracts without executing source actions.
Structural success does not establish correct evidence, complete coverage, safe
mutations, or reliable model behavior. Use fixture tests for fragile operations
and representative forward tests for orchestration, triggers and authorization.
See [the audit skill](../.codex/skills/audit-skills/SKILL.md).

Interactive native supervision and long-work recovery follow
[the execution contract](EXECUTION_CONTRACT.md). The legacy dispatcher remains
an explicitly selected unattended path. Its model defaults are unset. The isolated
SEC extraction CLI can inherit the root model selection from Codex user config;
an ephemeral chat or named-profile selection requires an explicit `--model`.
When no selection is available it leaves the runtime choice unresolved in
provenance and avoids reusing a model-specific cache entry under an unknown default.
