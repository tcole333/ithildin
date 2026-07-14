# Lead #59356 — GEO household-trade decision-maker and procurement-timing test

**Research date:** 2026-07-14  
**Profile / thread:** `geo-group` / 111  
**Competing hypotheses reviewed:** #351 and #352; neither was scored in this Tier 1 wave  
**Public-record scope:** OGE disclosures and guidance, GEO SEC filings, official SAM notice links, and the canonical USAspending-backed DHS action ledger

## Bottom line

The public record establishes a household-reportable GEO stock position and fifteen purchases or sales, but it does **not** establish who in the covered disclosure household beneficially owned the position, who directed any trade, whether an adviser or broker had discretion, or whether a decision maker possessed procurement information. The investigation did not assign or infer a household identity.

The strongest new diagnostic fact is portfolio context. All fourteen 2025 GEO transactions were entries within broad same-day **Investment Account #7** activity: the annual-report parser found between **16 and 616** Account #7 transaction rows on each GEO date, including the GEO row. The March 4, 2026 PTR contains **204 transaction rows on that date**, including GEO. This makes an isolated-GEO-trade narrative incomplete. It does not prove a discretionary mandate, automatic rebalancing, routine motive, or absence of knowledge.

The timing comparison is also non-discriminating. Within ±14 days of an action, the rate was **15/15 GEO trade dates, 198/198 matched same-weekday controls, and 292/293 weekdays**. Restricting the event set to base actions produced **7/15 trade dates, 128/198 matched controls, and 186/293 weekdays**. At ±7 days, the respective base-action rates were **5/15, 86/198, and 124/293**. Trade dates were not more concentrated near base actions than the controls. No causal or knowledge inference follows from proximity to this dense action stream.

One date remains worth exact-record follow-up: the February 24, 2025 purchase was three days before GEO publicly announced Delaney Hall. But Delaney was a public, full-and-open follow-on solicitation that received two offers, and the reviewed public record does not supply proposal receipt, evaluation, selection, awardee-notice, or trade-instruction timestamps. That gap prevents either hypothesis from being resolved.

## What the disclosures identify—and withhold

| Field | Public record | Evidentiary use |
|---|---|---|
| Public filer | Donald J. Trump, President | Identifies the filer/report, not the owner of every reported asset or transaction |
| Annual report | OGE received June 29, 2026; annual for calendar year 2025 | Disclosure/receipt date is not a trade date |
| PTR | Received May 8, 2026; official index dated May 14, 2026 | Reports a March 4, 2026 transaction and marks notification over 30 days |
| Security | `GEO GROUP INC NEW` / `GEO GROUP INC NEW REIT` | Direct issuer security exposure; not an option, fund holding, grant, vesting, or option expiration |
| Transaction fields | Purchase or sale, date, and categorical value range | Value bands are not exact consideration, share counts, proceeds, or cost basis |
| Annual account label | Investment Account #7 | Groups the annual rows; it does not identify the institution, account number, beneficial owner, or manager |
| Covered-person universe | Part 7 can include the filer, spouse, or dependent child | Household-member attribution remains unassigned |
| Public-form privacy rule | No account numbers, street addresses, or family members' names | The missing identity is an intentional form boundary, not evidence of one person or another |
| Management/control | Not stated | No public basis to name the person who instructed, approved, selected, or executed a GEO trade |

OGE's reviewer comment states that the filer paid late fees related to transactions not previously reported on 278-Ts. That statement is report-level. It does not identify GEO, a particular transaction, the covered owner, or the reason any specific row was late.

The official PAS index returned seventeen Trump transaction-report PDFs from August 2025 through July 2026. Exact-text screening found GEO only in the May 8, 2026 report. The archived OCR texts and URL ledger preserve this bounded negative. OCR can miss unreadable image content, so it is not treated as proof that no other report contains an unsearchable reference.

## Transaction and cadence reconstruction

The deterministic ledger preserves all fifteen rows, exact OGE source text, date, transaction type, value category, notification field, same-day context, nearest DHS action, nearest DHS base action, window counts, net action obligations, and official USAspending URLs. It deliberately keeps disclosure, ownership, transaction, and procurement fields separate.

The annual record contains ten GEO purchases and four sales during 2025. The PTR adds one purchase on March 4, 2026. Same-day Account #7 context was:

| GEO date | Type | Value band | Same-day rows in annual Account #7 |
|---|---|---:|---:|
| 2025-01-30 | Purchase | $15,001–$50,000 | 604 |
| 2025-02-03 | Purchase | $1,001–$15,000 | 616 |
| 2025-02-04 | Purchase | $1,001–$15,000 | 356 |
| 2025-02-05 | Purchase | $1,001–$15,000 | 296 |
| 2025-02-24 | Purchase | $15,001–$50,000 | 554 |
| 2025-03-27 | Sale | $1,001–$15,000 | 364 |
| 2025-04-28 | Purchase | $15,001–$50,000 | 415 |
| 2025-05-15 | Purchase | $15,001–$50,000 | 222 |
| 2025-06-30 | Sale | $1,001–$15,000 | 182 |
| 2025-07-31 | Purchase | $15,001–$50,000 | 238 |
| 2025-09-02 | Sale | $50,001–$100,000 | 177 |
| 2025-10-03 | Purchase | $15,001–$50,000 | 16 |
| 2025-10-16 | Sale | $15,001–$50,000 | 287 |
| 2025-11-24 | Purchase | $50,001–$100,000 | 220 |

The March 4, 2026 PTR does not show Account #7, so its 204 same-day rows are described only as same-report, same-day portfolio context. They are not assigned to an account. OCR was used only to normalize evident March 4 date variants; purchase/sale counts for those 204 rows were not inferred from degraded OCR.

The cadence is consistent with broad multi-security trading, but multiple mechanisms remain live: a discretionary manager, predetermined strategy, household-directed batch orders, or another portfolio process. The public forms do not distinguish them. Portfolio breadth is therefore diagnostic context, not proof of the null hypothesis.

## Controlled trade-to-procurement timing

### Method

- Observation dates run from January 20, 2025 through the last GEO trade on March 4, 2026.
- DHS/GEO action events extend through April 3, 2026 so the last trade and late-period controls receive a symmetric +30-day event window.
- The action universe begins at inauguration. The earliest trade is fully covered at ±7 days, but its ±14- and ±30-day windows are left-censored for pre-inauguration actions.
- A base action is a canonical ledger row with `is_modification == no`. Modifications, deobligations, closeouts, and zero-dollar actions remain in the broader all-action class.
- The 198 matched observations are the same weekdays one through eight weeks before and after each trade, excluding other trade dates and dates outside the observation interval. A calendar date matched to more than one trade remains a separate matched observation.
- Windows are descriptive and overlapping. They are not an independent statistical sample or causal test.

### Results

| Event set / window | GEO trade dates | Matched same-weekday controls | All weekdays |
|---|---:|---:|---:|
| Any action, ±1 day | 10/15 (66.7%) | 119/198 (60.1%) | 176/293 (60.1%) |
| Any action, ±3 days | 13/15 (86.7%) | 162/198 (81.8%) | 241/293 (82.3%) |
| Any action, ±7 days | 14/15 (93.3%) | 191/198 (96.5%) | 281/293 (95.9%) |
| Any action, ±14 days | 15/15 (100%) | 198/198 (100%) | 292/293 (99.7%) |
| Base action, ±1 day | 1/15 (6.7%) | 22/198 (11.1%) | 35/293 (11.9%) |
| Base action, ±3 days | 3/15 (20.0%) | 42/198 (21.2%) | 66/293 (22.5%) |
| Base action, ±7 days | 5/15 (33.3%) | 86/198 (43.4%) | 124/293 (42.3%) |
| Base action, ±14 days | 7/15 (46.7%) | 128/198 (64.6%) | 186/293 (63.5%) |

The familiar “all fifteen trades were within fourteen days” observation is mathematically true but not useful: virtually every date was. Base-action separation improves construct validity, and those comparisons do not show excess trade-date concentration.

The ledger also demonstrates why action labels matter. The February 5 same-day row nearest a GEO purchase was a **$4.87 million deobligation and closeout**; the November 24 same-day row was a **zero-dollar closeout modification**. Treating either as a new contract award would invert the record.

## Specific milestone tests

### Delaney Hall

The February 24 purchase was three days before GEO's February 27 announcement and ten days before the March 6 base task action. It was also one of 554 Account #7 rows that day. Official SAM links identify public presolicitation and solicitation pages for `70CDCR24R00000012`; the parent reports full-and-open negotiated competition and two offers.

The public record did not establish the exact dates for proposal receipt, evaluation, source selection, contracting-officer approval, notice to GEO, or trade instruction. The three-day pre-announcement interval is therefore a live document question, not evidence that a named person traded on nonpublic information. The March 4, 2026 purchase was fourteen days before a Delaney successor base task, but that task was placed under the existing public parent vehicle; GEO's 2025 Form 10-K had been public since February 25, 2026 and recapped Delaney and other ICE developments.

### North Lake

GEO publicly announced a North Lake letter contract on March 20, 2025, stating that the multi-year contract would be finalized later. GEO subsequently stated that the finalized two-year contract was effective July 18. The July 31 GEO purchase occurred after both the March announcement and the disclosed effective date, and one day before the USAspending action date for the successor task order whose period began July 21.

SAM notice `JA-20-0057` supplies an unusual-and-compelling-urgency authority under FAR 6.302-2. The public audit did not recover market research, signatures, the definitization file, or a price-negotiation memorandum. The timing sequence is consistent with already-public contract exposure and does not identify a nonpublic selection event around July 31.

### ISAP V

The October 3 purchase came three days after the September 30 ISAP V base award. Solicitation `70CDCR25R00000018` had been publicly posted, and the parent IDV reports full-and-open competition with two offers. GEO later announced the September 30 award in an SEC-filed release. Exact source-selection and notice timestamps remain unavailable, but the purchase was after—not before—the base action.

### Other nearby action rows

Most other nearest rows are incumbent modifications, rate/funding actions, deobligations, closeouts, calls, or task orders under existing vehicles. The May 17 base row nearest the May 15 purchase carried a $250 minimum obligation; it should not be described as a substantive $250 award expansion. Net obligations in the ledger are action deltas, not payments, invoices, recognized GEO revenue, market value changes, or profits on the disclosed trades.

## Resolution of the lead's falsifiers

The public record did not satisfy either falsifier:

- **Hypothesis #351 falsifier:** no public record established an independent discretionary manager or predetermined strategy, and no record established that the actual decision maker lacked relevant access.
- **Hypothesis #352 falsifier:** no public record named a decision maker with relevant government access who directed GEO-specific trades around a nonpublic milestone.

Dense portfolio cadence and non-discriminating timing reduce the evidentiary value of action-date proximity. They do not decide who owned or controlled the position and do not prove or disprove knowledge. Accordingly, this Tier 1 wave added no hypothesis evaluation to #351 or #352.

## Negative coverage and bounded gaps

- All seventeen official Trump PTRs returned by the OGE PAS index were archived as text and screened; only the May 8, 2026 report produced an exact GEO issuer hit.
- The public OGE annual/PTR forms, blank form, and guidance did not identify the covered owner, trade decision maker, broker, adviser, account number, share count, cost basis, or order/instruction time.
- The full GEO 2025 10-K and relevant 2025–2026 8-Ks were reviewed for contract timing and ownership/control terms. They are public company disclosures, not records of the disclosure household's ownership or instructions.
- The reviewed public procurement record did not supply proposal logs, evaluation chronology, source-selection decisions, awardee notice timestamps, or price analyses for the salient Delaney interval.
- Live SAM wrapper calls for Delaney and North Lake exited without output or the requested file; papercut #991 preserves the credential-free reproduction. Prior archived official SAM URLs and official USAspending fields were used. No HigherGov API or HigherGov source was used in this wave.
- No household member, adviser, broker, or investment manager was contacted, identified, or inferred.

Human action **#69** is a narrowly framed OGE FOIA request for identity-neutral filing-review, amendment, late-fee, ownership-category, discretionary-authority, pre-clearance/recusal, and instruction-date records. It expressly excludes family names, account numbers, addresses, and subject contact. Existing infra request **#152** remains the proper route for missing North Lake and other acquisition files; the Delaney selection/notice chronology should be added if comparative evaluation is pursued.

## Durable artifacts and reproducibility

Verified Tier 1 findings are **#12948** (same-day portfolio cadence) and **#12957** (controlled all-action/base-action comparison). Prior findings **#12514, #12515, #12516, and #12543** supplied the previously accepted holding, transaction, and unadjusted timing record. Human action **#69** preserves the lawful identity-neutral records request. Hypotheses **#351/#352** remain unscored.

- Evidence matrix: `investigations/geo-group/reports/2026-07-14-lead-59356-evidence-matrix.csv`
- Trade-to-action ledger: `investigations/geo-group/reports/2026-07-14-lead-59356-trade-to-action-ledger.csv`
- Matched controls: `investigations/geo-group/reports/2026-07-14-lead-59356-matched-same-weekday-controls.csv`
- Window summary: `investigations/geo-group/reports/2026-07-14-lead-59356-window-control-summary.csv`
- Build summary: `investigations/geo-group/reports/2026-07-14-lead-59356-build-summary.json`
- Source archive: `investigations/geo-group/sources/2026-07-14-lead-59356/`
- Rebuild: `uv run python scripts/build_geo_household_trades_lead.py --annual-text investigations/geo-group/sources/2026-07-14-lead-59356/oge/Donald-J-Trump-2026-278ANNUAL.txt --ptr-text investigations/geo-group/sources/2026-07-14-lead-59356/oge/Trump-Donald-J-05.08.2026-278T-2.txt --actions-csv investigations/geo-group/sources/2026-07-14-lead-59356/procurement/2026-07-13-dhs-wide-geo-award-actions.csv --output-dir /tmp/geo-household-build`

Every source artifact is hashed in the companion manifest. The build summary points only to durable repository inputs, not to the temporary research directory.
