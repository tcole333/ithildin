# FOIA queue review — 2026-07-28

**Scope:** all 45 pending `human_actions` rows with `action_type='foia_request'` plus the 6 drafted-but-untracked requests in
`investigations/tech-right/reports/2026-07-26-foia-queue-ice-skip-tracing-uac.md` (51 total). Reviewed for legal viability,
custodian correctness, scope/breadth problems, and self-containment. Submission channels verified by web check on 2026-07-28
(section at end).

**Legend:** FILE = ready as-is or with trivial edits · FIX = one named fix, then file · SPLIT/REROUTE = restructure before filing ·
PREP = text must be assembled first · REPLACE = dead end as written, alternative route given · TRACK = not a new request.

---

## Summary table

| # | Target | Verdict | Core issue |
|---|--------|---------|-----------|
| 4 | IPI internship visa records | **REPLACE** | Individual visa records are confidential by statute (INA §222(f)); rewrite as program-sponsor request |
| 12 | IPI Schedule B via NY AG | **REPLACE** | NY suspended Schedule B collection post-*Bonta* (2021); never publicly releasable — dead end |
| 13 | USCIS GEN-10321032 (Marinese) | TRACK | GEN- prefix = **Genealogy Program case, not FOIA** — status at genealogy.uscis.dhs.gov, not FIRST; index search averages 191 business days |
| 23 | Franklin County Sheriff (SAT) | FIX | Add retention-schedule/disposition ask; expect uncharged-suspect redactions (Ohio CLEIR) |
| 24 | Ohio IG (Sturtz files) | FIX | Investigative files largely confidential; target final reports + State Archives transfer |
| 31 | FDIC/RTC Grand Chevrolet | FILE | Finding-aid-first approach is correct; all RTC records stayed with FDIC (no NARA transfer — RG 484 is an empty shell) |
| 37 | DHS OIG Rec-7 closure | FILE | Narrow, right custodian |
| 38 | ICE Golden State invoices | FIX | Add Exemption-4 fallback (monthly totals if unit prices withheld) |
| 39 | Joe Corley / Fund 222 | SPLIT | Two custodians, five record families — split ICE vs. Montgomery County TX |
| 40 | Val Verde CBP/county | FIX | USMS IGA mods are a DOJ record — get county's copy or add USMS request |
| 41 | RGV GEO-CBP packages | FILE | — |
| 42 | Maverick BPA call | FILE | 2015–16 contract files may be past retention; ask for disposition status if no records |
| 43 | Ballard-GEO contacts | SPLIT | DHS/ICE part is filable now; NARA/Trump Library part faces PRA 12-year restrictions — file as placeholder |
| 50 | Delaney Hall Feb-2025 contract | SPLIT | ECF 19 is a court record → PACER now; ICE FOIA for full contract separately |
| 53 | California City acquisition file | FILE | — |
| 60 | GEO performance-consequence files | SPLIT | 5 IDVs × 8 OIG reports × ~10 record types in one request — split by facility |
| 61 | Folkston ICE/Charlton | FILE | — |
| 62 | 70CDCR20R00000002 competition | SPLIT | Split acquisition record vs. utilization data (different program offices) |
| 63 | ICE Air P00005 / Classic Air | FILE | — |
| 64 | Venturella appointment records | FILE | Strong — appointment/delegation instruments are classically releasable |
| 65 | Venturella ethics / Warren response | FIX | Terminology: request the OGE Form **278e** report; Form 201 is the request form, not a record |
| 66 | Venturella GEO-matter participation | FILE | — |
| 67 | ISAP V item 42 | FILE | — |
| 68 | GTI/CSI subcontract financials | FILE | Pre-conceding security fields is smart drafting |
| 69 | OGE identity-neutral trade records | FILE | Novel framing but lawful; expect category-level answers |
| 70 | Salus CSRO omnibus | SPLIT | Four agencies in one action — must be four requests (GAO piece is not FOIA) |
| 71 | ICE Air Round-4 operators | FILE | Keep ICE primary; DOJ Civil litigation files will draw Exemption 5 |
| 72 | Homan ethics screen | FILE | Correctly bounded to agency-held; expect thin yield (WH not FOIA-covered) — null result meaningful |
| 73 | Guidepost–B.I. agreement | FILE | — |
| 74 | GEO CLIN pages (4 facilities) | FILE | Best-drafted request in the queue |
| 75 | Adelanto/Desert View package | FILE | — |
| 76 | GEO-CDR BAKER members | FIX | Sunbiz images are self-serve — download now; file only the FDEM/MFMP part |
| 77 | FDEM PO-010844 / warrants | FIX | Add FL Dept. of Financial Services as custodian for warrant clearance (FLAIR is DFS's) |
| 79 | Parlatore grade determination | REROUTE | Third-party personnel records — expect denial. PN check ran: none exists, and that's legally normal (O-5 = President alone) — FOIA is the only route |
| 80 | Parlatore orders/points/DD-214 | REROUTE | DD-214 not third-party releasable; rewrite around the no-consent list (source of commission, promotion sequence number, date of rank…) |
| 81 | Parlatore ethics approvals | REROUTE | Wrong custodian: JAGINST 5803.1 approvals live with the command + OJAG Code 13 — DON FOIA, not DoD SOCO |
| 82 | ISAP IV/V performance-remedy | PREP | Scope lives in rejected infra #150 — expand text before filing; CPARS line will be denied |
| 83 | 26-SOL-DCR-01 first tasks | PREP | Expand from infra #151; cross-reference Ballard Green protests (report item 1) when filing |
| 84 | Five GEO acquisition families | PREP | Expand from infra #152 |
| 85 | ISAP privacy approvals/ATOs | PREP | Expand from infra #153; unpublished PTAs are the right target |
| 87 | CIA Ruemmler medal | PREP | **Drafted request language is lost** (tmp workdir wiped); re-draft from lead 68444 residual list |
| 88 | MDE PIQC demand/recovery | FILE | Right statute (MGDPA); expect §13.39 withholding on live-litigation items |
| 89 | USDA FNS PIQC oversight | FILE | — |
| 94 | Zampolli notification/ethics | FIX | Congressional committees are not FOIA-subject — reframe that part as a voluntary ask; cite pending F-2025-18993 |
| 96 | SSA OIG Solly disposition | FIX | SSA OIG has no separate FOIA intake — file via SSA central portal (securefoia.ssa.gov) captioned "records of the OIG"; expect 7(A)/7(C) redactions |
| R1 | Ballard Green protest file (GAO) | FIX | GAO is not FOIA-subject — 4 C.F.R. Part 81 records request; protective-order material unreachable |
| R2 | SOSi letter-contract J&A | FILE | Pre-check done: **J&A never posted to SAM.gov** — cite the FAR 6.305 posting failure in the request |
| R3 | UAC evaluation record | FILE | Expect heavy Exemption 5; Factor-4 fallback already drafted |
| R4 | Fraud Inc / Gravitas CPARS | REROUTE | FAR 42.1503(d) + Pub. L. 111-212 §3010 bar CPARS release — lead with cure/show-cause/change-order file instead |
| R5 | Delaney Hall emergency J&A | FILE | Pre-check done: **never posted** despite exceeding the SAT — cite FAR 13.501(a)/6.305 in the request; cross-reference #50 |
| R6 | UAC PIA/SORN | FILE | Pre-check done: **no PIA/SORN exists** for a live program collecting data on ~100K minors — the null is documented; FOIA now targets the PTA + retention schedule |

R1–R6 = the six items in the 2026-07-26 tech-right report, which are **not yet tracked in `human_actions`**.

---

## Queue-wide issues

### 1. Six drafted requests are untracked
The tech-right report items (R1–R6) exist only in the markdown report. Add them to `human_actions` so the queue has one
source of truth. Suggested: one row each, `action_type='foia_request'`, priority high for R1–R3, medium for R4–R6.

### 2. Action #87's request language is gone
Lead 68444's findings say "Exact CIA FOIA request language drafted in /tmp/osint-DEOMQeBu/report-68444.md" — that workdir
no longer exists. Only the component list survives (certificate, final citation, nomination/approval packet, Brennan
2015-01-08 schedule, ceremony/photo records). The request must be re-drafted. Lesson for the queue: **never leave the only
copy of drafted request language in a session tmp dir** — paste full text into the `description` field or a repo file.

### 3. Four actions are not self-contained
#82–#85 say "described in infra request #150/151/152/153" — those infra rows are status `rejected` (they were converted,
and rejection was the conversion mechanism), so the scope text survives only there. Before filing, expand each action's
text from the infra row so the request stands alone. Same class of problem as #87, one step less severe.

### 4. Third-party privacy walls (Parlatore cluster, #79–81)
Military personnel records of a living current reservist are Privacy Act-protected; a third-party FOIA gets only the
"releasable without consent" categories. DD-214s (#80) are categorically not third-party releasable until archival
(62 years post-separation); grade-determination memos and point records will draw Exemption 6 denials.
- **Senate-confirmation check: RAN, and the answer changes the plan.** No PN for Parlatore exists anywhere in the
  118th/119th Congress (API sweep + zero Congressional Record full-text hits). But this is legally **normal**: 10 U.S.C.
  §12203(a) post-ROPMA requires Senate confirmation only for reserve grades **above O-5** — O-5 appointments are "by the
  President alone" (current Navy Reserve PN scrolls confirm: all are "to be Captain"). Two consequences: (a) there is no
  free public record of the appointment — the FOIA to Navy is the *only* route to the instrument; (b) the press claims
  that the commissioning "bypassed the Senate" (Washington Times 2026-05-05, MSNBC) are legally confused on this point —
  **do not promote that framing into findings**.
- The no-consent releasable list is broader than assumed and includes **source of commission, promotion sequence number,
  date of rank, dates of service, duty assignments, salary, military education, and awards** (NPRC/DoD published lists).
  A #80 rewritten around exactly those elements gets a useful skeleton — date-of-rank + source-of-commission lets you
  *infer* constructive credit (10 U.S.C. §12207) even if the computation paperwork is withheld.
- Custodian: Navy Personnel Command (BUPERS-00J FOIA office; PERS-912 for points) via DON's portal — NOT NPRC, which
  only holds separated members' records.
- #81's custodian is wrong as drafted: DoD SOCO serves OSD-level personnel only. Outside-practice-of-law approvals for a
  Navy JAG officer are processed under **JAGINST 5803.1** through the member's command and **OJAG Code 13** (Administrative
  Law; ethics counselors) — route via DON FOIA addressed to OJAG (Code 20 FOIA branch), keep OSD/JS (pal.whs.mil) only as
  a secondary if an OSD billet emerges. His documented tie to the SECDEF's office (sworn in by Hegseth personally, per
  press) is the one fact that keeps an OSD/SOCO copy plausible.

### 5. Overbroad single requests invite fee estimates and "reasonably describe" bounces
#39, #60, #62, #70 each bundle multiple custodians or record families. ICE in particular will respond with a fee estimate
or narrowing demand, which costs a full processing cycle. Split before filing (specific splits in per-item notes).
#70 must be split regardless — it names four different agencies, and the GAO piece isn't even FOIA.

### 6. Two legal-gate losers are in the queue as written
- **#12 (NY AG Schedule B):** confirmed dead end with the full chronology: the Charities Bureau **never** made
  public-charity Schedule B publicly inspectable (confidentiality upheld in *Citizens United v. Schneiderman*, 2d Cir.),
  suspended collection 2021-07-30 after *AFP v. Bonta*, and since 2022-03-16 accepts only name-redacted Schedule B
  (amended 13 NYCRR §91.5). A FOIL request for 2010–2020 donor names will be denied. Replace with: (a) funder-side
  990-PF grant-schedule mining (extend beyond the three known funders — note private foundations' donor schedules ARE
  public in their own 990-PFs), (b) government-donor grant registries — IPI's donor base is heavily governmental and
  Nordic aid portals publish grants (Norway MFA/Norad databases are public and IPI's Norway relationship is already a
  thread).
- **#4 (IPI visa records):** visa issuance/refusal records are confidential under INA §222(f); State denies these
  categorically, and USCIS third-party records of unnamed living individuals go nowhere. Rewrite at the program level:
  State ECA exchange-visitor (J-1) **sponsor file for IPI** — designation applications, annual reports, compliance and
  incident correspondence — plus ICE SEVP aggregate SEVIS statistics for the sponsor. Program records avoid the individual
  privacy bar entirely.

### 7. CPARS asks will be denied — everywhere they appear
FAR 42.1503(d) restricts completed past-performance evaluations to government personnel and the evaluated contractor
during the source-selection use window (3 years; 6 for construction/A-E), and past-performance reviews are statutorily
excluded from public availability by §3010 of Pub. L. 111-212 (cited in FAR 42.1503(h)(2)) — the official CPARS Guidance
says flatly they are "not releasable under FOIA." Expect Exemption 3/5 denials. Affects R4 (primary target) and CPARS
lines inside #60/#82. FAPIIS *integrity* records (terminations for default/cause, defective pricing) are public, by
contrast — a useful substitute ask.
Restructure to lead with what is releasable: cure notices, show-cause letters, contract discrepancy reports, QASP records,
the $0 change-order file, deduction/withhold records. Keep CPARS as a secondary line-item so the denial is documented.

### 8. Trump-era White House records: newly possible, mostly restricted
#43's Presidential Library component became legally possible on 2026-01-20 (PRA five-year mark for the 2017–21 term). But
the P2 (appointments) and P5 (confidential advice) restriction categories run 12 years — to January 2033 — and cover most
of what #43 wants from the WH side. File it anyway as a queue-position placeholder with expectations set at years, and put
the real weight on the DHS/ICE half of the request.

### 9. Refresh date ranges at filing time
#64–66 and others bound their ranges "through 2026-07-14" (the drafting date). Update end dates to the actual filing date
or "through the date the search is conducted" — otherwise the two-week gap is silently lost.

### 10. Stale FK notes
Several rows' notes claim `related_lead_id` was left NULL because of the legacy `leads_old_backup` FK (papercuts #854/#917/
#946/#956), but the column is now populated on those same rows (#37, #38, #61, #67, #82–85…). The FK repair evidently
landed and was backfilled. Harmless, but strip the stale sentences next time the rows are touched.

### 11. Volume strategy at ICE
Roughly 30 of the 51 requests go to ICE. Filed simultaneously they risk fee aggregation (related requests from one
requester can be aggregated for fee purposes) and practical slow-walking. Recommendations:
- Batch by program: (a) GEO detention pack, (b) ICE Air pack, (c) skip-tracing/UAC pack, (d) ethics/personnel pack.
- Stagger batches by 1–2 weeks.
- File the public-interest flagships (R1, R3, #65/#66) through MuckRock so responses are public; keep the
  competitive-sensitive ones direct. Note MuckRock publishes the request text too — that exposes investigative direction.
  Repo MuckRock API creds fail auth (per 2026-07-26 report), so use the web UI.
- Every federal request should include a fee-waiver paragraph (public-interest standard) and claim news-media requester
  category, citing the published dossier record (ithildin.pages.dev) as evidence of dissemination capacity.

### 12. PIID spot-check results (USAspending API, 2026-07-28)
Load-bearing identifiers in the queue were spot-checked against the USAspending award API:
| PIID | Result |
|---|---|
| 70CDCR26C00000001 (R2, SOSi letter contract) | ✓ exact match — SOS INTERNATIONAL LLC, start 2025-10-21, $6,954,758.46, ICE |
| 70CDCR26P00000013 (R5, Delaney Hall fencing) | ✓ exact match — RESPONSE AI SOLUTIONS, LLC, start 2026-05-30, $250,275.48, ICE |
| 70CDCR25FR0000127 (#67, ISAP V task) | ✓ — B.I. INCORPORATED, start 2025-09-30, $108.3M, ICE |
| 70B03C25P00000150 (#40, Val Verde) | ✓ — COUNTY OF VAL VERDE, start 2025-03-21, CBP |
| HSBP1016J00076 (#42, Maverick call) | ✓ — THE GEO GROUP, INC., start 2015-10-01, CBP |
| 70CDCR18DIG000013 (#39, Joe Corley IGSA) | ✗ absent from FPDS under every variant — see #39 note; PIID is from ICE's own mod documents |

### 13. Free pre-checks — RUN 2026-07-28 (full detail: `reports/foia-channels-20260728/report-prechecks.md`)
| Item | Check | Result |
|---|---|---|
| R2 | SAM.gov posting of the SOSi J&A | **Never posted** — 0 results for the PIID; the 26-SOL-DCR-01 notice family has SOW/Sections/Q&A but no J&A. FAR 6.305's window expired Nov 2025. Cite the posting failure in the request — and note DHS's documented practice (Salus case) of posting J&As only after protests |
| R5 | SAM.gov posting of the Delaney Hall urgency J&A | **Never posted**; $250,275.48 sits just above the $250K SAT, so posting was required (FAR 13.501(a)/6.305). Cite in request |
| #79/#80 | congress.gov PN scrolls | **No PN exists — and that is legally normal** for reserve O-5 (§12203(a): President alone). No free verification path; FOIA is the only route. Do not adopt the press "bypassed the Senate" framing |
| R6 | DHS PIA/SORN inventory | **Null confirmed before filing**: no PIA/SORN for the UAC Safety Verification Initiative (program live since 2025-11-14; MVM Inc. awarded ~April 2026 to locate ~100K UACs) and none for skip tracing. Closest: CARIER SORN (89 FR 55638, 2024-07-05) |
| #85 | ISAP privacy coverage | ISAP's only PIA is DHS/ICE/PIA-062 (ATD), last updated **Aug 2023** — nothing covers continuous-location or skip tracing. Cite the stale PIA by number |
| #65 | Warren letter + response | Letter **public** (warren.senate.gov, 2026-05-27); **no ICE/DHS response public** ~7 weeks past the 06-10 deadline — only a DHS statement to NPR (2026-06-03). The FOIA ask stands; attach the letter URL |
| #70 | APFS F2025069952 | **Scrubbed from APFS on 2025-05-18, two days after posting** — the day after CSI Aviation expressed competitive interest (COFC 1:25-cv-1338 complaint ¶28; Wayback-confirmed). The entry survives as complaint Ex. 5; DHS posted a **redacted** J&A on SAM 2025-06-09 (download now). Add an ask for the APFS record + its removal/audit trail — a demonstrably deleted public record |
| #76 | Sunbiz images | Self-serve download, no request needed (not re-run — standing instruction) |
| #50 | PACER/RECAP for ECF 19 | Court record, not FOIA (not re-run — standing instruction) |

---

## Per-item notes (where the table needs elaboration)

**#13 (Marinese / USCIS).** GEN-10321032 is a **Genealogy Program** case ID (GEN- prefix = online genealogy receipt), not
a FOIA control number — check status at genealogy.uscis.dhs.gov/#/cases/status/check or Genealogy.USCIS@uscis.dhs.gov,
not in the FIRST FOIA tool. Current genealogy averages: index search 191 business days, record request 300 — a 2025-11-25
filing plausibly runs into early 2027. Deceased-subject release is confirmed by rule (6 C.F.R. §5.21: death certificate
or obituary suffices). If she was born before ~1926 the A-file could already be at NARA Kansas City (100-years-after-birth
transfer rule) — she worked through 2000, so almost certainly still USCIS-held. Keep her SSN out of correspondence; the
A-number + proof of death is all the request needs.

**#31 (FDIC/RTC).** Channel finding that changes the plan: RTC's assets and records transferred to **FDIC** at
termination (1995) and stayed there — NARA's RG 484 is an unpopulated shell and NARA's own schedule note says RTC is
"not subject to the Federal Records Act; contact the FDIC directly." So skip NARA entirely: FOIA FDIC (SecureRelease or
efoia@fdic.gov) for the records inventories/box indices covering the Grand Chevrolet receivership materials, and sweep
archive.fdic.gov + the NARA catalog under predecessor RG 195 (FHLBB) for the little that was accessioned. The old
efoiarequest.fdic.gov form is dead (NXDOMAIN).

**#88/#89 (PIQC).** USDA note: FNS was renamed the **Food and Nutrition Administration (FNA)** on 2026-06-01. File via
efoia-pal.usda.gov (Login.gov required since Jan 2026) or FOIA-FNA@usda.gov; regional-office records are requested
centrally — there is no Midwest-region intake. Practical tip from FNA's own FOIA page: scope to electronic files where
possible ("analysts likely have reduced access to offices where paper files are maintained"). For #88, if MDE withholds
under Minn. Stat. §13.39 (civil investigative data), demand the written active/inactive determination — §13.39 data
become public once the action is inactive.

**#96 (SSA OIG).** SSA OIG has no public FOIA intake of its own — by rule (20 C.F.R. §402.35) everything goes to SSA's
Office of Privacy and Disclosure: securefoia.ssa.gov (FOIAXpress PAL) or FOIA.Public.Liaison@ssa.gov. Caption the request
"records of the Office of the Inspector General" so OPD tasks OIG. Do not use the OIG Touhy inbox (litigation subpoenas
only).

**#23 (Franklin County Sheriff).** Ohio case law cuts both ways: *State ex rel. Caster v. Columbus* (2016-Ohio-8394)
ended CLEIR protection at "completion of the trial," so closed *tried* 1990s cases are largely releasable — but
**uncharged-suspect identities stay exempt indefinitely** (applied as recently as *Mash v. Marysville*, 2026-Ohio-498),
which is exactly the posture of names like Wexner/Smith if never charged. Draft should: cite ORC 149.43 and *Caster*,
note the cases are closed, ask for segregable portions, and **file a first request for the RC-2 retention schedules and
RC-3 disposal certificates** covering investigative records 1988–2000 — if the files were lawfully destroyed, the
disposal certificate is the finding. Denials must cite legal authority with each redaction individually justified
(their own published standard). 5¢/page confirmed.

**#24 (Ohio IG).** Ohio IG investigative files are confidential by statute; final reports are public. Sturtz-era
(1988–94) material may have been transferred to the State Archives (Ohio History Connection) or destroyed. Three-pronged
approach: (1) all final reports 1988–1994 referencing SAT/Rickenbacker/Wexner, (2) retention/transfer status of that era's
investigative files, (3) parallel inquiry to Ohio History Connection.

**#38 (Golden State).** Post-*Argus Leader*, Exemption 4 fights over unit prices are the norm. Add: "If unit prices are
withheld under Exemption 4, release monthly invoice totals, quantities, and the deduction/credit fields, which correspond
to obligations already published in FPDS."

**#39 (Joe Corley).** Split: (a) ICE FOIA — task orders/mods under 70CDCR18DIG000013 + invoice images and payment dates
for the three named payments (P00020 $10,185.41 / P00040 $8,137.37 / P00043 $482,237.02); (b) Montgomery County TPIA —
Fund 222 ledger, GEO management amendments, current payee and fee schedule. County bank statements are gettable under
TPIA but will draw redaction and labor charges; ask for the ledger and vendor-disbursement register first.
PIID caveat (verified 2026-07-28): 70CDCR18DIG000013 returns nothing on USAspending under award or IDV type codes, in
either the DIG or D1G spelling, and HigherGov exact-ID queries were already negative (findings #12658/#12660) — the IGSA
is simply unreported to FPDS. Add a line to the ICE request: "This inter-governmental service agreement may not appear in
FPDS; it is identified in ICE modification documents P00020, P00040, and P00043" — this preempts a no-records response
based on an FPDS-only lookup.

**#43 (Ballard-GEO).** The DHS-HQ/ICE communications request is well-scoped (named custodians, named search terms,
bounded dates). Expect a long haul and "still interested?" letters — calendar a response cadence. NARA piece: the Trump
Library enforces **one topic per request**, so the calendars/correspondence/ethics bundle must be split into separate
single-topic submissions; NARA's first release tranche (notice PA 2026-099, 2026-07-23) confirms P2 (appointments) and
P5 (advice) restrictions are actively applied, and the April 2026 OLC opinion declaring the PRA unconstitutional adds
regime risk. File as early queue placeholders (FIFO), draft each with multiple phrasings ("sent to or from" vs "related
to" — the library has already given contradictory no-records answers on phrasing), and expect years.

**#62 (70CDCR20R00000002).** Split acquisition-record request (acquisition plan → debriefings) from the utilization
request (ADP/manifests/billed bed-days) — different custodial offices, and the source-selection material will draw
Exemption 5 and procurement-integrity withholding regardless. Offeror identities and question-submitter identities are
frequently withheld; keep them as line items but don't anchor the request on them.

**#65 (Venturella ethics).** Two edits: (1) request "public financial disclosure reports (OGE Form 278e and any 278-T
transaction reports)" — OGE Form 201 is the requester's form, not a record; for an ICE Senior Advisor (non-PAS) the 278e
custodian is DHS/ICE ethics, confirmed by the OGE Form 201 instructions (OGE holds only PAS/candidate/White House/DAEO
filings). (2) Cite 18 U.S.C. §208(d)(1) explicitly: §208(b)(1) *and* (b)(3) waivers **must** be made publicly available
on request (procedures via 5 U.S.C. §13107) — that line of the request is not a discretionary FOIA ask. Pre-check
results: Warren's 2026-05-27 letter is public (warren.senate.gov — attach the URL to the request); no ICE/DHS response
has surfaced ~7 weeks past the 06-10 deadline, only a DHS statement to NPR (2026-06-03) that Venturella "abides by all
ethics requirements" — so the response-records ask is live and time-anchored.

**#70 (Salus).** Four filings: (1) DHS HQ FOIA (OPO/PLCY/USM records incl. the APFS crosswalk), (2) ICE FOIA (any
ICE-side records), (3) GAO records request under 4 C.F.R. Part 81 (protest, agency report, ADR/withdrawal
correspondence), (4) State FOIA (Xator/CARE task order 19AQMM23F0766 entity-resolution records). The "Salus-principal
communications with the White House or political appointees" line only reaches records held by FOIA-covered agencies —
keep it inside the DHS/ICE filings, not as its own ask. Pre-check results that upgrade filing (1): APFS entry
F2025069952 was **removed from the public forecast on 2025-05-18 — two days after posting and one day after CSI Aviation
emailed DHS expressing interest in competing** (COFC 1:25-cv-1338 complaint ¶¶24, 28; the entry survives as complaint
Ex. 5, and the Wayback capture of the APFS API confirms the scrub). Add to the DHS request: the APFS record itself, its
change/removal audit trail, and the direction to remove it. Also download now: DHS's redacted urgency J&A posted to SAM
2025-06-09 after the GAO protest (ref. 70RDA225-FY25-00129) — part of what #70 seeks is already public in redacted form,
so the FOIA should target the unredacted version and the redacted-vs-unredacted delta.

**#71 (ICE Air Round 4).** Frame as "agency records corresponding to AR Tabs 91, 92b, 94, 101" — FOIA reaches the
underlying agency records regardless of the court's protective order over the filed versions. Keep DOJ Civil as a
secondary custodian only; litigation-file requests draw Exemption 5 work-product denials.

**#87 (CIA / Ruemmler).** Re-draft around the five components in lead 68444. Glomar reality check: per OGIS guidance the
recognized paths past a neither-confirm-nor-deny response are subject privacy waiver (unavailable — no-contact rule),
proof of death (n/a), **documented official acknowledgment by the agency** (press coverage does not count), or a
public-interest showing. Unless findings 13424–13433 include a CIA-originated acknowledgment of the award, expect Glomar
on the nomination packet and certificate; the Brennan 2015-01-08 schedule and ceremony/photo records framed as *event*
records (not records "about Ruemmler") are the realistic yield — draft the request so those components stand independent
of the personal-records components. foia.cia.gov is dead at DNS (queue note was right — and CIA's own regulation still
cites the dead URL); use the reading-room form, mail, or fax. CIA complex-track average is ~348 days.

**#94 (Zampolli).** House Foreign Affairs / Senate Foreign Relations are not FOIA-subject. Options: voluntary request to
committee staff (works surprisingly often for transmittal records), or wait for archival access rules. Reframe that
component; the State FOIA component should reference pending case F-2025-18993 to preempt a duplicate-request response.

**R1 (Ballard Green / GAO).** Channel is a GAO records request (4 C.F.R. Part 81) to RecordsRequest@gao.gov, not FOIA.
Confirmed mechanics: protesters must file a redacted copy of the protest within 1 day of filing (4 C.F.R. §21.1(g)), so a
releasable redacted protest letter exists in the file for every one of the five protests, and GAO releases redacted
protests and dismissal notices after closure. Protective-order material is never released. Agency reports are due 30 days
after notice (§21.3(c)) and agencies seeking dismissal move before filing one — so for the protests dismissed 2026-01-13
and -01-29, **no agency report exists at GAO**; the underlying agency documents exist only at ICE and must be sought
there. Ask GAO for the docket sheet + all releasable filings for B-424186.1–.5 in one request.

---

## Submission channels (verified 2026-07-28)

Full verification detail with cited URLs: `reports/foia-channels-20260728/` (one file per batch). Essentials:

### The big change: DHS is electronic-only as of 2026-01-22
DHS no longer accepts mail or email FOIA requests department-wide (Federal Register rule 2025-23783). ICE **destroys**
non-qualifying mailed requests. Everything goes through FOIA.gov or a DHS portal. This governs ~35 of the 51 queue items.

| Destination | Queue items | Channel |
|---|---|---|
| **ICE** | #38, #39(a), #43(a) (dual with DHS HQ), #50, #53, #60–68, #70(b), #71, #74–75, #82–85, R2–R6 | **SecureRelease portal — https://www.securerelease.us** (DHS → ICE component). No email/mail intake. Tracking format `XXXX-ICFO-XXXXX`, status in-portal. Fee-waiver + expedited-processing are portal checkboxes with written justification |
| **DHS HQ** (OGC Ethics, OPO, PLCY, USM) | #43(a), #65, #70(a), #72 | SecureRelease — DHS Headquarters/PRIV component. `foia@hq.dhs.gov` is defunct as intake |
| **DHS OIG** | #37 | **Separate portal**: https://foia.oig.dhs.gov (PAL, requires Login.gov). `FOIA.OIG@oig.dhs.gov` is questions-only now |
| **CBP** | #40(a), #41, #42 | SecureRelease — CBP component (FOIAonline is long dead; ignore the stale mail address still on cbp.gov/records) |
| **CIA** | #87 | Reading-room web form https://www.cia.gov/readingroom/foia_request (foia.cia.gov is dead at DNS — the queue note was right); mail: Information and Privacy Coordinator, CIA, Washington DC 20505; fax 703-613-3007. FOIA.gov relay newly listed — verify in UI before relying. Complex-track median 173 days, avg ~348 |
| **State** | #94, #70(d) | PAL portal https://pal.foia.state.gov. Pending F-2025-18993: do NOT resubmit — status via FOIAStatus@state.gov / (202) 261-8484 citing the case number |
| **NARA / Trump Library** | #43(b) | Online form at trumplibrary.gov/research/submit-foia-request or trump.library@nara.gov. **One topic per request** — #43(b) must be split into single-topic requests. FIFO queue; first tranche (PA 2026-099, 2026-07-23) confirms P2/P5 restrictions actively applied; DOJ's April 2026 OLC opinion clouds the whole regime. Expect years |
| **GAO** | R1, #70(c) | **Not FOIA** — 4 C.F.R. Part 81 records request to **RecordsRequest@gao.gov** citing the B-number, after protest closure. Redacted protest letters + dismissal notices are obtainable (a redacted protest copy exists by rule from day 1); protective-order material never. For the protests dismissed 2–4 weeks in, the agency report was almost certainly never filed — those documents only exist at ICE |
| **OGE** | #69 | FOIA: usoge@oge.gov (or mail: OGE FOIA Officer, Suite 750, 250 E St SW, Washington DC 20024 — they moved). Financial disclosures via OGE Form 201 online system only for PAS/WH/DAEO filers |
| **DHS/ICE ethics (disclosures)** | #65 | Venturella is non-PAS → his 278e/278-T sit with DHS/ICE ethics, not OGE. Request via OGE Form 201 to the agency or fold into the SecureRelease FOIA. §208(b)(1)/(b)(3) waivers are public-on-request per 18 U.S.C. §208(d)(1) — cite it |
| **DOJ Civil** | #71 (secondary) | Civil Division page on FOIA.gov; include case name, citation, court (Classic Air Charter v. U.S., No. 1:25-cv-286, Fed. Cl.) |

**Third-party identity mechanics (DHS family):** requests *about* named individuals (Venturella, Homan) target
official-capacity records, not Privacy Act personal records — no consent form needed, but say so explicitly in the request
("this seeks official-capacity records; no first-party consent is required") to preempt an administrative closure asking
for a Certification of Identity.

| Destination | Queue items | Channel |
|---|---|---|
| **Navy (DON)** | #79, #80, #81 | **SecureRelease** (yes, same portal — select U.S. Navy), record holder = Navy Personnel Command/BUPERS-00J (Millington), PERS-912 for points. NPRC is wrong for a current reservist. #81 → address to OJAG (Code 20 FOIA branch; Code 13 = ethics counselors) |
| **OSD/JS (SOCO)** | #81 (secondary only) | Own portal: https://pal.whs.mil — covers OSD/Joint Staff incl. SOCO; mail 1155 Defense Pentagon, DC 20301-1155 |
| **SSA** | #96 | Central portal https://securefoia.ssa.gov (or FOIA.Public.Liaison@ssa.gov) — caption "records of the Office of the Inspector General"; SSA OIG has no separate FOIA intake |
| **USDA FNA** (ex-FNS, renamed 2026-06-01) | #89 | https://efoia-pal.usda.gov (Login.gov required since 2026-01-09) or FOIA-FNA@usda.gov; regional records filed centrally |
| **FDIC** | #31 | SecureRelease (select FDIC) or efoia@fdic.gov; old efoiarequest.fdic.gov is dead. RTC records are FDIC-held — do not route to NARA |
| **USCIS** | #13 | Status of GEN-10321032 (Genealogy case): https://genealogy.uscis.dhs.gov/#/cases/status/check or Genealogy.USCIS@uscis.dhs.gov. Regular FOIA: first.uscis.gov |
| **NY AG** | #12 | FOIL portal ag.ny.gov/i-want/make-foil-request — but Schedule B route is closed (see issue 6); use only for other registry material |
| **Ohio IG** | #24 | watchdog@oig.ohio.gov, (614) 644-9110 — no portal. Reports public; files confidential (ORC 121.44). 1988–94 era: RIMS retention lookup + Ohio History Connection State Archives |
| **Franklin Co. Sheriff (OH)** | #23 | FCSOPublicRecords@franklincountyohio.gov or (614) 525-6096; mail Attn: Public Records, 370 S. Front St., Columbus 43215. Request RC-2 schedules + RC-3 disposal certificates first |
| **Minnesota MDE** | #88 | mde.datapractices@state.mn.us (Data Practices Compliance Official, 400 NE Stinson Blvd, Minneapolis 55413). Inspection free; ≤100 pages = 25¢/side |
| **Florida** | #76, #77 | FDEM: Records@em.myflorida.com · MFMP POs: publicrecords@dms.myflorida.com (DMS) or the buying agency · FLAIR/warrants: **DFS** PublicRecordsRequest@myfloridacfo.com — after free self-serve (DFS Vendor Payment History, Transparency Florida). Name both FLAIR *and* Florida PALM in date-spanning requests (mid-cutover) |
| **Montgomery Co. (TX)** | #39(b) | mcao.pia@mctx.org (contracts; 501 N. Thompson, Suite 300, Conroe 77301) · **County Auditor** for Fund 222 ledgers · mcsoopenrecords@mctx.org for sheriff/jail records. TPIA: response "promptly," AG-ruling deadline 10 business days |
| **Val Verde Co. (TX)** | #40(b) | Online form at valverdecounty.texas.gov/148/Transparency or County Clerk, PO Box 1267, Del Rio 78841. MuckRock-observed average response ~55 days |
| **Charlton Co. (GA)** | #61(b) | mnettles@charltoncountyga.gov (County Clerk; cc hraulerson@charltoncountyga.gov), county Open Records form attached; GORA 3-business-day rule |
| **MuckRock** (optional overlay) | R1, R3, #65/#66… | $20/4 requests; files federal + state + local. **Public by default** (no embargo on basic tier) — use for the deliberately-public filings only; direct portals for everything competitively sensitive. API creds broken → web UI |

---

## Recommended filing order

**Now (ready, high yield — pre-checks done):** #37, #53, #61, #63, #64, #65 (after edit), #66, #67, #68, #69, #71, #72,
#73, #74, #75, #88, #89, #96 (via SSA central), #31, R2, R3, R5, R6; R1 as GAO records request.
**After prep:** #82–85 (expand scope from infra #150–153), #87 (redraft), #38/#40/#76/#77/#23/#24/#94 (named fixes),
#41, #42.
**After splitting:** #39, #60, #62, #70, #43 (DHS/ICE now; NARA placeholders split one-topic-each), #50 (PACER first).
**Rework or replace:** #4, #12, #79, #80, #81, R4.
**Tracking only:** #13 (genealogy status channel, not FIRST).

Suggested ICE batching to avoid fee aggregation: **Batch A** (ethics/personnel): #64–66, #72–73 · **Batch B** (skip-
tracing/UAC): R2, R3, R5, R6, #67, #83, #85 · **Batch C** (GEO detention): #38, #53, #61, #74, #75, then the #60/#62
splits and #82/#84 · **Batch D** (ICE Air): #63, #68, #71. Stagger 1–2 weeks apart.
