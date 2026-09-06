# Skill modernization implementation plan

Date: 2026-09-05. Owner: current Codex task. Branch: `codex/skill-modernization-20260905`.
Base: `53acdf3eae8fe6a2e8a8ad406c30c1a2e3ade54b`.

## Intended behavior

Interactive investigation requests are completed under the current chat's supervision using native subagents when independent work helps. The parent stays engaged, accepts steering, reconciles evidence, and persists progress across long work and compaction. Models inherit the configured runtime choice; domain skills do not pin named generations. Headless dispatch remains an explicitly selected unattended compatibility path.

Skills specify scope, evidence standards, tool entry points, and completion criteria. Tools enforce database/profile selection, expected-state mutations, stable evidence identity, complete result artifacts, and truthful failure/partial states. Models choose appropriate investigation depth, document-reading strategy, relevant sources, and useful delegation within those constraints.

## Work units and ownership

| Unit | Owned paths | Acceptance / validation | State |
|---|---|---|---|
| A. Scoped lead operations | `tools/lead_tracker.py`, `tools/lead_dedup.py`, `tools/triage_policy.py`, paired triage/dedup skills, dedicated tests | Two DB/profile fixtures; foreign/stale decisions rejected; distinct questions retained; remaining-group batches complete | In progress |
| B. Validation and discovery | skill validator/parity/sync scripts, dedicated tests, repository discovery wiring | Native metadata accepted; invalid/uninspectable commands visible; current repo discovery without destructive HOME sync | In progress |
| C. Evidence identity | EDGAR/USASpending operations, paired analyze-filing/analyze-contract skills, dedicated tests | Selected accession/award retained; truthful transaction/obligation scope; complete artifacts and pagination | In progress |
| D. Editorial verification | evidence audit, dossier review handoff, current-target web checks, paired editorial/discovery/status skills, tests | Requested final content audited; pinned/cited evidence scoped; worker packets exist; status scope accurate | In progress |
| E. Research skill design | paired deep-investigate/pursue-lead/person/entity/infra/landscape/search skills and conditional references | Native supervised delegation; sufficient full-source reading; meaningful stop conditions; no conflicting role bans or bulk target expansion | In progress |
| F. Financial/source integration skills | paired financial/cohort/grant/source-onboarding skills, focused tests | Correct runnable examples; safe repeat-ingest scaffold; heuristics become explained defaults; underlying period/scope visible | In progress |
| G. Analysis skill design | paired network/timeline/systemic/hunch/case/framework skills, analysis export/tests | Evidence-sensitive novelty; observed-graph language; correct fields/quotes; preserved falsification and provenance | In progress |
| H. Parent orchestration and integration | root instructions, research/execution contracts, orchestrate/dispatch/init/methodology/audit skills, model-pin audit, final plan/results | Chat-native default; explicit unattended boundary; current context inheritance; no unintended model pins; integration tests and independent forward tests | In progress |

Subagents share this owned worktree with non-overlapping paths and leave commits to the parent. Root/shared instruction files and global metadata normalization are parent-owned. Any necessary edit to another unit's file is requested from its owner. Production investigation DBs and unrelated checkout changes are outside the implementation/test scope.

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

To be filled with commits, validation, forward-test results, and retained limitations as units complete.
