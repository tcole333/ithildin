# Project skill modernization review

Reviewed 5 September 2026 (America/New_York); research completed 6 September UTC.

## Assessment

The project would benefit from modernization. The main opportunity is to make evidence requirements precise, put mechanical correctness in tools, and give models more discretion over investigative strategy. A wholesale rewrite or indiscriminate reduction in instruction length would discard valuable domain knowledge.

Three problems interact:

1. Some instructions encode rigid research heuristics or prohibit useful actions, while other documents already provide more nuanced guidance.
2. Some copyable commands do not implement the behavior the prose promises. Stronger instruction following cannot repair a wrong database path, wrong filing selection, or misleading result scope.
3. Multiple skill copies and incomplete validators let outdated instructions remain available after repository improvements.

Modern model guidance supports reviewing these issues, but this audit does not establish that a particular prompt rewrite improves model performance. That requires outcome-based evaluation on the actual model and harness.

## Scope and checks

- All **36 project skills / 69 variants**: 36 Codex, 33 Claude. Six independent reviewers covered non-overlapping families and shared architecture; a seventh researched official Claude guidance. The parent researched OpenAI and practitioner guidance, reviewed the reports, and independently checked the prioritized findings below.
- Structural snapshot plus repository validator: **0 errors, 51 warnings, 5 informational results**. These are tool outputs, not a clean semantic bill of health. Several warnings are false positives or intentional runtime differences.
- Existing targeted tests: **26 passed** across `test_validate_skills.py`, `test_analysis_skill_commands.py`, and `test_triage_leads_skill.py`.
- Safe reproductions: CLI validator false passes, native Claude metadata rejection, and article selection using an injected Git function. Family reviewers also reproduced three financial/registry example failures in memory.
- All 36 repository Codex bodies compared with installed personal copies: **14 differ**, and both locations are present in this session's skill catalog. Selection precedence was not tested.
- No skill/tool source files, global installed skills, branches, or existing reports were changed. No live investigation workflow, source acquisition, or publication was run. Required friction observations were recorded: startup shell issue #2775 and validator false passes #2784.
- Audit artifacts live in this temporary workdir. The current branch and its two pre-existing untracked report directories were preserved.

## Current guidance and its application

### Model-specific guidance

**OpenAI GPT-6 Astra.** The current official guide explicitly recommends auditing skills and instruction files because stronger instruction following increases sensitivity to ambiguous or conflicting rules. It addresses unnecessary approval pauses, calibrating delegation, and excessive testing on small tasks. Application: resolve contradictory instructions and put model-level tuning in the harness rather than repeating it through every domain skill. This does not justify dropping evidence checks. [Using GPT-6 Astra](https://developers.openai.com/api/docs/guides/latest-model).

**Claude Fable 5.1.** Anthropic's current generally available generation is Fable 5.1; Mythos 5.1 is restricted to trusted access programs. The 5.1 guidance says long tasks often require little methodological direction and discusses finishing already-authorized work, scoped changes/testing, independent tool batching, and useful parent work during asynchronous delegation. Use Fable 5.1 for a generally accessible comparison, recording actual version and effort. [September announcement](https://www.anthropic.com/claude-fable-and-mythos-5-1), [Fable 5.1 prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1).

**Do not transfer every old prompting tip blindly.** Anthropic's general guide attributes aggressive tool-language overtriggering to particular earlier Opus versions and explicitly asks readers to re-evaluate techniques for each model. Treat “delete every MUST” as an untested prescription. Preserve consequential requirements; test removal of redundant emphasis. [Claude prompting guidance](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices).

### Skills, tools, and evaluation

| Source | Guidance relevant to this project | Application |
|---|---|---|
| [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) — current living docs | Focused jobs, explicit inputs/outputs, concise trigger descriptions, progressive disclosure; current repo discovery uses `.agents/skills`, supports symlinks, and does not merge same-name skills. | Remove duplicate distribution ambiguity; keep small runtime adapters and a canonical body. |
| [Anthropic: Skill authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — living docs | Assume model competence; match procedural freedom to task fragility; use scripts for fragile deterministic operations; start from representative failures. | Flexible source selection and interpretation; typed tools for database writes, evidence validation, and repeatable transformations. |
| [Claude Code: Skills](https://code.claude.com/docs/en/skills) — living docs | Runtime-specific metadata, concise bodies, references; `user-invocable` is documented, not `user_invocable`. `allowed-tools` grants permission rather than restricting availability. | Validate each runtime's schema accurately; use invocation/tool controls only when warranted. |
| [Anthropic: Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — 29 September 2025 | Avoid both brittle prompt decision trees and vague underspecified goals. | Keep the information needed to choose and verify a strategy; remove unnecessary scripting of the strategy itself. |
| [Anthropic: Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — 11 September 2025 | Distinct task-oriented tools, bounded useful responses, actionable errors, empirical tool evaluation. No universally best response format. | Improve current CLI discovery, scope, pagination, and failure semantics before adding another integration layer. |
| [OpenAI: Testing skills with evals](https://developers.openai.com/blog/eval-skills) — 22 January 2026 | Grade outcomes, relevant process, style, and efficiency through captured runs/artifacts. | Supplement syntax tests with task and trigger scenarios. |
| [Anthropic: Agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — 9 January 2026 | Evaluate resulting state, account for variability, combine deterministic checks and judgment. | Use isolated investigation fixtures and repeated model runs, allowing different valid approaches. |

Practitioner evidence points in the same direction. Simon Willison's [October 2025 skills article](https://simonwillison.net/2025/Oct/16/claude-skills/) describes the usefulness of small Markdown packages and discoverable CLI help. His [March 2026 account of using new tools](https://simonwillison.net/2026/Mar/9/not-so-boring/) reports success teaching capable agents through `--help` and examples. His [subagent chapter](https://simonwillison.net/guides/agentic-engineering-patterns/subagents/) emphasizes independent work and conserving the parent context, with caution against excessive specialist decomposition. These are informed practitioner observations, not controlled measurements of this repository.

## Prioritized verified findings

Severity describes the repository failure path, not the importance of a stylistic preference. P1 requires early correction; P2 affects a common path or creates substantial rework. Recommendations below are proposed changes, not completed fixes.

### F01 — P1: Triage can write to the wrong database

The skill selects leads through the environment-aware tracker, then promotes/dead-ends them using literal `sqlite3.connect('investigation.db')`. Updates match only numeric ID, without profile or expected-state checks. A staged database can therefore supply ID 42 while the snippet modifies canonical ID 42. Correctly setting `ITHILDIN_DB_PATH` does not affect the snippet. [Triage mutation](/Users/travcole/projects/osint-research/.codex/skills/triage-leads/SKILL.md:259), [tracker routing](/Users/travcole/projects/osint-research/tools/lead_tracker.py:34).

**Correction:** a typed tracker apply operation accepting a decisions file, binding database/profile, and rejecting changed row state. Remove inline mutation SQL. **Verify:** two databases with colliding IDs, two profiles, and a status change between export and apply.

### F02 — P1: Deduplication's backend bypasses scope

`lead_dedup.py` hardcodes the canonical database. The skill advertises an investigation selector, but `fill-targets` updates missing targets across profiles and the examples omit profile selection in scan/export. Scope must be enforced through fill, export, and apply, not merely added to one example. [Skill entry](/Users/travcole/projects/osint-research/.codex/skills/dedup-leads/SKILL.md:12), [backend database](/Users/travcole/projects/osint-research/tools/lead_dedup.py:24), [fill operation](/Users/travcole/projects/osint-research/tools/lead_dedup.py:215).

**Correction:** canonical context resolution and validated batch/decision ownership in the backend. **Verify:** same-name targets across two profiles; attempts to apply foreign IDs must fail without changing them.

Related read-only context bypasses occur in deep-investigate preflight, analyze-case, analyze-filing, dispatch, and other family examples. Fix the shared API path and replace snippets; repeating a pinning warning does not correct literal paths. [Case example](/Users/travcole/projects/osint-research/.codex/skills/analyze-case/SKILL.md:220), [filing example](/Users/travcole/projects/osint-research/.codex/skills/analyze-filing/SKILL.md:214). Shared entities and deliberately global infrastructure metrics should retain their intended scope.

### F03 — P2: Triage discards distinct questions about the same target

The stop rule treats an existing same-target lead at equal/higher depth as sufficient to dead-end a new lead. The backend implements it without comparing the actual question. That conflicts with dedup's correct rule preserving different financial, registry, and legal angles. [Triage rule](/Users/travcole/projects/osint-research/.codex/skills/triage-leads/SKILL.md:232), [backend](/Users/travcole/projects/osint-research/tools/triage_policy.py:175), [dedup distinction](/Users/travcole/projects/osint-research/.codex/skills/dedup-leads/SKILL.md:73).

**Correction:** use target/depth to suggest overlap, then require demonstrated question/scope coverage before closure. **Verify:** same-target/different-angle survives; a true duplicate closes with a keeper relation and rationale.

### F04 — P2: Installed duplicates can revive obsolete workflows

All 36 project Codex skills also exist in the personal installation, and 14 bodies differ. Stale personal versions include historical-log-only search skipping and older unscoped triage examples. Both locations appear in this session. The sync script still describes copying to personal `$CODEX_HOME/skills` as the required loading route. [Sync script](/Users/travcole/projects/osint-research/scripts/sync_codex_skills.sh:2), [comparison artifact](installed-diffs.json).

**Correction:** establish one version-controlled content source and expose project skills once through current runtime discovery. Use symlinks or generated adapters with normalized hashes where appropriate. Preserve personal edits and unrelated personal skills. **Verify:** clean-session effective paths, benign invocation, and migration fixtures. Do not infer that the current app cannot load `.codex` skills: it demonstrably can in this session.

### F05 — P2: Metadata and CLI validation give false assurance

The validator rejects documented Claude keys such as `user-invocable`, `disable-model-invocation`, and `context`, while accepting the project's underscore spelling. Existing true-valued metadata does not prove skills currently fail to appear, since true is the documented default. Separately, CLI inspection ignores help return codes and can return no issues for an invalid subcommand or failed help with an invalid flag. Both behaviors were reproduced. [Schema](/Users/travcole/projects/osint-research/scripts/validate_skills.py:48), [help handling](/Users/travcole/projects/osint-research/scripts/validate_skills.py:326), [skipped validation](/Users/travcole/projects/osint-research/scripts/validate_skills.py:470), [reproduction](reproduce-architecture-validator.py).

**Correction:** runtime-aware schemas, parser-backed checks, and explicit verified/failed/unverified outcomes. **Verify:** valid native metadata plus misspellings; valid/invalid subcommands, arguments, help failures, and intentional templates. Keep generic Agent Skills validation distinct from host extensions.

### F06 — P2: A full-text reading example returns a 2,000-character preview

The corpus worker is told to read full documents but supplied `ingest_kabasshouse.py doc EFTA_ID`. Without `--full` or `--output`, the renderer truncates long text. [Skill command](/Users/travcole/projects/osint-research/.codex/skills/deep-investigate/SKILL.md:187), [renderer](/Users/travcole/projects/osint-research/tools/ingest_kabasshouse.py:490), [defaults](/Users/travcole/projects/osint-research/tools/ingest_kabasshouse.py:649).

**Correction:** save the complete artifact and retrieve sufficient surrounding sections; distinguish retrieval completeness from actual reading coverage. **Verify:** a decisive qualification after character 2,000 is available and accounted for. This does not require dumping every long document into context.

### F07 — P2: Analysis commands lose the identity or scope of the evidence

`analyze-filing` supports historical filings and different forms, but its structured statement commands default to the latest 10-K. The resulting ratios can describe a different accession. [Skill](/Users/travcole/projects/osint-research/.codex/skills/analyze-filing/SKILL.md:149), [tool defaults](/Users/travcole/projects/osint-research/tools/query_edgar.py:1818).

`analyze-contract` labels an aggregate award-detail request as transaction-level payment history. The command fetches award totals, while adjacent timeline output is recipient-level. Neither is a selected award's payment ledger. [Skill](/Users/travcole/projects/osint-research/.codex/skills/analyze-contract/SKILL.md:84), [award handler](/Users/travcole/projects/osint-research/tools/query_usaspending.py:560).

**Correction:** bind every statement to the selected accession; preserve exact award identity and action records for obligation/modification analysis. Reserve payment language for supporting payment evidence. The existing transactions command has no award-ID flag; do not invent one. **Verify:** multiple filings/forms and two awards for one recipient, including pagination and differing dates.

### F08 — P2: Article verification can check the wrong content or an unrelated evidence backlog

Article skills use `HEAD~1...HEAD` for a draft that may be untracked or edited in the working tree. The selection helper excludes that draft in this mode; an injected-Git reproduction confirmed it. [Writer command](/Users/travcole/projects/osint-research/.codex/skills/write-article/SKILL.md:328), [selection implementation](/Users/travcole/projects/osint-research/web/scripts/changed-content-files.mjs:43).

The evidence gate also invokes a global `evidence_audit.py report`, despite making article-specific blocking claims. That tool hardcodes database paths, reads global evidence, and only announces availability of a cross-check rather than running it. [Gate](/Users/travcole/projects/osint-research/.codex/skills/write-article/SKILL.md:76), [audit scope](/Users/travcole/projects/osint-research/scripts/evidence_audit.py:378), [cross-check behavior](/Users/travcole/projects/osint-research/scripts/evidence_audit.py:483).

**Correction:** verify the explicit target and final content version; use WORKTREE mode for uncommitted changes where appropriate and assert target inclusion. Scope evidence checks to the selected database and cited findings, exposing actual missing/unavailable checks. **Verify:** new, modified, and unchanged requested articles; clean selected evidence alongside unrelated bad records. Preserve publication integrity gates.

### F09 — P2: Two batch handoffs do not match their tool behavior

Dedup tells the parent to increase offsets after each wave, while the exporter first removes processed groups. After processing 60 of 90 groups, offset 60 skips the remaining 30. [Instruction](/Users/travcole/projects/osint-research/.codex/skills/dedup-leads/SKILL.md:155), [filter](/Users/travcole/projects/osint-research/tools/lead_dedup.py:372), [slice](/Users/travcole/projects/osint-research/tools/lead_dedup.py:564).

Dossier batch checking writes one array file, but worker prompts reference per-slug files that are never produced. [Batch](/Users/travcole/projects/osint-research/.codex/skills/review-dossiers/SKILL.md:36), [handoff](/Users/travcole/projects/osint-research/.codex/skills/review-dossiers/SKILL.md:134), [writer](/Users/travcole/projects/osint-research/scripts/review_dossier_checks.py:945).

**Correction:** immutable batch manifests or reset offsets over remaining work; generate actual per-worker packets or pass an explicit array selector. **Verify:** every selected group reviewed once; every supplied artifact exists and matches its dossier hash.

## Changes to evaluate, rather than declare proven

### Replace broad restrictions with precise result requirements

- `pursue-lead`, `investigate-person`, and `trace-entity` prohibit reading full document text. Allow the agent to read a complete short document or sufficient sections when needed to resolve identity, context, qualifications, or contradiction. Preserve bounded retrieval and handoff of prolonged specialist work. [Example](/Users/travcole/projects/osint-research/.codex/skills/pursue-lead/SKILL.md:331).
- Research skill openers prohibit theorizing while later asking for hypotheses. The methodology already permits hypotheses that guide search. State that distinction directly: reasoning may guide collection; persisted statements retain the correct evidence and claim type. This is an alignment of existing intent, not abolition of the research/analysis/editorial separation. [Methodology exception](/Users/travcole/projects/osint-research/research/INVESTIGATIVE_METHODOLOGY.md:510).
- Treat three-context novelty rules, fixed growth thresholds, count-based coverage, and top-N finding quotas as documented defaults with calibrated overrides. Two highly diagnostic records can be more useful than three ordinary overlaps. “No screened flags” is more accurate than an unqualified “clean.” [Novelty filter](/Users/travcole/projects/osint-research/.codex/skills/generate-hunches/SKILL.md:126).
- Replace categorical interpretations such as low neighbor density proving that people do not know each other or that a node controls information flow with observed-graph descriptions and hypotheses to test. The shared methodology already requires alternative explanations; align examples with it. [Network interpretation](/Users/travcole/projects/osint-research/.codex/skills/analyze-network/SKILL.md:91).

### Reduce duplicated context selectively

The Codex tree totals 10,084 lines, but bodies are loaded on demand; this is not the initial context cost. Only `deep-investigate` exceeds the rough 500-line authoring guideline: 798 lines, approximately 46.7 KB. Its four inline worker templates repeat report and persistence instructions. Only two Codex packages currently bundle references/scripts; the other skills also use external shared documentation.

Start with `deep-investigate`: retain scope, inputs, source ownership, evidence reconciliation, failure handling, and completion criteria in the body. Move conditional source/worker menus and one report schema into directly linked references. Reuse the existing research contract rather than copying it into another document. Keep a self-contained shorter skill when splitting would cost more navigation than it saves.

Refine trigger descriptions around natural requests and distinct roles: targeted lookup; queued lead; named-person investigation; explicitly orchestrated research; source onboarding; registry integration. Front-load that distinction instead of internal tier labels. Test both positive and near-miss requests before changing activation policies.

### Improve the CLI instead of compensating through prose

The platform already has useful foundations: `public_records_catalog.py`, `public_records_search_plan.py`, property/court routers, `source_report.py`, and `output_util.py`. Extend those capabilities; a new MCP layer or rewritten CLI is not a prerequisite.

A proposed discover/describe facade could expose:

1. A compact offline list of relevant tools by question, jurisdiction, and record type.
2. One operation's input schema, exact examples, output shape, coverage, access requirements, mutation/cost behavior, and owning documentation anchor.
3. Explicit health checks, separate from discovery and cheap `--help`.
4. Consistent success/zero/partial/unavailable/error states, pagination, truncation, actual scope, and a full artifact path.
5. Structured decisions-file inputs for writes, with context and expected-state enforcement.

These are proposed capabilities, not existing command names. Keep domain detail and inspectable artifacts; avoid an opaque command that hides the whole investigation. Consider accession-bound statement batching and compact queue/status exports first, because existing skills repeatedly improvise those operations.

### Calibrate delegation and review

Use independent bounded tasks, clear ownership, and expected artifacts. Worker count should reflect independent work, available tools, and cost. Current deep-investigate already permits fewer than four workers; revise fixed-four examples rather than falsely treating the entire workflow as rigid. Keep parent reconciliation and report collection. Native completion/status signals are preferable to inferring failure from an unchanged file size.

For `review-dossiers --fix`, consider applying deterministic corrections before semantic review, then review final content once. Preserve content-bound receipts and invalidate them when later material changes occur. The audit did not find widespread gratuitous human approval inside ordinary editorial loops; many gates are legitimate evidence/publication boundaries.

## Proposed evaluation and rollout

1. **Repair tool correctness first:** F01–F03 and evidence/artifact scope failures. Use isolated database fixtures, mocked sources, parser tests, and exact-target verification. This can proceed independently of prompt style experiments.
2. **Repair distribution and validation:** establish effective runtime paths, preserve customized personal copies, support current metadata, and make unchecked commands visible. Normalize meaningful Claude/Codex parity rather than requiring raw text equality.
3. **Pilot three workflows:** `pursue-lead`, `deep-investigate`, and `triage-leads`. They cover research discretion, orchestration, and consequential state changes.
4. **Compare three variants:** current skill; compact revised skill; shared project instructions without that skill. Hold data, tools, and task constant. Record exact Codex/Claude model, harness version, effort, and instructions. Repeat runs to distinguish consistent improvements from variance.
5. **Roll out only supported changes:** expand successful patterns across skill families, retaining domain-specific checklists where they measurably help. Re-evaluate after model or harness upgrades.

Suggested initial scenario set:

| Scenario | Outcome to score |
|---|---|
| UK target; non-US target without a profile corpus | Appropriate sources and explicit coverage gaps, without irrelevant universal searches |
| Two profiles/databases with colliding IDs | Correct reads/writes; no unrelated state changes |
| Same entity, two distinct research questions | Correct overlap judgment and retained new angle |
| Qualification late in a source document | Contextually faithful claim and declared reading coverage |
| Historical 10-K or 10-Q | Same accession throughout statements and ratios |
| Two awards for one recipient; paginated transactions | Correct award/period/record type; no invented payment claims |
| Empty, unavailable, and partial tool responses | Different accurate outcomes, with continuation where needed |
| One worker, several workers, slow worker, failed worker | Useful completion, exact artifact collection, truthful incomplete handoff |
| New or revised article; unrelated evidence backlog | Review of the actual target and final bytes |
| Neighboring skill requests and explicit user steering | Correct invocation, scope retention, and no unnecessary permission pause |

Measure task completion, evidence fidelity, recall of relevant material, unintended mutations, reviewer effort, false stops, invalid commands, repeated work, calls, tokens, and elapsed time. Keep domain integrity as a must-pass condition. Do not grade harmless differences in tool order as failure. Existing tests that parse real evidence examples provide a stronger template than assertions that merely lock exact Markdown strings.

## Requirements to retain

Primary-source provenance; exact quotes and canonical IDs; distinction among allegations, observations and inference; confidence ceilings; identity resolution; independence of sources; scoped negative claims; pinned database/profile; atomic ownership and expected-state updates; preserved evidence artifacts; public-source/no-contact boundaries; verified endpoints before adapter implementation; and semantic review of the content actually being published.

These encode the platform's purpose and known failure modes. Better models make them easier to satisfy, not obsolete.

## Supporting reports and limits

The family reports contain additional command defects, lower-priority documentation findings, proposed tests, and dismissed false positives. They are supporting reviewer evidence; the shortlist above is the parent's prioritized adjudication.

- [Research workflows](report-research.md)
- [Analysis and depth workflows](report-analysis.md)
- [Editorial workflows](report-editorial.md)
- [Operations](report-operations.md)
- [Financial and infrastructure](report-financial-infra.md)
- [Architecture, installation, and CLI](report-architecture.md)
- [Official Claude guidance and version caveats](report-claude-guidance.md)
- [Structural snapshot](skill-snapshot.json)

No end-to-end comparison of model variants was performed. The identified execution defects are source-verified, with selected isolated reproductions. Suggested reductions in tokens, pauses, or unnecessary work remain hypotheses until the proposed evaluations run. Three Codex-only skills and ordinary runtime syntax differences are not automatically defects. Missing repeated safeguards in an individual skill are also not defects when the shared instructions already supply them; an executable command that bypasses those safeguards is different.
