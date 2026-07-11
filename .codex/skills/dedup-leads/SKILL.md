---
name: dedup-leads
description: Review open leads for duplicates using parallel sub-agents
---

# $dedup-leads

**CONTROL PLANE ORCHESTRATOR** — You dispatch batches of candidate duplicate lead groups to parallel sub-agents for review. Sub-agents decide which leads are duplicates, which should be consolidated, and which are genuinely distinct. You apply their decisions and verify the results.

## Arguments

- Optional: `--profile-id NAME` to scope to a specific investigation
- Optional: `--batch-size N` (default 20 groups per agent)
- Optional: `--agents N` (default 3 parallel agents)

## Workflow

### Phase 1: Preparation

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Working directory: $WORKDIR"
```

#### 1a. Fill missing target_names (deterministic)

```bash
uv run python tools/lead_dedup.py fill-targets --dry-run
# Review output, then apply:
uv run python tools/lead_dedup.py fill-targets
```

#### 1b. Scan for candidate groups

```bash
uv run python tools/lead_dedup.py scan --output $WORKDIR/all-groups.json
uv run python tools/lead_dedup.py stats
```

Review the scan output. Note the total groups and total leads involved.

### Phase 2: Export Batches

Export batches for parallel subagent review. Default: 3 agents, 20 groups each.

```bash
uv run python tools/lead_dedup.py export-batch --batch-size 20 --offset 0 --output $WORKDIR/batch-0.json
uv run python tools/lead_dedup.py export-batch --batch-size 20 --offset 20 --output $WORKDIR/batch-1.json
uv run python tools/lead_dedup.py export-batch --batch-size 20 --offset 40 --output $WORKDIR/batch-2.json
```

### Phase 3: Launch Sub-agents

Launch 3 sub-agents in parallel with `spawn_agent`. Each agent receives one batch file and the decision framework below.

**Sub-agent prompt template:**

```
You are reviewing lead dedup groups for the [INVESTIGATION_NAME] investigation. Each group contains 2+ open leads that may be duplicates, overlapping, or genuinely distinct investigation angles.

## Your Task

Read the batch file at [BATCH_FILE_PATH]. For each group, review all leads and decide:

1. **keep_all** — These leads represent genuinely distinct investigation angles. Different categories, different source types, or different questions about the same target. No changes.

2. **merge** — One or more leads are true duplicates (same target, same angle, same question). Pick the best lead as keeper (prefer: highest priority, most notes/evidence, best description). The rest get dead-ended.

3. **consolidate** — Leads overlap but each has unique information worth preserving. Pick the best as keeper, dead-end the rest. Their unique details will be appended as notes to the keeper.

## Merge Criteria (follow strictly)

- Same target + same investigation angle (same category, similar title asking the same question) = **merge**
- Same target + different angles (e.g., "financial flows" vs "corporate registrations" vs "legal history") = **keep_all**
- Same target + one lead is clearly a subset of another (broader lead covers narrower lead's scope) = **consolidate**
- Different targets grouped by name variant (e.g., "Les Wexner" and "Leslie Wexner") = **merge** if same angle, **keep_all** if different angles
- Auto-generated leads ("Cross-ref officer: X", "Serial director: X") that ask the same underlying question = **merge**
- When uncertain, **keep_all** — false merges lose investigation angles, which is worse than keeping a few duplicates

## Keeper Selection

When merging or consolidating, pick the keeper that:
1. Has the most detailed description
2. Has notes attached
3. Has higher priority
4. Was created earlier (more established)
5. Has a `depth_tier` set

## Output Format

Write your decisions to [OUTPUT_PATH] as a JSON array:

```json
[
  {
    "group_hash": "abc123...",
    "decision": "merge",
    "keeper_id": 1234,
    "dead_end_ids": [1235, 1236],
    "rationale": "Leads #1235 and #1236 are both auto-generated officer cross-refs asking the same question as #1234.",
    "target_name_fills": {}
  },
  {
    "group_hash": "def456...",
    "decision": "keep_all",
    "keeper_id": null,
    "dead_end_ids": [],
    "rationale": "Lead #500 investigates financial flows while #501 traces corporate registrations. Distinct angles.",
    "target_name_fills": {"502": "John Smith"}
  }
]
```

Notes:
- `target_name_fills`: if any lead in the group has no target_name, infer it from the title/description and include it here as {"lead_id": "inferred_name"}
- `rationale`: brief explanation (1-2 sentences) for audit trail
- Include ALL groups from the batch in your output, even keep_all decisions

Read the batch file now and process all groups:
```bash
cat [BATCH_FILE_PATH]
```
```

### Phase 4: Apply Decisions

After all sub-agents complete, read their output files and apply:

```bash
# Dry-run first
uv run python tools/lead_dedup.py apply --decisions-file $WORKDIR/dedup-decisions-0.json --dry-run
uv run python tools/lead_dedup.py apply --decisions-file $WORKDIR/dedup-decisions-1.json --dry-run
uv run python tools/lead_dedup.py apply --decisions-file $WORKDIR/dedup-decisions-2.json --dry-run

# If dry-run looks good, apply for real
uv run python tools/lead_dedup.py apply --decisions-file $WORKDIR/dedup-decisions-0.json
uv run python tools/lead_dedup.py apply --decisions-file $WORKDIR/dedup-decisions-1.json
uv run python tools/lead_dedup.py apply --decisions-file $WORKDIR/dedup-decisions-2.json
```

### Phase 5: Verify

```bash
uv run python tools/lead_dedup.py verify --sample-size 15
uv run python tools/lead_dedup.py stats
```

Check for:
- No chain problems (keeper was also dead-ended)
- All dead-ended leads have corresponding lead_relations
- Stats show reasonable merge/keep_all ratio (expect ~30-50% keep_all for well-curated leads)

### Phase 6: Iterate

If there are more unprocessed groups, repeat Phases 2-5 with increased offsets. The system is idempotent — already-processed groups are skipped automatically.

## Safety Guarantees

- **No deletions** — leads are only dead-ended, never deleted
- **Audit trail** — all decisions logged in `lead_dedup_log` with rationale
- **Reversible** — any lead can be reopened: `uv run python tools/lead_tracker.py reopen <ID>`
- **Concurrent-safe** — dead-end operations check current status before updating
- **Idempotent** — `group_hash` prevents reprocessing the same group

