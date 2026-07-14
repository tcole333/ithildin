# GEO executive/director federal donor identity resolution — lead 59035

## Outcome

The SEC-bounded universe contains 20 people. Nineteen have identity-retained FEC Schedule A rows; Scott M. Kernan returned zero exact-full-name rows across cycles 2016, 2018, 2020, 2022, 2024, and 2026. This is a bounded federal negative, not a claim that he never donated.

The FEC pass produced 4,548 candidate rows. Identity controls retain 1,467; the memo/transfer-safe source rule retains 1,335 individual-receipt rows totaling $1,632,401.60 gross. Those receipts split into $465,022.10 to GEO's federal PAC and $1,167,379.50 to external federal political committees. These are receipts attributed to individuals, not corporate contributions.

The totals are identity-scoped to people in the SEC-bounded roster, not tenure-scoped to dates when each person served GEO. Some retained receipts expressly predate GEO employment or board service, including Suchinski/Spirit AeroSystems, Koren/Darden, and Bartzokis medical-practice records. No in-tenure subtotal is inferred.

Transaction-level Schedule B review confirms seven refunds totaling $10,676.90. Six totaling $8,476.90 have a source-receipt link and produce a conservative linked-refund net of $1,623,924.70. The separate $2,200.00 DLJCC PAC refund is confirmed but not subtracted because the original Schedule A receipt was not found in targeted processed-data searches.

## Identity method

The 2026 SEC proxy supplies the current seven-director slate and thirteen-officer roster (George C. Zoley overlaps); the 2024 proxy supplies former CFO/CEO Brian R. Evans. A row is retained only when the name is corroborated by a combination of full/middle name, location, employer, title, date, or a career transition described in the proxy. Employer text alone is insufficient for common names.

The source-receipt rule then requires an identity-retained FEC `IND` row, an official line label for contributions from individuals, and `memoed_subtotal=false`. This keeps Form 3P line 17A individual receipts where the official label identifies them as individual contributions, while excluding memo redesignations, reattributions, and JFC/downstream transfers.

## Largest gross personal receipt totals

| Person | Source rows | Gross | GEO PAC | External | Linked refunds | Linked-refund net |
|---|---:|---:|---:|---:|---:|---:|
| George C. Zoley | 186 | $1,140,393.90 | $56,343.90 | $1,084,050.00 | $8,284.60 | $1,132,109.30 |
| Christopher D. Ryan | 126 | $61,159.60 | $53,959.60 | $7,200.00 | $0.00 | $61,159.60 |
| Ronald A. Brack | 125 | $59,659.30 | $55,959.30 | $3,700.00 | $0.00 | $59,659.30 |
| Shayn P. March | 127 | $58,709.30 | $55,959.30 | $2,750.00 | $0.00 | $58,709.30 |
| Daniel Ragsdale | 97 | $57,467.60 | $40,767.60 | $16,700.00 | $192.30 | $57,275.30 |
| David O. Meehan | 123 | $51,897.60 | $51,897.60 | $0.00 | $0.00 | $51,897.60 |
| Brian R. Evans | 20 | $31,001.00 | $0.00 | $31,001.00 | $0.00 | $31,001.00 |
| Paul Laird | 109 | $30,375.00 | $28,875.00 | $1,500.00 | $0.00 | $30,375.00 |
| Nicole Mannarino | 145 | $28,480.00 | $27,800.00 | $680.00 | $0.00 | $28,480.00 |
| Jack Brewer | 18 | $22,500.00 | $22,500.00 | $0.00 | $0.00 | $22,500.00 |

The full 20-person table, committee table, cycle table, and party/class table are in the CSV artifacts. Committee party fields are reproduced only where the FEC committee object supplies official party metadata. `trump_named_committee` is a literal committee-name flag, not an ideological or influence assessment.

## Literal Trump-named committee subset

Ten source-receipt rows totaling $302,940.00 went to committees whose official FEC names literally contain Trump, Save America, Never Surrender, or MAGA. The person breakdown is George C. Zoley $286,600.00, Brian R. Evans $11,600.00, Daniel Ragsdale $4,000.00, and Thomas C. Bartzokis $740.00. This is a gross committee-name classification only, not a complete ideological category, tenure-scoped total, or evidence of access or influence.

## Notable identity resolutions

- Mark Suchinski's records transition from Wichita/Spirit AeroSystems through June 2024 to Florida/GEO after his SEC-reported July 8, 2024 appointment. This resolves records beyond a GEO-only employer search.
- Lindsay Koren's Orlando/Darden records and later Boca/GEO board records follow the employer/role chronology in the SEC proxy.
- Thomas Bartzokis's pre-board Boca medical-practice records match the distinctive practice named in his SEC biography.
- Brian Evans's Florida GEO CFO and 2024 CEO records match the 2024 SEC proxy; the Tonawanda, New York debt-collector cluster is excluded.
- Paul Laird's Charlotte/Boca/Delray GEO operations and secure-services records are retained. The Los Angeles and Redondo Beach records are unresolved despite GEO employer text and are excluded.

## Refund controls

Schedule B aggregate hits are not themselves treated as refunds. The refund ledger contains only transaction rows with person, committee, date, amount, description, line, filing identifiers, and link status. The unmatched $2,200 item remains outside the net.

## Coverage and limitations

- Federal Schedule A coverage: six cycles from 2016 through 2026, plus one targeted 2014 lookup solely to resolve a 2015 refund link. Cycle 2026 is year-to-date through the July 14, 2026 archive date; it is not a completed two-year cycle and should not be compared as an equal-duration total.
- Federal Schedule B coverage: the same six cycles for all 20 names, followed by transaction-level resolution of plausible hits.
- Florida state coverage: unavailable because the official portal returned a Cloudflare challenge and no interactive browser backend was available. This is logged as an access boundary, not a zero.
- Candidate-name searches produce substring and same-name noise; every excluded row remains in the matrix for audit.
- The totals are identity-scoped, not tenure-scoped. They include retained pre-GEO or pre-board receipts where SEC career history resolves identity; no in-tenure subtotal was built.
- Totals describe receipts reported under resolved individual identities. They do not establish motive, access, favor, or policy influence.

## Primary evidence

- `investigations/geo-group/sources/2026-07-14-lead-59035/sec/geo-2026-def14a.html`
- `investigations/geo-group/sources/2026-07-14-lead-59035/sec/geo-2024-def14a.html`
- `investigations/geo-group/sources/2026-07-14-lead-59035/fec` (120 Schedule A cycle files)
- `investigations/geo-group/sources/2026-07-14-lead-59035/fec-refunds` (120 corrected Schedule B aggregate cycle files)
- `investigations/geo-group/sources/2026-07-14-lead-59035/fec-refund-transactions` (transaction-resolution files)
- `investigations/geo-group/sources/2026-07-14-lead-59035/fec-refund-links` (targeted Schedule A/committee link files)
