# GEO litigation–procurement timeline analysis

**Analysis run:** 83 (`timeline-analysis`)  
**Profile:** `geo-group`  
**As of:** 2026-07-13  
**Companion matrix:** [32-event litigation/action matrix](./2026-07-13-litigation-procurement-event-action-matrix.csv)

## Bottom line

The corrected DHS action ledger does not show a statistically discriminatory facility-level procurement response to the audited litigation milestones.

Twelve exact-date events at Tacoma/NWIPC, Aurora, or Adelanto had complete, equal 90-day pre/post exposure and were eligible for controlled testing. Six were adverse or mixed court milestones. Same-facility, same-federal-quarter permutation tests were run for action-count change, net-obligation change, and nearest-action proximity; Holm correction was applied separately to each metric across all 12 eligible events. No event had an adjusted p-value below 0.05 on any metric.

The observed directions were mixed. Some adverse decisions were followed by more actions but lower net obligations, some by fewer actions, and some by more actions and higher obligations. The 180-day robustness windows also lacked a common contraction pattern. The supported interpretation is therefore narrower than “litigation had no effect”: this action ledger alone does not distinguish a litigation response from ordinary annual task-order cycles, incremental funding, closeouts, deobligations, occupancy demand, or other contract administration.

Finding `#12619` records this controlled negative result at synthesis confidence. No new hypothesis pair or test lead was created because the timing result was non-discriminating. It was scored neutral against the existing performance-consequence competition, hypotheses `#335` and `#336`.

## Inputs and exclusions

The analysis used only the audited artifacts specified for this wave:

- [CourtListener litigation universe](./2026-07-13-courtlistener-litigation-universe.md) and its JSON inventory.
- [Lead 59489 litigation forensics](./2026-07-13-lead-59489-courtlistener-litigation-forensics.md) and [case/issue matrix](./2026-07-13-lead-59489-courtlistener-case-issue-matrix.md).
- [CourtListener contract, FCA, securities, employment, and tax report](../../../reports/geo-group-courtlistener-20260713/report.md).
- [Corrected DHS-wide procurement scan](./2026-07-13-dhs-wide-geo-procurement-scan.md) and [1,416-row action ledger](./2026-07-13-dhs-wide-geo-award-actions.csv).
- [Trump/DHS factual synthesis](./2026-07-13-trump-dhs-factual-synthesis.md), current profile findings, event timeline, and hypotheses.

All retracted QA rows identified by the source reports were excluded. The matrix cites only retained findings or the audited CourtListener universe for docket-filing dates.

## Facility attribution and null baselines

Case events were matched only where the action description or award description supported the same facility. A company-wide GEO action near a corporate case was not treated as a case-specific match.

| Facility match | Rows | Awards | Net action obligations | Supported action span | Mix |
|---|---:|---:|---:|---|---|
| Tacoma / NWIPC | 65 | 8 | $369,676,128.72 | 2017-05-31–2026-05-21 | 6 base task orders/calls; 43 ordinary positive modifications; 1 positive option/extension; 7 deobligations; 8 zero-dollar/option-zero modifications |
| Aurora CDF | 141 | 16 | $514,272,656.17 | 2015-01-15–2026-04-07 | 12 base task orders/calls; 98 positive modifications; 14 deobligations; 17 zero-dollar/option-zero modifications |
| Adelanto | 27 | 5 | $308,160,578.45 | 2020-06-30–2026-06-10 | 4 base task orders; 19 ordinary positive modifications; 2 positive option/extensions; 1 deobligation; 1 zero-dollar modification |
| Lawrenceville | 0 | 0 | $0.00 | No supported DHS match | Null: do not infer a DHS procurement response |

The Tacoma text-attributed series is especially weak before 2021: apart from a 2017 zero-dollar closeout, descriptions supporting Tacoma/NWIPC begin with 2021 task orders. Zero counts around the 2017 complaints therefore mean “no supportably attributed ledger action,” not “no ICE contracting activity.”

Of 32 event rows:

- 12 had a supported facility match and complete 90-day exposure;
- four had a facility match but were left- or right-censored for the 90-day comparison;
- five Lawrenceville events had no supported DHS action match; and
- 11 corporate, tax, month-precision, or pre-2015/BOP events were deliberately unmatched.

## Controls

### Equal-duration windows

For each eligible event:

- pre-window: `[event date − 90 days, event date)`;
- post-window: `[event date, event date + 90 days)`;
- rate: action count per equal 90-day exposure;
- size: mean positive obligation per positive action;
- mix: base task orders/calls, positive modifications, deobligations, zero-dollar modifications, and option/extension modifications; and
- robustness: the same summaries over equal 180-day windows when both sides were observable.

Negative obligations remain deobligations; they were not netted away or relabeled as award contractions. Base task orders under an existing parent vehicle remain distinct from modifications. Amounts are action obligations, not payments, outlays, ceilings, guaranteed minimums, or GEO revenue.

### Facility/quarter permutation

For each eligible exact-date event, every supportable pseudo-event date in the same federal fiscal quarter-of-year and the same facility series was used as a matched timing control, subject to full 90-day exposure. Two-sided empirical tests compared the absolute pre/post difference in action count and net obligations. A one-sided empirical test compared the observed nearest-action distance with the pseudo-date distances.

Holm family-wise correction was applied across the 12 eligible events for each of the three metrics. This prevents a dense action ledger from making at least one apparently close or asymmetric window look exceptional merely because many event dates were tested.

No count, net-obligation, or proximity test survived correction. This is a negative test result, not proof of independence or absence of nonpublic intervention.

## Adverse and mixed milestones

All amounts below are net action obligations inside equal 90-day windows. “Base −7” means a base task order occurred seven days before the legal event.

| Milestone | Nearest supported action | Pre 90 days | Post 90 days | Rate/size/mix observation | Adjusted result |
|---|---|---:|---:|---|---|
| Tacoma district judgment sequence, 2021-11-03 | Base task order `70CDCR22FR0000002`, −7 days, $11.166m | 2 actions; $16.683m | 4 actions; $10.694m | Post: 3 positive and 1 zero-dollar modification; mean positive size fell from $8.341m to $3.565m | Count, net, and proximity all non-significant |
| Tacoma Ninth Circuit merits judgment, 2025-01-16 | Positive modification on `70CDCR25FR0000004`, +8 days, $11.629m | 2; $19.090m | 6; $13.179m | Post: 4 positive modifications and 2 deobligations; mean positive size $4.540m versus $9.545m pre | All non-significant |
| Tacoma rehearing denial, 2025-08-13 | Positive modification, −20 days, $13.701m | 2; $13.698m | 1; $11.895m | Post action was an option/extension modification; lower rate and net, but no discriminatory deviation | All non-significant |
| Aurora class-certification affirmance, 2018-02-09 | Positive modification, +6 days, $779.31 | 3; $6.974m | 5; $19.177m | Post: 1 base task order and 4 positive modifications; mean positive size rose to $3.835m | All non-significant |
| Aurora partial-summary-judgment order, 2022-10-18 | Base task order `70CDCR23FR0000001`, −4 days, $5.554m | 7; $11.773m | 2; $1.784m | Post: 2 positive modifications. Raw count asymmetry was p=0.0494, but Holm-adjusted p=0.5923 | All non-significant after correction |
| Supreme Court *Menocal* appealability judgment, 2026-02-25 | Positive modification, −14 days, $43.876m | 2; $43.876m | 2; $15.119m | Post: 1 positive modification and 1 deobligation; rate unchanged | All non-significant |

The 180-day comparison also lacked a stable direction:

- Tacoma district judgment: post 8 actions/$21.782m versus pre 2/$16.683m.
- Tacoma appellate merits judgment: post 8/$34.989m versus pre 5/$25.710m.
- Tacoma rehearing denial: post 3/$29.027m versus pre 8/$41.926m.
- Aurora class certification: post 8/$20.301m versus pre 7/$16.720m.
- Aurora partial summary judgment: post 7/$19.352m versus pre 9/$22.703m.

These mixed rate and net directions are inconsistent with a simple cross-case rule that adverse milestones promptly contract facility obligations.

## Case-specific interpretation

### Nwauzor / State of Washington — Tacoma

The 2017 complaint windows contain no supportably attributed Tacoma actions, but the pre-2021 description coverage is too thin for that to establish a contraction. The November 2021 district judgment followed a new annual task order by seven days and was followed by incremental funding modifications. The January 2025 appellate merits judgment was followed by four positive modifications and two deobligations within 90 days. Rehearing denial was followed by an option/extension action.

The January 9, 2026 certiorari petition was followed by $38.248 million in two positive modifications within 90 days, but its raw net asymmetry did not survive Holm correction. The May 18 CVSG is right-censored: a new Tacoma task order appeared ten days before it and a $30.144 million modification three days after it. That proximity is descriptive only. The award sequence and dense incremental funding make a Court-response inference unsupported.

Result: observable incumbent facility activity continued through adverse merits, appellate, and pending Supreme Court milestones. The ledger does not show a statistically exceptional contraction or expansion attributable to those milestones.

### Menocal — Aurora

The 2014 complaint is left-censored by the ledger's 2015 start. Class-certification affirmance was followed by a base task order and positive modifications. The October 2022 partial-summary-judgment order occurred four days after a new annual task order; the post-window had fewer actions and lower net obligations, but the apparent count asymmetry failed multiple-comparison correction and the 180-day window still contained seven actions and $19.352 million.

The February 2026 Supreme Court judgment left action counts unchanged across the 90-day windows. The April 6 renewed GEO motion was followed one day later by a $1.795 million deobligation; its raw net asymmetry was p=0.0069 but Holm-adjusted p=0.0827. It was also a company-filed motion, not an adverse adjudication, and the action description/award sequence supports treating the deobligation as contract administration unless stronger records show otherwise.

Result: no controlled evidence of an Aurora contraction, relocation, or exceptional award acceleration tied to the legal milestones.

### Novoa — Adelanto

The 2017 complaint and 2022 stay each had zero supportably attributed Adelanto actions in their equal 90-day windows. The facility-attributed ledger is sparse before the December 2023 task-order series, so those null windows have low diagnostic value. Later records show continued Adelanto task orders under the Los Angeles AOR parent vehicle, including a 2026 Desert View Annex task order. The annex record shows an additional Adelanto-area instrument, not evidence that operations were relocated in response to the lawsuit.

The June 15, 2026 status report is right-censored and cannot support a symmetric test. A $35.4 million Adelanto modification occurred five days before it. No causal interpretation is warranted.

### Reid — Lawrenceville

The corrected DHS ledger contains no supportably matched Lawrenceville action. The 2024 complaint, 2025 mixed pleading order, 2026 partial federal dismissal, summary-judgment briefing, and scheduled settlement conference remain explicit null matches. This does not establish a contract loss; Lawrenceville is a Virginia correctional facility and the reviewed DHS direct-prime universe is not a general state-prison procurement ledger.

### Hartel, Zhang, tax matters, and GEO v. United States

*Hartel* and *Zhang* are corporate securities/derivative matters without a supported facility or award-family nexus. Their complaint, pleading, settlement, dismissal, and governance-reform dates remain in the matrix, but no company-wide DHS action was assigned to them.

The Texas sales-tax judgment and month-precision New Mexico payment disclosure likewise lack a supported award/facility match. The New Mexico event has no exact day and was not proximity-tested.

The 2011 Brooklyn reentry-center protest concerned BOP, predates the corrected DHS ledger, and ended after a TRO denial and GEO's voluntary dismissal. It is not evidence about ICE/CBP award continuity.

## Hypotheses, nulls, and leads

No new pair was registered. A new temporal hypothesis or lead would not be justified by a result in which all tested proximity and pre/post asymmetry signals are non-discriminating after correction.

Finding `#12619` was evaluated as neutral against the existing paired competition:

- `#335`: ICE contract design and monitoring may insulate GEO operations from proportional financial consequences.
- `#336` (H0): the oversight episodes are separate incidents handled through ordinary remedies and readiness purchasing.

The current ACH competition ranks H0 `#336` least inconsistent: 3 inconsistent of 23 evaluated findings, ratio 0.13, versus 4 of 23 and 0.17 for `#335`. This timing result moves neither hypothesis because action cadence and obligation amounts do not reveal CPARS, deductions, cure notices, occupancy needs, corrective-action closure, or acquisition rationale.

Existing leads already supply the bounded discriminatory tests:

- `#57784`: obtain inspection consequences, deductions, CPARS, cure records, and later renewals.
- `#57842`: explain GEO ICE obligation spikes, deobligations, option actions, capacity activations, and closeouts.
- `#59578`, `#59676`, and `#59678`: monitor the current *Menocal*, *Reid*, and *Novoa* merits/status records.

No duplicate lead was created. The parent investigation can run `auto_leads` after all visible-agent work is imported.

## Premortem and limitations

Assume the conclusion is wrong. The fastest way this analysis could have missed a real procurement response is facility attribution failure: older task-order descriptions may omit Tacoma, Aurora, or Adelanto even when the action belongs to the same operation. A second failure mode is measuring action obligations rather than occupancy, invoices, deductions, option decisions, or acquisition milestones. A third is event-date endogeneity: annual task orders cluster around fiscal/program-year schedules, while litigation dates are not random.

The fastest checks are to reconstruct each facility's full parent-IDV/task-order family without relying on description text; obtain QASPs, invoices, deductions, CPARS, cure/show-cause records, option-exercise files, occupancy, and acquisition plans; and compare the same consequence measures with non-GEO facilities. Until then, “no discriminatory action-ledger timing signal” is the supported conclusion—not “litigation had no procurement effect.”
