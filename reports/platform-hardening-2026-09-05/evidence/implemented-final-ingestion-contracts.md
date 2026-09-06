# Final ingestion contract integration

Completed the four assigned failures and the parent-authorized shared schema-cache repair. No live DB/API operations or Git mutations were performed.

## Findings and changes

1. **Marion roll-year identity was an implementation defect.** `query_oregon_marion_downloads` publishes `roll_year` from `TYYYY`, but `tools/ingest_property_records.py:811` previously only inspected `tax_year`, selected raw fields, and a revision-date fallback. Parcel adoption therefore persisted an empty year despite the assessment retaining 2026. `_roll_year` now accepts the explicit normalized `roll_year` field after `tax_year`. Existing sale-shell adoption, transaction-party versus owner scopes, observation provenance, and instrument/title limits remain asserted. The new integration test at `tests/test_oregon_marion_downloads_shared_integration.py:412` verifies separate 2025/2026 parcel snapshots for the same account, stable replay IDs, matching assessment years, preserved source-occurrence IDs, append-only envelope/record observations, and no ownership or recorded-instrument creation.

2. **Orange portal owner shape was an implementation defect.** `tools/query_orange_tax_collector.py:879` now exposes canonical `raw_name` from the explicit source `name`, matching the bill-detail and historical branches. Existing source entity fields remain intact, including the composite `external_id`; assertion type stays `tax_account_owner_label` and title caveat stays `not_a_title_chain`. The original failing test now also checks these fields. A new missing-name test at `tests/test_query_orange_tax_collector.py:191` verifies the composite address label is never substituted for an absent owner name. Removed an existing unused test import while linting the owned file.

3. **DCA and Virgin Islands projection contracts were already correct; full-suite failures exposed a shared database-cache defect.** Both clean-suite failures occurred only when their local query called real `log_search` against a DB lacking `search_log`. A focused baseline reproduced Marion and Orange only (**2 failed, 33 passed**), confirming the different trigger. `tools/lead_tracker.py:105` and `:566` now cache schema initialization per actual connected database file and schema state rather than one process-wide boolean. The cache uses device/inode, SQLite schema counter, and a digest of `sqlite_master`; this detects replacement or structural damage even when inode/counter values repeat. Ordinary data writes preserve cached initialization. Initialization is serialized within the process, explicit `_schema_initialized=False` invalidation is retained, independent in-memory/temporary connections bypass the path cache, and failed initialization closes its connection.

   `tests/test_lead_tracker_schema_cache.py` has six regression cases: switching A→B→A while logging and preserving per-DB history; deleted path; replacement file with repeated schema counter; same-file/same-counter schema damage; separate in-memory connections; and explicit invalidation. Tests count actual `_ensure_schema` calls to prove the unchanged schemas remain cached. DCA and VI integration tests additionally pin their own real logging databases and assert the local operation/source/count plus immutable history entry. Their complete regulatory identity, no-title, canonical claim reference, and limited-stub assertions remain in place; logging was not stubbed away.

## Owned paths

- `tools/ingest_property_records.py`
- `tools/query_orange_tax_collector.py`
- `tools/lead_tracker.py` (expanded scope explicitly authorized by root)
- `tests/test_lead_tracker_schema_cache.py` (new)
- `tests/test_new_jersey_dca_shared_integration.py`
- `tests/test_oregon_marion_downloads_shared_integration.py`
- `tests/test_query_orange_tax_collector.py`
- `tests/test_query_state_courts_vicourts.py`

## Verification

- **43 focused tests passed in 1.51 seconds**, `--offline`, covering all four assigned modules plus schema-cache regressions. `/tmp/osint-CUTDyZF1/final-ingestion-focused.txt`.
- **168 adjacent tests passed, 3 skipped in 12.15 seconds**, `--offline`. The three skips are existing opt-in official Lane/Marion ArcGIS probes, not deterministic tests. `/tmp/osint-CUTDyZF1/final-ingestion-adjacent.txt`.
- Ruff passed on all eight owned Python paths.
- Papercuts **1–3** were logged and resolved only in `/tmp/osint-CUTDyZF1/final-ingestion-papercuts.db`.

All test commands used explicit task-local `ITHILDIN_DB_PATH` and `ITHILDIN_PROFILE=epstein`; individual fixture DBs were independently selected. No live response freshness or external factual validity is claimed by these deterministic checks.

Adjacent selection:

```bash
uv run python -m pytest --offline -q \
  tests/test_ingest_property_records.py \
  tests/test_query_oregon_lane_marion_parcels.py \
  tests/test_query_oregon_marion_downloads.py \
  tests/test_oregon_marion_downloads_lifecycle.py \
  tests/test_ingest_orange_tax_collector.py \
  tests/test_orange_tax_collector_shared_integration.py \
  tests/test_query_new_jersey_dca_property.py \
  tests/test_new_jersey_dca_catalog_monitor.py \
  tests/test_query_vicourts.py \
  tests/test_core_schema_bootstrap.py \
  tests/test_lead_tracker_related_validation.py \
  tests/test_lead_tracker_fk_migration.py \
  tests/test_findings_tracker_evidence.py
```
