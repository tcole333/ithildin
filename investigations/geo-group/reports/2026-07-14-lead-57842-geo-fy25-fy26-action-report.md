# GEO FY2025-FY2026 DHS action forensics

**Lead:** #57842  
**Profile:** `geo-group`  
**Analysis run:** timeline-analysis #99  
**Coverage:** federal fiscal 2025 and fiscal 2026 actions through July 9, 2026  
**Primary denominator:** canonical 14-UEI DHS ledger; 215 exact-matched action rows

## Bottom line

The apparent acceleration is real at the obligation-action level but is not mainly an option-exercise or deobligation artifact. FY2025 net DHS obligations in the 14-UEI GEO universe were **$811,725,043.26**; ICE accounted for **$811,728,540.32**, while the small CBP slice was net negative. FY2026 through July 9 was **$648,483,130.88**, including **$648,450,369.52** at ICE.

On an equal elapsed-fiscal-year basis, net obligations increased from **$518,218,915.31** through July 9 of FY2025 to **$648,483,130.88** through July 9 of FY2026: **+$130,264,215.57**, or **25.1369%**. The portfolio did not move uniformly. New ISAP V skip-tracing funding, North Lake, Adelanto, Delaney Hall, Tacoma, and a GEO Transport task increased, while the FY2025 ISAP IV slice, South Texas, and Montgomery declined.

Official USAspending transaction action types are decisive. Funding-only actions plus initial new/base task actions represented **98.3474%** of FY2025 net obligations and **85.6478%** of FY2026-to-date net obligations. Across the ICE subset, the only explicit FY2025 option exercise was a **$11,894,500** Tacoma modification; no FY2026 ICE action through July 9 was coded `EXERCISE AN OPTION`. Two small CBP option actions bring the full DHS option count to three.

Fiscal timing still matters. September supplied **25.4681%** of FY2025 net obligations, including **16.1476%** in the final five calendar days. But fiscal-year-end timing is not sufficient by itself: **$262,845,644.26**, or **40.5324%** of FY2026-to-date net obligations, landed from January 21 through January 28 across seven facility/service categories.

These are procurement-mechanics findings. They do not establish that policy preference, lobbying, political relationships, improper influence, occupancy, or recognized service revenue caused any action.

## Denominator and exact join

The starting ledger contains 1,416 unique DHS actions across the corrected 14-UEI recipient set. This pass selected all 141 FY2025 rows and all 74 FY2026 rows through July 9. Every one of the 215 rows matched exactly and uniquely to USAspending's award-scoped transaction-history endpoint on PIID, action date, modification number, and action obligation rounded to cents. There were no unmatched or ambiguous rows.

The action-type denominator is:

| Official USAspending action type | Rows |
|---|---:|
| `FUNDING ONLY ACTION` | 140 |
| New/initial action type not populated | 26 |
| `CLOSE OUT` | 19 |
| `OTHER ADMINISTRATIVE ACTION` | 19 |
| `CHANGE ORDER` | 7 |
| `EXERCISE AN OPTION` | 3 |
| `SUPPLEMENTAL AGREEMENT FOR WORK WITHIN SCOPE` | 1 |
| **Total** | **215** |

The 26 rows with no populated action type are not silently called options. Each is modification `0` or is marked as a non-modification in the canonical ledger, and the matrix classifies it conservatively as a new/base/successor task action. The source value remains blank and visible.

## Measures that must remain separate

| Measure | Meaning here | Not equivalent to |
|---|---|---|
| Action obligation | Legal commitment or deobligation on the transaction action date | Outlay, invoice, guaranteed value, recognized revenue |
| Task cumulative obligation | Current award-level stock after all modifications | FY action flow or cash paid during the action period |
| Task outlay | Current cumulative USAspending cash-disbursement snapshot | Transaction-level or service-period outlay |
| Parent IDV value | Current base/all-options authority at the vehicle level | Task obligation or money received by GEO |
| Invoice | Contractor billing for units/services | Not present in the reviewed transaction data |
| Recognized revenue | GEO accounting recognition as services are performed | A federal action or outlay; GEO says timing may differ from invoicing |

The distinction is concrete. The Aurora parent IDV `70CDCR22D00000001` reports **$482,389,108.10** in current base-and-all-options value and **$0** parent obligation, while task order `70CDCR25FR0000111` reports **$66,893,395** in current obligations and **$36,399,063.73** in current outlays. The parent value is procurement authority; the task carries the funded action and cash-disbursement snapshots.

The same pattern appears across the 17 parent vehicles. Large values such as the Adelanto/Los Angeles IDV's **$2.147 billion** and the ISAP V IDIQ's **$1.028 billion** must not be added to task actions. They are repeated authority/value snapshots, not the FY2025-FY2026 flow.

## Fiscal timing

FY2025 increased **8.5532%** from FY2024's **$747,767,056.09** to **$811,725,043.26**. The year-end concentration is material:

| FY2025 timing slice | Net obligations | Share of FY2025 net |
|---|---:|---:|
| September 2025 | $206,730,750.11 | 25.4681% |
| September 26-30 | $131,073,892.51 | 16.1476% |

The final-five-day cluster included **$59.741 million** for ISAP IV, the **$21.966 million** ISAP V base task, **$15.128 million** at South Texas, **$11.895 million** for the Tacoma option/extension, and two Montgomery actions totaling **$21.336 million**. This is a mixed funding/rollover cluster, not one option action.

FY2026 shows a different timing signature. January alone supplied **$292,981,099.85**. Ten actions from January 21-28 supplied **$262,845,644.26**:

| Facility/service | Major January 21-28 actions |
|---|---:|
| B.I. ISAP V skip tracing | $76,011,425.00 |
| North Lake | $46,978,632.00 |
| Broward | $30,402,635.00 |
| Montgomery | $28,642,428.00 |
| Adelanto | $51,156,200.00 across three actions |
| Mesa Verde / Golden State | $15,715,124.26 |
| Desert View | $13,939,200.00 across two actions |

Because this concentration occurred eight months before fiscal year-end and the same-elapsed total is 25.1369% higher, September batching cannot by itself explain the FY2026 result. The action dates still do not establish service dates or occupancy.

## Action-mechanism result

| Fiscal period | Net obligations | Funding-only + initial task | Share | Explicit options | Gross deobligations |
|---|---:|---:|---:|---:|---:|
| FY2025 | $811,725,043.26 | $798,310,346.93 | 98.3474% | $12,227,962.46 DHS / $11,894,500 ICE | $7,062,337.49 |
| FY2026 through July 9 | $648,483,130.88 | $555,411,391.80 | 85.6478% | $348,904.40 DHS / $0 ICE | $3,004,649.21 |

Gross deobligations were only **0.8625%** of FY2025 gross positive obligations and **0.4612%** of FY2026 gross positives. They principally reflect closeouts and returns of unneeded balances, including Tacoma, Aurora, South Texas, Montgomery, and small CBP detention orders. They reduce net totals; they do not manufacture the positive acceleration.

The lower FY2026 funding/new-task share is mainly explained by one **$46.979 million** North Lake change order, **$32.579 million** of administrative actions, and South Texas's **$15.951 million** supplemental agreement within scope. Those classifications remain the official action types; the matrix separately flags literal term, rate, capacity, and closeout language.

## Facility and program decomposition

### B.I. / ISAP

FY2025 included **$168,359,626.96** net on ISAP IV and **$21,982,428** on the September 30 ISAP V base task and first modification. FY2026 contains **$86,361,425** in three ISAP V skip-tracing additions and **$1,624,500** on the separate nationwide skip-tracing task.

The largest FY2026 action—**$76,011,425** on January 27—was officially coded `FUNDING ONLY ACTION` and refers to Attachment 4 pricing schedule item 42. The public pre-award pricing schedule reviewed under lead #57838 contains 39 items, not the post-award item 42. The record therefore proves the funding action and program label, but not the undisclosed unit, quantity, unit price, scope-change approval, invoice amount, or recognized revenue.

### North Lake

North Lake rose from **$7,001,000** in the FY2025 same-elapsed activation slice to **$63,078,003.31** in FY2026 through July 9. The FY2026 amount includes the **$46,978,632** change order for continued support, **$1 million** of later funding, **$14.75 million** of continued-support funding, and **$349,371.31** finalizing undefinitized-period costs. A zero-dollar modification extended performance. These are compatible with activation/continuation and definitization mechanics, not proof of occupied beds or revenue timing.

### Adelanto and Desert View

Adelanto's same-elapsed net rose from **$64,869,918.16** to **$118,826,200**. FY2026 includes a new successor task and multiple funding additions. Desert View declined by **$2,565,295.82** on the same comparison while moving to a successor task. Literal descriptions reference operating charge, daily occupancy, transportation, guard services, expansion, and other direct costs, but the transaction data do not supply quantities, occupancy, rates, or invoices.

### Tacoma / Northwest

Tacoma/Northwest recorded **$79,671,252.41** in FY2025 and **$77,290,881.99** in FY2026 through July 9. The September 26, 2025 **$11,894,500** action was the only ICE action in scope coded `EXERCISE AN OPTION`; its text also says it extends the task term and funds detention, transportation, fuel, expansion, remote post, and overtime beds. The later FY2026 portfolio includes a new sole-source parent/task chain and substantial funding, while older orders produced closeout deobligations. An option exercise is therefore one part of the Tacoma chronology, not the portfolio-wide explanation.

### Aurora / Denver

Aurora's FY2026-to-date net was **$58,995,070.98**. A new task began with **$6.103 million** late in FY2025; FY2026 added **$43.876 million** and **$16.915 million**, then deobligated **$1.795 million** on the predecessor closeout. A zero-dollar modification made administrative corrections to the performance period and maximum beds. The records distinguish successor funding, administration, and closeout; they do not reveal monthly bed utilization or task-period revenue.

### South Texas

South Texas recorded **$82,355,559.83** in FY2025 and **$26,113,951.16** in FY2026 through July 9. FY2025 included a new task, emergency-bed incorporation, and September funding. FY2026 included a **$529,091.27** predecessor closeout/deobligation and a **$15,950,642.43** supplemental agreement within scope. This is a negative same-elapsed contributor, contrary to a claim that every detention site accelerated.

### Other contributors

Same-elapsed positive contributors also included Delaney Hall (**+$30.040 million**), Tacoma (**+$23.212 million**), GEO Transport's Salt Lake City task (**+$10.384 million**), Mesa/Golden/Central Valley (**+$5.500 million**), Broward (**+$2.961 million**), and Aurora (**+$2.060 million**). Montgomery declined **$13.586 million** and the ISAP IV slice disappeared after its vehicle end, offsetting the new ISAP V work. Positive facility contribution shares exceed 100% of the net change because negative offsets are retained rather than hidden.

## Options, rates, corrections, and closeouts

The three explicit DHS option actions were:

1. May 16, 2025: CBP RGV/La Villa detention space, **$333,462.46**.
2. September 26, 2025: ICE Tacoma, **$11,894,500**.
3. June 30, 2026: CBP RGV/La Villa option year 2, **$348,904.40**.

Rate and equitable-adjustment language appears separately from option coding. Examples include the ISAP IV wage-determination equitable adjustment, Montgomery Service Contract Act wage adjustment, CBP daily/CBA rate changes, Rio Grande guard-rate update, and Delaney Hall's approved equitable adjustment. Zero-dollar actions can change rates, beds, terms, or administration without themselves adding an obligation.

Closeouts likewise must be read as task-level cleanup. The largest was Tacoma's **$4,867,824.31** FY2025 deobligation. Aurora's **$1,795,324.02** FY2026 closeout was the largest in that year. These actions return or remove prior obligation authority; they are not negative invoices or evidence of a performance penalty unless the source says so.

## ACH and novelty decision

The companion ACH compares three explanations: cross-facility operational funding/new-task mechanics; fiscal-year-end batching alone; and option/deobligation/correction artifacts. The first is least inconsistent as a bounded descriptive explanation. It is not a finding about political motive or underlying service demand.

No new database hypothesis was created. The surviving mechanism is directly measured by official action types and exact transaction joins rather than an unexplained correlation. One nonduplicate follow-up, lead **#62587**, requests the missing ISAP V Attachment 4/item 42 and P00002-P00004 acquisition files to test whether the **$86.361 million** skip-tracing addition was priced and approved as existing-scope work, a post-award scope addition, or another documented vehicle mechanism.

Existing leads already cover the other decisive gaps: #62481 for the customer-revenue/invoice ledger, #60206 for Adelanto/Desert View/Aurora/Tacoma rates and invoices, and #60208 for South Texas/Folkston guarantee and remedy records.

## Finding-ready audited statements

Across the 215 exact-matched FY2025-FY2026 rows, USAspending coded 140 actions as FUNDING ONLY ACTION, 26 initial/base actions had no populated action type, three were EXERCISE AN OPTION, 19 were CLOSE OUT, 19 were OTHER ADMINISTRATIVE ACTION, seven were CHANGE ORDER, and one was SUPPLEMENTAL AGREEMENT FOR WORK WITHIN SCOPE.

Funding-only actions plus new/base task actions account for $798,310,346.93, or 98.3474%, of FY2025 net obligations and $555,411,391.80, or 85.6478%, of FY2026-through-July-9 net obligations. Within ICE, the only explicit option exercise in FY2025 was Tacoma modification P00008 for $11,894,500; no FY2026 ICE action through July 9 was coded EXERCISE AN OPTION.

Net obligations rose from $518,218,915.31 in the FY2025 same-elapsed window through July 9 to $648,483,130.88 in FY2026 through July 9, a $130,264,215.57 or 25.1369% increase.

Ten actions from January 21 through January 28, 2026 totaled $262,845,644.26, or 40.5324% of FY2026-to-date net obligations, across ISAP V skip tracing, North Lake, Broward, Montgomery, Adelanto, Mesa Verde/Golden State, and Desert View.

Gross deobligations were $7,062,337.49 in FY2025 and $3,004,649.21 in FY2026 through July 9, equal to 0.8625% and 0.4612% of gross positive obligations, respectively.

## Durable outputs

- `2026-07-14-lead-57842-geo-fy25-fy26-action-matrix.csv`
- `2026-07-14-lead-57842-geo-fy25-fy26-action-calculations.json`
- `2026-07-14-lead-57842-geo-fy25-fy26-source-manifest.json`
- `2026-07-14-lead-57842-geo-fy25-fy26-action-ach.json`
- `2026-07-14-lead-57842-geo-fy25-fy26-action-novelty.json`
- `investigations/geo-group/sources/2026-07-14-lead-57842/` — durable raw USAspending transaction, task-award, and parent-IDV snapshots
- `scripts/build_geo_fy25_fy26_action_matrix.py` — offline deterministic rebuild from those snapshots
- Verified findings **#12875-#12877**; follow-up lead **#62587**

Primary transaction documentation: [USAspending transaction-history endpoint](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/transactions.md) and [USAspending API](https://api.usaspending.gov/). Corporate metric boundary: [GEO 2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-20251231.htm). The attempted SAM contract cross-check returned the documented daily-limit response and was not used as evidence.
