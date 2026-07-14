# GEO-linked ICE IGSA recipient-attribution and payment-gap review

Date: 2026-07-13  
Profile: `geo-group`  
Lead: `57974`  
Skill: `analyze-contract`

## Outcome

The structured federal APIs tested did not provide an attributable obligation for any of the five local-prime IGSAs. Primary local records produced one near-complete annual federal-to-local-to-GEO waterfall (LaSalle), one GEO-agreement-linked fiduciary fund flow that does not name ICE or the downstream payee on the transaction line (Evangeline), and one county budget pass-through/fee trace with unresolved accounting sign and task-order linkage (Clearfield). Charlton and Karnes remain unquantified from primary payment records.

## Payment waterfall matrix

| Facility | Federal prime / PIID | Structured federal recovery | Federal/local inflow recovered | Downstream GEO-linked amount | Local fee | Attribution status | Missing records |
|---|---|---|---:|---:|---:|---|---|
| Folkston / D. Ray James | County of Charlton / `EROIGSA-17-0002` | USAspending: no DHS contract under exact local recipient; HigherGov: no exact award-ID result; SAM: zero exact PIID result | Not recovered | Not recovered | Amount visibly redacted in 2016/2025 local agreement copies | Relationship confirmed (`P00022`; local operating agreement); dollars not attributable | Task orders, ICE payment history, county general ledger/check register, invoices, unredacted fee/rate schedules |
| Pine Prairie / South Louisiana | Evangeline Parish Sheriff’s Office / `EROIGSA-15-0006` | USAspending: none; HigherGov: none; SAM: zero | 2024 Prisoner Maintenance Fund “Inmates” additions: **$39,454,943** | 2024 same fund “Other settlements” reductions: **$39,454,943**; fund definition ties it to the parish-GEO agreement, but the reduction line does not name GEO | Not recovered | GEO-agreement-linked fund flow; not a complete ICE-to-GEO attribution | Federal task orders/payment history; operator contract; accounts-payable detail; checks/EFTs; payer and payee labels; fee schedule |
| Alexandria / Central Louisiana | LaSalle EDD / `DROIGSA-07-0015` | USAspending: none; HigherGov: none; SAM: zero | 2023 audited ICE revenue: **$39,802,562** | 2023 audited “LaSalle Detention Center-GEO” expenditure: **$39,802,794** | 2023 “Administrative GEO Income”: **$180,000** | Near-complete annual waterfall. GEO expenditure / ICE revenue = **100.000583%**; the $232 excess prevents treating it as an exact same-dollar pass-through. The $180,000 fee equals 0.452232% of ICE revenue. | Task-order obligations, monthly invoices/checks, reconciliation of $232 difference, post-2010 amendments |
| Moshannon Valley | County of Clearfield / `70CDCR21DIG000012` | USAspending: none; HigherGov: none; SAM: zero | County 2026 budget lists 2024 actual “GEO / ICE PASS THROUGH” **$4,687,231** | Same account label, but no separate payee transaction line; accounting sign/direction unresolved | 2024 actual “ADMIN FEE FROM GEO GROUP” **$166,667**; 2025 and 2026 budget **$200,000** | County-level trace only. Fee / pass-through account = **3.56%**, but this ratio is descriptive, not a contract rate. | General ledger, checks/EFTs, services agreement, task orders, federal obligations/outlays, accounting explanation for pass-through sign |
| Karnes County IPC | Karnes County / `70CDCR24DIG000018` | USAspending: none; HigherGov: none; SAM: **not tested after daily quota** | Base explicitly obligates **$0**; funded annual task orders required | Not recovered | Not recovered | No amount attributable. Federal base provides invoice-data requirements but not task-order spending or GEO identity. | All funded task orders, operator agreement, invoices/support, federal payment history, fee and payee records |

## Structured-data test details

- HigherGov exact `contract --award-id` lookups returned `[]` for all five PIIDs.
- USAspending prime-contract lookups using exact legal local recipients and DHS returned `[]` for all five. The unconstrained Charlton lookup returned four unrelated Interior/Agriculture purchase orders, confirming that the legal recipient search itself could return records.
- SAM exact PIID award searches returned zero for Charlton, Evangeline, LaSalle, and Moshannon. Karnes was not completed because the API reported the daily limit; do not classify Karnes as a SAM zero-result.
- FSRS/subaward attribution was not recovered. The reviewed records therefore do not support a measured “share visible in federal subaward data.”

## Exact interpretation limits

- LaSalle is the only reviewed case whose audited line items separately name ICE revenue, GEO detention-center expenditure, and GEO administrative income for the same year.
- Evangeline’s fund definition names the GEO agreement, but its $39,454,943 transaction lines are generic “Inmates” and “Other settlements.” They do not independently identify ICE and GEO as payer/payee.
- Clearfield’s adopted budget labels the account “GEO / ICE PASS THROUGH,” but the 2024 actual lacks the parentheses used on most revenue entries. Direction cannot be assigned without ledger context.
- Charlton’s operating agreement confirms an operator/local fee relationship while redacting the values; Karnes confirms funded-task-order and invoice-support architecture without a local operator identity or payment.
- The direct-prime GEO baseline (finding `12403`) shows GEO-affiliate ICE awards are recoverable in USAspending. The five IGSA searches therefore demonstrate a retrieval/attribution gap for these local-prime identifiers, not a universal USAspending failure.

## Findings recorded

`12436`, `12437`, `12438`, `12441`, `12443`, with base/role findings `12404–12408`.

## Lead disposition

Do not complete `57974`. Block pending the enumerated task orders, FSRS/subaward records, local ledgers, invoices, and payment records. The current evidence proves partial local visibility and quantifies LaSalle, but it cannot calculate a five-facility attributable share.

## Learnings

- [Methodology] Reconstruct IGSA spending from three ledgers: federal task-order obligations/outlays, local-government receipts/disbursements, and operator/customer revenue. An IGSA base award can legitimately show zero while annual task orders carry the spending.
- [Source Quality] Local audited statements can yield a more exact downstream trace than recipient-name federal searches, but audit labels vary. Preserve whether a line names ICE, GEO, both, or neither.
- [Methodology] Do not convert equal annual fiduciary-fund additions/reductions into a named payer/payee claim unless the transaction line or note supplies those names.
- [Process Gap] Record API-zero, missing document, redaction, and quota-limited untested state separately.

## Primary sources

- Louisiana Legislative Auditor, LaSalle EDD 2023 audit `00005485`: https://lla.la.gov/publicreports.nsf/0/6fef8ffe87f626c086258b6a0053836f/%24file/00005485.pdf
- Louisiana Legislative Auditor, Evangeline Parish Sheriff 2024 audit `00006009`: https://app.lla.la.gov/publicreports.nsf/0/54a26038f84da60486258ba2006324ac/%24file/00006009.pdf
- Clearfield County 2026 adopted budget: https://www.clearfieldcountypa.gov/DocumentCenter/View/1036/2026-Proposed-Budget-Detail
- Federal and local instruments listed in `report-terms-control.md`.
