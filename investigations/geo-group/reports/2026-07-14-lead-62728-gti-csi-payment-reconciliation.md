# GTI–CSI ICE Air subcontract and payment reconciliation

**Lead:** 62728  
**Builds on:** lead 57836 and findings 12892–12895, 12899, 12901, 12906–12907, 12909–12912, 12914, 12916  
**New accepted finding:** 12940  
**Pending human action:** 68  
**As of:** 2026-07-14  
**Evidence package:** [money/claim matrix](2026-07-14-lead-62728-gti-csi-payment-reconciliation-matrix.json) · [source manifest](2026-07-14-lead-62728-gti-csi-payment-reconciliation-source-manifest.json) · [archived primary sources](../sources/2026-07-14-lead-62728/sha256sums.txt)

## Bottom line

No public signed GTI–CSI subcontract or amendment, option-exercise notice, GTI invoice, CSI accounts-payable or payment ledger, remittance record, or quantified GTI cash receipt was found after searches of GEO SEC filings, the formal USAspending advanced subaward endpoint, SAM data, CourtListener/RECAP, DHS-released procurement records, and Florida UCC records.

The new primary evidence narrows—but does not close—the realized-revenue gap. In a transcript filed with the SEC on November 13, 2023, GEO stated: “Our third quarter results reflect an increase in our GTI secure transportation revenues. This increase was primarily driven by our new emergency contract to provide air operations in support for ICE.” A transcript filed February 22, 2024 similarly said the year-over-year increase in fourth-quarter 2023 secure-transportation revenue was “primarily driven” by the air-support contract. These are GEO's filed statements that the contract affected recognized secure-transportation revenue. They do not prove the dollar amount, margin, cash collection, subcontract face value, payment schedule, or GTI's share of CSI's federal receipts.

The DHS-released statement of work identifies the best agency-held financial records to request. CSI's DSLA invoices run in 14-day periods, SHRC invoices by single mission, and both use an ICE invoice template plus flight-hour/cost information and flight logs. CSI must submit an electronic RPA Invoice Charter Air Template (ICAT) and supporting documents to the contracting officer's representative and ICE's ERO RPA team; discrepancies must be corrected before final submission. ODC invoices require receipts and COR approvals. For government-cancellation reimbursement, the SOW expressly requires receipts substantiating costs, including “payment receipts to subcontractors.” Routine security-crew cost, however, is embedded in CSI's fixed flight-hour rate, so an ordinary prime invoice may not separately identify GEO or GTI.

## Money and claim boundaries

| Layer | Public measure | What it establishes | What it does not establish |
|---|---:|---|---|
| CSI ICE Air BPA 70CDCR24A00000001 | $3.6 billion potential ceiling | Maximum prime-vehicle authority | Revenue, obligations, payments, or GEO share |
| Known CSI orders/calls | Cumulative obligations and outlays by instrument; see lead 57836 matrix | Federal commitment and disbursement to the prime level | CSI-to-GTI payment |
| 2023 emergency GTI subcontract | Up to about $16 million over nine months if the full term ran | GEO's conditional forecast | Realized revenue or cash |
| Q3/Q4 2023 GEO filed statements | Qualitative increase in secure-transportation revenue, primarily driven by ICE air support | GEO said the contract affected recognized segment/division revenue | Amount, margin, cash receipt, subcontract terms, or option exercise |
| March 2024 five-year subcontract | About $25 million expected annualized revenue; contract includes option periods | GEO's forward-looking estimate and disclosed subcontract role | Guaranteed value, exercised options, realized revenue, or cash |
| 2025 investor scenario | $40–$50 million potential incremental annualized revenue at a 500,000-removal scenario | Management sensitivity/forecast | Actual removals, award value, realized revenue, or payment |
| 2025 performance statement | Support services “continued to steadily increase” | Qualitative performance trend | Dollar amount, margin, or cash |

Amounts across these rows are not additive.

## Corrected public-subaward coverage

Lead 57836 used the generic `/api/v2/subawards/` route. During this pass, the local wrapper was found to ignore or misapply recipient filters and return an unrelated fixed corpus for name/UEI searches (papercut 978); that wrapper output was discarded.

The coverage test was rerun through USAspending's formal advanced endpoint, `POST /api/v2/search/spending_by_award/`, using `subawards: true`, `spending_level: "subawards"`, contract award-type codes A–D, and a 2023-01-01 through 2026-07-14 date range. Three independent filters returned zero rows:

1. recipient text `GEO Transport, Inc.`;
2. recipient identifier `DFEKRCYPZD84`;
3. award IDs 70CDCR23FR0000035, 70CDCR24FR0000024, 70CDCR24FC0000003, 70CDCR25FR0000022, and 70CDCR26FC0000001.

This reproduces the bounded conclusion in finding 12901 using the documented advanced-search route. It is only a public FSRS/USAspending coverage result. It does not prove there was no subcontract or no payment.

## SEC reconciliation

### Emergency subcontract

- **Forecast, August 15, 2023:** GEO expected “up to approximately $16 million in revenues over a nine-month period, assuming the contract runs through its full term.” This is explicitly conditional.
- **Role:** GEO's executive chairman said the company was a subcontractor to a prime and supplied “the security staffing on the airplane.”
- **Recognized-revenue effect, November 13, 2023:** GEO said third-quarter GTI secure-transportation revenue increased and that the emergency ICE air contract was the primary driver.
- **Recognized-revenue effect, February 22, 2024:** GEO said fourth-quarter 2023 secure-transportation revenue increased year over year and that the air-support contract was the primary driver.

The filings do not separately report emergency-subcontract revenue. A separate CFO statement attributes higher overall transportation revenue to the ICE air contract and higher international revenue to an Australian health-care contract, reinforcing why a combined segment percentage cannot be allocated to GTI air support alone.

### Long-term subcontract

GEO's May 13, 2024 SEC filing disclosed that GTI was CSI's subcontractor under a five-year contract inclusive of option periods and expected about $25 million in annualized revenue. That remains a forecast. A 2025 investor presentation modeled $40–$50 million in incremental annualized revenue if annual removals rose from a 160,000 baseline to 500,000; it is a scenario, not realized revenue. A February 12, 2026 filing stated only that ICE air-subcontract support “continued to steadily increase throughout 2025.”

## CourtListener/RECAP coverage

The public docket for *Classic Air Charter, Inc. v. United States*, No. 1:25-cv-00286 (Fed. Cl.), includes an agency-certified administrative-record index. It inventories CSI's January 2023 quote, a memorandum concerning oral-presentation subcontractors, CSI's December 2023 quote and discussion responses, price and technical evaluations, responsibility documents, and the March 8, 2024 award. The filing states that the administrative record was filed under seal pursuant to the Court of Federal Claims protective order; the docket also records delivery of the record to the clerk by portable storage/file share.

That index proves the existence of agency/court-held record categories, not the contents of a GTI subcontract or payment. Public CourtListener searches for `"GEO Transport" "CSI Aviation"`, `"GEO Transport" subcontract invoice`, and `"CSI Aviation" subcontract invoice` produced no public GTI payment exhibit. Sealed filings were not treated as accessible evidence.

## DHS invoice architecture and FOIA targets

The released BPA SOW provides a precise record map:

- DSLA flight invoices cover 14-day periods; SHRC invoices cover single missions.
- Invoices include routes, flight hours, associated costs, flight logs, and relevant ODCs.
- The ICAT/RPA process records charter-service and other covered costs electronically, with supporting documentation, COR review, and correction of discrepancies before final submission.
- ODC invoices require legible receipts and approval documentation.
- Expedited SHRC additional-cost requests may require invoices showing extra subcontractor costs.
- Government-cancellation claims require payment substantiation, including payment receipts to subcontractors.
- DSLA fixed flight-hour rates include the security crew; large SHRC hourly rates include 15 security guards, while additional guards can be billed as ODCs.

The resulting FOIA should request financial/vendor-identification portions of ICATs, invoice support, COR approvals and discrepancy logs, cancellation claims, expedited-SHRC cost support, and subcontractor receipts that contain `GEO Transport`, `GTI`, or UEI `DFEKRCYPZD84`. It should expressly permit exclusion or redaction of passenger identities, itineraries, routes, tail numbers, crew identities, operational tactics, and other security-sensitive details. Because ordinary guard costs are bundled into the prime flight-hour rate, the request must not assume every invoice identifies GTI.

## SAM and Florida UCC coverage

Live SAM contract/opportunity calls were rate-limited with HTTP 429 and were not retried. The local March 2026 public entity extract confirms CSI Aviation, Inc. (UEI D5BNEHB3UL89, CAGE 1HTW5) and GEO Transport, Inc. (UEI DFEKRCYPZD84, CAGE 6PV86), but contains no subcontract or payment term.

The official Florida UCC exact-name search returned seven GEO Transport filings. Their listed secured parties are Alter Domus, Ankura Trust, and Citizens Bank; CSI Aviation is not listed. These are general financing filings and do not disclose the ICE Air subcontract or payment chain. The absence of CSI as a secured party is not evidence of nonpayment.

## Exhausted public-source result

The public record presently supports four separate propositions:

1. GEO disclosed that GTI served as CSI's ICE Air security-support subcontractor.
2. CSI received prime-level federal obligations and outlays.
3. GEO stated that the emergency contract primarily drove an increase in recognized secure-transportation revenue in Q3 and Q4 2023.
4. The public sources reviewed do not quantify CSI-to-GTI obligations, invoices, payments, GEO's realized subcontract revenue, or cash collections.

The shortest path to the remaining evidence is an ICE FOIA keyed to the SOW's invoice repositories and the sealed administrative record's subcontractor/quote categories. A signed private subcontract or CSI accounts-payable ledger may not be an agency record; the request is therefore limited to records ICE received, created, reviewed, or retained.

## Papercuts logged

- **978:** the generic USAspending subaward wrapper ignored/misapplied recipient filters; formal advanced endpoint used instead.
- **981:** the Florida UCC tool completed successfully but silently failed to write `search_log` because it used the legacy `log_search` signature inside a swallowed exception.
- **983:** `human_actions.related_lead_id` references the stale `leads_old_backup` table. Action 68 retains the lead number in its title and notes, while the broken foreign-key field is left unset.
