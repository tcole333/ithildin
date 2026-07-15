# GEO-CDR BAKER / FDEM corporate and contract package

**Leads:** 60501 and 60503  
**Thread:** 114  
**Research date:** 2026-07-14  
**Disposition:** both blocked; each stop condition remains unmet

## Bottom line

The public record establishes GEO-CDR BAKER, LLC as the North Florida management entity, GEO's joint control with an unnamed independent contractor, FDEM purchase order PO-010844, and five posted Florida expense warrants to the LLC. It does not establish the LLC's legal member schedule or name CDR Maguire Inc. as a member. It also does not expose PO-010844's signed rate schedule, term, modifications, or a crosswalk from the five FLAIR transactions to the PO and its two visible line descriptions.

The strongest new evidence is the official Florida Accounting Information Resource (FLAIR) source family. Five statewide-document and departmental exports identify invoice numbers, agency-document numbers, amounts, posting dates, warrant numbers, warrant dates, and the warrant type `Expense`. Together they total **$28,897,523.51**. These are five transactions within one FDEM/FLAIR payment-chain source family, not five independent corroborating contexts. “Posted” and the presence of a warrant number/date do not establish that a warrant cleared or was cashed.

## Lead 60501 — operating agreement and member schedule

Florida Division of Corporations record L25000395700 identifies GEO-CDR BAKER, LLC, formed August 28, 2025. The current public record names George C. Zoley, Carlos Duart, and Tina Vidal-Duart as managers; the 2025 record also named J. David Donahue, who is absent from the April 29, 2026 annual report. A manager designation is not a member designation.

GEO's third-quarter 2025 Form 10-Q says that on August 28, 2025 it entered an agreement with “another contractor” to form the management entity for the 1,310-bed North Florida Detention Facility. GEO says it shares joint control with that independent third-party contractor and accounts for the investment under the equity method. The filing does not name the contractor or disclose an ownership percentage, capital contribution, voting allocation, distribution formula, or profit-sharing term.

CDR Maguire's official Florida registry page names Carlos Duart as CEO and Tina Vidal-Duart as EVP. That officer overlap authenticates an affiliation with two GEO-CDR BAKER managers. It does **not** prove that CDR Maguire is a legal member of GEO-CDR BAKER. No operating agreement, member schedule, ownership ledger, court exhibit, or SEC exhibit resolving the unnamed contractor was recovered. The ownership/member matrix therefore leaves the CDR member field `unproven`.

The official Sunbiz index exposes the formation, September 9, 2025 amendment, and April 29, 2026 annual-report image links. Direct retrieval returned Cloudflare interstitial HTML rather than the scanned documents; the in-app browser runtime was unavailable. Those interstitial responses are preserved as negative-access artifacts and are not cited for substantive contents. Unified-registry snapshots and the official indexed page support the manager-level facts, not a member-level conclusion.

Lead 60501 is blocked on the exact documents requested in pending human action **76**: the formation/amendment images and any agency-held operating agreement, member schedule, or vendor-responsibility/ownership materials. No request was submitted during this task.

## Lead 60503 — PO terms, rates, invoices, and payment status

The agency-generated public purchase-order production shows PO-010844 issued October 17, 2025 to GEO-CDR BAKER, LLC, method O2, mission 00354, and total authorization **$100,357,654.76**. The visible line descriptions are `Monthly rate` and `Mobilization`. The amount is an authorization, not an amount paid. The linked signed terms object, `069cs00001C12EsAAJ`, redirects to authenticated Salesforce access. No signed schedule or modification was recovered from the public portal, FACTS exact searches, official indexed searches, or the Wayback Machine.

FLAIR adds the transaction identifiers missing from the prior Transparency Florida result:

| Warrant date | SWDN | Agency document | Invoice | Amount | Warrant | Status/type |
|---|---|---|---|---:|---|---|
| 2026-01-07 | D6000294462 | V0016050001 | 33.00_001 | $5,000,000.00 | 0494827 | Posted / Expense |
| 2026-01-26 | D6000330868 | V0018070002 | 33.00_002 | $7,946,471.23 | 0538334 | Posted / Expense |
| 2026-05-11 | D6000512228 | V0032180001 | 33.04_003 | $7,946,471.23 | 0838840 | Posted / Expense |
| 2026-06-29 | D6000601410 | V0040420001 | 33.04_005 | $7,946,471.23 | 0979363 | Posted / Expense |
| 2026-06-29 | D6000601421 | V0040540001 | 9.00_006B | $58,109.82 | 0979365 | Posted / Expense |

The official vendor export separately lists masked vendor ID `F3941XXXXX`, sequence `001`, name `GEO|CDR BAKER LLC`, a Miami address, W-9 status `Y`, the description `W9 ON FILE, PASSED IRS TIN MATCHING`, and EFT indicator `N`. The W-9 is tax-registration evidence, not member evidence. `EFT=N` is only the vendor-file indicator; it does not establish the instrument or clearance status of a particular transaction.

The PO authorization equals $5,000,000 plus twelve times $7,946,471.23 exactly. This is a **medium-confidence arithmetic observation only**. Without the signed schedule it does not prove that $5 million is the mobilization line, that $7,946,471.23 is the contractual monthly rate, that the term is twelve months, or that any individual FLAIR invoice belongs to PO-010844. Invoice `9.00_006B` also remains unassigned. No database finding was created from the arithmetic.

Lead 60503 is blocked on the documents requested in pending human action **77**: signed terms, complete line/rate/quantity/term schedules, modifications, invoice support, receiving and approval records, a PO-to-SWDN crosswalk, and any public void/reissue/return/clearance status. No request was submitted during this task.

## Database writes

- Added and verified findings **13033–13037**, one per FLAIR posted expense warrant. Each finding explicitly collapses the five transactions into one FDEM/FLAIR source family and preserves the no-PO-number and no-cleared/cashed boundaries.
- Added and verified finding **13038** for the FLAIR vendor/W-9 record.
- Added structured manager roles **2580** (J. David Donahue, bounded to August 28, 2025–April 29, 2026), **2581** (Carlos Duart), and **2582** (Tina Vidal-Duart) to existing entity **4980** from Florida Division of Corporations record L25000395700. Manager role **2579** for George C. Zoley pre-existed this package and is not counted as a new write.
- Added the primary-supported FLAIR vendor address to existing entity **4980**. No new entity, member edge, ownership percentage, or CDR Maguire member relation was added; the four manager roles remain manager designations, not member designations.
- Added pending human actions **76** and **77** after confirming no matching action or infrastructure request already existed.
- Reused findings **12669**, **12670**, **12677**, and **12708**. No duplicate ownership or aggregate-payment finding was added.
- No new lead, hypothesis, connection, or infrastructure request was created. `auto_leads.py` was not run.

## Evidence boundaries

Facts in this package are confined to the records' printed fields. The package makes no opacity, influence, intent, favoritism, cleared-payment, or beneficial-ownership inference. Three views of the same Florida accounting chain remain one source family. The same document appearing in a central SWDN export, departmental drilldown, and Transparency Florida is redundancy, not independent corroboration.
