# Research workflow contract

Read this before planning source coverage, reusing search results, or assigning
research workers. Skills own their task-specific steps; this document owns the
shared profile, coverage, reuse, and evidence handoff rules.

## Pin the task context

Resolve the requested investigation before any scoped work. If the task does not
name one, read the active context once and pin that resolved profile for this run:

```bash
uv run python tools/investigation_context.py show
export ITHILDIN_PROFILE="<resolved-profile-id>"
uv run python tools/investigation_context.py show
```

Preserve an existing `ITHILDIN_DB_PATH`, or set it to the explicitly selected
database's absolute path when using a staged/test database. Pass both environment
values to child workers. Do not change the shared active profile to route a task.
Create one isolated workdir per run; assign each worker unique output paths.

When changing investigations, replace the task pin before any seed or tracker
operation. `investigation_context.py set` changes an interactive default; it does
not override an inherited `ITHILDIN_PROFILE`. For an explicitly scoped command,
use `investigation_context.py run --profile NAME --db PATH -- uv run python
tools/TOOL.py ...`. Read the selected profile's case instructions even when the
shell remains at the repository root.

## Choose applicable sources

Start with the factual question, target identity, role, jurisdiction, relevant
dates, and the profile's corpus tools. The table below is the canonical source
applicability checklist. The source catalog and linked module documentation own
current commands and access routes.

| Question / nexus | Sources to assess |
|---|---|
| Profile corpus can cover the target and period | Configured corpus tools; distinguish independent documents from mirrors |
| Legal entity identity or ownership | Registries in relevant jurisdictions; GLEIF where covered; officer/address pivots |
| Public-company, securities, or investment-filing nexus | Relevant regulator's filings; SEC EDGAR for a U.S. filing nexus |
| Nonprofit roles or grant flows | Applicable charity filings; IRS 990 lookup/officers/grants where covered; EIN-based network queries |
| Litigation or legal claims | Relevant court systems; federal and state/local routes via the public-record catalog for a U.S. nexus |
| Property, secured assets, or aircraft | Relevant recorder/property/UCC/aircraft registries; choose jurisdictions from evidence, including ownership history |
| U.S. political giving, lobbying, or foreign representation | FEC, lobbying disclosures, FARA for the corresponding activity or question |
| U.S. federal procurement or grants | USASpending, SAM, relevant award/subaward records |
| Relationships, sanctions, or public role | LittleSis, OpenSanctions, ICIJ and comparable datasets where coverage is relevant; resolve identity before connecting records |
| Biographical context, first-party statements, missing source discovery | Official pages, archives and published reporting; preserve source attribution |

Record a coverage row for every assessed source: source, question/scope, relevance
reason, owner, and outcome. Outcomes are `searched`, `reused`, `not_applicable`,
`unavailable`, or `partial`. A relevant source remains required even when another
source returns useful results. A source outside the target's jurisdiction or
question may be `not_applicable` with a concrete reason. An access failure or
local-cache miss is a coverage gap, not a negative result. If a gap is the next
useful step, record the needed action and continue independent useful work;
stop or hand off when no authorized path can advance the requested outcome.
There is no universal minimum source count.

Use `docs/modules/` and the public-record search planner for executable routes.
Corporate, corpus, legal and network worker templates are menus: instantiate only
the applicable operations and include the resulting source list in each mandate.

## Read enough of the source to support the question

Search snippets and extracted sections locate evidence; they do not establish
whole-document coverage. Retain canonical identity (accession, docket/document
ID, version or date), URL, and complete retrieved artifact. Read full opinions,
filings, contracts, or correspondence when the question depends on context,
qualifications, definitions, exhibits, or omissions. Use available model context
for sustained reading; choose sections or chunks when that improves accuracy or
accommodates tool/context limits.

Track sections/pages read, skipped material and reasons, cross-references still
to inspect, extraction/OCR limitations, contradictions, and exact supporting
passages. Follow material cross-references and inspect tables or renders when
text extraction loses meaning. Reopen the original passage before persisting a
load-bearing quotation. A character slice, search window, or model summary is
not the complete source. Report partial coverage if material sections remain
unread. Do not reread unchanged documents solely as a ritual; use the retained
coverage record.

Hypotheses and domain knowledge may guide collection, source choice, and useful
follow-up questions. Keep those working explanations distinct from what a source
establishes, test ordinary alternatives and counter-evidence, and persist them
with the correct claim type and confidence ceiling. Workflow roles do not forbid
reasoning or require another agent before a researcher can verify a pattern.

## Reuse a result, not a historical log entry

`check_searched` describes prior work. A matching historical row alone never
justifies skipping a new search. Reuse requires the same source, operation,
query, all filters and limits, a successful complete response, and an intact
output artifact. A dynamic source also needs a freshness bound; a fixed corpus
needs an exact immutable version. Use `tools/search_reuse.py`, which shares
`canonical_search_key` with query tools and leaves legacy history untouched.

Create a request JSON without credentials or pagination cursors:

```json
{
  "source": "courtlistener",
  "operation": "search",
  "query": "<target>",
  "filters": {"jurisdiction": "<jurisdiction>", "limit": 25}
}
```

Use the actual operation/filter names and every value affecting coverage. Add
`source_version` only for an immutable corpus snapshot; do not invent a version.
Choose `max-age-hours` for the task's freshness needs, rather than inheriting an
old source-specific default. A missing or unusable result means run the query.

```bash
uv run python tools/search_reuse.py check \
  --request-file "$WORKDIR/search-request.json" --max-age-hours 24 \
  --output "$WORKDIR/search-reuse.json"
```

Read `reusable` and `reason`. If true, inspect the returned artifact and record
`reused` with its scope; otherwise execute the planned source query. After
inspecting a complete response, record its actual count and output artifact:

```bash
uv run python tools/search_reuse.py record \
  --request-file "$WORKDIR/search-request.json" --outcome success \
  --result-count 0 --artifact "$WORKDIR/search-results.json" \
  --output "$WORKDIR/search-recorded.json"
```

Replace zero with the actual count. Use `partial`, `failed`, or `unavailable`
for those outcomes. An error-shaped or truncated response is not `success`.
Retain the normal `log_search` audit entry; the reuse record does not replace it.
Deleting or editing the artifact invalidates reuse, so temporary outputs offer
reuse only while they remain available.

## Evidence and worker handoffs

Each source category has one search/persistence owner. Workers receive the pinned
profile/database, factual question, applicable sources, unique outputs, and the
expected report path. The parent collects every expected report or records an
explicit incomplete handoff before synthesis.

Store claim type, confidence ceiling, canonical evidence references, exact
`ref:quote` pairs, and source tokens using the tracker APIs. Preserve the source
artifact and distinguish the existence of a statement from its truth. Correct
existing findings through `findings_tracker.py correct` so normalized fields and
the correction trail stay synchronized. New synthesis cites its underlying
evidence and calculation/report artifact, not only an analysis-run label.

Reports include completed/reused/unavailable/partial coverage, finding and entity
IDs, bounded negative results, contradictions, unresolved questions, and artifact
paths. A zero supports only its searched scope. Test likely alternate explanations
before inferring intent or coordination; record collection gaps separately from
observed inactivity. Follow the shared methodology's competing-hypothesis and
confidence rules. Finding counts measure work, not truth or narrative importance.
