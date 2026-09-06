---
name: deep-investigate
description: Investigate a person, entity, or topic through independent research tracks in the current chat. Use for a deep multi-source investigation that benefits from supervised parallel work; use pursue-lead for a queued factual question or search-all-sources for a quick lookup.
---

# $deep-investigate

Resolve the requested question through source research, then reconcile the evidence
and remaining uncertainty. Coordinate native chat subagents for independent tracks
while continuing useful parent work. Choose the number and shape of tracks from the
question and available capacity.

## Inputs and context

Accept a target and any factual question, date range, jurisdiction, investigation,
or depth constraint in the user's request. Resolve ambiguous identities before
making connections. If the request is broad, state the question and bounded first
scope, then adapt as evidence arrives.

Before source planning, read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and
`docs/EXECUTION_CONTRACT.md`. Pin `ITHILDIN_PROFILE` and the selected absolute
`ITHILDIN_DB_PATH`; pass them to every worker. Use the configured corpus and current
module documentation. Create a unique workdir:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
uv run python tools/findings_tracker.py search "<TARGET>" --output "$WORKDIR/existing-findings.json"
uv run python tools/lead_tracker.py search "<TARGET>" --output "$WORKDIR/existing-leads.json"
uv run python tools/entity_tracker.py lookup --name "<TARGET>" --output "$WORKDIR/existing-entities.json"
```

Inspect resolved entity details with `entity_tracker.py show <ENTITY_ID>` when roles,
addresses, or relations affect the briefing. These trackers honor the pinned
database. Existing facts guide deduplication; a historical search row alone is not a
reusable result.

## 1. Build the source and worker plan

Use the shared applicability checklist to select sources from the question,
identity, role, jurisdiction, and dates. Record source, operation/scope, reason,
owner, and coverage outcome. Retain relevant sources even when another already
returns useful evidence. An access failure is a coverage gap.

For a broad multi-target request, a landscape pass may identify the targets worth
deeper work. Use that route when it advances the question, accounting for any
explicitly selected targets and requested depth.

Possible tracks are a menu:

| Track | Questions and discovery routes |
|---|---|
| Corpus | Configured corpus tools, name variants, full source documents, structured email/entity layers; `docs/modules/corpora.md` and the profile's AGENTS.md |
| Entity and financial | Relevant registries, ownership, filings, charities, property/secured assets, awards, political disclosures; corresponding `docs/modules/` references |
| Legal | Relevant court systems, parties and legal roles, filings/opinions, enforcement; `docs/modules/legal.md` and public-record planner |
| Network and open web | Published relationships, offshore records, sanctions, first-party context, missing-source discovery; `docs/modules/network-sanctions.md` |
| Digital infrastructure | Domain/IP/certificate/history questions supported by evidence; `$investigate-infra` |

Assign each source category one search/persistence owner. Workers can identify
cross-category evidence and send a reference/question to its owner rather than
repeat searches or duplicate findings. Combine thin tracks and split independent
subquestions when useful. The parent can own a concrete source or verification
task too; include it in the same matrix.

Before delegation, read [references/worker-contract.md](references/worker-contract.md)
for the packet fields and shared report shape. Instantiate only relevant
operations, using current module commands or `--help`. State the factual question
without supplying an intended conclusion.

## 2. Launch and supervise research

Use native subagents for bounded independent tracks and inherit the configured model.
In Codex, use `spawn_agent` to create tracks.
Launch independent tracks before waiting; use `send_message` to steer active
workers and `followup_task` for a bounded continuation when needed. In Claude Code,
use the native Agent tool and the host’s messaging/continuation facilities for
the corresponding actions.

Give each worker the pinned context, applicable sources, ownership/mutation
policy, unique output/report paths, and evidence standard from the shared
contract. Record its runtime ID and expected report path in `$WORKDIR/progress.md`.

While workers run, complete unassigned useful work: inspect existing evidence,
resolve identity, prepare the coverage matrix, investigate a parent-owned source,
or verify an emerging contradiction. Keep the user informed about material
findings and changes of direction. Use `list_agents` for a compact status check and
`wait_agent` when no useful independent work remains; in Claude Code use the
host’s worker status and completion notifications. Inspect a worker's status or
send a targeted progress request if a report is missing. Quiet reasoning or a
long retrieval alone does not establish a hung worker.

Reconcile every expected report with runtime completion. If a worker failed or
finished without its artifact, recover the partial work and request completion or
record the incomplete handoff. Adapt the plan when new evidence changes relevance.
Preserve the original objective and accepted steering across interruptions and
compaction; checkpoint completed scope, worker IDs, artifact paths, unresolved
questions, and next steps, then resume remaining work under the shared contract.

## 3. Read evidence and reconcile reports

A saved result is available evidence, not proof that its contents were read.
Retrieve complete source artifacts and inspect the context needed for the claim.
For an applicable EFTA document in the Kabasshouse corpus:

```bash
uv run python tools/ingest_kabasshouse.py doc "<EFTA_ID>" --output "$WORKDIR/corpus-document.json"
```

Use a distinct path per document. This artifact retains the full retrieved rows;
the console's default `doc` preview is limited. Read a whole document when required.
For long documents, work through relevant sections or sequential chunks, record
pages/sections already read and the continuation point, and continue until the
question's evidence requirement is met. Preserve pagination/truncation and any
unread relevant material as partial coverage. Other corpora use their documented
retrieval operation and canonical IDs.

Collect all worker reports or explicit incomplete handoffs. Reconcile:

- Identity and duplicate underlying records; mirrors/re-OCRs are one source.
- Claims supported by independent evidence, contradictions, and alternatives.
- Required-source coverage, failures, partial results, and bounded negatives.
- Persisted finding/entity IDs against report claims and quoted source artifacts.
- Remaining factual questions and which next action could resolve them.

Inspect underlying evidence for load-bearing conclusions and disagreements.
Workers may form and test hypotheses to guide collection. Persist observations,
inferences, and cross-source synthesis with the correct claim types and confidence
ceilings; finding counts measure work rather than evidence strength.

## 4. Finish the investigation

Before completion, run or assign a disconfirmation check for the working
explanation and record its exact searched scope. Where competing hypotheses are
registered, inspect `hypothesis_tracker.py list` and the applicable competition
groups (`matrix` / `compete`); report the least-inconsistent explanation with its
remaining uncertainty.

Record synthesis through the tracker with underlying evidence references, exact
`ref:quote` pairs, actual source tokens, and the retained analysis artifact. Use
`claim_type=synthesis` and at most `confidence=medium`. Search existing findings
first. Register discovered entities, roles, addresses, and relations as required
by the shared contract, including useful ambient facts.

Create follow-up leads for unresolved actionable questions and infra requests for
verified missing capabilities. Probe public endpoints only enough to describe the
gap; `$build-infra` owns integration work. Ingest report learnings with
`methodology_tracker.py ingest-report` and run the shared post-wave
`uv run python tools/auto_leads.py run` under the pinned context.

Completion means the factual question is answered to its evidence standard and
applicable coverage is complete, or the remaining uncertainty/access barrier has
an explicit disposition and next action. A source limit, worker completion, or
large finding count alone does not finish the investigation.

Return the answer, supporting evidence, material contradictions, source coverage
(completed/reused/partial/unavailable), created record IDs, durable artifact paths,
and unresolved next steps. Preserve reports or source artifacts that support
findings according to `docs/GIT_WORKFLOW.md`; temporary location is not permission
to discard the only evidence copy.
