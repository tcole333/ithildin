# Research worker packet and report

Read this when preparing a delegated research track or receiving one.
`docs/RESEARCH_WORKFLOW_CONTRACT.md` owns source applicability, result reuse,
document coverage, and evidence rules; `docs/EXECUTION_CONTRACT.md` owns runtime
selection, supervision, and recovery.

## Parent packet

Send a concise factual mandate with these fields filled from the current task:

- **Objective:** the user's question, target identity/aliases, relevant dates and
  jurisdictions, and the specific subquestion this worker owns.
- **Context:** resolved `ITHILDIN_PROFILE`, absolute `ITHILDIN_DB_PATH`, repository
  workdir, parent lead/thread IDs when applicable, known evidence, and any
  user-specified constraints. Set the environment before importing tracker code.
- **Sources:** applicable source categories and current operation routes; why
  each belongs, expected scope, and any already reusable artifact. The worker may
  adapt query variants or propose an additional source when evidence warrants it.
- **Ownership:** sole search/persistence scope, cross-track owner contacts, and
  whether this mandate permits tracker writes or is explicitly artifact-only.
  Shared-file edits stay with the assigned owner.
- **Artifacts:** unique output prefix, expected report path, and a checkpoint
  path. Preserve complete source responses and read-coverage/continuation notes.
- **Done:** the factual answer/evidence standard, coverage to account for,
  disconfirmation check, and which unresolved barriers should return to the parent.

A suitable mandate is “Determine whether the named company had an ownership
interest during the specified period, using the relevant registry and filings;
report conflicting evidence and ordinary alternatives.” Avoid supplying the
conclusion the worker is expected to discover.

The parent records every worker ID and expected report path before waiting.
A modified mandate updates that record; additional workers need their own scopes
and report paths.

## Worker execution

1. Resolve identity and inspect prior records/artifacts before searching.
2. Execute the selected coverage with unique outputs. Track actual query,
   filters/limits, completeness, availability, and pagination.
3. Read the source context needed for the claim. Retain complete artifacts;
   read full documents or sequential sections/chunks when required. Record read
   coverage, unread relevant material, and continuation instead of treating a
   preview or retrieval as a completed review.
4. Form and test search hypotheses, including contrary evidence. Persist claims
   only with correct claim types, confidence ceilings, canonical refs, exact
   quotes for every ref, and source tokens. Register useful ambient entity facts.
5. Send cross-category records/questions to their owner or the parent. Mention
   contradictions and newly relevant gaps promptly so other tracks can adapt.
6. Write the report and identify any incomplete work or blocker. Respond to
   steering while preserving the original objective and previously accepted facts.

Checkpoint after meaningful progress and before a context boundary: current
question, accepted steering, pinned context, completed queries/read scope, record
IDs, artifacts, unanswered questions, and next action. Resume from this state
after interruptions/compaction. A temporary path is not disposable when it is the
only retained supporting artifact.

## Report shape

Use the parent-assigned path. This is one common schema; omit inapplicable
sections and add fields that a specific task needs. Set status truthfully rather
than copying `completed` into a partial report.

```markdown
---
agent: <runtime-id-or-track-name>
target: "<resolved target>"
skill: deep-investigate
status: completed | partial | blocked
findings_added: <count>
connections_added: <count>
entities_registered: <count>
leads_spawned: <count>
---
# Research report: <subquestion>

## Answer and supporting evidence
Supported observations, source refs, record IDs, and limitations.

## Source coverage
| Source / operation | Query and filters | Limits / continuation | Outcome | Artifact | Read coverage |
|---|---|---|---|---|---|

## Persisted records
Finding, entity, connection, and lead IDs; indicate artifact-only candidates
explicitly if persistence was outside the mandate.

## Contradictions and disconfirmation
Contrary evidence checked, competing explanations, and unresolved identity.

## Bounded negative results
Exact scope, authoritative coverage when known, limitations, and supported absence.

## Incomplete work and next action
Unavailable/partial sources, unread relevant material, continuation, and owner.

## Learnings
- [Friction] tool/source issue and its logged observation ID
- [Surprise] unexpected evidence
- [Methodology] reusable investigative lesson
- [Source quality] coverage/reliability qualification
```

Coverage outcomes use the shared `searched`, `reused`, `not_applicable`,
`unavailable`, and `partial` values. Counts measure work and can be zero; they do
not determine factual importance.

The parent reconciles each expected report with runtime status, inspects
load-bearing artifacts, integrates contradictions and partial handoffs, and
retains the final evidence/report artifacts under the Git workflow. Report
ingestion captures learnings; it does not certify factual completion.
