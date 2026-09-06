# Source integration contract

Use this reference while implementing a new source adapter or onboarding a
dataset. The calling skill owns the target, queue state and specialized schema;
this reference owns the common implementation and verification expectations.

## Context and access

Read `docs/GIT_WORKFLOW.md` for file ownership and
`docs/RESEARCH_WORKFLOW_CONTRACT.md` for pinned profile/database and source
applicability. Keep the current chat responsible for integration and completion.
Native workers inherit model choice and pinned context, use unique artifacts
and non-overlapping files, and return evidence/validation handoffs.

Probe a source-observed endpoint or inspect an actual bulk file before coding.
Record URL, request parameters, response/record grain, coverage/version,
authentication, rate limits and failure behavior. Preserve a bounded response
fixture with its source provenance. A 200 response alone does not establish
valid data: confirm content, schema and expected target/record identity.

For partially available, paid, registered, offline or request-based sources,
record the viable access route and complementary official coverage. An adapter,
catalog entry or reproducible human action can be the right deliverable.
Proceed within existing authorization; report a precise unmet dependency when
credentials/access are necessary. Do not guess APIs or acquire non-public data
through unauthorized access.

## Adapter interface

Inspect the nearest current tool and tests, `docs/modules/<category>.md`,
`docs/TOOL_REFERENCE.md`, `tools/output_util.py`, and `--help` before extending
an interface. Add only the operations supported by the source and needed by the
investigation. The common contract is:

- CLI help explains inputs, scope, defaults, output schema and limitations.
- `--output` uses the shared output utility for complete machine-readable
  artifacts and bounded stdout; optional stdout JSON follows the existing convention.
- Records retain stable source identity, source URLs, query filters and
  pagination/coverage metadata. An observed count is not automatically a total.
- Distinguish success with zero rows, partial results, unavailable access and
  parser/request failures. Preserve useful partial artifacts and return a
  truthful process status; retries are bounded to recoverable failures.
- Respect rate limits and preserve resume state for longer acquisitions.
  Verify repeated ingestion is idempotent and does not replace linked identities.
- Search logging follows `lead_tracker.log_search` and the research reuse
  contract. Scoped consumers honor `ITHILDIN_PROFILE` and `ITHILDIN_DB_PATH`;
  test databases must never fall through to the checkout database.
- Use the repository's `uv` dependency/runtime configuration. Retain only
  needed dependencies and keep credentials out of source, artifacts and logs.

Acquisitions belong in ignored data storage with a tracked source/version/
retrieval/checksum manifest. Temporary probes use an isolated workdir.
Preserve raw field values and occurrence identities; normalize joins only where
the source supports them. Follow schema-specific guidance for nullable fields,
history, updates and provenance.

## Acceptance and discoverability

Verify the implementation using meaningful isolated fixtures: known positive
identity, zero results, malformed/failed access, multi-page or truncated
responses, pinned database routing, repeat ingestion and resumability as
applicable. Tests should detect plausible source/interface failures rather than
asserting implementation details. Run changed-file lint and focused tests;
a successful live request or JSON parse alone is not sufficient.

Use a bounded real source check within authorized access when required to
confirm the adapter, retaining its provenance. State what offline fixtures
establish and what live access remains unverified.

Document capabilities and current commands in the canonical source module and
tool reference. Register structured citation types in
`web/src/lib/citations.ts` (one-off mappings in `web/src/data/source-urls.json`)
and health/readiness checks in `tools/source_report.py` where appropriate.
Update root inventories when their overview changes. Update a workflow skill
only when its task selection or interpretation needs new guidance; let the
canonical catalog expose new tools instead of copying menus across every skill.

Completion includes the adapter, reproducible tests, artifact/manifest paths,
discoverability updates, and a report of verified capabilities and retained
limitations. If a dependency blocks implementation, preserve completed work,
document the dependency and update the originating queue/request accordingly.
