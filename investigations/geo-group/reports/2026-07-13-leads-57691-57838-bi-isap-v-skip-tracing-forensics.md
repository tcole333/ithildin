# BI Incorporated / ICE ISAP contract forensics

**Research date:** 2026-07-13  
**Profile:** `geo-group`  
**Leads:** #57691 (BI/ICE ATD chronology), #57838 (ISAP V and skip-tracing forensics)  
**Evidence layer:** public procurement and government documents only; no intent or influence inference

## Result

Public award records document a continuous sequence of competitively awarded BI Incorporated instruments from the first Intensive Supervision Appearance Program (ISAP) through ISAP V. The record also separates two different 2025 procurements that now fund skip tracing:

1. ISAP V is a single-award, full-and-open IDIQ (`70CDCR25D00000062`, solicitation `70CDCR25R00000018`) with two reported offers and a public potential value of $1.028 billion. Its first task order (`70CDCR25FR0000127`) has $108,343,853 in obligations.
2. Three modifications to that task order explicitly added $86,361,425 for skip tracing—79.71% of current task-order obligations. Two descriptions identify “ATTACHMENT 4 PRICING SCHEDULE ITEM 42,” but the public solicitation pricing template contains only 39 numbered operational-support items. The post-award Attachment 4/item 42 is therefore a material missing record, not evidence of what the undisclosed unit or quantity was.
3. ICE separately competed solicitation `26-SOL-DCR-01` as a multiple-award skip-tracing vehicle. Structured award records show 14 prime IDIQ awardees, generally 51 offers (two award records report 53), and BI's parent IDIQ `70CDCR26D00000005` plus task order `70CDCR26FR0000021` for $1,624,500.

The machine-readable award, task-order, transaction, and peer-award matrix is [bi-isap-award-solicitation-matrix-2026-07-13.csv](bi-isap-award-solicitation-matrix-2026-07-13.csv).

## Award chronology

| Generation | Parent instrument | Solicitation | Recorded competition | Ordering/performance span | Public potential value | Current cumulative task obligations |
|---|---|---|---|---|---:|---:|
| ISAP I | `HSCEAB04C0008` / `HSACB4C0008` | not recovered | 3 offers; full and open | matched tasks, 2004–2009 | not reliably reported | $80.31m across six matched tasks |
| ISAP II | `HSCECR09D00002` | `HSCECR09R00004` | 3 offers; full and open | 2009–2014 | $372.84m | $202.82m across six tasks |
| ISAP III | `HSCEDM14D00004` | `HSCECR14R00001` | 4 offers; full and open | 2014-09-08–2020-07-31 | $673.83m | $643.01m across six tasks |
| ISAP IV | `70CDCR20D00000011` | `70CDCR19R00000002` | 2 offers; full and open | 2020-03-23–2025-09-30 | $2.217bn | $1.449bn across five tasks |
| ISAP V | `70CDCR25D00000062` | `70CDCR25R00000018` | 2 offers; full and open | award record: 2025-09-30–2026-09-29 | $1.028bn | $108.34m on first task |

The ISAP I parent start date in the HigherGov-normalized parent record is anomalous (2017, after the ordering end), so the chronology uses the dates of matched contract/task records and preserves the anomaly in the matrix. Amounts are current cumulative values, not original ceilings or annual expenditures.

Named protest records independently confirm competition at two generations. GAO denied G4S Technology LLC's protest of the ISAP II award to BI under `HSCECR-09-R-00004`, and denied CoreCivic's protest of the ISAP IV award to BI under `70CDCR19R00000002`. Those records identify actual competitors, not merely abstract offer counts. Sources: [GAO B-401694/B-401694.2](https://www.gao.gov/products/b-401694%2Cb-401694.2) and [GAO B-418620/B-418620.2](https://www.gao.gov/products/b-418620%2Cb-418620.2).

## ISAP V structure, pricing, and modifications

The [final SAM opportunity](https://sam.gov/opp/8bcce9c16821469395136f30f092ffbf/view) describes a single-award IDIQ, a $4 million total minimum, a $2 billion maximum, and two one-year ordering periods, excluding the possible FAR 52.217-8 extension. It states that the existence of an ordering period does not obligate ICE to place orders. The public award record currently reports a one-year ordering end of 2026-09-29 and a potential value of $1,027,594,113.39. That difference could reflect the present award state or unexercised ordering authority; it does not establish a cancellation or reduction.

The first task order's transaction chronology is:

| Date | Action | Obligation | Description |
|---|---|---:|---|
| 2025-09-30 | base | $21,966,324.91 | ISAP V technology and case management |
| 2025-09-30 | P00001 | $16,103.09 | additional ISAP V funding |
| 2025-10-30 | P00002 | $690,000.00 | “ADDS FUNDING FOR SKIP TRACING SERVICES” |
| 2025-12-17 | P00003 | $9,660,000.00 | “ATTACHMENT 4 PRICING SCHEDULE ITEM 42 SKIP TRACING SERVICES” |
| 2026-01-27 | P00004 | $76,011,425.00 | same item-42 description |

Source: [USAspending award record](https://www.usaspending.gov/award/CONT_AWD_70CDCR25FR0000127_7012_70CDCR25D00000062_7012/). The $86,361,425 figure is the sum of P00002–P00004; it is a transaction-record calculation, not a ceiling or invoice total.

The solicitation pricing workbook has 39 numbered operational-support line items. It prices office visits, home visits, enrollments, court tracking, exception reporting and residence verification as each; case management and the monitoring modalities as daily units; maintenance supervision as monthly units; and lost/stolen devices as each. It warns that quantities are “estimated for evaluation purposes only” and that the Government is not obligated to order them. The public file contains no offeror rates and no item 42.

## Required services, staffing, devices, and quality controls

The statement of work says the contractor must provide “community-based supervision, in-person reporting, GPS monitoring or biometric technology monitoring services across the nation.” The required modalities include GPS ankle and wrist devices, a supervisory biometric mobile application with location collection, a non-supervisory biometric application, mobile telephonic/biometric reporting, case management, and an electronic case-management system.

Operational requirements include a four-month transition; U.S. citizenship for personnel who access DHS IT systems; a program director with a degree and ten years of relevant experience; a deputy with five years; qualified program managers/case specialists; and one program manager at every C-site. The contractor owns, warehouses, deploys, monitors, retrieves, and maintains the monitoring equipment. The public pre-award package does not name a device manufacturer, model, cloud subcontractor, commercial-data supplier, or downstream skip-tracing vendor. Instead, post-award hardware/software architecture was a contractor deliverable, and the Q&A said contractor-to-contractor arrangements were outside the Government's purview.

The QASP makes surveillance and financial remedies explicit. It states: “If it is determined that the contractor is not completing services and it is deemed negligent/fraudulent, there will be a 2% deduction on total monthly billing for the month in which discrepancies were found.” Other service-specific remedies include return of service charges and invoice deductions up to 20%, including for mobile-app/case-system availability and GPS-system performance. Withholdings may be recoverable after correction; deductions are not. Existing GAO performance findings #12397 and #12417–#12419 document that ICE's earlier contract surveillance and financial consequences were incompletely recorded; that history does not prove a current ISAP V failure.

## Data, AI, and privacy boundaries

ISAP V makes ICE the owner of user-created and loaded data, gives the Government unrestricted rights, requires access within one business day, bars release without written consent, and requires records to be returned to ICE rather than destroyed or altered at contract end. The AI attachment requires a human in the loop, bars AI output as sole evidence, requires provenance and auditability, and prohibits contractor reuse or model training on Government data or AI output without authorization.

There is a documented change between the 2023 privacy assessment and the 2025 solicitation. The [2023 DHS/ICE ATD Privacy Impact Assessment](https://www.dhs.gov/sites/default/files/2023-08/privacy-pia-ice062-atd-august2023.pdf) identifies the proprietary app as BI's SmartLINK and says: “the Monitoring App is not continuously monitoring the participant's location.” It says longitude/latitude are sent at login/check-in; captured template photos are deleted from the device while facial measurements are stored in the app; and ISAP records in ICE systems fall under 75-year retention schedules. The 2025 ISAP V technical attachment, by contrast, requires the supervisory biometric app to allow “continuous tracking” by storing coordinates at most every three minutes and uploading at least every four hours, plus Government on-demand location requests. This is a source-level change in required functionality. A superseding PIA or privacy compliance record addressing the new supervisory-app requirement was not located in the reviewed public package.

## Separate ICE skip-tracing vehicle

The [final SAM opportunity for `26-SOL-DCR-01`](https://sam.gov/opp/bc8d7837d72149479146485298ff5ed5/view) describes a new, full-and-open requirement with no incumbent. The final SOW estimates a 1.5-million-case docket and approximately 50,000 cases per vendor per month. Contractors receive government-furnished case data, use commercial data and automated/manual research, and may use physical observation to verify residence or employment. The Q&A says per-case, firm-fixed unit pricing; completed-case monthly invoicing; multiple awards followed by competed task orders; and vendor responsibility for any Skopenow, Babel Street, or other commercial licenses it chooses to use.

Amendment 2 removed language naming EARM/EID, ENFORCE, IDENT/HART, ATLAS, and NCIC and removed direct contractor access to DHS systems. Final Q&A says the Government would furnish extracted case data instead. The solicitation set a $7.5 million minimum and $281.25 million maximum per IDIQ after Amendment 2, two years of ordering plus one option year, with funding placed at task-order level.

Structured records enumerate 14 prime IDIQ awardees: BI Incorporated plus AI Solutions 87, Bluehawk, Capgemini Government Solutions, Constellation, Enprovera, GSS/Government Support Services, Global Recovery Group, Gravitas Professional Services, National Protective Services, Omniplex World Services, Response AI Solutions, SOS International, and the awardee attached to UEI `D13LLJJZYH64` (whose HigherGov clean-name value is only “Fraud” and requires legal-name verification). The matrix preserves each award ID, UEI, ceiling/value, dates, and offer count.

BI's task order was awarded for $1,624,500 on 2025-12-18. P00001 added no obligation and extended performance 60 days. The task-order record reports one offer under subject-to-multiple-award fair opportunity. That single task-order offer is not the same as the 51-offer parent competition.

## Subawards, suppliers, and disconfirmation

- The USAspending task detail for `70CDCR25FR0000127` reports structured `subaward_count = 0` and no subaward amount. HigherGov returned zero records where BI was the identified subcontract awardee. Existing finding #12431 records the same structured-zero pattern across sampled ISAP tasks.
- The USAspending subaward search endpoint used by the local tool did not honor the supplied award ID and returned unrelated nationwide rows, so those results were excluded. This is a known tool defect, not negative evidence.
- The public ISAP V solicitation, Q&A, and pricing files did not name manufacturers, models, commercial-data providers, or subcontractors. The public ISAP III FOIA contract PDF was located, but it is image-only and its disclosed portions require OCR/review before any supplier names can be claimed.
- Therefore, the finding is **structured zero / publicly unresolved**, not “BI had no subcontractors” or “BI built every device.” The apparent-awardee subcontracting plan, post-award architecture, bills of material, and task-order Attachment 4 remain required for supplier attribution.
- Full-and-open competitions, named GAO protesters, two offers on ISAP IV/V, and 14 prime awards/51 offers under the skip vehicle are ordinary procurement evidence that weighs against a BI-only or predetermined-award assumption. They do not answer whether task-level work is concentrated after award.

## Remaining record requests

The public-record stopping point is reached for the two leads, but four documents would materially improve the record:

1. ISAP V task order `70CDCR25FR0000127`, post-award Attachment 4 and pricing schedule item 42, including quantities and non-exempt unit descriptions.
2. P00002–P00004 modification packages, independent government estimates, acquisition plans, approvals, and any competition/fair-opportunity determination for the added skip-tracing work.
3. Releasable portions of BI's apparent-awardee subcontracting plan, post-award hardware/software architecture, equipment list, and supplier/subcontractor schedule.
4. A current PIA, PTA, SORN analysis, or privacy-compliance decision covering the ISAP V supervisory biometric application's continuous-location requirement.

## Source and reproducibility notes

The matrix was built from USAspending transaction/award records, HigherGov's normalized federal award mirror, the two SAM opportunity packages, GAO bid-protest decisions, DHS/ICE's 2023 PIA, and ICE's released ISAP III contract. Award values are snapshot values as of the research date. Offer counts and competition labels are structured procurement fields; they are not assessments of competitive intensity. Three sources returning the same federal award record were treated as redundancy, not corroboration.

Primary documents:

- [SAM ISAP V opportunity](https://sam.gov/opp/8bcce9c16821469395136f30f092ffbf/view)
- [SAM ICE skip-tracing opportunity](https://sam.gov/opp/bc8d7837d72149479146485298ff5ed5/view)
- [USAspending ISAP V task order](https://www.usaspending.gov/award/CONT_AWD_70CDCR25FR0000127_7012_70CDCR25D00000062_7012/)
- [GAO ISAP II protest](https://www.gao.gov/products/b-401694%2Cb-401694.2)
- [GAO ISAP IV protest](https://www.gao.gov/products/b-418620%2Cb-418620.2)
- [DHS/ICE ATD PIA, August 2023](https://www.dhs.gov/sites/default/files/2023-08/privacy-pia-ice062-atd-august2023.pdf)
- [ICE FOIA ISAP III contract `HSCEDM14D00004`](https://www.ice.gov/doclib/foia/contracts/biIncorporatedHSCEDM14D00004.pdf)
