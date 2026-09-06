---
name: add-registry
description: Add a state or country corporate registry adapter to the unified registry database. Use for jurisdiction-specific corporate registration, officer and filing ingestion.
user-invocable: true
---

# /add-registry

Accept a jurisdiction identifier. Read
[the source integration contract](../build-infra/references/source-integration.md)
for pinned context, verified discovery, output contracts and completion.
Use `docs/modules/registries.md` for current adapters/access routes, and inspect
`tools/query_registry.py` for the live unified schema instead of copying a
historical table/field inventory.

## Discover the jurisdiction

Identify available entity types, original IDs, dates, officers, agents, addresses,
filing history, raw documents and coverage gaps. Jurisdiction choice follows the
user's question and evidenced entity/address nexus, not a fixed priority-country
list. Inspect official documentation and the actual portal/API/bulk format;
record successful bounded probes, authentication, rate limits and limitations.

If anonymous machine access is unavailable, preserve useful paid/account,
manual/request or archive routes under the source integration contract. Do not
invent endpoint parameters or equate a CAPTCHA with absence of registry records.
Use native browser tools for interactive discovery where needed.

```bash
uv run python tools/query_registry.py --help
uv run python tools/query_registry.py search --help
uv run python tools/query_registry.py jurisdictions
```

Reuse a suitable existing adapter where possible. Inspect representative raw
records before mapping fields; preserve original values, occurrence identity and
source URLs. Source-jurisdiction codes follow the existing registry conventions.

## Implement stable entity identity

Build `tools/ingest_<jurisdiction>.py` with query and ingestion operations
appropriate to the verified access route. Use the live schema from
`query_registry.py` and the stable-ID update pattern in
`ingest_florida.py`; add output handling, bounded errors and provenance.

Entity identity is the natural key `(source_jurisdiction, source_id)`, with a
stable internal ID referenced by officers, agents, filings and name history.
Update the existing entity in place; replacement deletion breaks those links.
A minimal pattern, extended only with actually observed source fields:

```python
def upsert_registry_entity(db, jurisdiction, source_id, entity_name, source_url):
    row = db.execute(
        """
        INSERT INTO registry_entities (
            source_jurisdiction, source_id, entity_name, source_url
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(source_jurisdiction, source_id) DO UPDATE SET
            entity_name = excluded.entity_name,
            source_url = COALESCE(excluded.source_url, registry_entities.source_url),
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (jurisdiction, source_id, entity_name, source_url),
    ).fetchone()
    return row[0]
```

Persist related rows against that returned ID in a transaction. Preserve
historical officer/filing/name occurrences and distinguish missing values from
source-confirmed removal. Idempotency includes rows with nullable key fields:
SQLite uniqueness may not deduplicate NULL-containing keys automatically.
Record source fields, record IDs, dates and raw-artifact references so the
mapping can be audited. Rebuild/update the relevant search indexes through the
current registry implementation.

## Verify and deliver

Use isolated database fixtures for first ingest, repeat ingest, changed data,
partial data, empty results and failures. Assert the entity ID remains unchanged,
related officer/agent/filing rows survive, duplicate history is not introduced,
and rollback preserves a prior valid state. Query through the unified CLI to
verify discoverability and indexed field behavior.

Choose bounded live verification targets from the pinned profile only when they
are applicable to the jurisdiction. Prefer the profile artifact or supported
findings tracker over an unscoped checkout-database query. Read enough source
records to resolve mapping ambiguity; there is no fixed target/page quota.

Complete the source-integration documentation, citation and health registration;
update affected skill guidance only where task decisions need new information.
Report access route, mapping, coverage, test results, acquisition manifest and
remaining gaps. Keep parallel work under native chat supervision with inherited
models and explicit file ownership; preserve resumable progress until the
requested adapter is validated or its exact dependency is documented.
