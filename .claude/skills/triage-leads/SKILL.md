---
name: triage-leads
description: Review pending investigation leads, preserve distinct questions, and apply scoped scheduling decisions. Use to triage, prioritize, deduplicate, or route the pending lead queue; --dry-run previews decisions.
user-invocable: true
---

# /triage-leads

Turn pending leads into justified research assignments, holds, or documented dead-ends. Use the pinned investigation/database from the research workflow contract. The current chat owns the review and final application; native subagents can review independent batches when useful and inherit the configured model.

## Scope and inputs

- No arguments: review the next batch, default 20 leads.
- `--batch-size N`: choose a batch suited to the work; 20 is a convenience, not a cognitive limit.
- `--dry-run`: preview decisions and leave the database unchanged.
- Continue through further batches when the user requested the whole queue; preserve completed batch artifacts and resume after context compaction.

Use existing findings, notes, and relevant source checks to resolve identity and question overlap. If deciding a lead would require substantial new research, promote or hold it with a concrete next step instead of silently expanding triage into that investigation.

## 1. Export the review context

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/lead_tracker.py triage-export --limit 20 \
  --output "$WORKDIR/triage-batch.json"
```

Use the requested batch size in place of 20. The packet contains the resolved `profile_id`, `database_path`, total pending count, full lead rows, notes, evidence references, and review revisions. Treat it as the immutable input to apply. An empty `leads` array means this scoped queue is empty.

Listing is not a claim. Another task can work concurrently; application rejects stale revisions or changed statuses instead of overwriting that work.

## 2. Review the questions

For each lead, inspect its title, description, notes, and evidence. Find related leads and findings when needed:

```bash
uv run python tools/lead_tracker.py list --target "<TARGET>" --limit 50 \
  --output "$WORKDIR/related-leads.json"
uv run python tools/findings_tracker.py search "<TARGET>" \
  --output "$WORKDIR/target-findings.json"
uv run python tools/triage_policy.py assess "<TARGET>" --lead-id 123 \
  --output "$WORKDIR/triage-assessment.json"
```

Replace 123 with the reviewed lead ID. `assess` returns scoped structural signals, suggested depth/routing, and same-target candidate overlaps. Entity roles are shared records and are labeled global. Read more related results when a limit obscures the decision.

Apply judgment to these signals:

- **Duplication:** same identity plus the same research question and covered source/date scope can justify a duplicate. Different legal, financial, registry, or temporal questions remain available even at the same depth. A target/depth match alone cannot close a lead.
- **Coverage:** assess what the evidence establishes and what remains unknown. Counts of findings, roles, or connections are useful review cues, not proof of exhaustive research. Mirrors and repeated mentions do not create new corroboration.
- **Priority/depth:** consider likely information value, evidentiary significance, dependencies, user priorities, and the question's complexity. Use policy suggestions as defaults; record why a novel low-degree target needs deeper research or why a familiar target does not.
- **Scheduling:** a busy thread may justify holding lower-value work; it does not justify a dead-end. A hold needs a dependency or scheduling reason and a next step.
- **Routing:** use the focused filing, contract, case, nonprofit/grant, person, or entity skill when it matches the question. Persist the scheduler’s slash-prefixed skill IDs; use the host’s native syntax for interactive invocation.

## 3. Record structured decisions

Write a JSON array to `$WORKDIR/triage-decisions.json`, one decision for every exported lead. Use actual integer IDs:

```json
[
  {
    "lead_id": 123,
    "action": "promote",
    "priority": "high",
    "depth_tier": "standard",
    "recommended_skill": "/trace-entity",
    "rationale": "The ownership question is distinct from the existing litigation lead.",
    "related_lead_ids": [122]
  }
]
```

Actions are `promote`, `hold`, or `dead_end`; every action needs a rationale. Promotion needs `priority`, `depth_tier`, and `recommended_skill` (existing values may be retained). Optional enrichments: `category`, `target_name`, and a **global database** `thread_id` belonging to this profile; `null` can clear a thread assignment.

A dead-end needs `stop_reason`. For a reviewed duplicate also supply `keeper_id`; the keeper must belong to this profile and survive the batch. If it is outside the selected pending batch, re-export with `triage-export --reference-lead-id <KEEPER_ID>` (repeatable) and review the resulting `reference_leads` snapshots as well as any changed batch membership. Preserve novel details as notes/evidence on the keeper before that fresh export, or use /dedup-leads consolidation for open leads. Do not close an unreviewed question merely to complete the packet. A justified `hold` can record the information needed to decide it.

## 4. Preview, apply, and verify

```bash
uv run python tools/lead_tracker.py triage-apply \
  --batch-file "$WORKDIR/triage-batch.json" \
  --decisions-file "$WORKDIR/triage-decisions.json" --dry-run \
  --output "$WORKDIR/triage-preview.json"
```

Read the preview. For an authorized triage run, apply the reviewed file by omitting `--dry-run` and saving `$WORKDIR/triage-applied.json`. A requested dry run ends with the preview. The command validates database/profile, exact batch membership, revisions, pending status, related/keeper IDs, and thread ownership, then applies atomically and writes audit notes. Invalid input exits nonzero with no decision changes; re-export and review stale work rather than editing revisions or bypassing checks.

Report processed/promoted/held/dead-ended counts, key rationale and keeper links, any incomplete research/dependencies, and artifact paths. Re-read scoped tracker stats for the remaining pending count. Distinguish a finished batch from a finished queue.
