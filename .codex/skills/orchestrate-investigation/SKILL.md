---
name: orchestrate-investigation
description: Launch, supervise, review, and import staged investigation workers through the shared dispatcher control plane
---

# $orchestrate-investigation

**CONTROL PLANE ORCHESTRATOR** — Use this skill when you want Codex to act as the investigation foreman. Codex decides what to run, launches bounded workers through the shared dispatcher, monitors progress, reviews staged artifacts, and imports approved output. Worker execution still happens through repo-local Claude skills and the shared `scripts/dispatcher.py` backend.

Use this skill instead of `$dispatch` when you need to:
- launch workers
- supervise running jobs
- review staged artifacts
- approve or reject runs
- import approved output into canonical tables

Keep `$dispatch` read-only. Use it for queue visibility only.

## Shared Backend

All control-plane actions go through:

```bash
uv run python scripts/dispatcher.py <subcommand> ...
```

This Codex wrapper always records `--orchestrator codex` on manual launches.

## Workflow

### 1. Plan or Status First

Use one of:

```bash
uv run python scripts/dispatcher.py status
uv run python scripts/dispatcher.py plan
```

Use `status` when you need current run health, auth health, or review queue state.
Use `plan` when you need the next wave recommendation.

### 2. Launch Typed Jobs

Manual launches should use explicit task-contract fields. Common examples:

```bash
uv run python scripts/dispatcher.py launch trace_entity "Swiss Commodity Re Limited" \
  --brief "Map ownership, directors, addresses, and filing anomalies" \
  --priority high \
  --review-required \
  --orchestrator codex

uv run python scripts/dispatcher.py launch investigate_person "Malcolm Scott Macintyre" \
  --brief "Clarify role in the ASA and any overlap with Jett/Capella" \
  --priority high \
  --review-required \
  --orchestrator codex

uv run python scripts/dispatcher.py launch pursue_lead 32512 \
  --lead-id 32512 \
  --brief "Focus on evidence of post-F-3 share monetization" \
  --priority high \
  --review-required \
  --orchestrator codex
```

### 3. Monitor for Completion or Stall

```bash
uv run python scripts/dispatcher.py status
```

Look for:
- `health=stalled`
- auth failures
- completed runs waiting in the review queue

### 4. Review Staged Artifacts

Inspect:

```bash
uv run python scripts/dispatcher.py review
uv run python scripts/dispatcher.py review --run-id <RUN_ID>
```

Approve or reject:

```bash
uv run python scripts/dispatcher.py review --approve <RUN_ID> --reviewer codex
uv run python scripts/dispatcher.py review --reject <RUN_ID> --reviewer codex --note "reason"
```

### 5. Import Approved Output

```bash
uv run python scripts/dispatcher.py import --run-id <RUN_ID> --actor codex
uv run python scripts/dispatcher.py import --all-approved --actor codex
```

## Rules

- Prefer repo-local Claude worker skills as the canonical worker instructions.
- Use staged review/import for manual research and analysis launches.
- Keep task briefs short and concrete.
- Do not bypass the dispatcher with raw `claude -p` when doing orchestrator work.
- Do not use `$dispatch` to launch or import. It stays read-only.

## Supported Subcommands

- `run`
- `daemon`
- `status`
- `plan`
- `launch`
- `review`
- `import`
- `stop`

## Notes

- Claude Code is the only worker backend in v1.
- Future worker backends should plug into the dispatcher adapter, not into this skill.
