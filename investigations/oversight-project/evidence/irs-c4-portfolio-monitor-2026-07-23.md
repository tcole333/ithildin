# IRS public-filing monitor: Oversight, Frontier, and Blueprint

Checked 2026-07-23 (America/New_York) for lead #74242. This memo uses exact
identifiers and formation-record anchors. It does not adopt an IRS record merely
because a common organization name is similar.

## Exact target anchors

| Target | Exact anchors used |
|---|---|
| The Oversight Project | FEIN `33-3863270`; Wyoming corporation formed 2025-02-21; Florida charitable-registration number `CH78695`; fiscal year ending 12/31 |
| Frontier Foundation | Wyoming filing ID `2024-001554350`; filed 2024-11-14; mailing and principal address 300 Independence Ave SE, Washington, DC 20003; incorporator William M. Klimon; intended section 501(c)(4) |
| Blueprint for America Coalition | Wyoming filing ID `2025-001739274`; filed 2025-08-06; mailing and principal address 853 New Jersey Ave SE, Suite 200, Washington, DC 20003; incorporator William M. Klimon; intended section 501(c)(4) |

The earlier alleged Frontier ID `2024-001536327` is excluded: the Wyoming
register assigns it to Global Rescue Kitchen. Finding #14281 documents that
correction.

## Current public-source snapshot

The official IRS pages showed these current dates when re-opened on 2026-07-23:

- EO BMF: posting date **2026-07-14**, 1,983,563 records.
- Publication 78: **2026-06-09**.
- Form 990-N: **2026-07-06**.
- Form 990-series XML: the IRS bulk landing page showed **2026-06-17**; the
  directly downloaded 2026 index used here had 353,650 data rows and SHA-256
  `00c1d156ef89fc676c2a3f59c81100dc0d9f7601d251fdfcd02ba58c0877110f`.
- ProPublica Nonprofit Explorer exact/fuzzy results saved 2026-07-22 were used
  only as a secondary discovery/collision check.

Exact searches of the current 2026 XML index returned:

```text
The Oversight Project / EIN 333863270: 0
Blueprint for America Coalition: 0
Frontier Foundation (raw exact-name rows): 1
```

Across the 2024-2026 XML indices, the raw exact-name search for `FRONTIER
FOUNDATION` returned two filings, both for EIN `20-1261404`: TY2024 Form 990-PF
object `202531359349104973` and TY2025 Form 990-PF object
`202621279349102742`. The official Publication 78 file resolves that EIN to
**Frontier Scholarship Fund**, Gardena, California, classification `POF`.
That is a private-foundation record, not the Wyoming section 501(c)(4) formed
in 2024 at 300 Independence Ave SE. It is rejected as a name collision.

The selected current BMF files for the known Wyoming/DC/Virginia/Washington
addresses, the nationwide 990-N extract, and Publication 78 had zero exact
target rows for all three organizations. The broader nationwide exact-EIN
check for Oversight is preserved separately in
`irs-ein-333863270-bulk-check-2026-07-22.md`; it also found zero rows in BMF
regions 1-4, Publication 78, automatic revocation, 990-N, the 2025/2026 XML
indices, and the TEOS determination-letter search.

The live TEOS determination-letter interface is JavaScript-only. The browser
control surface was unavailable during this 2026-07-23 recheck, so no new
interactive determination-letter result is claimed for Frontier or Blueprint.
That access limitation does not change the bounded negative from the current
BMF/XML/990-N files, and it is not converted into an inference that no
application or determination exists.

## Entity-specific disposition and filing windows

### The Oversight Project

Oversight's EIN is resolved, but no exact current federal filing/exemption row
is public. The Florida renewal is the controlling timing evidence: it states a
12/31/2025 fiscal-year end, selects “Extension request for financial statement
only,” and lists the submitted Form 8868 attachment
`260211 TOP IRS 8868 to 11-15-26.pdf`. The first calendar-year Form 990 or
990-EZ was normally due 2026-05-15. The attachment documents an extension
through 2026-11-15; because that date is a Sunday, the next-business-day rule
makes Monday 2026-11-16 the practical filing date. A public-filing monitor
should resume on **2026-12-15**, allowing roughly 30 days for IRS/aggregator
posting, or earlier only if exact EIN `33-3863270` appears.

No delinquency or nonfiling inference is warranted before that condition.

### Frontier Foundation

Frontier's verified Wyoming articles do not designate a fiscal year, and no
verified EIN has surfaced. The available windows are therefore conditional:

- If it used a short calendar initial period ending 2024-12-31, a Form 990 or
  990-EZ was normally due 2025-05-15 and could have been extended to Monday
  2025-11-17.
- If its first accounting year ended 2025-10-31, the ordinary due date was
  Monday 2026-03-16 and a six-month extension could run to 2026-09-15.
- If operations began in 2025 and it used a calendar year ending 2025-12-31,
  the ordinary due date was 2026-05-15 and an extension could run to Monday
  2026-11-16.
- The Wyoming corporation was administratively dissolved 2026-01-09. A final
  return tied to that termination would ordinarily be due 2026-06-15 and could
  be extended to 2026-12-15. State dissolution does not itself prove federal
  termination, a missed filing, or that the organization ever adopted a
  particular accounting period.

Resume the TY2024/TY2025 exact-name/identifier monitor on **2026-12-15** (or
earlier if a verified EIN appears). If still absent, perform one final-return
lag check on **2027-01-15** before drawing any filing-status inference.

### Blueprint for America Coalition

Blueprint's verified Wyoming articles likewise do not designate a fiscal year,
and no verified EIN has surfaced.

- If it used a short calendar period from formation through 2025-12-31, its
  first Form 990 or 990-EZ was normally due 2026-05-15 and could be extended to
  Monday 2026-11-16.
- A permissible first fiscal year ending 2026-07-31 would instead produce a
  normal due date of 2026-12-15 and a six-month extended date of 2027-06-15.

Run an early calendar-year check on **2026-12-15**. Because the articles do not
establish the accounting period, do not classify the first return as missing
until an exact-identifier check after **2027-07-15** (the latest conditional
extended date above plus roughly 30 days for posting).

## Public-record limits

- IRS instructions state that section 501(c)(4) organizations generally are
  not required to file optional Form 1024-A to be tax-exempt. A missing
  determination letter or BMF row therefore is not proof of nonexempt status.
- Most new section 501(c)(4) organizations must file Form 8976, but the IRS
  states that the form is not open to public disclosure and that it keeps no
  public database of filers. Public OSINT cannot establish Form 8976
  nonfiling.
- An organization claiming exemption generally must file its annual return
  even before recognition. Form 990/990-EZ may receive a six-month extension;
  Form 990-N cannot. Before the accounting period and return type are known,
  990-N absence does not establish that an extendable Form 990/990-EZ is late.

## Primary source URLs

- https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads
- https://www.irs.gov/charities-non-profits/annual-exempt-organization-return-due-date
- https://www.irs.gov/instructions/i1024a
- https://www.irs.gov/irm/part4/irm_04-070-012
- `investigations/oversight-project/evidence/fdacs-ch78695-dtn4229006-application-2026.pdf`
- `investigations/oversight-project/evidence/frontier-foundation-articles-2024.pdf`
- `investigations/oversight-project/evidence/blueprint-for-america-articles-2025.pdf`

## Local evidence integrity

| Artifact | SHA-256 |
|---|---|
| Current 2026 XML index | `00c1d156ef89fc676c2a3f59c81100dc0d9f7601d251fdfcd02ba58c0877110f` |
| IRS EO BMF page snapshot | `7fb19ff41bc137ba7df355ba36816358dc9a4eea01dbb2b045eacf4645002ea3` |
| IRS bulk-data page snapshot | `512fb77c25de4f8a3232a4cc8e3e1413961e5c79d9f5a5a21664487c616b6396` |
| 990-N extracted text | `79b7e1c5f8230e81b660d1909bf68a0bed4022c3c13e4a697e182dcdcc3d15e3` |
| Publication 78 extracted text | `bcdb1032fb69ad92286355106a0f5a3b414e78f5ac9b95b3d6d8115d1a9ac2c1` |
| Frontier articles | `b329edb24d94b096fcf40485399ff71450d33148a9a93ddd6e5519a023edcf35` |
| Blueprint articles | `9c332e2099c39e008777fb6f37f50d1a83662a149d12cbd4c8fb3ed48b485f5b` |
| Oversight Florida renewal | `7029a90170824659a96ef2d2acd23acbe11d0941b5bdfbfec062b2d0ece36a77` |
