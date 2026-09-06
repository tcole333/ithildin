# Independent review of new ownership events

September 4, 2026. Local review only. I visually read all pages of the saved Norfolk deeds and discharge (13 pages total) and page 1 of the eight-page mortgage. All six PDF hashes match the source manifest. The watermark-only extracted text was not used as a substitute for reading the page images.

## Norfolk unit chain

| Instrument | Independent check | Result |
|---|---|---|
| 22537/499, two pages | Unit W305 at 227 Summit; Mehmet Goker to Madiha and Zouhair; June 20 execution / June 21, 2005 recording | Matches. The deed calls the grantees “Husband and Wife, as Tenants by the Entirety.” Numerals state $900,000, while the words read “Nine hundred.” The export preserves this discrepancy; do not silently rewrite the source wording. |
| 30161/456, page 1 reviewed | Revolving-credit mortgage; Zouhair and Madiha / Belmont Savings Bank; June 29 instrument date / July 6, 2012 recording | $647,500 is the maximum principal at any time, not actual advances or current balance. `original_partial_review` is appropriately explicit. Signature and acknowledgment pages were not reviewed here; see requested precision correction below. |
| 32418/159, three pages | Zouhair and Madiha to Madiha individually; $1; July 3 execution and acknowledgments / July 24, 2014 recording | Matches. The deed again describes the grantors as husband and wife. The homestead reservation is distinct from the life estate created by the next deed. Prior 22537/499 is correctly linked. |
| 32418/162, three pages | Madiha to Houssam; $1; July 3 execution and acknowledgment / July 24, 2014 recording | Matches. Page 2 reserves Madiha's life estate, exclusive occupancy, rents/profits, sale or mortgage powers without the remainderman's consent, and a special power of appointment. Houssam's interval must remain subject to those reservations. The prior deed is 32418/159. |
| 40732/419, one page | M&T successor chain; specific discharge of 30161/456; July 11 execution/effective date / August 4, 2022 recording | Matches. It identifies the borrowers, original lender, mortgage dates, book/page, property and $647,500 original amount. It releases this mortgage; it is not proof of a $647,500 repayment, all debts being paid, or repayment funding. |
| 42842/317, four pages | Houssam's $1,585,000 deed to Mohammad Asif Iqbal Qureshi; December 18 execution/acknowledgments / December 19, 2025 recording | Matches. Page 2 expressly limits Madiha's execution to release of her life estate and any homestead rights. This is not a second seller-interest or second consideration. Prior 32418/162 is correctly cited. Gross consideration is not Houssam's net proceeds. |

The dated spouse wording is supported by the deeds. These records do not by themselves establish a parent-child relationship between the people involved.

## Requested corrections and qualifications

1. **Mortgage date precision:** the export calls June 29, 2012 the mortgage's execution date while declaring only page 1 reviewed. Page 1 says when the mortgage was “made”; the discharge labels it the “Date of Mortgage.” I asked the source owner to call this the instrument date, or review the saved signature/acknowledgment pages before retaining a verified execution date. The July 6 recording event itself is correct.
2. **Discharge amount semantics:** the discharge export repeats `loan_amount_usd=647500`, which the renderer labels “Loan face amount” at the 2022 discharge. I asked the source owner to leave that numeric field blank and keep `referenced_original_mortgage_amount_usd=647500` in notes, or coordinate an explicit type-specific label. This avoids treating the discharge as another loan or a proved repayment amount.
3. **Stable identifiers:** Norfolk's `instrument_id` currently contains the native annual document number. Root should normalize the merged stable ID to county, recorded-land system and book/page, retaining the native document number in notes. The current merge already deduplicates using county/book-page, so this has not caused a duplicate in the audited snapshot.

No other material correction to the six Norfolk source events was found. Source artifacts were not edited by this reviewer; requests were sent to their persistence owner.

## Merge and rendering review

The audited snapshot of `ownership-events.csv` contained **401 rows**: the 395-row corrected baseline and six Norfolk events. Its SHA-256 was `6c6d05ba24dcde463c2dac47cb2c492ec40b4a3f3f015527c424aa0f30c4df57`. The source merge was still in progress: Suffolk, Plymouth, local-courts and capital exports were not present in that snapshot. This review does not claim that their later replacement rows were checked.

The snapshot has no duplicate event IDs and no repeated county/book-page/property combination. All ten baseline court/claim events retain a single explicitly non-title participant list. HTML and Markdown generation use title arrows for deed/conveyance events; court events do not receive grantor/grantee labels or directional arrows. The HTML contains all snapshot event IDs. Amounts are presented as historical observations; the artifact computes no ownership or debt total.

The merge script replaces baseline rows when a source-owner original review has the same normalized county/book-page, then preserves the source-owner parcel rows. Its merge audit exposes old/new property sets. Root must inspect those sets after the Suffolk export arrives, especially the expanded three-parcel 56448/321 deed and the special 419 Boylston PILOT term conveyance. Neither a source review's mere presence nor this earlier 401-row audit proves that a later legal interest or parcel expansion was reconciled correctly.

No new online searches, source findings, or first-wave edits were performed for this review.

## Norfolk correction follow-through

The source owner subsequently reported and applied both requested precision fixes. Discharge 40732/419 now leaves numeric loan amount blank and retains the $647,500 referenced mortgage amount in notes. The owner read all eight pages of mortgage 30161/456 and found the June 29, 2012 acknowledgment at book page 459; the verified execution date is retained and its review status now reflects that completed review. The latter additional pages were reviewed by the source owner, not independently re-read during this bounded audit. The owner's seventh, Middlesex event was outside the six-document Norfolk original review above.

## Plymouth title-sequence review

The Plymouth review compared the 15 original-document event rows with all saved manual excerpts, their earlier detailed notes, and the source manifest. There are **no saved original scan files for these Plymouth instruments**. This is an independent consistency review of the source owner's original-image transcriptions, not a claim that this reviewer independently viewed the original images. All 24 source-manifest artifact hashes, including the subsequently consolidated assessor references, matched their files.

**53 Beach Avenue, Hull, parcel 25-084:** the excerpts support Amine Ali Hassan → Hicham Abdul Hafiz Ali Hassan in 1984 (5787/169); Hicham, expressly identified by that expanded name, → the three named trustees of 400 Boylston Street Realty Trust in January 1993 (11586/230); the three trustees → Zouhair individually in April 2001 (19629/323); Zouhair individually → Hicham individually in December 2001 (21123/41). All four deeds describe the same lots 1626 and 1625 with beach rights. The grant to Zouhair does not state an undivided-share limitation in the reviewed grant. Amine's kinship and the trust beneficiaries remain unresolved.

The December 2001 deed's apparent handwritten execution/acknowledgment date of December 14 conflicts with December 13 recording. The export correctly retains the recording date as its dated event and exposes the unresolved discrepancy in notes. The assessor's compressed grantor label does not override the deed's identification of Zouhair as individual grantor.

**121 Nantasket Avenue, Unit 307, Hull, parcel 39-307:** all six distinct title events are preserved:

| Recorded date | Instrument | Title change supported by the excerpts |
|---|---|---|
| 1987-12-10 | 8177/20 | Nantasket Realty Trust trustees → Gregory Sullivan and Hicham as Hassull Realty Trust trustees; $195,000 |
| 2002-05-23 | 22123/80 | Hassull trustees → Gregory individually; $10 |
| 2003-03-20 | 24543/109 | Gregory individually → Hassull Realty Trust; $1 |
| 2004-02-27 | 27625/57 | Gregory as Hassull trustee → Gregory individually; $1 |
| 2006-04-07 | 32484/265 | Gregory individually → Gregory as Hassull trustee; $1 |
| 2017-08-31 | 48873/284 | Gregory and Hicham as Hassull trustees → Hicham individually; $1 |

These events do **not** support continuous Hassull title between 2002 and 2006. Every step preserves the same unit, area and common-interest description and cites its immediate predecessor. The 2004 deed's single trustee signature does not prove that Hicham ceased to be a trustee; the separate trustee certificate remains unread. The 1987 execution/declaration chronology and the 2017 declaration-year discrepancy remain explicitly qualified. No beneficial-share interval is created from trustee status.

**4 and 6 Pinecrest Road, Hingham:** the 2006 acquisition is by Houssam individually for $1.3 million (32556/341); the 2007 $1 transfer is to Pinecrest Road, LLC (35274/54); the 2010 $1.375 million disposition is by the LLC through Houssam as manager (38184/289). He is not an additional personal seller in 2010. The matching lots, 129,679-square-foot area and plan bridge the 2010 prior-book typo. The unresolved handwritten January 2010 day is not fabricated. The later deed's April 15, 2006 recital is correctly identified as support for the acquisition's execution date.

The 1993 Beach mortgage has a $1 million face principal, with the three trustees signing as trustees and not individually. Only pages 1, 12, 13 and 14 of 14 were reviewed by the source owner. The reviewed Exhibit A contains the Hull lots; this does not establish a Boston allocation of proceeds or cross-collateralization. The 1987 Nantasket deed was also only partly reviewed (pages 1 and 3 of 4). At my request, the owner changed both events and the source manifest to **`original_partial_review`** while retaining precise pages reviewed.

## Plymouth assessor integration

The final source-owner export at this review stage has **24 rows: 15 recorder events plus nine assessor observations/history references**. Per root's explicit instruction, all nine assessor rows were retained. Five historical rows duplicate a transaction already established by an original deed, but now use `assessor_history`, link the original event in notes, and expressly warn against counting another transaction. These are supporting observations, not five additional title changes.

The Hingham assessor and original-deed rows now share property key `plymouth-hingham-116-0-47`, so the municipal `4 Pinecrest` label does not split the deed's `4 and 6 Pinecrest` group. The three municipal-card valuation rows retain FY2026 year precision. The separate MassGIS archive rows are labeled FY2027 in the source; that future fiscal label must not be turned into a prediction of 2027 title or silently substituted for FY2026 card values.

The 2025 Pinecrest sale reference, 59910/341 with an assessor-reported $2.32 million price, remains an **assessor history reference**; no original deed was reviewed in this track. I asked root to label `assessor_history` monetary fields “Assessor sale-price field,” instead of generic “Consideration,” and to exclude these rows from title intervals and transaction sums. The renderer's existing classification places them under Assessments, which already prevents title arrows. The export correctly leaves assessed values out of consideration and loan fields.

The checked 24-row Plymouth export SHA-256 was `0786a379e7253cee42032fc654f3f7303a7db5f356dc3b5ac38bddb689cb4224`; it had no duplicate event IDs. No other material sequence or capacity correction was found. All review work remained local, and source-owner exports were not edited by this reviewer.
