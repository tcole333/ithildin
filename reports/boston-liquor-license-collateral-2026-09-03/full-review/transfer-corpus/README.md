# Boston license-transfer and pledge decision corpus

The current [Boston Licensing Board archive](https://www.boston.gov/departments/licensing-board/licensing-board-information-and-members) supplied **64 decision-bearing documents for 2024–2026 through September 3, 2026**. Every linked document in that window was retrieved and reviewed for explicit alcoholic-beverage license transfers and pledges: 23 documents in 2024, 25 in 2025, and 16 in 2026. The corpus contains 918 PDF pages and one published HTML document without stable pagination.

The extracted records are Board decisions and acknowledgments. A granted transfer is evidence of local approval, not evidence that the sale closed, that ABCC approval was issued, or that the transferee currently holds the license. A granted pledge is not proof of a currently outstanding loan, lien, or balance. No sale price or completed sale is established by this corpus.

## Results

| Recorded action | Granted | Other application outcomes | Separate acknowledgments |
|---|---:|---|---:|
| License transfer | 190 | 4 deferred; 3 continued; 1 rescheduled; 1 withdrawn | 3 notices of mutual intent to revoke prior transfers |
| License pledge | 101 | 1 deferred | 3 releases of prior pledges/security interests |

There are **199 transfer application decisions**, **102 pledge application decisions**, and **6 separate acknowledgments**, totaling **307 events**. The transfer records name 176 distinct non-null Boston license IDs. Two 2024 transfer items omit an LB number, which remains null. Repeat decisions and sequential transfers of the same license are retained as separate dated events. Thirteen prospective-transfer or other status notices are stored separately and excluded from these counts.

| Year | Transfer applications granted | Pledge applications granted |
|---|---:|---:|
| 2024 | 77 | 40 |
| 2025 | 59 | 31 |
| 2026 through September 3 | 54 | 30 |

## Files and schema

- `events.json`: canonical, reviewed event array; `transfers.csv` and `pledges.csv` are flat exports.
- `notices.json`: prospective-transfer and other status notices, not approvals.
- `source-index.json`: every indexed decision document, source URL, local files, hashes, retrieval metadata, and pagination.
- `coverage.json`: counts and scope; `extraction-2024/cross-year-coverage-audit.json`: heading, filename, calendar, and video-link audit.
- `archive-index.html` and `archive-coverage.json`: retrieved index and initial parsed link inventory. The detailed cross-year audit corrects split anchor labels and two malformed video hrefs in this initial inventory.
- `documents/`: source PDFs or HTML, extracted text, and page-preserving JSON.
- `candidates-2025-2026.json`, `excluded-candidates-2025-2026.json`, and `extraction-2024/`: candidate review audit trail. Candidate inclusion alone does not make an event; an excluded candidate may instead be represented as a labeled notice/release in the canonical outputs.
- `validation/` and `extraction-2024/visual-*.png`: targeted visual checks; `extraction-2024/cross-audit-*.png` records the additional hearing-heading checks.

Each canonical event includes `event_id`, `event_type`, `action_subtype`, `license_number` (for example `LB-99139`), `license_num` (`LB99139`), `archive_date`, `document_vote_date`, `date`, `outcome`, `disposition`, `outcome_text`, `source_url`, `page_start`, `page_end`, `item_number`, and complete `item_text`. Transfer events have seller/buyer legal names, DBAs, and from/to addresses. Pledge events identify the pledging licensee and recipient. `ambiguity_notes` preserve source discrepancies and corrections. Pagination is one-based physical PDF pagination; HTML page values are null. `date` is the voting-document date, not an assumed closing or transactional-hearing date.

`board_granted_application` is true only for a granted application disposition. Revocation and release acknowledgments have distinct `action_subtype` values and never set this flag. `completed_sale_verified` is false throughout because these records do not establish closing. All items in `events.json` are decision-bearing; separate notices may have no stated disposition.

## Chronology and corrections that matter

- **LB-99643, Mirage Charcoal Kebab → LZZ LLC:** the March 28, 2024 approval was followed on June 6 by an acknowledged mutual intent to revoke; the source states that the purchase-and-sale agreement was voided.
- **LB-99671, Gogle Mogle → Selfup:** the September 26, 2024 approval was followed on April 17, 2025 by an acknowledged notice that the transaction had not timely closed. A March 5, 2026 approval names a different buyer, Fort Point Partner Inc.
- **LB-99070, D Street Music → Proctor Restaurant Enterprise:** approved August 28, 2025, with an issuance condition; a March 5, 2026 acknowledgment reports the transaction had not timely closed. Proctor later appears on a different license, LB-99804, in the June 25, 2026 decisions.
- **LB-99452:** the June 5, 2025 decision corrects the proposed buyer name from 1928 Boston Harbor, LLC to **1928 Rowes Wharf LLC**.
- **LB-101911:** the March 5, 2026 petition proposed the DBA Sip City Liquors; the decision grants with **Jersey Street Liquors** as DBA.
- **LB-99389:** the November 20, 2025 decision corrects the target address from Dorchester Avenue to **289 Dorchester Street**.
- Some grants expressly withhold license issuance until community-process or other conditions are met. The full source text and a condition note are retained; a grant count does not treat these conditions as satisfied.

## Coverage limits and verification

This is a complete extraction of the explicit transfer and license-pledge items in the **64 linked documents**, not a claim of complete Boston license history or every decision ever issued. Older archive sections exist but are outside this collection window. The archive snapshot was retrieved on September 3, 2026 Eastern time; some retrieval timestamps fall on September 4 UTC.

All 64 document voting headings agree with their archive dates. Two URL filenames differ: the October 17, 2024 file says October 15, and the January 8, 2026 file says January 9. Events use the actual document headings. Two internal hearing headings contain weekday/date inconsistencies, preserved in the cross-year audit.

Of 64 voting-video records in the same window, 63 have same-date indexed minutes after joining a split March 28, 2024 label. March 5, 2024 has a combined transactional/voting video without separately dated minutes; March 7 minutes explicitly include the March 5 transactional hearing. This is not treated as a proven missing transaction record. December 18, 2025 minutes have no matching video link. Videos were not watched. The October 1, 2025 published Google document has no stable page numbers; November 6 and November 20 PDFs were retrieved through download URLs actually exposed by the official archive-linked Drive pages.

All 2024 candidate items and all 178 keyword candidate items for 2025–2026 were reviewed. Stock-only changes/pledges, non-transferability policy text, new licenses, and mere intentions were excluded from transfer-application counts. A broad source-line audit found zero transfer/pledge keyword lines outside reviewed candidate material. The final merge verifies unique event IDs, source-text correspondence, document page bounds, and stated dispositions for canonical events. Eleven targeted visual checks cover source corrections, omitted/malformed IDs, sequential transfers, old/new business outcomes, revocation/release notices, conditional grants, and deferrals. All extraction scripts passed Ruff.

The extraction scripts reproduce the files from the retained documents. `collect_corpus.py` discovers and downloads direct official PDFs; the retained Google HTML/Drive records are processed by `prepare_extraction.py`. Running source-index discovery again replaces that index, so preserve the enriched snapshot before recollection. Run `extract_2025_2026.py` and then `finalize_corpus.py` to regenerate canonical outputs from reviewed material.
