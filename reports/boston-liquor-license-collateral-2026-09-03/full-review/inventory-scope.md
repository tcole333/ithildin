# Full roster inventory and UCC queue

The supplied Boston export contains **3,610 source rows and 3,593 license numbers**. The core alcohol-license inventory contains **1,522 rows, 1,512 license numbers, and 1,437 normalized legal-holder groups**. The broader queue contains **1,530 rows, 1,520 license numbers, and 1,444 holder groups**, including the boundary categories below. These are inventory counts, not counts of operating venues, current liens, common owners, or completed reviews.

| Scope | Rows | License numbers | Holder groups |
|---|---:|---:|---:|
| Explicit alcohol-license categories | 1,522 | 1,512 | 1,437 |
| BYOB permits, reported separately | 5 | 5 | 5 |
| Druggist and SPCMWA labels requiring category verification | 3 | 3 | 3 |
| Broad review queue, deduplicated across these categories | 1,530 | 1,520 | 1,444 |
| Excluded non-alcohol categories | 2,080 | 2,073 | 1,520 nonempty names |

Holder counts across category rows overlap. One core holder also appears in a boundary category. BYOB permits remain visible for completeness and are not treated as transferable alcohol-sale licenses. The ambiguous `Druggist` and `SPCMWA` labels remain queued for category review; no legal interpretation of those labels is inferred from the export alone. Pure `Common Victualler`, dormitory/lodging, no-liquor innholder, billiards, bowling, and fortune-teller types are excluded from the UCC queue. Every source row remains in the inventory. New, unknown categories are retained with an explicit review flag instead of silently excluded.

`source-licenses.csv` is the complete original export, copied from the session workdir without changes. Its SHA-256 is `95373009e2f8c566525838a8feabc77a8c4a4e7cb30b6428b926491f35be4ef9`. The source is the [Boston licensing dataset](https://data.boston.gov/dataset/licensing-board-licenses); the prior source manifest preserves the exact download URL and capture provenance.

## Roster lineage and limitations

- `inventory-rows.json` and `.csv` retain all 3,610 rows, original business/license fields, `descpremadd`, source record numbers, raw-row hashes, duplicate counts, and scope flags. The original CSV also preserves columns not projected into the inventory.
- Ten in-scope license numbers occur twice. One pair consists of identical complete source rows; the others have differences in at least one source field. They are retained as repeated observations, not assumed to be transfer history. No in-scope duplicate license has conflicting normalized holder names in this export.
- Every source row says `Active`, but 18 in-scope rows covering 17 licenses have expiration dates before September 3, 2026. They remain in the queue. Neither status nor an unexpired date verifies current operation. Issued dates are not transfer dates.
- Pledge/collateral/lien/loan markers were checked in **comments, location_comments, and descpremadd**, with matched terms attributed to the source field. Only Caveau (LB-99457) and Jana (LB-99458) match those terms, both in comments. A missing keyword is not evidence of no financing. Premises descriptions remain available for other relationships, including management agreements.
- Holder grouping removes case, punctuation, and spaces while retaining corporate endings. It does not merge LLC with Inc., resolve aliases, establish beneficial ownership, or combine businesses because their DBA, manager, lender, registered agent, or address is shared.
- Thirty-three holder names have an explicit individual label or lack a clear organization designator. `ucc-queue-name-review.json` and `.csv` identify these for review. Some are trade names or institutional names rather than people. An organization-mode no-result cannot exclude debt indexed under a proprietor or partner's individual name.

## Coverage and resumption

`ucc-queue.json` is the durable holder queue. Stable `BH-` identifiers are derived from normalized legal names; each holder retains every linked license and source row. `ucc-queue.csv` is the initial inventory snapshot, not a live progress ledger. The first-pending list was an alphabetical operational batch, not a representative sample.

The initial queue imported **18 complete current-database queries**: 12 from the fixed sample, four pilot searches, and two subsequent in-app observations. This left **1,426 current queries pending** and **all 1,444 lapsed scopes pending**. Exact source queries, page-size limits, capture methods, counts and source-file hashes are retained in `ucc-queue-prior-events.json`. A complete query with candidate results is not a completed entity match. In particular, the Keryan corporation/LLC mismatch and the Harvard predecessor/successor case remain separate identity issues.

Each scope has its own state and evidence attempts. A complete event requires equal nonnegative reported/returned counts and `truncated:false`; restricted city/state/date queries cannot complete the broad holder scope. Filing-history and attachment review are independent dimensions. Earlier document work is retained as partial prior evidence; no holder is marked as having every attachment reviewed. A later failed attempt preserves earlier complete query evidence without erasing the failure.

The in-app capture bridge writes observations and events separately under `ucc-cua/`. To form a new checkpoint from those events:

```bash
uv run python tools/boston_license_review.py merge \
  --queue reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-queue.json \
  --events reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-cua/events.jsonl \
  --output reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-queue-merged.json
```

Use `coverage --queue FILE --output FILE` to aggregate a checkpoint and `validate --queue FILE --output FILE` to check state/lineage integrity. Optional `--transfers` and `--owners` inputs count supplied evidence only; they do not infer unreviewed relationships. The report aggregator also overlays the bridge event log without changing the baseline queue. JSONL merges are idempotent.

`ucc-search-log-audit.json` records the pre-query checks for 2,870 pending scope items (2,868 distinct canonical keys), skipping the 18 evidence-backed completed scopes. No pending key was already logged at the audit time. After each saved in-app batch, synchronize its result events into the repository search log without issuing network requests:

```bash
uv run python tools/boston_ucc_runner.py \
  --sync-events reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-cua/events.jsonl \
  --log-checkpoint reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-cua/search-log-checkpoint.json
```

The checkpoint suppresses repeated event logging. Complete and partial result events retain their original scope and returned count; blocked/error events are not recorded as zero-result searches. This command writes only the search log and its checkpoint, not findings or leads.

## Alternate serial transport

`tools/boston_ucc_runner.py` wraps the existing verified `query_massachusetts_ucc.execute()` transport without changing it. It is implemented and tested offline; no live smoke or full run was started in this subtask because the parent chose the in-app route.

The existing transport launches one isolated, visible Chrome session per query, uses the ordinary public form, spaces navigation by at least one second, and limits a query to 500 occurrences/20 pages. Its browser deadline is 180 seconds, with a 210-second Python timeout. It retries an initial transient server/timeout error once but does not retry an access challenge. The wrapper adds one-second minimum spacing between queries, one exclusive runner lock, structured result files, atomic queue checkpoints, canonical search-log checks, same-query capture reuse, a stop-file mechanism, and progress every ten processed holders. It stops immediately on an error. A search-log entry without a saved result is not substituted for evidence.

The wrapper processes only pending scopes. Truncated searches remain partial and blocked searches stay blocked for review. There is no offset-based resume beyond the source's 500-row limit; an oversized name requires a documented exact-name, Article 9, or other justified partition strategy and result reconciliation. Neither current nor lapsed index completion retrieves filing histories or PDFs automatically. Source HTML is not saved by the existing transport; returned JSON records the page URLs/hashes and structured rows.

A coordinated two-query smoke would use `--max-queries 2`; the batch wrapper should not run against the site while another worker is issuing live queries. Full-run authorization does not turn a blocked page into an empty result or authorize access-control evasion.

## Validation

The local inventory/merge utility and alternate runner pass 17 focused tests and scoped Ruff checks. Tests cover row lineage, corporate-ending separation, category boundaries, markers in premises descriptions, false completeness, filtered searches, archive separation, idempotent resumption/log synchronization, cached identical queries, partial results, and stopping on a challenge. These are offline tests; live transport availability and throughput were not asserted.
