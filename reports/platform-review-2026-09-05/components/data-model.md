# Core data model and provenance review

Reviewed current working-tree versions of `tools/lead_tracker.py`, `tools/findings_tracker.py`, `tools/entity_resolution.py`, profile/thread resolution, `tools/analysis_export.py`, and core model migration scripts. No production files or investigation records were changed. All behavioral repros used disposable SQLite databases under `/tmp/osint-SXYkyRSJ/data-model-fixtures/`. A live database audit used SQLite `mode=ro` and emitted aggregate counts only. Global active-profile switching is owned by the parent review.

## Ranked defects

### 1. P1 — Correcting the actual claim preserves its previous verification

**Location:** `/Users/travcole/projects/osint-research/tools/findings_tracker.py:1609`–`1615` (`update_finding`).

The correction path invalidates verification only for `claim_type` and `source_datasets`. Changing `summary`, `detail`, `target_name`, or `date_of_event` leaves `verification_status='verified'` and the former human verifier attached to materially different content. Evidence edits correctly invalidate verification through `_invalidate_verified_finding`, so the behavior is internally inconsistent.

**Verified repro:** Add and verify a quoted legal finding, then call `update_finding(fid, 'summary', 'An entirely different allegation.', 'Fixture correction')`. The stored result is `{'summary': 'An entirely different allegation.', 'verification_status': 'verified', 'verified_by': 'fixture-reviewer'}`. This is the supported correction API, not a raw SQL bypass.

**Impact:** A corrected allegation continues to look reviewed, even though that reviewer never assessed the new claim. The corrections history exists, but ordinary finding consumers read the stale verification flag.

**Smallest fix:** Define the fields that change the claim's meaning and invalidate verification when their values actually change. Keep the field update, audit entry, and invalidation in the existing transaction. Add a regression test for a verified finding corrected through this API.

### 2. P1 — A learned alias overrides explicit conflicting entity identity

**Location:** `/Users/travcole/projects/osint-research/tools/entity_resolution.py:481`–`499` (`resolve_or_create_entity`).

Alias lookup matches only the name and returns its entity ID before checking the requested jurisdiction, entity family, or EIN. The following exact/fuzzy paths contain jurisdiction guards, but the alias path bypasses them.

**Verified repro:** Resolve `Example Holdings LLC`, Delaware, EIN `11-1111111`; resolve the whitespace variant `Example  Holdings LLC` with the same identity, which creates a score-100 alias; then resolve that variant with Florida and EIN `22-2222222`. The third call returns the Delaware entity with `action='alias', score=100.0`; no Florida entity is created. Stored jurisdiction/EIN remain Delaware/`11-1111111`.

**Impact:** Once one task learns a spelling variant, another task researching a genuinely different same-name corporation can silently attach evidence and relationships to the first entity, despite supplying discriminating identifiers. Entities and aliases are shared across all profiles, broadening contamination.

**Smallest fix:** Validate the alias target against supplied jurisdiction, entity type family, and strong identifiers before accepting/backfilling it. On explicit conflict, fall through to an appropriately scoped resolution or raise ambiguity; never discard conflicting identifiers. Longer term, aliases need ambiguity-aware identity scoping rather than an unconditional name-only shortcut.

### 3. P1 — Corrections and verification bypass the mandatory confidence caps

**Locations:** `/Users/travcole/projects/osint-research/tools/findings_tracker.py:1555`–`1578`, `:1609`–`1615`, `:1625`–`1692`; compare insertion enforcement at `:1002`–`1013`.

`add_finding` applies both claim-type and source-provenance caps. `update_finding` does not recompute them after changing `claim_type`, `source_datasets`, or `confidence`. `verify_finding` validates references and quotes but never checks confidence against these invariants.

**Verified repro:** Add a `direct_quote` finding at `confirmed`; correct its type to `inference`; verify again. The result is `{'claim_type': 'inference', 'confidence': 'confirmed', 'verification_status': 'verified'}`. Separately changing its confidence from `low` to `confirmed` through `update_finding` is accepted and leaves it verified.

**Live read-only evidence:** There are 485 currently stored rows above the documented claim-type cap: 25 high inferences, 117 confirmed paraphrases, 10 confirmed syntheses, and 333 high syntheses. These counts demonstrate actual invariant drift, but do **not** prove this correction path originally created those rows; historical imports/raw writes may also contribute.

**Impact:** The platform can label an inference as confirmed through ordinary maintenance operations, undermining the core distinction between evidence and interpretation.

**Smallest fix:** Use one shared candidate-record validator on add, correction, and verify. Recompute/reject the effective confidence after any relevant change, audit any adjustment, and refuse verification of preexisting invalid rows. Review existing violations with their provenance rather than automatically promoting or reinterpreting them.

### 4. P2 — Correcting a finding's subject leaves its canonical entity link behind

**Locations:** `/Users/travcole/projects/osint-research/tools/findings_tracker.py:1609`–`1613`; linking exists only on insertion at `:1076`–`1078` and `:2126`–`2183`. Consumer: `/Users/travcole/projects/osint-research/tools/analysis_export.py:549`–`553`.

The target correction changes only `findings.target_name`. Its `finding_entities` subject link and `raw_name` still refer to the old person/organization. The entity-network exporter explicitly uses that junction table to determine profile membership.

**Verified repro:** Add a finding about `Original Company LLC`, then correct `target_name` to `Unrelated Organization Inc`. Joining the finding to its subject entity returns `('Unrelated Organization Inc', 'Original Company LLC', 'Original Company LLC')` for current target, canonical entity name, and link raw name.

**Impact:** The prose says the attribution was corrected while network analysis still assigns the evidence to the original subject. This can preserve a false relationship after an editorial correction.

**Smallest fix:** Reconcile the automatically generated subject link atomically when `target_name` changes; preserve unrelated manually asserted mentions, and record the old/new subject mapping. Handle an ambiguous new target explicitly instead of retaining a stale asserted link.

### 5. P2 — The historical connection-table rebuild loses columns and leaves foreign keys off

**Location:** `/Users/travcole/projects/osint-research/tools/lead_tracker.py:1378`–`1423`.

The migration for a connections table lacking the `owns` relationship builds a hard-coded replacement that omits `agent_run_id`, even though the column is added earlier in the same initializer. It also executes `PRAGMA foreign_keys=ON` while the replacement insert/drop/rename transaction is active; SQLite ignores that toggle until outside the transaction, leaving enforcement disabled on the returned connection.

**Verified repro:** Initialize an old-shape connections table containing one row with `agent_run_id='original-agent'`, then call the real `_ensure_schema(db)`. It returns with `foreign_keys=0`, no `agent_run_id` column, and accepts an orphan `connection_evidence` row for connection ID 999999. Thus the rebuild loses recorded agent provenance and disables the referential-integrity guard for the caller. A subsequent schema initialization can re-add the missing column but cannot recover discarded provenance.

**Scope:** This affects the historical upgrade path. The inspected live database already has the widened constraint, so this is **not** a claim that its current connections table is being rebuilt or currently has foreign keys disabled.

**Smallest fix:** Preserve all existing columns/indexes using the safer transactional rebuild approach already present in `_repair_stale_leads_foreign_keys`; restore the connection's original foreign-key setting in `finally` after commit/rollback; run `foreign_key_check`. Add a migration fixture containing provenance and dependent rows.

### 6. P2 — Fresh initialization does not install tables required by current commands

**Locations:** `/Users/travcole/projects/osint-research/tools/lead_tracker.py:481` (`_ensure_schema`), `/Users/travcole/projects/osint-research/scripts/migrate_core_model_v2.py:58`–`86`, and `/Users/travcole/projects/osint-research/tools/analysis_export.py:549`–`553`.

Current `get_db()` initialization creates neither `finding_entities` nor `finding_relations`; those exist only in the separately invoked core-v2 migration. The normal finding write silently skips entity linking when the junction is missing. Current profile-scoped entity-network export assumes the table exists.

**Verified repro:** Point `lead_tracker.DB_PATH` at an empty fixture, run `get_db()`, then `analysis_export.export_entity_network(profile_id='fixture-profile')`. It fails with `OperationalError: no such table: finding_entities`. The fresh database also lacks `finding_relations`, `investigation_profiles`, and `schema_migrations` after standard initialization.

**Scope:** This is a reproducibility/bootstrap defect. The live database has all four v2 tables and does not exhibit the missing-table failure. This review did not find an automatic bootstrap invocation of that v2 migration; the initializer's own contract is to create all investigation tables.

**Smallest fix:** Make one versioned migration/bootstrap entry point establish the current complete schema, and call it from normal database initialization. A fresh-db smoke test should exercise an actual finding write, relationship write, and profile-scoped export instead of manually adding the tables to test fixtures.

## Verification and artifacts

- `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/repro-data-model.py.txt`: reproduces findings 1–4 with fixture databases and the current production functions. Adds the v2 DDL explicitly to model the already-migrated live schema; stubs only name spelling canonicalization so no live DB is consulted.
- `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/repro-data-migrations.py.txt`: reproduces historical migration and fresh bootstrap defects separately.
- Run either from repository root with `PYTHONPATH="$PWD" uv run python /tmp/osint-SXYkyRSJ/<script>.py`.
- Existing targeted regression suite: `uv run python -m pytest tests/test_findings_tracker_evidence.py tests/test_lead_tracker_fk_migration.py tests/test_entity_identity_papercuts.py -q` → **21 passed**. These passing tests do not cover the defects above.
- No external research, network requests, investigation workflow mutations, or production patches were needed. Exploratory missing-file searches were ordinary review navigation, not repository workflow papercuts. The larger substantive defects are documented here for triage.

## Architecture observations and strengths

The appropriate improvement is a smaller and more consistent set of write invariants, not a wholesale replacement of SQLite. WAL, bounded busy timeouts, parameterized statements, typed evidence references, correction history, quote-span validation, atomic evidence editing, explicit directional relationship handling, and conservative export-time alias resolution are useful foundations.

The weak seam is semantic consistency across operations: add validates one set of rules, correct another, verify another, and raw SQL maintenance can bypass all three. A narrowly scoped finding mutation service should own validation, confidence, verification invalidation, temporal derivation, and subject-link reconciliation in one transaction. Keep CLI commands thin and reuse that service from imports.

Schema ownership is similarly fragmented: a 1,180-line `_ensure_schema` mixes table creation, recurrent data repairs, exception-driven column probing, direct `sqlite_master` changes, table rebuilds, and hard-coded investigation reassignments; a separate migration ledger already exists but is not the authoritative initializer. Adopt that ledger incrementally, with explicit historical migration fixtures and current-schema bootstrap tests. Avoid replaying data repair logic on every new CLI process.

Entity resolution has substantial guardrails in exact/fuzzy paths and handles ambiguity conservatively during export, but identity compatibility must apply before **every** resolution shortcut. Centralizing those checks is more valuable than adding further special-case name normalization rules.
