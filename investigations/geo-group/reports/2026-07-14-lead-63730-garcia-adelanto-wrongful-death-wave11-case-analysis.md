# Garcia v. GEO / Wellpath — bounded public-record case analysis

**Case:** *Gabriel Alejandro Garcia et al. v. The GEO Group, Inc. et al.*, C.D. Cal. No. 5:25-cv-03614-KK-DTB, CourtListener docket 72097949  
**Cutoff:** 2026-07-14  
**Lead / thread:** #63730 / 113  
**Disposition:** blocked at a documented public-source stop; human action #78

## Result

The refreshed CourtListener record contains the same 37 docket entries as the wave-10 capture. The docket remains un-terminated, its last filing remains July 8, 2026, and no post-July-8 filing or availability change was found. There is therefore no new docket/posture fact warranting a duplicate finding. Verified finding #12993 remains the controlling database record.

The full requested-document audit recovered no new substantive filing. Free public copies remain limited to ECF 1-1, the three-page civil cover sheet, and ECF 30, the two-page June 30 procedural order to show cause. CourtListener reports ECF 1 main and attachments 2-3; ECF 17-18 and 22; ECF 27-29; and ECF 32-34 as `is_available=false` and `is_sealed=null`. Null sealing metadata is not evidence that a document is sealed.

Direct probes of the expected CourtListener storage paths and Justia PDF paths returned 404 for the requested missing documents. Justia's docket listing stops at February 27. Exact CACD/GovInfo searches found no public package. The Internet Archive RECAP item for this docket contains only ECF 1-1 and ECF 30. No PACER purchase, RECAP request, clerk contact, or outside contact was made.

## Parties and pleaded material

The public cover sheet names Gabriel Alejandro Garcia and Mariel Garcia Mora as plaintiffs; The GEO Group, Inc., Wellpath LLC, and Does 1-100 as defendants. It characterizes the action as involving negligence/wrongful death, negligent hiring/training/supervision, intentional infliction of emotional distress, and California Government Code § 7320; it records a jury demand and money to be determined at trial. These are filer characterizations, not adjudicated facts, and the cover sheet neither replaces nor supplements the missing complaint.

The docket says GEO moved to dismiss the fourth and fifth complaint claims, plaintiffs opposed, and GEO replied. The filings are unavailable, so the claim-number-to-theory mapping, parties' arguments, requested disposition, and cited evidence cannot be stated. ECF 27 is indexed only as `Dismiss`, ECF 28 as `Extension of Time to Amend`, and ECF 29 as `Order`. Their texts are unavailable, so the scope of any dismissal, prejudice, leave to amend, deadline, governing rule, and reasoning remain unknown.

Wellpath answered at ECF 24, but the answer is unavailable. The Rule 26 report and declarations at ECF 32-34 establish continued filing activity after the June 30 warning; they do not expose the claims or the parties' explanation. The current public record establishes no judgment, settlement, merits causation finding, negligence holding, compliance determination, or individual Doe identification.

## Court holding recovered

ECF 30 holds only that the parties had not timely filed the joint Rule 26(f) report required by the June 4 scheduling order. The court ordered a written response and report within seven days and warned that failure could result in dismissal without prejudice or other sanctions. The July 7 filings show a response sequence; the refreshed docket contains no later public dismissal or sanction. The order does not decide civil liability or the adequacy of detention medical care.

## ICE record and privacy boundary

The current official ICE PDF is byte-identical to the wave-10 archived report. The prior URL now returns 404; the live official URL is `https://www.ice.gov/doclib/foia/reports/dderGabrielGarciaAviles.pdf`. The report records ICE custody, transfer to Adelanto on October 15, 2025, later hospital transfer, and death on October 23, 2025. It does not determine civil causation, negligence, GEO or Wellpath liability, or facility compliance. This package intentionally omits granular medical information, date of birth, arrest detail, and other unnecessary personal data.

Because the complaint is missing, the court record still does not independently authenticate the relationship between the named plaintiffs and the individual in the ICE report. The official ICE record and the court docket are preserved as separate provenance chains.

## Entity and database handling

Wellpath LLC was absent from the canonical entity table and was registered once as entity #5144 using CourtListener docket 72097949. Verified connection #6414 records only the docket's exact statement that GEO and Wellpath were both served as defendants; it expressly makes no business-relationship or liability inference. No private family member or medical-care individual was registered.

No new finding was created. Finding #12993 remains verified (`paraphrase`, high confidence) and is not duplicated. Lead #63730 is blocked with an explicit stop reason. Human action #78 covers only authorized PACER retrieval or a later free-RECAP/court-hosted copy of the exact missing ECFs. Its `related_lead_id` is intentionally NULL because that live column points to the legacy `leads_old_backup` table; linkage to #63730 is preserved in the action title and notes so the foreign-key baseline remains 64. Papercut #1048 records that schema defect for repair.

## Public-source stop

The unresolved questions are the complaint's exact factual allegations and counts, the parties' motion arguments, the court's June dismissal/amendment reasoning, and the current schedule details. Those questions cannot be answered from the publicly retrieved record without speculating. Human action #78 is the bounded next step; no paid retrieval is authorized by this package.

## QA

- CourtListener entries: 37 over two API pages; docket-document ledger: 40 RECAP-document rows.
- Requested RECAP records audited: 13 across ten docket entries.
- Docket delta from wave 10: zero.
- Current and prior ICE PDF SHA-256 match: `2e32126f054b8fd6acffb6f723ed5256a627a563f372bd69502782f9615fb90d`.
- Database `PRAGMA quick_check`: `ok`.
- Foreign-key violations: `64`, unchanged baseline.
- No new finding, lead, or hypothesis; no `auto_leads.py` run.
