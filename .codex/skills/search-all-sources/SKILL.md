---
name: search-all-sources
description: Look up a name, entity, address, term, or selector across selected relevant datasets and consolidate the returned records. Use for bounded discovery or availability checks; use pursue-lead or deep-investigate to resolve a full investigation.
---

# $search-all-sources

Return a deduplicated view of what relevant sources can tell us about the supplied
query, with exact search scope and coverage. Choose operations from the question
and selector type; the skill name does not require querying every installed tool.

## 1. Resolve the lookup

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and `docs/EXECUTION_CONTRACT.md`.
Pin the investigation profile and database, inherit any parent source ownership,
and create an isolated workdir:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
```

Identify the query type, target identity, question, jurisdictions, dates, and
requested breadth. For a namesake or mixed selector, establish candidates before
connecting results. Use existing evidence and search history for planning; reuse
only an intact complete response satisfying the shared operation/filter/freshness
contract.

## 2. Select executable source operations

Build a source plan using the canonical applicability checklist, the profile's
`corpus_tools`, and these discovery references. Inspect current commands or
`--help` for the selected operation before adapting an example.

| Question or selector | Discovery route |
|---|---|
| Configured document corpus can cover the query | Profile AGENTS.md and `docs/modules/corpora.md`; fetch canonical documents behind hits |
| Company, officer, address, secured asset | `docs/modules/registries.md`; jurisdiction-specific source availability |
| Securities, charity, financial records | `docs/modules/financial.md`; filing/organization identifiers before detail calls |
| Litigation, legal role, case | `docs/modules/legal.md`; select the field that matches the expected role |
| Public property/recorder/court routes | `public_records_search_plan.py`; normalized routers and catalog-backed acquisition actions |
| Procurement, grants, public payments | `docs/modules/government.md`; recipient and award identity |
| Political activity | `docs/modules/political.md`; relevant FEC/lobbying/FARA operation |
| Relationships/offshore/sanctions | `docs/modules/network-sanctions.md`; identity resolution before graph traversal |
| Domain/IP infrastructure | `docs/modules/osint-infra.md` or `$investigate-infra` |
| Published context or missing-source discovery | Official pages, archives, and attributed reporting; reporting is not independent primary proof |

Run relevant independent operations in parallel when useful, within source limits.
Give each search a unique `--output` path, or explicit redirection for a command
without that option. Preserve actual filters, limits, pagination, warnings, and
availability. A result cap limits the observed scope; it does not establish that
the source is exhausted.

Useful capability-discovery examples:

```bash
uv run python tools/public_records_search_plan.py "<QUERY>" --output "$WORKDIR/public-record-plan.json"
uv run python tools/query_property.py sources --output "$WORKDIR/property-sources.json"
uv run python tools/query_state_courts.py sources --output "$WORKDIR/court-sources.json"
```

Run these when property/court records are relevant. Follow the plan's selected
source IDs and operations. Use `public_records_actions.py plan` for account,
request, paid product, formal feed, or physical-office routes and `enqueue` only
when tracking the prepared action belongs to the authorized task. Report its
barrier state rather than a source-authoritative zero.

For California corporate search, consult `docs/modules/registries.md` and check
the self-contained Node/Chrome runtime before a bounded search:

```bash
uv run python tools/query_california.py runtime-check --output "$WORKDIR/ca-runtime.json"
uv run python tools/query_california.py search "<QUERY>" --limit 25 --output "$WORKDIR/ca-search.json"
```

Source access changes belong in the source catalog/module documentation; do not
assume a cached skill-era availability claim is current.

## 3. Selector lookup branch

For email, username, phone, domain, or IP queries, the selector pivot tool can
coordinate applicable adapters and emit candidate leads:

```bash
uv run python tools/selector_pivot.py run "<SELECTOR>" --output "$WORKDIR/selector-pivot.json"
```

Inspect its current help, enabled adapters, scope, and side effects. Paid adapters
are opt-in through `--enable-paid` only when paid usage is within the task's
authorization/budget. Retain raw evidence responsibly; leaked/anonymous links need
independent primary corroboration and are at most medium confidence. Preserve
selector types and candidate identity rather than silently treating a match as a
confirmed person relationship.

## 4. Inspect, log, and consolidate

Inspect the response artifacts before reporting hit counts or claims. Fetch and
read enough underlying source text to establish identity and context. Full or
long-document reading is supported when necessary; retain complete artifacts and
track sections/chunks read and continuation. A quick lookup may leave further
verification to an explicit follow-up, labeled as such.

Log actual searches and results using `lead_tracker.log_search` and the shared
reuse recorder. Distinguish `searched`, `reused`, `not_applicable`, `unavailable`,
and `partial`. Avoid double-logging adapters that already record the query. A
`session_id` refers only to an existing integer session record.

Deduplicate by underlying record/canonical evidence ID. Mirrors, re-OCRs, and
multiple indexes of one document are redundant coverage. Corroboration requires
independent evidence supporting the same proposition; one authoritative record
can establish a bounded direct observation without an arbitrary source quota.

Return:

- Query, identity candidates, question, and searched scope.
- Relevant records with canonical IDs/artifact paths and brief supported facts.
- Independent corroboration, redundant indexes, contradictions, and unverified
  candidate matches.
- Per-source operation, filters/limits, counts, coverage outcome, and continuation.
- Useful next steps or leads, distinguishing record absence from coverage gaps.

As a worker, use the assigned report path or
`$WORKDIR/report-search-<query-slug>.md`. Retain evidence artifacts required by the
parent or persisted claims. Complete when the requested lookup scope is accounted
for; do not imply that a bounded lookup exhausts an investigation.
