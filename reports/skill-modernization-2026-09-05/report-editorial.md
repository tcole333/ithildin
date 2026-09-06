# Editorial and analysis skill audit

Reviewed 2026-09-05/06. Scope: `write-article`, `review-article`, `curate-dossier`, `review-dossiers`, `discover-investigations`, `discover-frameworks`, and `status-report`. Read the complete Codex skills and all differences against their Claude counterparts; `discover-investigations` has no Claude counterpart in the supplied snapshot. Other paired differences are expected invocation/frontmatter changes, including the intentional `spawn_agent` adaptation in `review-dossiers`. Read the review rubric, Git workflow, research workflow contract, candidate rubric, and targeted implementations. Repository/DB were not changed; no production skill or research command was run. One pure JavaScript helper check used an injected fake Git implementation (no real Git reads/writes).

## Verified defects

### E1 — P2: Article coverage checks select the previous commit, excluding a newly written draft

**Skill locations:** `.codex/skills/write-article/SKILL.md:328-333`; `.codex/skills/review-article/SKILL.md:141-145`. Claude counterpart locations are +1 line. Both prescribe `--base-ref HEAD~1 --head-ref HEAD` while reviewing an article the current task just wrote or revised. The drafting path writes at `.codex/skills/write-article/SKILL.md:269-280`, and nothing guarantees a commit before these verification commands. The final revision pass does not rerun coverage either (`:364-372`).

**Implementation proof:** `web/scripts/changed-content-files.mjs:43-56` uses only `git diff HEAD~1...HEAD` for those arguments. It includes untracked files only in the WORKTREE/no-base branches (`:57-94`). `web/scripts/report-support-coverage.mjs:76-81` skips every article absent from the selected set; `:133-141` emits a successful JSON report even with zero files. A new untracked article can therefore receive an unrelated or empty metrics report. Conversely, the dossier skill already uses the appropriate working-tree mode (`.codex/skills/curate-dossier/SKILL.md:252-257`).

**Small correction:** Use explicit current-target coverage, or at minimum `--base-ref HEAD --head-ref WORKTREE` for uncommitted drafting/revision. Assert the selected article appears in the metrics and rerun after changes affecting claims/citations. Keep commit-range mode only for a requested committed-diff review.

**Verification performed:** Imported `collectChangedContentFiles` in Node with an injected Git function simulating one untracked `content/articles/new-draft.mdx` and no committed diff. The instructed mode returned `[]`; WORKTREE returned that article. Existing helper already has the required behavior, so this is primarily a skill command fix. Forward test: one untracked new article, one tracked uncommitted revision, and a standalone review of an unchanged article must all report the requested file.

### E2 — P2: Article evidence gates are not actually implemented by the prescribed audit command

**Skill locations:** `.codex/skills/write-article/SKILL.md:76-90`; `.codex/skills/review-article/SKILL.md:77-88`. Writer gates on missing quote percentage, any cross-check mismatch, and unresolved duplicate clusters; reviewer describes article-referenced findings and duplicates. Both invoke only `scripts/evidence_audit.py report`.

**Implementation proof:** `scripts/evidence_audit.py:25-26` fixes the investigation DB to the root checkout and document DB to another local project. `:54-64` opens these constants, so the pinned `ITHILDIN_DB_PATH` is ignored. `:378-397` reads all findings/evidence without profile or article filtering. `:420-431` counts EFTA reference overlap across three findings; it does not identify unresolved semantic duplicate clusters. Most importantly, `:483-492` merely checks whether a documents DB exists and says to run `cross-check`; it never runs mismatch verification. The parser (`:500-518`) has no profile, article, finding-ID, or DB arguments.

**Failure path:** Healthy article evidence is blocked by unrelated backlog in another profile, while the claimed cross-check gate has not been executed. A staged/test review can also audit an entirely different DB from the article's selected context. These are reliability issues in the gate/tool contract, not arguments for dropping evidence verification.

**Small correction:** Give the evidence audit a pinned DB and explicit finding/article scope, output categorized machine-readable results, and distinguish overlap candidates from adjudicated duplicates. Invoke the actual source-text check on cited primary documents and report unsupported/unavailable checks explicitly. The article blocker should concern its load-bearing evidence; platform backlog is separate maintenance information.

**Forward test:** Two-profile fixture with bad unrelated quotes, a selected clean article, a selected mismatched quote, and multiple legitimate findings from the same document. Only problems affecting the selected evidence should block; changing `ITHILDIN_DB_PATH` must change the audited fixture; lack of corpus access must never count as a passed cross-check.

### E3 — P2: Dossier batch reviewers are sent an automated-results file that batch mode never produces

**Skill locations:** `.codex/skills/review-dossiers/SKILL.md:36-39` writes `$WORKDIR/automated-results.json`; the mandatory child prompt at `:130-134` tells each reviewer to read `$WORKDIR/automated-<slug>.json`. Claude locations are +1. No splitting/materialization step occurs between them. The current-content hash is required at `:72` and in the output schema `:105-109`, so this is not merely a cosmetic path issue.

**Implementation proof:** `scripts/review_dossier_checks.py:945-958` collects records into one array and writes only `args.output`. It does not emit per-slug artifacts. The per-slug file belongs to the separate single-target `check` command (`:933-940`).

**Failure path:** A normal batch subagent receives a nonexistent dependency and cannot obtain the required Phase 1 hash/check report as instructed. A capable agent may recover by searching for the aggregate file, but the documented handoff predictably requires repair.

**Small correction:** Either materialize one immutable per-slug packet from the batch array before dispatch, or point each worker to the array with an explicit slug selector. Include the actual output schema (especially hash and verdict) in the bounded worker mandate. Do not rerun the checker simply to manufacture missing files unless the underlying content changed.

**Forward test:** Two-dossier fixture batch; build the documented mandates; verify every referenced path exists and the selected record's slug/hash equals the reviewed file. Parent must collect two results and reject missing/stale hashes.

### E4 — P2: Status report labels do not match the queries that populate them

**Skill locations:** `.codex/skills/status-report/SKILL.md:16-20` versus `:35-45`; Claude +1. It queries `--status open --limit 5` to show leads needing triage, asks for a “Last 7 Days” section after an undated `list --limit 10`, and requests “all” open critical/high and in-progress leads after fetching at most ten per category.

**Implementation proof:** `tools/lead_tracker.py:1870-1914` applies status equality, orders priority first then creation date, and applies `LIMIT`. Thus the open-lead sample excludes `pending_triage` and is not even the five newest globally. `tools/findings_tracker.py:1156-1192` applies no age filter; it simply returns the newest N. The findings CLI exposes no `--since` in its `list` parser (`:3469-3480`). Project lifecycle explicitly assigns newly generated untriaged work `pending_triage`, and agent triage can promote it; “haven't been reviewed by a human” is an obsolete distinction.

**Small correction:** Select `pending_triage` for the queue, label bounded lists “top/latest N” with remaining totals, and either add/apply a timestamp filter or rename the findings section “Latest findings.” Avoid inventing human review state where none is queried. A compact status exporter could encode the full summary as one tested command.

**Forward test:** Fixture with open and pending-triage leads, more than ten high-priority leads, and newest finding older than seven days. Report must surface the actual triage queue, disclose truncation, and not call the old finding a last-seven-days result.

### E5 — P2: Discovery's frozen snapshot can come from a different database than its analysis run and derived exports

**Skill location:** `.codex/skills/discover-investigations/SKILL.md:59-78` pins `export_snapshot.py --db investigation.db`, then invokes shared derived exports that use the configured runtime DB. This conflicts with the pinned-database contract for a staged/test or explicitly selected alternate database (`docs/RESEARCH_WORKFLOW_CONTRACT.md:18-21`).

**Implementation proof:** `.codex/skills/discover-investigations/scripts/export_snapshot.py:53-60` defaults to a literal relative DB path, `:235-243` opens the supplied argument, and `:191-192` correctly makes that chosen DB read-only. In contrast, `tools/analysis_export.py:34-37` imports the tracker DB accessor and `tools/lead_tracker.py:34` honors `ITHILDIN_DB_PATH`. Setting the environment alone cannot fix the skill's explicit `--db investigation.db` override.

**Failure path:** When run with a staged DB, its run audit/derived views describe the staged data while primary packets silently describe the live root DB. The resulting “frozen scope” is internally inconsistent. Default interactive root-DB runs are unaffected.

**Small correction:** Resolve one absolute DB path at setup, preserve an existing override, and pass it to the snapshot exporter. Include and compare DB identity in every export packet. An environment-aware default can remove the duplicate context resolver.

**Forward test:** Two tiny fixture DBs with disjoint sentinel finding IDs; set `ITHILDIN_DB_PATH` to one and run only the exporter/derived fixture commands. Every packet and run snapshot must use that fixture. No production mutation is needed.

## Optional modernization opportunities (not verified model-quality defects)

1. **Separate a compact procedure from detailed craft references.** `write-article` is 436 lines and `review-article` 399; much is repeated style/citation/report scaffolding. Examples: writer `:212-227`, `:241-247`, `:410-436`; reviewer `:199-226`, `:287-298`, `:337-388`. Their literal budgets (30–50 cited findings, 3–5 principals, 8–12 supporting characters, 7–12 named-character ceiling), required surprise hook, fixed confidence-framing paragraph, and prohibition of particular sentence structures can optimize compliance rather than reader understanding. Preserve evidence rules and product syntax, make craft counts defaults with reasons, and link one craft rubric for a writer/editor who needs it. The principals/supporting counts also sit awkwardly beside the total character ceiling. Test representative article rewrites blindly for factual support, readability, editorial time, and token/tool cost before deleting guidance.

2. **Fix deterministically before semantic dossier review.** Current `review-dossiers :137-151` persists a semantic review/receipt, then `:184-202` applies optional deterministic changes, invalidates that receipt, and repeats semantic review. For a user-requested `--fix` pass, applying bounded deterministic cross-link/title fixes first, then rerunning structural checks and conducting one semantic review of final bytes avoids needless duplicate review. Keep exact-content receipts; weakening receipt invalidation is the wrong optimization. Check behavior with a dossier needing crosslinks and a true claim-support defect.

3. **Give dossier reviewers selective evidence packets rather than a blanket full-JSON load.** `review-dossiers :233` says 50–200 KB JSONs should be read in full, while `:236` already supports selective evidence reading. `curate-dossier :36-46` likewise loads all dossier fields. A helper could expose current prose, cited findings, necessary relationships/identifiers, hash, and locator paths to underlying records, with additional context available on demand. Maintain review of every material assertion; reducing redundant machine metadata is different from sampling factual claims. Benchmark both a small dossier and a large dossier containing many uncited findings.

4. **Centralize command/source discovery instead of maintaining embedded source menus.** `write-article :106-146` reproduces source commands, inactive Aleph/GDELT routes, and case-specific DS10/NYC routes. The higher-priority research contract already says instantiate only applicable sources and use the catalog, so these are not mandatory universal searches. Still, replacing the menu with a concise task/source packet builder and links to relevant module docs reduces drift, context, and contradictory instructions. Similarly, absolute `/Users/travcole/.../web` paths at writer `:311`, `:331`, `:371`, reviewer `:143`, and curator `:255` should derive from the actual worktree root, especially under `docs/GIT_WORKFLOW.md`'s worktree workflow.

5. **Make framework detector discovery semantics explicit and batch its repeated work.** `discover-frameworks :28` advertises `--update-detector` as adding detection rules, but `:218-226` only verifies dynamic loading. The implementation actually loads both adopted and evaluated lenses automatically (`tools/model_detector.py:114-154`), including on runs without that flag. Document the real behavior or rename the option to verification; avoid gratuitous code edits. Also `:68-75` calls a deterministic one-finding detector 30–50 times. A tested batch read-only command could return unmatched IDs and short excerpts once. Treat keyword “gaps” as a candidate signal, not proof that existing theories fail: keyword absence is not semantic absence. Consider replacing “three grounding findings” and review-mode promotion by article count (`:278-279`) with evidence independence, falsification and measured usefulness—counts are useful triage signals, not validation.

6. **Keep commissioning gates, but evaluate the score mechanics.** `discover-investigations` is notably more modern: clear trigger/non-goals, linked rubric, frozen scope, independent read-only discovery, final evidence audit, truthful coverage and no forced recommendation. Its fixed 5–15 raw candidates per track (`:132`), at-least-three anchors, two independent numerical scores with 10/5-point adjudication thresholds (`:188`), and multi-floor 100-point rubric could be calibrated against historical commissioned/rejected stories rather than treated as inherently reliable. Use “up to” candidate counts for sparse profile runs. The intent—bounded independent scrutiny and evidence gates—should remain. This is an evaluation proposal, not evidence that the current scoring is harmful.

## Strengths to preserve

- `review-dossiers :54-76, :123-151, :202, :229` explicitly separates structural PASS from semantic support, binds review to exact content, requires the actual reviewer judgment, collects reviewer output, serializes receipt persistence, and invalidates stale reviews. These are concrete integrity controls, not obsolete handholding.
- `review-article :232-240, :261-271` tests causation, implied intent, planted/provenance-opaque sources, attribution, alternatives, and estimative language. Do not simplify these into a vague “fact check.”
- `curate-dossier :127-134` explicitly warns against confusing research volume with importance and delegates narrative judgment. Its case/type adaptation `:105-113` is sensible flexibility.
- `discover-frameworks :8, :117-119, :134, :282-288` requires falsification, boundary conditions, overfit risks, and evidence grounding. These are necessary constraints for theory-building in an investigative setting.
- `discover-investigations :25-32, :81, :103-118, :122-138, :163-184` has clear mutation boundaries, modest context packets, truthful index-versus-semantic coverage, independent tracks, and primary-source/contradiction checks. Its separation of discovery from launching operational investigations is sensible scope control.
- There is little evidence in these seven packages of gratuitous user approval inside ordinary editing/review loops. Most “blocking” language concerns publication/evidence readiness, not asking permission for reversible drafting.

## Dismissed or qualified suspicions

- **Missing repeated profile bootstrap instructions:** not a defect alone. `docs/RESEARCH_WORKFLOW_CONTRACT.md` already requires pinned profile/database and explicit inheritance; repeating it in every skill would add drift. E2/E5 are different because their actual tool paths ignore or override that context.
- **All three writer research tracks must always hit every U.S. source:** shared applicability policy explicitly makes worker menus conditional. Reduce duplication, but do not report unconditional source-count noncompliance from these examples alone.
- **Absence treated as evidence:** writer `:187, :245` is overbroad shorthand, but the binding research contract already restricts negative findings to bounded source scope and distinguishes collection gaps. Prefer linking that rule; do not claim the whole workflow authorizes speculation.
- **`source_report.py report` is stale:** false; `tools/source_report.py:1061` implements it and `:1097-1099` retains the bare invocation alias.
- **Claude/Codex text inequality in review-dossiers:** intentional runtime adaptation, not semantic drift.
- **All styles/word budgets are inherently bad for modern models:** unproven. The user may want a house style; evidence and product-specific formatting are useful. Test loosening brittle counts and repetitive phrasing prohibitions rather than stripping all editorial direction.
- **Extra commissioning confirmation is automatically an authorization defect:** not established. Discovery's declared output is recommendations only; promotion is a separate explicit scope. Existing user authorization takes precedence over repeat confirmation per the parent session instructions. Keep the boundary, avoid manufacturing new approval requirements.

## Suggested order

First fix E1–E5 and validate with bounded fixtures. Then pilot compact writer/reviewer instructions and deterministic-first dossier fixes against representative existing tasks. Use model/practitioner sources from the parent's research to select evaluation criteria; this read-only audit does not assert newer-model gains without measurement.
