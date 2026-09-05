# Boston liquor-license collateral review

The [full-roster review](/Users/travcole/projects/osint-research/reports/boston-liquor-license-collateral-2026-09-03/full-review/README.md) now checks all 1,512 core alcohol-license IDs against 153 collected documents in the linked 2020–2026 archive windows and tracks UCC and ownership work separately. It identifies **202 roster licenses with a granted pledge application, 200 without financing markers in the checked roster fields**. These are historical local approvals, not established current loans. Full UCC collection is paused pending supported bulk access; ownership research remains incomplete. Use its [dashboard](/Users/travcole/projects/osint-research/reports/boston-liquor-license-collateral-2026-09-03/full-review/dashboard.html) for current generated coverage and the [prepared state-data inquiry](/Users/travcole/projects/osint-research/reports/boston-liquor-license-collateral-2026-09-03/full-review/massachusetts-bulk-data-inquiry-draft.md) for the next access questions.

The [follow-up review](/Users/travcole/projects/osint-research/reports/boston-liquor-license-collateral-2026-09-03/follow-up/README.md) adds nine transfer approvals and a fixed sample of twelve unannotated holders: eight legal-name-matched holders with UCC records, including two specifically identified license pledges. The original first-pass results remain below.

Checked September 3, 2026, America/New_York. This first pass found **seven local board grants of license pledges**, six matching the supplied Boston roster, and **one UCC filing that explicitly identifies an alcoholic-beverages license as collateral**. It is a selected review, not a complete inventory of Boston borrowing.

## Direct UCC evidence: Bauer Wine & Spirits

Massachusetts **UCC 201960725880**, filed **December 18, 2019**, names **SK Wine and Liquors Inc** as debtor and **Northern Bank & Trust Company** as secured party. Its collateral description expressly identifies the all-alcoholic-beverages store license **89702-PK-0116** and references a pledge, assignment and security agreement dated **December 17, 2019**. The filing history also displays continuation **202414184220**, dated **October 10, 2024**. No termination is displayed in that two-entry history. [Original UCC document](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2019/1218/000000000/8564/201960725880_1.pdf), [continuation](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2024/1010/000000000/4690/202414184220_1.pdf).

The original one-page document was visually inspected in the in-app browser. Its visible data agree with the filing-history text. The packaged JSON is a transcription of that browser observation; the original PDF is linked, not locally downloaded.

The current roster identifies SK Wine and Liquors / Bauer under Boston license **LB-101973**, at **255 Newbury Street**. The 2019 UCC gives **330 Newbury Street** and a different license identifier. The March 2026 board decision independently grants a pledge by the same named licensee to Northern Bank. These records establish license-collateral activity by the business, but do not independently certify continuity between the historical ABCC identifier and current Boston identifier, or establish that the 2026 vote represents a new loan.

## Board-approved pledge candidates

Each linked decision records a grant of the license pledge, not merely a pending petition. Page and item placement were visually checked.

| Business / legal licensee | Boston license | Pledge recipient | Board vote and source | Additional evidence |
|---|---|---|---|---|
| Bauer Wine & Spirits / SK Wine and Liquors, Inc. | LB-101973 | Northern Bank and Trust | [March 26, 2026, p. 8, item 19](https://www.boston.gov/sites/default/files/file/2026/03/Voting%20Minutes%203-26-26.docx.pdf#page=8) | Explicit historical license-specific UCC described above. |
| Caveau / CMG CP1, LLC | LB-99457 | Eastern Bank | [July 11, 2024, p. 3, item 5](https://www.boston.gov/sites/default/files/file/2024/07/Voting%20Agenda%20July%2011.docx_2.pdf#page=3) | Roster pledge note; Eastern Bank UCC with broad collateral. |
| Jana Grill & Bar / Keryan & Co, Inc. | LB-99458 | Russian Benevolent Society, Inc. | [June 26, 2024, p. 7, item 15](https://www.boston.gov/sites/default/files/file/2024/06/Voting%20Minutes%206-26-24.docx.pdf#page=7) | Roster pledge note; the same item grants a transfer from the pledge recipient. |
| Roger’s Fish & Chips / RFC LA, LLC | LB-603766 | The Bank of Canton | [March 26, 2026, p. 8, item 21](https://www.boston.gov/sites/default/files/file/2026/03/Voting%20Minutes%203-26-26.docx.pdf#page=8) | No matching debtor in the current MA UCC searches used here. |
| The Pearl / The Pearl Group at Boston Landing, LLC | LB-98996 | Railyard Sports, LLC | [December 12, 2024, p. 5, item 8](https://www.boston.gov/sites/default/files/file/2024/12/Voting%20Minutes%2012-12-24.docx.pdf#page=5) | UCC not reviewed in this pass. |
| Seaport Hospitality, Inc. | LB-99041 | Eastern Bank | [December 12, 2024, p. 5, item 9](https://www.boston.gov/sites/default/files/file/2024/12/Voting%20Minutes%2012-12-24.docx.pdf#page=5) | License/name match; minutes say 42 Summer St and roster says 425 Summer St. |
| Namu Distilling Co., LLC | LB-612517 | Coastal Heritage Bank | [March 26, 2026, p. 8, item 18](https://www.boston.gov/sites/default/files/file/2026/03/Voting%20Minutes%203-26-26.docx.pdf#page=8) | Farmer-distillery pouring license; absent from the downloaded roster. |

For Caveau, **UCC 202300127090**, filed May 1, 2023, names Eastern Bank. It describes broad personal/fixture collateral, including generic license language, without identifying a particular alcoholic-beverages license. Two other CMG CP1 originals describe equipment. The board decision is therefore the specific license-pledge evidence for Caveau. [Eastern Bank filing](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2023/0501/000000000/4433/202300127090_1.pdf).

## Coverage and limits

- The [Boston dataset](https://data.boston.gov/dataset/licensing-board-licenses) supplied **3,610 rows and 3,593 distinct license numbers**, covering several license types, including non-alcohol licenses. It has legal business names and free-text conditions but no dedicated lender, loan amount or collateral field. Only two comments explicitly noted a license pledge: Caveau and Jana. These notes cannot support an estimate of total pledged licenses.
- Exact license numbers link six board events to roster entries. UCC searches use legal debtor names, with DBA and business addresses as supporting evidence. `KERYAN` returned an LLC in Belmont; the roster licensee is an Inc. in Allston. The LLC was not treated as an exact debtor match.
- Current MA UCC debtor searches covered CMG CP1, KERYAN, SK WINE AND LIQUORS, and RFC LA, with an additional RFC prefix check. CMG had three original histories reviewed; SK had four. No lapsed-archive review or other-state UCC search was performed. A non-match is not proof of no financing.
- Other SK filings include generic collateral, an unidentified lender represented by C T Corporation, and a Liberty Capital filing with a March 31, 2026 termination. None was treated as evidence of Northern Bank’s license pledge. Broad all-assets wording alone was not classified as explicit liquor-license collateral.
- Roster labels are not independently verified operating status: Jana’s entry is labeled Active while its comments say temporarily closed, documents needed, and do not issue. Seaport’s conflicting street numbers remain unresolved.
- **Principal amounts, advances, outstanding balances and present loan status are not established.** A continuation is a filing event, not evidence of the balance. A Boston grant alone also does not establish the separate state approval required for the pledge. [M.G.L. c. 138, §23](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXX/Chapter138/Section23).

The next records for amounts and terms are the actual pledge applications and attachments. The [ABCC pledge form, p. 2](https://www.mass.gov/doc/amendment-pledge-of-collateral-license-stock-or-inventory-042022/download#page=2) calls for pledge documentation and a promissory note, and includes lender, amount and financing-type fields. No applications were submitted, paid records ordered, or third parties contacted in this review.

## Saved files

- `review.csv`: seven-row comparison for sorting and follow-up.
- `pledge-events.json`: board events, source locators, roster matches, and UCC assessments.
- `roster-candidates.json`: relevant business/license columns for the six roster matches.
- `source-manifest.json`: source URLs, full-download hash, scope, counts and evidence-file hashes.
- `evidence/board/`: downloaded decisions, relevant rendered pages, extracted text and supporting official materials.
- `evidence/ucc/`: search results, selected histories, and explicitly labeled in-app-browser observations. Incidental individual co-debtor details were omitted from the two derivative comparison files.

No findings or leads were added to the unrelated active investigation profile.
