# AAF intermediary-grant origin attribution

Date reviewed: 2026-07-23  
Profile: `oversight-project`  
Lead: `73863`  
Investigation thread: `181`

## Question and evidentiary boundary

This memo tests whether public records identify the originating donor, donor-advised
account, recommending individual, or enforceable use restriction behind six grants
reported to the American Accountability Foundation (AAF; EIN 85-4391204) by five
charitable intermediaries.

The IRS Schedule I rows prove that the named filing organizations paid AAF. They do
not, by themselves, prove that any particular donor recommended the payment, that
the money came from a donor-advised account rather than the intermediary's
discretionary pool, or that the Schedule I purpose text was an enforceable
restriction.

## Exact primary-source grant matrix

The “grant year” below follows the repository's recipient-grant convention. The
period-end column preserves the return's exact fiscal period and removes ambiguity
for fiscal-year filers.

| Grantor | EIN | Grant year | Tax-period end | IRS object | Cash | Schedule I purpose |
|---|---:|---:|---:|---|---:|---|
| Servant Foundation, d/b/a The Signatry | 43-1890105 | 2024 | 2024-03-31 | `202500439349301825` | $153,236 | `COMMUNITY DEVELOPMENT` |
| DonorsTrust | 52-2166327 | 2023 | 2023-12-31 | `202423189349304787` | $20,000 | `for general operations` |
| Fidelity Charitable Gift Fund | 11-0303001 | 2022 | 2022-06-30 | `202430459349302913` | $17,500 | `For grant recipient's exempt purposes` |
| Fidelity Charitable Gift Fund | 11-0303001 | 2023 | 2023-06-30 | `202441369349301334` | $22,300 | `For grant recipient's exempt purposes` |
| Goldman Sachs Charitable Gift Fund | 11-3813663 | 2022 | 2022-06-30 | `202311099349301951` | $25,000 | `CAPITAL CAMPAIGN` |
| National Christian Charitable Foundation | 58-1493949 | 2023 | 2023-12-31 | `202443169349306424` | $16,750 | `CULTURE` |
| **Total** |  |  |  |  | **$254,786** |  |

All six rows identify AAF by EIN 85-4391204. The Fidelity 2022 row is taken from
the later amended return received 2024-02-14. An earlier return object,
`202321309349304807`, mispaired recipient names and EINs in the relevant area;
the amended object correctly pairs AAF with EIN 85-4391204 and controls here.

## What the purpose fields can and cannot establish

The purpose text is not unique to AAF. Counts across each complete Schedule I XML
show the same labels repeated broadly:

| Return | Total recipient rows | AAF purpose label | Rows using that label |
|---|---:|---|---:|
| Servant 2024 | 2,695 | `COMMUNITY DEVELOPMENT` | 1,110 |
| DonorsTrust 2023 | 779 | `for general operations` | 471 |
| Fidelity 2022 amended | 65,439 | `For grant recipient's exempt purposes` | 65,439 |
| Fidelity 2023 | 72,328 | `For grant recipient's exempt purposes` | 72,328 |
| Goldman Sachs 2022 | 2,488 | `CAPITAL CAMPAIGN` | 66 |
| National Christian Foundation 2023 | 14,557 | `CULTURE` | 824 |

These repeated classifications support treating the strings as broad reporting
labels. They do not identify an originating donor. Nor do they establish an
enforceable restriction without a grant letter or agreement. Fidelity Charitable's
own program guidelines are particularly explicit that a donor's “special purpose”
recommendation is non-binding and “does not constitute a restriction placed by
Fidelity Charitable.”

## Attribution tests

### First-party DAF mechanics

- [DonorsTrust's FAQ](https://www.donorstrust.org/faqs/) says donor advisors may
  recommend grants and may send them anonymously; DonorsTrust does not publish
  donor names. Its [grant-request page](https://www.donorstrust.org/requesting-grant-daf/)
  says amounts allocated to an account are DonorsTrust's general operating funds
  and DonorsTrust retains sole legal discretion.
- [Fidelity Charitable's DAF guidance](https://www.fidelitycharitable.org/guidance/philanthropy/what-is-a-donor-advised-fund.html)
  says donors may recommend grants, select a purpose, and choose anonymity. Its
  [program guidelines](https://www.fidelitycharitable.org/content/dam/fc-public/docs/programs/fidelity-charitable-program-guidelines.pdf)
  distinguish a non-binding recommended purpose from a legal restriction.
- [National Christian Foundation's Giving Fund page](https://www.ncfgiving.com/solutions/giving-fund/)
  describes a donor-advised fund whose donors recommend grants and may give
  anonymously.
- [Goldman Sachs Gives](https://www.goldmansachs.com/community-transformation/goldman-sachs-gives)
  is a donor-advised fund through which participating senior employees recommend
  grants. Goldman's [launch announcement](https://www.goldmansachs.com/pressroom/press-releases/2007/2007-11-21)
  also describes individual partner accounts, while leaving open institutional or
  pooled funding.
- Servant Foundation's [audited 2025 financial statements](https://wp.thesignatry.com/wp-content/uploads/2026/04/The-Signatry-Audited-Financial-Statements-FY25.pdf)
  define its donor-advised funds as separately identified funds owned and
  controlled by the organization, with donors retaining advisory privileges over
  distribution or investment.

These policies establish that donor recommendations and anonymity are possible.
They do not establish that any specific AAF grant was donor-advised, name the
recommender, or exclude a pooled/discretionary grant.

### Named-donor and restriction search

The following public-source classes were reviewed for a named donor, account,
restriction, or grant instrument:

- the six primary IRS return XMLs and the intermediaries' filing inventories;
- AAF's public IRS exemption application and public Form 990 materials;
- first-party grant announcements, donor acknowledgments, DAF guidance, and
  audited statements;
- DocumentCloud, the local unified/document corpora, and CourtListener results for
  AAF;
- targeted public searches for the exact grantors, amounts, grant agreements,
  acknowledgments, audited statements, board packets, and litigation exhibits;
- EDGAR, FEC, USASpending, GLEIF, UCC, ACRIS, and DS10 as negative-control or
  mandatory financial-source sweeps.

No reviewed public record named an originating donor or donor-advised account for
any of the six AAF grants. No reviewed public record supplied a grant agreement or
award letter that made `COMMUNITY DEVELOPMENT`, `CAPITAL CAMPAIGN`, or `CULTURE`
an enforceable use restriction.

This is a bounded negative result, not proof that no such donor or restriction
exists.

### Peterson Prize near-match is not attribution

The [Gregor G. Peterson Prize site](https://www.petersonventureprize.com/) lists
AAF as a 2023 finalist, lists Children's Entrepreneur Market as the 2023 winner,
and states that finalists receive no prize money. That first-party record
disconfirms an otherwise tempting inference that AAF's DonorsTrust grant came
from the Peterson family or Peterson Prize merely because AAF appeared in the
prize process.

## Conclusion

**Confirmed primary-source fact:** the five intermediaries reported six cash
grants totaling $254,786 to AAF over the 2022-2024 grant-year range.

**Bounded synthesis:** the reviewed public record does not identify the
originating donor, recommending individual, or donor-advised account behind any
row. The Schedule I purpose strings are too generic and repeatedly used to serve
as donor identifiers, and no grant instrument was found that converts the
project-like labels into proven legal restrictions. Pooled, intermediary-
discretionary, anonymous DAF, and unrestricted/general-purpose explanations
therefore remain live alternatives.

No donor should be attributed from ideological adjacency, co-funding, finalist
status, or the identity of an intermediary.

## Reopening dependencies

Further attribution requires at least one record not present in the reviewed
public corpus:

1. the intermediary's grant-recommendation record, donor-advised account name, or
   internal grants/board approval record;
2. AAF's grant transmittal or acknowledgment letter, deposit/general-ledger entry,
   donor correspondence, or unredacted contribution record;
3. a grant agreement or restriction letter signed by the intermediary or donor;
4. an AAF board packet or audited financial-statement workpaper naming the source;
5. a litigation, regulatory, or FOIA exhibit containing one of those records.

Absent such a document, further name-search permutations would not satisfy the
evidentiary standard for donor attribution.
