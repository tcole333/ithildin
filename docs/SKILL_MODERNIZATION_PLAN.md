# Skill modernization implementation plan

Date: 2026-09-05. Owner: current Codex task. Branch: `codex/skill-modernization-20260905`.
Base: `53acdf3eae8fe6a2e8a8ad406c30c1a2e3ade54b`.

## Intended behavior

Interactive investigation requests are completed under the current chat's supervision using native subagents when independent work helps. The parent stays engaged, accepts steering, reconciles evidence, and persists progress across long work and compaction. Models inherit the configured runtime choice; domain skills do not pin named generations. Headless dispatch remains an explicitly selected unattended compatibility path.

Skills specify scope, evidence standards, tool entry points, and completion criteria. Tools enforce database/profile selection, expected-state mutations, stable evidence identity, complete result artifacts, and truthful failure/partial states. Models choose appropriate investigation depth, document-reading strategy, relevant sources, and useful delegation within those constraints.

## Work units and ownership

| Unit | Owned paths | Acceptance / validation | State |
|---|---|---|---|
| A. Scoped lead operations | `tools/lead_tracker.py`, `tools/lead_dedup.py`, `tools/triage_policy.py`, paired triage/dedup skills, dedicated tests | Two DB/profile fixtures; foreign/stale decisions rejected; distinct questions retained; remaining-group batches complete | Complete |
| B. Validation and discovery | skill validator/parity/sync scripts, dedicated tests, repository discovery wiring | Native metadata accepted; invalid/uninspectable commands visible; current repo discovery without destructive HOME sync | Complete |
| C. Evidence identity | EDGAR/USASpending operations, paired analyze-filing/analyze-contract skills, dedicated tests | Selected accession/award retained; truthful transaction/obligation scope; complete artifacts and pagination | Complete |
| D. Editorial verification | evidence audit, dossier review handoff, current-target web checks, paired editorial/discovery/status skills, tests | Requested final content audited; pinned/cited evidence scoped; worker packets exist; status scope accurate | Complete |
| E. Research skill design | paired deep-investigate/pursue-lead/person/entity/infra/landscape/search skills and conditional references | Native supervised delegation; sufficient full-source reading; meaningful stop conditions; no conflicting role bans or bulk target expansion | Complete |
| F. Financial/source integration skills | paired financial/cohort/grant/source-onboarding skills, focused tests | Correct runnable examples; safe repeat-ingest scaffold; heuristics become explained defaults; underlying period/scope visible | Complete |
| G. Analysis skill design | paired network/timeline/systemic/hunch/case/framework skills, analysis export/tests | Evidence-sensitive novelty; observed-graph language; correct fields/quotes; preserved falsification and provenance | Complete |
| H. Parent orchestration and integration | root instructions, research/execution contracts, orchestrate/dispatch/init/methodology/audit skills, model-pin audit, final plan/results | Chat-native default; explicit unattended boundary; current context inheritance; no unintended model pins; integration tests and independent forward tests | Complete |

Subagents shared this owned worktree with non-overlapping paths and left commits to the parent. Root/shared instruction files and global metadata normalization are parent-owned. Any necessary edit to another unit's file is requested from its owner. Production investigation DBs and unrelated checkout changes are outside the implementation/test scope.

## Sequence

1. Preserve the audit baseline and create this plan before editing behavior.
2. Implement A–G independently while the parent implements H and audits model selection.
3. Review each coherent diff, run focused tests/ruff and repository hygiene, and commit explicit paths in validated units.
4. Normalize runtime metadata after concurrent skill edits finish. Validate effective discovery, links, and paired substantive behavior.
5. Run combined affected tests and offline CLI checks. Independently forward-test representative read-only/staged skill requests without providing the expected answer.
6. Record results, retained limitations, and all task-owned changes. Do not claim cross-provider efficiency gains without actual repeated model comparisons.

## Scope decisions

- User authorization covers the review findings, native chat orchestration, model-pin cleanup, and persistence/document-reading improvements. No additional approval is needed for these local changes.
- Preserve evidence confidence ceilings, quoted provenance, source independence, public-source/no-contact boundaries, and content-bound publication review.
- Review/apply are distinct user intents. Existing authorization carries forward; prepare concrete reviewable work before any genuinely required approval.
- Keep optional unattended infrastructure functional. Do not launch headless jobs to implement or test this request.
- Remove arbitrary cognitive limits; use completion criteria and resumable artifacts. Shorter prompts are useful only when they retain relevant procedure.
- Existing personal skill files may contain user changes. Distribution tooling must inventory/backup/verify managed paths and preserve unrelated skills. Do not silently overwrite HOME installations.
- Model/version references in historical research, fixtures testing a specific version, or detector names unrelated to LLM selection are not automatically active pins.

## Research basis

The prior review compared all 36 skills / 69 variants. Current guidance: [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model), [OpenAI skills](https://learn.chatgpt.com/docs/build-skills), [Claude prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1), [Claude skills](https://code.claude.com/docs/en/skills), [skill evaluation](https://developers.openai.com/blog/eval-skills), and [practitioner CLI experience](https://simonwillison.net/2026/Mar/9/not-so-boring/).

## Results

All eight units were implemented and committed on the owned workstream branch.
The original checkout and personal skill installations were preserved. The
following records the initial implementation handoff; subsequent integration
checks are recorded in the merge PR and its CI results.

### Resulting behavior

- Interactive investigations use native subagents in the current chat when
  independent work helps. The parent remains active, accepts steering, reviews
  evidence and owns integration. Headless dispatch is an explicit unattended
  option. Missing native collaboration tools mean sequential work, not an
  automatic headless launch.
- Skills inherit the runtime model. Active dispatcher and extraction generation
  pins were removed; unknown runtime choices remain unknown in provenance.
  The isolated extractor inherits the root Codex user-config model, or accepts
  an explicit override, without loading unrelated user rules or features.
- Completion depends on the requested questions, material evidence and source
  coverage. Count limits are export/batching defaults, not cognitive ceilings.
  Full material documents can be read when needed. Artifacts and checkpoints
  retain progress, context, unresolved questions and ownership across compaction.
- CLI contracts, typed review packets and content hashes enforce fragile
  mechanics. Lead changes are scoped, freshness-checked and atomic; filing and
  award operations retain the selected record; status distinguishes unavailable
  data from zero; editorial review binds to actual current content and evidence.
- Current repository discovery uses `.agents/skills`. Runtime metadata and
  shared instructions are consistent across Claude/Codex. The tool catalog and
  linter inspect declarations without executing application code. The old sync
  command now defaults to a read-only check, with explicit inventory/backup
  commands for personal duplicates.

### Validated commits

| Commit | Completed unit |
|---|---|
| `9e11b903` | Audit baseline and implementation plan |
| `666445ed` | C: selected filing/award identity and truthful result scope |
| `0eb2ef95` | F: financial/source workflows and correct scoped examples |
| `3a4eba7d` | E/G and shared H contracts: persistent research and analysis |
| `f5c4d98c` | A: scoped, atomic triage and dedup review packets |
| `df2153b5` | H: model inheritance, read-only scoped status and orchestration |
| `8e01d6ed` | D: current-content editorial verification and review packets |
| `b15aa7ff` | B: discovery, runtime metadata and safe CLI introspection |

The final documentation commit adds the integration results and small paired
clarifications on full methodology-review coverage and useful parallelism.

### Validation and independent review at implementation handoff

- **459 tests passed** in the combined affected Python suite across 36 files
  with the repository's offline network guard. Three edgartools dependency
  deprecation warnings remain. Tests used synthetic/temporary databases and a
  temporary model-config fixture.
- The Node changed-content coverage fixture passed for explicit new, changed
  and unchanged target files. It checks the actual content bytes selected for
  verification; no production publication was attempted.
- Final skill snapshot: **36 skills, 69 variants, 0 errors, 34 warnings and 3
  informational unpaired packages**. Normalized shared-body/resource drift is
  **0**. Discovery resolves all 36 repository Codex packages.
- Independent reviews covered scoped mutations, static parser/distribution
  safety, editorial evidence/content binding and runtime status. Reproduced
  issues were corrected and rechecked. The independent H forward exercise
  selected native supervision, honored an explicit DB over ambient context,
  preserved partial/unknown status and resumed from a saved planning checkpoint.
- Changed Python passes Ruff; shell syntax, staged repository hygiene and diff
  whitespace checks pass. The active model-pin scan found no remaining named
  generation/tier defaults in skills and launch paths.

Temporary fixtures and raw check output remain under `/tmp/osint-q8INnbtl`;
durable reports are copied into the repository. An initial ignored worktree
`.venv` is a regenerable local dependency cache. The temporary `web/node_modules`
link used for the Node fixture was removed after validation.

[Detailed implementation reports, independent reviews and test artifacts](../reports/skill-modernization-2026-09-05/implementation/README.md)
record the exact checks and their boundaries. [Runtime/distribution guidance](SKILL_RUNTIME.md)
explains how to use the revised packages.

### Retained limits and follow-up

1. At initial handoff, 34 static warnings were 17 occurrences per runtime across six dynamic
   CLIs: USASpending, SAM, UK company ingestion, property, state courts and
   California. Integration subsequently expanded safe declaration inspection
   and separated unknown interface shapes from unexecuted custom value checks.
   Unknown shapes still fail strict mode; static success does not establish
   network health or custom value semantics. See the integration validation
   record in the merge PR for the full documentation/CI scope and final results.
2. Personal skill copies still exist. Inventory/backup protects differing user
   content; deliberate retirement can follow integration. An already-running
   chat can retain an earlier skill inventory. No temporary worktree link was
   installed as a permanent personal dependency.
3. The forward exercise tested fixture execution and checkpoint-based planning
   continuation, not recovery from a host crash with live workers. No headless
   jobs or external research were launched for validation. No repeated Claude
   versus Codex benchmark establishes token, latency or quality improvements.
4. The isolated extraction process cannot infer an ephemeral desktop selection
   or named-profile model choice; pass `--model` for those cases. An unknown
   default is not assigned a fabricated resolved model or reused as a known
   model-specific cache entry.
5. Evidence standards, confidence ceilings, source independence, no-contact
   boundaries and content-bound publication review remain enforced. Longer
   context and stronger persistence do not replace these domain requirements.
