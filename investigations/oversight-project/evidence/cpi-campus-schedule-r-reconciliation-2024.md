---
title: CPI / Conservative Partnership Campus TY2024 Schedule R reconciliation
profile: oversight-project
thread_id: 180
lead_id: 73121
tax_year: 2024
irs_object_id: "202513189349303026"
reviewed: 2026-07-23
status: completed
---

# CPI / Campus TY2024 Schedule R reconciliation

## Bottom line

CPI's TY2024 return reports six Schedule R transaction types with its wholly
owned taxable C corporation, Conservative Partnership Campus Inc. The codes
show reciprocal related-party activity, but they are not six independently
proven cash transfers. IRS instructions say one transaction may appear on more
than one line and define "amount involved" as the higher fair-market value
provided or received.

Two comparisons are especially strong:

- CPI's $1,775,000 type-B contribution to Campus exactly equals the increase in
  CPI's "investments-other securities" balance from $1,764,881 to $3,539,881.
- The $1,201,864 type-M services performed by Campus are $365 below the
  $1,202,229 Campus contractor-compensation disclosure.

The return does not disclose the type-A receipt subtype, the accounting lines
for each Schedule R amount, or Campus's underlying Form 1120. A full
counterparty-side reconciliation is therefore not publicly possible.

## Code map and economic direction

All six rows use "Book Value" as the valuation method.

| Code | Amount | IRS meaning | Economic direction |
|---|---:|---|---|
| A | $1,544,108 | Receipt of interest, annuities, royalties, or rent from a controlled entity | Campus to CPI receipt/accrual; subtype undisclosed |
| B | $1,775,000 | Gift, grant, or capital contribution to a related organization | CPI to Campus |
| M | $1,201,864 | Performance of services by a related organization | Campus supplies services to CPI; the code alone does not establish cash timing |
| P | $867,137 | Reimbursement paid to a related organization for expenses | CPI to Campus |
| Q | $188,169 | Reimbursement paid by a related organization for expenses | Campus to CPI |
| K | $3,152,365 | Lease of facilities, equipment, or other assets from a related organization | Campus supplies leased assets to CPI; the code alone does not establish cash timing |

Schedule R Part V marks A, B, K, M, P, and Q "Yes." It marks the other
categories "No," including loans, dividends, asset sales or purchases,
exchanges, leases to Campus, services performed by CPI for Campus, shared paid
employees, and other cash/property transfers.

## Bounded arithmetic

| Test | Calculation | Result | Limit |
|---|---|---|---|
| Contribution vs. investment-asset growth | $3,539,881 - $1,764,881 | $1,775,000 exact match | CPI does not identify every security in the balance |
| Services vs. contractor compensation | $1,202,229 - $1,201,864 | $365 difference | Return does not explain the difference |
| Lease vs. occupancy expense | $4,638,976 - $3,152,365 | $1,486,611 outside K | Occupancy includes other costs |
| Lease plus services vs. occupancy | $4,638,976 - ($3,152,365 + $1,201,864) | $284,747 residual | Only valid if M was classified as occupancy; filing does not say |
| Reciprocal reimbursements | $867,137 - $188,169 | $678,968 net toward Campus | Does not establish expense-line classification |
| A vs. Workspace Share Revenue | $2,044,685 - $1,544,108 | $500,577 difference | A subtype and Part VIII line are undisclosed |
| A vs. gross rents | $1,544,108 - $156,702 | $1,387,406 difference | A may include interest, annuities, royalties, or rent |
| Campus income vs. K+M+P | $5,908,148 - ($3,152,365 + $1,201,864 + $867,137) | $686,782 residual | Not a strict revenue reconciliation; Schedule R values can overlap and are FMV-based |
| All six rows | Sum of A+B+M+P+Q+K | $8,728,643 | Not six proven cash payments and unsafe to net |

CPI reports Campus's share of total income as $5,908,148 and share of
end-of-year assets as $709,526 at 100.000% ownership. IRS instructions say the
C-corporation income figure is derived from Form 1120. Campus itself has no
public Form 990 in the current IRS e-file index; that absence is expected for
a taxable C corporation.

## Disconfirmation sweep

The narrow hypothesis that Campus had only internal CPI customers is false.
Barry Moore for Congress reported two September 2024 Schedule B disbursements
to Campus at 300 Independence Ave SE:

- $5,000 on September 19, described as "CONTRIBUTION."
- $50 on September 30, described as "EVENT TICKETS."

The event-ticket payment documents an outside political-committee customer in
TY2024. It is far too small, and FEC itemized disbursement coverage is too
incomplete, to explain the $686,782 arithmetic residual. The evidence supports
substantial internal property/service activity plus at least some external
activity; it does not support an internal-only revenue account.

## Sources

| Source | Reference | Use |
|---|---|---|
| Official IRS e-file XML | `IRS:202513189349303026`; object `202513189349303026_public.xml` in `2025_TEOS_XML_11D.zip` | Exact return fields and Schedule R rows |
| Official IRS public-inspection PDF | https://apps.irs.gov/pub/epostcard/cor/821470217_202412_990_2026030223963130.pdf | Visual/page-level verification: Form 990 pp. 8-11; Schedule R pp. 2-3 (PDF pp. 52-53) |
| Official 2024 Schedule R | https://www.irs.gov/pub/irs-prior/f990sr--2024.pdf | Code definitions |
| Official 2024 Schedule R instructions | https://www.irs.gov/pub/irs-prior/i990sr--2024.pdf | Overlap, threshold, and fair-market-value rules |
| Official FEC Schedule B | https://docquery.fec.gov/pdf/804/202410159685546804/202410159685546804.pdf | External Campus payments, image page 38 of 62 |
| Current IRS e-file index | https://apps.irs.gov/pub/epostcard/990/xml/2026/index_2026.csv | Exact Campus EIN search returned zero Form 990 rows |

## File integrity

| File | SHA-256 |
|---|---|
| CPI official TY2024 PDF | `ce11848d8c0d7fa924f0f805b1df7e9563c0dae8b4ca0cafe6274b09bb316de3` |
| CPI official TY2024 XML | `4327b1cb874fde8b8154e26ea4a4f1f917cd0525163999000d22b5d352b6b5ad` |
| 2024 Schedule R form | `ec53b688cf1902345c8bb284555a795598b8348b0e40f0de2d4ac4d7c03ebff4` |
| 2024 Schedule R instructions | `e9251dfcf30f269275612bb1cf225b3fe45ff63378a08fbab402915d1ad7cbc2` |

## Structured records

- Finding #13965: decoded six-row fact and economic directions.
- Finding #14249: bounded reconciliation synthesis, confidence medium.
- Finding #14308: FEC external-customer disconfirmation.
- Finding #14309: expected absence of a Campus Form 990 and counterparty
  coverage limit.
- Follow-up lead #76507: locate CPI's consolidated audit or voluntarily
  disclosed Campus financial statements.
