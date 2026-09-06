# AAF / AAF Action reciprocal-service disclosure, TY2023–TY2024

Lead: #73865  
Finding refined: #14057  
Prepared: 2026-07-23

## Bottom line

American Accountability Foundation (AAF, EIN 85-4391204) checked both reciprocal-service indicators on Schedule R, Part V, line 1 in its tax-year 2023 and tax-year 2024 Forms 990:

- code **l**: performance of services or membership/fundraising solicitations **for** a related organization; and
- code **m**: performance of services or membership/fundraising solicitations **by** a related organization.

In both years, AAF Action (EIN 93-4774398) was AAF's only listed related organization, was identified as a controlled Delaware 501(c)(4), and no Part V, line 2 transaction row was reported. Under the applicable Schedule R instructions for transactions between a 501(c)(3) filer and a related non-501(c)(3), line 2 reporting is required only when the amount involved for a transaction type exceeds USD 50,000. The instructions define the amount involved for services as fair-market value, considering what was provided or received, whichever is higher.

Accordingly, the public returns establish that services occurred in both directions and bound the fair-market value reported under each direction to **no more than USD 50,000 in TY2023 and independently no more than USD 50,000 in TY2024**. They do not disclose the actual amounts, invoices, payment terms, staff allocations, or whether the services were paid, donated, reimbursed, or uncompensated.

## Primary-source matrix

| Source | Coverage | What it establishes | Limits |
|---|---|---|---|
| [AAF TY2023 Form 990 XML](https://gt990datalake-rawdata.s3.us-east-1.amazonaws.com/EfileData/XmlFiles/202413199349311136_public.xml) | 2023-01-01–2023-12-31 | AAF Action is the sole listed related organization; EIN 93-4774398; controlled 501(c)(4); both service indicators are 1; all other Part V line 1 indicators are 0; no line 2 row | No amount or contractual terms |
| [2023 Schedule R instructions](https://www.irs.gov/pub/irs-prior/i990sr--2023.pdf) | TY2023 rules | Codes l/m and the over-USD-50,000 line 2 threshold for transactions between a 501(c)(3) and a related non-501(c)(3) | Threshold permits a bound, not an exact value |
| [AAF TY2024 Form 990 XML](https://gt990datalake-rawdata.s3.us-east-1.amazonaws.com/EfileData/XmlFiles/202533189349310698_public.xml) | 2024-01-01–2024-12-31 | Same sole related organization and reciprocal service indicators; no line 2 row | No amount or contractual terms |
| [Current Schedule R instructions](https://www.irs.gov/instructions/i990sr) | TY2024 interpretation checked against current IRS instructions | Amount involved for services uses fair-market value; line 2 threshold applies by listed transaction type | Does not identify payer, price, or allocation method |
| [IRS 990-N bulk data](https://www.irs.gov/charities-non-profits/exempt-organizations-form-990-n-e-postcards) | Snapshot dated 2026-07-20 | AAF Action filed a TY2024 990-N; Tom Jones is principal officer; gross receipts were not greater than USD 50,000 | 990-N contains no expense, compensation, related-party, or service detail |
| [AAF Form 1023](https://www.documentcloud.org/documents/22080176-american-accountability-foundation-1023/) | Application dated 2021-01-25 | General statement that officers/directors could work on paid or volunteer bases and with outside organizations on volunteer or contract bases | Predates AAF Action's 2023 formation and contains no Action-specific arrangement |
| [IRS EO BMF](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf) | DC and Delaware files downloaded 2026-07-23; BMF dated 2026-07-14 | AAF appears in the DC file; AAF Action did not match either file | Absence is not proof that no Form 1024-A was submitted or that no exemption claim exists |
| [IRS Form 1024-A guidance](https://www.irs.gov/forms-pubs/about-form-1024-a) | Current guidance | Form 1024-A is optional for a 501(c)(4); Form 8976 notification is separate | Form 8976 data is not publicly disclosed |

## Return-level facts

### TY2023

- AAF return object: `202413199349311136`
- SHA-256: `27fd1d531e567f331ebae294f63e5004df9feaf47aa704cd939c059eb1395c80`
- Schedule R lists only American Accountability Foundation Action Inc.
- `ControlledOrganizationInd=1`
- `PerformOfServicesForOthOrgInd=1`
- `PerformOfServicesByOtherOrgInd=1`
- All other Part V line 1 transaction indicators are 0.
- No `TransactionsRelatedOrgGrp` / Part V line 2 row appears.
- Thomas Jones: president, 40 hours/week; AAF reportable compensation USD 200,000; related-organization reportable compensation USD 0.
- AAF reported no independent, consolidated, or accountant-compiled/reviewed financial statements.

### TY2024

- AAF return object: `202533189349310698`
- Submitted: 2025-11-14
- SHA-256: `916633f33aef98fc488703494dff0bec512f1374b5301eea0d4db3ae62e520a2`
- Schedule R again lists only AAF Action, with the same two service indicators and no Part V line 2 row.
- Thomas Jones: president, 40 hours/week; AAF reportable compensation USD 203,583, including USD 3,583 deferred compensation; related-organization reportable compensation USD 0.
- AAF Action's TY2024 990-N names Tom Jones as principal officer but reports no hours or compensation.
- AAF reported USD 79,856 in other service fees, described on Schedule O as USD 62,667 in outside contracted services and USD 17,189 in payroll processing. These are counterparty-blind aggregates and cannot be attributed to AAF Action.
- AAF reported no independent, consolidated, or accountant-compiled/reviewed financial statements.

AAF also reported no contractor paid more than USD 100,000 in either TY2023 or TY2024. That threshold does not identify contractors paid less.

## Filing-window check

- AAF's complete public Form 990 series located for TY2021–TY2024; TY2024 is the latest located full return.
- The official 2026 IRS e-file index, downloaded 2026-07-23, contained no newer AAF or AAF Action full Form 990 filing.
- The IRS 990-N bulk snapshot dated 2026-07-20 contained AAF Action's TY2024 filing but no TY2025 filing.

These checks are current only through the stated source snapshots.

## Public-document negative and disconfirmation

Targeted searches produced no public:

- reciprocal-services, shared-services, cost-allocation, or management agreement;
- invoice, reimbursement ledger, or accounting allocation;
- audited financial statement or related-party footnote;
- AAF Action Form 1024-A; or
- document in the configured Unified or DocumentCloud corpora matching AAF Action's exact name and explaining the arrangement.

The archived `aafaction.org` captures located were a parked-domain page, not organizational disclosures. Exact-name and agreement/invoice searches also produced no responsive public web document. This is a **bounded public-document negative**, not evidence that no agreement or payment exists.

AAF's 2021 Form 1023 predates AAF Action. It contains only general language about paid, volunteer, and contract work and answers no to then-existing insider agreements; it cannot resolve a relationship with an organization formed on 2023-12-08.

No later filing or exemption document was located that expressly denies shared services or shows that the relationship ended. Therefore the service indicators are not disconfirmed.

## Interpretation guardrails

- The checked boxes establish transaction **types**, not exact amounts.
- The absence of reimbursement boxes means AAF did not classify a separate transaction as a reimbursement; it does not prove services were unpaid.
- Zero related-organization compensation reported for Thomas Jones means AAF reported no such compensation on its Form 990. AAF Action's 990-N cannot independently confirm compensation.
- The expense categories in AAF's Form 990 do not name counterparties.
- Do not infer that the reciprocal services were uncompensated.

## Reopening dependency

Reopen this lead if any of the following becomes public:

1. the underlying reciprocal/shared-services or cost-allocation agreement;
2. invoices, general-ledger entries, reimbursement records, payroll/staff allocation schedules, or audited related-party notes;
3. AAF Action's Form 1024-A or another exemption-application attachment describing the relationship;
4. a later full Form 990, Schedule R line 2 disclosure, or later AAF Action filing that quantifies the transaction; or
5. a primary record naming the staff, resources, price, payment terms, or valuation method.

Without one of those documents, the defensible resolution is the two-year, per-direction upper bound above, not a precise dollar amount or characterization of compensation.

