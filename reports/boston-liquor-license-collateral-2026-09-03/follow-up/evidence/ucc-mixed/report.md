# Fixed sample S05–S08: current Massachusetts UCC checks

All four assigned holders were searched using the preselected name queries, current debtor begins-with mode, and no city/state/date filter. All matching index rows and all three matching original histories were inspected. **No explicit liquor-license collateral was observed in these four cases:** two had no current name match, and two had broad collateral descriptions. These results are not a finding that any holder lacks secured borrowing, nor a current-loan-balance determination.

| Sample | Roster holder / license | Current index | Observed result |
|---|---|---:|---|
| S05 | MAPLE & ASH BOSTON, LLC / LB-99388 | 0 | Verified no matching current MA UCC record for `MAPLE & ASH BOSTON`. |
| S06 | 10 City Square LLC (Prima) / LB-445992 | 3 occurrences; 2 originals | Cambridge Savings Bank broad all-assets filing; US Foods broad supplier-credit filing with a recorded termination. |
| S07 | Castillo Morton Street, LLC / LB-101905 | 0 | Verified no matching current MA UCC record for `Castillo Morton Street`. |
| S08 | Virpa Corp (Square Bites) / LB-464464 | 1 occurrence; 1 original | Rockland Trust broad assets/general-intangibles collateral. |

## S06: 10 City Square LLC / Prima

The exact legal entity name matches the roster. UCC mailing addresses (426 West Broadway and 12 Park Street) differ from the roster premises at 10 City Square. All three source search occurrences belong to that exact legal name, with no unrelated-name rows.

**MA-UCC:202634020070**, filed July 31, 2026 at 1:13 PM, names **CAMBRIDGE SAVINGS BANK**. The HTML history displays no collateral text, so its one-page original PDF was opened and visually inspected in the Chrome CUA PDF viewer. Its entire collateral statement reads:

> All assets of the Debtor, whether now owned or hereafter acquired, and all products and proceeds of the foregoing.

This is broad all-assets collateral, with no explicit liquor-license wording. The displayed history contains only the initial filing; absence of a displayed termination does not establish an outstanding loan. [Original PDF viewer](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2026/0731/003241149/0001/202634020070_1.pdf).

**MA-UCC:202634147290**, filed August 7, 2026 at 8:59 AM, names **US FOODS, INC.** and describes supplier-credit security. Exact excerpt:

> To secure the full and timely payment by Applicant to Seller of all amounts due to Seller, Applicant grants to Seller a security interest in all of Applicant's personal property

The remaining text includes goods delivered on credit, inventory, equipment, fixtures, vehicles, and proceeds. It does not specifically identify a liquor license. **MA-UCC:202634733240**, filed August 25, 2026 at 3:00 PM, records `TerminationSecuredParty`. [Original PDF viewer](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2026/0807/000000000/2366/202634147290_1.pdf); [termination PDF viewer](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2026/0825/000000000/3504/202634733240_1.pdf).

## S08: Virpa Corp / Square Bites

**MA-UCC:202398867270**, filed March 23, 2023 at 12:14 PM, names **VIRPA CORP.**, 38 Maverick Square, East Boston MA 02128, matching both roster legal name and premises. The secured party is **ROCKLAND TRUST COMPANY**. Displayed collateral covers inventory, equipment, accounts, and other categories, including this exact phrase:

> general intangibles (including but not limited to all software and all payment intangibles)

The complete source text is in `S08-cua-observed.json`. No explicit liquor-license wording appears. The displayed history has only the initial filing. [Original PDF viewer](https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchViewPDF.aspx?Path=DRIVE1/2023/0323/000000000/1164/202398867270_1.pdf).

## Non-matches and evidence handling

S05 and S07 each showed the verified source marker `* No records found; try a new search using different criteria`, with the requested organization name, Begins With, DEBTORS, and INCLUDE ALL city/state/date criteria visible. These are current MA index non-matches, not “no lien” conclusions. Debtor spelling, entity identity, state of organization, another filing jurisdiction, and historical/lapsed records remain outside this bounded check.

The browser was an isolated task tab controlled through CUA in the existing Chrome session after the parent authorized that alternative to the unavailable subagent in-app surface. No user tabs were used and no external Playwright process was launched. `content.export()` proved unsupported (papercut #2655), so the artifacts are explicitly labeled **CUA-observed JSON transcriptions**. The Cambridge PDF was visually inspected; no PDF or HTML file was downloaded. Other PDF viewer links were recorded from the displayed filing histories.

Canonical initial search keys and filing keys were checked before retrieval and successful counts logged afterward (`log-audit.jsonl`). No findings were added, no investigation profile changed, and no repository code edited. Coverage is complete for all matched current records in these four queries; there is no five-original cap truncation.

Artifacts: `results.json`, one `Sxx-cua-observed.json` per case, `samples.json`, and `log-audit.jsonl`. Selection comes from the parent's fixed sample plan, not these UCC outcomes.
