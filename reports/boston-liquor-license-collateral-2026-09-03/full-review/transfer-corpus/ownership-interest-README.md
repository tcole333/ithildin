# Ownership-interest changes in the retained Board archive

All 64 retained decision records for 2024–2026 through September 3, 2026 were reviewed for explicit stock, membership/ownership/beneficial-interest changes, updated stockholders, and corporate-structure conversions. The review covers 918 PDF pages plus the unpaginated October 1, 2025 HTML document. The original 307 transfer/pledge events and the frozen model benchmark were not changed.

## Results

`ownership-interest-events.json` and `.csv` contain **146 application decisions: 145 granted and 1 continued**. There are 53 decisions in 2024, 58 in 2025, and 35 in 2026. `ownership-interest-notices.json` separately retains five informational, participation, or required-application notices; none is counted as an approved ownership change.

Of the 146 decisions, **111 explicitly concern alcohol licenses**: 110 granted and one continued, covering **98 distinct Boston license numbers**. The other 35 records are tagged separately: 34 Common Victualler items without alcohol stated and one billiards-license item. Filter `license_scope == "explicit_alcohol"` for the alcohol subset.

**None of the 111 alcohol-license items identifies before/after equity holders or ownership percentages.** The generic phrase “change of Ownership Interest” establishes that the Board considered an ownership-change application, not who ultimately owned or controlled the business, whether a sponsor participated, or whether a transaction closed. Corporate-form conversions identify entity names, not shareholders. This ledger can identify records that warrant examination of the underlying applications; it does not itself establish concentration by parent or sponsor.

There are 14 corporate-structure action occurrences, including 12 items with explicit before/after entity conversions. Some repeat the same apparent conversion across licenses. Stock-interest changes, ownership-interest changes, and conversions can occur in the same item, so action totals overlap. No separate explicit share-issuance action was identified. Named percentage-bearing entries are confined to the separately tagged nonalcohol records.

## October 23, 2025 examples

The [official minutes](https://www.boston.gov/sites/default/files/file/2025/10/Voting%20Minutes%2010-23-25.docx_0.pdf) record:

| License | Entity | Page / item | Granted action |
|---|---|---|---|
| LB99259 | Tavern in the Square Causeway Street, LLC | 8 / 21 | Ownership-interest and officer/manager changes |
| LB98812 | Tavern in the Square South Station, LLC | 8 / 22 | Ownership-interest and officer/manager changes |
| LB99058 | James Associates, Inc. / The Broadway | 8 / 23 | Corporate structure to James Associates, LLC, plus ownership-interest change |
| LB99057 | JABC Corp. / The Playwright Bar | 9 / 24 | Corporate structure to JABC, LLC, plus ownership-interest change |

These items do not identify the incoming owners, percentages, sponsor, consideration, or closing. Any sponsor attribution must be independently supported by another source.

## Audit and use

Each event retains the voting date, license number, legal entity and DBA, source URL, physical PDF page, item number, action list, disposition, full source item, before/after parties when explicitly stated, entity-conversion names separately, and ambiguity notes. `board_granted_application` records only Board approval; `equity_change_completion_verified` is false because closing was not established. `ownership_subject_entity` and `ownership_subject_scope` preserve the November 6, 2025 Night Shift item’s explicit parent-company stock-interest change without treating the named manager as an owner.

Share quantities without percent signs remain quantities, not percentages. Incomplete before/after lists are not assumed to be complete capitalization tables. Manager, officer, attorney, and pledge-recipient names do not become owners without explicit equity language. A stock pledge alone, storage of inventory, shared premises, manager/officer changes alone, license transfers alone, and license-type conversions alone are excluded.

Repeated source occurrences are retained with notes: for example Mass. Bay Brewing’s same LB number across three pouring categories, Roche Bros. repeats, multiple Marriott/Whole Foods locations, and Fresh Boston’s continuance followed by a grant. Counts therefore describe decisions rather than distinct economic transactions.

`ownership-interest-coverage.json` inventories all 64 documents, including zero-event documents, and points to each year’s detailed candidate and exclusion audit. All broad keyword candidates were reviewed; source text, page bounds, event IDs, and party quotes were validated. Fourteen targeted page renders across the three year reviews checked conversions, percentage/quantity language, duplicate records, parent-company scope, and ownership notices. Extraction and merge scripts passed Ruff. Coverage remains bounded to the retained archive documents, not full corporate or license history.
