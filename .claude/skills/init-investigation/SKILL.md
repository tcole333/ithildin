---
name: init-investigation
description: Create an investigation profile and seed its threads, dates, pillars, and initial leads under explicit database/profile context. Use when starting an investigation or scaffolding its config.
user-invocable: true
---

# /init-investigation

Create a profile for a subject or topic. With no target, list available profiles
and the current context. `--dry-run` prepares proposed configuration and seed
actions without creating files or database rows. Existing authorization carries
through the setup; ask only when a conflicting existing profile leaves identity
or scope unresolved.

Read [the research workflow contract](../../../docs/RESEARCH_WORKFLOW_CONTRACT.md)
and [the Git workflow](../../../docs/GIT_WORKFLOW.md). Preserve existing profiles
and unrelated work. Inspect `investigations/_template/config.yaml` and:

```bash
rg --files investigations -g config.yaml
```

## Build the profile

Read matching profile configs directly for this inventory. The existing
`investigation_context.py list` command reconciles the database catalog; do not
use it in a dry run. Resolve a task's current pin through the read-only status
tool/context resolver when needed, without seeding or registering profiles.

Choose a short lowercase slug and create `investigations/<slug>/config.yaml`
from the template without overwriting an existing file. Populate required
`name`, `primary_subject`, and `description`, then add supported context:

- `key_persons`, `known_addresses`, `key_dates`, and `seed_pillars` from identified
  public sources or user-provided context, with provenance notes in the profile's
  case instructions. Do not turn recalled allegations into established identity
  or priority rules. Keep uncertain associations as provisional research questions.
- Useful thematic `threads`, with scoped targets and classification patterns.
  Start with enough to organize this investigation; no fixed thread/person quota.
- `corpus_tools` only for actual available corpora. Generic sources are selected
  for relevance using the research contract, not seeded indiscriminately.
- Evidence prefixes, reliability overrides, and graph settings when applicable.

Place case-specific source/provenance and uncertainty notes in
`investigations/<slug>/AGENTS.md`; provide equivalent discoverable case guidance
for the host when needed. Tasks working from the repository root must read these
instructions explicitly.

## Pin and seed the new investigation

Select the intended database and replace any inherited old profile pin before
seeding. Use explicit context on each command; `set` alone does not override an
inherited `ITHILDIN_PROFILE`.

```bash
uv run python tools/investigation_context.py run --profile "<slug>" \
  --db "$ITHILDIN_DB_PATH" -- uv run python tools/lead_tracker.py thread seed
uv run python tools/investigation_context.py run --profile "<slug>" \
  --db "$ITHILDIN_DB_PATH" -- uv run python tools/event_timeline.py seed
uv run python tools/investigation_context.py run --profile "<slug>" \
  --db "$ITHILDIN_DB_PATH" -- uv run python tools/pillar_tracker.py seed
```

Read the returned thread IDs from this database. Add a small set of distinct,
useful initial questions through `lead_tracker.py add`, using the same explicit
context and actual thread IDs. Check existing leads before re-seeding a resumed
setup. Do not infer that a matching title means every question is answered.

Change the shared interactive default with `investigation_context.py set` only
when the user requested that change; the new task can run with explicit context.
Verify the new profile and rows with scoped `show` and `stats` commands through
the same wrapper. Report files created, actual seed counts, selected database,
profile, any intentionally missing context, and the next useful investigation step.
