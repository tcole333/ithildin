# GEO Group CourtListener/RECAP coverage audit — wave 10

**Audit date:** July 14, 2026  
**Profile / thread:** `geo-group` / 113  
**Primary inventory cutoff:** July 13, 2026  
**Scope:** coverage and retrieval audit, not a new merits search

## Audit conclusion

The CourtListener work has a strong, identity-controlled federal baseline and substantial full-text coverage of the highest-priority litigation clusters, but it is not a complete litigation census. The durable universe contains **4,597 canonical candidate records**, divided without overlap into **1,494 exact-party-supported dockets**, **196 reference-only records**, and **2,907 false-positive query records**. The 1,494 count reconciles exactly to **1,489 identity-confirmed GEO/current-or-legacy-subsidiary dockets plus five unresolved same-name-party dockets**.

Of the 1,489 identity-confirmed dockets, **1,087** expose at least one returned RECAP-document ID or `more_docs` indicator and **402** expose neither a returned RECAP indicator nor an opinion link in the inventory. Only **17** identity-confirmed canonical dockets link to an opinion-search or docket-detail cluster in the inventory. Those figures describe API/index availability, not whether PACER contains filings. **Absence from RECAP is never treated as absence of a filing.**

The principal detainee-labor, NWIPC inspection, custodial-death, FCA, securities, New Jersey, employee-wage, legacy-commercial, and procurement-protest clusters have received full-text or developed-posture review. No reliable percentage of the 1,489 dockets can be labeled “fully analyzed,” because the universe has no document-level completion flag and later reports expanded beyond the early 458-docket seed through targeted searches. The defensible coverage statement is cluster-based, not a fabricated docket completion rate.

## 1. What was searched and identity-confirmed

- The bounded universe searched **75 alias rows representing 67 normalized query groups**. It covered all 60 guarantor-subsidiary names in GEO's fiscal-2025 Exhibit 22, the parent and supported punctuation variants, Wackenhut predecessor names, primary-supported current/legacy names from the 14-UEI DHS map, and supported former names.
- Each alias row received party, quoted RECAP/case, and opinion-search treatment. Punctuation-only equivalents shared normalized query groups; genuinely distinct legacy names were searched separately.
- The parent party queries hit the 500-result ceiling and were replaced by date-sharded searches. The repaired parent quoted-case shards were also split until each shard was below the cap. `Community Alternatives` remains a capped, generic, identity-ambiguous query and is not used as GEO identity evidence.
- Canonicalization merged court+docket-number variants, division prefixes, and judge suffixes while retaining distinct district, transfer, and appellate dockets.
- The candidate layer is exactly: **1,494 exact-party-supported + 196 reference-only + 2,907 false-positive = 4,597**.
- The identity-confirmed category routing is: 801 civil-rights, 369 other, 148 detention-conditions, 89 employment, 37 labor/wage/TVPA, 25 medical/death, 15 contract/procurement/FCA, and five securities/investor dockets. These are metadata routing labels, not allegation, holding, or outcome classifications.
- Termination metadata reports 1,310 `terminated`, 177 `active`, and two `unknown` identity-confirmed dockets. `Active` means only that CourtListener lacked a termination date at the snapshot.
- Forty-four alias rows returned no exact-party-supported docket. This is a bounded negative, not proof that those entities were never parties.
- FJC coverage failed at source level: 14 exact-name sentinel searches timed out and a broad `GEO` starts-with query returned Georgia-prefixed noise. Structured monetary fields therefore remain incomplete.

### Exact 1,494-to-1,489 reconciliation

| Bucket | Count | Records |
|---|---:|---|
| Identity-confirmed GEO/current-or-legacy subsidiary | 1,489 | `identity_status=confirmed` |
| Unresolved `Community Alternatives` same-name party | 1 | *Harris v. Community Alternatives*, N.C.E.D. 5:11-cv-00052, docket 5549851 |
| Unresolved `SECON, Inc.` same-name parties | 4 | M.S.S.B. 87-02647, docket 19415800; N.C.E.D. 3:90-cv-00009, docket 19328834; N.C.E.B. 90-00281 and 91-00001, dockets 33801649 and 33802281 |
| **Exact-party-supported canonical dockets** | **1,494** | **1,489 + 1 + 4** |

Exact spelling is not corporate identity. The five generic-name cases remain excluded from the GEO count until independent corporate-lineage evidence resolves them.

### Relationship to the earlier 458-docket seed

The lead-59509 inventory of 458 dockets was an earlier, capped nine-name sweep plus five targeted additions. It is neither additive to nor a superset of the 1,489 identity-confirmed universe. It overlaps **426** identity-confirmed dockets, contains **32** targeted, caption-variant, lineage-review, or ambiguous records outside that confirmed set, and misses **1,063** identity-confirmed dockets later recovered by the broader sharded universe. Its seven `selected_for_deep_read` flags describe only that early wave; later targeted reports substantially expanded full-text coverage.

## 2. High-priority clusters with full-text or developed-posture analysis

| Cluster | Coverage achieved | Remaining boundary |
|---|---|---|
| **Nwauzor / Washington / NWIPC detainee labor** | Full Washington Supreme Court and Ninth Circuit merits/rehearing opinions, district judgment/JMOL, remedies, contract economics, and pending Supreme Court No. 25-828 posture reviewed. | CVSG remains pending; no Supreme Court merits disposition at cutoff. |
| **Menocal / Aurora detainee labor** | Tenth Circuit certification, 2022 cross-motions order, Supreme Court Yearsley decision, renewed 2026 motion, and pretrial posture reviewed in full. | July 13 order and late ECF filings are PACER-only/missing; trial and dispositive posture may have changed. |
| **Novoa / Adelanto detainee labor** | All 654 public docket objects paginated; ECF 542 partial merits ruling and ECF 561 stay order reviewed in full. Review corrected the earlier “allegation-only” characterization: California wage/UCL liability was decided nonfinally, while forced-labor claims remain unresolved. | ECF 607-610 are indexed but unavailable; no final judgment, remedy, stay-lifting order, or trial appears publicly. |
| **Inslee / DOH / NWIPC inspection** | Complaint, district orders, four opinions, appellate briefs available in RECAP, mandate, remand filings, July 2026 injunctions, and notices of appeal reviewed. | New Ninth Circuit numbers, March 27, 2026 ICE contract exhibit, State briefs, and any Supreme Court merits docket are missing. |
| **Reid / Lawrenceville death** | All 258 public docket entries paginated; third amended complaint, 2025 dismissal opinion, 2026 Daubert opinion, and GEO/officer summary-judgment memorandum reviewed. | No public July 13 settlement-conference outcome; key state-record attachments, party memoranda, sealed material, and later summary-judgment filings/rulings are missing. |
| **Medical/conditions appellate sample** | *Minneci*, *Bilal*, *Pesci*, and *Newsome* were read and allegation/holding/disposition boundaries recorded. | This is not full coverage of the 25 medical/death or 148 detention-condition routing buckets. Recent active cases remain unreviewed at full-text level. |
| **FCA** | *Roycroft* appellate opinion and district skeleton fully audited; *Burciaga* public docket exhausted and later federal quotations authenticated; *Hynd* procedural dismissal reviewed. | *Roycroft* pleadings/invoices/district order and *Burciaga* complaint, ECF 41, terminal documents, payer, and settlement facts remain missing. *Burciaga* cannot yet be classified as ICE/DHS. |
| **Procurement protests** | GEO's BOP protest was reviewed through TRO and dismissal. The Salus CSRO/CSI GAO–COFC record was deeply analyzed as an independent DHS comparator, including the reported opinion and 93-source manifest. | Salus's protected administrative record, GAO file, signed RFP/award/modifications, OCI file, partners, and political-link records are not public; no Salus–GEO bridge was established. |
| **New Jersey / Delaney Hall** | Both federal dockets fully paginated; removal, answer, City complaint, DOJ position, inspection exhibits, CoreCivic precedent, and mediation posture reviewed. | Actual Newark municipal complaint, complete ICE contract, several exhibits, and any current state disposition are unavailable. |
| **Securities / governance** | *Hartel* DE 45, recovered DE 63, pleadings, settlement, final judgment, and distribution record reviewed; *Zhang* governance settlement and *Maldonado* were screened. | The ICE-side reimbursement/equitable-adjustment record underlying Hartel's pleaded theory remains unauthenticated and uncollected. |
| **Employee wage** | The 458 seed was re-screened and targeted searches added *Lewis*, *Mayes*, and other older cases. Full-text review covered the $3.69 million five-case California settlement, three-job-group conditional certification, 1,446 opt-ins, and individual controls. | Final agreements/approval orders are missing for *Lewis*, *Mayes*, *Giles*, state *Perez*, *Mazzei*, and *Burch*; no complete portfolio amount is possible. |
| **Legacy commercial** | HCC stop-loss, ARAMARK/CEC, *Watson*, *Gilliland*, and *McDougall* were posture- and acquisition-timing-audited. | Several complaints, judgments, and settlements remain PACER-only; amounts must retain demand/judgment/settlement distinctions. |

## 3. What remains uncovered or inaccessible

### Structural coverage limits

1. **State and local courts:** CourtListener/RECAP is not a state-case census. Newark Municipal Court, California employment cases, state wage approvals, county filings, and removed-case origin records require state portals, clerks, or PACER attachments. State cases absent from RECAP cannot be counted as nonexistent.
2. **PACER-only and missing RECAP:** Known gaps include Menocal late filings, Reid state/SJ records, Novoa status reports, Inslee's contract exhibit, Delaney Hall contract materials, Roycroft pleadings/invoices, Burciaga merits/terminal papers, and legacy settlement/judgment documents.
3. **Sealed/protected/confidential records:** Reid has sealed attachments; Salus's administrative record and several COFC filings are protected or sealed; qui tam pre-unsealing records may remain sealed; settlement negotiations and agreements may be confidential. The audit does not infer contents.
4. **Appeals:** New July 13 NWIPC appeals had no public Ninth Circuit number; *Inslee* may or may not have generated a Supreme Court merits docket after application 25A1145; *Nwauzor* remains at CVSG; current appellate assignments can lag notices.
5. **Same-name identity:** Five exact-name records remain unresolved, and generic/capped searches—especially `Community Alternatives`—cannot establish lineage. The early seed also contained B.I. and legacy-name records requiring identity or acquisition review.
6. **Current docket drift:** The main universe is a July 13 snapshot. The 177 unterminated and two unknown-status dockets require refresh; post-cutoff filings, new cases, transfers, appeals, sealed entries, and delayed RECAP contributions are outside the snapshot.
7. **Index/document availability:** 402 identity-confirmed dockets expose neither a RECAP-document indicator nor an opinion link. This is an acquisition queue, not a negative finding. Conversely, the 1,087 with indicators have not all been read.
8. **Universe boundary:** The 1,494 count is a bounded, exact-party-supported search result, not all litigation involving facilities, trade names, officers, contractors, indirect subsidiaries, or caption omissions. The targeted BOP protest in the early seed is one example of a relevant case outside the later identity-confirmed set.

## 4. Ranked remaining court-record retrieval actions

1. **Menocal current PACER record — critical.** Complete human action #45: obtain the July 13 order and ECF 479, any 482, and 481/483-492. This could change the renewed TVPA motion, trial, stay, or settlement posture.
2. **Reid death-case current record — high.** Complete human action #44: obtain the July 13 settlement entry/outcome, all post-June 5 summary-judgment papers and ruling, ECF 226/227/232-240, and Brunswick County origin record. Preserve sealed/private boundaries.
3. **NWIPC appeals and 2026 ICE contract — high.** Complete human actions #46-47: resolve both new Ninth Circuit dockets, stay orders, any Supreme Court petition, and ECF 77 Exhibit F. Extract PIID, value, term, access/control, standards hierarchy, defense-of-suit, and modification clauses.
4. **ICE detainee-labor defense-cost/equitable-adjustment record — high.** Pursue new lead #63588: authenticate the May 30, 2018 Zoley letter, ICE responses/denials or later payment/referral, and relevant Aurora/NWIPC/Adelanto contract clauses. This is the missing ICE-side test of Hartel's pleaded reimbursement theory.
5. **Burciaga FCA merits and terminal file — high.** Complete human action #59: retrieve the complaint, ECF 41, ECF 70-75, and terminal record to identify the alleged false claim, payer/contract, ACA-audit context, intervention posture, holdings, dismissal terms, and any payment. Do not presume an ICE/DHS nexus.
6. **Delaney Hall state charge and ICE contract — high.** Complete human actions #49-51: obtain municipal complaint S 2025 5303 and disposition, the complete February 2025 ICE contract/ECF 19, unavailable inspection exhibits, and the April 17 transcript.
7. **Novoa current stay/final-merits record — high.** Complete human action #57: retrieve ECF 607-610 and useful clarification filings, then determine whether certiorari/CVSG is the parties' stated reason for continued stay and whether trial/remedies moved.
8. **Residual deaths and detention conditions — high.** Deep-read complaints and dispositive/current filings for the highest-scored active medical/death-routed dockets (*Patterson*, docket 70844088; *Garcia*, 72097949; *Okoroafor*, 73178988) and the strongest unreviewed ICE/DHS conditions/FOIA dockets, including *Mendez*, 66846016, and *Detention Watch Network*, 4522862. Metadata routing must be verified from text.
9. **Employee-wage terminal records — medium-high.** Obtain the *Lewis*, *Mayes*, *Giles*, state *Perez*, *Mazzei*, and *Burch* agreements and approval/dismissal records to recover gross/net amounts, class/collective scope, releases, practice changes, and no-admission clauses. Do not combine detainee labor with employee payroll.
10. **Salus CSRO protest/contract/Trump-ties record — high comparator.** Complete human action #70: seek the signed solicitation/award/modifications, J&A/D&F, source-selection and OCI record, option documentation, GAO file, partners/subawards, performance records, CARE entity bridge, and releasable political-appointee communications. Preserve the current no-GEO/no-political-bridge result as bounded.

Lower-priority acquisition remains warranted for legacy commercial terminal documents and resolution of the five same-name cases, but neither outranks the ICE/DHS, death, detainee-labor, FCA, and current-appeal actions above.

## Database and QA disposition

- One narrowly scoped lead was created: **#63588**, open/high, thread 113, with three evidence links. No new finding was created because the audit did not establish a new source fact.
- Existing top actions are already represented by human actions #44-47, #49-51, #54-55, #57, #59, and #70.
- Papercut #1018 records that `lead_tracker.py search` failed to return newly created exact-title lead #63588 even though the row and evidence links exist in SQLite.
- The database foreign-key-check baseline remained **64** before and after the audit write. `PRAGMA quick_check` returned `ok`.
- This audit used no HigherGov data and made no new external CourtListener/PACER queries.

The companion CSV is the machine-readable cluster/gap matrix. The JSON manifest maps source artifacts, DB records, and finding IDs. The SHA-256 ledger hashes the three substantive audit outputs and the source artifacts relied on.
