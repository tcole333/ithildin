# Tier 2 timeline analysis: GEO household-reportable trades and DHS milestones

**Analysis date:** 2026-07-14  
**Profile / thread:** `geo-group` / 111, Corporate Structure, Governance & Finance  
**Analysis run:** #108 (`timeline-analysis`)  
**Assessor:** `agent:timeline-analysis:run-108`  
**Scope:** verified public-record findings and the completed lead #59356 package only; no external queries and no HigherGov use

## Bottom line

The verified record does **not** distinguish hypothesis #351 (active positioning around detention expansion) from hypothesis #352 (routine portfolio management unrelated to procurement). Both have **zero inconsistent findings** in the verified-only matrix. The formal ACH verdict is therefore an exact tie on inconsistency, not a finding that routine management is favored.

The two new findings are neutral to both hypotheses. Finding #12948 shows that every annual GEO trade occurred amid broad Investment Account #7 activity and that the March 4, 2026 GEO row appeared among 204 same-report, same-day transactions. That context makes an isolated-GEO narrative incomplete, but it does not establish a discretionary manager, predetermined allocation, routine motive, owner identity, control, or absence of knowledge. Finding #12957 shows that DHS-action proximity was no greater for GEO trade dates than for matched same-weekday controls once the dense action background and base actions were separated. That invalidates broad action proximity as a causal discriminator; it does not test exact selection, awardee notice, access, or trade-instruction timing.

The February 24, 2025 purchase remains a **diagnostic records lead**, not diagnostic evidence. It occurred three days before GEO's Delaney Hall announcement and two days before the archived parent-award record's February 26 signed date, but Delaney had a public solicitation and two reported offers. The public record still lacks the proposal, evaluation, source-selection, contracting-officer approval, awardee-notice, and trade-instruction timestamps needed to compare the two sequences. No household member, beneficial owner, adviser, manager, or decision-maker is identified or inferred.

## Current-run ACH treatment

Run #108 added four history-preserving evaluations:

| Finding | #351 active positioning | #352 routine management | Current-run diagnosticity |
|---|---|---|---|
| #12948 broad same-account/same-report cadence | neutral | neutral | non-diagnostic |
| #12957 matched action-date controls | neutral | neutral | non-diagnostic |

The assessments are neutral rather than `consistent` with #352 because “broad portfolio activity” and “no excess action-date proximity” are compatible with routine management but do not observe the management mechanism. Treating compatibility as support would assume the very owner, controller, discretion, rationale, and instruction facts that remain missing.

The database-wide competition output counts prior asymmetric compatibility rows #12517 and #12543 as tool-level “diagnostic” because their labels differ across the pair. Finding #12517 is unverified and is excluded from this verified-only verdict. Finding #12543 is `neutral` to #351 and `consistent` with #352, but it creates no inconsistency against #351 and does not establish routine management. The tool's full output therefore shows more `consistent` labels for #352 while still producing the correct **0.0000 versus 0.0000 inconsistency tie**.

### Verified-only competition

| Measure | #351: active positioning | #352 H0: routine management |
|---|---:|---:|
| Verified evaluated findings | 10 | 10 |
| Consistent | 7 | 8 |
| Inconsistent | 0 | 0 |
| Neutral | 3 | 2 |
| Inconsistency ratio | 0.0000 | 0.0000 |

**Verdict:** tie. Neither hypothesis has less evidence against it. Additional consistency is not a ranking criterion and is not proof of #352.

The ten verified rows are #12447, #12514, #12515, #12516, #12531, #12532, #12542, #12543, #12948, and #12957. They collapse into three dependent source families rather than ten independent observations: OGE disclosures and cadence derivations; the USAspending-backed DHS action ledger and timing derivations; and GEO's SEC-filed activation statements.

## What the portfolio cadence does—and does not—show

Finding #12948 establishes broad portfolio context:

- fourteen 2025 GEO transactions were among **10,311** parsed Part 7 rows under Investment Account #7;
- every GEO date contained **16 to 616** same-day Account #7 rows, including the GEO row; and
- the March 4, 2026 PTR contained **204** normalized same-day rows, although that PTR does not display Account #7.

This cadence reduces the plausibility of describing the GEO rows as the only activity on those dates. It does not show how any security was selected inside a batch. A broad batch can arise from discretionary management, a predetermined rule, household-directed orders, tax or liquidity management, or another process. It can also contain one security selected for a different reason from the others. The public forms provide no order tickets, mandate, broker/adviser authority, owner category, rationale, or instruction time.

The cadence therefore does not materially discriminate between #351 and #352. It is neither evidence of a named household actor's discretion nor evidence that a household actor lacked knowledge. OGE's public forms intentionally omit family-member names and account numbers; that design boundary must not be filled by inference.

## What the matched controls do—and do not—show

The control comparison properly separates base actions from modifications and other transaction rows:

| Window / event class | GEO trade dates | Matched same-weekday observations | Difference in hit rate |
|---|---:|---:|---:|
| Any action, ±14 days | 15/15 (100.0%) | 198/198 (100.0%) | 0.0 pp |
| Any action, ±7 days | 14/15 (93.3%) | 191/198 (96.5%) | -3.2 pp |
| Base action, ±14 days | 7/15 (46.7%) | 128/198 (64.6%) | -17.9 pp |
| Base action, ±7 days | 5/15 (33.3%) | 86/198 (43.4%) | -10.1 pp |

There is no excess concentration of GEO trade dates near base actions in the reported windows. The result explains why “15 of 15 within fourteen days” is non-discriminating: virtually every matched observation and weekday was also near an action.

This is a descriptive control, not an independent causal sample. The 198 observations overlap; a date can be matched to more than one trade, and their event windows share actions. The event universe includes a symmetric +30-day buffer through April 3, 2026 after the last trade. The first trade is fully covered at ±7 days, but ±14- and ±30-day windows are left-censored before the January 20, 2025 action-universe start. These boundaries preclude inferential claims from the percentage differences.

Most importantly, an action date is not the relevant information event for #351. Base actions improve construct validity, but they still do not identify procurement initiation, evaluation, source selection, notice, or a person's access. The controls defeat broad proximity as evidence; they do not prove that trading was routine.

## Delaney Hall: live discriminator, unresolved chronology

The February 24 purchase is the only salient pre-announcement interval in the audited series:

- February 24: $15,001–$50,000 GEO purchase reported within 554 same-day Account #7 rows, including 409 purchases and 145 sales;
- February 26: archived USAspending parent record reports the Delaney IDIQ's signed date;
- February 27: GEO publicly announced the Delaney award; and
- March 6: the first base task action in the reconstructed ledger.

Official award fields describe a public, full-and-open negotiated solicitation with two offers. That public competition supplies an ordinary public-information pathway and means the later award was not an unannounced same-day procurement creation. It does not reveal when evaluators reached a decision, when the contracting officer approved it, when GEO learned it had won, or when the trade was instructed. The signed date is not a proxy for each of those events.

Accordingly, the three-day interval remains worth testing only through matched primary records. It does not identify who owned or controlled the reported position, whether that person had relevant access, or whether a trade instruction preceded a nonpublic milestone. Public solicitation plus missing internal timestamps leaves both explanations live.

## Key assumptions and premortem

The active-positioning theory would require at least four unobserved links: a covered owner or controller; discretion over the GEO row; relevant nonpublic access; and an instruction after access but before public release. The routine-management theory likewise requires unobserved control terms or a documented allocation/rebalancing process. Neither theory can borrow those facts from portfolio breadth.

Assume this analysis is wrong. The likeliest failure is that the broad batch obscures a GEO-specific instruction inserted into otherwise routine trading, or conversely that investigators overread the Delaney interval even though it arose from a documented standing mandate. The fastest corrective test is the same in both directions: compare a lawful identity-neutral OGE/account-control record and GEO order-instruction timestamp with ICE's selection, approval, and awardee-notice chronology. A gap on either side remains a gap; it is not evidence for the other theory.

## Novelty and database decision

No new hypothesis, lead, synthesis finding, tag, connection, or entity was created.

- Hypotheses #351/#352 already define the competing explanations and remain `investigating`.
- Verified findings #12948 and #12957 already capture the cadence and control facts; another synthesis finding would duplicate them.
- Completed lead #59356 and pending human action #69 already define the identity-neutral ownership/control, adviser-discretion, ethics-review, and instruction-record test without requesting family names or account numbers.
- Pending human action #50 and infra request #152 preserve contract-file and acquisition-file retrieval paths. The Tier 1 package identifies the Delaney selection/notice chronology as the analogous missing procurement layer; no duplicate lead was opened.
- The pattern does not pass the generate-hunches requirement for three independent contexts or a new mechanism. No hunch was recorded.

Run #108's only substantive database writes are four neutral hypothesis-evidence evaluations under assessor `agent:timeline-analysis:run-108` and the analysis-run completion record.

## Next best discriminator

Obtain, without identifying a spouse or dependent, two matched chronologies:

1. **Trade side:** covered-person category, whether a broker/adviser/trust had discretion, pre-clearance or ethics-review dates, and the GEO order/instruction timestamp.
2. **Procurement side:** proposal receipt, evaluation close, source-selection decision, contracting-officer approval, and awardee-notice timestamps for Delaney.

Only a chronological bridge between the actual controller's access and the actual instruction could materially support #351. A documented pre-existing discretionary mandate or predetermined allocation, paired with no relevant access, could materially weigh against it. Until then, the least-evidence-against verdict remains a tie.

## Artifacts

- Evidence matrix: `investigations/geo-group/reports/2026-07-14-tier2-household-trade-timeline-run108-evidence-matrix.csv`
- Full ACH matrix: `investigations/geo-group/reports/2026-07-14-tier2-household-trade-timeline-run108-ach.json`
- Competition output: `investigations/geo-group/reports/2026-07-14-tier2-household-trade-timeline-run108-compete.json`
- Novelty decision: `investigations/geo-group/reports/2026-07-14-tier2-household-trade-timeline-run108-novelty.json`
- Verified source/finding manifest: `investigations/geo-group/reports/2026-07-14-tier2-household-trade-timeline-run108-manifest.json`
- Required analysis exports: `investigations/geo-group/sources/2026-07-14-tier2-household-trade-timeline-run108/analysis-exports/`

