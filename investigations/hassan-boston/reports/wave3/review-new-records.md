# Independent review of selected wave-three records

Reviewed September 5, 2026, using only saved local evidence. This report distinguishes direct inspection of saved document images from consistency checks of another agent's manual original-image transcription. I did not query a registry or other online source, edit a source owner's export, or create duplicate database findings.

## 18 Brimmer Street financing and foreclosure

**Review basis:** transcription consistency only. No local images of these Suffolk instruments were saved. I compared `evidence/wave3/suffolk/events.csv`, `documents.json`, and `scan-observations.md` with prior Brimmer records. The source owner reports having read each original in the public land-records viewer.

The chronology and capacities are internally consistent:

| Recorded date | Instrument | Capacity and amount supported by the transcription |
|---|---|---|
| 1994-06-20 | 19143/176 | Alexander Randall, 5th and Cameron Hall, borrowers/mortgagors → Interstate National Mortgage Corporation, lender/mortgagee. **$618,000 loan face amount.** Executed June 15. |
| 1994-06-20 | 19143/185 | Interstate, mortgage holder/assignor → Crossland, assignee. Executed June 15 and recorded one minute after the mortgage. This is an assignment, not another loan. |
| 1994-12-13 | 19491/107 | Crossland, mortgage holder/assignor → Guaranty Federal Bank, assignee. The original was dated only to December in the saved transcription. This is an assignment, not another loan or evidence of balance. |
| 1997-12-02 | 21956/120 | Institutional Asset LLC, foreclosing mortgage holder under a separate junior mortgage → Zouhair as trustee of Eighteen Brimmer Street Realty Trust. **$325,000 foreclosure-auction bid/consideration.** Executed November 3 according to the transcription. |
| 1999-07-20 | 24001/64 | Guaranty Federal Bank, senior mortgage holder, releases 19143/176. Signed in December 1997; exact day unresolved. The record does not state a payoff amount, payer, or funding source. |

Only 19143/176 should carry `loan_amount_usd=618000`. The two assignments and release refer to that historical face principal but do not state a new advance, then-current balance, or payoff. I asked the source owner to blank those three numeric loan fields and preserve `referenced_original_mortgage_face_amount_usd=618000` in notes. The foreclosure deed correctly puts $325,000 in consideration and leaves the loan field blank.

The foreclosure was expressly subject to the senior mortgage, taxes, tax titles and liens. The senior mortgage's **original** $618,000 face amount cannot be treated as its 1997 balance, added to the $325,000 bid to derive cash paid, or used to calculate current equity. I asked that the interim `$943,000` arithmetic sentence be removed because the source does not establish that economic amount.

There is a facial chronology conflict requiring qualification: the foreclosure deed is transcribed as executed and acknowledged on **November 3, 1997**, but names Zouhair as trustee of Eighteen Brimmer Street Realty Trust “u/d/t dated **December 1, 1997**.” Recording on December 2 is unambiguous. Until the source owner completes the requested date recheck, preserve both printed dates, do not infer that the trust existed on November 3, and do not use the execution date to start an unquestioned trust-title interval. The date conflict does not alter the December 2 recording observation.

## Trustee instruments and later signatures

**Review basis:** transcription consistency only. No Plymouth original images are saved. The source owner visually reviewed the public-registry images and preserved one-page manual transcriptions for 28008/229 and 28008/230.

Both instruments were executed and acknowledged **December 14, 2000**, then recorded together **April 21, 2004 at 12:01**:

- In 28008/229, Hicham describes himself as sole trustee of 400 Boylston Street Realty Trust and, under beneficiary directions and Section Seven, removes Abdul Rahman as trustee.
- In 28008/230, Zouhair signs a resignation as trustee under Section 7.1.

Neither instrument identifies beneficiaries, a cause, a separate effective date, the family Settlement Agreement, or an explanation for delayed recording. Their shared signing date is also the date alleged for the family agreement in later litigation, but temporal coincidence is not documentary linkage.

The later deed 19629/323, executed March 30, 2001, bears signatures by **Hicham, Abdul Rahman and Zouhair as trustees**. This conflicts with a simple narrative that the December instruments conclusively ended Abdul Rahman's and Zouhair's trustee roles at signing. Unless the exact governing trust provision establishes another effective rule, the timeline should use April 21, 2004 as the registry event and retain December 14, 2000 as the execution/acknowledgment date in notes. It should not construct an uninterrupted Hicham-only interval beginning in 2000 or offer an opinion on the legal validity of the 2001 deed.

The new Hassull certificates are consistent with a separate, qualified chronology:

- 22123/77, recorded immediately before the May 2002 deed, is signed by Gregory Sullivan and Hicham and describes them as the sole trustees. It documents beneficiary direction but not beneficiary identities or shares.
- 27625/56, recorded immediately before the February 2004 deed, is signed by both as incumbent trustees. The related deed is signed only by Gregory, which is consistent with the declaration's one-trustee execution clause; it is not proof that Hicham left office.
- 48873/282, signed August 14, 2017, says Gregory is current trustee and Hicham would be successor if Gregory ceased serving. The related deed executed August 30 nevertheless names and is signed by both as trustees. An intervening appointment is possible but not established. Preserve the difference and infer neither invalidity nor a specific appointment/resignation.

These Hassull provisions and certificates do not govern the separate 400 Boylston Street Realty Trust.

## Concepts International registry packet

**Review basis:** direct visual review of saved page images for the dispositive pages: French and English consent pages/signature counterparts (packet pages 3–7) and French/English LLC-agreement opening and signature pages (pages 9, 12, 13 and 16). I also checked the packet's saved OCR/text and the full local PDF metadata. The PDF is a certified Nanterre commercial-registry copy deposited November 6, 2019.

The English LLC agreement says it was entered into as of **October 2, 2014 by Tarek Ali Hassan as sole member**. The management clause vests management solely in the member, and the final English signature page is signed over the printed name Tarek Ali Hassan and title “Sole Member.” The corresponding French translation says `associé unique`. This supports Tarek's sole-member status at that dated agreement. It does not establish unchanged ownership after October 2, 2014, consideration for any later investment, or use of proceeds.

The 2019 branch consent states that the undersigned comprise all members of the Board of Managers. The signatures appear **across separate English counterparts**:

- Kedar Deshpande and Scott Schaefer sign one page dated October 14, 2019; Tarek's line is blank there.
- Tarek Hassan signs another copy of the same signature page dated October 17, 2019; the Kedar and Scott lines are blank there.

The combined counterparts therefore support all three as consent signatories/board managers, with completion no earlier than October 17. The French signature page shows Kedar and Scott dated October 14 and a blank Tarek line; Tarek's English counterpart supplies the omitted signature. The November 6 French filing date is distinct from both consent-signing dates.

Board-manager capacity in 2019 is not membership or equity evidence. The consent establishes a French branch and appoints Joel Dion and Raman Rekhi to branch-manager roles. Its footer says “Managers Consent re Merger,” but the reviewed operative text concerns the branch; it does not document a merger consideration or capitalization table. It refers to an Exhibit A delegation policy and bears internal “Page 1 of 7” numbering, while the saved six-page filed Act segment does not appear to contain that exhibit. No detailed Exhibit A terms should be reported as reviewed.

The parent report's current phrasing correctly states the 2014 dated ownership point and the three 2019 signatures across counterparts. The source owner was alerted to retain those limits.

## Corrections requested

1. Clear `loan_amount_usd` on Brimmer assignments 19143/185 and 19491/107 and release 24001/64; keep $618,000 only as the referenced original mortgage face amount.
2. Preserve and recheck the November 3 foreclosure-execution versus December 1 trust-date conflict. Do not derive a November trust-title interval.
3. Remove the suggested $943,000 sum because the 1997 senior balance is unknown.
4. Represent 28008/229–230 as April 21, 2004 registry events with December 14, 2000 execution context and the March 2001 three-signature contradiction.

These requests were sent to the relevant source owners and root. No additional material correction was found in the Concepts packet.
