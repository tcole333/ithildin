# Cross-skill architecture and CLI review

Scope: read-only inspection of both repository skill trees, root agent instructions, distribution/parity/validation code, representative CLI discovery and output interfaces, and skill-specific tests. Compared all 36 repository Codex SKILL.md files against same-name installed personal copies. No production database writes, skill workflow invocation, repository edits, sync, or runtime model evaluation. Worktree already had unrelated untracked report directories.

## Verified findings

### [P2] Distribution leaves 14 stale personal copies alongside the current repository skills

ID: architecture:distribution:stale-personal-copies

- Evidence: `scripts/sync_codex_skills.sh:2-8,11-25` calls `.codex/skills` a mirror and copies it into `$CODEX_HOME/skills` with `rsync --delete`; `scripts/lint_agent_docs.sh:5-14` assumes this manual sync is how stale HOME skills are refreshed. All 36 repo skills also have installed same-name copies. Fourteen SKILL.md bodies differ. This session's supplied catalog includes both project and personal copies, so duplicate availability is observed, not hypothetical.
- Concrete stale content: `/Users/travcole/.codex/skills/triage-leads/SKILL.md:42-69` still selects all profiles using raw SQL and applies `dict(r)` to default tuple rows. Repository `.codex/skills/triage-leads/SKILL.md:42-63` instead has profile-scoped tracker calls. Installed `/Users/travcole/.codex/skills/pursue-lead/SKILL.md:73-98` skips a source solely because the historical log matches and mandates U.S. sources for every person; repository `.codex/skills/pursue-lead/SKILL.md:72-86` requires reusable result artifacts and jurisdiction-specific source applicability. Higher-priority root policy protects the correct interpretation, but contradictory stale examples reintroduce the exact implementation friction recent changes fixed.
- Impact: repo fixes are not enough to remove obsolete executable examples from the model-visible catalog; same-name descriptions also consume discovery space and make which copy to read ambiguous. Selection precedence was not tested, so do not claim the stale copy necessarily executes or that this session cannot discover repository skills.
- Recommendation: select one version-controlled canonical content source, separate small runtime metadata/adapters, and expose each project skill once through the documented current repo discovery path. Parent is verifying latest `.agents/skills` and symlink guidance. Plan migration of managed personal copies using a manifest/hash check; preserve unrelated personal skills and any user modifications. Avoid another unverified bulk sync.
- Verification: enumerate effective skill paths from clean current Codex/Claude sessions, assert one intended same-name entry per project skill, compare normalized content hashes, and invoke a benign explicit skill to verify the selected source. Test migration using temporary home/repository fixtures.
- Evidence artifact: [installed-diffs.json](installed-diffs.json) contains all read-only diffs as an exact encoded string. Differing names: analyze-network, build-infra, curate-dossier, deep-investigate, generate-hunches, investigate-person, pursue-lead, review-article, review-dossiers, search-all-sources, systemic-analysis, timeline-analysis, trace-entity, triage-leads.

### [P2] Frontmatter validation locks the project to a repo-specific schema rather than current runtime capabilities

ID: architecture:validation:runtime-schema

- Evidence: `scripts/validate_skills.py:48-56` allows only six base fields plus `user_invocable`; `:185-195` rejects every other key. It labels underscore spelling a required Claude convention at `:23-26,48-51`. All 33 Claude variants use it (representative `.claude/skills/pursue-lead/SKILL.md:1-5`). `tests/test_validate_skills.py:29-43,83-98` explicitly protects this convention.
- Reproduction: direct `validate_skill_frontmatter()` call with `user-invocable: true`, `disable-model-invocation: true`, and `context: fork` returns `Unexpected frontmatter key(s): context, disable-model-invocation, user-invocable`. These fields need official runtime confirmation in the parent report; the rejection itself is verified. Current Anthropic documented names should replace assumptions from a bundled skill-creator validator.
- Impact: adopting current invocation controls or context delegation can fail the strict CI job (`.github/workflows/lint-agent-docs.yml:35-44`), even when runtime-valid. The existing true-valued underscore field should not be framed as a currently observed visibility failure: user visibility commonly defaults true; the defect is false validation assurance and inability to express current controls correctly.
- Recommendation: validate supported runtime metadata separately from shared Agent Skills metadata, use documented spellings, and allow explicitly documented runtime extensions. Add fixtures for valid current Claude/Codex fields and invalid/misspelled fields. Do not automatically enable restrictive options everywhere; choose behavior per skill with tests.
- Verification: runtime-specific schema fixtures plus actual CLI discovery/invocation checks. Update tests that currently entrench the private convention.

### [P2] CLI lint reports clean results when help fails or a documented subcommand is invalid

ID: architecture:validation:help-fails-open

- Evidence: `scripts/validate_skills.py:326-347` invokes `--help`, ignores `returncode`, and converts exceptions to an empty option set. `:460-474` guesses a subcommand from the first non-flag token and skips validation if there are no options. It validates option names, not subcommand choices or required arguments. Existing test module concentrates on frontmatter (`tests/test_validate_skills.py:28-135`).
- Reproduction, entirely in `/tmp/osint-q8INnbtl/validator-fixture`: an argparse script accepting only `search`, documented with `nonexistent-subcommand`, yields `[]` issues; a script whose help raises `ImportError`, documented with `search --nonexistent-option`, also yields `[]`. Thus clean lint can mean unchecked commands.
- Impact: strict CI can approve stale executable examples and commands that cannot even show help. This is precisely the kind of failure that produces agent retries and growing workaround prose.
- Recommendation: track `verified`, `unsupported`, and `failed` help/schema checks separately; make a nonzero/timeout/import failure visible. Expose pure `build_parser()` functions or a small stable machine-readable command schema for core tools, and parse representative examples without running actions. Maintain explicit exceptions for intentional templates and genuinely non-argparse tools instead of silently passing them.
- Verification: fixtures for valid commands, nonexistent subcommands, missing/invalid argument values, help failures, timeouts, global flags before subcommands, and templated examples. Add parser-backed command tests to the existing meaningful findings example tests.

### [P3] Legacy parity check classifies normal runtime syntax as unexpected drift

ID: architecture:validation:raw-parity

- Evidence: `scripts/audit_codex_skill_parity.py:49-57` compares raw SKILL.md text and exempts only `deep-investigate` via `:15`. Most variants intentionally differ in `user_invocable` frontmatter and `$skill` versus `/skill` syntax. Execution returns exit 1, `Unexpected drift: 32`, `Intentional Codex adaptations: 1`. Snapshot's normalized comparison finds only 10 shared pairs unequal beyond runtime normalization, meaning 23 shared pairs normalize equal (the snapshot itself is not proof the remaining differences are defects).
- Impact: noise makes the parity tool poor at surfacing real behavioral divergence and calls Claude definitive despite three Codex-only packages. It is not currently invoked by the inspected CI job, so this is a useful tooling correction rather than CI blockage.
- Recommendation: consolidate on one normalization implementation, compare shared substantive instructions plus referenced resources, and record intentional runtime differences explicitly. Report missing/extra skills separately with ownership intent.
- Verification: fixtures where invocation/frontmatter differences pass; a removed evidence requirement fails; runtime-specific packages produce an intentional-presence result.

### [P3] Root discovery index omits the property module even though skills route into it

ID: architecture:discovery:property-index

- Evidence: `AGENTS.md:181-195` (also corresponding CLAUDE table) lists module references for sources but has no property row. `docs/modules/property.md` exists and is 4,810 lines; property queries and public-record planning are now explicitly part of `.codex/skills/pursue-lead/SKILL.md:88-106` and `.codex/skills/trace-entity/SKILL.md:180-203`.
- Impact: the promised top-level module index does not expose an important current source family; agents must rediscover it through other links/searches.
- Recommendation: add the property/recorder module to the root routing index, or generate that index from one maintained source list. A direct link is the proportionate immediate improvement.
- Verification: verify every intended module in the authoritative index exists and current source families are routed to their owning reference.

## Concrete CLI/discovery proposal (design option, not an existing command)

The repository already has valuable CLI infrastructure; an all-new MCP server or rewritten command framework is not required. `tools/source_report.py:416-419` and other entries map names/descriptions to query tools; `:1007-1051` performs one-source health checks lazily; `:1054-1103` exposes `report`, `check`, and JSON. Public-record catalog/planner and unified routers already provide richer operation-aware discovery: `tools/query_property.py:17813-17821`, `tools/query_state_courts.py:14155-14169`, and `tools/public_records_search_plan.py:1798-1822`. The shared contract explicitly assigns commands/routes to these catalogs and modules (`docs/RESEARCH_WORKFLOW_CONTRACT.md:25-28,52-54`). `tools/output_util.py:102` already centralizes output flags.

Extend this into a small read-only discovery facade (illustrative names):

- `uv run python tools/tool_catalog.py list --domain legal --jurisdiction US --json`: compact source/tool summaries; no live probes, bulk data loads, or credential values.
- `... describe courtlistener search --json`: exact command/schema, required arguments, bounded examples, output shape, data coverage and noncoverage, access requirements, mutation/cost classification, and owning documentation anchor.
- Keep health checks explicit (`... check SOURCE` or existing `source_report.py check`) and keep `--help` cheap/offline. The full source report presently includes live checks through `generate_report()` (e.g. `tools/source_report.py:946-980`); a catalog request should not require them.
- Route execution to existing tested tools. Standardize a versioned output envelope gradually where needed: status distinguishing zero/partial/unavailable/error, count, coverage, continuation, artifact path, and actionable next step. Do not flatten domain-specific evidence or jurisdiction details.

This replaces the need to preload command menus into each SKILL.md. Pilot on three workflows (pursue-lead, trace-entity, search-all-sources) and compare actual tool selection, invalid commands, coverage quality, context use, and completion before expanding. Avoid one huge front-end help dump: discover names, then describe exactly one operation.

## Strengths and context-efficiency observations

- 36 Codex variants, 33 Claude variants; all 36 Codex packages have interface metadata reported valid by the snapshot. Only deep-investigate exceeds 500 lines (798 Codex / 799 Claude); do not classify every long-ish skill as obsolete. Body text is loaded on demand, so 10,084 total Codex skill lines are not all initial prompt cost.
- Most packages already fit normal size guidance. Only audit-skills and discover-investigations have bundled scripts/references. Further splitting should target repeated source menus and invariant policy likely to drift, not maximize file count.
- Snapshot metadata name+description character totals are 5,012 for repository Codex and 3,672 for Claude, before paths/wrappers. Installed duplicates increase discovery footprint, but this does not establish that any skill was omitted in this session.
- Root instructions are 19,604 characters (AGENTS.md) and 17,234 (CLAUDE.md). TOOL_REFERENCE is 8,311 lines / 450,097 characters; legal and property modules are each roughly 4,800 lines. The root's direction to consult relevant modules is good progressive disclosure, but larger modules need direct anchors/compact operation lookup. Avoid requesting full-document reads for routine CLI selection.
- The shared research contract is a strong modern control plane: pinned context, applicability rather than universal source quotas, reuse of actual bounded artifacts, one persistence owner, explicit failed/partial handoffs, exact evidence provenance, and no claim that finding counts establish truth (`docs/RESEARCH_WORKFLOW_CONTRACT.md:7-21,43-54,56-63,104-123`). Preserve these constraints while reducing prose elsewhere.
- Dispatcher already pins child database/profile and refuses missing scoped context (`scripts/dispatcher.py:1397-1401,1423-1430`); do not report all orchestration as unscoped based solely on older skill examples.

## Validation and limits

Ran `uv run python -m pytest tests/test_validate_skills.py tests/test_analysis_skill_commands.py tests/test_triage_leads_skill.py --offline --basetemp /tmp/osint-q8INnbtl/pytest-architecture -p no:cacheprovider -q`: **26 passed**. The analysis examples parse the actual finding CLI with persistence mocked and enforce evidence/ref/quote/confidence semantics (`tests/test_analysis_skill_commands.py:13-41`); this is a strong template for deterministic contract tests. Triage tests are narrower string-level checks (`tests/test_triage_leads_skill.py:11-25`). The inspected tests are not model behavior/trigger evaluations; the audit skill appropriately recommends fresh unprimed forward tests (`.codex/skills/audit-skills/SKILL.md:168-178`). Add a small versioned scenario set measuring correct selection, completion, calls/tokens, stop conditions, evidence quality and unintended mutations on target runtimes/models. This is a proposal, not a claim that a particular rewrite is proven better.

No live source probes, model runtime discovery experiment, end-to-end skill trials, global home modifications, or exhaustive inventory-completeness check were performed. Static count of 388 Python files under tools / 254 query_*.py files is an orientation fact, not a count of independent data sources. Official best-practice citations and specific model-generation claims are owned by the parent review.

Exact validator reproduction is preserved in `/tmp/osint-q8INnbtl/reproduce-architecture-validator.py`. From the repository root, run `PYTHONPATH="$PWD" UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache uv run python /tmp/osint-q8INnbtl/reproduce-architecture-validator.py`. Observed output:

```text
Invalid real argparse subcommand lint result: []
Broken help + invalid flag lint result: []
Native Claude option lint result: ['Unexpected frontmatter key(s): context, disable-model-invocation, user-invocable. Allowed: allowed-tools, compatibility, description, license, metadata, name, user_invocable']
```

Parent confirmed the official Claude documentation uses `user-invocable` with default true. Thus current underscore-true fields should be corrected without claiming current invocation is broken.
