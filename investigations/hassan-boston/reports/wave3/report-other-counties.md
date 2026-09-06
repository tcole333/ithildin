# Other counties — wave 3

Completed September 5, 2026. Owner: corporate subagent. Profile: `hassan-boston`.

This wave completes the priority Middlesex originals and exact-name coverage assigned after wave 2. Eight events are exported in `evidence/wave3/other-counties/events.csv`; `coverage.csv` records every executed query; `source-url-manifest.json` pairs source references, URLs, artifact hashes, and review status. Findings 15628, 15646, 15647, 15650, and 15659 are new; finding 15618 was refined in place from partial to full original review.

## Groton mortgage and discharge

Middlesex South recorded-land mortgage 83538/298, document 137750, was signed and acknowledged November 21, 2024 and recorded December 3, 2024. All six pages were visually reviewed. Nina Kudla f/k/a Nina F. Centauro grants mortgage covenants to **Houssam Ali-Hassan as mortgagee**, using his 227 Summit Avenue #W305 Brookline address. It secures two notes dated November 15 and November 21, 2024 with total original principal of **$562,000**. Exhibit A describes Lot 108, 1.274 acres, and points to the mortgagor’s title deed at 63603/484. The index labels all three names “Grantor”; the original controls legal capacity. This is a secured-creditor role and does not establish Houssam’s ownership of the Groton property.

Linked instrument 84057/291, document 48731, was fully reviewed across all three pages. The registry filed it May 6, 2025 as a DISCHARGE. Its payoff statement identifies Nina as mortgagor and Houssam as mortgagee, says payoff “shall be satisfied” by $562,000 with no interest or daily interest, and expires June 30, 2025. Houssam signed and acknowledged it April 28, 2025. The export leaves `loan_amount_usd` blank: this is no new advance, and the instrument’s stated payoff is not independent proof that payment occurred.

## Tarek’s 2004 Lexington acquisition

An exact Middlesex South registered-land search found one row for **HASSAN TAREK ALI**. Original document 1354544 is a quitclaim deed from Jay R. and Phyllis J. Goldstein to **Tarek Ali Hassan individually**, conveying Lexington Lot 128, indexed as 5 Lawrence Lane, for **$795,000**. It was executed October 28, 2004 and registered November 2 at book 01292/page 104. The deed identifies Tarek as “of 15 Shasta Drive, North Reading.” All three pages were reviewed.

Transfer Certificate of Title 232457 separately certifies Tarek Ali Hassan as the fee-simple owner of the Lexington parcel at issuance. Its viewer metadata reads `CANCELLED SEE CERT# 232457 BK: 1292 PG: 104 / DOC# 1354544`; because that number is the certificate being displayed and the body says it came from certificate 192808, the line appears to describe the prior-certificate transition rather than identify a later successor. The interface label is not treated as present-title proof.

A bounded exact Certificate Search for 232457 returned seven associated entries. The deed was filed November 2, 2004; the two latest entries, documents 1356582 and 1356583 on November 22, are discharges of pre-sale mortgages involving Jay R. Goldstein and Salem Five Cents Savings Bank or Eastern Bank. No later deed or successor-certificate entry appeared in the exact result set as of September 5, 2026. This narrows the continuation question but is still an index result rather than a fresh current-title certificate or assessor confirmation. The exact full name and 15 Shasta address, which also appears in the 2005 Norfolk deed for Zouhair/Madiha, support resolution to the investigation target. Shared address evidence is not kinship evidence.

## FY2026 Lexington assessment observation

The Town of Lexington’s online assessment database, hosted by Vision Government Solutions, lists parcel **PID 243 / Mblu 4/ /68/ /** at 5 Lawrence Lane. In its static **FY2026** snapshot, the `Owner of Record` is **HASSAN TAREK ALI**. The assessment is $667,000 for improvements plus $718,000 for land, or **$1,385,000 total**. Its ownership panel repeats the $795,000 sale price, November 2, 2004 sale date, and book/page **01292/0104**, exactly linking the parcel to the deed and certificate reviewed above. The assessor’s certificate field is blank.

Lexington states that its public database is a static annual snapshot extracted each January and approved by Massachusetts DOR/DLS. This is therefore a current FY2026 municipal assessment observation and deed pointer. It is recorded separately from registered title and does not establish current equity, a lien balance, or a newly certified title state.

## 15 Shasta Drive title check

The registry’s town lists place **North Reading in the Middlesex South district**, not the North district. A South registered-land address search returned zero. The South recorded-land address search for 15 Shasta, default date range January 1, 1900 through September 5, 2026, returned six records.

- 26113/433: 1996 deed, Caruso Home Stylists Inc. to Carmine Petrosino, $110,000.
- 41297/20: 2003 deed, Carmine Petrosino indexed as grantor and grantee, with Shasta Realty Trust as grantee.
- 79736/302: 2022 homestead, Carmine Petrosino as trustee and Shasta Realty Trust as indexed grantors.

The remaining results are a 1996 mortgage, a 2013 homestead, and a 2022 discharge. No Hassan is an indexed party in this bounded address result set. The address therefore remains evidence of residence or mailing use by Tarek and later Zouhair/Madiha, not proof that they owned 15 Shasta. Original instruments in the Petrosino/Trust chain were not opened; no beneficial ownership beyond the index is inferred.

## Exact-name coverage

All queries used Name Search, party type Both, middle name blank, and the registry’s default date range. South displayed January 1, 1900 through September 5, 2026. North’s advanced panels displayed January 1, 1901 through September 5, 2026.

| Name query | South recorded | South registered | North recorded | North registered |
|---|---:|---:|---:|---:|
| HASSAN / HICHAM | 0 | 0 | 0 | 0 |
| HASSAN / ZOUHAIR | 0 | 0 | 0 | 0 |
| HASSAN / ABDUL RAHMAN | 0 | 0 | 0 | 0 |
| HASSAN / HOUSSAM | 0 | 0 | 0 | 0 |
| HASSAN / TALAL | 0 | 0 | 0 | 0 |
| HASSAN / TAREK | 0 | 1 resolved target deed | 0 | 0 |
| ALI-HASSAN / HOUSSAM | 2 resolved Groton instruments | 0 | 0 | 0 |
| ALI-HASSAN / ZOUHAIR | 0 | 0 | 0 | 0 |

Middlesex North’s Recorded Land menu separately exposes **Pre-1976 Grantor Index** and **Pre-1976 Grantee Index** modes. Those modes were not run, so the standard-name zeroes are not a complete pre-1976 absence claim. Every zero is limited to the exact entered spelling, office, party choice, and stated UI range. No unrelated namesakes were promoted.

## Limits and concrete follow-ups

- Broader observed spellings such as Hachim/Hisham/Hesham, Zuhair/Zouheir, Abdelrahman/Abdur Rahman, Hossam/Hussam/Husam, and Tarik/Tariq were not expanded across all four office/district combinations in this bounded wave. Exact canonical names and the record-proven hyphenated forms were prioritized.
- Vehicle-name searches were not expanded in Middlesex North because no Northern District property nexus emerged. Suffolk and Plymouth remain owned by other agents.
- The 3 Summit Avenue mortgage exhibit gives title reference 63603/484. That deed was not opened after the original/discharge priority was completed; it is a concrete mortgagor-title follow-up, not evidence of Houssam ownership.
- The exact certificate 232457 search found no post-2004 transaction, and the FY2026 assessor carries the same owner and deed pointer, but a freshly certified registry title statement remains necessary before presenting registered title as current.
- A current North Reading assessor card remains unexecuted. The recorded 15 Shasta chain is sufficient to reject the address-as-title inference, but it is not a current municipal assessment.
- The browser’s `pageAssets.bundle` call hung for about 24 minutes and produced no usable output. Papercut #2708 records the failure. All priority originals were instead reviewed and preserved through the ordinary official image viewer screenshots.

No present balance, payoff receipt, beneficial trust ownership, family relationship, or current title is inferred beyond what the cited records state.
