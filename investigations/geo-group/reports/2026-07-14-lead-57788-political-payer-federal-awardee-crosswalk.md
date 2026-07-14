# GEO political payers versus federal awardees

Lead `#57788` | Profile `geo-group` | Thread `112` | Evidence reviewed through 2026-07-14

## Bottom line

The scoped political records show a durable entity split, but not a proven avoidance scheme.

Across **26 recipient-reported corporate-payment rows** in 2016, 2024, and 2025, the reported payer was **GEO Corrections Holdings, Inc.; GEO Acquisition II, Inc.; or GEO Reentry Services, LLC**—not the parent federal awardee. The parent, **The GEO Group, Inc.** (`UEI JMLKZZ1NL2Z6`, `CAGE 3JMR1`), had **1,128 DHS prime-award actions** in the bounded 2015–2026 ledger and was an active ICE awardee on every tested payment date. Depending on the date, six to fifteen distinct parent-awarded ICE orders met the conservative overlap test.

That supports the descriptive part of H1: GEO used subsidiaries with **no exact direct-award match in the bounded records** as the named political payers in this sample. It does **not** establish that GEO selected those entities to evade federal-contractor restrictions, obtain contracts, or influence officials. H0 presently has the stronger documented explanation: SEC filings show distinct subsidiaries; GEO's attributed MUR 7180 response described a 2013 REIT restructuring, taxable subsidiaries, holding-company functions, and separate contracting entities. Because that explanation comes from GEO's own enforcement response, it is evidence of GEO's stated rationale—not independent proof that ordinary accounting explains each payment.

## Entity crosswalk

| Political or corporate entity | Political-record treatment | Federal-recipient result | ICE/DHS relationship |
|---|---|---|---|
| **GEO Corrections Holdings, Inc.** | Two Rebuilding America Now receipts and one inaugural donation, $475,000 in the scoped Trump-related rows; MUR 7180 later addressed a broader $945,000 | SEC-verified subsidiary; no exact current SAM registration, UEI, or direct award match in the bounded records | Parent had 6–7 active ICE awards on the three scoped dates; MUR 7180 disputed whether affiliate integration brought GCH within the contractor ban |
| **GEO Acquisition II, Inc.** | 13 recipient receipts totaling $2.125 million in 2024; three totaling $250,000 in 2025 | SEC-verified subsidiary/guarantor; no exact current SAM registration, UEI, or direct award match | Parent had 10–15 active ICE awards on the payment dates |
| **GEO Reentry Services, LLC** | Seven recipient receipts totaling $1.415 million in late 2025 | Current SAM exact match: `CLKXSJLN8EN1`, `7G0N6`; no exact direct contract in USAspending/HigherGov tests and zero DHS actions in the bounded ledger | Parent had 14 active ICE awards on each scoped payment date |
| **GEO PAC / C00382150** | Employee-funded separate segregated fund. The Trump-Vance inaugural Form 13 reports a $500,000 payer label, but no matching PAC Schedule B payment was found | Not a procurement entity; no award match expected | Must not be conflated with parent or subsidiary corporate treasury |
| **The GEO Group, Inc.** | No verified parent-treasury payer row in the scoped ledger. Recipient abbreviations tested as `THE GEO GROUP` reconciled to donor-side GEO PAC rows where date, recipient, and amount matched | Current SAM exact match: `JMLKZZ1NL2Z6`, `3JMR1`; 343 exact-UEI HigherGov contract rows in the query | 1,128 bounded DHS actions; direct ICE awardee throughout the scoped dates |

The machine-readable [CSV](./2026-07-14-lead-57788-political-payer-federal-awardee-crosswalk.csv) and [JSON](./2026-07-14-lead-57788-political-payer-federal-awardee-crosswalk.json) preserve the entity IDs, payment windows, amounts, UEIs/CAGEs, negative-result qualifications, and payment-date award counts.

## SEC identity proof

GEO's [2017 Exhibit 21.1](https://www.sec.gov/Archives/edgar/data/923796/000119312517056831/d320699dex211.htm) is titled “The GEO Group, Inc. Subsidiaries” and lists the exact legal names **GEO Acquisition II, Inc. (DE)**, **GEO Corrections Holdings, Inc. (FL)**, and **GEO Reentry Services, LLC (FL)**.

The [2024 Exhibit 21.1](https://www.sec.gov/Archives/edgar/data/923796/000095017024023181/geo-ex21_1.htm) states that, unless otherwise noted, GEO holds the listed subsidiaries “directly or indirectly 100%” and lists GCH and Reentry. Acquisition II is absent from that significant-subsidiary list, but the same filing's [Exhibit 22.1](https://www.sec.gov/Archives/edgar/data/923796/000095017024023181/geo-ex22_1.htm) lists all three as subsidiary guarantors. The [2025 Exhibit 22.1](https://www.sec.gov/Archives/edgar/data/923796/000095017025029972/geo-ex22_1.htm) again lists all three. These filings establish distinct legal names and parent control; they do not identify which bank account funded a political payment.

## Political-payment identity

The underlying FEC ledger preserves the payer label exactly as filed rather than forcing every `GEO` string into the parent.

- GCH: Rebuilding America Now reported **$100,000 on August 19, 2016** and **$125,000 on November 1, 2016**. The 58th Presidential Inaugural Committee reported **$250,000 on December 10, 2016**. GEO's MUR response independently acknowledged the two Rebuilding America Now checks.

- Acquisition II: five federal committees reported 13 2024 receipts totaling **$2.125 million**. CLF reported three more 2025 receipts totaling **$250,000**. Punctuation and one recipient misspelling were normalized only after matching the SEC name, dates, addresses, and surrounding filing context.

- Reentry: six federal committees reported seven late-2025 receipts totaling **$1.415 million**, including MAGA Inc.'s October 9 **$1 million** line-17 receipt.

- GEO PAC: C00382150's donor-side filings establish a separate employee PAC stream. The Trump-Vance Inaugural Committee's amended Form 13 reports `THE GEO GROUP, INC. POLITICAL ACTION COMMITTEE`, December 11, 2024, **$500,000**, but no matching GEO PAC Schedule B disbursement was located. That remains a **committee-reported payer label with unresolved funding stream**, not a verified PAC check and not a corporate-treasury payment.

The arithmetic context for the 26 corporate rows is $4.265 million, but it combines super-PAC receipts, hybrid-PAC non-contribution-account receipts, and inaugural donations. It is not one legal contribution category or a complete GEO political-spending total.

## Award match and payment-date overlap

Current local SAM exact-name searches matched only:

- `THE GEO GROUP, INC.` → `JMLKZZ1NL2Z6`, `3JMR1`;
- `GEO REENTRY SERVICES LLC` → `CLKXSJLN8EN1`, `7G0N6`.

They did not match GCH, Acquisition II, or GEO PAC. Current SAM is not a historical snapshot, so those negatives cannot establish registration status in 2016, 2024, or 2025.

Bounded exact award searches found no direct federal contract for GCH, Acquisition II, or Reentry. The verified DHS action ledger likewise has zero actions for those three payer identities and 1,128 for the parent. For payment-date overlap, an award was counted only when: the exact parent UEI matched; the award action occurred on or before the payment date; and the recorded performance period covered that date. Examples include:

- August 19, 2016: seven parent ICE orders, including `HSCEDM16J00004` (South Texas), `HSCEDM16J00017` (Rio Grande), and `HSCEDM16J00019` (Broward).
- February 9, 2024: eleven parent ICE orders, including `70CDCR23FR0000045` (South Texas), `70CDCR24FR0000001` (Aurora), and `70CDCR24FR0000011` (Adelanto).
- October 9, 2025: fourteen parent ICE orders, including `70CDCR25FR0000029` (Delaney Hall), `70CDCR25FR0000091` (South Texas), and `70CDCR25FR0000100` (Broward).

These overlaps establish simultaneity and legal-entity difference. They do not establish a quid pro quo, procurement causation, or evasion purpose.

## MUR 7180: what was and was not decided

The [FEC matter page](https://www.fec.gov/data/legal/matter-under-review/7180/) records a 5–0 reason-to-believe vote concerning GCH and the federal-contractor prohibition. In 2021 the Commission deadlocked 3–3 on probable cause and separately 3–3 on no probable cause, then voted 6–0 to close the file. The result was **no final probable-cause finding, adjudicated violation, or civil penalty**.

The primary record contains genuine competing views:

- GEO's [January 2017 response](https://www.fec.gov/files/legal/murs/7180/7180_15.pdf) stated: “GEO Corrections Holdings, Inc. was not a federal contractor during the relevant period.” It identified Reentry—not GCH—as party to the Louisiana subgrant agreement and Cornell—not GCH—as the D. Ray James contractor. It also said the 2013 REIT conversion required “separate legal wholly-owned operating business units known as ‘taxable REIT subsidiaries.’”

- Commissioners Broussard and Weintraub [wrote](https://www.fec.gov/files/legal/murs/7180/7180_38.pdf) that GCH's “management, finances, and governing policies are so tightly interwoven” with affiliates that they constituted a single entity for the prohibition.

- Commissioners Dickerson, Cooksey, and Trainor [wrote](https://www.fec.gov/files/legal/murs/7180/7180_39.pdf) that the investigation showed GCH was not the named contractor and rejected enforcement based on OGC's separate-and-distinct theory.

Those documents explain the deadlock. Neither bloc's statement is a court judgment or a final Commission finding.

## Hypothesis assessment and Tier 2 gate

**H1 — subsidiaries with no exact direct-award match in the bounded records serve as named political payers:** supported as a descriptive pattern. The subsidiary payer changes across cycles—GCH in 2016, Acquisition II in 2024 and early 2025, Reentry in late 2025—while the parent remains the central direct ICE/DHS awardee. If “vehicle” is used as shorthand, it means only “named payer” unless internal records establish purpose.

**H0 — ordinary legal/accounting separation:** better supported as an explanation because the SEC and MUR records document longstanding legal entities, guarantor roles, REIT/tax structure, and separate contracting subsidiaries. But the record does not show the internal approval or bank-account rationale for any specific payment.

The pattern clears a Tier 2 hunch gate **only as a hypothesis**: it is repeated, financially material, network-central, and supported across FEC/SEC/SAM/USAspending-derived records. It does not clear a causal or misconduct gate. The decisive next evidence is GEO's check register, bank-account owner, board/officer authorization, intercompany transfer entries, and historical SAM/award lineage for each paying subsidiary.

## Coverage and limitations

The [source manifest](./2026-07-14-lead-57788-source-coverage-manifest.json) records each positive and negative query. The USAspending subaward command returned apparently unfiltered pages; exact local post-filtering found no GEO payer-name match, but those pages were excluded and the defect was logged as papercut `#923`. No live SAM call was made.

The three MUR PDFs were also visually inspected from 150-DPI page renders, not merely text-extracted. The respondent response renders cover PDF/printed response pages 1–4, including the GCH/Reentry assertion on page 1, the Louisiana/Reentry contract discussion on page 3, and the REIT/GCH holding-company discussion on page 4. The Broussard/Weintraub statement renders cover all three pages, including the failed probable-cause statement and their integrated-entity reasoning. The Dickerson/Cooksey/Trainor renders cover pages 1–2, including their named-contract and separate-and-distinct reasoning. The durable render directory is [`2026-07-14-lead-57788-pdf-qa`](./2026-07-14-lead-57788-pdf-qa/); the manifest preserves page, Bates, hash, and local-path metadata. All inspected pages were legible and unclipped.

Negative results are bounded. They do not prove no historical registration, subaward, grant-funded state agreement, lease, intergovernmental arrangement, or award under a different legal identity. Recipient FEC filings do not prove the owner of the payer's bank account. The MUR respondent's factual assertions are attributed to GEO, and the commissioner statements are attributed to their authors.
