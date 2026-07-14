# GEO-linked ICE facilities: oversight and corrective-action crosswalk

**Lead:** 57703  
**Profile:** `geo-group`  
**Research date:** 2026-07-14  
**Scope:** Primary DHS OIG, ICE Office of Detention Oversight (ODO), ICE detainee-death-review, and GAO records. Financial consequences are excluded and remain assigned to lead 57784.

## Result

This wave produced a quote-reviewed matrix of **31 adverse, compliant, corrective-action, causation-caveat, and systemwide oversight rows**. It also established a larger source denominator: **78 ICE inspection events with 138 linked artifacts** across 16 GEO-linked facility identities on ICE's 2018–2022 public inspection index, plus **23 current death-review reports containing GEO-facility timeline linkages** and one older, quote-reviewed Adelanto death review.

The most defensible conclusion is not that every report supports the same theory. The primary record is mixed:

- DHS OIG documented facility-specific noncompliance at Adelanto, South Texas, Folkston, Northwest, Mesa Verde, Golden State, and Denver/Aurora. Grievance or staff-detainee communication problems recur in several reports, but each inspection remains a separate observation tied to its own date and scope.
- The same OIG reports also recorded compliant domains. Mesa Verde complied with the voluntary-work, facility-condition, and grievance standards reviewed; Golden State complied in several use-of-force, legal, work-program, and segregation domains; and Denver complied in recreation, use of force, library, and voluntary work.
- ICE ODO's July 2024 Adelanto follow-up reported no findings. That is meaningful later-period counterevidence, not a retroactive negation of OIG-18-86.
- ICE ODO's August 2024 Denver and Tacoma follow-ups remained mixed. Denver had six deficiencies in four standards and compliance in 14; Tacoma had 11 deficiencies in six standards, compliance in 14, and two repeat deficiencies after a prior corrective-action plan.
- GAO found systemwide weaknesses in inspection consistency, trend analysis, acquisition documentation, and contract-officer independence. Those findings place GEO facilities within a broader oversight system; they cannot be attributed to a specific GEO facility without the underlying facility or contract records.

## Quote-reviewed facility crosswalk

| Facility identity | Primary records reviewed | Balanced result |
|---|---|---|
| Adelanto ICE Processing Center | OIG-18-86; OIG-19-47; ICE-ODO-2024-002-386; ICE-DDR-GONZALEZ-2017 | Serious 2018 PBNDS violations and a 2019 aggregate segregation observation; 2024 ODO follow-up reported no findings; 2017 death review expressly disclaimed inferring causation from a listed deficiency. |
| Denver Contract Detention Facility / Aurora | OIG-19-47; OIG-24-29; ICE-ODO-2024-002-330 | OIG identified communication and grievance deficiencies but compliant recreation, use-of-force, library, and work-program domains; later ODO found 14 compliant standards and six deficiencies in four others, plus a staffing area of concern. |
| Folkston main and annex | OIG-22-47 | Noncompliance across conditions, medical care, grievances, segregation, communication, and property, alongside compliant legal-services, work-program, and classification findings. |
| Golden State Annex | OIG-24-23 | Classification, grievance, request, segregation-recreation, and condition problems alongside several compliant domains. Payment consequences are excluded here. |
| Mesa Verde ICE Processing Center | OIG-24-03 | Use-of-force reporting deficiency and optometry delay context, alongside compliant work-program, condition, and grievance findings. |
| Northwest / Tacoma | OIG-20-45; OIG-23-26; ICE-ODO-OPR-201200440; ICE-ODO-2024-005-389 | Recurrent grievance/language and later follow-up deficiencies; also extensive compliant domains in 2012, 2023, and 2024. Two August 2024 items were explicitly repeat deficiencies. |
| South Texas ICE Processing Center | OIG-22-40 | Grievance, segregation, COVID-19, and communication noncompliance alongside compliant legal-services, work-program, classification, and medical findings. Payment consequences are excluded here. |
| Karnes County Residential Center | DHS OIG investigative summary, 2015-01-07 | OIG did not substantiate the specified sexual-misconduct allegations and reported PREA reporting compliance. This is not a general facility-compliance determination. |

Every quoted proposition, locator, response, recommendation status, identity note, and source URL is in the [oversight matrix](./2026-07-14-lead-57703-geo-ice-oversight-matrix.csv). The [source manifest](./2026-07-14-lead-57703-geo-ice-oversight-source-manifest.json) records primary-file hashes and visual-QA coverage.

## Corrective-action and recommendation status

Corrective-action language is not treated as proof of durable remediation. The records use several materially different states:

- OIG reports often classified recommendations as resolved/open, resolved/closed, or unresolved/open at issuance.
- Public Oversight.gov pages checked on 2026-07-14 displayed open recommendations for South Texas (2, 4), Northwest (1, 2, 3, 7, 8), Mesa Verde (1), Golden State (1, 2, 3), and Denver (1, 4, 6, 7, 8, 13). An absent recommendation was not treated as proof of closure.
- ICE ODO's Tacoma report said the January 2024 uniform corrective-action plan “may not have been sufficient to prevent the repeat deficiencies.” This is direct counterevidence to equating plan completion with sustained correction.

The matrix preserves agency responses separately from observations. It does not infer a contractual remedy, deduction, nonrenewal, or payment consequence. Those questions remain in lead 57784.

## Source denominator and residual review

The [ICE inspection index](./2026-07-14-lead-57703-geo-ice-inspection-index.json) normalizes public facility aliases to 16 canonical GEO-linked identities and preserves each event's date, contract channel, award or IGSA where known, and every linked cover letter, summary form, or inspection report. It contains 78 events and 138 links. Inclusion means only that the official ICE index contains an inspection record for a facility in the declared GEO identity set.

The [death-review index](./2026-07-14-lead-57703-geo-ice-death-review-index.csv) contains 23 current reports with a GEO-facility mention and the older Gonzalez-Gadba review. Except for the separately quote-reviewed Gonzalez-Gadba row, these are labeled **timeline linkage only**. A transfer through a GEO facility does not establish that the death occurred there, that the facility was deficient, or that any facility condition caused the death.

The remaining 138 inspection artifacts and 23 current death reviews have not all received document-by-document quote extraction. They belong in a bounded follow-on lead, rather than being silently treated as completed findings.

## Contract and identity controls

- Facility, award, and procurement-chain counts are not interchangeable. Folkston and D. Ray James share the Charlton IGSA chain; Pine Prairie and South Louisiana share the Evangeline Parish chain.
- Historical and current names must be time-bounded. Adelanto's historical City D-IGSA period must not be merged into later direct-contract periods. Aurora's historical `HSCEDM11D00003` and newer `70CDCR20D00000001` periods remain distinct.
- Karnes County Residential Center records are not automatically assigned to the later Karnes County Immigration Processing Center award `70CDCR24DIG000018`.
- A systemic GAO sample or recommendation is not a GEO-specific finding unless the underlying report identifies a GEO facility or award.
- OIG inspection observations, OIG investigative allegations, adjudicated court findings, and ICE death-review conclusions are different evidence classes.

## Database imports

Findings 12789–12806 were imported under lead 57703 and thread 113. Their summaries were narrowed during audit so that each attached quote supports the full proposition. The batch includes both adverse and compliant findings and retains the Gonzalez-Gadba causation disclaimer.

## Primary sources

- [DHS OIG-18-86, Adelanto](https://www.oig.dhs.gov/sites/default/files/assets/Mga/2018/oig-18-86-sep18.pdf)
- [DHS OIG-19-47, four facilities](https://www.oig.dhs.gov/sites/default/files/assets/2019-06/OIG-19-47-Jun19.pdf)
- [DHS OIG-20-45, FY2019 unannounced inspections](https://www.oig.dhs.gov/sites/default/files/assets/2020-07/OIG-20-45-Jul20.pdf)
- [DHS OIG-22-40, South Texas](https://www.oig.dhs.gov/sites/default/files/assets/2022-05/OIG-22-40-Apr22.pdf)
- [DHS OIG-22-47, Folkston](https://www.oig.dhs.gov/sites/default/files/assets/2022-07/OIG-22-47-July22.pdf)
- [DHS OIG-23-26, Northwest](https://www.oig.dhs.gov/sites/default/files/assets/2023-05/OIG-23-26-May23.pdf)
- [DHS OIG-24-03, Mesa Verde](https://www.oig.dhs.gov/sites/default/files/assets/2023-11/OIG-24-03-Nov23.pdf)
- [DHS OIG-24-23, Golden State](https://www.oig.dhs.gov/sites/default/files/assets/2024-04/OIG-24-23-Apr24.pdf)
- [DHS OIG-24-29, Denver/Aurora](https://www.oig.dhs.gov/sites/default/files/assets/2024-06/OIG-24-29-Jun24.pdf)
- [ICE facility inspections index](https://www.ice.gov/detain/facility-inspections)
- [ICE detainee death reporting](https://www.ice.gov/detain/detainee-death-reporting)
- [GAO-15-153](https://www.gao.gov/products/gao-15-153), [GAO-20-596](https://www.gao.gov/products/gao-20-596), [GAO-21-149](https://www.gao.gov/products/gao-21-149), and [GAO-25-107580](https://www.gao.gov/products/gao-25-107580)

