# Independent review of Unit A

Reviewed only Unit A's `tools/lead_tracker.py` review packet/apply functions, `tools/lead_dedup.py`, `tools/triage_policy.py`, and related old/new tests in `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`. No repository source edits or production database operations. Findings were sent to `review_operations` and the parent for correction.

## Findings identified and corrected during review

### P2 — Exported snapshot bodies are not actually bound to their revision

`tools/lead_tracker.py:129-135` compares the live revision only to the packet's supplied revision, but does not verify the supplied packet body. `tools/lead_dedup.py:539-546` subsequently reads title, description, and notes from the packet itself while consolidating them into the keeper.

Reproduced with an isolated generated SQLite database: export two open leads, edit the source snapshot's description without changing its revision, then consolidate. Application succeeds and inserts the edited description into the keeper notes. Output: `{"tampered_packet_accepted": true, "changed_description_persisted": true}`. This can introduce text that was never persisted or reviewed as the original source while claiming a snapshot-bound consolidation.

Fix by verifying the complete supplied snapshot against its revision/live snapshot before accepting it, and/or using the returned validated current snapshot as the sole source of copied fields. Add a body-tampering regression, not only membership/hash checks.

### P2 — Duplicate closure does not bind the keeper's reviewed question

`tools/lead_tracker.py:2698-2704` validates a keeper outside the pending-lead packet only for current profile and active status. Its reviewed revision is not captured or required. A keeper can retain open status while its target, question, notes, or evidence changes between review and apply.

Reproduced with an isolated generated SQLite database: export the pending ownership question, then change its open keeper's title from that same ownership question to an unrelated litigation question. Apply the earlier duplicate decision. The pending question is closed with status `dead_end`; the changed keeper is accepted. Output: `{"changed_keeper_accepted": true, "victim_status": "dead_end"}`.

Fix by including/requiring the keeper's reviewed snapshot or revision and validating it under the same `BEGIN IMMEDIATE` transaction before closing the source. The active-status check should remain. The reviewed snapshot must be independently bound to the intended same-profile keeper, rather than inferred from its current active state.

### P2 — Existing profile-metadata regression test fails after the signature change

`tools/triage_policy.py:227` now requires `_load_profile_config(profile_id)` and correctly uses `load_profile(profile_id)`. `tests/test_profile_analysis_papercuts.py:10-23` still calls it without an argument and patches `get_active_profile`. Running the related old/new suites produces `TypeError: _load_profile_config() missing 1 required positional argument: 'profile_id'`.

Update this fixture to assert the intended explicit-profile behavior, including that the requested profile ID reaches `load_profile`. Do not restore dependence on another database's shared active profile simply to satisfy the old fixture.

## Checks and observations

Executed with the shared uv environment and `--offline`:

```bash
uv run pytest --offline tests/test_lead_review_workflows.py tests/test_profile_analysis_papercuts.py tests/test_enforcement.py -q
```

Result before corrections: **85 passed, 1 failed**, 5.33s. The failure is the profile-metadata test above. Two additional disposable-database reproductions confirmed the snapshot-body and keeper-staleness defects.

No separate atomicity defect found: application validates all planned mutations before applying them inside a write transaction, rolls back on failure, and uses profile/status predicates for lead closures. Foreign IDs, changed statuses, wrong databases, and incomplete decision sets have meaningful fixture coverage. Dedup replay compares the canonical decision and profile; dry runs use read-only connections and skip writes/schema creation.

The 90-group fixture exercises shrinking queues across waves with all packets exported before writes and offsets reset each wave. It passes and I did not find a nonterminating dedup loop. Structural depth/finding counts no longer automatically close distinct questions. These positive checks do not supersede the two staleness/content defects above.

## Correction status

The Unit A owner corrected all three findings, and I independently re-read the changes:

- `validate_review_lead` now compares the entire current snapshot with the supplied snapshot under the transaction, rejecting edited descriptions/notes as well as changed revisions.
- `triage-export --reference-lead-id ID` (repeatable) saves same-profile external keeper snapshots in `reference_leads`. Apply requires the keeper in the selected batch or reference set and validates its full snapshot before closure.
- The metadata fixture now calls the explicit-profile loader and patches `load_profile` rather than the shared-active helper.

New regressions exercise modified snapshot bodies, missing keeper snapshots, and changed keeper questions. The same independent offline test command now reports **88 passed in 6.20s**. No unresolved substantive issue remains from this review; normal limits of focused code and fixture review apply.
