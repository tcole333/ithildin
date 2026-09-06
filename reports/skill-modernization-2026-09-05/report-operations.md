# Operations skill audit

Reviewed the full Codex skill text for `orchestrate-investigation`, `dispatch`, `init-investigation`, `triage-leads`, `dedup-leads`, `review-methodology`, `fix-papercuts`, and `audit-skills`; compared every existing Claude counterpart using full diffs (six paired packages; `fix-papercuts` and `audit-skills` are Codex-only). Read the audit rubric, Git workflow, research workflow contract, and relevant tracker/dispatcher implementations. Scope was clean per the parent snapshot. This was static read-only review: no audited workflow, jobs, tests with database side effects, or production mutations were run. Current external best-practice research is owned by the parent.

All paths below are repository-relative under `/Users/travcole/projects/osint-research`; line numbers were verified in the present files.

## Verified findings

### [P1] Triage reads the selected database but writes the hardcoded canonical database

ID: `triage-leads:context:split-read-write-database`

- Evidence: `.codex/skills/triage-leads/SKILL.md:55` selects leads through the tracker, while `:259` and `:275` open `sqlite3.connect('investigation.db')` before promotions and dead-ends. Claude equivalents are `:56`, `:258`, and `:274`. The mutations filter only by `id` at Codex `:264`/`:280`; they do not check the pinned profile or that the row remains `pending_triage`. Additional structural and coverage reads at `:176` and `:212` use the same hardcoded database and unscoped queries.
- Verified implementation: `tools/lead_tracker.py:34` honors `ITHILDIN_DB_PATH`. `docs/RESEARCH_WORKFLOW_CONTRACT.md:18` explicitly requires preserving this path, so simply inheriting the required environment cannot make the embedded SQL honor it.
- Failure: a staged/test-database run selects lead ID 42 from its isolated database, then promotes/dead-ends canonical lead 42. In concurrent canonical triage, an agent can also overwrite a row another worker has already changed, because “Claim Batch” is only a list and the update has no expected-state condition.
- Correction: add/use one typed tracker operation for applying reviewed triage decisions, honoring pinned database/profile and expected `pending_triage` status; accept a decisions file so rationale is data rather than nested shell/Python code. Remove the inline mutation scripts and scope the remaining assessment queries.
- Verification: a two-database, two-profile fixture with colliding numeric IDs; apply a decision under `ITHILDIN_DB_PATH` and prove the canonical and other-profile rows remain untouched. Change the selected row’s status between export/apply and require a reported conflict.
- Why existing validation misses it: `tests/test_triage_leads_skill.py:11` and `:20` assert exact tracker command strings and absence of old query text. They do not execute the write path or prohibit the remaining hardcoded database connections. Keep structural checks, but add behavior tests on the typed command rather than more prose-string locks.

### [P1] Dedup's advertised scoped workflow can change all profiles in the canonical database

ID: `dedup-leads:context:unscoped-backend`

- Evidence: `.codex/skills/dedup-leads/SKILL.md:12` offers `--profile-id NAME`; `:28`–`:30` first calls `fill-targets`, then `:36` and `:47`–`:49` scan/export without an explicit profile. Claude lines are one higher.
- Verified implementation: `tools/lead_dedup.py:24` hardcodes canonical `investigation.db`; `:91` opens it and ensures schema. `cmd_fill_targets` at `:215` selects every open/pending lead missing a target and updates them at `:239`, without a profile filter. CLI `fill-targets` has no profile option (`:940`–`:943`). `_build_groups` at `:291` filters only if an explicit argument is supplied, not from `ITHILDIN_PROFILE`. `apply` accepts a decisions file and dry-run only (`:963`–`:966`) and does not validate group membership/profile before mutations (`:670`–`:730`).
- Failure: an invocation scoped to one investigation still fills target names in other investigations; the default scan can group the same target across investigations and dead-end distinct profile-owned leads as duplicates. An isolated database environment still points this entire tool at canonical state.
- Correction: make database/profile resolution a backend invariant across fill, scan, export, apply, verify, and stats; bind exported batches/decision validation to the selected profile and database. Default to the pinned profile; make truly all-profile operations explicit. Merely adding `--profile-id` to scan examples does not repair fill/apply.
- Verification: fixture with the same target and similar titles in two profiles and a missing-target row in each; a scoped fill/review/apply must touch only one profile and never another database. Reject foreign IDs and mismatched group hashes in decision files.

### [P2] Dedup iteration skips the next unprocessed groups

ID: `dedup-leads:workflow:shrinking-offset-pagination`

- Evidence: `.codex/skills/dedup-leads/SKILL.md:155` / Claude `:156` says to repeat with **increased offsets** after applying the previous wave.
- Verified implementation: `tools/lead_dedup.py:372`–`:377` removes already-reviewed hashes before returning the current group list; `:561`–`:565` rebuilds that reduced list and then applies the requested offset.
- Failure: with 90 original groups, the first 60 are processed; the next wave beginning at offset 60 finds nothing among the remaining 30. With larger queues it skips a block rather than completing coverage. Idempotency makes this offset recipe wrong, not safe.
- Correction: reset per-wave offsets to 0/20/40 against the remaining queue, or create one immutable batch manifest and slice it once. Report collected groups versus the manifest, including worker failures.
- Verification: at least 90 synthetic groups and two waves; prove every original group is reviewed exactly once and the remaining count is zero.

### [P2] Triage treats distinct research questions about one target as duplicates

ID: `triage-leads:policy:target-depth-is-not-duplication`

- Evidence: `.codex/skills/triage-leads/SKILL.md:232` / Claude `:231` requires dead-ending any same-target lead with an existing open/in-progress lead at the same or higher depth. No same-question/source-scope condition is present. `tools/triage_policy.py:175`–`:190` implements that exact target/depth test, confirming this is not just a shorthand example.
- Contradictory local guidance: `.codex/skills/dedup-leads/SKILL.md:73`–`:78` correctly requires the same investigation angle to merge and explicitly keeps distinct financial, registry, and legal angles.
- Failure: an open standard-depth corporate-registration lead causes a new standard-depth court-case lead about that entity to be dead-ended despite different evidence and question. This is a verified example of an overrestrictive heuristic that suppresses useful model judgment.
- Correction: make target/depth a candidate-overlap signal; require demonstrated question/scope coverage to close a lead, with unique evidence/questions preserved on a keeper. Consolidate that policy in one backend rather than maintaining conflicting tables in two skills.
- Verification: same-target/different-angle pair survives triage; same-target/same-question pair can be closed with a keeper relation and rationale. Include conflicting depth tiers to show that depth alone is not decisive.

### [P2] Dispatch reports global canonical counts as the current investigation queue

ID: `dispatch:context:global-queue-report`

- Evidence: `.codex/skills/dispatch/SKILL.md:22` and `:79` hardcode `investigation.db`; all lead/finding/connection counts and scheduler recommendations at `:25`–`:53` and `:82`–`:105` omit profile filters. Claude counterparts are one line higher. Later top-lead queries at `:192`–`:193` use the profile-aware tracker.
- Failure: a small profile can show thousands of another investigation’s pending/high-priority leads, while the “top leads” and analysis view use different scope. A test/staged environment silently sees canonical counts. The resulting launch recommendations and stalled/healthy assessment can be wrong.
- Correction: replace the two improvised Python blocks with a compact structured, read-only queue-report command honoring pinned profile/database; explicitly label any global totals for shared infrastructure/entities. This also removes roughly 90 lines of repeated SQL from the skill.
- Verification: report two distinct profiles from the same fixture and an alternate database; scoped counts must differ predictably while deliberately shared metrics remain labeled.
- Caution for the fix: do not blindly substitute `dispatcher.py status/plan` while retaining the strict “does not modify any data” promise. Those commands reap/refresh run health and ensure tables (`scripts/dispatcher.py:2931`–`:2935` for plan); use a read-only view or describe maintenance effects honestly.

### [P2] Initializing a new profile does not replace an inherited task pin before seeding

ID: `init-investigation:context:seed-uses-old-pin`

- Evidence: `.codex/skills/init-investigation/SKILL.md:102` sets the interactive active profile and `:108`–`:110` immediately seeds without setting `ITHILDIN_PROFILE` to the new slug. Claude `:103` and `:109`–`:111` follow the same sequence.
- Verified implementation: `tools/investigation_context.py:258`–`:262` gives an inherited `ITHILDIN_PROFILE` precedence over the interactive database setting. `set_active_profile` at `:325`–`:340` only updates that setting. `tools/lead_tracker.py:3085` loads the effective pinned profile for thread seeding.
- Failure: in a normally pinned investigation task, creating a new investigation changes the shared default but seeds the old investigation; the final “created/seeding complete” output does not mean the new profile was initialized.
- Correction: resolve the new profile once and explicitly use that pin for every seed/add/verify command. Change the shared interactive default only if requested or inherent in the requested initialization mode; preserve the database path.
- Verification: begin with `ITHILDIN_PROFILE=old`, create a new profile in a fixture, and verify only the new profile is seeded without altering unrelated state.

### [P2] The Claude initialization variant still documents a removed CLI command

ID: `init-investigation:cli:claude-top-level-seed`

- Evidence: `.claude/skills/init-investigation/SKILL.md:109` calls `uv run python tools/lead_tracker.py seed`; the Codex mirror at `:108` already correctly uses `thread seed`.
- Verified implementation: `tools/lead_tracker.py:2689`–`:2701` defines seed only under the `thread` subparser; the top-level parser has no seed command. This is genuine behavioral mirror drift, unlike `$`/`/` syntax or harness-name adaptations.
- Failure: Claude bootstrapping fails to create its investigation threads at this required step.
- Correction: port the exact existing Codex command correction to Claude.
- Verification: parser/`--help` validation for `thread seed`, plus paired command-parity check that normalizes only expected runtime differences.

## Additional backend concern worth including if report space permits

`dedup-leads` promises consolidation of unique information as keeper notes (`.codex/skills/dedup-leads/SKILL.md:69`). `tools/lead_dedup.py:734`–`:747` copies only the old title and first 200 description characters; it does not copy the old lead notes or evidence links. The source rows remain recoverable, so this is not deletion, but the promised consolidated context is incomplete and relevant details after character 200 or in notes disappear from ordinary keeper-only views. Prefer structured provenance links plus full reviewed unique details; test a consolidated lead with an essential note and a description longer than 200 characters. Suggested P2, but subordinate to the database-isolation defects.

## Optional improvements, not verified defects

- **Replace rote scheduling constants with adjustable defaults and inspectable rationale.** Triage has many count-based rules (`:101`–`:114`, `:231`, `:363`–`:368`) and dispatch hardcodes four analysis thresholds (`:140`–`:143`, `:218`). The shared contract already states counts measure work, not truth (`docs/RESEARCH_WORKFLOW_CONTRACT.md:123`). Preserve useful budget defaults, but make evidence coverage, marginal value, question novelty, and user priority legitimate overrides. Current count-based behavior should be evaluated on labeled cases before broad changes.
- **Delegation should scale with actual work.** Dedup advertises `--agents N` (`:14`) but repeatedly mandates exactly three workers (`:44`, `:54`, fixed batch/apply examples). Make three a default maximum constrained by independent groups and tool availability; a one-group request should not require three workers. The stable batch manifest and parent-owned apply are more important than worker count.
- **Do not convert every “review” skill into an editor.** `audit-skills` appropriately defaults to read-only and recognizes explicit fixes/later approval (`:14`–`:18`). `review-methodology` is intentionally proposal-oriented (`:8`, `:165`, `:181`), whereas `fix-papercuts` says to implement bounded fixes (`:8`, `:62`–`:81`). Add an explicit “existing user authorization carries forward; fix wording invokes fix mode” rule to methodology review if desired, rather than deleting its meaningful review/apply distinction. Higher-priority session authorization already overrides blanket skill wording; no extra approval should be inferred here.
- **Make exhaustive review versus a sample explicit.** Methodology review promises all open observations (`:12`) but retrieves only the newest 100 of each state (`:31`, `:34`); the tracker applies a literal LIMIT (`tools/methodology_tracker.py:100`–`:109`). It gets overall counts first, which gives an attentive model a way to detect truncation. A structured count/has-more/next-page result would reduce ambiguity, and `--category` should feed every relevant query. Do not call a 100-row sample a complete review.
- **Use provisional grounded seeds instead of a training-memory quota.** Init asks for 10–30 key people from training knowledge (`:49`–`:52`) and those entries trigger downstream priority escalation. Better: only enough names to establish a first useful wave, with source/provisional status. The main issue is certainty and routing impact, not the presence of a number itself.
- **Give the CLI stronger contracts before adding more prompt warnings.** Stable JSON decisions, schema validation, explicit scope, useful exit codes, expected-state writes, and machine-readable counts should live in Python. The model should own novelty/identity/evidence judgment, not hand-author mutable SQL.

## Strengths to preserve

- `orchestrate-investigation` is short (124 Codex lines), clearly owns launch/review/import, and intentionally centralizes lifecycle actions in the dispatcher. The backend creates unique staging paths (`scripts/dispatcher.py:597`–`:601`), tells staged workers not to mutate canonical state (`:675`–`:679`), and binds review/import to artifact contents (`:2724`). These are useful engineering boundaries, not obsolete micromanagement.
- Dedup uses explicit structured decisions, preserves leads by dead-ending rather than deleting them, includes rationale, asks for dry-run before apply, and defaults to keep-all under uncertainty (`SKILL.md:78`, `:89`–`:117`, `:125`–`:162`). Preserve this conservative identity/angle judgment while repairing the backend scope.
- `fix-papercuts` already has narrow scope, concrete stop conditions, outcome taxonomy, proportionate verification, and owner-controlled local edits. It distinguishes insufficient evidence from obsolete/nonissue and will not call workarounds fixes (`:41`–`:50`, `:66`–`:81`). No verified defect found in this package.
- `audit-skills` demonstrates progressive disclosure, a reusable deterministic helper, independent semantic review, exact evidence requirements, and forward tests with the diagnosis withheld (`:10`, `:55`–`:76`, `:106`–`:114`, `:170`–`:178`). No verified defect found in this package.

## Dismissed suspicions / no-action notes

- Slash-prefixed recommended_skill values in Codex triage are correct database protocol values, not stale invocation syntax: the skill explicitly explains the distinction (`:189`), and `tools/triage_policy.py:25`–`:53` consumes slash-prefixed IDs.
- Claude/Codex orchestrator actor names, runtime headings, and child-tool syntax are intentional. The raw diff alone would be a false positive.
- The Claude-only worker backend is an explicit v1 implementation constraint, not proof that Codex is artificially forbidden from using its own subagents elsewhere. Keep the dispatcher adapter boundary; changing backends is a separate capability project.
- The orchestrator review/approve examples use the agent as reviewer; “approved output” does not itself force a new human confirmation. The artifact review boundary is valuable and should remain.
- The research workflow contract already supplies pinned context, applicability, per-worker sources, artifact collection, and incomplete-handoff handling. Do not copy that long policy into every skill merely because each SKILL.md omits the same prose. The verified problems above are implementations that violate the contract, not mere omissions.
- Init's `--dry-run` is a skill-level argument; absence of a matching standalone initialization executable is not enough to call the argument broken. No dry-run mutation claim is made without a behavioral test.
- Two missing Claude counterparts are scope observations, not automatic defects; no requirement was found that every Codex-only utility must exist in both harnesses.
