# GEO corporate Federal/National Committees reconciliation, 2024–2025

Lead `#59037` | Profile `geo-group` | Thread `112` | Primary-source review through 2026-07-14

## Bottom line

GEO's company reports cannot be fully reconciled to public recipient filings without forcing the arithmetic.

| Report year | GEO corporate Federal/National Committees | Eligible recipient-filed gross | Exact difference | Status |
|---|---:|---:|---:|---|
| 2024 | $2,150,000 | $2,125,000 | **$25,000 company residual** | 98.8372% itemized; unreconciled |
| 2025 | $1,575,000 | $1,665,000 | **$90,000 recipient-filed overrun** | 105.7143% itemized; unreconciled |

The 2024 itemization consists of 13 corporate-subsidiary receipts reported by five federal committees. The 2025 itemization consists of 10 corporate-subsidiary receipts reported by six federal committees. Targeted Schedule B searches found no exact GEO-named refund or reversal that closes either difference.

The 2025 total includes two distinct positive CLF non-contribution-account receipts: **$150 on May 28** ([image `202510279792025505`](https://docquery.fec.gov/cgi-bin/fecimg/?202510279792025505), sub-ID `4121020251297765123`) and **$149,850 on June 11** ([image `202510279792025549`](https://docquery.fec.gov/cgi-bin/fecimg/?202510279792025549), sub-ID `4121020251297765255`). Both carry amendment indicator `N`, line 17, and memo `NON CONTRIBUTION ACCOUNT`; together they equal $150,000. The $150 is not a refund, fee, or amendment reversal, so the correct 2025 recipient gross is $1,665,000—not $1,664,850.

## Company denominators

The [2024 GEO report](https://www.geogroup.com/media/tufn44mo/geo-political-activity-and-lobbying-report-_2024_.pdf) introduces its tables as containing “aggregate political contributions made by GEO corporate subsidiaries and GEO PAC broken down by Source of Funds and by Recipient Category.” Its Federal/National table reports `Committees` of **$225,000 GEO PAC** and **$2,150,000 Corporate**. The same table separately reports **$515,000 Corporate** for `527 Organizations`.

The [2025 GEO report](https://www.geogroup.com/geo-2025-political-activity-and-lobbying-report/) uses the same introductory sentence and reports Federal/National `Committees` of **$95,000 GEO PAC** and **$1,575,000 Corporate**. It separately reports **$450,000 Corporate** for `527 Organizations`.

Those categories control this reconciliation. Employee-funded GEO PAC checks, individuals, state/local recipients, 527 organizations, inaugural donations, and convention-host donations are not interchangeable with the corporate committee denominator.

## 2024 recipient reconstruction

| Recipient | FEC type | Recipient filing treatment | Gross |
|---|---|---|---:|
| Make America Great Again Inc. (`C00825851`) | Super PAC (IE-only) | line 11AI contribution/receipt | $1,000,000 |
| CLF (`C00504530`) | Hybrid PAC with non-contribution account | line 17; `NON CONTRIBUTION ACCOUNT` | $450,000 |
| SLF PAC (`C00571703`) | Super PAC (IE-only) | line 11AI contribution | $400,000 |
| Right for America (`C00867036`) | Super PAC (IE-only) | line 11AI contribution | $250,000 |
| Oklahoma Victory Committee (`C00879072`) | Super PAC (IE-only) | line 11AI receipt | $25,000 |
| **Total** |  |  | **$2,125,000** |

All 13 included rows name `GEO ACQUISITION II INC`, the punctuated variant, or the recipient's misspelling `GEO ACQUISTION II INC.` They have 2024 receipt dates and belong to FEC-registered federal committees. The recipient-filing classification subtotal is **$1,675,000 on IE-only committee contribution/receipt lines** and **$450,000 on a hybrid PAC's non-contribution-account line 17**.

No included recipient is state/local-only, 527-only, inaugural, or convention-host. The public itemization leaves exactly **$25,000** of GEO's denominator unexplained.

## 2025 recipient reconstruction

| Recipient | FEC type | Recipient filing treatment | Gross |
|---|---|---|---:|
| MAGA Inc. (`C00892471`) | Hybrid PAC with non-contribution account | line 17; `NON-CONTRIBUTION: TAXED AS A CORPORATION` | $1,000,000 |
| CLF (`C00504530`) | Hybrid PAC with non-contribution account | line 17; `NON CONTRIBUTION ACCOUNT` | $400,000 |
| SLF PAC (`C00571703`) | Super PAC (IE-only) | line 11AI contribution | $150,000 |
| Restore Our Nation / RON PAC (`C00841130`) | Hybrid PAC with non-contribution account | line 17; `NON CONTRIBUTION ACCOUNT` | $100,000 |
| First Principles PAC (`C00893537`) | Hybrid PAC with non-contribution account | line 17; `NON FEDERAL CONTRIBUTION` | $5,000 |
| Conservative Leadership for Florida (`C00916924`) | Super PAC (IE-only) | line 11AI contribution | $10,000 |
| **Total** |  |  | **$1,665,000** |

The 10 included rows name `GEO ACQUISITION II INC.`, `GEO REENTRY SERVICES LLC`, or `GEO REENTRY SERVICES`. Every transaction has a 2025 receipt date even when the recipient filed or amended the public report in 2026. The denominator comparison therefore uses the reported transaction date, not the later FEC load or filing date.

All six recipients are FEC-registered federal committees. `CONSERVATIVE LEADERSHIP FOR FLORIDA` is not treated as state/local merely because of its name: FEC metadata classifies `C00916924` as a federal **Super PAC (Independent Expenditure-Only)**. The recipient-filing classification subtotal is **$160,000 on IE-only committee contribution lines** and **$1,505,000 on hybrid-PAC line-17 non-contribution/non-federal receipts**.

The public itemization exceeds GEO's denominator by exactly **$90,000**. The records do not identify which company payment, internal accounting date, category coding, or report error explains the difference. It remains an overrun; it is not netted by assumption.

## Federal-law classification boundary

The ledger records the classification the federal recipient actually filed:

- `F3X` line `11AI` and the recipient's `CONTRIBUTION`/receipt description for IE-only committees;
- `F3X` line `17`, the line label `Other Federal Receipts`, and recipient memos such as `NON CONTRIBUTION ACCOUNT`, `NON FEDERAL CONTRIBUTION`, or `NON-CONTRIBUTION: TAXED AS A CORPORATION` for hybrid PACs;
- `F13` `Donations Accepted` for an inaugural committee.

This is narrower than a final legal conclusion. It does not decide whether the payer was a federal contractor at that moment, whether a particular subsidiary was legally distinct for source-prohibition purposes, or whether a regulator would find a violation. No such adjudication is inferred here.

## Refunds, reversals, and amendments

Exact-name post-filtering of Schedule B disbursement searches for every included recipient found **zero GEO-named refunds**. The 2024 and 2025 gross totals therefore remain unchanged. This is a bounded negative result, not proof that no private repayment, later accounting correction, or differently named refund exists.

The ledger preserves amendment indicator, file number, image number, and sub-ID for each row. It uses the processed recipient records and does not sum superseded amendment copies. The $150 and $149,850 CLF rows are distinct current positive receipts with different dates, images, and sub-IDs.

## Exclusions and attribution conflicts

### Employee-funded GEO PAC

Two recipient abbreviations initially resemble corporate rows but match GEO PAC Schedule B:

- `THE GEO GROUP` → Tom Barrett for Congress, $1,000 recipient receipt in 2024; GEO PAC reports the corresponding $1,000 check.
- `THE GEO GROUP, INC.` → Lance Gooden for Congress, $1,000 on April 30, 2025; GEO PAC reports the same recipient, amount, and date. The recipient API supplies two sub-IDs for one image, so the apparent second $1,000 is also excluded as a duplicate.

Advance the Senate's $25,000 receipt explicitly identifies contributor ID `C00382150`—GEO PAC—and GEO PAC Schedule B reports the matching $25,000 check ([donor image `202410209699390299`](https://docquery.fec.gov/cgi-bin/fecimg/?202410209699390299)). It is not the missing corporate $25,000.

### Trump-Vance inaugural Form 13

The current located amended [Trump Vance Inaugural Committee Form 13](https://docquery.fec.gov/pdf/858/202507319779596858/202507319779596858.pdf) reports:

> THE GEO GROUP, INC. POLITICAL ACTION COMMITTEE

It gives a December 11, 2024 receipt date, **$500,000**, and transaction `F132.147237991`. A targeted GEO PAC Schedule B search found no matching inaugural disbursement. The recipient label and donor-side record therefore conflict. Because Form 13 names GEO PAC—not a corporate subsidiary—and because an inaugural donation is not a federal campaign contribution, the record is excluded from the corporate committee denominator and left unresolved.

### American Liberty Foundation

American Liberty Foundation (`C00830042`) reports a July 15, 2025 line-17 `NON-CONTRIBUTION ACCOUNT` receipt of **$250,000** from `THE GEO GROUP, INC. PAC` ([image `202604069857012775`](https://docquery.fec.gov/cgi-bin/fecimg/?202604069857012775)). A targeted GEO PAC Schedule B search found no matching payment. The recipient's PAC label is preserved; the record is not reassigned to corporate treasury without donor-side evidence.

## Convention-host and 527 checks

FEC guidance states that convention and host committees disclose receipts and disbursements on Form 4. No eligible GEO corporate Form 4 receipt appeared in the processed 2024 recipient-name universe. That bounded negative result contributes nothing to either denominator.

GEO separately names the Republican Governors Association, Republican Attorneys General Association, GOPAC, and Republican State Leadership Committee as National 527 recipients in both reports. It does not publish per-recipient allocations. The **$515,000** 2024 and **$450,000** 2025 527 totals remain a separate company-report row and are not used to plug the committee residuals.

## Audit conclusion and required primary record

Public federal filings establish a strong but incomplete recipient reconstruction. They do not supply GEO's internal check register, general-ledger category, payment/clearing date, or a recipient-level schedule behind the company reports. The minimum record needed to finish this reconciliation is GEO's recipient-level corporate treasury schedule for each year, including payee legal name, amount, approval/payment date, refund, and the exact report bucket used.

Until that record is obtained:

- 2024 remains **$2,125,000 itemized + $25,000 unresolved = $2,150,000 company-reported**.
- 2025 remains **$1,665,000 recipient-filed − $90,000 unresolved overrun = $1,575,000 company-reported**.

## Durable artifacts

- [`2026-07-14-lead-59037-geo-corporate-federal-committee-ledger.csv`](./2026-07-14-lead-59037-geo-corporate-federal-committee-ledger.csv) — transaction ledger with donor legal entity, recipient, date, amount, refund status, filing line, legal-stream classification, amendment, image, and sub-ID.
- [`2026-07-14-lead-59037-geo-corporate-federal-committee-reconciliation.json`](./2026-07-14-lead-59037-geo-corporate-federal-committee-reconciliation.json) — machine-readable denominators, recipient totals, classifications, exclusions, and exact residuals.
- [`2026-07-14-lead-59037-source-coverage-manifest.json`](./2026-07-14-lead-59037-source-coverage-manifest.json) — source-by-source coverage, negative tests, applicability, and limitations.

## Database records and supersession

Verified findings: `#12752`–`#12759`. Finding `#12751` was retracted with an audit trail after a CLI-quoting defect and replaced by correctly quoted finding `#12752`. Human action `#48` requests GEO's recipient-level corporate treasury ledger/check register.

The amended Trump-Vance Form 13 in finding `#12755` supersedes the bounded negative that remained in lead `#58870`'s report artifacts. Those prior Markdown, JSON, and CSV artifacts were corrected on 2026-07-14. The correction preserves the Form 13 donor label as GEO PAC, leaves the payer stream unresolved because no matching donor-side Schedule B record was found, and does not add the $500,000 to a corporate or PAC arithmetic total.
