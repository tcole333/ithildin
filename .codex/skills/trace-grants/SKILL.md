---
name: trace-grants
description: Trace nonprofit grant flows and shared governance from charity filings. Use for funding-chain, reciprocal-transfer, or nonprofit coordination questions with reproducible primary evidence.
---

# $trace-grants

Investigate an organization by name or `--ein`, with optional `--depth`,
`--min-amount` and traversal limit. Read
`docs/RESEARCH_WORKFLOW_CONTRACT.md` for pinned context and evidence handoffs;
use `docs/modules/financial.md` and `query_990.py <command> --help` for current
coverage and interfaces. Create an isolated workdir and preserve it across a
long investigation.

## Resolve identity and financial context

Resolve the exact EIN with `search` and `lookup`; confirm name, jurisdiction,
form coverage and years before expanding. Use `financials` to examine revenue,
expenses and retained assets. Register the entity with its real jurisdiction.
A local miss can require ProPublica/IRS filing discovery; it does not establish
that the organization has no activity.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_990.py lookup "<EIN>" --output "$WORKDIR/lookup.json"
uv run python tools/query_990.py financials "<EIN>" --output "$WORKDIR/financials.json"
uv run python tools/query_990.py flow --help
uv run python tools/query_990.py flow "<EIN>" \
  --depth 2 --min-amount 50000 --limit 50 --output "$WORKDIR/flow.json"
```

The shown depth 2, minimum individual grant 50,000 and 50 edges per queried node
are **starting defaults**. Honor explicit arguments and adapt omitted values to
the factual question, recording every filter and reason. Small grants may matter.

## Understand traversal before interpreting the graph

`flow` alternates outgoing grants at odd depths and incoming funders at even
depths, then checks reverse flows for discovered pairs. Depth 2 therefore finds
co-funders of recipients, not every two-hop downstream recipient. Each per-node
query is capped by `--limit`; an edge at the cap means possible missing frontier.
The tool's `depth` reports the requested bound, not proof that all hops were
visited or the graph was exhausted. EIN-missing records cannot form exact-EIN
edges, and the amount filter is applied to individual rows before aggregation.

Report the observed graph's traversal, years, amount filter, edge limit and
unresolved frontier. If the research question needs a missing downstream branch,
query its recipient as a new seed or inspect its `filer` rows; expand only as
needed to answer the question. Account for uncovered branches explicitly instead
of describing the bounded graph as complete.

Select material flows, reciprocal pairs, and governance overlaps for review
based on relevance and evidence, not mandatory top-N finding counts. Top
recipients and co-grantors are useful starting priorities, not a ceiling on
follow-up. Native chat workers can independently hydrate different filings with
inherited model settings, pinned context and unique artifacts; the parent
reconciles every promoted amount and identity.

## Hydrate load-bearing evidence

`flow.json` and `shared-officers` output are discovery artifacts. For each
promoted edge or officer overlap, retrieve the underlying rows and return links:

```bash
uv run python tools/query_990.py filer "<FUNDER_EIN>" \
  --output "$WORKDIR/filer-<FUNDER_EIN>.json"
uv run python tools/query_990.py filings "<FUNDER_EIN>" \
  --output "$WORKDIR/filings-<FUNDER_EIN>.json"
uv run python tools/query_990.py officers "<ORG_EIN>" \
  --output "$WORKDIR/officers-<ORG_EIN>.json"
uv run python tools/query_990.py filings "<ORG_EIN>" \
  --output "$WORKDIR/filings-<ORG_EIN>.json"
```

Filter by exact normalized recipient EIN, observed tax years, **and the same
per-row cash_amount threshold used by flow**. Reproduce the edge count and sum;
resolve discrepancies before promotion. Preserve the exact Schedule I/Part VII
row serialization or verbatim XML/PDF span and each return URL/object ID. Read
the full relevant filing sections when purpose, accounting treatment or authority
is load-bearing; quotes should support the resulting claim.

For shared officers, use `shared-officers`, then confirm the same person, title,
tax years, overlapping tenure and role authority from the filings. For reciprocal
flows, retain both directions and timing. Net flow measures observed transfers,
not control. Test regranting, fiscal sponsorship, returned funds and other
innocent explanations before advancing a coordination hypothesis.

Use `co-grantors` for relevant recipients and `red-flags` for material entities.
A common funding pattern may reflect program area, geography or grant cycles.
A node with both incoming and outgoing grants is a candidate conduit; examine
purpose, timing, governance and retained assets before classifying it.
Hub-and-spoke shape alone does not establish a donor-advised fund or donor anonymity.

## Cross-reference and persist

```bash
uv run python tools/query_990.py cross-ref --output "$WORKDIR/cross-ref.json"
uv run python tools/findings_tracker.py add --help
uv run python tools/hypothesis_tracker.py add --help
```

Cross-ref uses shared canonical entities in the **pinned database**. Intersect its
results with the observed grant network and validate name-only matches. Shared
entity presence is not itself an investigation-specific finding or relationship.

Record findings when verified evidence advances the investigation. Aggregated
flows and shared-officer results are synthesis, maximum medium confidence.
Attach one reference per load-bearing return and matching
`--source-quote "REF:<exact row/span>"` pairs. Store calculations, filters,
timing, graph limitations and artifact paths in detail. A single verbatim primary
row may separately be direct_quote/confirmed if its summary adds no inference.
A tool label such as “Schedule I grant records” is not a source quote.

Record coordination hypotheses with best innocent explanations, falsification
criteria and next tests. Create evidence-linked leads for meaningful unanswered
questions, including new entities when their role matters.

## Complete

Report seed identity, form/year coverage, observed graph and filters, material
flows and shared governance, competing explanations, findings/leads, and source
artifacts. Form coverage is specific: a 501(c)(4) may file a full 990/990-EZ;
990-N lacks detailed finances, and contributor identities or recipient EINs may
be absent. State the missing year/form/field instead of treating all (c)(4)s as
invisible. Finish when the requested question is answered or each unresolved
branch has a recorded evidence need and disposition; keep resumable progress
during long work.
