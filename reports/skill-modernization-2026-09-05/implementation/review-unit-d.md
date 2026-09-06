# Independent review of Unit D

Reviewed Unit D in `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`, including a final independent reread and retest after the owner completed corrections. Read-only review; no repository edits, production database queries, source requests, site output writes, model invocations, or commits. Tests used temporary fixtures. All findings raised in this review are resolved; no outstanding blocker was found.

## Verified findings

### Resolved and independently retested: batch inventory omitted actual curated files absent from the index

The prior `get_curated_slugs()` derived its selection exclusively from `_index.json`, while the updated paired review-dossiers skills promise all curated dossiers for an unbounded batch (`.codex/skills/review-dossiers/SKILL.md:13`, `:41`). A stale index silently excluded a newly created curated dossier, producing no automated packet or semantic-review assignment for it. This was a pre-existing implementation gap exposed by the new all-curated handoff contract, rather than a receipt bypass: `validate_receipts()` already inventories actual files (current `scripts/review_dossier_checks.py:1242`–`1247`).

The independent temporary fixture initially reproduced this with two curated files and only one indexed entry. Final code at `scripts/review_dossier_checks.py:811`–`829` enumerates actual JSON files and treats the index as optional ranking metadata. `cmd_batch()` at `:954`–`967` emits a packet for each selected file. The regression at `tests/test_editorial_verification_scope.py:131`–`155` now indexes only the first dossier, creates both dossiers, and verifies that both aggregate entries and both individual packets exist with exact current hashes. This fixture passed in the final independent rerun.

### Resolved during review: canonical citation tokens could disappear from evidence scope

The initial `article_citations()` accepted only alphabetic uppercase/underscore prefixes. Documented numeric, mixed-case and hyphenated tokens such as `[990:123456789]`, `[COURT-DATA:example]`, `[OffshoreAlert:example]`, and `[LittleSis:1234]` were silently ignored. An article containing a valid `[Finding #1]` alongside one of those unresolved citations could report a clean audit for only the first finding.

Owner corrected `scripts/evidence_audit.py:55`–`70`: bracket tokens are retained conservatively; exact unresolved aliases remain visible. `load_scope()` reports unmapped citations (`:119`) and `build_report()` makes their presence incomplete (`:222`). Five parametrized fixture variants now pass (`tests/test_editorial_verification_scope.py:85`–`93`), including legacy space-separated SEC syntax.

### Resolved during review: redirected npm output was not valid JSON

The new editorial examples redirected `npm run report:support-coverage` stdout into `support-coverage.json`, but npm prepends lifecycle banners. A temporary package reproduction exited zero while `json.loads(stdout)` failed. Adding `--silent` produced valid JSON. Owner applied that correction to both runtimes of write-article, review-article and curate-dossier; current examples are at `.codex/skills/write-article/SKILL.md:76`, `.codex/skills/review-article/SKILL.md:27`, and `.codex/skills/curate-dossier/SKILL.md:258`.

### Minor clarification resolved

The review-dossiers sample at `.codex/skills/review-dossiers/SKILL.md:72` now explicitly requires the SHA-256 of the raw dossier bytes, matching the automated packet. This corrects the earlier ambiguous packet-and-dossier wording. Incorrect use fails closed rather than accepting a stale receipt.

## Verified strengths and dismissed concerns

- Evidence audit opens the selected DB read-only, begins a snapshot, resolves its pinned profile, and filters finding IDs/reference joins by that profile (`scripts/evidence_audit.py:24`, `:73`, `:87`, `:171`). A foreign-profile citation is reported missing/out-of-profile instead of importing its findings.
- The text checker compares the complete normalized quote (`scripts/evidence_audit.py:149`–`167`), so a shared opening followed by a materially different ending produces mismatch. Missing/unreadable source text is unknown, never match. Non-EFTA references accept explicit source artifacts. Quote presence is explicitly distinguished from semantic support, authenticity, independence and allegation truth.
- Shared primary references produce overlap candidates, not an automatic duplicate finding or unrelated article blocker (`scripts/evidence_audit.py:206`–`232`). This retains useful reuse without inventing corroboration.
- Explicit coverage targets do not depend on Git changes. Requested paths are validated and missing targets fail (`web/scripts/support-coverage-scope.mjs:10`–`20`); output includes each current file hash and rejects incomplete requested-target coverage (`web/scripts/report-support-coverage.mjs:96`, `:127`, `:142`–`149`).
- Existing semantic receipts still require exact current dossier content, a real reviewer/timestamp, an explicit internally consistent verdict and issue list. Automated PASS and historical unbound DB reviews do not grant semantic PASS; current receipt validation reruns independent static blockers and rechecks content after validation (`scripts/review_dossier_checks.py:1184`, `:1237`–`1267`). No stale-receipt acceptance was found. The new `bound_checks()` guard (`:933`–`940`) also rejects a dossier edited during automated checking, preventing earlier checks from acquiring a later content hash.
- The shortened writing/review skills retain primary-source verification of material claims, full contextual source reading, every quotation/load-bearing figure, current and event-date legal context, identity/role/date/amount accuracy, provenance independence, allegation/inference distinctions, alternative explanations, rendering and final-content revalidation. Removing rhetorical quotas did not remove these obligations. Article argument remains distinct from encyclopedic dossier tone; craft guidance remains linked.
- The explicit unattended compatibility wrapper now uses unique run directories, pinned context, actual final review artifacts, serial persistence and receipt validation. Inspection plus dry-run fixtures verified no model launch in dry-run; actual unattended execution was deliberately not tested.

## Validation and coverage

Final independent run of `tests/test_editorial_verification_scope.py` plus `tests/test_dossier_review_receipts.py`: **35 passed**. This includes the corrected unindexed dossier packet fixture, concurrent-content-change rejection, missing/foreign citation checks, stale receipt tests, and parent-requested output collision/hardlink/SQLite-sidecar guards. These are the two suites rerun here; the owner's broader total is separate.

Final rerun of `node web/scripts/test-support-coverage-targets.mjs`: passed new/modified/unchanged target selection, missing/out-of-scope/conflicting-mode rejection, and the newly added full coverage CLI fixture with exact current hash assertions. Scoped `git diff --check` also passed.

Independent end-to-end executions of the real coverage CLI used a temporary `ITHILDIN_CONTENT_DIR`, a non-existent scratch DB path and an unrelated cwd. Each of three explicit article targets (new, edited, unchanged) returned one nonempty result with its exact current SHA-256. The edited article returned two sentences versus one for the others. A missing named target exited nonzero. No DB was created. The initial missing-jiti environment limitation was resolved when the owner wired the existing shared dependency directory.

Inspected full current evidence-audit and coverage scripts; the dossier checker delta and relevant inventory/packet/receipt paths; the rewritten unattended wrapper; paired review-article, write-article, review-dossiers and status-report skills; curate-dossier/discover-investigations deltas; associated tests and source/craft contracts. This was a code/fixture and semantic-instruction review, not a claim of measured cross-model research-quality improvement or a semantic review of real published content.
