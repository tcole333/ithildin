---
agent: pursue-lead
target: GEO performance failures and contract consequences
skill: pursue-lead, analyze-contract
status: blocked
findings_added: 18
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_id: 57970
profile: geo-group
thread_id: 113
workdir: /tmp/osint-hibLY9QR
ledger: /tmp/osint-hibLY9QR/performance-financial-consequence-ledger.md
infra_request: 150
---

# Lead 57970 report

## Outcome

Primary records support a narrower and better-documented conclusion than a blanket claim that GEO performance failures had no consequences. Folkston is the clearest GEO example: DHS OIG said ICE tried to impose staffing penalties in 2019 and 2021, did not enforce them, and continued full contract funding. A non-GEO comparator at Torrance shows ICE publicly tied the same type of staffing discrepancy to a proposed 25% billing reduction and a guaranteed-minimum cut. For B.I./ISAP and Golden State, public records show remedy authority, oversight findings, corrective responses, current closure status, and subsequent awards, but do not disclose the invoice-level or contract-modification consequences needed for a closed financial ledger.

The lead is blocked on infrastructure request 150 rather than completed. The remaining stop condition requires ICE contract-administration/FOIA records, not additional public-web repetition.

## Key discoveries

1. **Folkston — documented attempted penalties that were not enforced.** OIG-22-47 found the contract required 95% staffing and ICE used discrepancy reports in 2019 and 2021 to attempt penalties. OIG concluded Folkston continued to receive full contract funding without consequence. ICE later said every post was being covered through overtime at the vendor's expense; Oversight.gov now marks the staffing recommendation closed, but the public closure page does not provide the penalty decision, invoices, deductions, or closeout evidence. Findings 12425-12427.

2. **Torrance comparator — material disconfirmation of a broad “ICE never imposes financial remedies” theory.** For a non-GEO CoreCivic facility, OIG-22-75 says ICE was assessing a 25% monthly billing penalty until staffing compliance and cut the guaranteed minimum from 714 to 505. Canonical finding 12428.

3. **B.I./ISAP — remedy authority and credits are documented; quantified consequences are not.** GAO-22-104529 says the ISAP IV contract permitted withholdings or deductions for unsatisfactory performance and B.I. credits billing discrepancies regardless of who caused them. GAO's recommendation requiring ICE to document B.I.'s resolution of case-file audit findings remains open after September 2024 evidence; a separate legal-orientation monitoring recommendation closed in June 2024. ICE later awarded ISAP V after full-and-open competition with two offers and a $1.028 billion potential value. Findings 12417-12420, 12430, 12434.

4. **Golden State — oversight closure plus continued awards, but no public post-OIG minimum.** OIG-24-23 found roughly $25.3 million paid for unused guaranteed beds and ICE promised a new operationally appropriate minimum. Oversight.gov now marks recommendation 7 closed. FY2025 and FY2026 Mesa Verde/Golden State tasks show $66.19 million and $41.17 million obligated, respectively; the public records do not state Golden State's revised minimum, rates, effective date, or savings. Parent IDIQ 70CDCR20D00000008 has a $1.686 billion ceiling and runs through 2034. Seed finding 12398 and new findings 12421-12424 and 12433.

5. **USAspending transaction descriptions did not reveal a performance penalty.** Seven negative actions across four ISAP and five California detention tasks were labeled accounting corrections, deobligations, or excess-fund closeouts. This is a negative transaction-description result only: invoice offsets, payment deductions, credits, and CPARS consequences may not appear in obligation actions. Finding 12429.

6. **Subaward/exclusion negatives are bounded.** Nine reviewed USAspending task records showed zero subawards; HigherGov returned zero B.I. partnership records; the SAM Exclusions API returned zero exact-name results for B.I. Incorporated. None proves the absence of subcontractors across IGSAs/affiliates or exclusions under aliases. Findings 12431-12432.

## Findings added

- 12417 — ISAP IV withhold/deduct authority.
- 12418 — B.I. billing-discrepancy credit practice.
- 12419 — GAO case-file-audit recommendation remains open.
- 12420 — ISAP V successor IDIQ and first task.
- 12421 — Golden State operational-readiness/minimum response.
- 12422 — Golden recommendation 7 currently closed without disclosed terms.
- 12423 — FY2025 Golden/Mesa task obligation.
- 12424 — FY2026 Golden/Mesa task obligation.
- 12425 — Folkston attempted penalties not enforced/full funding.
- 12426 — Folkston vendor-expense overtime/current closure.
- 12427 — Folkston P00022 GEO subcontract and 2027 period.
- 12428 — canonical Torrance comparator covering both the 25% monthly billing-penalty assessment and guaranteed-minimum reduction.
- 12429 — negative USAspending actions lacked performance-penalty descriptions.
- 12430 — ISAP task-order obligation series.
- 12431 — bounded subaward/partnership negative results.
- 12432 — bounded SAM exact-name exclusions negative.
- 12433 — California detention IDIQ ceiling/term/competition.
- 12434 — GAO legal-orientation recommendation closed.

## Audit consolidation

Finding 12440 duplicated the Torrance billing-penalty portion of finding 12428. The audit trail records **12428 supersedes 12440**, and 12440 is retracted as a duplicate rather than deleted. The active-finding count for this workstream is therefore 18: findings 12417–12434.

## Negative results and limitations

- No public CPARS evaluations were located. FAR 42.1503(d) restricts completed evaluation release during the source-selection-use period; this is an access limitation, not a claim that an evaluation does not exist.
- No public cure/show-cause notices, monthly QASP files, invoice-level deductions, payment offsets, or case-audit closure files were located for ISAP IV/V.
- No public OIG-24-23 recommendation 7 closure package, revised Golden State guaranteed minimum, effective date, rate schedule, or calculated savings was located.
- No public Folkston penalty calculation, waiver/non-enforcement decision, invoices, or OIG recommendation 12 closeout package was located; signed P00022 is not a remedy document.
- Exact-name USAspending searches for Charlton/Charlton County did not yield a directly reported Folkston federal award. This likely reflects IGSA reporting structure and is not evidence of no contract.
- USAspending `subaward_count = 0` and HigherGov's zero partnership result do not rule out vendors, subcontractors, or IGSA pass-throughs.
- SAM's zero exact-name B.I. result does not cover all affiliates, officers, former names, or historical exclusions.
- Golden and Folkston Oversight.gov reports show $0 “questioned costs” and $0 “funds put to better use.” Torrance shows that those report-level fields can coexist with contract remedies, so they are not coded as proof of no deductions or modifications.

## Sources checked

- GAO-22-104529 PDF and current recommendations 9 and 10.
- DHS OIG OIG-24-23 and current Oversight.gov report/recommendation pages.
- DHS OIG OIG-22-47 and current Oversight.gov report/recommendation pages.
- ICE FOIA signed Folkston P00022.
- DHS OIG OIG-22-75 Torrance comparator.
- USAspending award/detail and current transaction APIs for four ISAP and five California detention tasks, ISAP V, and California IDIQ.
- HigherGov B.I. award/partnership records.
- SAM Exclusions exact-name query and local SAM bulk entity confirmation.
- Acquisition.gov FAR 42.1503(d).

The source searches were logged in `search_log`. Raw transaction responses and downloaded PDFs remain in `/tmp/osint-hibLY9QR/`.

## Exact blocker / FOIA scope

Infrastructure request 150 requests:

- **ISAP:** QASPs, monthly QA and case-file audit closure records, discrepancy/cure/show-cause notices, invoice adjustments/payment deductions, releasable CPARS equivalents, and ISAP V evaluation records excluding protected proposals for IDIQs 70CDCR20D00000011 and 70CDCR25D00000062 and the listed tasks.
- **Golden:** OIG-24-23 recommendation 7 closure package, operational-readiness/housing analysis, revised guaranteed minimum and rate terms, signed modifications, invoices, and deductions for IDIQ 70CDCR20D00000008 and FY2024-FY2026 tasks.
- **Folkston:** 2019/2021 discrepancy reports, proposed penalty calculations, non-enforcement decisions/waivers, staffing files, invoices/deductions, OIG-22-47 recommendation 12 closeout, and modifications P00023 onward for EROIGSA-17-0002.

## Learnings

- [Methodology] Keep “no public remedy record found” separate from “no remedy occurred.” USAspending obligation actions do not expose invoice credits, payment offsets, QASP determinations, CPARS effects, or guaranteed-minimum terms reliably enough to collapse those categories.
- [Surprise] The non-GEO Torrance comparator disclosed both a contemplated 25% billing penalty and a guaranteed-minimum reduction for persistent staffing failure, while the Folkston report documented attempted penalties that ICE did not enforce. Comparator selection materially changes how non-enforcement can be evaluated.
- [Source quality] Oversight.gov's current recommendation status is useful for closure state but insufficient for the underlying financial terms: a recommendation can be closed while the public page omits the revised minimum, effective date, invoices, or savings calculation.
- [Process gap] Contract-performance consequence work needs a standard ICE FOIA package covering discrepancy reports, contracting-officer determinations, QASP files, invoice deductions/credits, signed modifications, and OIG closure evidence; otherwise task continuation and negative obligation actions are easy to overinterpret.

## Repository friction logged

- Papercut 770: relevant GAO/DHS OIG/Oversight/ICE/SAM source labels are absent from the finding source registry, producing warnings despite complete evidence references.
- Papercut 773: `infra_requests.related_lead_id` still references `leads_old_backup`; this caused a valid `--related-lead 57970` insertion to fail. The lead ID is therefore preserved in request 150's description.
