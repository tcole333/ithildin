# Offline reconciliation of the seven older UCC histories

Reviewed September 4, 2026 from unchanged saved evidence. **Seven histories, containing eleven entries, have now been read and reconciled.** All seven source-file hashes match the original source manifest. This adds explicit analyst review of the saved material; it does not refresh source coverage or establish current liens or balances.

The [review ledger](/Users/travcole/projects/osint-research/reports/boston-liquor-license-collateral-2026-09-03/full-review/filing-review-reconciliation.json) contains one record per original filing, with the roster holder ID, source path/hash/JSON pointers, exact collateral quote, named parties, each amendment, every listed PDF, and unresolved work. **Only one original PDF has prior complete visual-review evidence; six original PDFs and four amendment PDFs remain pending.** The current index baseline remains 96 completed queries and no lapsed searches completed.

| Original / recorded secured party | Reconciled evidence | Remaining work |
|---|---|---|
| 201960725790 — Northern Bank & Trust | Broad personal-property collateral; October 10, 2024 continuation 202414183890. | Original and continuation PDFs; historical premises/license continuity. |
| 201960725880 — Northern Bank & Trust | Explicit alcoholic-beverages license **89702-PK-0116** and December 17, 2019 pledge/security agreement. Prior root note verifies the complete single-page original PDF. | Continuation PDF 202414184220; continuity to current Boston LB-101973 and 255 Newbury Street. |
| 202516533430 — C T Corporation, as representative | Business debtors include SK Wine and Liquors Inc, SK Pizza Inc and Bauer Wine and Spirits. Collateral was not captured. April 14, 2026 **DebtorDelete** amendment 202631151100. | Two-page original PDF; amendment PDF identifying the deleted debtor; underlying creditor if disclosed. |
| 202630298860 — Liberty Capital Management | Broad all-assets collateral; March 31, 2026 **TerminationSecuredParty** 202630725870. | Original and termination PDFs. Do not characterize it as an ongoing debt. |
| 202293005740 — North Star Leasing, a division of Peoples Bank | Restaurant/refrigeration, AV and lighting equipment and related services. | Original PDF and attachment completeness. |
| 202398472870 — North Star Leasing, a division of Peoples Bank | Displayed lighting/AV equipment text directs the reader to **Schedule A**, explicitly unread in the prior capture. | Original PDF, complete Schedule A, and missing party addresses. |
| 202300127090 — Eastern Bank | Broad personal/fixture property, including generic licenses/permits. No particular liquor license identified in the displayed text. | Original PDF and missing party addresses. Caveau's separate board grant does not turn this UCC text into a specific-license pledge. |

SK's historical 330 Newbury address differs from the current 255 Newbury roster address. The historical ABCC identifier and Boston LB-101973 remain distinct. Two SK saved histories intentionally omit incidental individual co-debtors; complete party inventories cannot be certified from those derivatives. In particular, the repeated business-party list around DebtorDelete does not identify who was removed.

`history_text_review_state: reviewed_saved_history_text` means all preserved entries were read, **not** that collateral attachments, party-amendment effects, or current source coverage are complete. `collateral_review_state`, `document_reviews[].pdf_review_state`, `pending_actions`, and continuity caveats must survive any import. No listed pending PDF is exempted just because HTML collateral was available.

The existing builder's `--decisions` input supports holder-identity decisions only. Accordingly this ledger was kept separate; **the main filing queue, aggregate and dashboard were not modified**. Their existing 19 imported-sample-review counter remains unchanged until a deliberate integration of this seven-record ledger. No new browser, network, UCC/API, PDF retrieval, or profile/finding writes occurred.
