# USAspending acquisition and output fixes

Implemented in `tools/query_usaspending.py` with existing regression assertions updated and a new `tests/test_query_usaspending_failures.py` suite. No external API requests, Git operations, or production database writes were performed.

## Behavior

- Every command now writes a consistent structured envelope for `--output` / `--json`: `query`, `retrieval`, `status`, `errors`, and `results`. Retrieval records timestamp, endpoint, HTTP method, exact POST payload, request outcome, returned count, and available upstream pagination/messages.
- Successful empty responses remain `status: success`, `results: []`, and `errors: []`.
- HTTP, connection, timeout, incomplete-read, JSON/encoding, and response-shape failures write an error artifact before exiting 1. They cannot print a successful “No recipient found” / “No COVID awards” conclusion. Failed invocations cannot inherit or leak another invocation's error state.
- Recipient lookup retains the matched recipient when the agency query fails: `status: partial`, recipient in `results` and the existing top-level `recipient`, `spending_by_agency: null` to indicate unknown spending, and a nonzero exit.
- COVID searches retain rows from successful award-type groups after another group fails. Per-group pagination, unqueried groups, and omitted counts disclose limit-driven coverage gaps.
- Keyword transaction pagination preserves prior rows when a later request fails and records the failed page as the retry continuation. The existing 50-page cap remains bounded and now emits `status: partial`, `errors: []`, `pagination.next_page`, and `stopped_reason: page_cap` with exit 0.
- `transactions-keyword --page N` supports resuming at the recorded continuation. A resumed response does not claim coverage of preceding pages. `retrieval.complete` is null when the API does not report pagination coverage.
- Saved-file keyword queries preserve source query/retrieval context, pagination and partial state; missing, malformed, invalidly encoded, or previously failed saved responses no longer silently succeed.
- Award resolution preserves candidate rows when resolution fails and refuses to assert a unique PIID match when the resolution search reports another page. Detail acquisition failures now produce the same structured error artifact.
- Subaward scope validation still fails closed: an error artifact contains no out-of-scope result rows.

## Intentional compatibility changes

- Commands that previously emitted bare JSON lists now place those lists under `results`. Consumers should read `payload["results"]` and inspect `status`/`errors` before drawing a no-results conclusion.
- Existing recipient fields (`recipient`, `spending_by_agency`), award detail fields, transaction scope-disclosure fields, and transaction pagination keys remain available at the top level. Award detail also appears as a single row under `results`.
- Failed commands now produce the requested output file and exit 1; older tests expecting no output file were updated to assert an error envelope with no result rows. This retains the fail-closed guarantee while making failures auditable.
- A successfully requested page can have `status: success` and `retrieval.complete: false`; request success does not imply full search coverage. The keyword safety cap explicitly reports partial status.
- Updated the module's usage example from the nonexistent `uei` subcommand to `awards --uei`, and documented the new output/exit contract in its module docstring.

## Verification

`uv run ruff check tools/query_usaspending.py tests/test_query_usaspending*.py` — passed.

`uv run python -m pytest tests/test_query_usaspending.py tests/test_query_usaspending_papercuts.py tests/test_query_usaspending_subawards.py tests/test_query_usaspending_failures.py -q` — **61 passed**.

The new HTTP fixtures exercise all twelve list/search handlers for empty success and connection failure, plus partial recipient/COVID/keyword retrieval, malformed response variants, timeouts/incomplete reads, cap continuation/resume, file replay failure, machine-readable error stdout, command-state isolation, and CLI failure exit codes. Existing transaction identifiers, agency filtering, subaward scoping, award resolution, and captured keyword fixtures continue to pass.

## Files

- `tools/query_usaspending.py`
- `tests/test_query_usaspending.py`
- `tests/test_query_usaspending_papercuts.py`
- `tests/test_query_usaspending_subawards.py`
- `tests/test_query_usaspending_failures.py` (new)
