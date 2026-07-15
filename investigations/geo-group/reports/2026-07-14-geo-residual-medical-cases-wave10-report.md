# GEO residual medical/death case review — wave 10

**Cutoff:** 2026-07-14  
**Profile / thread:** `geo-group` / litigation thread 113  
**Dockets reviewed:** CourtListener 70844088, 72097949, and 73178988; related main docket 73114403

## Disposition

The source label “medical/death” is substantively wrong for two of the three dockets. Patterson and Okoroafor are employee-leave/employment cases routed into this set because “Family and Medical Leave Act” contains medical terminology. Garcia is the only wrongful-death action.

The three cases do **not** establish a recurring GEO medical-liability pattern:

- none contains a publicly retrieved merits judgment, causation finding, or settlement;
- Patterson is stayed for arbitration and administratively closed;
- Garcia remained in pretrial litigation as of the last indexed activity, but crucial pleadings and the partial-dismissal order are unavailable in free RECAP;
- the supplied Okoroafor docket is a duplicate dismissed without prejudice, while its main employment action remains active.

This is a routing/classification result, not a finding that GEO lacks medical-liability exposure elsewhere.

## Evidence boundaries

CourtListener docket metadata, docket-entry metadata, and retrieved filings are the principal sources. The ICE detainee-death report is an official primary record for the named person’s ICE custody and transfer to Adelanto; it does not establish civil causation, negligence, or compliance. Justia is used only as a public docket-listing mirror for Patterson. LAist and the San Francisco Chronicle are used only for the family-identity bridge in Garcia and are not independent proof of the complaint’s allegations.

“Unavailable” below means that the document was not contributed to free RECAP or otherwise retrieved in this pass. CourtListener’s `is_sealed` values were null for the missing Garcia documents, so they are **not** characterized as sealed.

## Archived source bundle

The exact primary CourtListener and ICE JSON/PDF captures used in this review are retained under [`investigations/geo-group/sources/2026-07-14-geo-residual-medical-cases-wave10/`](../sources/2026-07-14-geo-residual-medical-cases-wave10/). The companion manifest maps each capture to a canonical URL and evidentiary role. The SHA-256 ledger now uses conventional repository-relative paths and can be checked from the repository root with:

```bash
shasum -a 256 -c investigations/geo-group/reports/2026-07-14-geo-residual-medical-cases-wave10-sha256.txt
```

The secondary Justia Patterson listing could not be archived: a direct retrieval attempt returned HTTP 403. Its canonical URL remains recorded, but no HTML file or substitute content is represented as a capture.

## 1. Patterson v. The GEO Group, Inc.

**Identity and issue.** Penelope Patterson sued The GEO Group, Inc. in the Northern District of Georgia, No. 1:25-cv-03984. CourtListener classifies the action as `751 Labor: Family and Medical Leave Act`, cause `29:2601 Family and Medical Leave Act`. GEO is the only named defendant in the retrieved docket metadata. No detention facility, detained person, government defendant, or custodial-medical issue is identified in the public material reviewed.

**Posture.** A public Justia docket listing reports that on September 10, 2025 the court granted the parties’ joint motion to stay pending arbitration, directed administrative closure, and required status reports beginning December 9, 2025. The listing shows a December 9 status report but no freely accessible arbitration result, merits ruling, or settlement. CourtListener’s API record is stale—it exposes only two July 2025 entries and a July 23, 2025 modification date—so its null termination field cannot supersede the later public listing.

**Liability boundary.** There is no public basis in this record to assign individual liability, facility-level liability, detention-related liability, or government responsibility. The dispute is an employment/FMLA matter and remains unresolved on the merits in the reviewed public record.

**Finding:** 12992 (verified).

Sources: [CourtListener docket](https://www.courtlistener.com/docket/70844088/patterson-v-the-geo-group-inc/); [Justia docket listing](https://dockets.justia.com/docket/georgia/gandce/1%3A2025cv03984/346649).

## 2. Gabriel Alejandro Garcia et al. v. The GEO Group, Inc. et al.

**Identity and issue.** Gabriel Alejandro Garcia and Mariel Garcia Mora sued The GEO Group, Inc., Wellpath LLC, and Does 1–100 in the Central District of California, No. 5:25-cv-03614. The docket identifies diversity jurisdiction and wrongful death. The retrieved civil cover sheet—counsel’s characterization, not an adjudication—lists negligence/wrongful death, negligent hiring/training/supervision, intentional infliction of emotional distress, and California Government Code § 7320.

**Facility/person bridge.** ICE’s official detainee-death report records that Gabriel Garcia Aviles was transferred by ERO Los Angeles to Adelanto ICE Processing Center on October 15, 2025 and died on October 23, 2025. LAist identifies Mariel Garcia as his daughter in reporting expressly about the Adelanto lawsuit; the San Francisco Chronicle identifies Gabriel Alejandro Garcia as his son. Together with the plaintiffs’ names and case timing, this creates a **high-confidence but secondary-source identity bridge** between the lawsuit and the person in the ICE report. The missing complaint prevents primary court-document authentication of that bridge in this pass.

The ICE report does not state that GEO or Wellpath caused the death and does not make a compliance determination. Because the complaint and exhibits were unavailable, this review does not restate or elevate any specific medical allegation.

**Posture through July 8, 2026.** GEO moved to dismiss the complaint’s fourth and fifth claims on April 3; the motion was fully briefed and taken under submission without oral argument on May 8. Docket entries then show a June 4 item described only as `Dismiss`, a June 9 `Extension of Time to Amend`, and a June 10 `Order`; their documents are unavailable, so the claims affected, whether leave to amend was granted, and the exact legal reasoning remain unknown. A retrieved June 30 order to show cause addressed the parties’ failure to submit a timely Rule 26(f) report and warned of dismissal or sanctions. Entries for a Rule 26(f) report and declarations on July 7, followed by scheduling activity on July 8, show that the action continued after the warning. The docket has no termination date. No public source reviewed establishes judgment, settlement, or a merits finding.

**Liability boundary.** GEO and Wellpath are the named corporate defendants. The Doe defendants are unidentified; no named individual defendant can be assessed. The record supports an Adelanto/ICE-custody nexus for the decedent through the official report and secondary identity bridge, but it does not support a finding of corporate causation, facility compliance failure, or individual culpability.

**Finding:** 12993 (verified).  
**Retrieval lead:** 63730 (high priority; complaint, exhibits, motion papers, and ECF 27–29/32–34).

Sources: [CourtListener docket](https://www.courtlistener.com/docket/72097949/gabriel-alejandro-garcia-v-the-geo-group-inc/); [June 30 order](https://www.courtlistener.com/opinion/10917261/evon-v-law-offs-of-sidney-mickell/) (CourtListener’s citation-derived page title is unrelated to the actual Garcia caption); [ICE detainee-death report](https://www.ice.gov/doclib/foia/reports/detaineeDeaths/Garcia-Aviles_Gabriel.pdf); [LAist identity bridge](https://laist.com/brief/news/politics/lawsuit-alleges-inhumane-conditions-at-ice-adelanto-facility); [San Francisco Chronicle identity bridge](https://www.sfchronicle.com/projects/2026/ice-detention-deaths/).

## 3. Okoroafor v. The GEO Group Inc.

**Duplicate supplied docket.** CourtListener 73178988 is W.D. Washington No. 3:26-cv-05375. The May 21, 2026 order says the action was inadvertently opened as a duplicate of No. 3:26-cv-05307, dismisses the duplicate without prejudice, and directs refund of the duplicate filing fee. This is administrative housekeeping, not a merits disposition.

**Main action and true issue.** The main docket is CourtListener 73114403, W.D. Washington No. 3:26-cv-05307. Uzonna Okoroafor, a former GEO detention officer at Northwest ICE Processing Center, sued GEO alone. The complaint alleges federal FMLA interference and retaliation, Washington associational-disability discrimination, wrongful discharge in violation of public policy, and Washington paid-family-and-medical-leave interference and retaliation. Those are allegations, not findings. The facility is relevant as the workplace; the case is not a detainee medical-care or death action, and no government entity is a defendant.

**Posture.** GEO answered on June 30, 2026, and the court entered a discovery/depositions/joint-status-report scheduling order on July 2. The answer and scheduling order were indexed but not available as free documents. No dismissal, settlement, or merits adjudication appears in the main docket through the cutoff.

**Liability boundary.** GEO is the only defendant. No individual employee or government actor is named. Any liability question is corporate-employer liability under the pleaded employment statutes and state theories; none has been adjudicated.

**Findings:** 12994 and 12995 (verified).

Sources: [duplicate docket](https://www.courtlistener.com/docket/73178988/okoroafor-v-the-geo-group-inc/); [main docket](https://www.courtlistener.com/docket/73114403/okoroafor-v-the-geo-group-inc/).

## Cross-case issue matrix

| Case | Route result | Facility / government nexus | Public posture | Merits signal |
|---|---|---|---|---|
| Patterson | False positive: employee FMLA | None established | Stayed for arbitration; administratively closed | None |
| Garcia | True wrongful-death case | High-confidence Adelanto/ICE-custody nexus; complaint bridge still missing | Active pretrial record after partial-dismissal sequence and OSC | None; causation unadjudicated |
| Okoroafor | False positive: employee leave/discrimination | NWIPC only as GEO workplace; no government defendant | Duplicate dismissed without prejudice; main action answered and in discovery | None |

The strongest systemic conclusion is a data-quality one: two of three residual “medical/death” candidates (66.7%) were caused by lexical or duplicate-docket routing. The only common defendant-level fact is GEO’s presence. That denominator is too small and the dispositions too preliminary to support a systemic medical-care hypothesis.

## Database writes and QA

- Verified findings: 12992–12995, all attached to litigation thread 113.
- New lead: 63730, attached to thread 113. No other lead was warranted.
- The required post-wave `auto_leads.py run` generated four reciprocal fuzzy-match items (63795–63798) for entity labels carrying the same exact ICE contract identifiers. Each was immediately closed as `dead_end` because it is an entity-alias/deduplication issue, not a separate investigative lead.
- Papercut 1023 records CourtListener public HTML returning HTTP 403 while the authenticated API remained usable.
- Papercut 1024 records silent source-quote mapping loss in `findings_tracker.py`; the affected evidence rows were repaired and all four findings were verified.
- Archival QA strengthened finding 12993 with the exact docket-entry metadata for ECF 27–29 and 32 and finding 12995 with exact complaint excerpts naming the workplace and all five pleaded causes; both were re-verified.
- Papercut 1026 records the Justia archival HTTP 403. Papercut 1027 records that `query_courtlistener.py recap-search --output` returns before logging the search.
- Final database checks: `PRAGMA quick_check` returned `ok`; `PRAGMA foreign_key_check` returned the unchanged pre-existing baseline of 64 rows.

The companion CSVs carry the row-level case/posture classification and the negative/missing-document audit. The JSON manifest records each source capture, repository path, canonical URL, hash, and evidentiary role. The SHA-256 ledger covers the complete archived source bundle plus the generated artifacts (excluding the ledger itself).
