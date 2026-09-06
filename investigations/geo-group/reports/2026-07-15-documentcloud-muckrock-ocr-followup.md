# DocumentCloud-to-MuckRock OCR follow-up

**Research date:** 2026-07-15  
**Scope:** MuckRock-linked DocumentCloud records, using DocumentCloud as the OCR/full-text layer and MuckRock as the provenance/release-status layer  
**Result:** two high-value GEO/private-detention productions and one BI Incorporated contract are import-ready after page-level visual review; one current IGSA hit was rejected as evidence because the indexed text is hidden by a full-page black redaction

## Outcome

This pass ran 84 new, exact DocumentCloud searches after checking the existing `documentcloud` search log:

- 47 record-class and enforcement-language queries;
- 19 contract/FOIA identifiers and facility-plus-document-class queries; and
- 18 conjunctions addressing active `epstein-gates-ipi` document gaps.

The governing form was:

```text
+data__mr_request:* +text:"TERM"
```

Conjunctions used multiple required text clauses, for example:

```text
+data__mr_request:* +text:"Torrance County Detention Facility" +text:"medical staffing"
+data__mr_request:* +text:"John Brennan" +text:"visitor log"
```

All 84 searches, including zeroes and capped result sets, were logged manually in `search_log` and `search_history` with `source=documentcloud`. Searches returning 100 records were capped at the retrieval limit and should not be interpreted as complete counts.

No database findings were added. The candidates below are prepared for a normal finding-import and independent verification step.

## Import-ready candidates

### 1. GEO Denver mortality review: unsafe care and delayed emergency response

**MuckRock request:** `72921`, *IHSC Mortality Reviews*  
**MuckRock status:** `appealing`, but the request has an actual agency production attached  
**Release detail:** 11 attachment references / 412 pages; the substantive production is attachment `1047437`, 196 pages, delivered November 1, 2022  
**DocumentCloud:** `23256300`, file hash `0086882861f11be8747ab44b631315f41b0171ce`  
**Database dedup:** no existing finding, lead, report, or evidence reference matched `72921`, `23256300`, `Kamyar Samimi`, or the reviewed claim language

The production contains multiple ICE Health Service Corps mortality reviews. Its GEO-specific report concerns Kamyar Samimi at the Denver Contract Detention Facility in Aurora, Colorado.

- `MUCKROCK:72921:2019-ICFO-38745:p50`: the review says care was “delivered outside the safe limits of practice,” and “either directly or indirectly contributed to his death.”
- `MUCKROCK:72921:2019-ICFO-38745:p56`: the review says DCDF did not follow GEO Policy 902's requirement to refer detainees on methadone or similar substances to a qualified facility. It also says the physician did not follow GEO clinical guidelines or establish withdrawal-assessment protocols, and nursing staff lacked withdrawal-management training.
- `MUCKROCK:72921:2019-ICFO-38745:p57`: the review says access to EMS was delayed because staff sought physician/HSA approval instead of immediately calling 911, and because staff did not assess Samimi or initiate CPR promptly.

Pages 50, 56, and 57 were rendered from the PDF and visually reviewed. The production is a primary ICE record. Its repeated references in two request communications and its single DocumentCloud copy are the same release, not independent corroboration.

The same 196-page file contains mortality reviews for Huy Chi Tran, Ronal Francisco Romero, Carlos Armando Mejia-Bonilla, Olubunmi Toyin Joshua, Osmar Epifanio Gonzalez, Jean Carlos Alfonso Jimenez Joseph, Gourgen Mirimanian, Wilfredo Padron, Roger Rayson, Atulkumar Babubhai Patel, Agustina Ramirez Arreola, and others. Those reports are a useful facility/operator normalization corpus but were not individually promoted in this pass.

### 2. CoreCivic Torrance CDR: 10% invoice deduction and disputed staffing data

**MuckRock request:** `137286`, *CoreCivic CDRs*  
**MuckRock status:** `done`; completed June 25, 2025  
**Release detail:** one 12-page substantive agency file plus two zero-page delivery artifacts  
**DocumentCloud:** `25896156`, `25939719`, and `26370215` are byte-identical copies, all with file hash `4af6e2ac0930cb57be45a688271b9e4de5623c40`  
**Database dedup:** no existing finding/evidence reference matched `137286`, the CDR, or the reviewed Torrance claim

- `MUCKROCK:137286:2023-ICFO-04847_005:p1`: ICE rejected CoreCivic's December 29, 2020 response as an inadequate remedy and ordered a 10% deduction from each monthly invoice beginning in December 2020 until the facility achieved an 85% minimum staffing level and otherwise satisfied the CDR.
- `MUCKROCK:137286:2023-ICFO-04847_005:p2`: ICE said CoreCivic's response omitted 4.75 medical vacancies, that actual medical staffing was about 44.92% rather than the asserted 95%, and that ICE was paying for a guaranteed minimum with associated staff support rather than staffing reduced to the current population.

Pages 1 and 2 were rendered and visually reviewed. The three DocumentCloud IDs are mirrors of one source file and must not be counted as corroboration.

### 3. BI Incorporated CSOSA GPS task order: pricing and ceiling

**MuckRock request:** `111477`, *B.I. Incorporated (CSOSA)*  
**MuckRock status:** `no_docs`, but the communication/file record contradicts the label: five agency attachments totaling 77 pages include a 70-page executed/rescinded contract production  
**DocumentCloud:** `21073244`, file hash `63e1d65584e0614ac40df679be8aa0ff94cc10d5`  
**Database dedup:** no existing finding/evidence reference matched `111477`, `CSOSA-15-F-0335`, `CSOSA-15-005629`, or `$2,821,127.40`

`MUCKROCK:111477:FOIA-Final-Supplemental-BI-INC-AWARD-CSOSA-15-F-0335:p6` identifies BI Incorporated as contractor under order `CSOSA-15-F-0335` and lists 132,000 device-days at `$1.83`, 132,000 monitoring-service days at `$2.10`, a `$519,939` base award, and a `$2,821,127.40` total task-order value if all options were exercised through August 2, 2020.

Page 6 was rendered and visually reviewed. This is a useful non-ICE pricing and contract-design comparator for BI's electronic-monitoring business. The anomalous request status is an important control: MuckRock's top-level status cannot substitute for enumerating communication attachments.

## High-value processing candidate, not yet evidence

### MuckRock 199633: current Orange County ICE package

Request `199633`, *DHS + Orange County Jail (Orange County Sheriff)*, is marked `done` and contains nine released attachments totaling 1,975 pages. The June 29, 2026 delivery includes:

- a 159-page 2025 ICE/Orange County IGSA (`DocumentCloud 28364498`);
- 1,042 pages titled `DailyIntakesAndReleases`;
- a 691-page executed YesCare inmate-health-services contract;
- a health-services document and inmate handbook; and
- a detention-compliance/removal extension.

This is a strong processing target for current local-facility economics, daily population/use, and medical-subcontract controls. It is not GEO-operated and is therefore a comparator rather than direct GEO evidence.

Important control: DocumentCloud indexed text underneath a full-page black redaction in the IGSA PDF. The OCR/text endpoint exposes a detention rate and other terms, but the corresponding PDF page renders as a solid black rectangle in Poppler, Cairo, and Ghostscript. Because the words are not visibly reviewable on the released page, this pass rejected the hidden text as finding evidence. This illustrates why DocumentCloud snippets must never be promoted without rendering the cited page.

## Known releases and false-positive request mappings

- `117845` resurfaced through `"ODO Inspection"`, `"Office of Detention Oversight"`, and repeat-deficiency queries. It is the already acquired ODO annual-report compilation described in the earlier hidden-release report, not a new source.
- `72960` resurfaced through `"Request for Equitable Adjustment"` and exact contract IDs `HSCEDM-11-D-00003` and `HSCEDM-15-D-00013`. It is the already known GEO Voluntary Work Program REA-denial matter and appears in the Hartel source manifest.
- `112717`, concerning the death at Richwood Correctional Center, is marked `rejected`. Its DocumentCloud hit is the requester's own eight-page FOIA request, not responsive agency records. It must not be treated as a release.
- `169660` is a DHS CRCL FOIA-log production. Matches for facility, mortality, and IGSA language describe requests in the log, not the underlying responsive records.
- `137286` has three DocumentCloud IDs with the same file hash. They are mirrors, not corroboration.
- Request descriptions, acknowledgment letters, appeal letters, and FOIA logs were excluded from the candidate set unless an actual primary record was attached and separately reviewed.

## Record-class query results

The most useful exact searches were:

| Exact query suffix | Returned | Triage |
|---|---:|---|
| `+text:"Contract Discrepancy Report"` | 10 | Led to `137286`; other hits were unrelated/template references |
| `+text:"Mortality Review"` | 56 | Led to `72921`; many state-corrections and unrelated policy hits |
| `+text:"Detainee Death Review"` | 4 | Included rejected request `112717`, not a release |
| `+text:"Office of Detention Oversight"` | 6 | Mostly known `117845`, logs, or incidental correspondence |
| `+text:"ODO Inspection"` | 4 | Known `117845` plus FOIA activity reports |
| `+text:"Annual Inspection Report"` | 13 | No new GEO production |
| `+text:"Request for Equitable Adjustment"` | 33 | Known `72960`; remaining results unrelated procurement files |
| `+text:"Quality Assurance Surveillance Plan"` | 20 | Led to BI/CSOSA contract `111477`; most other hits unrelated contracts |
| `+text:"staffing vacancy"` | 3 | No new GEO document |
| `+text:"guaranteed minimum"` | 42 | Broad; reinforced the need for facility/ID conjunctions |
| `+text:"Intergovernmental Service Agreement"` | 17 | Known Pine Prairie and CoreCivic records plus current Orange County comparator |
| `+text:"repeat deficiency"` | 1 | Known `117845` |
| `+text:"repeat deficiencies"` | 3 | Known `117845` plus unrelated behavioral-health contract |

Capped at 100 results: `"Death Review"`, `"Corrective Action Plan"`, `"Staffing Plan"`, `"Intergovernmental Agreement"`, `"suicide prevention"`, `"notice to proceed"`, `"termination for convenience"`, and `"liquidated damages"`.

Exact zero-result controls were:

```text
+data__mr_request:* +text:"invoice deduction"
+data__mr_request:* +text:"monthly vacancy report"
+data__mr_request:* +text:"medical staffing plan"
+data__mr_request:* +text:"staffing noncompliance"
+data__mr_request:* +text:"withhold invoice"
+data__mr_request:* +text:"deducted from invoice"
+data__mr_request:* +text:"records of noncompliance"
+data__mr_request:* +text:"deficiency worksheet"
+data__mr_request:* +text:"Death in Detention Reporting Act"
```

Identifier searches showed a second limitation: OCR often mangles contract numbers. Exact `70CDCR19DIG000009` and `2023-ICFO-04847` returned zero even though the reviewed Torrance PDF visibly contains those identifiers; the facility-plus-class query found the document. Conversely, `HSCEDM-11-R-00002`, `CSOSA-15-F-0335`, and `70CDCR25DIG000027` each returned the expected source.

## Epstein-Gates-IPI gap search

No MuckRock-linked primary record closed the requested gaps.

Exact zeroes:

```text
+data__mr_request:* +text:"vaccine-derived genetic material"
+data__mr_request:* +text:"Shakil Afridi" +text:"vaccination"
+data__mr_request:* +text:"Afridi" +text:"vaccination program"
+data__mr_request:* +text:"John Brennan" +text:"visitor log"
+data__mr_request:* +text:"Brennan" +text:"White House visitor"
+data__mr_request:* +text:"Lisa Monaco" +text:"public health deans"
+data__mr_request:* +text:"Kathryn Ruemmler" +text:"White House Counsel"
+data__mr_request:* +text:"International Peace Institute" +text:"Gates Foundation"
+data__mr_request:* +text:"Terje Rod-Larsen" +text:"Gates"
+data__mr_request:* +text:"OPP1096058"
+data__mr_request:* +text:"INV-007752"
+data__mr_request:* +text:"OPP1100586" +text:"International Peace"
```

Positive-result conjunctions were reviewed and proved incidental:

- `"vaccination program" + "genetic material"` returned two documents. One combined Interior Department COVID-vaccination material with an unrelated sturgeon-genetics passage; the other combined an HPV-vaccination article with an unrelated cancer-genetics article thousands of pages later.
- `"John Brennan" + "calendar"` returned 11 token-AND matches. A leading Ebola-response file referred to WHO official **Richard John Brennan** and a Google Calendar invitation, not CIA Director John Brennan's calendar.
- `"May 16, 2014" + "public health"` returned 10. The leading NIH file concerned a May 16 Mapp Biopharmaceutical Ebola teleconference and a separate Public Health Agency of Canada author affiliation; it was not Lisa Monaco's public-health-deans letter.
- `"Ruemmler" + "calendar"` returned two duplicate uploads of a DOJ FOIA-transparency email where “calendar” referred to calendar years, not a Ruemmler calendar.
- `"777 United Nations Plaza"` returned two unrelated records: a 1966 FBI Ramparts press-conference record and a New York City schedule.

These are token-co-occurrence false positives, not evidence of the investigation targets.

## Practical lessons

1. Exact facility-plus-record-class searches outperformed broad entity searches.
2. Search both the formal contract/FOIA identifier and a human-readable fallback; OCR may destroy hyphens or confuse `I`, `1`, `O`, and `0`.
3. Always retrieve MuckRock request detail. `appealing` can coexist with a production, while `no_docs` can coexist with a later supplemental contract attachment.
4. Deduplicate on file hash and MuckRock request/file lineage. Three DocumentCloud copies of one PDF are one source.
5. Render every proposed citation. DocumentCloud may index words hidden under a black redaction or otherwise not visible in the public PDF.
6. Preserve request descriptions and FOIA logs as leads only; they are not proof that responsive records were released.

## Stored material

The four reviewed DocumentCloud PDFs and page renders were downloaded only to the session's temporary `/tmp/dc-muckrock-*` directory for visual QA. No evidence files were added to `datasets/`, and no FOIA requests were filed.
