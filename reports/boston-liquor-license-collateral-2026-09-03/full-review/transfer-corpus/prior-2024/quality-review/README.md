# Independent audit of the finalized 2020–2023 extension

The bounded offline audit passed with **no correction requests**. Review began after `readiness.json` and `coverage.json` were marked `qa_complete`. No canonical corpus, dashboard, or benchmark file was edited, and no network or portal call was made.

- All **91 source entries** match the local PDF hashes and byte sizes; extracted text hashes and PDF/page-index counts also match. They represent **89 unique PDFs / 906 pages**, with two explicit duplicate-URL variants and **zero content-hash overlap** with the original 64-source corpus.
- All **644 record IDs** are unique across 473 main actions, 155 ownership dispositions, 6 transfer/status notices, 9 ownership notices, and 1 ambiguous outcome. All source references, URLs, canonical source mappings, and cited page bounds pass.
- All **60 unapproved main applications** retain `board_granted_application=false`. Seven release acknowledgments remain separate from new pledges. Notices and the ambiguous outcome remain outside granted-application counts; sale/equity completion is not certified.
- The original **8 canonical files and 16 benchmark files** remain byte-identical to the independently frozen baseline. All 11 consolidated artifacts match the readiness hashes at the beginning and end of this audit.

## Purposeful PDF checks

Eight cases were checked against saved full page text and **nine freshly rendered PDF pages**, covering nine consolidated rows plus two document-date cases. This is a purposeful sample, not another full manual review of every source page.

| Case | Evidence | Result |
| --- | --- | --- |
| Asmabanu stock-transfer item | December 3, 2020, p8 | Visible “Grated” remains ambiguous and withheld from decision counts. |
| Le additional license pledge | September 2, 2021, p1 | WITHDRAWN applies to the additional license pledge; prior transfer/stock pledge remain context. |
| Three release receipts | March 24, 2022, p19 | Acknowledged releases, not new pledge grants or proof no other lien exists. |
| Bombolotti | October 26, 2022, p9 | Printed `L-99088` is preserved; normalized LB identity withheld. |
| J. P. Partners | January 5, 2023, p10 | Printed `LB- 9216` retains its digits and explicit caveat; no missing digit inferred. |
| BAM / Good Tacos | September 14, 2023, p11 | “45.” is a wrapped occupancy figure within item 24; complete item supports distinct transfer and pledge actions. |
| Emergency inspection notice | April 20, 2021, p1 | Hearing date is stated; vote date remains null; no scoped transaction event is created. |
| Conflicting internal heading | August 17, 2023, pp1 and 4 | Voting heading says August 17; internal transactional heading says Wednesday August 18. Recorded vote date and conflict qualification remain intact. |

## Consumer boundary

Twelve notice rows have `decision_bearing=true` because they record an acknowledgment or directive. That field alone does not mean an approved application. Consumers must respect the containing ledger/action subtype and `board_granted_application`, which is false for every notice. This is a documented reuse caveat, not a failed source audit.

The audit does not establish calendar-complete or lifetime license history, independent roster identity, completed sales, paid consideration, current liens, debt balances, or current ownership.

## Audit artifacts

- [source-hash-audit.json](source-hash-audit.json): per-source hash/page checks, readiness hashes, and original-file preservation checks.
- [source-reference-audit.json](source-reference-audit.json): independent ID/reference/page/outcome and ledger-boundary checks.
- [purposeful-spot-checks.json](purposeful-spot-checks.json): exact short quotes, IDs, source hashes, interpretations, and PNG evidence references.
- [frozen-canonical-baseline-manifest.json](frozen-canonical-baseline-manifest.json): preserved baseline manifest, including per-record fingerprints for later integration checks.
- [audit-manifest.json](audit-manifest.json): hashes of this audit's inputs and deliverables.
