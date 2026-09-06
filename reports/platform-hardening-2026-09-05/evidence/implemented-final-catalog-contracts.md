# Final catalog/shared-route integration fixes

Four failures from `/tmp/osint-CUTDyZF1/full-offline-current.txt` were traced against the current source. They required a missing implementation-status entry and test-contract corrections; no acquisition guard or adapter implementation needed changing.

## Maryland MDP parcel points

The catalog, monitor handler, source citation, property module, CLI reference, and OSINT resource reference already described the implemented point adapter. The roadmap's implemented-property list omitted it. Added the adapter and source ID with the existing identity contract: `ACCTID` joins the same SDAT account, while `OBJECTID` preserves each ArcGIS occurrence. The entry explicitly retains withheld current-owner names and the lack of independent corroboration between representations. The existing integration assertion remains intact.

## New York attorney discovery

`PublicRecordsResult` deliberately freezes nested sequences internally; its public `to_dict()` envelope converts them back to JSON arrays. The test incorrectly compared the internal tuple against a list. It now checks the serialized envelope, preserving the exact expected route set, non-case projection, and field-gap assertions. No production result or source availability changed.

## Property source-selection and access-review guards

Two tests invoked the real investigation search logger without providing a fixture database. In a clean source copy this failed at missing `search_log`; in a populated checkout it could write to the live database. Each now captures and verifies the log call explicitly, including the source and `None` result count for an unexecuted search. The multiple-source test also asserts that live dispatch cannot occur before explicit source selection. The Orleans test retains its adapter-dispatch tripwire and verifies the `unavailable` / `access_review_required` result.

Tracing that missing-table exception also identified a separate production defect: `lead_tracker.get_db()` used a process-global `_schema_initialized` flag even when `DB_PATH` changed. This was reported to the task owner, who assigned the core initialization fix and separate/recreated-database regressions to `workflows_review`. It is not hidden by, or claimed as fixed by, the hermetic guard tests here.

`tools/query_property.py` was inspected but not edited by this subtask. No live endpoint requests, live database mutations, or Git mutations were performed.

## Verification

- `uv run ruff check tests/test_md_mdp_parcel_points_shared_integration.py tests/test_ny_attorneys_shared_integration.py tests/test_query_property.py` — passed.
- Changed-path `git diff --check` — passed.
- `ITHILDIN_DB_PATH=/tmp/osint-CUTDyZF1/catalog-contracts-isolated.db uv run pytest tests/test_md_mdp_parcel_points_shared_integration.py tests/test_ny_attorneys_shared_integration.py tests/test_query_property.py --offline -q -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-final-catalog-contracts` — **243 passed in 158.78 seconds**.

## Owned changes

- `docs/PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md`
- `tests/test_ny_attorneys_shared_integration.py`
- `tests/test_query_property.py`

No change was needed in `tests/test_md_mdp_parcel_points_shared_integration.py`.

The reproduction above also supplies the task owner with papercut context; this bounded subtask was explicitly instructed not to write the live observation log.
