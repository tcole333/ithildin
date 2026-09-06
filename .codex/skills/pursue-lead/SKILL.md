---
name: pursue-lead
description: Claim and resolve a queued investigation lead, or select the next open lead when no ID is given. Use for an existing factual question with a tracked disposition; use deep-investigate when independent research tracks would help.
---

# $pursue-lead

Answer the lead's factual question and leave its evidence, coverage, and disposition
usable by the next researcher. Form and test hypotheses to choose searches;
distinguish observed facts, attributed statements, and inference in persisted claims.

## 1. Pin context and claim the lead

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and `docs/EXECUTION_CONTRACT.md`.
Resolve and pin `ITHILDIN_PROFILE` and absolute `ITHILDIN_DB_PATH` before tracker
calls. Preserve user-provided context and create an isolated workdir.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
```

With no ID, atomically select and claim a lead:

```bash
uv run python tools/lead_tracker.py claim-next
```

With an explicit ID, load its details, confirm it belongs to the selected profile
and is eligible, then claim it:

```bash
uv run python tools/lead_tracker.py show <LEAD_ID>
uv run python tools/lead_tracker.py claim <LEAD_ID>
```

Honor a failed claim or concurrent state change. If no eligible lead remains,
report that outcome. Do not substitute another lead for an explicitly requested
one. Record its question, thread, existing evidence, and unresolved assumptions.

## 2. Plan and execute the relevant research

Use the canonical source-applicability and result-reuse rules. A reusable response
needs its exact operation/filters, complete successful artifact, and appropriate
freshness or immutable source version; inspect it before relying on it.

Choose the task-specific workflow when useful:

| Lead question | Workflow |
|---|---|
| Person identity, roles, relationships | `$investigate-person` |
| Entity ownership, corporate/financial structure | `$trace-entity` |
| Domain/IP or other digital infrastructure | `$investigate-infra` |
| Particular filing, award, or case | `$analyze-filing`, `$analyze-contract`, or `$analyze-case` |
| Independent multi-source subquestions | `$deep-investigate` or native chat subagents under the execution contract |
| Specific document/relationship/financial question | Select operations that can resolve that question; the full person/entity checklist need not be repeated |

Carry the same lead question, pinned context, source ownership, and accumulated
coverage through nested workflows. Reuse the existing plan and artifacts instead
of restarting the investigation whenever a skill is consulted.

For property or litigation questions, discover executable source routes first:

```bash
uv run python tools/public_records_search_plan.py "<TARGET>" --output "$WORKDIR/public-record-plan.json"
```

Read the relevant `docs/modules/` reference for the selected operations.
Public-record account/request/paid/physical-office routes use
`public_records_actions.py plan` to prepare the concrete action. Keep collection
barriers separate from source-authoritative zero results. For ICIJ, official
remote search and first-hop traversal are available without local Neo4j; deeper
local access is a separate limitation.

Use unique `--output` artifacts for searches, inspect source/identity quality,
and log exact queries and outcomes with `lead_tracker.log_search`. A `session_id`
is supplied only for an existing integer session record; attach lead-specific
notes with `lead_tracker.py note`. Persist notable evidence as it is established.

Read complete documents when needed to resolve identity, context, qualifiers, or
the lead itself. For long documents, retain the complete artifact, inspect
sections or sequential chunks, and keep a read-coverage/continuation note. Resume
unread relevant material until the claim is established or its uncertainty is
explicit. A relevant quote is the citation payload, not a substitute for reading
enough source context.

## 3. Persist evidence and useful context

Search existing findings before adding new ones. Every finding needs canonical
evidence references, exact source quotes for each reference, registered source
tokens, and the appropriate claim type/confidence ceiling. Preserve allegation
language and distinguish the existence of a statement from its truth.

```bash
uv run python tools/findings_tracker.py add \
  --target "<TARGET>" --type communication \
  --summary "What the source establishes" \
  --evidence "<EVIDENCE_REF>" --claim-type paraphrase \
  --source-quote "<EVIDENCE_REF>:exact source text" \
  --sources <SOURCE_TOKEN> --confidence high \
  --lead-id <LEAD_ID>
```

Use the lead's `--thread-id` on findings when present. `direct_quote` from a primary
source can be `confirmed`; `paraphrase` is at most `high`; `inference` and `synthesis`
are at most `medium`. Correct existing claims through the audited correction API.

A relationship also needs quoted connection evidence:

```bash
uv run python tools/findings_tracker.py connect \
  --person-a "<ENTITY_A>" --person-b "<ENTITY_B>" \
  --type financial --strength medium \
  --evidence "<EVIDENCE_REF>" \
  --source-quote "<EVIDENCE_REF>:exact source text supporting this relationship" \
  --finding-id <FINDING_ID>
```

Use `entity_tracker.py lookup` / `add-entity` / `add-role` / `add-address` /
`add-relation` for discovered structured facts; resolve identity before connecting
records. Preserve ambient officers, dates, jurisdictions, addresses, financial
amounts, and affiliations even when they do not answer the immediate hypothesis.
Record employment arcs with `pillar_tracker.py arc` when the institution is a
registered pillar. Keep currency-bearing evidence shell-safe.

## 4. Resolve the lead

Perform a disconfirmation sweep: select a search or evidence check that could
refute the working explanation, and record its outcome and scope. Consider ordinary
alternatives before treating missing records or timing as intent.

Complete when applicable coverage answers the factual question to its evidence
standard, or the remaining bounded uncertainty has been documented and no useful
in-scope search remains. Further speculative variations need not continue after
coverage is complete and returns diminish. Relevant unsearched sources remain
gaps; useful evidence elsewhere does not erase them.

Create related leads for actionable new questions, and infra requests for missing
source/tool capabilities. Endpoint verification may support the request;
`$build-infra` owns integration. A finished answer need not generate a follow-up.

Use the appropriate disposition after rechecking the current lead state:

```bash
uv run python tools/lead_tracker.py complete <LEAD_ID> --findings "Question answered; evidence and remaining uncertainty"
uv run python tools/lead_tracker.py dead-end <LEAD_ID> "Why the available evidence leaves no useful pursuit"
uv run python tools/lead_tracker.py block <LEAD_ID> "Next useful primary-record action and the actual access barrier"
```

Choose one, not all three. Exhaust public alternatives before blocking for access.
A lack of a direct primary-subject connection is not a close reason when the lead's
own thread question remains valuable.

## 5. Handoff and continuity

Report the question answered, findings/connection/entity IDs, source coverage,
scoped negatives, contradictions, disposition, and next action. As a worker, use
the parent-assigned report path; otherwise retain `$WORKDIR/report-lead-<ID>.md`.
The report summarizes persisted records and identifies evidence artifacts and
partial/unavailable work. Ingest its learnings:

```bash
uv run python tools/methodology_tracker.py ingest-report "$WORKDIR/report-lead-<ID>.md" --skill pursue-lead --lead-id <LEAD_ID>
```

Use the actual report path. Log papercuts when encountered under the project
workflow. Preserve progress, sources read, unread continuation, and pending worker
IDs across interruptions/compaction; continue the original lead unless the user
changes the objective. Retain evidence/report artifacts according to the Git and
research contracts.
