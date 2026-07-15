---
name: fix-papercuts
description: Triage and resolve accumulated repository friction from methodology_observations. Use when the user asks to fix, clean up, review, burn down, deduplicate, or promote papercuts, recurring tool frustrations, dead commands, misleading errors, stale instructions, or small process gaps.
---

# $fix-papercuts

Turn logged friction into verified fixes, deduplicated records, or linked infrastructure work. Do not merely propose changes.

## Arguments

- No arguments: process up to 10 distinct, oldest open friction roots.
- One or more observation IDs: process only those records.
- `all`: continue in batches until no safely actionable friction remains. Stop if progress would require broad or externally consequential work.

## 1. Snapshot the Queue

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/methodology_tracker.py list \
  --category friction --status open --oldest-first --limit 500 \
  --output "$WORKDIR/open-friction.json"
uv run python tools/methodology_tracker.py list \
  --category process_gap --status open --limit 500 \
  --output "$WORKDIR/open-gaps.json"
uv run python tools/infra_tracker.py list --status open --limit 500 \
  --output "$WORKDIR/open-infra.json"
uv run python tools/infra_tracker.py list --status evaluating --limit 500 \
  --output "$WORKDIR/evaluating-infra.json"
uv run python tools/infra_tracker.py list --status in_progress --limit 500 \
  --output "$WORKDIR/active-infra.json"
git status --short
```

Treat `friction` as the primary queue. Include a `process_gap` only when the user names its ID or it is inseparable from a selected friction root. Preserve unrelated worktree changes.

Sort selected records oldest-first and group exact or clearly equivalent descriptions. A workaround mentioned in an observation is reproduction context, not the desired fix.

## 2. Classify Each Root

Use one outcome:

1. **Already fixed** — verify the current behavior and relevant regression coverage, then address it.
2. **Duplicate** — confirm the same root cause and keep the oldest or clearest record canonical.
3. **Small fix** — reproduce and implement it during this run.
4. **Infrastructure work** — link it to an existing request or create one, then promote it.
5. **Insufficient evidence** — leave it open and report the missing reproduction detail.
6. **Obsolete/non-issue** — dismiss only with objective evidence. Inability to reproduce once is not sufficient.

A small fix must be local, root-caused, testable, and bounded. It must not require a new paid service, contacting a subject, bypassing access controls, broad schema redesign, large data ingestion, or unrelated refactoring. If the change expands while investigating, stop and promote it.

## 3. Close Duplicates First

For exact duplicates, verify that context does not reveal distinct causes, then run:

```bash
uv run python tools/papercut.py --duplicate <DUPLICATE_ID> --of <CANONICAL_ID>
```

For near-duplicates, reproduce or inspect the affected code before merging them. Similar symptoms from different tools are not duplicates.

## 4. Fix Small Roots

For each selected root:

1. Inspect the relevant code, documentation, and existing tests.
2. Reproduce the failure or establish a deterministic code-level cause.
3. Make the smallest root-cause change.
4. Add or update proportionate regression coverage.
5. Run the narrow test first, then the relevant surrounding suite.
6. Review the diff for silent fallbacks, special cases, weakened checks, and unrelated edits.
7. Resolve only after verification succeeds:

```bash
uv run python tools/papercut.py --resolve <ID> \
  --resolution "<root-cause change>; verified with <checks>"
```

If several observations share the fixed root, resolve the canonical record and mark the rest duplicate of it.

Do not resolve an entry because a workaround succeeds. Do not add unbounded retries, swallow exceptions, duplicate an implementation, hard-code investigation-specific data, or weaken a test to obtain a passing result.

## 5. Promote Larger Work

Search the exported open, evaluating, and active infra JSON files for the tool name, failure signature, and root-cause terms before creating a request. Inspect plausible matches with `uv run python tools/infra_tracker.py show <ID> --output "$WORKDIR/infra-<ID>.json"`.

If none matches, create a specific `tool_fix` or `tool_improvement` request:

```bash
uv run python tools/infra_tracker.py add \
  --title "<specific root problem>" \
  --type tool_fix \
  --description "Observation #<ID>: <failure, reproduction, desired behavior>" \
  --priority <critical|high|medium|low> \
  --existing-tool "<path when applicable>" \
  --discovered-by fix-papercuts
```

Then link and acknowledge the observation:

```bash
uv run python tools/papercut.py --promote <ID> --infra-id <INFRA_ID>
```

Link duplicates to the canonical observation rather than creating multiple infra requests.

## 6. Report Outcomes

Return:

- records inspected;
- fixes made and verification commands;
- duplicates consolidated;
- records promoted with infra IDs;
- records left open and the evidence needed;
- remaining open-friction count.

Do not claim the queue is clear while acknowledged infrastructure work or unresolved open records remain.
