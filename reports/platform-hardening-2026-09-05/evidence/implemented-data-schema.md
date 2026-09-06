# Implemented core schema fixes

Completed review defects 5 and 6. No live database was opened, migrated, or mutated for implementation or verification; all database operations used disposable pytest fixtures.

## Changes

- `tools/core_schema.py` is the authoritative location for core-v2 additive DDL and temporal columns. Its `ensure_core_model_schema()` installs them in a savepoint and records schema-only migration `2026-09-05_core_model_v2_schema` atomically. Existing caller transactions are preserved. Historical backfills remain separate and are not inferred from schema installation.
- `scripts/migrate_core_model_v2.py` imports the shared DDL/bootstrap function instead of maintaining a second DDL definition. Its existing backfill migration ID, `2026-07-04_core_model_v2`, is unchanged; `DDL` remains re-exported for compatibility.
- `tools/lead_tracker.py` calls the shared schema initializer during normal `_ensure_schema()` startup, so fresh databases have `finding_entities`, `finding_relations`, `investigation_profiles`, `data_change_sets`, and `schema_migrations`, plus precision-aware date columns.
- Extracted the existing metadata-preserving rebuild implementation into `_rebuild_table()` and reused it for stale-lead FK repair and historical connections CHECK widening. The connection migration retains actual table columns (including provenance and generated columns), arbitrary indexes/triggers, existing row IDs, dependent evidence/cascading child rows, and the highest AUTOINCREMENT sequence. It runs transactionally and restores the caller's original foreign-key setting after commit or rollback. Migration errors now propagate instead of being silently swallowed.
- Connection widening runs after stale-lead FK repair and compares `foreign_key_check` results before/after, rejecting new violations without treating unrelated preexisting integrity debt as damage introduced by this migration.

## Verification

`uv run ruff check tools/core_schema.py tools/lead_tracker.py scripts/migrate_core_model_v2.py tests/test_core_schema_bootstrap.py` — passed.

`uv run python -m pytest tests/test_core_schema_bootstrap.py tests/test_lead_tracker_fk_migration.py tests/test_connection_dedup_migration.py -q` — **12 passed**.

New tests exercise fresh normal initialization, real finding insertion with canonical entity links, typed finding relationship insertion, profile-scoped entity-network export, date normalization, idempotent migration recording, enforced junction FKs, additive upgrade without historical claim backfills, transaction/DDL rollback, legacy provenance/custom/generated-column preservation, custom indexes and working triggers, dependent-row preservation, ID sequence preservation, acceptance of newly supported `owns`, orphan rejection, and original FK-state restoration on both success and failure (initially on and initially off).

Existing stale-lead-FK/FTS and connection-dedup regressions also pass after sharing the rebuild helper. Broader finding/entity mutation tests are owned by the parent agent.
