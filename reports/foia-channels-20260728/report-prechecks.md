# Pre-FOIA Public-Availability Checks (as of 2026-07-28)

(Persisted by orchestrator; subagent file writes are hook-blocked.)

> **CORRECTION (2026-07-28, orchestrator):** Item 3's legal implication is WRONG. 10 U.S.C. §12203(a) post-ROPMA requires
> Senate confirmation only for reserve appointments in grades ABOVE O-5; O-5 (CDR) and below are "by the President alone."
> Verified against the statute text and 119th-Congress Navy Reserve PN practice (all §12203 scrolls are "to be Captain") —
> see `report-channels-dod-misc.md` §1, which controls. The PN-negative RESULT stands (no PN exists), but it is legally
> NORMAL for an O-5 reserve appointment, and the press claims that the commissioning "bypassed the Senate" are legally
> confused on this point — do not promote that inference into findings.

Methods: SAM.gov queried via its public search API (`sam.gov/api/prod/sgs/v1/search/`, requires `Accept: application/hal+json`); exact-ID queries returning zero are reliable. Congress.gov website bot-blocks (403), so the official api.congress.gov API + GovInfo full-text search were used. Nothing was submitted.

**Verdicts:**
1. J&A for 70CDCR26C00000001 (SOSi skip tracing): NOT-FOUND — never posted to SAM.gov; FAR 6.305 window expired Nov 2025.
2. Urgency J&A for 70CDCR26P00000013 (Delaney Hall fencing): NOT-FOUND — never posted; 30-day window expired ~2026-06-29.
3. Parlatore Navy Reserve PN: NOT-FOUND — no PN exists in the 118th/119th Congress; zero Congressional Record hits; corroborates reporting that the 3/7/2025 commissioning bypassed the Senate.
4. DHS PIA/SORN: NOT-FOUND for UAC "Safety Verification Initiative" and for skip tracing; ISAP covered only by DHS/ICE/PIA-062 (2023, Aug-2023 update, nothing newer); closest SORN = DHS/ICE-011 CARIER (89 FR 55638, 7/5/2024).
5. Warren 5/27/2026 Venturella letter: YES-PUBLIC (letter + press release on warren.senate.gov); ICE/DHS response: NOT-FOUND anywhere public.
6. APFS F2025069952: NOT ACCESSIBLE — removed from APFS 5/18/2025 (Wayback-confirmed scrub); contents reconstructed from CSI Aviation v. US, COFC 1:25-cv-01338 complaint.

## 1. J&A for ICE letter contract 70CDCR26C00000001 — NOT-FOUND (not posted)

- SAM.gov search for `70CDCR26C00000001`: 0 results (active + archived).
- Only notice family under `26-SOL-DCR-01` is the Solicitation "Skip Tracing Services" (posted 2025-11-10, amended through 11-20, due 11-24): https://sam.gov/opp/bc8d7837d72149479146485298ff5ed5/view (original version id `58bc65a42ae94a36856d46bc72652176`). Attachments: SOW (+Amd 2), Sections B–M (+Amds 1–2), Q&A — no J&A. Related RFI `26-SS-DCR-01`: https://sam.gov/opp/ba672b1263504509be2fa823ee9b6725/view
- Type-filtered search of ALL "Justification" notices mentioning skip tracing: 9 hits, none ICE, none skip tracing.
- Award confirmed in FPDS/USAspending: signed 2025-10-21, $6,954,758.46, SOS INTERNATIONAL LLC, "TO AWARD A LETTER CONTRACT FOR SKIP TRACING SERVICES…", NOT COMPETED: https://www.usaspending.gov/award/CONT_AWD_70CDCR26C00000001_7012_-NONE-_-NONE-/ (mirrors: govtribe.com/award/federal-contract-award/definitive-contract-70cdcr26c00000001; highergov.com/contract-opportunity/skip-tracing-services-26-sol-dcr-01-o-52176/)
- Timeline point: the sole-source letter contract (10/21) predates the public IDIQ solicitation (11/10–20). Pattern evidence: in the CSI Aviation protest (item 6), DHS's urgency J&A stated the action "will not be published at SAM.gov… exempt… per FAR 5.202(a)(2)" — documented practice of withholding postings; there DHS posted a redacted J&A only after a GAO protest.

## 2. Urgency J&A for ICE PO 70CDCR26P00000013 — NOT-FOUND (not posted)

- SAM.gov search for `70CDCR26P00000013`: 0 results. J&A-filtered searches for "Delaney" (17 hits) and "fencing lighting" (189 hits): none ICE/Delaney/Newark 2026.
- Award confirmed: signed 2026-05-30, $250,275.48, RESPONSE AI SOLUTIONS, LLC, "EMERGENCY FENCING AND LIGHTING AT DELANEY HALL DETENTION FACILITY, NEWARK NEW JERSEY," NOT COMPETED: https://www.usaspending.gov/award/CONT_AWD_70CDCR26P00000013_7012_-NONE-_-NONE-/
- Nuance: $250,275.48 is just above the $250K SAT; a FAR 13.5 commercial sole source still requires posting per FAR 13.501(a)/6.305 — only a ≤SAT action would escape it.

## 3. Parlatore PN (Feb–Apr 2025) — NOT-FOUND (no PN exists)

- Congress.gov API sweep of all 119th (~1,750) and 118th (~2,750) nominations: "Parlatore" in no description.
- GovInfo full-text of the Congressional Record — where every nomination scroll's names print: "Parlatore" = 0 hits (control "Hegseth" = 255 CREC hits; "Parlatore" across all GovInfo = 63, all USCOURTS records incl. NYT v. DoD FOIA case).
- Timeline: no Navy military scrolls existed at all Feb–Apr 2025 in the 119th Congress; only civilian Navy PNs (PN12-36 Phelan/SECNAV confirmed 3/24/25; PN26-10 Cao; PN60-12/-17). First Navy officer scrolls: received 2025-05-22 (PN189+), confirmed 2025-06-29.
- Press: Hegseth personally swore Parlatore in as Commander on 3/7/2025; May-2026 reporting says the commissioning "bypass[ed]… the U.S. Senate" (washingtontimes.com/news/2026/may/5/hegseths-legal-aide-prompts-new-democrat-attack/ ; ms.now/rachel-maddow-show/maddowblog/pete-hegseth-appoints-personal-lawyer-powerful-pentagon-post-rcna196431 ; redstate.com/streiff/2025/03/08/hegseths-navy-jag-nomination-is-another-bold-choice-that-indicates-huge-changes-ahead-n2186439).
- Implication: 10 U.S.C. § 12203(a) requires Senate confirmation for reserve O-5+ appointments. No PN → the appointment instrument/legal review exists only inside DoD/Navy — strengthens a FOIA to Navy/OSD for the scroll, SECNAV memo, and accession/constructive-credit paperwork.

## 4. DHS privacy inventory — NOT-FOUND for (a)/(b); closest-only for (c)

Checked full ICE PIA inventory (PIA-001 → PIA-067) at https://www.dhs.gov/privacy-documents-ice and SORNs at https://www.dhs.gov/system-records-notices-sorns.

- (a) UAC "Safety Verification Initiative" (70CDCR26R00000015): NO PIA/SORN. Program is live — DHS announcement 2025-11-14: https://www.dhs.gov/news/2025/11/14/ice-and-state-local-law-enforcement-287g-partners-launch-initiative-protect ; MVM Inc. awarded ~mid-April 2026 to locate ~100K UACs (Guardian 2026-05-02: theguardian.com/us-news/2026/may/02/ice-contracter-torture-allegations-undocumented-children). Contractor collection of minors' data with no program PIA is itself a notable gap.
- (b) Skip tracing (26-SOL-DCR-01): NO dedicated PIA/SORN. Closest: DHS/ICE-011 CARIER SORN, updated July 5, 2024, 89 FR 55638; DHS/ICE/PIA-015 (EID); DHS/ICE/PIA-044 LeadTrac (+ DHS/ICE-015 LeadTrac SORN, 81 FR 52700); DHS/ICE/PIA-064 (publicly available info/social media).
- (c) ISAP: DHS/ICE/PIA-062 Alternatives to Detention (ATD) — https://www.dhs.gov/publication/dhsicepia-062-alternatives-detention-atd-program ; original March 2023 ("first-ever" per ice.gov/news/releases/ice-announces-first-ever-alternatives-detention-privacy-impact-assessment), only hosted file = August 2023 update (dhs.gov/sites/default/files/2023-08/privacy-pia-ice062-atd-august2023.pdf). No 2024–2026 update covering continuous location monitoring or skip tracing. Newest ICE PIA overall = PIA-067 (Immigration Bond Management Lifecycle).

## 5. Warren letter — YES-PUBLIC; response NOT-FOUND

- Letter (5/27/2026, response due 6/10/2026): https://www.warren.senate.gov/imo/media/doc/warren_ethics_letter_to_david_venturella.pdf
- Press release: warren.senate.gov/newsroom/press-releases/warren-presses-new-ice-acting-director-on-abuse-of-revolving-door-cloud-of-corruption-surrounding-ice-and-trump-admin-seeks-ethics-commitments-amid-conflicts-of-interest/
- No formal ICE/DHS response public as of 2026-07-28; only a DHS statement to NPR (6/3/2026) that Venturella "abides by all ethics requirements": npr.org/2026/06/03/nx-s1-5836625/geo-group-private-prisons-ice-close-ties (syndicated: kpbs.org/news/economy/2026/06/03/a-former-geo-group-executive-now-runs-ice-the-companys-government-ties-run-deep). Deadline passed ~7 weeks ago.
- Related: Warren/Raskin 3/29/2026 GEO letter: warren.senate.gov/wp-content/uploads/media/doc/letter_from_sen_warren_repraskinlawmakerstogeogrouponinvolvementindetentionwarehousesystem.pdf

## 6. APFS F2025069952 — NOT ACCESSIBLE (removed); contents reconstructed

- Live APFS API (https://apfs-cloud.dhs.gov/api/forecast/): current 785-record dataset lacks F2025069952; /api/forecast/69952/ → 404 (ID↔suffix mapping verified via F2026073831=id 73831).
- Wayback confirmation of the scrub: the 5/23/2025 API snapshot (web.archive.org/web/20250523134902/https://apfs-cloud.dhs.gov/api/forecast/, 872 records) contains neighbors 69949 and 69960 but not 69952; the 4/7/2025 snapshot predates posting.
- Per CSI Aviation, Inc. v. United States, COFC No. 1:25-cv-01338-MHS (Doc. 17, filed 8/13/2025; documentcloud.org/documents/26100057-csi-v-salus-complaint-from-docket/): ¶24 — posted "May 16, 2025 at 1:21 pm… describing the acquisition" (entry attached as Ex. 5 to the complaint); ¶28 — "On May 18, 2025, the day after CSI emailed DHS expressing an interest in competing… the Agency inexplicably removed the Acquisition Forecast." Two-day public lifespan.
- The acquisition described: Comprehensive Support to Removal Operations (CSRO) — rushed 3-year $915M single-award IDIQ 70RDA225D00000005 (RFP 70RDA225R0000008) to Salus Worldwide Solutions Corp. for "voluntary self-deportation" support (Project Homecoming/Proclamation 10935; EO 14159), FAR 6.302-2 urgency. DHS later posted a redacted J&A (2025-06-09) after CSI's GAO protest: https://sam.gov/opp/c85929c0a5b049d2a2bc6b7df9dc6469/view (ref. 70RDA225-FY25-00129).
- FOIA implication: the unredacted forecast exists as Ex. 5 in the COFC docket and inside DHS; a FOIA for the APFS record plus its removal/audit trail targets a record DHS demonstrably deleted from public view, with dates pinned by the complaint and the Wayback snapshot.
