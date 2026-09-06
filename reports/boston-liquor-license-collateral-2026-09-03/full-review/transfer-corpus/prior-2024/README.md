# Boston license history: 2020–2023 archive extension

All **91 exact URLs** in the retained official pre-2024 archive index were downloaded and reviewed. They represent **89 unique PDFs and 906 pages**, dated **April 23, 2020–December 14, 2023**. SHA-256 comparison found **zero duplicates against the original 64 source documents from 2024–2026**. The original event, ownership and benchmark files remain unchanged.

| Year | Observed URLs | Unique PDFs | Pages | Transfer dispositions | License-pledge dispositions | Release acknowledgments | Ownership dispositions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 | 20 | 19 | 97 | 28 | 16 | 0 | 26 |
| 2021 | 26 | 25 | 230 | 112 | 40 | 0 | 47 |
| 2022 | 24 | 24 | 302 | 101 | 43 | 5 | 51 |
| 2023 | 21 | 21 | 277 | 78 | 48 | 2 | 31 |
| **Total** | **91** | **89** | **906** | **319** | **147** | **7** | **155** |

The duplicate variants are September 10, 2020 and April 8, 2021. Both URLs remain in the [source index](source-index.json); `canonical_source_id`, `is_duplicate_asset` and `include_in_unique_document_count` identify shared documents. No separate event duplicates were removed during consolidation. Repeated applications and decisions remain separate source occurrences.

## Recorded outcomes

| Outcome | License transfers | License pledges | Releases |
| --- | ---: | ---: | ---: |
| Granted | 275 | 131 | 0 |
| Deferred | 32 | 12 | 0 |
| Continued | 6 | 1 | 0 |
| Rescheduled | 2 | 1 | 0 |
| To be re-noticed | 1 | 0 | 0 |
| Withdrawn | 1 | 1 | 0 |
| Rejected | 2 | 1 | 0 |
| Acknowledged | 0 | 0 | 7 |
| **Total** | **319** | **147** | **7** |

The main [events ledger](events.json) contains these **473 actions**. All 155 [ownership-interest dispositions](ownership-interest-events.json) are explicitly granted: 126 items state an alcohol license and 29 concern Common Victualler licenses without alcohol stated. Four items explicitly identify entity conversions; these are source occurrences, not necessarily four distinct economic transactions. The ownership ledger preserves stated parties and share units, without deriving beneficial ownership, current control or private-equity sponsorship.

Separate from application decisions are **six transfer-intent/status notices**, **nine ownership-related informational, clarification or cancellation/directive records**, and **one ambiguous outcome**. The latter is the December 3, 2020 Asmabanu stock-transfer item, whose disposition visibly reads “Grated.” It is retained in [proposed-events.json](proposed-events.json) with `withheld_from_decision_counts=true`, not normalized to a grant. No other proposed-only or unresolved application outcome remained in the reviewed candidates. [Notices](notices.json) and [ownership notices](ownership-interest-notices.json) retain their actual action wording; they do not establish equity transfers. Five 2022 release acknowledgments were moved from the year's notices file into the consolidated main ledger to match the baseline convention; the [normalization log](normalization-log.json) records this routing.

## Review and source limits

Each year underwent page-preserving text extraction, broad keyword coverage review, item-level reading, and visual inspection of sparse pages and ambiguous layouts. No OCR was required. Consolidation validated all 91 file hashes, the exact observed-URL inventory, the document dates, full item text within cited page spans, explicit outcome wording, printed license IDs, and uniqueness across **644 retained event/notice/unresolved rows**. Whitespace and zero-width formatting are ignored for text-containment checks; source text and item hashes remain retained. Targeted Ruff checks passed.

Most files say Voting Agenda or Voting Hearing Agenda, but individual items contain explicit dispositions. Titles were not used to infer approval. All document dates match their index labels. One April 20, 2021 emergency notice has a stated hearing date and annotated disciplinary dispositions, but no independently stated voting date; it produces no transfer/pledge/ownership event here. Two 2023 metadata inconsistencies remain explicit: the May 25 anchor title says 5-23-23, and the August 17 document internally labels a transactional hearing Wednesday, August 18. The visible voting headings establish the recorded May 25 and August 17 decision dates.

Examples important for reuse:

- **BLB-2021-09-02-c003-pledge:** the additional license pledge is withdrawn. The transfer and stock/inventory pledge mentioned in the item are historical context, not additional withdrawn transactions.
- **BLB-2022-10-26-028-transfer:** the printed identifier is `L-99088`; normalized LB ID is withheld. **BLB-2023-01-05-033-transfer** prints `LB-9216`; no missing digit is supplied.
- **BLB-2023-09-14-033-transfer / -pledge:** a wrapped occupancy figure “45.” was merged back into the visually verified full item 24.
- Source corrections and conditions remain effective in the structured fields: Metro supersedes proposed U-Bahn; F1 Arcade supersedes proposed F1 Club; issuance conditions are retained without claiming fulfillment.
- Stock/inventory-only pledges are excluded from license-pledge counts. The two 2021 cases are retained in [their separate source-year ledger](2021/stock-pledge-events.json).

Five main-event rows and 19 ownership rows lack normalized LB identifiers. Missing and malformed IDs are not resolved by address or name alone. The current-roster join is a separate downstream step; no roster-match count is asserted here.

This completes review of the retained **linked archive window**, not every meeting or lifetime history. No pre-April 2020 material or unlinked application packets were added. A grant does not prove a completed sale, paid consideration, a current lien, an outstanding loan or current ownership. See the earlier [access-options audit](../../transfer-history-access-options.md) for the existing-records routes that could address earlier history, financial terms and post-approval outcomes.

## Artifacts and integration

- [coverage.json](coverage.json): source counts, ranges, outcomes, unresolved counts and cross-window hash audit.
- [readiness.json](readiness.json): `integration_status=qa_complete` and consolidated artifact hashes.
- [events.json](events.json) / [CSV](events.csv): normalized transfer, license-pledge and release actions.
- [ownership-interest-events.json](ownership-interest-events.json) / [CSV](ownership-interest-events.csv): separate ownership decisions.
- [notices.json](notices.json), [ownership-interest-notices.json](ownership-interest-notices.json), [proposed-events.json](proposed-events.json): separate non-application and ambiguous records.
- [year-coverage.json](year-coverage.json), year directories and [consolidate.py](consolidate.py): provenance, review details and deterministic normalization.

Events preserve `event_id`, `source_id`, `source_url`, `source_sha256`, exact/normalized license IDs, archive and document dates, page range, item number, full `item_text`, disposition, parties and ambiguity notes. No original corpus file or main dashboard/owner mapping was modified by this extension.
