# Research skill audit — repository evidence

Scope: paired `.claude/skills` and `.codex/skills` packages for `deep-investigate`, `pursue-lead`, `investigate-person`, `search-all-sources`, `trace-entity`, `investigate-infra`, and `landscape-scan`. Read all seven complete Codex bodies (3,124 lines; 162,170 UTF-8 bytes), all counterpart diffs, all seven `agents/openai.yaml` files, the snapshot, review rubric, Git workflow, research workflow contract, relevant methodology sections, and targeted implementations/module docs. Claude counterparts differ only by invocation/frontmatter or intentional runtime language within this scope. Unless stated otherwise, cited skill locations below are Codex; corresponding Claude content is one line later.

This report separates verified repository defects from modernization hypotheses. It does not claim that current model capabilities alone prove an architecture should change. The parent owns external best-practice research and final prioritization. No research queries, credentials, DB writes, skill execution, repository edits, or new agents were used. The two existing untracked report directories remain untouched. Only read-only CLI `--help` checks and temporary audit artifacts were produced.

## Verified findings

### R1 — P2: The full-text corpus retrieval example returns only a prefix

**Evidence.** `.codex/skills/deep-investigate/SKILL.md:187–188` (Claude `:188–189`) instructs Agent A to read full text for every found document, then supplies `uv run python tools/ingest_kabasshouse.py doc EFTA_ID`. The parser defaults `--chars` to 2,000 and requires `--full` to override that (`tools/ingest_kabasshouse.py:643–651`). The renderer prints `text[:args.chars]` plus ellipsis for longer text (`:483–491`). `--output` takes a separate branch that writes the complete retrieved rows (`:469–482`). Read-only `doc --help` verified that both `--full` and `--output` exist.

**Failure path.** A corpus worker copies the canonical retrieval command for a long document, sees the opening paragraph, and persists a conclusion without reaching a qualification, denial, or counterparty elsewhere in the text. It can also inaccurately report full-document coverage. This is a concrete mismatch between the prescribed task and executable example, independent of opinions about prompt length.

**Small correction.** Retrieve to a unique `--output` artifact, then read sufficient surrounding text/sections to establish the claim; use `--full` when sending complete text directly to the console is appropriate. Keep limits visible and distinguish a preview from complete retrieval. Avoid replacing the current example with a blanket requirement to dump every complete document into model context.

**Verification.** A small mocked document longer than 2,000 characters with decisive text after the prefix should demonstrate that the documented command retains that text and that the worker reports the actual read scope. Existing help and source inspection establish the defect; no live corpus access was needed.

### R2 — P2: A single-entity trace silently expands into a database-wide remote ACRIS search

**Evidence.** `.codex/skills/trace-entity/SKILL.md:196–199` (Claude `:197–200`) places `query_acris.py batch-entities` immediately after the target-specific party search, without a target restriction. The implementation selects every shared `entities` row whose name has at least four characters (`tools/query_acris.py:670–677`) and loops over them, issuing an exact remote query and potentially a second fuzzy query for each (`:682–703`). There is no selected-target argument in the command. The parser defaults `--investigation-db` to the repository's database, independently of `ITHILDIN_DB_PATH` (`:1037–1047`). `batch-entities --help` verified the available scope arguments.

**Failure path.** A trace of one NYC-linked company triggers requests for unrelated entities across all investigations. On a substantial entity registry this can consume a large amount of time and remote traffic. In a staged investigation the same command additionally reads the shared live database rather than the pinned stage. Per-query record limits do not bound the number of entities searched.

**Small correction.** Remove the corpus-wide batch command from the ordinary trace. Use the already-present `party "<ENTITY>"` operation and issue explicitly selected officer/entity pivots. If a corpus-wide ACRIS maintenance workflow is wanted, give it separate explicit scope and selected-database handling; do not merely add a smaller per-entity result limit.

**Verification.** A mock source and DB containing a target plus unrelated names should confirm that the documented single-target path queries only the chosen target/pivots. No live ACRIS request is necessary.

### R3 — P2: Deep-investigate's preflight bypasses the pinned database

**Evidence.** `.codex/skills/deep-investigate/SKILL.md:138–144` (Claude `:139–145`) opens `sqlite3.connect('investigation.db')` for existing entity and role checks. The same skill requires preserving the selected `ITHILDIN_DB_PATH` at `:18–22`, and the canonical contract requires it at `docs/RESEARCH_WORKFLOW_CONTRACT.md:18–21`. Tracker APIs already honor that variable, for example `tools/entity_tracker.py:19,62–63` and `tools/findings_tracker.py:40–41`.

**Failure path.** An orchestrator running against a staged or alternate database reads entity history from the shared root database while reading findings/leads and assigning worker writes under the pinned environment. Its briefing can falsely say an entity already exists or fail to see staged records. Pinning the environment alone cannot repair this inline literal path.

**Small correction.** Prefer the existing entity tracker lookup interface, with a targeted role lookup through the appropriate existing API where needed. If direct SQL is essential, resolve the database through the same shared context helper and open it read-only. Do not replace it with another independently maintained default-path implementation.

**Verification.** An isolated two-database fixture with distinct target records should prove preflight observes the selected database. This is a read-scope defect, not a claim that this particular snippet writes the wrong database.

### R4 — P3: The source menu describes an obsolete California browser prerequisite

**Evidence.** `.codex/skills/search-all-sources/SKILL.md:187–188` says California search needs “MCP Playwright Chrome.” Canonical `docs/modules/registries.md:149–163` describes the current short-lived headed Chrome/Node helper and gives `runtime-check`, `probe`, and bounded search commands. `tools/query_california.py:620–639` routes search through `_run_helper`, not its retained legacy CDP functions.

**Failure path.** A fresh worker following the skill may look for or launch an unavailable MCP browser even though the repository's self-contained helper supports the query. Conversely it is not directed to the useful runtime diagnostic that can explain a missing dependency.

**Small correction.** Link to the canonical California module subsection and mention `runtime-check` rather than duplicating a stale runtime requirement. The existing search command itself is valid.

**Verification.** Documentation comparison and dispatch inspection suffice for the text correction; a local `runtime-check` can validate the user-facing prerequisite route during implementation.

## Modernization opportunities requiring evaluation, not asserted model-era defects

### O1 — Replace blanket document-reading prohibitions with evidence-sufficiency rules

`pursue-lead:331`, `investigate-person:408`, and `trace-entity:358` prohibit reading full document text and direct workers to extract relevant quotes only. `pursue-lead:247` also says full document reading is something discovery agents should not spend time on. Deep-investigate's general rule at `:781` partly conflicts with its corpus mandate at `:187`.

The legitimate goal is avoiding unbounded context and unnecessary deep analysis. A categorical reading ban also denies workers discretion when one short complete document is the cheapest way to verify identity, context, or a qualifier. Proposed rule: search/preview first, then inspect the text and surrounding context required for every load-bearing claim; use section/chunk retrieval for long documents; hand off prolonged specialized analysis under existing depth rules. Test against documents with misleading early snippets and late qualifications, and measure factual accuracy plus tokens/time. Do not simply mandate full reading of every result.

### O2 — Express research/analysis boundaries in outputs, while allowing reasoning to select searches

Openers prohibit theorizing/framework use (`pursue-lead:8`, `investigate-person:8`, `trace-entity:8`, `search-all-sources:8`, `investigate-infra:8`, `landscape-scan:8`). Yet pursue-lead mandates hypotheses (`:287`) and disconfirmation (`:251`), investigate-person mandates explicit hypotheses (`:65–68`) and missing-pattern analysis (`:385–393`), and trace-entity mandates structural analysis (`:327–343`).

The canonical methodology already makes an intentional distinction: Research “MAY” form hypotheses about where to search (`research/INVESTIGATIVE_METHODOLOGY.md:510–513`) while reserving theory-building and editorial framing to other planes (`:497–507,515–530`). Therefore this is not proof that the architecture is broken. Compress the opening to that precise distinction: reasoning and alternate hypotheses may guide collection; persisted assertions must match evidence/claim-type rules; sustained synthesis can be handed off. Benchmark whether the rigid agent-role separation adds latency or missed pivots before removing it. Preserve the separation of observation, inference, and publication.

### O3 — Move adaptive source selection ahead of the long static menus

`search-all-sources:37–230` embeds a very large command menu, with Epstein corpora “FIRST” at `:41–60`, then adds profile-specific corpora at `:240–247`. `investigate-person:109–110` calls this “primitive” as a comprehensive baseline and then repeats numerous source categories. `trace-entity:99–122` and `investigate-infra:240–243` also hardcode Epstein corpus commands. Some real profiles intentionally have no corpus (`investigations/allbirds/config.yaml:161`, `investigations/altman/config.yaml:100`, `investigations/chesney/config.yaml:28`).

The higher-level contract already resolves applicability, so do not report “all these sources must always be run” as a verified behavior. The usability opportunity is to make the first visible executable path match the canonical contract: question + jurisdiction + identity + source capabilities → selected source operations. Move case-specific routes to profile documentation, and detailed command menus to the existing module docs or linked references. A default pointer should still make tool discovery easy; deleting examples without replacing their discovery value would be a regression.

Potential deterministic helper: render a plan from the existing profile and capability catalog, with source operation, selector/filter schema, freshness, availability, output path, and persistence owner. Verify with a U.S. public-company task, a UK company task, a non-U.S. target without corpora, and a selector lookup. Tool availability/runtime health should be a result state, not a guessed zero.

### O4 — Extract repeated worker/report material from deep-investigate

Deep-investigate is 798 lines and about 46.8 KB. Most bulk is four inline worker templates (`:165–651`), each repeating persistence, infrastructure-request, and report instructions (`:216–254`, `:365–405`, `:485–523`, `:613–651`). Four near-identical report schemas create drift risk; a single report contract plus short source mandates can retain the durable invariants with less context.

Keep the orchestrator's essentials in SKILL.md: trigger, inputs, pinned context, selected sources/ownership, expected artifacts, wait/failure policy, evidence reconciliation, completion. Put worker menus and one shared report schema in directly linked references, preferably reusing canonical docs rather than inventing another source catalog. The byte/line count is evidence of size, not evidence that model performance worsens; compare completion/coverage against the current baseline.

### O5 — Replace file-count polling and rigid wave sizing with expected-artifact and worker-status coordination

Deep-investigate wisely allows fewer workers when it declares the report set (`:10,158,793`), but its executable polling example still waits for count 4 and reads A–D (`:665–673`); the synthesis intro also assumes four (`:690`). Liveness prose assumes visible output growth and possible failure after two unchanged checks (`:676–682`). These are brittle examples even though the earlier exact-report-set instruction lets a competent agent adapt them.

Retain structured report artifacts and bounded independent mandates, but wait through the runtime's status/completion primitives and collect the declared report set. In Codex, reports still have value even though subagent finals arrive automatically. Permit the coordinator to perform a short verification/reconciliation read when cheaper than launching another wave; this would require intentionally updating the canonical Control Plane policy (`research/INVESTIGATIVE_METHODOLOGY.md:478–486`), not silently deleting a skill sentence. Test 1-worker, 4-worker, partial failure, and slow-but-active cases.

### O6 — Convert assumption-heavy investigative slogans into questions with alternatives

Trace-entity asserts “Every layer of corporate complexity is a layer of obfuscation” and “The jurisdiction choice reveals the intent” (`:47–53`), then asks who benefits from opacity (`:334`). Investigate-infra asserts shared infrastructure signals reveal a hidden relationship (`:35`), every allowed CSP domain is a technology relationship (`:169`), and offers categorical DNS/HTTPS conclusions (`:33`). The same skill has excellent bounded-negative guidance (`:39–44`).

These are verified statements in the prompt, not empirically tested conclusions about their downstream effect. They can prime a worker toward a conclusion before evidence is collected and deserve expert review irrespective of model generation. Rewrite them as hypotheses and require discriminating evidence against ordinary shared-service, legal/administrative, historical, or collection explanations. Review the methodology too: some similar assertions originate there (e.g. `research/INVESTIGATIVE_METHODOLOGY.md:215–225`). The general alternative-hypothesis contract already exists, so the narrow change is to align vivid examples with it, not add another full caution checklist.

### O7 — Standardize evidence examples and discovery metadata rather than repeating CLI schemas

Connection examples in `pursue-lead:172–176`, `investigate-person:264–267`, `trace-entity:255–258`, and `landscape-scan:154–157` omit `--source-quote`. In current code connection insertion can retain empty metadata (`tools/findings_tracker.py:3018–3028`), while verification/publication requires each edge evidence row to have a quote (`:2652–2664`). Passing `--finding-id` alone does not populate quoted connection evidence. The shared workflow contract already requires exact `ref:quote` pairs, so this was not elevated to a claim that the whole workflow lacks provenance safeguards. Align copyable examples with the current canonical contract and preferably centralize the minimal valid creation shape.

Skill descriptions are concise but several lack routing boundaries: “Comprehensive investigation ... across all sources” for investigate-person overlaps the orchestrated deep-investigate and pursue-lead entry points. The search-all-sources body explains the difference at `:10`, but its frontmatter does not. Improve trigger descriptions with the question each entry point owns and relevant non-triggers; evaluate a small routing set containing a quick lookup, a queued lead, a named-person research request, and explicit parallel deep research. The seven Codex interface YAML files are valid; their generic default prompts are an optional usability refinement, not a structural failure.

## Strengths worth preserving

- The project already uses skills to encode non-obvious domain requirements rather than generic writing tips: canonical evidence IDs, exact source quotes, claim-type confidence ceilings, source ownership, entity resolution, scoped negative results, and source availability states.
- `deep-investigate:62–73` requires applicable source planning and one persistence owner; this directly addresses redundant searches and false corroboration. The shared contract explicitly rejects universal source counts (`docs/RESEARCH_WORKFLOW_CONTRACT.md:43–54`).
- `pursue-lead:48–59` uses atomic claiming; `:72–78` checks actual reusable artifacts; `:249–279` supplies useful completion/access-barrier criteria and a disconfirmation sweep. Preserve these deterministic safeguards.
- `deep-investigate:688–700` labels cross-agent synthesis correctly and checks contradictions/competing hypotheses, rather than treating finding counts as proof.
- ICIJ routes are updated to remote search with exact numeric IDs and distinguish deeper local graph access (`trace-entity:75–89`, `investigate-person:217–227`, `pursue-lead:277–279`).
- Property/court workflows use a capability planner and preserve account/request/paid/physical-office barriers as coverage states (`investigate-person:195–200`, `trace-entity:226–231`). That is a good model for other tool families.
- Incremental structured persistence, unique temporary paths, evidence/source references, and collecting compact worker reports are valuable in long and parallel investigations. Ambient documentation is an explicit project requirement, so simply deleting it to shorten skills would change user policy.

## Dismissed or downgraded suspicions

- **Exactly four agents/all sources are mandatory:** not accurate after reading the full source-plan and reduced-track provisions. Recommend clearer examples, not a false defect.
- **Missing pin-context block in five skills proves wrong-profile writes:** the user-supplied AGENTS and canonical research contract already impose the pinning rule. The hardcoded SQLite/ACRIS paths above are different because they bypass the environment even when it is pinned correctly.
- **Research hypotheses are categorically forbidden:** the canonical methodology explicitly allows search hypotheses. The scope wording is unnecessarily broad, but the architecture has an intentional exception.
- **Claude/Codex drift in the snapshot proves stale behavior:** the scoped differences are intentional runtime invocation/coordination language. No unintended counterpart semantic divergence found.
- **`query_shodan.py reverse-dns <IP1>,<IP2>` is invalid:** dismissed; the parser explicitly accepts comma-separated addresses (`tools/query_shodan.py:411–412`).
- **`query_courtlistener.py party` does not exist:** dismissed; it is a current parser operation (`tools/query_courtlistener.py:895–898`).
- **Missing quote fields necessarily make `connect` crash:** dismissed; current insertion permits incomplete unverified evidence. Publication/verification is gated, which is why the report describes example/documentation drift and later rework rather than a nonexistent immediate failure.
- **Line count alone proves poor performance:** not claimed. Suggested progressive disclosure must be tested for navigation cost, coverage, and correctness.

## Coverage and validation limits

All seven paired packages and seven Codex interface files reviewed. Implementations checked where required for candidates: `ingest_kabasshouse.py`, `query_acris.py`, `query_california.py`, `findings_tracker.py`, `entity_tracker.py`, relevant parsers in Shodan/CourtListener/USVI/DS10, and canonical registry/public-record/research docs. Read-only help checks: `ingest_kabasshouse.py doc --help` and `query_acris.py batch-entities --help`, using a unique temporary `UV_CACHE_DIR`. No source endpoint was probed; no runtime claim about remote API health was made; no allegation about investigation subjects was researched. Broad best-practice recommendations are hypotheses for evaluation and should be paired with the parent's official/practitioner source research.
