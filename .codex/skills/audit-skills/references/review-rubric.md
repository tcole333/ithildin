# Skill review rubric

Use this rubric to judge material behavior, not personal prose preferences. A finding needs a cited artifact, a realistic failure path, and a proportionate correction.

## Contents

- [Severity](#severity)
- [Trigger and scope](#1-trigger-and-scope)
- [Workflow completeness](#2-workflow-completeness)
- [Command and repository correctness](#3-command-and-repository-correctness)
- [Authorization and safety](#4-authorization-and-safety)
- [Evidence and investigative integrity](#5-evidence-and-investigative-integrity)
- [Multi-agent design](#6-multi-agent-design)
- [Context efficiency and maintainability](#7-context-efficiency-and-maintainability)
- [Runtime variants and interface metadata](#8-runtime-variants-and-interface-metadata)
- [Recommendation quality gate](#recommendation-quality-gate)

## Severity

| Level | Use when | Examples |
|---|---|---|
| P0 | The skill can cause severe irreversible harm, evidence corruption, unauthorized external action, or dangerous access. | Destructive command without authorization; instruction to fabricate provenance. |
| P1 | The main workflow is unusable, materially incorrect, unsafe, or violates a binding project rule. | Required command does not exist; wrong database/profile is mutated; evidence confidence rule is inverted. |
| P2 | A common path is unreliable, ambiguous, incomplete, or likely to waste substantial work. | Missing stop condition; output artifact is never collected; trigger description collides with another skill. |
| P3 | The improvement is bounded and useful but does not threaten normal completion. | Stale example, avoidable repetition, weak UI prompt, or minor context inefficiency. |

Do not use P0 merely to mean important. If impact depends on an unlikely assumption, state it and lower severity.

## 1. Trigger and scope

- Does frontmatter say what the skill does and when it should trigger?
- Would natural user phrasings select it without relying on body text?
- Does it distinguish adjacent skills and state meaningful non-goals?
- Are arguments, defaults, target resolution, and empty-result behavior defined?
- Is default scope proportionate, especially for broad, expensive, or mutating work?

Verify overlap by comparing descriptions and ownership boundaries, not keyword counts alone.

## 2. Workflow completeness

- Is the sequence executable from a fresh session?
- Are prerequisites, context loading, workdir creation, inputs, outputs, and stop conditions present?
- Does each produced artifact have a consumer?
- Are partial failure, zero results, retries, and unavailable sources handled without false success?
- Does the final report distinguish completed, skipped, failed, and unverified work?

Flag a missing step only if another binding instruction or directly linked reference does not already supply it.

## 3. Command and repository correctness

- Do files, modules, subcommands, flags, tables, fields, and paths exist?
- Does `--help` confirm CLI syntax when available?
- Do project Python calls use `uv run python`?
- Do data-producing searches use an isolated workdir and `--output`?
- Does the skill load the active investigation profile instead of hardcoding case data?
- Are Git and database assumptions compatible with the repository's current conventions?

Treat generated examples and placeholders differently from commands intended to run verbatim.

## 4. Authorization and safety

- Does the skill distinguish read-only inspection from edits, database writes, queue jobs, external messages, deployment, or publication?
- Do consequential actions have the needed authorization, with existing user authorization preserved and approval requested only after the proposed action is concrete?
- Are destructive, paid, authenticated, or rate-limited operations bounded?
- Does the workflow preserve unrelated worktree changes and concurrent agent work?
- Does it respect public-source-only and no-contact rules?

Recommend the narrowest missing guardrail. Do not make all useful actions approval-gated.

## 5. Evidence and investigative integrity

- Are fact, allegation, inference, synthesis, and absence kept distinct?
- Are claim type, confidence ceilings, evidence IDs, source quotes, and provenance required where findings are created?
- Does the skill avoid counting mirrors or repeated reporting as independent corroboration?
- Does it preserve charge/allegation/conviction language?
- Are negative results recorded only when the searched source and scope make the absence meaningful?
- Are identity resolution and source reliability handled before load-bearing conclusions?

Any recommendation must preserve or strengthen the project's audit trail.

## 6. Multi-agent design

- Are tasks independent enough to parallelize?
- Does each subagent have an explicit mandate, source or file scope, mutation policy, and unique output path?
- Are shared-file edits avoided or serialized?
- Does the active parent collect artifacts, reconcile contradictions, check coverage, coordinate writes, and resume after compaction without an unnecessary headless launch?
- Can failed agents be detected without treating silence as a negative result?
- Does the prompt avoid leaking intended conclusions into independent review?

More agents are not automatically better. Flag parallelism only when coordination failure is plausible.

## 7. Context efficiency and maintainability

- Is SKILL.md focused on non-obvious procedure with detail justified by task complexity? Treat roughly 500 lines as a review signal, not a hard cap.
- Are detailed rubrics, schemas, or variants moved to directly linked references?
- Are bundled files reachable from SKILL.md and free of placeholders?
- Is duplicated policy likely to drift from AGENTS.md or a canonical reference?
- Are examples concise, current, and representative?
- Is deterministic repeated work implemented by a tested script rather than repeatedly improvised code?

Do not recommend splitting a skill if the extra navigation costs more than it saves.

## 8. Runtime variants and interface metadata

- Does the directory name match frontmatter `name`?
- Does the Claude variant use its intended invocation syntax and `user-invocable` field and currently documented native metadata?
- Does the Codex variant use `$skill-name` and omit Claude-only frontmatter?
- Are material Claude/Codex differences intentional and documented by behavior, not accidental drift?
- Does `agents/openai.yaml` contain quoted interface strings, a 25–64 character short description, and a default prompt that explicitly names `$skill-name`?

Raw text inequality is not automatically drift. Normalize expected runtime syntax before judging parity.

## Recommendation quality gate

Before reporting a finding, confirm all five:

1. The cited text or missing behavior is verified.
2. The failure path is realistic and material at the assigned severity.
3. No higher-priority instruction already resolves it.
4. The correction is smaller and safer than leaving the issue in place.
5. A command, focused test, or realistic forward test can verify the correction.

If any condition fails, omit the finding or place it in no-action notes as a dismissed suspicion.
