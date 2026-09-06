---
name: ingest-source
description: Onboard a named dataset, corpus, API or source URL with a reproducible query wrapper. Use build-infra for queued infrastructure and add-registry for a corporate jurisdiction.
---

# $ingest-source

Accept a source identifier or URL. Read
[the source integration contract](../build-infra/references/source-integration.md)
before acquisition or implementation. It owns pinned context, verified access,
artifact/provenance handling, dependencies, query contracts and completion tests.

## Characterize and access the source

Establish format, record grain, size, provenance, date/version coverage,
independence/overlap with existing sources, and relevance to the requested
investigation. Use the profile's corpus tools and applicable
`docs/modules/*.md`; historical case-specific sources are not universal defaults.

Verify actual endpoints, parameters, response schema and bulk file layout with
bounded discovery before writing the wrapper. For interactive portals, inspect
source-observed network/form routes through native browser tools as needed.
Preserve useful licensed/account/request routes if public machine access fails.
A failed access attempt is a coverage gap, not a negative search result.

Retain acquisitions under an appropriate ignored data directory with a tracked
manifest of source, retrieval/version, checksum, size and relative file path.
Keep probes and temporary transformations in an isolated workdir. Inspect the
actual header/schema and representative rows before joins or parser assumptions.
For large datasets, inspect schema/row groups or bounded samples before deciding
whether full materialization is practical.

Install durable dependencies through the repository's `uv` project workflow;
an isolated experiment can use `uv run --with <package> python ...` with its
dependency/version recorded. A global `pip install` does not define the project
runtime. Use `pyproject.toml` and current package documentation to select the
dependency and source access interface.

## Implement and smoke-test

Create the appropriate query/ingest adapter under the linked contract. Read a
similar current implementation and its tests; `--help` owns exact commands.
A text-search wrapper normally exposes `search`, `--limit`, structured
`--output` and optional JSON stdout. Specialized sources may need other
operations; implement the question's useful interface rather than a forced
generic search command.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show --output "$WORKDIR/profile.json"
PROFILE=$(jq -r '.name' "$WORKDIR/profile.json")
uv run python tools/findings_tracker.py list --profile "$PROFILE" \
  --limit 1000 --output "$WORKDIR/profile-findings.json"
```

Select test targets from the pinned profile and supported findings artifact,
checking source applicability and result limits. Include the primary subject or
key persons when this source can cover them; target quotas are not evidence of
coverage. Start with fixtures for positive, zero, partial and failed responses,
then run a bounded authorized source probe.

```bash
uv run python tools/query_<source>.py search "<APPLICABLE_TARGET>" --limit 10 \
  --output "$WORKDIR/ingest-source-smoke.json"
uv run python -m json.tool "$WORKDIR/ingest-source-smoke.json" >/dev/null
```

JSON validity alone is insufficient: verify expected fields, row identities,
evidence URLs, pagination/completeness and the distinction between zero results
and access/parser errors. Initial discoveries can become evidence-linked leads
when they answer a relevant new question; review existing work before adding them.

## Complete

Register the tool in the canonical source module/reference, citations and
health/readiness inventory as applicable under the source integration contract.
Report ingested record/version coverage, acquisition manifest, verified query
examples, isolated tests, evidence/lead IDs and remaining access/data gaps.
Supervise independent native chat workers when they help, inherit model settings,
and collect artifacts before integration. Continue from saved acquisition and
implementation state through long tasks rather than restarting or imposing
an arbitrary source-reading limit.
