# Source adapters and ingestion review

Reviewed the current working tree, which contains extensive existing changes. This was an offline, read-only production-code/data review; only isolated fixtures and this report were written, plus the required friction observation #2718. No endpoint health claims were made and no remote services were queried.

## Highest-priority findings

### 1. [P1] Reimporting Florida registry data changes entity identity and strands existing evidence

**Location:** `/Users/travcole/projects/osint-research/tools/ingest_florida.py:416` (especially 418–430 and 478–479). Referenced schema: `/Users/travcole/projects/osint-research/tools/query_registry.py:64`, officer/agent/filing FKs at 100–148.

`cmd_ingest -> _ingest_corps -> _flush_batch` uses `INSERT OR REPLACE` against `(source_jurisdiction, source_id)` while omitting the entity's primary key. A repeat import deletes the old entity row and inserts another ID. The function deliberately disables foreign keys to allow that deletion, so preexisting officers, agents, filings, and name history continue to reference the deleted ID. Its apparent re-enable runs inside the write transaction and has no effect. The connection stays with foreign-key enforcement disabled after commit.

**Verified reproduction:** `sources-repro.py` creates the actual registry schema in memory, imports one Florida company/officer using the actual batch function, adds a filing, and repeats the identical batch. Output:

```text
original_id=1, current_id=2, fk_enabled=0
foreign_key_check=[registry_officers orphan, registry_filings orphan]
filings_visible_via_entity_join=0
```

This is evidence disappearing from normal queries after an ordinary refresh, not a cosmetic duplicate problem. No assertion is made here about the amount of damage in the live registry database.

**Narrow remedy:** replace entity `REPLACE` with `INSERT ... ON CONFLICT(source_jurisdiction, source_id) DO UPDATE` so IDs remain stable; remove FK toggling; keep each import batch transactionally consistent. Add a repeat-import regression with existing child history and an asserted `PRAGMA foreign_key_check`/enabled state. Separately assess already-orphaned records using recoverable source snapshots before attempting repairs.

### 2. [P2] Nullable registry uniqueness makes identical Ohio ingests accumulate agents

**Location:** `/Users/travcole/projects/osint-research/tools/ingest_ohio.py:678`–687; schema `/Users/travcole/projects/osint-research/tools/query_registry.py:121`–133. Related Florida inserts omit officer/agent effective dates at `ingest_florida.py:455`–474; officer uniqueness includes the same nullable field at `query_registry.py:115`.

Ohio `_upsert_entity` uses `INSERT OR REPLACE INTO registry_agents` but omits `effective_date`. Its uniqueness constraint is `(entity_id, agent_name, effective_date)`. Because the omitted date is NULL, identical rows do not conflict. Each refresh therefore inserts another copy. Florida's officer/agent `INSERT OR IGNORE` has the same uniqueness hole once entity identity is repaired.

**Verified reproduction:** call the real Ohio `_upsert_entity` twice with the same charter and same registrant using an in-memory schema: one entity, **two identical agent rows**.

**Impact:** inflated officer/agent search results and relationship counts; `OR REPLACE` suggests idempotence that the schema does not provide.

**Narrow remedy:** define explicit identity for undated current observations (for example, a partial unique index where effective_date IS NULL plus an UPSERT that refreshes current details), keeping dated history separate. Do not invent dates or erase distinguishable historic observations. Add same-input and changed-agent/address repeat-import tests. Audit sibling registry ingesters for the same SQL pattern.

### 3. [P2] USAspending transport errors become successful “no recipient” results

**Location:** `/Users/travcole/projects/osint-research/tools/query_usaspending.py:95`–101 and 198–206. A second failure-to-empty conversion occurs at 221–231. Many adjacent commands early-return after failed requests (e.g. 128–129, 513–515, 843–844), while `cmd_award_detail` correctly exits nonzero at 440–445.

`_fetch_post` prints HTTP/network failures and returns `None`. `cmd_recipient` combines that failure with an authoritative empty search and prints “No recipient found”; it returns normally before writing `--output`. If recipient lookup succeeds but the spending request fails, the saved summary instead silently contains `spending_by_agency: []` with no failure metadata. This leaves automation unable to distinguish an outage from an actual lack of spending.

**Verified reproduction:** patched only `urlopen` to raise `URLError('fixture offline')`, then called the real recipient command:

```text
stderr: ERROR: fixture offline
stdout: No recipient found matching 'FIXTURE'
return: None; requested output artifact not written
```

**Narrow remedy:** have the transport raise a typed request exception or return a typed outcome; at the command boundary always write the requested structured artifact and exit nonzero for failed acquisition. Preserve a partial recipient summary with the spending error when only the secondary request fails. Adopt the already-existing public-record outcome vocabulary instead of adding another bespoke result shape.

**Required friction logging:** recorded as papercut **#2718**. Left open because this is a review, not a code-change task.

### 4. [P2] FEC search-history keys collapse different cycles and filters

**Location:** `/Users/travcole/projects/osint-research/tools/query_fec.py:224`–242; consuming search-log behavior at `/Users/travcole/projects/osint-research/tools/lead_tracker.py:2276`–2299.

The donor request includes employer, cycle, state, and amount filters, but `_log(args.query, 'fec', total)` records only the name and source. Therefore a negative search confined to one cycle is indistinguishable from another cycle or an unrestricted donor search. `check_searched` compares those exact two fields, and `log_search` replaces the dedup row. The immutable history also lacks the omitted scope.

**Verified reproduction:** patched `_fetch` to return no matches, invoked `cmd_donor` for 2022 and 2024, and captured `_log`:

```json
[["FIXTURE", "fec", 0], ["FIXTURE", "fec", 0]]
```

**Impact:** research workflows can skip a materially different query as already searched or mistake a scoped negative for a broader negative. FEC's logged count is also the API's total rather than the number retrieved, a further inconsistency with newer adapters.

**Narrow remedy:** use `canonical_search_key` (already adopted by CourtListener, lobbying, Florida UCC, Massachusetts UCC, and OpenCorporates) for both lookup and logging. Include operation, filters, limit and cursor/page bounds. Preserve returned count, reported total, and completion separately; don't overload one integer. Migrate keys where scope is recoverable and label old keys as unknown scope.

## Strongest simplification opportunities

### A. Shrink the routers by giving adapters a consistent Python entry point

Measured with AST inspection of the current working tree (`source-metrics.py`):

| Component | Lines | Top-level functions | Calls to `parse_args` |
|---|---:|---:|---:|
| query_property.py | 17,953 | 150 | 49 |
| query_state_courts.py | 14,333 | 147 | 2 |
| public_records_monitor.py | 26,146 | 229 | 59 |

The monitor contains 167 `probe_*` functions. Across these three files there are 58,432 lines. Much is necessary source-specific knowledge, but its location forces one source addition to expand several central modules. The property router translates internal options into an argv list, invokes an adapter's argument parser, catches `SystemExit`, then invokes `execute`; see `query_property.py:10397`–10412 and 17452–17456. Numerous wrapper classes compensate for different adapter signatures, with instances at 481–535. The same adapter is represented again in source guidance, source manifests, routing tables, and monitor probe registrations.

**Recommendation:** incrementally move source-specific query translation and probe logic beside each adapter; expose a consistent `execute(query/options, access_decision=...)` and `probe(...)` Python API. Keep a small explicit registry of source IDs, capabilities, and module references. The CLI should parse once at its boundary. Reuse source-family primitives where formats actually match; retain jurisdiction-specific normalizers. Migrate a small family first and use its tests to prove no behavior changes. A dynamic plugin framework or generalized query language would add machinery without addressing the immediate problem.

### B. Extend existing contracts to legacy tools before inventing more infrastructure

The newer `public_records_contract.py` and `public_records_http.py` already distinguish no_results, partial, unavailable, restricted, rate_limited, and source_changed and accept injected transports. Older wrappers remain inconsistent: USAspending prints-and-returns, FEC has its own exception payload, LittleSis exits inside the HTTP helper, and EDGAR supports optional `raise_errors` on the same function. This is observable behavioral drift, not just style.

Across the 254 `query_*.py` and 31 `ingest_*.py` modules, 42 query modules define local `_log` wrappers and 19 source modules copy the old `.env` line parser even though `tools/env_loader.py` exists. The FEC loader at 71–79 strips only double quotes, while the shared loader also strips single quotes. These are good small, mechanical consolidations after tests establish expected semantics.

**Recommendation:** standardize only the boundaries: environment loading, outcome envelope, query key, output/error exit behavior, transport retry policy. Keep request construction and source-specific validation local. Add a reusable adapter contract test suite covering empty, failed, partial, malformed, rate-limited, and capped/paginated responses. That buys more reliability than testing ever more happy-path field mappings.

### C. Preserve completion information in artifacts, especially when agents consume only files

USAspending `cmd_transactions_keyword --all-pages` stops at 50 pages and prints a warning (`query_usaspending.py:837`–855), but writes only a bare results list. The artifact cannot tell a cap-limited response from an exhaustive one. A source error on a later page returns without saving already collected rows. Similar bare-list legacy outputs lack query scope and retrieval metadata. This was verified by code inspection, not by live calls.

**Recommendation:** emit the same envelope for interactive and file output, including query scope, retrieval time, returned/reported counts, `next_cursor`, and completion/error state. Preserve partial acquired rows when later pages fail. Avoid building a separate cache/audit layer until these semantics are explicit.

## What is well designed and should be kept

- Public-record result construction validates explicit status vocabulary and rejects an error-bearing `no_results` response (`public_records_contract.py:427`–437). Source/jurisdiction/query context is canonicalized and detached from mutable inputs.
- Socrata/ArcGIS HTTP clients accept injected transports, clocks, and sleepers; bound retries; surface access errors explicitly; reject schema errors; detect repeated pages; and carry continuation cursors/schema fingerprints. This is sound reusable infrastructure, not intrinsically overengineered.
- Newer adapters such as North Carolina (`query_nc_property.py:398`–481) preserve failure categories and complete query scope. Newer registry/entity code generally uses stable UPDATE paths rather than REPLACE, although child-row uniqueness still needs attention.
- Useful verification already exists for pagination, retries, response limits, malformed responses, and source-scope expansion. The best improvement is to connect these tested patterns consistently to every adapter/ingester.

## Verification and limits

Ran:

```text
uv run python -m pytest tests/test_public_records_http.py tests/test_public_records_contract.py tests/test_query_usaspending.py tests/test_query_usaspending_papercuts.py tests/test_ingest_ohio_downloads.py -q -p no:cacheprovider --basetemp /tmp/osint-SXYkyRSJ/pytest-sources
36 passed in 0.27s
```

Additional deterministic reproductions are in `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/sources-repro.py.txt`; counts in `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/source-metrics.py.txt`. Passing tests do not cover the four reproduced defects. No broad live-data migration, remote endpoint validation, or exhaustive review of all 285 source modules was performed. Read-only sampling included old/new financial and registry tools, ingest paths, public-record HTTP/contracts, routers, monitor plumbing, output/search utilities, and associated tests.
