# Testing license costs and restaurant ownership concentration

Checked September 3, 2026. This report supplies policy cohorts and comparison requirements; it does not establish that license prices caused concentration. The downloaded primary sources and short quotations are indexed in `sources.json`. No public-records request or other third-party contact was made.

## What the policy actually changes

[Chapter 202 of the Acts of 2024](https://malegislature.gov/Laws/SessionLaws/Acts/2024/Chapter202), approved September 11, created the following program. The ZIP allocation begins in calendar 2024, not with the first observed 2025 awards; unissued allocations carry forward.

| Program | Authorized supply | Implication for the comparison |
|---|---:|---|
| ZIP-restricted, non-transferable | 195: 117 all-alcohol and 78 beer/wine | Three all-alcohol and two beer/wine per ZIP per year for three years across 13 ZIPs; on-site food preparation required; returned licenses can be reallocated in the ZIP |
| Oak Square restricted | 3 all-alcohol | Separate geographic cohort |
| Community spaces | 15 all-alcohol | Different operating model; exclude from the main restaurant comparison or show separately |
| Citywide transferable awards | 12 all-alcohol | Directly awarded licenses can later transfer; transferability is not evidence of a market-price acquisition |

The City's [October 2024 rollout announcement](https://www.boston.gov/news/mayor-wu-announces-new-details-applying-new-liquor-licenses) says these awards avoid buying a license from an existing business. Thus an expensive-license variable must capture **acquisition route and documented consideration**, rather than treating all ordinary all-alcohol licenses as expensive purchases.

There is a second policy change. [MGL chapter 138, section 12D](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXX/Chapter138/Section12D), effective July 1, 2025, lets opting-in municipalities permit beer/wine licensees to convert to non-transferable all-alcohol licenses without increasing the total license count. Boston finalized its regulations January 8, 2026. Under [Boston's upgrade FAQ](https://www.boston.gov/departments/licensing-board/beer-and-wine-license-upgrades-frequently-asked-questions), on-premises beer/wine licensees, including cordials and both transferable and restricted licenses, can apply; package stores and farmer-series operators cannot. Upgraded licenses may change location with approval. An upgrade is therefore neither a new restaurant nor a sale, and non-transferable does not automatically mean immovable.

The annual fee schedule does not explain a six-figure barrier: Boston's [CV license fees](https://www.boston.gov/departments/licensing-board/fees-licenses) list the same $2,800 base for ordinary and restricted all-alcohol licenses, plus $100 and a capacity fee capped at $500. Beer/wine is $1,800 before those additions. The [new-license FAQ](https://www.boston.gov/departments/licensing-board/liquor-license-frequently-asked-questions) separately lists $200 application, $100 hearing, and $170 advertising fees. These administrative costs are distinct from private purchase consideration, legal costs, rent, build-out and financing.

## Usable official award lists

`award-candidates.json` and `.csv` preserve 97 named approval candidates from seven official announcements: **81 from the 2024 program, five legacy restricted awards, and 11 upgrades**. These are a research frame, not a verified current-license census. License-number joins and state approval remain unchecked in this subtask. News update dates are retained separately from known vote dates. The list is incomplete after March 2026.

| Official announcement | Named approvals captured | Cohort |
|---|---:|---|
| [February 13, 2025](https://www.boston.gov/news/city-boston-licensing-board-approved-37-new-liquor-licenses) | 37 | 31 ZIP, 2 Oak Square, 4 community |
| [July 3, 2025](https://www.boston.gov/news/city-boston-licensing-board-approves-21-new-liquor-licenses) | 21 | 20 ZIP, 1 Oak Square |
| [August 1, 2025](https://www.boston.gov/news/mayor-michelle-wu-celebrates-new-beer-and-wine-state-legislation-and-promotes-available-liquor) | 3 | Community |
| [October 24, 2025](https://www.boston.gov/news/city-boston-licensing-board-approves-four-new-liquor-licenses) | 4 | ZIP |
| [January 16, 2026](https://www.boston.gov/news/city-boston-licensing-board-approves-three-new-liquor-license-applications-and-finalizes-beer) | 3 | Citywide transferable; vote December 18, 2025 |
| [First five upgrades, updated February 27, 2026](https://www.boston.gov/news/licensing-board-approves-first-five-liquor-license-upgrades-beer-and-wine-licensees) | 5 | Upgrades |
| [March 9, 2026](https://www.boston.gov/news/city-boston-licensing-board-approves-new-liquor-license-applications-and-beer-and-wine) | 24 | 13 ZIP, 5 legacy 2006 restricted, 6 upgrades |

**Unresolved reconciliation:** the City's [FY27 budget presentation](https://www.boston.gov/sites/default/files/file/2026/05/EOI%20Cabinet%20FY27%20Budget%20Hearing%20Presentation.pdf), PDF page 52, reports 75 new licenses under the 2024 program and 31 upgrades. This differs from the 81 program approvals named across announcements. Different stages, reporting dates, withdrawals, or revisions may explain it; none is established here. Do not present 81 as licenses issued or open businesses, or 75 as a September total.

Restricted recipients must receive the same ownership research as other licensees. The first list includes Smoke Shop BBQ, Stoked Pizza and bb.q Chicken; the second includes Chilacates Cantina; March includes Nan Xiang Express. These brand names are research leads, not proof of common ownership or PE. The city specifically links direct transferable award recipient Ama to Pearl & Law Hospitality Group. A franchise brand's global scale cannot substitute for the local franchisee's ownership and size.

## What is and is not known about prices

The first-upgrades announcement attributes the phrase “With liquor licenses costing upwards of $600,000” to Councilor Gabriela Coletta Zapata. This is an official's market claim, not a transaction-level price observation. No documented completed Boston license-only sale price was established by this subtask.

The prior saved ABCC [transfer application analysis](../../../follow-up/evidence/sales/report-license-sales.md) identifies the correct evidence path: completed transfer application, purchase-and-sale agreement, asset allocation, funding schedule, promissory note/security agreement, and final approval/issuance. The blank form collects business-asset and real-estate prices plus financing, without a dedicated license-only price field. A business acquisition amount cannot be substituted for a license price.

## A concrete test rather than a correlation claim

Start with annual snapshots and a dated event ledger, ideally covering 2014–2026: legal license holder, venue, operating parent, controlling owner, capital sponsor, license class/statutory basis, geographic restrictions, acquisition route, seller/buyer, board/state approvals, opening/closing dates, license-only consideration, and evidence dates. Preserve legal-entity identifiers and a separate license number. Parent ownership can change without changing the licensee, while a DBA change can occur without ownership changing.

Keep three independent ownership dimensions:

1. **Capital:** disclosed PE control; disclosed PE minority investment; public-company control; other institutional/private capital; founder/family ownership documented; unresolved. Bank or supplier debt, wealthy individuals and a restaurant group's size do not by themselves establish PE. Record sponsor and investment/exit dates; do not convert no evidence into no PE.
2. **Scale:** verified operating venues controlled by the operator, with actual count/date and consistently chosen bands (one, 2–5, 6–19, 20+). Keep Boston footprint separate from total footprint. Franchised brand units and unrelated managed concessions require distinct fields.
3. **License acquisition:** documented private transfer; direct transferable award; 2024 ZIP/Oak award; legacy restricted; upgrade; other statutory program; unresolved. Retain price as missing where unknown.

For the descriptive result, report PE-backed and group-owned shares by cohort with full denominators and unresolved counts. Show both license-weighted share and distinct operator count. Compute top-five/top-ten operator share only after parent matching; several LLCs may belong to one operator, while a single food-hall license may support several independent businesses. Capacity-weighted shares can be supplemental, not a substitute for license counts.

For change over time, classify seller and buyer at each transaction date. Report independent-to-group, group-to-group, group-to-independent and unresolved transitions, plus net licensed-location changes by parent and neighborhood. Stock, membership-interest and beneficial-ownership transactions need their own ledger alongside license transfers. Do not infer consolidation from legal-name changes alone.

The useful first comparison is new 2024 restricted entrants against contemporaneous private-transfer entrants **within comparable neighborhoods and business types**, then prior cohorts in the same areas. Analyze 2026 upgrades separately; current beer/wine holders are a selected survivor group. Test whether independent entry rises and buyer concentration falls after alternative license access expands. With enough history, a difference-in-differences or matched event study can examine eligible versus comparable noneligible areas, but only after checking pre-policy trends, migration across ZIPs and spillovers into license prices. ZIP eligibility is not random; avoid claiming the design automatically identifies causation.

Important confounders are neighborhood rents and redevelopment, venue capacity/build-out cost, tourist/office traffic, cuisine and business model, pandemic exits, opening vintage, prior license ownership, operator experience, credit access, sponsor acquisitions unrelated to licenses, and the timing of the 2026 upgrades. Award-selection criteria also matter: the [January 23, 2025 chair's statement](https://www.boston.gov/sites/default/files/file/2025/01/Voting%20Minutes%201-23-25.pdf), PDF pages 10–12, explicitly considers readiness, longevity, track record and multi-concept premises and notes that early applicants overwhelmingly already held beer/wine licenses.

Evidence against the hypothesis would include similar concentration growth in low-cost cohorts, concentration predating license-price changes, no shift toward independent entry when alternative access expands, or transactions driven chiefly by real estate and nonlicense assets. Evidence supporting the mechanism would combine transaction prices, financing/denial evidence, dated ownership changes and a comparable change in entry after access improves. Current ownership shares alone cannot establish that mechanism.
