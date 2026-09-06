# Look Ahead America TY2024 officer-compensation reconciliation

Research date: 2026-07-23  
EIN: 82-1645970  
IRS object: `202543159349300844`  
Tax period: 2024-01-01 through 2024-12-31  
Lead: #75701  
Thread: #181

## Result

The public record does not reconcile or attribute the $87,060 that Look Ahead
America reported in Form 990 Part IX as compensation of current officers,
directors, trustees, and key employees.

The TY2024 e-file XML reports all three named officers at $0 in Part VII and
reports Part VII aggregate compensation from the organization at $0. Part IX
separately reports $87,060 on line 5, entirely allocated to program services.
No person-level schedule or supporting statement identifies a recipient.
Accordingly, the amount must not be assigned to Matthew Braynard, Thomas
Datwyler, Witold Chrabaszcs, a former officer, or any other person on the
available evidence.

## Exact TY2024 fields

| Return location | Machine-readable field | Reported value |
|---|---|---:|
| Part VII | Matthew Braynard, `ReportableCompFromOrgAmt` | $0 |
| Part VII | Thomas Datwyler, `ReportableCompFromOrgAmt` | $0 |
| Part VII | Witold Chrabaszcs, `ReportableCompFromOrgAmt` | $0 |
| Part VII | Each officer, related-organization and other compensation | $0 |
| Part VII | `TotalReportableCompFromOrgAmt` | $0 |
| Part VII | `FormerOfcrEmployeesListedInd` | false |
| Part IX line 5 | `CompCurrentOfcrDirectorsGrp/TotalAmt` | $87,060 |
| Part IX line 5 | `CompCurrentOfcrDirectorsGrp/ProgramServicesAmt` | $87,060 |
| Part IX line 7 | `OtherSalariesAndWagesGrp/TotalAmt` | $0 |
| Part IX line 9 | `OtherEmployeeBenefitsGrp/TotalAmt` | $375 |
| Part IX line 10 | `PayrollTaxesGrp/TotalAmt` | $68,759 |
| Part X | End-of-year total liabilities | $0 |
| Part XII | Accounting method | accrual |
| Part XII | Independent accountant compilation/review | false |
| Part XII | Financial-statement audit | false |

The return reports three employees. Its four public return-data documents are
Form 990, Schedule A, Schedule B, and Schedule O. It expressly reports that
Schedule J is not required. Schedule O contains only governance, conflict
policy, public-disclosure, and return-review explanations; it contains no
compensation explanation.

## Historical classification comparison

Part IX line 5 exactly matched Part VII aggregate reportable compensation in
each earlier public return. TY2024 is the first public mismatch.

| Tax year | IRS object | Part VII aggregate | Part IX line 5 | Difference |
|---|---|---:|---:|---:|
| 2021 | `202233119349303683` | $60,340 | $60,340 | $0 |
| 2022 | `202313199349321846` | $56,054 | $56,054 | $0 |
| 2023 | `202520669349300602` | $43,737 | $43,737 | $0 |
| 2024 | `202543159349300844` | $0 | $87,060 | $87,060 |

The historical match is a classification fact, not evidence that a particular
person received the TY2024 amount.

## IRS instruction check

The 2024 Form 990 instructions say that Part VII reports compensation for the
calendar year ending within the tax year. They say Part IX line 5 reports total
compensation paid to current officers, directors, trustees, and key employees
for the organization's tax year, using the organization's accounting method.
The instructions therefore recognize that Parts VII and IX can differ because
of accounting period or method.

That rule creates a possible category-level explanation, but it does not
reconcile this filing:

- Look Ahead America's calendar year and tax year are the same.
- The return uses accrual accounting but reports no year-end liabilities.
- Part VII reports no reportable or other compensation for any named officer.
- Part IX provides only an aggregate and no recipient.

An accrued, deferred, reimbursed, or omitted compensation entry is possible in
the abstract. None is established by this return.

## Amendment, PDF, and supporting-record sweep

- The official IRS 2025 XML index contains one TY2024 row for EIN 82-1645970:
  object `202543159349300844`, batch `2025_TEOS_XML_11B`.
- The current 2026 IRS XML index contains no row for the EIN.
- The TY2024 XML contains no affirmative amended-return indicator.
- No Schedule J or compensation-related Schedule O statement is present.
- ProPublica's TY2024 document entry exposes the full filing view and XML but
  no rendered PDF link. Older TY2021 and TY2022 entries expose both PDF and
  XML. The absence is limited to the reviewed public page; it is not proof that
  a PDF cannot later be posted.
- The return itself reports that its financial statements were neither
  compiled/reviewed by an independent accountant nor audited.

## State-record sweep

- Wisconsin DFI credential `21794-800` identifies Look Ahead America Inc but
  says the credential is not current and was revoked after 2023-07-31. Its
  public Financials tab offers only fiscal year 2020, so it supplies no TY2024
  compensation record.
- New Hampshire DOJ registration `33602` listed Look Ahead America Inc as not
  in good standing, with a report due 2023-11-15, in the official list updated
  2024-10-03. It supplies no TY2024 compensation record.
- California's charity registry was unavailable during its announced
  2026-07-22 to 2026-07-23 maintenance window.
- Virginia's current official registry host returned HTTP 400 during review.
  A separate URL in a Virginia FAQ now redirects to a parked third-party
  domain and was not used.

The state sweep is therefore bounded. California and Virginia were not treated
as cleared, and no claim is made that a nonpublic ledger or state submission
cannot exist.

## Reopening criteria

The mismatch can be resolved only by a record that identifies the accounting
entry or recipient, such as:

1. an amended TY2024 Form 990;
2. a state-filed Form 990 copy with a compensation attachment;
3. the FY2024 general ledger, payroll register, Forms W-2/1099, or deferred
   compensation records;
4. board minutes or a compensation resolution; or
5. a later Form 990 that expressly corrects or explains TY2024.

## Source audit

| Artifact | SHA-256 / status |
|---|---|
| TY2021 XML, object `202233119349303683` | `7fe3b7b6c57c11c6c2a31152b92a3e3ee7caead90e43aa8b474f37e0e643e11a` |
| TY2022 XML, object `202313199349321846` | `40711be76b45fe6e6d7cd65a5099cfd2e24cde95b60a6092167c6cdf577f2c6d` |
| TY2023 XML, object `202520669349300602` | `d4afadda4518aaf1f44c96f863c0163e822412177ea4c37c9577c7c353e3007f` |
| TY2024 XML, object `202543159349300844` | `6140ba9a0ad00c6feda1d3edf20755960fd040fe60fedfa4d57cbb7095bf145c` |
| IRS 2025 XML index | `e54ba6938d98b1746f2fd464a0f77e520efd956dc3da737d73843dc0013c6770` |
| IRS 2026 XML index | `00c1d156ef89fc676c2a3f59c81100dc0d9f7601d251fdfcd02ba58c0877110f` |

Primary/reference URLs:

- IRS Form 990 XML downloads:
  <https://www.irs.gov/charities-non-profits/form-990-series-downloads>
- 2024 Instructions for Form 990:
  <https://www.irs.gov/pub/irs-prior/i990--2024.pdf>
- ProPublica filing page:
  <https://projects.propublica.org/nonprofits/organizations/821645970>
- Wisconsin DFI charity search:
  <https://apps.dfi.wi.gov/ice/berg/Registration/OrganizationCredentialSearch.aspx>
- New Hampshire DOJ registered-charities list:
  <https://mm.nh.gov/files/uploads/doj/remote-docs/registered-charities.pdf>

Database records: finding #14265 was refined and attached to lead #75701;
bounded-negative finding #14316 was added. Both passed the provenance audit
with zero reported issues.
