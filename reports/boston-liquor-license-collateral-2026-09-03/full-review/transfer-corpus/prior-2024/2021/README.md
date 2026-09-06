# Boston licensing decisions: 2021 archive extension

The retained official archive supplied **26 URLs for 25 dated entries** from January 21 through December 16, 2021. All 26 URLs returned PDFs. The two April 8 URLs have identical SHA-256 hashes, leaving **25 unique PDFs and 230 pages**. Both URLs and all 27 original anchor occurrences remain in `source-index.json`; only one copy of the duplicate PDF is extracted.

The reviewed output contains **112 license-transfer decisions and 40 license-pledge decisions**. It also contains **47 ownership-interest decisions**, five notices, and two separately identified stock/inventory-only pledge decisions. These are meeting-level decisions, not counts of completed sales or outstanding loans.

| Decision type | Granted | Deferred | Continued | Rescheduled | Rejected | Other | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| License transfer | 87 | 17 | 4 | 2 | 1 | 1 to be re-noticed | 112 |
| License pledge | 31 | 5 | 1 | 1 | 1 | 1 withdrawn | 40 |
| Ownership interest | 47 | 0 | 0 | 0 | 0 | 0 | 47 |

The transfer rows contain 89 distinct explicit license IDs. Two September 30 old-business transfer decisions omit the license ID; those fields stay null. No identifier is inferred from another meeting or the current roster.

## Sources and coverage

The acquisition selectors are the observed 2021 URLs in the saved [official Voting Minutes archive](https://www.boston.gov/departments/licensing-board/licensing-board-information-and-members), inventoried at `../../../history-access-evidence/older-archive-index.json`. The source manifest retains observed/final URLs, PDF hashes, byte sizes, page counts, text hashes, original anchor occurrences, and retrieval times.

The first printed meeting/hearing date matches the archive label in all 25 unique documents. Twenty-four have Voting Agenda/Voting Hearing Agenda headings and explicit dispositions. April 20 is an annotated emergency inspection notice with disciplinary dispositions; its printed hearing date is April 20, but an actual vote date is not independently stated. It produces no transfer, pledge, or ownership row.

This is complete for the observed archive links, **not a calendar-completeness or all-transactions claim**. No attempt was made to discover unlinked 2021 meetings. The existing 2024–2026 corpus and benchmark were not modified.

## Evidence distinctions and review cases

- [January 28, item 16, p5](https://www.boston.gov/sites/default/files/file/2021/02/Board%27s%20Voting%20Agenda%201.28.21.pdf): Kitty O’Shea’s / Flann O’Brien’s transfer is marked **TO BE RE-NOTICED**. Its later grant is a separate decision occurrence.
- [April 29, items 9–17, pp4–7](https://www.boston.gov/sites/default/files/file/2021/05/Board%20Voting%20Agenda%204.29.21.pdf): nine Legal Sea Foods license-transfer applications and nine license pledges to Northern Bank & Trust Company are granted. The records do not establish the number of economic loans or their current balances.
- [September 2, item 3, p1](https://www.boston.gov/sites/default/files/file/2021/09/Voting%20Agenda%20%28Corrected%29%209-2-21_0.pdf): LE, Inc. refers to a prior transfer and stock/inventory pledge, then requests an **additional license pledge**. The additional petition is withdrawn. This is one withdrawn pledge event; the historical transfer is not coded as a new withdrawn transfer.
- [September 30, item 3, p20](https://www.boston.gov/sites/default/files/file/2021/09/Maria%27s%20Copy%20of%20Final%20Voting%20Agenda%209_30_21%20.pdf): Big Bad Dog’s transfer and a following DBA amendment are separately granted within the same item. The transferee is Witchcraft LLC; the final granted DBA is New England Witchcraft Company.
- [October 7, item 15, p6](https://www.boston.gov/sites/default/files/file/2021/10/FINAL%20VOTING%20AGENDA%2010-7-2021.pdf): the Silhouette Lounge item grants a transfer and license pledge but ends its recipient clause at “to.” The pledge recipient remains null; the attorney is not used as the recipient.
- December 2 old-business item 3 rejects VJP / The Wine Cave’s transfer-and-pledge application **without prejudice**. The November deferral and December rejection remain separate events.

All `completed_sale_verified` and `equity_change_completion_verified` flags are false. A grant establishes the Board’s stated application disposition, not ABCC approval, issuance, payment, closing, current ownership, or a currently outstanding lien. No transaction price or loan amount is established by this ledger.

## Ownership and other collateral

Of 47 ownership decisions, **37 explicitly concern alcohol licenses** and **10 occur in Common Victualler material without an alcohol license stated**. All are granted. Nine of the latter items explicitly state before/after owner names or shares; these details are retained without linking them to an alcohol license. One alcohol item explicitly converts Lunas Restaurant LLC to Lunas Restaurant Corporation; this is an entity-form change, not proof of a new beneficial controller.

September 30 p16 item 11, Air Ventures, LLC d/b/a N.E. Mkt, is labeled an officers change but prints share figures for AV Holdings, George H. Walker, and Black Dog, LLC/William R. Newlin. The printed after figures are `75. Shares`, `12.25 Shares`, and `12.25 Shares`, totaling 99.5 if read numerically. They remain **shares as stated**, not percentages or a reconstructed capitalization table. The item states no alcohol-license ID. The neighboring Oak Sq. Coffee House item leaves the owner unchanged while adding a manager, so it is excluded from ownership changes.

`stock-pledge-events.json` separately retains the April 1 Beehive stock pledge to Cambridge Savings Bank and the July 29 LE’s stock/inventory pledge to LE, Inc. Neither is counted as an explicit license pledge. Generic officer changes, manager-only changes, room descriptions mentioning stock, alcohol-sales hours, and non-alcohol lodging transfers are excluded from the main ledger.

## Review and artifacts

The broad whole-document audit covered **199 candidate items and 278 keyword lines**, including transfer, pledge, owner, interest, share, equity, sale/sold, stock, beneficial interest, membership, and conversion terms. The five keyword lines outside candidate items are non-alcohol lodging/innholder transfer section headers and were reviewed. September 30’s unpunctuated transaction-item numbers and two occupancy sentences resembling item numbers required adjusted boundaries. Raw candidates remain available; final events trim unrelated subsequent section headings.

`pdftotext -layout` yielded usable text for every PDF. April 29 p9 was the sole zero-text page and was visually confirmed blank. Seven rendered pages were inspected for blank-page, collateral, shares, spelling, and entity-conversion ambiguities; see `visual-qc.json`. Every main event, ownership event, and notice passed the retained PDF hash, URL, exact normalized source-text/page-span, explicit-ID, disposition, and completion-flag checks. Python files passed Ruff.

- `events.json` / `events.csv`: 152 transfer/pledge decisions.
- `ownership-interest-events.json` / `.csv`: 47 decisions, with scope and before/after parties.
- `notices.json` / `.csv`: ownership information hearing, cancellation, and three closure/intent-to-transfer notices.
- `stock-pledge-events.json`: two stock/inventory-only pledge decisions.
- `proposed-events.json`: empty after review; all included applications have explicit dispositions.
- `excluded-candidates.json`, `candidates.json`, `all-keyword-contexts.json`, and `unmatched-keyword-contexts.json`: review trail.
- `source-index.json`, `coverage.json`, `validation.json`, `visual-qc.json`, and `manifest.json`: provenance and validation.
- `documents/`: 25 unique PDFs with extracted text and per-page JSON.

Initial sandbox requests failed DNS resolution before any HTTP response. Those environment failures are retained in `sandbox-dns-failures.json`. The authorized network-capable run fetched each observed URL once, with no HTTP errors or retry loops. No SOS portal, paid API, external contact, or records request was used.
