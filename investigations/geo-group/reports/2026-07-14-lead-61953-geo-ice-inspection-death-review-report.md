# GEO-linked ICE inspections and death reviews: complete linked-denominator review

**Lead:** 61953  
**Profile / thread:** `geo-group` / 113  
**Review date:** 2026-07-14  
**Scope:** all artifacts linked by finding #57703's inspection index, plus all 23 current death-report alias hits and the previously indexed Gonzalez-Gadba full death review

## Result

The review covers all 78 indexed inspection events, their 138 artifact associations, and 24 death-review/report records. Those associations resolve to 161 official ICE PDF URLs and 160 distinct SHA-256 content hashes. One pair of Karnes URLs carries identical content; both indexed event associations remain in the matrix, and the content duplication is disclosed rather than silently discarded. All downloads succeeded. Sixty-six image-only or partially image-only documents required Apple Vision OCR.

The main inspection result is a measurement distinction, not a claim that the inspections were uniformly adverse. Of the 78 events:

| Inspection outcome/control | Events |
|---|---:|
| `Meets Standards`, `Meets Standard`, or `Acceptable`, with separately stated deficient components | 42 |
| Same compliant-grade family, with an explicit zero-component statement | 12 |
| Same compliant-grade family, with component status not stated or ambiguous | 4 |
| Karnes monthly report saying no area of noncompliance was identified | 16 |
| Pre-occupancy SIS rating `Not Selected`, with conditional action-plan language | 2 |
| Deep-dive recommendations with `Issue(s): None` | 1 |
| One stated Personal Hygiene noncompliance with mitigation | 1 |
| **Total** | **78** |

Thus, 43 events contain a nonzero deficient-component/noncompliance count: 42 also carry a compliant overall grade, and one is the Karnes Personal Hygiene noncompliance. The matrix never converts `Meets Standards` into zero deficient components. It also preserves 29 explicit zero/no-finding controls: 12 explicit zero-component inspections, 16 Karnes no-noncompliance reports, and the one deep-dive no-issue record. Four additional compliant-grade inspections leave component status unstated or ambiguous and retain blank component counts.

## Component and repeat-deficiency patterns

Across the indexed events, the most frequently named deficient standards were Visitation (14 events), Staff-Detainee Communication (10), Significant Self-Harm and Suicide Prevention and Intervention (9), Food Service (8), Special Management Units (7), Grievance System (7), and Medical Care (7). These are event counts within this linked denominator, not counts of unique components, affected people, adjudicated violations, or all ICE inspections ever conducted.

Twelve events contain explicit repeat-deficiency language. Examples that show why grade and component fields must remain separate include:

- Mesa Verde, June 28, 2018: `Meets Standards`, alongside seven deficient components in six standards; one Food Service component was identified as repeat. Finding #12846.
- South Texas, February 27, 2020: `Meets Standards`, alongside two component deficiencies; both Staff-Detainee Communication and Grievance System were described as repeat deficiencies.
- Denver, January 27, 2021: `Meets Standards`, alongside nine deficient components in three standards; the source identifies repeat components in Hold Rooms and Grievance System.
- Northwest, May 12, 2022: `Meets Standards`, alongside seven deficient components in five standards; Staff-Detainee Communication was identified as repeat. Finding #12847.

The records also contain genuine compliant controls. Mesa Verde's June 2022 inspection, for example, says the team identified no deficient components; that explicit zero is numeric `0` in the matrix. Karnes monthly `no areas of noncompliance` statements remain a different control class because they do not report component counts. Events 013, 018, and 063 state a compliant overall grade and zero standards rated Does Not Meet but do not state a component count. South Louisiana event 042 says `No components were rated Does Not Meet Standards`, which is not treated as equivalent to zero deficient components because other records can list deficient components without rating the overall standard Does Not Meet. All four are classified as component status not stated or ambiguous, with blank component counts.

## Conditional readiness and corrective language

Golden State Annex (October 16, 2020) and Desert View Annex (October 29, 2020) are pre-occupancy records, not ordinary compliant grades. Each SIS lists `Recommended Rating: Not Selected`; each cover letter says the facility will comply if it completes action plans and other promised procedures and policy revisions. Findings #12848 and #12849 preserve both clauses and do not treat the condition as proof of completion.

The Karnes June 7, 2021 monthly inspection is the one event in this denominator that expressly identifies an area of noncompliance: Personal Hygiene, because the center was not providing hair-care services. The stated mitigation was a request-based process compliant with the source's wording, `current COVD protocols`. Finding #12850 preserves the typo and does not assert that mitigation was completed.

No literal UCAP reference appears in the 138 linked inspection artifacts. Six events contain narrower action-plan, mitigation, or corrective-action language: the two pre-occupancy records; Denver's statement that incidents are reviewed and corrective action is implemented when warranted; Karnes's hair-care mitigation; Folkston's statement that corrective action began promptly; and Adelanto's recommendation to document corrective action and provide remedial camera/use-of-force training. The absence of `UCAP` in this linked set is a bounded coverage result, not proof that no UCAP existed elsewhere.

## Death reports and the Gonzalez-Gadba full review

The 24 death records are a separate evidence class. Twenty-three are public Detainee Death Reports that principally provide custody/transfer and medical timelines. They do not state a detention-standards grade or adjudicate facility compliance. The matrix therefore records `not stated`; it does not convert silence into either a deficiency or a clean inspection.

Death location is kept separate from prior GEO custody. Six records describe pronouncement or cessation of resuscitation at a GEO-linked facility; 18 describe death at a hospital or other medical setting after a custody or treatment transfer. Ten reports state a cause, manner, or preliminary cause of death; one says an autopsy was pending; the remaining 13 provide a pronouncement or terminal-event statement without a cause determination. Those classifications reproduce what the public reports state and make no medical or custodial causation inference.

The 2017 Gonzalez-Gadba record is different: it is a full ERAU review. It says Gonzalez-Gadba died at Victor Valley Global Medical Center while detained at Adelanto; the introductory summary records hypoxic encephalopathy and hanging, with manner of death suicide. The review enumerates nine PBNDS 2011 deficiencies:

1. Medical Care — translation and language access.
2. Medical Care — psychotropic-medication informed consent.
3. Medical Care — medication-refusal counseling and documentation.
4. Sexual Abuse and Assault Prevention and Intervention — prompt and effective intervention.
5. Special Management Units — administrative-segregation order.
6. Special Management Units — status-review interview and documentation.
7. Special Management Units — 30-minute personal observation and logging.
8. Custody Classification System — disciplinary-infraction scoring.
9. Funds and Personal Property — currency documentation.

The same report says the health-services administrator initiated corrective actions before ERAU's review and that, after the death, the Security Chief required 20-minute segregation rounds to help avoid exceeding the 30-minute standard. Finding #12851 records the nine areas and those two response clauses as a high-confidence paraphrase.

The report's causation disclaimer controls all use of those deficiencies: `Their inclusion in the report should not be construed in any way as indicating the deficiency contributed to the death of the detainee.` That exact language remains separately preserved in finding #12806 and is repeated in #12851's evidence. Neither the chronology, the deficiencies, nor the corrective actions are treated here as proof of causation.

## Award-period and remedy controls

Each row carries a period-aware award/vehicle routing label. Direct ICE IDIQs, city/county/parish IGSAs, and historical arrangements remain distinct. The label is a routing aid, not proof that a particular task order paid for the inspected building, caused an outcome, or imposed a remedy.

No linked inspection or death artifact states an applied payment reduction, award modification, CPARS consequence, or other financial remedy. Generic inspection boilerplate about possible sanctions is not recoded as an applied sanction. Any direct payment/remedy evidence belongs with completed lead #57784 or a nonduplicative follow-up.

## Audit and limitations

- Every one of the 102 matrix rows has at least one evidence quotation, official URL, and SHA-256 hash.
- Every stored quotation was normalized and tested as an exact substring of one of that row's linked source texts.
- Counts for South Texas event 029 and Adelanto event 067 were manually regression-checked after the parser initially missed `found two` and spelled-out `three` formulations.
- Only explicit no-deficiency statements, such as event 076's `identified no deficient components`, are recorded as numeric zero; event 042 remains ambiguous with blank counts, and area-level Karnes negatives remain categorically separate.
- Representative pages for Mesa Verde 2018, Golden State 2020, Karnes June 2021, Northwest 2022, and Gonzalez-Gadba were rendered and visually compared with extracted text.
- ICE inspection records and death reports are official primary records, but they are not equivalent to independent OIG findings, court holdings, contract-payment records, or a complete PACER/ICE universe.

## Durable artifacts and database imports

- `investigations/geo-group/reports/2026-07-14-lead-61953-geo-ice-inspection-death-coverage.csv`
- `investigations/geo-group/reports/2026-07-14-lead-61953-geo-ice-inspection-death-source-manifest.json`
- `investigations/geo-group/reports/2026-07-14-lead-61953-geo-ice-inspection-death-review-report.md`
- Verified findings: #12846–#12851.
