---
name: build-infra
description: Implement an infrastructure queue request, or scan platform source gaps and create requests. Use ingest-source for a named dataset and add-registry for a corporate registry adapter.
user-invocable: true
---

# /build-infra

No arguments selects the next open request; an ID selects a specific request;
`scan` audits gaps and creates justified requests. Use
[the source integration contract](references/source-integration.md) for endpoint
discovery, implementation, isolated tests and completion requirements.

## Build a request

Pin the task context using `docs/RESEARCH_WORKFLOW_CONTRACT.md`, create an
isolated workdir, and inspect the request before claiming it:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/infra_tracker.py next
uv run python tools/infra_tracker.py show "<ID>"
uv run python tools/infra_tracker.py claim "<ID>"
```

If there is no open request, report that state; scan when requested or when a
relevant unmet need makes it useful. Existing queue work and prior evaluations
are evidence to inspect, not instructions to repeat obsolete implementations.

Probe the observed access route before coding, then record the result:

```bash
uv run python tools/infra_tracker.py evaluate "<ID>" \
  --probe-results "<observed URL, response format, tested scope, access limits>" \
  --proceed
```

Paid, registered, physical and request-based routes can still be useful.
Retain supported adapters, catalog entries and reproducible human actions.
Use `--block` for an unmet implementation dependency; reject only invalid,
duplicate, superseded or unusable requests. The current `evaluate --help`
documents these state transitions. Do not treat a failed probe as a zero-result
source or fill gaps with guessed endpoints.

When the primary route is partial or difficult, assess complementary official
routes—such as indexes, opinions, notices, bulk archives or copy requests—and
record their distinct fields/periods. Preserve raw occurrence grain, blanks,
whitespace and sentinel encodings before projecting entity joins.

Implement and validate the smallest useful integration under the linked contract.
Use native chat workers when independent adapter/fixture tasks help, with inherited
model settings and explicit non-overlapping file ownership; the parent integrates
and tests the result. Keep user steering and ongoing work in this chat.

After the tool, fixtures and documentation meet acceptance criteria, complete
the request with the actual changed paths and validation summary:

```bash
uv run python tools/infra_tracker.py complete "<ID>" \
  --tool-file "tools/query_<source>.py" \
  --files-modified "tools/query_<source>.py" "tests/test_<source>.py" "docs/modules/<module>.md" \
  --summary "<capabilities, verified coverage, checks, retained limitations>"
```

Completion can unblock dependent leads, so it requires a working deliverable
rather than a speculative scaffold. Preserve partial work and note the exact
remaining dependency if completion is not yet supported.

## Scan gaps

Read source health, canonical modules, `docs/TOOL_REFERENCE.md`,
`research/OSINT_RESOURCES.md`, and existing open/evaluating/blocked requests.
Use current CLI help for focused inventory queries:

```bash
uv run python tools/source_report.py
uv run python tools/infra_tracker.py list --help
uv run python tools/infra_tracker.py search --help
```

Compare required coverage with actual capabilities. Inspect repeated failures
or zero searches in the **selected database**, distinguishing source applicability,
query quality, stale data and access errors. A platform-wide scan may deliberately
aggregate profiles; state that scope. Any direct SQL audit must open the pinned
database in read-only mode and use live schema names.

Create requests for useful, non-duplicate gaps with confirmed source/access facts,
expected coverage, priority reasoning and a concrete acceptance test.
`infra_tracker.py add --help` owns required fields and enum values; do not copy
a generic request whose source facts have not been observed.

Return healthy/problematic sources, created or existing request IDs, supporting
artifacts, access dependencies and next priorities. Finish when the requested
scan scope is accounted for; broad discovery can be continued from a saved
coverage list without restarting or imposing an arbitrary source quota.
