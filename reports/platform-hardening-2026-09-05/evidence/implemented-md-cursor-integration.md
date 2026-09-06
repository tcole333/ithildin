# Maryland estate notices and claims: bounded results

Reproduced the reported failure in the current checkout: `tests/test_query_md_estate_notices_claims.py` had 1 failure and 11 passing tests. Both notice and claim searches constructed `PublicRecordsResult.success` after issuing a continuation cursor. The shared success constructor deliberately returns `ok` for a successful page; it cannot infer whether a source-specific collector promised full traversal. This collector defaults to all native pages, and its neighboring Maryland estate-index adapter already reports an explicit caller limit as partial coverage. The fixture expectation was therefore valid.

## Changes

- `tools/query_md_estate_notices_claims.py`: both search paths use a small shared result constructor. When a caller limit leaves records available, the envelope is `partial` with the existing snapshot-bound cursor and an explicit `caller_result_limit` pagination diagnostic carrying `source_total` and `emitted_through`. Records, source artifacts, warnings, and retrieval time are preserved. Completed traversal remains `ok`, and authoritative empty results retain their existing `no_results` path.
- `tests/test_query_md_estate_notices_claims.py`: retained the failing assertions and added checks for the bounded-coverage diagnostic. Added synthetic full native pages (20 plus 1 rows) to verify continuation across page boundaries without duplicate or skipped identities, exact claim-detail enrichment, omitted and exact limits, final completion, and cursor rejection after source/query/snapshot/schema/count changes. Existing abbreviated HTML fixtures remain unchanged.

No cursor encoding, source identity, query binding, snapshot validation, endpoint, access policy, or shared result constructor behavior was weakened or changed.

## Validation

`uv run pytest tests/test_query_md_estate_notices_claims.py tests/test_md_estate_notices_claims_shared_integration.py tests/test_public_records_contract.py -q --offline -p no:cacheprovider`

**40 passed in 7.49 seconds**, including 16 added parametrized regression cases.

`uv run ruff check tools/query_md_estate_notices_claims.py tests/test_query_md_estate_notices_claims.py` passed. `git diff --check` passed for both owned paths.

No network requests, live database operations, or Git mutations were performed. Integration fixtures used their isolated temporary databases.
