---
name: dedup-leads
description: Review duplicate or overlapping open investigation leads and preserve distinct research questions. Use to deduplicate or consolidate the lead queue with scoped review packets and verified application.
user-invocable: true
---

# /dedup-leads

Review candidate overlaps under the current chat's supervision. Preserve different investigation angles; consolidate unique context when one keeper should own the work. Tools enforce database/profile isolation, reviewed membership, revisions, audit relations, and atomic writes.

## Inputs and execution

- Optional `--profile-id NAME` selects an investigation; otherwise use the pinned/default profile. Preserve `ITHILDIN_DB_PATH`.
- Optional `--batch-size N`, default 20 groups per review packet.
- Optional `--agents N` bounds native parallel reviewers. Choose fewer for small queues or tightly coupled work; use sequential review when native subagents are unavailable.
- `--dry-run` previews all decisions without target fills or decision application.

Keep the parent engaged through review, application, and further waves. Use the host’s native subagents only for independent packets; inherit the configured model unless the user selected an override. Do not launch headless workers for an interactive dedup request.

## 1. Inspect and prepare the selected queue

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/lead_dedup.py fill-targets --dry-run \
  --output "$WORKDIR/target-preview.json"
```

Inspect deterministic target-name inferences. For an authorized modifying run, apply by omitting `--dry-run` and saving `$WORKDIR/target-fills.json`. This only fills missing targets in the selected profile. Leave ambiguous/unrecognized names for review; do not equate string similarity with identity.

```bash
uv run python tools/lead_dedup.py scan --output "$WORKDIR/all-groups.json"
uv run python tools/lead_dedup.py stats --output "$WORKDIR/before-stats.json"
```

Report an empty candidate queue honestly. Check `unfilled` target records separately; a lead excluded because its target is unknown is not a reviewed nonduplicate.

## 2. Freeze each wave's review packets

```bash
uv run python tools/lead_dedup.py export-batch --batch-size 20 --offset 0 \
  --output "$WORKDIR/wave-1-batch-0.json"
```

For multiple workers, export the other disjoint packets at offsets 20, 40, etc. **Finish all exports for the wave before applying any decisions.** Use the chosen batch size and actual worker count; do not launch workers for empty packets.

Each packet binds the database/profile, group IDs, complete lead descriptions/notes/evidence, and revisions. Preserve it unchanged. Assign each reviewer one input path and one distinct decision-output path, with read-only access to canonical state. The parent collects every expected file or records the missing handoff before applying that packet.

## 3. Review each group

Give reviewers the packet and these criteria, without a desired merge rate or expected conclusion:

- `keep_all`: different identity, different questions, relevant source/date scopes, or uncertain equivalence. Same target does not mean same investigation angle.
- `merge`: same identity and same underlying research question with no unique context to transfer.
- `consolidate`: overlapping scope where one keeper should own the question and every unique detail must remain available.

Select a useful keeper by question coverage, existing evidence/notes, clarity, active dependencies, and priority. Higher depth or an earlier creation date alone does not decide. A group may contain both true duplicates and distinct leads; close only the reviewed duplicate subset.

Write one JSON decision per group, including `keep_all`:

```json
[
  {
    "group_hash": "<exact exported group_hash>",
    "decision": "consolidate",
    "keeper_id": 123,
    "dead_end_ids": [124],
    "rationale": "Both ask the same ownership question; preserve the second lead's filing notes on the keeper.",
    "target_name_fills": {}
  }
]
```

Use actual integer lead IDs from that group. `keep_all` uses `keeper_id: null` and `dead_end_ids: []`. All decisions require rationale. Target fills, if needed, use string lead IDs and may fill only previously empty names.

Reviewers return file paths and unresolved issues. They do not apply decisions or alter the exported packets.

## 4. Parent review and application

Read the returned decisions and reconcile any identity/scope uncertainty with the packet. Preview each packet:

```bash
uv run python tools/lead_dedup.py apply \
  --batch-file "$WORKDIR/wave-1-batch-0.json" \
  --decisions-file "$WORKDIR/wave-1-decisions-0.json" --dry-run \
  --output "$WORKDIR/wave-1-preview-0.json"
```

For an authorized modifying run, apply the reviewed pair by omitting `--dry-run` and saving a separate application result. No additional permission question is needed for the already requested deduplication. In dry-run mode, stop at previews and report the remaining unmodified queue.

Application requires one decision per exported group, valid group membership/keeper IDs, the same database/profile, and unchanged open leads including their notes/evidence. It validates the full packet before any changes. Invalid/stale packets exit nonzero; re-export affected work and review it. Never remove revision checks or silently skip a failed reviewer.

Consolidation preserves full source descriptions and notes on the keeper with provenance and copies evidence references. Original rows remain, linked by duplicate/supersedes relations. Repeating an identical successfully applied decision is idempotent; a conflicting prior decision requires review.

## 5. Verify and continue

```bash
uv run python tools/lead_dedup.py verify --sample-size 15 \
  --output "$WORKDIR/dedup-verification.json"
uv run python tools/lead_dedup.py stats --output "$WORKDIR/after-stats.json"
```

Resolve reported keeper/relation issues before declaring success. Sampling checks consistency of recent decisions; it does not establish that every judgment was correct.

For the next wave, **reset offsets to 0, batch-size, twice batch-size, etc.** The exporter removes processed groups, so increasing offsets across completed waves skips work. Use new wave filenames, continue until the requested scope is covered, and retain a packet/result manifest across compaction. Report reviewed groups, merges/consolidations/keep-all, unfilled targets, unresolved packets, and remaining groups. Do not promise any expected percentage of merges.
