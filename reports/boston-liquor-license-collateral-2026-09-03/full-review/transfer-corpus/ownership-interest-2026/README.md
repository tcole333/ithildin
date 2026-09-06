# Boston Board ownership-interest extraction: 2026

All **16 archived decision documents through September 3, 2026**, totaling **280 PDF pages**, were audited offline. The broad scan produced **63 candidate items**, each reviewed in full. Four documents contain no qualifying events; coverage retains them explicitly.

`events.json` contains **36 events**:

| Event action | Count |
|---|---:|
| Ownership-interest change | 17 |
| Stock-interest change | 11 |
| Stock transfer | 1 |
| Corporate-structure change | 6 |
| Required ownership-change application notice | 1 |

The first four categories are **35 granted application dispositions**. The remaining event is the May 21 enforcement directive that Brewed Intentions submit ownership- and manager-change applications within 30 days. Its July 16 grant is recorded separately. A Board grant does not establish that a transaction closed or that beneficial control changed.

There are **29 events with alcohol explicitly stated** (28 grants and the directive) and **7 Common Victualler events with no alcohol stated** (all grants). The six corporate-structure-only grants cover Ishtiaq H. Naqvi converting from sole proprietor to Shaboo Bee, Inc. and five Whole Foods license items changing from Inc. to LLC. They do not establish changed beneficial ownership.

Only three items disclose owner percentages: Zarhan, Pho Que and China Bros. Owner arrays preserve only stated interests. The prior named China Bros managers/officers are not labeled owners; the unmentioned prior 50% of Zarhan is not invented. Generic interest changes leave owner arrays empty. Manager changes, officer appointments, corporate name changes alone, stock pledges alone, premises conversions and ordinary license transfers are excluded.

`candidates.json` preserves all 63 candidate texts and inclusion/exclusion decisions. `coverage.json` lists every source, page count, source hash, candidate count, event count and visual checks. Source URLs, page ranges, item numbers, full item text and complete disposition wording are retained in each event. Event IDs use the document and item position, because printed item numbering restarts within documents.

Validation checked all keyword occurrences against candidate spans, event-ID uniqueness, required fields, owner quotations, totals, and source coverage. Six rendered pages confirmed owner percentages, a source punctuation defect, the Naqvi conditions and a Whole Foods approval crossing a page break. Ruff passed for `extract.py`. The parser also handles source item headings such as `4.Tatte` without treating decimal rule numbers as item headings.

Rebuild offline from the repository root with:

```bash
uv run python reports/boston-liquor-license-collateral-2026-09-03/full-review/transfer-corpus/ownership-interest-2026/extract.py
```

The original transfer corpus and benchmark files were not modified.
