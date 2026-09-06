---
name: trace-entity
description: Trace a named entity's registration, ownership, officers, assets, and financial relationships across relevant jurisdictions. Use for an entity-centered factual question; use analyze-filing or trace-grants for specialized document or funding depth.
user-invocable: true
---

# /trace-entity

Map the entity and the evidenced relationships needed to answer the question.
Corporate complexity, shared addresses, intermediaries, or jurisdiction choice
are search leads; test ownership/control and ordinary legal or administrative
explanations before inferring purpose.

## 1. Resolve the entity and context

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and `docs/EXECUTION_CONTRACT.md`.
Pin profile/database and inherit the parent lead, source ownership, report path,
and any existing search plan. Create unique output paths:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
uv run python tools/findings_tracker.py search "<ENTITY>" --output "$WORKDIR/entity-findings.json"
uv run python tools/lead_tracker.py search "<ENTITY>" --output "$WORKDIR/entity-leads.json"
uv run python tools/entity_tracker.py lookup --name "<ENTITY>" --output "$WORKDIR/entity-lookup.json"
```

Resolve legal name, aliases, entity type, registration number, jurisdiction, dates,
and status from records. Distinguish registry IDs from canonical investigation
entity IDs and namesakes before linking them. State the ownership, asset, or
transaction question and hypotheses that would guide the next source check.

## 2. Build and execute applicable coverage

Use the shared source-applicability/reuse contract. Select jurisdictions from
evidence and assess relevant source families:

| Nexus | Operations and references |
|---|---|
| Registration/ownership | Relevant registry search, entity detail, officers, filing history, beneficial ownership; `docs/modules/registries.md` |
| Public securities/financial entity | Regulator filings, EDGAR, GLEIF hierarchy where covered; `docs/modules/financial.md` |
| Charity/funding | Charity filings and EIN-resolved 990 records; `/trace-grants` for deeper flow analysis |
| Property/secured assets | Property/recorder/UCC/aircraft records and ownership history; public-record planner and source modules |
| Litigation | Relevant courts, party roles, dockets, and actual filings; `docs/modules/legal.md` |
| Procurement/political | Relevant award/subaward, campaign, lobbying, and FARA records; government/political module docs |
| Offshore/network | ICIJ and applicable relationship datasets; `docs/modules/network-sanctions.md` |
| Documentary context | Configured corpus tools and first-party sources that can cover this target/period |

Consult current module commands or `--help` before choosing an operation. Use
unique artifacts and record actual query scope, limits, continuation, and
availability. Independent tracks may use native chat subagents under the shared
execution contract; the parent retains reconciliation and useful unassigned work.

For a UK company number/address/corporate nexus, check Companies House search,
company, officers, PSC, and filings. The UK module owns current routes.
Identity-resolved company numbers should appear in distinct output paths.
Officer-name ambiguity needs company/date context.

ICIJ example: review search candidates, then use the exact numeric node ID:

```bash
uv run python tools/query_icij.py search "<ENTITY>" --type Entity --output "$WORKDIR/icij-search.json"
uv run python tools/query_icij.py officers <EXACT_NODE_ID> --output "$WORKDIR/icij-officers.json"
uv run python tools/query_icij.py connections <EXACT_NODE_ID> --output "$WORKDIR/icij-connections.json"
```

The official remote service supports first-hop lookup. Deeper local traversal is
a separate capability; an unavailable local graph does not erase remote coverage.

## 3. Follow selected property and lateral pivots

For property/court questions, build the capability plan:

```bash
uv run python tools/public_records_search_plan.py "<ENTITY>" --output "$WORKDIR/public-record-plan.json"
```

Follow the plan's source IDs and operations, preserving local-cache and acquisition
barriers as coverage information. For a NYC connection, search the selected entity:

```bash
uv run python tools/query_acris.py party "<ENTITY>" --output "$WORKDIR/acris-party.json"
```

Repeat targeted party queries only for evidence-selected aliases, officers, or
entities relevant to the question, each with a unique output. The ordinary entity
trace does not expand into a corpus-wide entity search.

Trace upstream owners, downstream entities, relevant officers, formation/lifecycle
dates, and material transactions. Use exact registration numbers and dates to
separate legal ownership, asserted control, and nominee roles. For address,
registered-agent, or officer pivots, assess the provider's client base and routine
shared-service explanations. Explore related entities while the pivot produces
evidence relevant to the question; retain useful ambient facts and queue further
independent questions. Record search scope and why a broad or noisy pivot stopped.

## 4. Read and persist the records

Retrieve complete artifacts and read the full document when required to establish
ownership, chronology, qualifiers, or the claim. For long filings/documents,
inspect sections or sequential chunks, record read coverage and continuation, and
continue until the question is resolved or unread relevant material is an explicit
gap. Snippets are navigation aids.

Persist findings with canonical evidence refs, exact `ref:quote` pairs for each
reference, source tokens, and claim-type confidence ceilings. Preserve primary
assertions versus independently established truth. Use inherited lead/thread IDs.

Register entities/roles/addresses/relations through `entity_tracker.py` and resolve
before adding. Preserve source refs, dated officer roles, formation numbers,
jurisdictions, observed addresses, and useful financial details. Use the audited
correction API for repairs; keep currency-bearing text shell-safe.

A relationship needs quoted evidence in its own record:

```bash
uv run python tools/findings_tracker.py connect \
  --person-a "<ENTITY>" --person-b "<OWNER_OR_OFFICER>" \
  --type corporate --strength medium \
  --evidence "<EVIDENCE_REF>" \
  --source-quote "<EVIDENCE_REF>:exact source text supporting this relationship"
```

For matching retained public-record rows to canonical entities, consult
`public_records_entity_candidates.py generate` / `list` and inspect candidates
before making identity assertions.

## 5. Reconcile and finish

Map the ownership chain and distinguish unknown endpoints from natural persons
actually established by evidence. Cross-check dates, financial counterparties,
and contradictions. Perform a disconfirmation check for the working explanation;
consider legitimate structuring, shared service providers, and incomplete
collection before inferring concealment or common control.

Complete when applicable coverage answers the question to its evidence standard
or the remaining uncertainty/access barrier has a concrete disposition/next
action. Mark partial ownership chains and unavailable sources explicitly.
Create related leads for actionable next questions; `/build-infra` owns missing
tool/source integration.

When useful, update `research/entities/<entity-slug>.md` with identity,
registration, ownership, dated roles, assets/flows, cited findings, coverage, and
open questions. Preserve existing authored work and evidence artifacts under the
Git workflow. Workers write the assigned report path or
`$WORKDIR/report-trace-<entity-slug>.md`, including status, record IDs, contradictions,
bounded negatives, source outcomes, and continuation. Preserve progress across
interruptions/compaction and resume the original question.
