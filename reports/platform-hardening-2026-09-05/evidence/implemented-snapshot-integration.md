# Publication snapshot integrity integration

Status: complete and verified. Owned files are stable: `pipeline/publication_snapshot.py` and `tests/test_publication_exports.py`. Parent CLI changes (`check` permits omitted `--output`; `build` requires it) are preserved and regression-tested. No Git changes, live database/API access, publication builds, or content facts/status changes were made.

## Fix and preserved contract

`collect_content` now reports invalid JSON, payload/container/record/evidence shapes with their file and record location; valid finding IDs are included in finding-level issues. Malformed files do not conceal issues in later files. The reported release crash was specifically `evidence: null` on five exported findings in `dossiers/conductor-inc.json`: 11472, 11475, 11505, 11471, 11517. These now produce `invalid_evidence_collection` with the exact `findings[index]` location.

A verified status alone cannot admit a record into the candidate catalog. Each finding needs valid claim/confidence metadata, a nonempty evidence array, nonblank textual evidence references and quotations, and valid supplied evidence metadata. Duplicate refs and mismatched stored evidence types are diagnosed. Pure helpers/constants from the canonical findings tracker provide claim vocabulary, source vocabulary, reference classification, and claim/source confidence ceilings. Validation rejects over-cap records; it does not clamp or rewrite published content.

Raw `source_datasets` is checked whenever present, including null, malformed stored JSON, unsupported source tokens, and provenance-opaque source caps. Older exports can omit that metadata; this preserves the current schema-1 catalog contract. No source metadata is inserted into normalized fingerprints. `FIELDS`, `EVIDENCE_FIELDS`, and normalization of valid records remain unchanged, preserving Python/TypeScript fingerprint compatibility.

Static validation does not resolve local evidence spans, open source corpora, or read a database. A test makes DB/corpus reads fail while validating an EFTA reference successfully against exported metadata. This remains a content consistency/provenance gate, not semantic review or proof of the quoted statement. The explicit existing `--db` audit remains available, unchanged.

Malformed snapshot JSON and non-object snapshot payloads now receive contextual diagnostics. Candidate build refuses any content issue and preserves an existing output artifact rather than overwriting it. Cited IDs that exist but fail publication checks use `unpublishable_cited_finding`; IDs absent from content use `missing_cited_finding`. Repeated identical references within a file produce one citation diagnostic.

## Verification

**63 tests passed** across `tests/test_publication_exports.py` and the parent-owned `tests/test_release_validation.py`; no changes to the latter. Changed-file Ruff and `git diff --check` passed.

```sh
uv run pytest tests/test_publication_exports.py tests/test_release_validation.py --offline -q -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-snapshot-final
uv run ruff check pipeline/publication_snapshot.py tests/test_publication_exports.py
```

Log: `/tmp/osint-CUTDyZF1/snapshot-integration-final-tests.txt`.

The real current-content check completed with **exit 1**, `ok=false`, and zero generic crash errors. This is the expected publication block for existing content debt and the missing snapshot. It read 534 source files, retained 116 eligible finding IDs in memory, and reported 32,446 issues across source occurrences/references (not unique findings). No candidate snapshot was materialized.

Artifacts:

- `/tmp/osint-CUTDyZF1/current-publication-diagnostics.json`: complete contextual diagnostics.
- `/tmp/osint-CUTDyZF1/current-publication-diagnostics-summary.json`: exit code and aggregate counts.

The checker now flags two actual verified above-cap records: `dossiers/anduril-industries-llc.json` findings 4565 and 4577 are synthesis/high and receive `confidence_exceeds_cap` with `max_confidence=medium`. Their content and verification states remain untouched.

## Papercut handoff

Logged/resolved isolated observations #2 and #3 in `/tmp/osint-CUTDyZF1/strict-finding-papercuts.db`; parent owns any canonical methodology logging. Exact prior reproductions:

1. Run the snapshot check against current content: `normalize_finding` iterates `record.get("evidence", [])`, so an explicit null value triggers TypeError and the generic `invalid_publication_input` / NoneType-not-iterable response. The source file/finding is omitted. The five conductor-inc IDs above reproduce it.
2. Build/collect a synthetic `verification_status=verified`, `claim_type=synthesis`, `confidence=high` record with missing/unquoted evidence. Prior collection only compared verified status; complete provenance and shared confidence limits were not rechecked. The current Anduril records demonstrate the confidence side of this gap.

Known existing publication debt is deliberately not repaired by status/confidence edits, inferred source metadata, fabricated quotes, or semantic PASS receipts.


## Follow-up: optional current-database provenance audit

An independent final review reproduced a blind spot in the explicit `--db` path: exported and database rows had identical schema-1 fingerprint fields, but the current DB source_datasets changed from `["courtlistener"]` to `["dehashed"]` while confidence remained high. Because source metadata is deliberately omitted from the normalized snapshot shape, the old comparison incorrectly returned ok.

`audit_database` now validates the actual current row/evidence through `finding_issues` before normalization. Missing current database source metadata is treated as invalid (distinct from legacy static exports that omit that schema-1 metadata). Diagnostics retain their meaningful policy code plus `scope=database`, file path, finding ID, and location. Fingerprint fields and production content remain unchanged.

Five new integration cases establish that a matching courtlistener baseline passes, then dehashed/intelx source-cap violations, null source metadata, an empty source list, and unsupported source tokens fail even though normalized fingerprints remain equal. The database remains byte-for-byte unchanged by the audit.

Final focused validation: **68 publication/release tests passed**; Ruff and whitespace checks passed. Log: `/tmp/osint-CUTDyZF1/snapshot-source-drift-tests.txt`. Full-suite snapshot running under the parent predates this follow-up; only the two owned files changed.

Command:

```sh
uv run pytest tests/test_publication_exports.py tests/test_release_validation.py --offline -q -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-snapshot-source-drift
```
