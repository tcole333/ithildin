# Public-records integration repair

Implemented the bounded DOJ, Florida DOR, and Mason County integration task. No source acquisition, production data repair, Git mutation, source catalog rollback, gate relaxation, or deterministic-test skip was used.

## Proven defects and fixes

1. **Negative spatial selectors were parsed as flags.** The existing Mason integration cases for `point -123.1,47.2` and `bbox -123.2,47.1,-123.0,47.3` failed in `argparse` before reaching the adapter. `tools/query_property.py:17604` now recognizes exact numeric coordinate tuples as positional arguments only in the point/bbox subparsers. The other subcommands and option parsing retain their existing behavior. Regression assertions cover comma and whitespace pairs, a negative bounding box, options on both sides of the selector, preserving coordinates and caller limit, rejection of an unknown option, and rejection of mixed positional/explicit coordinates.

2. **DOJ source validation escaped its result envelope.** `tools/query_state_courts.py:7713` called `_canonical_case_url` in the translator. Invalid case selectors raised `DOJCourtRecordsError` (a source-specific RuntimeError) before the direct adapter could encode its normal error result. The translator now passes the selected URL to the existing direct adapter. Its client validates/canonicalizes the selector before HTTP, and `_case_result` catches the domain error into `PublicRecordsResult`. The new end-to-end shared-router tests at `tests/test_doj_court_records_shared_integration.py:185` prove `invalid_case_url` and `unofficial_url` retain status, category, retryability, and detail in the shared output; a session stub rejects any HTTP attempt and verifies client closure. Unsupported shared filters still raise the intended ValueError. The old test expecting a translator ValueError for malformed case URLs was replaced by these stronger execution assertions.

## Verified test contract drift

- DOJ and Mason source lifecycle assertions used the old manifest input key `jurisdiction_geoids`. `PublicRecordsCatalog` deliberately normalizes that to `jurisdictions` objects and removes the shorthand. Tests now assert the exact GEOIDs through those normalized objects; no catalog code or configuration was changed.
- Florida tests described geometry decoding as pending request #314. The catalog, implementation, and documentation already describe native CRS geometry projection. The existing synthetic `test_gis_pin_projects_native_geometry_without_losing_occurrences` passes: four source features are retained, blank/repeated join occurrences survive, two geometry rows are created, and repeat ingestion is idempotent. Lifecycle tests now assert the implemented state, exact projection list, joinable-only parcel geometry creation, native feature/collection output, and the existing prohibition on recorded-title instruments or surveyed-boundary interpretation. Documentation assertions check the implemented concepts instead of a stale request number.
- Two Mason assertions had drifted from current prose ("usable business join key" and "treasury balance/payment history"). They were updated to current wording; the scope and identity semantics remain asserted.

## Files changed in this task

- `tools/query_property.py`
- `tools/query_state_courts.py`
- `tests/test_doj_court_records_lifecycle.py`
- `tests/test_doj_court_records_shared_integration.py`
- `tests/test_fl_dor_property_lifecycle.py`
- `tests/test_mason_county_tax_parcels_lifecycle.py`
- `tests/test_mason_county_tax_parcels_shared_integration.py`

No source-specific ingester, docs, or catalog configuration needed modification. Pre-existing working-tree changes belong to their existing owners.

## Validation

- Baseline five assigned modules: **9 failed, 26 passed**, 48.74 seconds. Log: `/tmp/osint-CUTDyZF1/records-current-tests.txt`.
- Fixed five assigned modules: **40 passed**, 27.29 seconds. Log: `/tmp/osint-CUTDyZF1/records-fixed-tests.txt`.
- DOJ shared integration repeated after aligning the no-network stub with the client's actual `session.request` call: **14 passed**, 0.45 seconds.
- Existing Florida geometry occurrence-preservation test: **1 passed**, 0.08 seconds.
- `uv run ruff check` on all seven changed Python files: **passed**.
- Explicit `--offline` verification of the two existing shared point parser tests, direct DOJ tests, direct Mason tests, Florida shared integration, and Florida ingestion: **53 passed**, 32.41 seconds. External sockets were disabled. Log: `/tmp/osint-CUTDyZF1/records-adapter-offline.txt`.
- An optional broad rerun adding all shared property/state-court router tests was interrupted after **43 passed in 164.55 seconds** because those modules repeatedly reload the large source catalog. It produced no assertion failure before interruption and is **not claimed as a completed validation**. Its interruption trace is in `/tmp/osint-CUTDyZF1/records-adjacent-tests.txt`. The five assigned modules, meaningful new regressions, existing affected parser tests, and direct adapters all completed; no assigned deterministic test was skipped.

Papercut **#2732** was logged with the reproductions and resolved after the assigned tests and lint passed. No changes were made to root's unrelated tax-parcel identity work.
