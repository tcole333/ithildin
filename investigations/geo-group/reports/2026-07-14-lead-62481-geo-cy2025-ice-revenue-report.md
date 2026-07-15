# GEO CY2025 ICE customer revenue and contract-to-ledger reconciliation

Generated: 2026-07-14  
Investigation: `geo-group`  
Lead: `#62481`  
Method: `analyze-filing`, supplemented by `analyze-contract`

## Result

The bounded public record does not contain a complete calendar-year 2025 customer subledger assigning GEO's recognized ICE revenue to direct-prime awards, B.I./ISAP and skip-tracing work, IGSA/public-prime facilities, transportation, invoices, accounts receivable, cash receipts, or individual facilities. It does support a reproducible reconciliation that keeps those measures separate.

GEO reported $2,631,549,000 of consolidated CY2025 revenue and said ICE accounted for 47.6%. Applying that rounded share produces a $1,252,617,324 point estimate, with a purely mechanical nearest-tenth rounding interval of $1,251,301,549.50 to less than $1,253,933,098.50. Those are derived estimates, not company-disclosed ICE dollars.

The direct-prime action ledger contains 124 ICE actions across 34 task/order PIIDs and totals $699,338,118.97 in action-date obligations. The ratio of those obligations to the rounded ICE-revenue point estimate is 55.8301%. The resulting $553,279,205.03 arithmetic difference is not missing money, an IGSA residual, a pass-through estimate, or a revenue allocation. Recognized revenue and federal action-date obligations are different measures, and the filing states that revenue recognition may differ from invoicing.

The public-prime review identifies nine SEC facility rows corresponding to six independent ICE-public-prime-GEO chains, but no compatible CY2025 downstream GEO-receipt total. The review therefore confirms a visibility boundary without establishing that the unresolved amount is material or attributing any part of the arithmetic difference to those chains.

## Reproducible artifacts

- [Action-date obligation ledger](./2026-07-14-lead-62481-geo-cy2025-ice-revenue-action-ledger.csv)
- [Award-lifetime snapshot ledger](./2026-07-14-lead-62481-geo-cy2025-ice-revenue-award-snapshot-ledger.csv)
- [Quarterly revenue and activation ledger](./2026-07-14-lead-62481-geo-cy2025-ice-revenue-quarterly-ledger.csv)
- [Evidence and quotation matrix](./2026-07-14-lead-62481-geo-cy2025-ice-revenue-evidence-matrix.csv)
- [Machine-readable reconciliation](./2026-07-14-lead-62481-geo-cy2025-ice-revenue-reconciliation.json)
- [Source and output manifest](./2026-07-14-lead-62481-geo-cy2025-ice-revenue-source-manifest.json)
- [Deterministic builder](../../../scripts/build_geo_cy2025_ice_revenue_reconciliation.py)

Rebuild command:

```bash
uv run python scripts/build_geo_cy2025_ice_revenue_reconciliation.py
```

## Measurement rules

The reconciliation preserves the following distinctions:

| Measure | Period/entity basis | Permitted interpretation |
|---|---|---|
| SEC recognized revenue | GEO consolidated CY2025 | Revenue under GEO's accounting policy |
| ICE customer percentage | Rounded issuer concentration disclosure | A point/range estimate, not exact ICE dollars |
| Action-date obligations | ICE actions signed during CY2025 for verified GEO/B.I. recipients | Federal legal commitments; not revenue, invoices, cash, or outlays |
| Award snapshots | Current cumulative award-life fields for awards with a CY2025 action | Context only; not a CY2025 flow |
| Outlays | Current award-life outlays where USAspending reports a value | Not a dated CY2025 disbursement ledger; missing values are not zero |
| Local/public-prime records | Instrument-specific fiscal periods and payer/payee chains | Not joinable to GEO CY2025 ICE revenue without downstream remittance records |
| Annualized contract values | Issuer forecasts or run rates | Not recognized CY2025 revenue |

## SEC revenue bridge

### Consolidated and customer concentration

The 2025 Form 10-K reports consolidated revenue of $2,631,549,000. It separately says ICE accounted for 47.6% of consolidated revenue in 2025. Because the percentage is printed to one decimal place, this report treats $1,252,617,324 as a point estimate and also supplies the mechanical rounding interval above.

The same 10-K paragraph says BOP, ICE, and USMS together accounted for 66.6%, while the printed components—2.6%, 47.6%, and 15.9%—sum to 66.1%. A separate concentration presentation reports the federal government at 67%. The reconciliation preserves those issuer disclosures and does not silently force them to agree.

GEO also said its ISAP contract accounted for 9% of consolidated revenue. Applying that rounded whole percentage yields a $236,839,410 point estimate and a mechanical interval of $223,681,665 to less than $249,997,155. A financial-statement footnote says ISAP accounted for less than 10%; that bound is compatible with the 9% narrative but is not an exact second disclosure of ISAP dollars.

### Segments and source categories

The four reported CY2025 segment totals reconcile exactly to consolidated revenue:

| Segment | CY2025 recognized revenue |
|---|---:|
| U.S. Secure Services | $1,827,000,000 |
| Electronic Monitoring and Supervision Services | $320,919,000 |
| Reentry Services | $286,521,000 |
| International Services | $197,109,000 |
| **Consolidated** | **$2,631,549,000** |

The filing also reports $1,388,316,000 for owned-and-leased secure services, $438,684,000 for managed-only U.S. Secure Services, and $320,919,000 for electronic monitoring and supervision. None of those categories is an ICE-only contract schedule. The facility table identifies locations, customers, capacity, and ownership/management characteristics, but does not assign recognized revenue to each facility.

### Recognition and invoice boundary

GEO's accounting policy states that the timing of revenue recognition may differ from invoicing and that GEO records a receivable when services are performed and consideration becomes due through the passage of time. Accordingly, an obligation signed in 2025, an invoice dated in 2025, an award-life outlay snapshot, and CY2025 recognized revenue cannot be treated as interchangeable without service-period and receivable records.

The reviewed filing sequence consisted of the full extracted texts of the Q1, Q2, and Q3 2025 Forms 10-Q; the 2025 Form 10-K; the Q1 2026 Form 10-Q; and the Q1 2026 results exhibit. Exact quotations used in the reconciliation were validated against those archived texts. The reviewed sequence did not supply a customer-to-contract subledger, a facility revenue schedule, a contract-level invoice register, or a general-ledger extract.

## Quarterly sequence

The reported segment totals reconcile for each quarter. Q4 is derived as the annual total less the first nine months.

| Period | Consolidated | U.S. Secure | EM/Supervision | Reentry | International |
|---|---:|---:|---:|---:|---:|
| Q1 2025 | $604.647m | $405.716m | $77.713m | $70.376m | $50.842m |
| Q2 2025 | $636.169m | $441.665m | $78.925m | $71.310m | $44.269m |
| Q3 2025 | $682.341m | $481.628m | $80.538m | $72.657m | $47.518m |
| Q4 2025, derived | $708.392m | $497.991m | $83.743m | $72.178m | $54.480m |

GEO's sequential period-over-prior-year activation disclosures also reconcile arithmetically:

- H1 cumulative increase: $20.2m; Q2 increase: $17.5m; therefore Q1 residual: $2.7m.
- Nine-month cumulative increase: $76.0m; Q3 increase: $55.8m.
- Full-year cumulative increase: $152.4m; therefore Q4 residual: $76.4m.
- $2.7m + $17.5m + $55.8m + $76.4m = $152.4m.

This is a mixed change bundle. By year-end the issuer described company-owned Delaney Hall, North Lake, and D. Ray James; managed-only North Florida; and new transportation contracts. It is not an ICE-only revenue total and cannot be assigned to facilities or contracts from the filing alone.

## Direct-prime action ledger

The action ledger starts from the existing 14-UEI verified recipient universe and retains the two recipients with CY2025 ICE actions:

| Legal recipient | UEI | Actions | CY2025 action-date obligations |
|---|---|---:|---:|
| The GEO Group, Inc. | JMLKZZ1NL2Z6 | 115 | $527,827,186.25 |
| B.I. Incorporated | PKK6L9KLMYR5 | 9 | $171,510,932.72 |
| **Total** | | **124** | **$699,338,118.97** |

The deterministic classification is:

| Program class | Actions | Obligations |
|---|---:|---:|
| ICE detention services | 111 | $508,878,952.25 |
| ICE ISAP/electronic monitoring | 6 | $159,536,432.72 |
| ICE skip tracing | 3 | $11,974,500.00 |
| ICE transportation/removal services | 2 | $9,414,567.00 |
| ICE other/unresolved | 2 | $9,533,667.00 |

The $159,536,432.72 narrow ISAP obligation total can be compared descriptively with the $236,839,410 rounded revenue point estimate, but it does not reconcile to it. The additional $11,974,500 in skip-tracing obligations is kept separate because the broader B.I. total is not an ISAP-program measure.

## Award-lifetime snapshots

For the 34 task/order PIIDs with a CY2025 action, current USAspending award-detail fields show $2,124,471,883.77 in cumulative obligations over the awards' full lives. Current cumulative outlays total $1,939,034,265.44 for the 32 awards where an outlay value is reported. USAspending did not report an outlay value for `70CDCR20FR0000036` or `70CDCR25FR0000075`; the builder preserves those fields as missing rather than converting them to zero.

These totals are not CY2025 cash measures. The awards include performance and funding outside CY2025, and the snapshots do not provide dated disbursement transactions sufficient to allocate CY2025 cash to GEO's recognized revenue.

## IGSA and public-prime channels

The preserved IGSA work identifies nine SEC ICE-facility rows that resolve to six independent federal-public-prime-GEO chains. The public record does not provide one compatible CY2025 downstream GEO total across those chains.

Two records illustrate why they cannot be summed into the revenue bridge:

- The Joe Corley county fund reports $43,194,467 in revenue and an equal operations expense for a single ICE/USMS pass-through cycle. The ICE/USMS split and GEO payee amount are not available. Revenue and expense represent the same cycle and must not be added.
- The North Florida record contains $28,897,523.51 in state payments dated January through June 2026 under Florida FY2025-26. Those checks are not CY2025 payments and cannot be joined publicly to a federal allocation or to GEO CY2025 recognized revenue.

The public-prime evidence supports the existence of a structured-data visibility problem. It does not establish how much CY2025 revenue flowed through those channels and does not justify treating the $553.279m different-metric arithmetic difference as an IGSA estimate.

## Q1 2026 read-forward

The Q1 2026 Form 10-Q reported a $96.9m year-over-year increase in U.S. Secure Services revenue and attributed $79.1m to the same mixed facility/transport activation bundle. The Q1 2026 results exhibit described approximately $300m of annualized revenue from ICE facility activations, approximately $60m of incremental annualized transportation revenue combining ICE and USMS contracts, and up to $60m annually for skip tracing, with the latter service beginning in March 2026.

These figures are forecasts, run rates, or Q1 2026 changes. They are not CY2025 recognized revenue and are excluded from the numerical CY2025 bridge.

## What the reconciliation establishes

### Facts

- GEO's 47.6% ICE concentration implies about $1.253bn of CY2025 ICE revenue, but the issuer did not report exact ICE dollars.
- Verified direct ICE action-date obligations to GEO and B.I. totaled $699.338m in CY2025.
- The direct-obligation/ICE-revenue comparison is a 55.8301% context ratio, not a reconciliation ratio.
- Current award-life obligation and outlay snapshots are materially larger than CY2025 action totals because they cover different periods and measures.
- Six public-prime chains lack one compatible public CY2025 downstream GEO total.
- The filing sequence does not bridge recognized revenue to contracts, invoices, receivables, facilities, outlays, or local remittances.

### Inference

The visibility gap remains open: public sources do not permit a complete contract-to-general-ledger reconciliation. The evidence is consistent with several nonexclusive explanations for the arithmetic difference, including timing, prior-period obligations, public-prime channels, accrual accounting, entity scope, and service categories. The evidence does not allocate the difference among them.

## Hypotheses #341 and #342

The new work should change the qualitative balance but does not resolve either hypothesis.

- `#341`, which predicts a material GEO IGSA exposure gap, gains evidence for a visibility gap: six independent chains lack a compatible CY2025 downstream total, and the sampled local records do not close through standard structured joins. It should not be marked confirmed because materiality is still unmeasured.
- `#342`, the null that legal-prime reporting plus structured subaward/description fields removes any material gap, loses support because the public records did not produce consistent downstream amounts. It should not be marked refuted because the investigation still lacks complete local receipt/remittance ledgers for the denominator.

Recommended rescore: keep both `proposed` or move both to `investigating`; record bounded evidence for `#341` and bounded contrary evidence for `#342`. Do not confirm/refute either until downstream dollar coverage is measured across the six-chain denominator.

## Records still required

1. GEO's CY2025 customer subledger assigning recognized revenue to ICE contracts and facilities.
2. Contract-level service-period invoices, accounts-receivable aging, and general-ledger extracts.
3. Dated federal disbursement records for the 34 direct-prime awards.
4. Funded IGSA task orders and public-prime receipt/remittance ledgers for all six chains.
5. County/state-to-GEO vendor disbursements and administrative-fee schedules.
6. GEO Transport/ICE Air subcontract invoices and recognized-revenue schedules.
7. B.I. ISAP and skip-tracing contract-level recognized-revenue schedules.

## Audit limits

- The ledger uses public USAspending action and award-detail records and the verified recipient identity map; it is not a GEO internal ledger.
- A different database reproducing a USAspending or SEC record would be redundant, not independent corroboration.
- The arithmetic intervals assume ordinary rounding only and do not assert the issuer's internal rounding method.
- Absence statements are limited to the archived filing sequence and public records reviewed for this lead.
- No credentials are embedded in the report, source archive, ledgers, matrix, reconciliation, or manifest.
