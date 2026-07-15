# Western GEO contract detention facility economics

**Lead:** 60206  
**Profile / thread:** `geo-group` / 110  
**Workflow:** `analyze-contract`  
**Status:** blocked on unreleased contract-administration records

## Result

Official ICE workbooks materially narrow the guarantee and occupancy gap for Adelanto, Desert View, Aurora, and Tacoma. The FY25 workbook is a year-to-date extract as of **September 15, 2025**, not a locked full-fiscal-year dataset. The FY26 workbook is year-to-date as of **April 2, 2026**. Both report facility-level detainee-classification ADP components and a `Guaranteed Minimum` field.

| Facility | Guaranteed minimum | ADP (A-D sum) | Avg. unused minimum | Avg. above minimum |
|---|---:|---:|---:|---:|
| Adelanto ICE Processing Center | 640 | 575.544413 | 64.455587 | 0.000000 |
| Desert View Annex | 480 | 423.303725 | 56.696275 | 0.000000 |
| Aurora / Denver Contract Detention Facility | 600 | 1180.948424 | 0.000000 | 580.948424 |
| Tacoma / Northwest ICE Processing Center | 1181 | 1179.616046 | 1.383954 | 0.000000 |

In the FY25-to-September-15 extract, Adelanto averaged 64.455587 below its reported minimum, Desert View 56.696275 below, and Tacoma 1.383954 below; Aurora averaged 580.948424 above. These are arithmetic differences between the workbook's minimum and the sum of its four classification-level ADP fields. They are **not** billed empty-bed counts, payment amounts, or evidence that the same rate applied throughout the average period.

| Facility | Guaranteed minimum | ADP (A-D sum) | Avg. unused minimum | Avg. above minimum |
|---|---:|---:|---:|---:|
| Adelanto ICE Processing Center | 640 | 1733.153006 | 0.000000 | 1093.153006 |
| Desert View Annex | 120 | 425.606557 | 0.000000 | 305.606557 |
| Aurora / Denver Contract Detention Facility | 600 | 1260.038251 | 0.000000 | 660.038251 |
| Tacoma / Northwest ICE Processing Center | 1181 | 1289.437159 | 0.000000 | 108.437159 |

All four FY26-to-April-2 ADPs were above their reported minimums on average. The reported Adelanto minimum remained 640 and Aurora remained 600; Tacoma remained 1,181. Desert View changed from 480 in the FY25 workbook to 120 in the FY26 workbook. The workbook label is operational evidence of the minimum but does not identify the governing CLIN, amendment, effective date, pricing tier, or invoice rule. Accordingly, this pass does not call the change a contract amendment without the funded schedule.

The best recovered rate/payment comparator remains historical Tacoma evidence. DHS OIG reported that Northwest had a 1,181-detainee minimum, a $138.86 daily rate as of October 2021, a September 2021-August 2022 ADP of 374, and more than $40 million paid for unused bed space for the year before its inspection. The OIG also said ICE paid nearly $5 million monthly. Those findings establish historical economics, not the current FY25/FY26 rate.

Current unit rates, complete funded CLIN schedules, gross invoices, receiving reports, Treasury/payment vouchers, and facility-specific credits or deductions were not recovered. Public Aurora P00011 and Tacoma P00049 modifications prove that rate, quantity, guarantee and staffing fields exist but visibly withhold the values. The Adelanto/Desert View IDV shows the historic tier architecture and withholds price fields; a 2020 modification removes the revised Desert View minimum. Existing human actions 60 and 74 already target performance deductions and current rate pages. A separate Adelanto/Desert View rate-and-invoice request is recorded with this pass.

## ICE workbook method and period controls

The raw workbooks were imported and inspected with the repository's spreadsheet workflow. Target cells were inspected directly, the two facility sheets were rendered and visually checked, and a formula-error scan returned zero errors. The derived extraction JSON preserves the exact cell ranges and raw values. `FY25_detentionStats.xlsx` and `FY25_detentionStats09242025.xlsx` are byte-identical with SHA-256 `3b9e2d626b1e249b2c87539554758333b27bc0da64a37e5dac99944a210c0782`.

The FY25 facility sheet states `Data Source: ICE Integrated Decision Support (IIDS), 09/15/2025`; the FY26 sheet states `Data Source: ICE Integrated Decision Support (IIDS), 04/02/2026`. The FY26 filename embeds `04092026`, while the internal data-as-of date is April 2, 2026; the ledger uses the internal as-of date and preserves the filename separately. This report therefore uses explicit as-of labels and does not describe either extract as the final completed performance year. ADP is calculated only as Level A + Level B + Level C + Level D. No occupancy component is combined with a task award stock to derive an implied rate.

## Facility-specific reconstruction

### Adelanto and Desert View

The 2019 IDV schedule identified Adelanto CLIN 0002 as 1-1,455 guaranteed beds and CLIN 0003 as the 1,456-1,940 above-minimum tier. It identified Desert View CLIN 0002A as 1-600 guaranteed beds and CLIN 0003A as 601-750 above minimum. Unit prices and obligated amounts are withheld. P00004 says it changes Desert View's guaranteed-minimum CLIN to a new number of beds effective October 26, 2020, but the number is withheld.

The later ICE facility workbooks report Adelanto at 640 in both reviewed extracts and Desert View at 480 then 120. Because the IDV/task-order schedule establishing those later numbers was not recovered, the ledger labels them as ICE-reported operational minimums rather than reconstructing a contract rate.

USAspending separates the sites into task orders. The FY25-period tasks report cumulative obligations/outlays of $120,393,306.26 / $103,779,111.73 at Adelanto and $34,270,827.48 / $34,317,588.35 at Desert View. Their successor tasks report $86,404,000.00 / $35,037,490.56 and $17,972,900.00 / $9,822,302.78. Transaction descriptions refer to facility operating charges, daily occupancy, transportation, guard services and per-diem rates, but disclose no billable quantities or unit prices.

### Aurora

The FY25-to-September-15 workbook reports a 600 minimum and 1,180.948424 ADP; the FY26-to-April-2 workbook reports the same minimum and 1,260.038251 ADP. P00011 changes multiple rate-bearing CLINs but withholds monthly, bed-day, transportation and labor rates. USAspending P00011 on the FY25 task added $7,004,194.70 while increasing the maximum number of beds; P00012 later deobligated $1,795,324.02 in remaining funds and closed the award. The latter description is not evidence of a performance deduction, invoice credit, or unused-bed adjustment.

### Tacoma / Northwest

The ICE workbooks report a 1,181 minimum in both periods. FY25-to-September-15 ADP was 1,179.616046, almost exactly the minimum on average; FY26-to-April-2 ADP was 1,289.437159. P00049 says it changes the guaranteed-minimum bed-day rate and incorporates guaranteed-minimum and full-capacity staffing plans but withholds the bed counts, rate, headcounts, quantities, unit price, and amount.

The FY25 task accumulated $117,431,349.50 in obligations and $114,161,655.04 in outlays; its actions included funding above-guarantee services, fuel, expansion, remote posts, overtime beds, and an $11,894,500 option/extension. The successor task reports $39,042,746.99 obligated and $1,243,153.97 outlaid. These award measures do not disclose current per-diem rates or invoice allocation.

## Award and transaction measures

| Facility / task | Performance | Cumulative obligation | Cumulative outlay |
|---|---|---:|---:|
| Aurora / Denver Contract Detention Facility / `70CDCR25FR0000005` | 2024-10-16 to 2025-10-15 | $59,993,453.20 | $59,995,192.61 |
| Adelanto ICE Processing Center / `70CDCR25FR0000009` | 2024-12-20 to 2025-12-19 | $120,393,306.26 | $103,779,111.73 |
| Desert View Annex / `70CDCR25FR0000010` | 2024-12-20 to 2025-12-19 | $34,270,827.48 | $34,317,588.35 |
| Tacoma / Northwest ICE Processing Center / `70CDCR25FR0000004` | 2024-10-28 to 2026-03-27 | $117,431,349.50 | $114,161,655.04 |
| Adelanto ICE Processing Center / `70CDCR26FR0000028` | 2025-12-20 to 2026-06-19 | $86,404,000.00 | $35,037,490.56 |
| Aurora / Denver Contract Detention Facility / `70CDCR25FR0000111` | 2025-10-16 to 2026-08-15 | $66,893,395.00 | $36,399,063.73 |
| Desert View Annex / `70CDCR26FR0000031` | 2025-12-20 to 2026-06-19 | $17,972,900.00 | $9,822,302.78 |
| Tacoma / Northwest ICE Processing Center / `70CDCR26FR0000055` | 2026-03-28 to 2026-10-27 | $39,042,746.99 | $1,243,153.97 |

The four first rows are the most recently completed or closed predecessor tasks recovered for each facility; the four later rows are successor/current tasks aligned to the FY26 context. Values are current cumulative snapshots in the archived USAspending response, not cash paid within the workbook's occupancy period. Outlays can slightly exceed obligations in public snapshots (Aurora and Desert View predecessor tasks); this pass preserves the reported figures and does not recast the difference as an overpayment.

The transaction/modification ledger contains every public action for the eight task orders. It classifies closeouts and extensions only when the description supports that label. No action is called a performance deduction merely because it is negative or closes an award.

## Evidence-class controls

- A guaranteed minimum is not physical capacity, maximum beds, funded quantity, above-minimum ceiling, or ADP.
- ADP-to-minimum arithmetic measures average utilization relative to the reported floor, not invoice bed-days.
- A federal action obligation is a legal commitment or deobligation, not an invoice, payment or recognized revenue.
- USAspending's cumulative outlay is retained as an award/account disbursement measure, not a gross invoice or facility-period payment ledger.
- A closeout deobligation is not a penalty, credit, or unused-bed adjustment unless the source identifies it that way.
- The historical Tacoma rate is not carried into FY25/FY26.
- The SEC filing is used only for corporate context; it does not provide facility-level invoice or revenue allocation.

## Source coverage and stop rule

This pass used the official ICE detention-management page and raw FY25/FY26 workbooks, ICE FOIA contract releases, current archived USAspending award and transaction histories, parent IDV records, DHS OIG reports, local SAM bulk identity/exclusion checks, and GEO's 2025 SEC filing. HigherGov, live SAM, and paid PACER were not used.

The lead's stop condition is not met. None of the four facility chains has a period-compatible package containing the funded minimum, current rate, occupancy, gross invoice/payment and deduction inputs. ICE's public releases document agency redaction of current Aurora/Tacoma rate-bearing pages and older Adelanto/Desert View economic fields, but no current task-order schedule or agency no-record response was acquired. Current invoices, vouchers and deductions also remain agency-held. The lead is therefore blocked rather than completed.

## Database disposition

New verified findings: #13024, #13025, #13026, #13027, #13028. Existing findings on the historical IDV schedules and redacted modifications are reused rather than duplicated. No post-write automatic lead generation was run; the root coordinator reserved that batch operation until all wave-11 tracks finish.

Companion artifacts preserve the [facility-period ledger](./2026-07-14-lead-60206-western-cdf-economics-wave11-facility-period-ledger.csv), [transaction/modification ledger](./2026-07-14-lead-60206-western-cdf-economics-wave11-transaction-modification-ledger.csv), [negative/redaction log](./2026-07-14-lead-60206-western-cdf-economics-wave11-negative-redaction-log.csv), source/finding manifest, and checksum ledger.
