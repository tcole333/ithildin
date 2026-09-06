# Property identity integration fixes

Completed the bounded Palm Beach and Texas ingestion task. Four reported failures reduce to one real parser/ingester jurisdiction mismatch and two stale or inconsistent test expectations. Occurrence/provenance storage was preserved. No Git mutations, live queries, or live database changes were made.

## Actual implementation defect

`query_palm_beach_tax_deeds.parse_detail` emits the shared `JurisdictionMetadata` representation, whose full county GEOID is in `county_fips` and whose county name is in `locality`. `tools/ingest_property_records.py:834` previously read only `county_geoid` or `state_fips`; real parser output therefore could not project a tax-deed case at all. This was not merely an old fixture: the tests obtain their records through the production parser.

The helper now accepts `county_fips` as the shared alias and uses `locality` when an explicit `county_name` is absent. Conflicting nonempty `county_geoid` and `county_fips` values are rejected. Numeric GEOID validation and the tax-deed mapper's required Palm Beach county `12099` remain enforced. No default county is invented for missing or invalid source metadata. The source observation retains its original jurisdiction object rather than rewriting the preserved record to match projection columns.

Tests assert the normalized jurisdiction row and original observation metadata, continued legacy `county_geoid` support, and rollback of both the envelope observation and projections for missing, short/ambiguous, different-county, state-only, and conflicting county identifiers. Existing tests continue to prove later appraiser adoption of a tax-deed parcel shell preserves the parcel ID, tax-deed observation, tax-event provenance, aliases, and event links, without creating current-title ownership assertions.

## Test contract corrections

- **Palm Beach repeated addresses:** The two fixture occurrences share street/address text but the second omits locality/postal fields. `_address_identity` includes those fields, and the incomplete snapshots correctly retain both address assertions. The test now compares all four complete/incomplete address rows, including their open status, and verifies replay inserts no additional address assertions. It still requires both OBJECTID observations, a single exact candidate parcel shell, no PARID alias, and no recorded-title instrument creation. The production address behavior was not changed.
- **HCAD unlinked occurrences:** The old fixture created a linked normalized feature, removed several parcel keys afterward, and left the linked `feature_ref` behind; it then incorrectly expected the ingester to discard that full reference in favor of a bare OBJECTID. The fixture helper now accepts absent raw account fields before calling the production normalizer. Two unlinked features (`99`, `100`) must retain separate fully qualified `unlinked:OBJECTID` references, raw occurrence IDs, null join keys, and no parcel projection. No occurrence mapper, canonical reference, or source adapter implementation was changed.

## Changed files

- `tools/ingest_property_records.py` — shared county-field compatibility and conflicting-alias rejection only.
- `tests/test_ingest_palm_beach_property_appraiser.py` — full address identity and replay assertions.
- `tests/test_ingest_palm_beach_tax_deeds.py` — original/normalized jurisdiction assertions plus six compatibility/rejection cases.
- `tests/test_ingest_texas_property_sources.py` — coherent raw unlinked fixtures and distinct retained-reference assertions.

## Validation

- Reproduced with `uv run pytest --offline -q` on all three assigned test files: **4 failed, 5 passed**. Log: `/tmp/osint-CUTDyZF1/property-identities-baseline.txt`.
- After fixes, those same files: **15 passed in 0.61 seconds**. Log: `/tmp/osint-CUTDyZF1/property-identities-fixed.txt`.
- Proportionate adjacent offline tests: `tests/test_ingest_property_records.py`, `tests/test_ingest_palm_beach_tax_collector.py`, `tests/test_query_palm_beach_tax_deeds.py`, and `tests/test_query_hcad_gis.py`: **84 passed in 1.96 seconds**. Log: `/tmp/osint-CUTDyZF1/property-identities-adjacent.txt`.
- `uv run ruff check` on all four changed Python files: **passed**.

The reproduced jurisdiction papercut was recorded and resolved as **#1 in the isolated task database `/tmp/osint-CUTDyZF1/property-identities-papercuts.db`** via `ITHILDIN_DB_PATH`. This respects the task's explicit prohibition on live DB changes; no production papercut or investigation rows were written.
