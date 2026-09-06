# Suffolk acquisition, title and financing review — wave 3

## Result

This wave converted four core Suffolk property chains from index leads or partial pages into an original-instrument ledger. The source-owner export contains **28 unique instruments** and **38 parcel-linked event rows**. Twenty-six instruments were read in full. All six images offered for acquisition deed 20630/164 were read, but the deed refers to an Exhibit B attachment that is absent from the viewer. Mortgage 19679/1 remains a page-1-only review; its other eighteen pages are explicitly outstanding.

The strongest acquisition-and-finance pairings are:

- **216–218 Newbury Street:** $2,718,000 acquisition deed and $1,200,000 original-principal Berkshire mortgage recorded in the same June 10, 1996 session. The related fixture filing was continued in 2001, then terminated the same day that Guardian, Berkshire's successor by merger, discharged the mortgage.
- **372–378 Boylston Street / 376 trust:** $2,450,000 acquisition deed and $1,000,000 original-principal Berkshire mortgage recorded in the same minute on April 3, 1995. Guardian discharged the cited mortgage in 2001.
- **18 Brimmer Street:** $325,000 foreclosure acquisition in 1997, expressly subject to a 1994 senior mortgage whose original principal was $618,000. The recorded chain traces that senior mortgage through two assignments to a later release.
- **384–390 Boylston Street:** $4,500,000 acquisition deed in January 2011. The reviewed deed and trust declaration do not identify purchase financing, and this wave did not exhaustively search the separate recording session for it.

Those amount pairs show recorded acquisition consideration and contemporaneous secured debt. They do **not** establish closing disbursement, equity contribution, the source of the difference between deed price and mortgage face principal, later balance, payoff amount or present encumbrances.

## Source and review method

The source was the official [Massachusetts Land Records Suffolk Recorded Land Book Search](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx), reviewed September 5, 2026 by exact book/page. Original pages were visually examined in the public viewer. Registry index entries supplied recording metadata and references; the original instrument controlled when an index party string or amount differed. Canonical citations use `SUFFOLK-DEEDS:<book>/<page>` because the viewer's image-session URLs expire. No locally downloaded certified copy is claimed, except that the already preserved first page of 19679/1 remains available as a local image artifact.

The evidence set is:

- `evidence/wave3/suffolk/events.csv` — 25-column event contract;
- `evidence/wave3/suffolk/documents.json` — instrument-level document, party, capacity, quote and page-status manifest;
- `evidence/wave3/suffolk/scan-observations.md` — detailed original-page transcriptions and limitations;
- `evidence/wave3/suffolk/citation-map.json` — all 28 canonical source references mapped to the official portal;
- `evidence/wave3/suffolk/coverage.json` — counts, chain scope and exclusions;
- `evidence/wave3/suffolk/next-records.csv` — exact remaining Suffolk queue.

Shared instruments covering both Newbury parcels are repeated once per parcel with the same `instrument_id`; their price or original principal is transaction-level and must not be summed across rows. Modern parcel IDs come from the separately established Boston assessment baseline. This is a selected recorded-land review, not a certified or complete title examination. Registered Land/Land Court was outside this source-owner scope.

## Title and trust findings

### 18 Brimmer Street

Zouhair Ali Hassan created the Eighteen Brimmer Street Realty Trust by declaration executed December 1 and recorded December 2, 1997 at **21956/113**. He is the original sole trustee named in the declaration. It is a nominee trust: beneficiary identities and proportions reside in a separate Schedule of Beneficial Interest filed with the trustee, and that schedule is not part of the six recorded pages. All-beneficiary direction governs trust actions. The declaration establishes trustee capacity and governance; it does not identify beneficial owners.

Institutional Asset LLC conveyed 18 Brimmer to Zouhair as trustee through foreclosure deed **21956/120**, recorded December 2, 1997. The auction price was **$325,000**, and the affidavit calls Zouhair's trustee bid the highest bid. The deed says title remained subject to senior mortgage **19143/176**, plus taxes, tax titles and liens to the extent applicable.

The deed has an unresolved facial chronology. It is printed as executed and acknowledged November 3, 1997, yet names the grantee as trustee of a trust under declaration dated December 1. Both dates are preserved without inferring an undocumented earlier declaration or retroactive trust action.

In August 2016, Hicham Ali Hassan, certifying that he was then the only trustee, conveyed the property to Hassan Residential Properties LLC for **less than $100** at **56617/279**. Companion certificate **56617/281** says all beneficiaries authorized and directed the deed, but names none and does not explain how Hicham succeeded Zouhair as sole trustee.

Relevant findings: **15572** (declaration and foreclosure) and **15569** (2016 deed and certificate).

### 216–218 Newbury Street

Zouhair created the 216-218 Newbury Street Realty Trust as original sole trustee on May 24, 1996 at **20592/119**. Its separate beneficiary schedule is absent from the five recorded pages.

Allmerica Financial Life Insurance and Annuity Company, formerly SMA Life Assurance Company, executed acquisition deed **20630/164** on June 5 and recorded it June 10, 1996. It conveyed both the 216 and 218 parcels to Zouhair as trustee for **$2,718,000**. Exhibit A describes both parcels. The deed cites the declaration as 20592/343, but Hicham's 2016 certificate **56617/269** expressly calls that prior `/343` reference a scrivener's error and identifies the declaration as 20592/119. The deed's referenced Exhibit B attachment is missing from the official image set.

In August 2016, Hicham, as only trustee, conveyed both parcels to 216-218 Newbury Street Realty LLC for **less than $100** at **56617/267**. The companion certificate says all unnamed beneficiaries directed the deed. It establishes Hicham's certified capacity for the transaction, but does not document the intervening trustee succession.

Relevant findings: **15635** (1996 declaration/acquisition) and **15570** (2016 deed/certificate).

### 372–378 Boylston Street / 376 Boylston Street Realty Trust

Original declaration **19678/327**, all six pages, names Hicham of Hull and Zouhair of North Reading as original co-trustees. They executed it March 31, 1995; it was recorded April 3. It places beneficial interests in a separate schedule filed with the trustees and absent from the recorded instrument.

Acquisition deed **19678/333**, all seven pages, was executed March 31 and recorded April 3 at 16:20 as document 536. Trust Company of the West, acting only as trustee of Rockwell International Group Trust Real Estate Trust, conveyed the land and buildings numbered 372–378 Boylston to Hicham and Zouhair as trustees for **$2,450,000**. The deed cites predecessor title **16654/336** and includes a schedule of permitted exceptions.

In August 2016, Hicham conveyed the parcel from the trust to 376 Boylston Street Realty LLC for **less than $100** at **56617/271**. Companion certificate **56617/273** states that Hicham was then the only trustee and all unnamed beneficiaries directed the deed. The declaration index identifies intermediate certificate or acceptance records **19728/320**, **20592/118**, **34256/228** and **53977/69**. They remain unread, so the change from the 1995 co-trustees to Hicham's 2016 sole-trustee capacity is not yet narrated.

Relevant findings: **15648** (1995 declaration/acquisition) and **15591** (2016 deed/certificate).

### 384–390 Boylston Street

Hicham of Boston executed declaration **47449/1** on January 4, 2011 as original sole trustee of the 384 Boylston Street Realty Trust. It was recorded January 7. Like the other declarations, it defines a nominee trust and places beneficiary identities and shares in a separate schedule filed with the trustee but absent from the five recorded pages.

Acquisition deed **47449/6**, both pages, was executed January 6 and recorded January 7 at 13:38:37.063 as document 2110. Andrew Fienberg, also written Andrew Feinberg in the deed, acting as successor trustee of the Aidee Realty Trust, conveyed 384–390 Boylston to Hicham as trustee for **$4,500,000**. This original corroborates the price and conveyance later discussed in Fienberg litigation, while the legal owner's court evidence is the appropriate source for the adjudicative history.

In July 2016, Hicham, as only trustee, conveyed the parcel to 384 Boylston Street Realty LLC for **less than $100** at **56448/317**. Companion certificate **56448/319** says all unnamed beneficiaries authorized the deed. Neither the 2011 declaration nor the 2016 certificate identifies those beneficiaries.

Relevant findings: **15649** (2011 declaration/acquisition) and **15590** (2016 deed/certificate).

## Financing and release findings

### 18 Brimmer Street

Mortgage **19143/176**, all nine pages, was executed June 15 and recorded June 20, 1994. Alexander Randall, 5th, and Cameron Hall borrowed **$618,000 original principal** from Interstate National Mortgage Corporation, secured by 18 Brimmer. It was an adjustable-rate loan: 6.625% initial rate, first change July 1, 1995, annual changes using the six-month U.S.-dollar LIBOR index, 2.875-point margin, one-point periodic cap and 12.625% lifetime ceiling.

Interstate assigned the mortgage and note to Crossland at **19143/185**; Crossland assigned them to Guaranty Federal Bank, F.S.B. at **19491/107**. Neither assignment states a new advance or current balance. The 1997 foreclosure deed expressly took subject to the senior mortgage but gives no outstanding amount at that date.

Guaranty signed release **24001/64** in December 1997, acknowledged it December 31, and recorded it July 20, 1999. The release establishes discharge by its recording date but does not identify payoff amount, payer or source. The junior mortgage actually foreclosed at **21879/264** remains a separate next-record priority.

Relevant finding: **15622**.

### 216–218 Newbury Street

Certificate **20630/163** says Zouhair was the only trustee, acted as trustee and not individually, and had beneficiary authority to execute documents for a **$1,200,000 original-principal** Berkshire Life loan. Mortgage **20630/170**, all nineteen pages, was recorded in the same June 10, 1996 session as the acquisition deed. It secures both parcels, rents, fixtures and related property. Rate, maturity and payment terms remain in the separate promissory note.

Financing statement **20630/196** perfects related fixture and personal-property collateral. Continuation **26038/328** continued the filing in March 2001 and states no new advance or balance. UCC-3 **27659/174**, re-read at enlarged top and signature fields, has the **termination** box visibly marked. Field 9 names Guardian Life Insurance Company of America as successor by merger to Berkshire as the secured party of record authorizing the amendment; Lucinda D. Scheerer signed for it. The related mortgage discharge at **27659/175** says the indebtedness secured by 20630/170 “is hereby DISCHARGED.” Both were recorded December 21, 2001. Neither states payoff amount, payer or source.

Relevant finding: **15636**.

### 372–378 Boylston Street

Original mortgage page 1 at **19679/1**, recorded in the same minute as the $2.45 million deed, identifies Hicham and Zouhair solely as trustees/mortgagors and Berkshire Life as mortgagee. It secures **$1,000,000 original principal** with 372–378 Boylston. Pages 2–19 remain unreviewed. Guardian's later discharge **27659/170**, both pages read, states that the indebtedness secured by that mortgage is discharged. It supplies no payoff amount or source.

Relevant findings: **15539** and **15594**.

### 384–390 Boylston Street

The two reviewed 2011 originals, declaration 47449/1 and deed 47449/6, state no mortgage or funding source. A dedicated exact-party and same-date financing search was not completed, so the evidence supports no negative finding about whether separate financing records exist.

## Independent audit corrections resolved

The independent artifact audit identified four material issues, all resolved before delivery:

1. `citation-map.json` now covers all 28 instrument references, and `scan-observations.md` includes the Newbury and both Boylston chains.
2. Finding **15635** now carries certificate **56617/269** and the exact `/343`-to-`/119` scrivener-error quote.
3. Finding **15636** no longer says that the mortgage financed a specific share of the purchase or computes a percentage. It reports only the deed consideration, original mortgage principal and same-session timing, and expressly leaves disbursement and the remaining purchase-fund source unresolved.
4. UCC termination **27659/174** was re-read. The marked termination box, full Guardian successor field and signer are now in the finding, event export and document manifest.

Loan amounts appear only on the three origination mortgages: **$618,000** at Brimmer, **$1,000,000** at 372–378 Boylston and **$1,200,000** at Newbury. Assignments, continuations, terminations and discharges have blank numeric loan fields.

## Remaining Suffolk priorities

1. Read pages 2–19 of mortgage **19679/1** and the 376-trust succession records **19728/320**, **20592/118**, **34256/228** and **53977/69**.
2. Read the foreclosed Brimmer junior mortgage **21879/264** and evidence-led successors or discharge, keeping it separate from the senior 19143/176 chain.
3. Obtain the missing Exhibit B attachment to Newbury deed **20630/164** through a lawful registry or certified-copy route.
4. Read the 419 Boylston declaration **20420/333**, acquisition deed **20428/305** and certificate **56617/265**; resolve liens **61827/227** and **62309/299** and their actual releases.
5. Resolve the Suffolk recording locator and any release or satisfaction for the **$22,373** mechanics-lien judgment described by the legal owner in case **0684CV00302** against the Eighteen Brimmer Street Realty Trust interest. The public court docket's lack of a satisfaction entry is not a present-balance conclusion.
6. Search the 47449 recording session and exact parties for separate 384–390 Boylston financing, and search recorded trustee changes for Brimmer and Newbury.
7. Run bounded later-instrument checks before any present-title or present-lien conclusion. Coordinate Newbury attachment **72957/242** with the Tivoli docket and any later recorded release rather than adding overlapping judgment and attachment amounts.

The complete locator-by-locator queue, status and question is in `next-records.csv`.

## Interpretation limits

- A nominee-trust trustee holds and conveys record title under the instrument; the role does not establish a beneficial percentage.
- Beneficiary-direction clauses establish authority recited for a transaction but do not name the beneficiaries.
- Mortgage face principal is not a later balance, purchase equity, property value or payoff amount.
- An assignment carries recorded rights but is not a new advance. A termination or discharge extinguishes the cited recorded interest without proving who paid, how much was paid or where the funds came from.
- Same-session deed and mortgage recording supports a close temporal and collateral relationship, but not precise settlement disbursement.
- A later trustee certificate establishes the signer's stated capacity for that transaction, not the complete succession history.
- No negative result follows from an absent private beneficiary schedule, a missing attachment, a partial read or a query that was not executed.

## Database record IDs

New findings: **15635**, **15636**, **15648**, **15649**. Refined existing findings: **15539**, **15569**, **15570**, **15572**, **15590**, **15591**, **15594**, **15622**. All new records use profile `hassan-boston`, lead **95686**, primary-source evidence references, quoted text and explicit claim types.
