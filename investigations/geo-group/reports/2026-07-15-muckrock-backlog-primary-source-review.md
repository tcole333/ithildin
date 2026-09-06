# MuckRock backlog primary-source review

**Research date:** 2026-07-15  
**Profile:** `geo-group`  
**Requests reviewed:** `38021`, `117845`, `73576`  
**Outcome:** three priority releases processed; no database imports; quote-level candidates and negative controls prepared below

## Executive result

This pass completed the three strongest unreviewed items identified in the July 15 MuckRock searches.

1. The request `38021` workbook contains 367 ICE intake/case rows dated 2013-2018, not 367 adjudicated incidents. Facility labels, exact duplicates, and at least six obvious facility/synopsis conflicts make raw facility totals unsafe. The workbook nevertheless contains several novel, explicitly GEO-attributed allegation records with exact row-level provenance. It contains no disposition or substantiation field.
2. The request `117845` release is a four-year ICE Office of Detention Oversight (ODO) annual-report compilation. It permits defensible annual normalization and exposes several facility-specific GEO facts, but it does not provide a complete facility-by-facility deficiency or repeat-deficiency matrix. The strongest novel item is a FY2021 Rio Grande medical-care Area of Concern involving a positive tuberculosis skin test that was not followed by further treatment or documentation of latent TB.
3. The request `73576` production confirms the four Family Case Management Program base/task-order pairs beyond the previously imported Washington/Baltimore pair: Los Angeles, New York, Miami, and Chicago. The mapping and first-page order totals were visually verified.

No findings were inserted. Allegation-only workbook rows should not be imported as established misconduct. The inspection and contract facts below are import-ready, but leaving the actual insert to the coordinating pass avoids mixing reviewed candidate selection with the ongoing concurrent GEO database work.

## Method and evidence handling

- Read both July 15 source-discovery reports and the MuckRock/DocumentCloud corpus playbook before review.
- Preserved every original in `datasets/muckrock/`; decrypted, extracted, and rendered only temporary sidecars.
- Parsed the request `38021` XLS row by row with `xlrd` and retained the original sheet-row numbering, including the header as row 1.
- Opened the public request `117845` delivery chain, used its separately supplied public credential in memory, and decrypted only a temporary copy of the nested annual-report PDF.
- Extracted native text by page and rendered every PDF page cited as a proposed finding or contract mapping for visual verification.
- Queried `investigation.db` under profile `geo-group` for exact identifiers and distinctive quote fragments. Request descriptions were used only for prioritization, never as evidence.
- Canonical page numbers below are the one-based PDF pages printed by the local render, not the reports' internal pagination.

## Request 38021: ICE Texas sexual-abuse case workbook

### What the workbook actually is

The release `FOIA_2018-ICFO-45499_-_Responsive_Records.xls` contains one worksheet, `Sheet 1`, with 367 data rows and 17 columns. Every row has both `Case Is` and `Status` set to `Closed`. Incident dates run from 2013-01-01 through 2018-06-08; reported dates run from 2013-01-02 through 2018-06-08.

The useful distinction is:

- the workbook records referrals, management inquiries, information-only records, and ICE/IG investigations;
- a row can identify a reported allegation and still provide no investigative outcome;
- `Closed` must not be paraphrased as substantiated, unsubstantiated, charged, disciplined, or cleared;
- there is no disposition, finding, substantiation, prosecution, or discipline column.

### Row-level quality audit

The workbook has four exact duplicate groups when all 17 source fields are compared:

- rows `8`, `9`, and `10`;
- rows `36` and `37`;
- rows `271` and `272`; and
- rows `295` and `296`.

Additional rows share the same or near-identical synopsis without being byte-for-byte duplicates, including rows `12`/`13`, `15`/`16`, and `269`-`272`. Consequently, neither the 367-row total nor a facility-label subtotal is an incident count.

Facility-label matching produces 101 raw rows under six well-known GEO facility fields:

| Workbook facility field | Raw rows | Caution |
|---|---:|---|
| South Texas Detention Complex | 65 | includes at least three obvious records whose synopses identify Dilley or Central Texas instead |
| Joe Corley Detention Facility | 17 | includes at least two obvious records whose synopses identify Krome or IAH Secure Adult instead |
| Karnes County Residential Center | 11 | one row's synopsis identifies Karnes County Correctional Facility instead |
| Rio Grande Detention Center | 4 | facility label alone does not state operator |
| Karnes County Correctional Facility | 3 | distinct from the residential center |
| Val Verde Correctional Facility | 1 | facility label alone does not state operator |

At least these source-data conflicts were found during the row audit:

- row `85`: facility field says Joe Corley; synopsis says Krome Service Processing Center, Miami;
- row `174`: facility field says South Texas Detention Complex; synopsis says South Texas Family Residential Center, Dilley;
- row `182`: facility field says South Texas Detention Complex; synopsis says the CCA-operated South Texas Family Residential Center, Dilley;
- row `185`: facility field says South Texas Detention Complex; synopsis says Central Texas Detention Facility, San Antonio;
- row `268`: facility field says Joe Corley; synopsis says IAH Secure Adult Detention Facility, Livingston; and
- row `364`: facility field says Karnes County Residential Center; synopsis says Karnes County Correctional Facility.

The 101-row subtotal is therefore a search set, not a clean GEO incident denominator. Fifteen rows contain `GEO` in the synopsis, case summary, or topic, but several describe a GEO employee merely receiving a report or appear under a contradictory facility field. Explicit text still requires role-by-role reading.

### Strongest novel allegation records

These are proposed only as allegation-log findings. Each summary must preserve `alleged`, `reported`, or `possible`; confidence should not exceed `high` as a paraphrase unless the database finding quotes the workbook directly and makes clear that the quote is an intake record rather than an adjudicated conclusion.

#### South Texas: alleged forced oral sex by a kitchen contractor

> On February 17, 2014, the Joint Intake Center (JIC) Duty Agent received a telephone call from Immigration and Customs Enforcement (ICE) Supervisory Immigration Enforcement Agent (SIEA) (b)(6);(b)(7)(C), Enforcement and Removal Operations, San Antonio, CA (ERO/San Antonio), who reported detainee (b)(6);(b)(7)(C) at the South Texas Detention Center (STDC), in Pearsall, TX, alleged kitchen contractor (b)(6);(b)(7)(C) forced him to perform oral sex.

- Source fields: `Investigation IG`; `Criminal`; primary FD `0612 Detainee/Alien - Sexual Assault (Staff on Detainee)`; status `Closed`.
- Evidence: `MUCKROCK:38021:FOIA_2018-ICFO-45499_-_Responsive_Records:Sheet 1:row362`
- Novelty: no matching summary, detail, or distinctive phrase in the `geo-group` finding set.
- Limit: the row does not identify the contractor's company and gives no outcome.

#### South Texas: allegation against an unidentified GEO officer

> On December 21, 2016, the Joint Intake Center (JIC) received a referral from the Department of Homeland Security, Office of the Inspector General (DHS/OIG) regarding an allegation from (b)(6);(b)(7)(C), a detainee at South Texas Detention Center located in Pearsall, TX, who claims he was sexually assaulted by an unidentified GEO officer.

- Source fields: `Investigation ICE OPR`; `Criminal`; primary FD `0650 Detainee - Sexual Assault-Staff on Detainee`; status `Closed`.
- Evidence: `MUCKROCK:38021:FOIA_2018-ICFO-45499_-_Responsive_Records:Sheet 1:row226`
- Novelty: no matching GEO finding.
- Limit: no disposition is supplied.

#### Karnes residential center: allegation naming a GEO/GTI contractor

> On April 16, 2015, the Joint Intake Center (JIC) received information from Immigration and Customs Enforcement (ICE) Assistant Field Office Director (AFOD) (b)(6);(b)(7)(C), Enforcement and Removal Operations, San Antonio, TX, (ERO/San Antonio), who reported an allegation of sexual abuse from (b)(6);(b)(7)(C). Detainee (b)(6);(b)(7)(C) alleged she was sexual assaulted by GEO/GTI contractor (b)(6);(b)(7)(C).

- Source fields: `Investigation ICE OPR`; `Non-Criminal (S)`; primary FD `0612 Detainee/Alien - Sexual Assault (Staff on Detainee)`; status `Closed`.
- Evidence: `MUCKROCK:38021:FOIA_2018-ICFO-45499_-_Responsive_Records:Sheet 1:row150`
- Novelty: no matching GEO finding.
- Limit: the case summary supplies a more specific reported proposition, but the exact synopsis above remains the safer import quote; no disposition is supplied.

#### Joe Corley: possible employee-detainee relationship

> On October 8, 2014, the Joint Intake Center (JIC) Immigration and Customs Enforcement (ICE) Supervisory Detention and Deportation Officer (SDDO) (b)(6);(b)(7)(C), Enforcement and Removal Operations, Conroe, TX (ERO/Conroe), who reported a possible inappropriate relationship between GEO employee (b)(6);(b)(7)(C) and detainee (b)(6);(b)(7)(C) at the Joe Corley Detention Facility in Conroe, TX.

- Source fields: `Investigation ICE OPR`; `Non-Criminal (S)`; primary FD `0801 Conflict of Interest-Association with Known Criminals/Illegal Aliens`; secondary FD `0612 Detainee/Alien - Sexual Assault (Staff on Detainee)`; status `Closed`.
- Evidence: `MUCKROCK:38021:FOIA_2018-ICFO-45499_-_Responsive_Records:Sheet 1:row259`
- Novelty: no matching GEO finding.
- Limit: the synopsis calls the relationship only `possible` and supplies no disposition.

#### Joe Corley: assistant-warden harassment allegation

> On May 27, 2015, the Joint Intake Center (JIC) received an email from the Department of Homeland Security (DHS), Office of Inspector General (OIG) regarding an allegation of sexual harassment. Detainee (b)(6);(b)(7)(C) alleged that Assistant Warden (b)(6);(b)(7)(C) did sexually harass (b)(6);(b)(7)(C) while he entered the shower at the Joe Corley Detention Center, Conroe TX.

- Source fields: `Information Only`; `Criminal`; primary FD `0600 Detainee/Alien - Sexual Harassment (Staff-on-Detainee)`; status `Closed`.
- Evidence: `MUCKROCK:38021:FOIA_2018-ICFO-45499_-_Responsive_Records:Sheet 1:row275`
- Novelty: no matching GEO finding.
- Limit: this is explicitly an information-only allegation record, not an investigative conclusion.

### Useful supporting rows and duplicate control

- Row `22` records a September 2014 South Texas detainee allegation of feeling sexually assaulted while being escorted by a GEO contract officer.
- Row `53` records a July 2016 Pearsall allegation that an unidentified female GEO staff member touched a detainee's buttocks over clothing.
- Row `55` records an August 2016 La Salle/Jena allegation that an unidentified GEO staff member forcefully separated a detainee's buttocks during a strip search. The source's city/county labels are internally inconsistent, so location should be taken from the synopsis rather than the facility field.
- Row `158` records an August 2015 South Texas allegation that an unknown GEO contract officer stared at a detainee using the toilet.
- Row `220` records a March 2016 South Texas allegation that a GEO contract officer opened a shower door and watched a detainee.
- Row `281` explicitly says an OIG email reported an allegation against a DHS contractor `of the GEO Group` at West Texas Detention Facility; the operator attribution should be separately checked because the facility history and source fields may conflict.
- Row `364` appears potentially related to the Karnes allegation set covered by existing finding `12805`, whose OIG source concluded that it found no evidence to substantiate the allegations reviewed. Do not import row `364` as a novel misconduct finding without case-level linkage and the OIG disposition beside it.

## Request 117845: ICE ODO FY2018-FY2021 annual reports

### Normalized annual metrics

| Fiscal year | Inspections | Deficiencies | Repeat deficiencies | Areas of concern | Corrective actions initiated | Evidence |
|---|---:|---:|---:|---:|---:|---|
| 2018 | 33, including 2 follow-ups | 663 | 83 | 34 | 95 | `MUCKROCK:117845:2022-ICFO-14071:p3`, `p6`, `p11`-`p13` |
| 2019 | 48 | 1,216 | 80 | 105 | 175 | `MUCKROCK:117845:2022-ICFO-14071:p27`, `p29`, `p34`-`p36` |
| 2020 | 120 | 2,311 | 224 | 142 | 196 | `MUCKROCK:117845:2022-ICFO-14071:p55`-`p56`, `p63`-`p65` |
| 2021 | 211 inspections across 128 distinct facilities | 2,340 | 229 during full inspections; 283 during follow-ups | 188 | 76 | `MUCKROCK:117845:2022-ICFO-14071:p88`, `p95`-`p97` |

These figures are not a clean performance time series. Standards and inspection modes changed; FY2020 included COVID-19 contingency inspections; FY2021 was shaped by a twice-yearly congressional inspection mandate; and FY2021 separates full-inspection repeats from same-year follow-up repeats. The totals describe the annual ODO program, not GEO alone.

The reports do not publish a complete facility-level deficiency/repeat table. Their repeat-deficiency facility tables list only facilities with the most repeats. No GEO facility appears in the FY2020 top-five list or FY2021 full-inspection top-five list. Prairieland appears in the FY2021 follow-up top-five list with seven, but absence of another GEO facility from a `most repeat deficiencies` table does not mean zero repeats.

### Strongest novel GEO-specific candidates

#### Rio Grande: positive TB skin test without further treatment or latent-TB documentation

ODO listed this FY2021 Medical Care Area of Concern:

> Detainee skin tested for Tuberculosis (TB) upon arrival to the facility and the tuberculin skin test (TST) was positive at 15 mm. The facility's medical staff immediately conducted a chest x-ray, which was negative for active TB. The facility's medical staff did not offer the detainee any further treatment, nor did they document the diagnosis of a positive TST or Latent TB in the detainee's medical file.

- Facility: Rio Grande Detention Center.
- Evidence: `MUCKROCK:117845:2022-ICFO-14071:p115`
- Claim type: `direct_quote`; eligible for `confirmed` as a direct statement in an ICE ODO annual report.
- Novelty: no matching phrase or fact in the GEO finding set.
- Framing: ODO categorized this as an `Area of Concern`, not as a detention-standard deficiency.

#### Folkston Annex: non-working call boxes and an unstaffed control position

ODO's FY2020 Areas of Concern table states:

> Six cell call boxes did not work in the Annex housing pods.

and:

> Control in Annex Housing Unit C has not been staffed since July 2019.

- Facility: Folkston ICE Processing Center and Annex.
- Evidence: `MUCKROCK:117845:2022-ICFO-14071:p73`
- Claim type: `direct_quote`; eligible for `confirmed` with the `Area of Concern` qualifier.
- Novelty: the exact facts are absent from the GEO finding set. Existing findings `12399`, `12425`, and `12426` concern unsanitary/dilapidated conditions and a separate staffing-penalty dispute, so they provide context rather than duplication.

#### Joe Corley: plumbing fixtures appeared inadequate

ODO's FY2018 Personal Hygiene Area of Concern says:

> The number of plumbing fixtures appeared inadequate for the population housed in several areas.

- Facility: Joe Corley.
- Evidence: `MUCKROCK:117845:2022-ICFO-14071:p21`
- Claim type: `direct_quote`; eligible for `confirmed` only with `appeared` and `Area of Concern` preserved.
- Novelty: no matching GEO finding.

#### Rio Grande: one 15-minute call per day

ODO's FY2019 Telephone Access Area of Concern says:

> Detainees permitted on one 15-minute call per day

- Facility: Rio Grande.
- Evidence: `MUCKROCK:117845:2022-ICFO-14071:p47`
- Claim type: `direct_quote`; eligible for `confirmed` with the `Area of Concern` qualifier.
- Novelty: no matching GEO finding.

#### Coastal Bend: six intake, segregation, force, and visitation concerns

ODO's FY2020 Areas of Concern table identifies these Coastal Bend practices:

- `Showers are not available at intake.`
- Detainees signed a form saying they received a three-minute intake call `when phone calls are not provided at intake.`
- Detainees signed a form saying they watched the orientation video and could ask questions, but `the video is not shown during intake.`
- Two Special Management Unit policies contradicted staff guidance regarding visual searches and restraints.
- The facility had insufficient area for accountability of required protective equipment.
- The facility did not require an approved visitors list from detainees.

- Evidence: `MUCKROCK:117845:2022-ICFO-14071:p72`-`p73`
- Novelty: no matching GEO finding located.
- Framing: six Areas of Concern, not six formal standard deficiencies.

### Karnes facility-level control and standard break

The annual reports provide the only clear facility-level deficiency totals for a GEO-linked family residential center:

- FY2020: `Karnes County Residential Center accounted for 4 deficiencies.` Evidence: `MUCKROCK:117845:2022-ICFO-14071:p62`.
- FY2021: `Karnes County Residential Center had no deficiencies.` Evidence: `MUCKROCK:117845:2022-ICFO-14071:p93`.

This should not be presented as a four-to-zero improvement trend without qualification. FY2020 used FRS 2007, while FY2021 used the updated FRS 2020, and inspection conditions differed. The pair is useful as a methodological control showing why annual/facility normalization must retain the governing standard.

### Counterevidence and best practices

The compilation is not uniformly adverse. Its FY2020 Best Practices appendix says:

- Folkston's suicide-prevention team tried, where possible, not to house a detainee without another detainee who spoke the person's native language;
- Joe Corley's tablet grievance system allowed direct responses to detainees and electronic grievance storage; and
- Broward's tablets supported communications, requests, and sick calls.

Evidence: `MUCKROCK:117845:2022-ICFO-14071:p81`. These are ICE ODO characterizations of selected practices, not facility-wide endorsements.

## Request 73576: additional Family Case Management metro pairs

Existing finding `13439` covers Washington, DC/Baltimore under base award `HSCEDM-15-D-00008` and task order `HSCEDM-16-J-00044`. The same production confirms the four remaining metro pairs. All orders are to `GEO CARE LLC`, dated 2016-09-16, and state that they fund Option Year One through 2016-10-19.

| Metro | Base award | Task order | First-page total/grand total | Evidence |
|---|---|---|---:|---|
| Los Angeles | `HSCEDM-15-D-00010` | `HSCEDM-16-J-00046` | `$186,692.41` | `MUCKROCK:73576:2019-ICFO-39460:p153`-`p154` |
| New York | `HSCEDM-15-D-00011` | `HSCEDM-16-J-00047` | `$213,765.49` | `MUCKROCK:73576:2019-ICFO-39460:p161`-`p162` |
| Miami | `HSCEDM-15-D-00012` | `HSCEDM-16-J-00048` | `$186,919.05` | `MUCKROCK:73576:2019-ICFO-39460:p169`-`p170` |
| Chicago | `HSCEDM-15-D-00013` | `HSCEDM-16-J-00049` | `$171,208.56` | `MUCKROCK:73576:2019-ICFO-39460:p177`-`p178` |

The first page for each pair identifies the contractor, base award, task order, city, and displayed total. The continuation page completes the phrase `metropolitan region`, repeats both identifiers, and describes the funding/allotment limitation. These four pairs and identifiers were absent from the GEO finding set at final deduplication.

The displayed amount should be described as the total/grand total on this September 16, 2016 order page, not as the full contract ceiling or total program spend. Several detailed line-item amounts are redacted under `(b)(4)`.

## Import-ready priority

Recommended order for a coordinated import:

1. Rio Grande FY2021 positive TST followed by no further treatment offer and no latent-TB documentation (`p115`).
2. Folkston FY2020 six non-working call boxes and Annex Housing Unit C control unstaffed since July 2019 (`p73`), either as one tightly related finding or two direct-quote findings.
3. Four FCMP metro base/task mappings, preferably one synthesis finding with all four exact pairs and amounts rather than four near-duplicate findings.
4. Joe Corley FY2018 inadequate-plumbing Area of Concern (`p21`) and Rio Grande FY2019 call restriction (`p47`).
5. Allegation-log rows from request `38021` only if the editorial goal is to document intake patterns. Every summary must say `alleged` or `reported`, state that the workbook supplies no disposition, and avoid counting rows as incidents.

## Negative results and unresolved questions

- Request `117845` cannot support a complete facility-by-facility repeat-deficiency comparison. Its facility lists are explicitly top lists, not complete zero/nonzero tables.
- The Karnes four-to-zero change is not clean longitudinal evidence because the governing Family Residential Standards changed from FRS 2007 to FRS 2020.
- Request `38021` does not contain investigative dispositions. `Closed` is not a finding on the allegation.
- Facility labels in `38021` contain enough mismatches that facility-level rates or rankings require a separate normalization table keyed to the synopsis and operator history.
- Exact duplicate rows and semantically repeated synopses preclude treating row count as incident count.
- Row `364` should be held beside existing no-substantiation finding `12805`, not promoted independently.
- The four FCMP order-page amounts are not program ceilings. The release contains later modifications that can support a separate obligation timeline if needed.

## Stored evidence

Original evidence remains at:

- `datasets/muckrock/38021/FOIA_2018-ICFO-45499_-_Responsive_Records.xls`
- `datasets/muckrock/117845/2022-ICFO-14071.zip`
- `datasets/muckrock/73576/releases/9-14-21 MR73576/2019-ICFO-39460.pdf`

Temporary extracted files, decrypted copies, native-text sidecars, and page renders were kept outside the evidence directories. No FOIA request was filed, and no original was altered.
