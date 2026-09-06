# opus-P — THE ANOMALY BUNDLE

**Agent:** opus-P (Wave 3) · **Date of pull:** 2026-07-27 · **Profile:** tech-right (threads 11/15/16)
**Scope:** (a) Gravitas non-renewal · (b) Capgemini ceiling excess · (c) the four pre-competition instruments ·
(d) Delaney Hall · (e) GEO securities filings · (f) current program state
**Discipline:** read-only DB; no tracker writes; no repo edits. Every claim labelled.
**Work dir:** `/tmp/osint-FRmkNLeM/work-P/` (all raw FPDS XML, solicitation text, SEC text preserved there)

---

## 0. HEADLINE — the six items produced four things bigger than the questions asked

1. **The competed $1.44B program is not where the skip-tracing money went.** ICE has added
   **$86,361,425** of skip-tracing funding to **B.I. Incorporated's sole-source ISAP V electronic-monitoring
   task order** (`70CDCR25FR0000127`, mods P00002/P00003/P00004) — **4.5× the $19,032,607 obligated across
   all fourteen competed awardees combined.** The largest tranche, **+$76,011,425 on 2026-01-27**, was
   previously unknown to this investigation. **CONFIRMED** from FPDS-NG.
2. **The solicitation's own amendment history is the ceiling story.** The program was published on
   2025-11-10 with a **$180,000,000 total program ceiling** and a **$90,000,000 per-IDIQ cap**, and a
   **three-day** response deadline. Amendment 2 (2025-11-19) **deleted the total program ceiling entirely**
   and raised the per-IDIQ cap to $281,250,000. ICE wrote, in its published Q&A: *"The overall ceiling has
   been removed."* The 14 awards then totalled **$1,442,909,640.02 — 8.0× the originally advertised program
   maximum.** **CONFIRMED** from the primary solicitation PDFs.
3. **Gravitas is the wrong suspect.** The one firm ICE dropped is a **licensed, decade-old Ohio private-
   investigations firm** (dba Gravitas Investigations) that **outperformed on outlays two awardees ICE kept**
   (GSS and Bluehawk each disbursed **$0.00** and both got the 60-day extension). Gravitas renewed its SAM
   registration on 2026-01-29 and remains active to 2027-01-27 with no exclusion. There is no termination,
   no de-obligation, no cure notice, and no distress signal. **CONFIRMED**; the "performance failure"
   hypothesis is **REFUTED** on the only performance proxy that exists in public data.
4. **In ICE's published Q&A it told offerors, in writing, that there was no incumbent** — *"Yes this is a
   new requirement"* — while Capgemini, SOSi and B.I. were **already being paid for skip tracing** under
   three separate pre-existing instruments. **CONFIRMED** from the Amendment-2 Q&A PDF and FPDS.

---

## CORRECTIONS TO CANONICAL WAVE NUMBERS

| Canonical claim | Status | Correct position |
|---|---|---|
| "13 of 14 DOs extended +60 days; Gravitas alone not renewed" | **CHANGED** | **12 of 14.** Twelve P00001 extensions signed 2026-03-10/11 (Enprovera 03-10, eleven on 03-11). **Two** were not extended: Gravitas (`FR0000016`, lapsed 2026-03-15) and **Global Recovery Group** (`FR0000032`, PoP 2026-01-16→**2026-04-16**, no mod ever). This matches geo-group finding **#12488** ("12 received parallel 60-day extensions… Gravitas and Global are the two task histories without a visible extension") and corrects SYNTHESIS §1 / #14387. |
| Combined ceiling $1,442,909,640 | **CONFIRMED to the cent** | **$1,442,909,640.02** (sum of 14 FPDS `baseAndAllOptionsValue`, pulled 2026-07-27). |
| Obligated $19,032,607 (1.32%) | **CONFIRMED to the cent** | $19,032,607.00 exactly. **New:** outlays are **$11,878,879.65 = 62.4% of obligations**, 0.82% of ceiling. |
| Capgemini ceiling $365,821,219 | **CONFIRMED, refined** | **$365,821,218.75** (the rounded figure hid $0.25). |
| "Amendment 2 set a per-IDIQ maximum of $281,250,000" | **CONFIRMED, but incomplete** | True — and Amendment 2 *also* raised the guaranteed minimum from **$250 → $7,500,000** and **deleted the $180,000,000 combined program ceiling**. The deletion is the material change. |
| UAC "19 task orders totalling $86,822,317" | **CONFIRMED** | $86,822,317.14 (18 first TOs $85,376,317.14 + MVM `FR0000052` $1,446,000). **New:** those 18 TOs carry **combined ceilings of $10,108,872,474.05**. |
| "The FY2025 10-K gives no dollar value for the skip-tracing award, and that asymmetry is itself reportable" (fable-I §1.5) | **DOWNGRADED** | The no-value fact is **CONFIRMED**, but **GEO quantifies no contract award anywhere in the 10-K's Contract Developments section** — the silence is uniform practice, not singling-out. And GEO **did** give a figure in an SEC-filed exhibit (8-K EX-99.1, 2026-05-06: *"valued at up to $60 million in revenues per year"*). Do not publish this as concealment. See §e.1. |
| "Response AI reported zero subawards" (Delaney Hall) | **WITHDRAWN as evidence** | Per codex-Q: 228 of 228 USAspending-backed ICE prime awards in the geo-group archive report `reported_subaward_count = 0`, in every size band. The field has **zero discriminating power**. Stated below as a base rate, not a signal. |

---

# (a) THE GRAVITAS NON-RENEWAL

## a.1 The complete federal footprint — two transactions, ever

**CONFIRMED.** FPDS-NG ATOM, `VENDOR_UEI:"EJB9AHGV8BD1"`, pulled 2026-07-27
(`work-P/fpds_gravitas_uei.xml`). Gravitas Professional Services, LLC has **exactly two FPDS transactions
in its entire history**, both mod 0, both signed 2025-12-16:

| PIID | Type | Signed | Obligated | Ceiling | PoP end | createdBy | lastModifiedBy | approvedBy |
|---|---|---|---:|---:|---|---|---|---|
| `70CDCR26D00000018` | IDIQ | 2025-12-16 | $0.00 | $32,062,500.00 | — | JBOUDREAUX7012 | JABYAD7012 | SWRAY7012 |
| `70CDCR26FR0000016` | Delivery order | 2025-12-16 | $427,500.00 | $427,500.00 | **2026-03-15** | **JABYAD7012** | **JABYAD7012** | **JABYAD7012** |

- **No modification of any kind exists on either instrument.** No P00001, no termination for convenience or
  default, no de-obligation, no cure notice, no novation, no administrative mod. The delivery order simply
  reached `currentCompletionDate = ultimateCompletionDate = 2026-03-15` and stopped. 2026-03-15 was a
  **Sunday**.
- **The IDIQ is still alive.** `70CDCR26D00000018` has a ceiling of $32,062,500 and no termination. Gravitas
  remains one of fourteen holders of an unexpired ordering vehicle; ICE simply stopped ordering.
- **Gravitas has no other federal work, before or after** — this is its only appearance in FPDS under this
  UEI, and USAspending's recipient search returns the same single award
  (`work-P/us_gravitas_awards.json`).
- **Bonus for opus-O's sweep:** `FR0000016` is another JABYAD7012 create-modify-approve instance
  (created 2026-01-22 16:13:57, approved 16:15:37 — 100 seconds), and so is Capgemini's `FR0000024`
  (created 2026-01-22 16:07:11, approved 16:08:42 — 91 seconds).

## a.2 The money WAS spent — and Gravitas outperformed two firms ICE kept

**CONFIRMED.** USAspending `spending_by_award` with `Total Outlays`, pulled 2026-07-27
(`work-P/us_skip_all.json`), cross-checked against the award-detail endpoint for Gravitas
(`total_outlay = 130769.84`).

| Delivery order | Awardee | Obligated | **Outlaid** | Outlay % | PoP end | +60d ext? |
|---|---|---:|---:|---:|---|---|
| FR0000024 | Capgemini | $4,816,782.50 | $4,755,911.77 | 98.7% | 2026-05-14 | yes |
| FR0000032 | Global Recovery Group | $2,812,500.00 | $1,659,989.29 | 59.0% | **2026-04-16** | **no** |
| FR0000019 | Bluehawk | $2,656,327.50 | **$0.00** | **0.0%** | 2026-05-14 | **yes** |
| FR0000017 | SOSi | $1,642,226.25 | $1,589,893.79 | 96.8% | 2026-05-14 | yes |
| FR0000021 | B.I. Incorporated | $1,624,500.00 | $1,481,823.30 | 91.2% | 2026-05-14 | yes |
| FR0000025 | Omniplex | $1,487,580.00 | $54,296.67 | 3.6% | 2026-05-14 | yes |
| FR0000022 | National Protective Svcs | $909,750.00 | $666,122.68 | 73.2% | 2026-05-14 | yes |
| FR0000023 | Constellation | $767,468.75 | $748,905.25 | 97.6% | 2026-05-14 | yes |
| FR0000018 | GSS | $741,000.00 | **$0.00** | **0.0%** | 2026-05-14 | **yes** |
| FR0000015 | AI Solutions 87 | $636,500.00 | $629,920.30 | 99.0% | 2026-05-14 | yes |
| **FR0000016** | **Gravitas** | **$427,500.00** | **$130,769.84** | **30.6%** | **2026-03-15** | **no** |
| FR0000014 | Fraud Inc | $348,000.00 | $83,184.00 | 23.9% | 2026-05-14 | yes |
| FR0000020 | Response AI Solutions | $127,920.00 | $45,305.00 | 35.4% | 2026-05-14 | yes |
| FR0000013 | Enprovera | $34,552.00 | $32,757.76 | 94.8% | 2026-05-14 | yes |
| | **TOTAL** | **$19,032,607.00** | **$11,878,879.65** | 62.4% | | 12 of 14 |

**The analytic point:** the outlay ratio is the only public proxy for whether a vendor actually delivered and
invoiced. On that measure Gravitas (30.6%) outperformed **Bluehawk (0.0%)**, **GSS (0.0%)**, **Omniplex
(3.6%)** and **Fraud Inc (23.9%)** — all four of which received the 60-day extension. **REFUTED:** the
hypothesis that Gravitas was dropped for non-performance is not supported by any public performance
indicator. *(Inference: outlays lag invoicing and are a coarse proxy; a firm can perform and bill late.
But the comparison is like-for-like — same PoP start, same clock, same disbursing office.)*

**Money not spent, not returned:** $427,500.00 obligated − $130,769.84 outlaid = **$296,730.16 remains
obligated, undisbursed, and un-deobligated** on a delivery order whose performance period ended more than
four months ago. **CONFIRMED** (USAspending award `CONT_AWD_70CDCR26FR0000016_7012_70CDCR26D00000018_7012`).
No de-obligation transaction exists in FPDS.

## a.3 Corporate condition — no distress signal anywhere

**CONFIRMED (SAM.gov entity record, local bulk snapshot `datasets/sam.db`, UEI EJB9AHGV8BD1):**

- Legal name GRAVITAS PROFESSIONAL SERVICES, LLC · **dba GRAVITAS INVESTIGATIONS** · CAGE **11BS1**
- **entity_start_date 2015-04-15**, state of incorporation **OH** — a ten-year-old business, not a newcomer
- **registration_date 2025-02-21 · last_update and activation 2026-01-29 · expiration 2027-01-27** —
  Gravitas **renewed its SAM registration on 2026-01-29, six weeks before the delivery order lapsed**, and
  the registration is active for another six months. A firm winding down does not re-register.
- `exclusion_status` **empty** — not debarred, suspended or excluded
- Primary NAICS **561611**; also 561450 (credit bureaus), 561612 (security guards); PSC R615
- POC / president: **ADAM VISNIC**
- Physical address `1985 KING AVE # 321, KINGS MILLS OH 45034`; mailing address **`P.O. BOX 321`, same
  city/zip**. **Observation (fact):** the "# 321" in the street address is the same number as the PO box, so
  the SAM physical address is a mail drop rendered in street form. This is an address-quality note, not a
  shell finding — see below.

**CONFIRMED (company website `gravitasinv.com`, fetched 2026-07-27):** active site, three offices
(Cincinnati OH 525 Vine St #523; Kings Mills OH; Tampa FL 5005 W Laurel St Ste 100), principal **Adam
Visnic, MS, "Chief Fact Finder," 20+ years**. Services listed include **person location and skip tracing,
surveillance, asset searches, process serving, background research**. Company-claimed licences: **Ohio
Class A Private Investigator #20152100145022, Kentucky #289229, Indiana #PI22100013**; claims SOC2 and
HIPAA. *(Licence numbers are self-published on the vendor's own site — **UNCONFIRMED** against the Ohio
PISGS licence register; see NEEDS list.)*

**This inverts the framing.** Of the fourteen awardees, Gravitas is among the few whose stated business is
literally the contracted service and who holds state private-investigator licences in three states. ICE
dropped the licensed investigator and extended two firms that had disbursed nothing.

**CONFIRMED (CourtListener, `party` and `cases` searches, 2026-07-27):** **no litigation involving
Gravitas Professional Services, LLC.** All twenty returned rows are unrelated entities — *Gravitas NW, LLC*
(Bankr. D.D.C., 2026-04-22), *Quisenberry v. Gravitas LLC* (M.D. Fla.), *Gravitas Search Partners LLC v.
Deutsch* (S.D.N.Y.), *Gravitas Capital Advisors* (D.D.C. 2006). Name-only collisions; none is an Ohio
investigations firm. **"I checked and found nothing" is the result.**

**UNCONFIRMED — receivables factoring.** Finding **#14390** records four ICE awardees that factored
receivables (National Protective Services, Caduceus, Critical Response Strategies, Savvy Professor).
The repo's unified UCC index returned **0 hits for "Gravitas"** (`query_registry.py ucc-search`), but that
index does not cover Ohio, so this is a **coverage gap, not a negative finding**. Ohio SOS UCC and business
search are behind a WAF (both endpoints returned **HTTP 403** on 2026-07-27). See NEEDS list.

## a.4 What the non-renewal most likely was — and what would settle it

**Inference, clearly labelled.** Given (i) no termination, (ii) no de-obligation, (iii) a live IDIQ,
(iv) an active SAM registration, (v) no litigation, (vi) outlays above two extended firms, and (vii) the
fact that the extensions were a **$0.00 administrative action** created by JBOUDREAUX7012 and approved by
SWRAY7012 in a single batch on 2026-03-10/11 — the most parsimonious reading is that **the extension batch
was a discretionary administrative sweep and Gravitas was left out of it**, not that Gravitas was
sanctioned. The lapse date (Sunday 2026-03-15) and the absence of any adverse instrument are consistent
with a lapse-by-omission.

**Competing hypothesis that cannot be excluded from public data:** ICE declined to extend because it was
dissatisfied with quality (the solicitation Q&A confirms **"There will be no QASP"** and **"The government
does not have an expected threshold for the timeliness and accuracy"**, so there is no contractual metric to
have failed). **The performance standard the other thirteen were held to is, on the face of the
solicitation, no standard at all** — which is itself the answer to the question as posed.

**What would settle it:** the contract file — FOIA the ICE ERO acquisition file for `70CDCR26FR0000016`
(CPARS entry, any COR memoranda, the extension decision memo covering the 2026-03-10/11 batch, and any
show-cause/cure correspondence).

---

# (b) THE CAPGEMINI CEILING EXCESS

## b.1 Both figures verified against primary documents

**CONFIRMED — the award.** FPDS-NG, `70CDCR26D00000015` mod 0, signed 2025-12-16:
`baseAndAllOptionsValue = 365821218.75`, `solicitationID = 26-SOL-DCR-01`,
`numberOfOffersReceived = 51`, NAICS 561611, PSC R799, createdBy JBOUDREAUX7012, approvedBy SWRAY7012.

**CONFIRMED — the amendment.** The actual Amendment-2 solicitation PDF text
(`Skip Tracing Solicitation Sections B-M Amendment 2.pdf`, posted 2025-11-19T20:59:28-05:00; text preserved
at `work-P/soldocs/`), Section B "Minimum and Maximum Quantities", verbatim:

> "In accordance with FAR 16.504(a)(4)(ii), the minimum and maximum quantity the government will acquire
> under this contract is as follows: **Minimum: The minimum for each IDIQ contract award will be
> $7,500,000.00 Maximum: Maximum ceiling per IDIQ not to exceed $281,250,000.00.**"

and Section G, verbatim (including ICE's own typo):

> "No funding will be obligated on the base IDIQ contract. Funding will be provided via issuance of task
> orders as requirements arise. **IDIQ Minimum Per Individual Award: $7,500,000.00 / IDIQ Maximum Per
> Individual Award: $281,250,000.000.00**"

**Capgemini's ceiling exceeds the stated per-IDIQ maximum by $84,571,218.75 — 1.301× the cap. CONFIRMED.**

## b.2 The bigger finding: what Amendment 2 actually changed

**CONFIRMED** by diffing the original solicitation PDF (posted 2025-11-10T17:15:45-05:00) against
Amendment 2. The **original** Section B read, verbatim:

> "Minimum: The minimum for each IDIQ contract award will be **$250.00**. Maximum: **The total
> combined/shared ceiling for all IDIQ awards is $180,000,000.00. Maximum ceiling per IDIQ not to exceed
> $90,000,000.00.**"

| Term | Original (2025-11-10) | Amendment 2 (2025-11-19) | Change |
|---|---:|---:|---|
| Guaranteed minimum per IDIQ | $250.00 | $7,500,000.00 | **×30,000** |
| Maximum ceiling per IDIQ | $90,000,000.00 | $281,250,000.00 | **×3.125** |
| **Total combined/shared program ceiling** | **$180,000,000.00** | **— (deleted)** | **removed** |
| FAR 52.216-19 order-limitation window | 365 days | 730 days | doubled |

ICE said so itself. From the Q&A published as part of Amendment 2 (`Skip Tracing Questions and
Answers.pdf`), answering an offeror who asked whether the $180M was a single shared ceiling or per-IDIQ:

> "The minimum and maximum ceiling per IDIQ have been updated to $7,500,000.00 and $281,250,000.00
> respectively. **The overall ceiling has been removed.**"

**Consequences (arithmetic, CONFIRMED):**
- 14 awards totalled **$1,442,909,640.02 = 8.02× the $180,000,000 program ceiling advertised nine days
  earlier**.
- Capgemini's single award is **4.06× the original $90,000,000 per-IDIQ cap**.
- The trade press reported the program on the original terms — GovConWire, *"DHS Seeks Proposals for
  Potential $180M Skip Tracing Services IDIQ Contract."* **(Secondary — reporting, not proof; but it
  corroborates that $180M was the publicly understood size.)**

**Timeline (CONFIRMED, HigherGov opportunity version history, four versions):** posted **2025-11-10** with
proposals due **2025-11-13 — three calendar days**. Amendment 1 (2025-11-12) fixed the NAICS from 541199 to
561611 and moved the due date to 11/20, then 11/21. Amendment 2 (2025-11-19) moved it to **2025-11-24 5:00
PM ET**. **There is no Amendment 3** — Amendment 2's terms were operative at close. Awards signed
2025-12-16, **22 days after close**, on 51 offers.

## b.3 How the excess arises — a reproducible arithmetic explanation

**INFERENCE (arithmetic derivation, high confidence; the inputs are all CONFIRMED).**

The Q&A establishes the pricing unit: *"Please confirm that the Price Schedule B CLIN amount should be for
a 50,000 case unit?"* → **"Yes, the CLIN amount should be for a 50,000 per month case unit."** and
*"The Government intends to release 50K per month in one batch."*

Dividing each awardee's base delivery order by 50,000 yields an implied per-case price. Dividing each
IDIQ ceiling by that price yields an implied maximum case quantity:

| Awardee | IDIQ ceiling | Base DO | Implied $/case | ceiling ÷ DO | Implied max cases |
|---|---:|---:|---:|---:|---:|
| **Capgemini** | **$365,821,218.75** | $4,816,782.50 | **$96.3357** | 75.95 | 3,797,361 |
| Global Recovery Group | $217,265,625.00 | $2,812,500.00 | $56.2500 | 77.25 | 3,862,500 |
| Bluehawk | $201,443,062.50 | $2,656,327.50 | $53.1266 | 75.84 | 3,791,759 |
| SOSi | $123,166,968.76 | $1,642,226.25 | $32.8445 | **75.00** | **3,750,000** |
| B.I. Incorporated | $121,837,500.00 | $1,624,500.00 | $32.4900 | **75.00** | **3,750,000** |
| Omniplex | $113,242,027.50 | $1,487,580.00 | $29.7516 | 76.13 | 3,806,250 |
| National Protective Svcs | $68,231,250.00 | $909,750.00 | $18.1950 | **75.00** | **3,750,000** |
| Constellation | $57,848,437.51 | $767,468.75 | $15.3494 | 75.38 | 3,768,781 |
| GSS | $55,575,000.00 | $741,000.00 | $14.8200 | **75.00** | **3,750,000** |
| AI Solutions 87 | $48,491,250.00 | $636,500.00 | $12.7300 | 76.18 | 3,809,211 |
| Gravitas | $32,062,500.00 | $427,500.00 | $8.5500 | **75.00** | **3,750,000** |
| Fraud Inc | $25,578,000.00 | $348,000.00 | $6.9600 | 73.50 | 3,675,000 |
| Response AI Solutions | $9,715,500.00 | $127,920.00 | $2.5584 | 75.95 | 3,797,491 |
| Enprovera | $2,631,300.00 | $34,552.00 | $0.6910 | 76.16 | 3,807,739 |

Five awardees land on **exactly 3,750,000 cases** (ratio 75.000 to the cent); the rest cluster within ±3%.
And **$281,250,000 ÷ 3,750,000 = exactly $75.00 per case.**

**Therefore:** the Amendment-2 per-IDIQ maximum appears to have been computed as a **quantity** cap —
3,750,000 cases at a $75.00/case reference price — and each award's FPDS ceiling was set as *that vendor's
own per-case price × the same 3,750,000-case maximum*. **Capgemini's ceiling exceeds $281,250,000 because
Capgemini's per-case price ($96.34) exceeds the $75.00/case reference — ICE applied the quantity cap and
not the dollar cap.** All thirteen other awardees priced below $75.00/case, so all thirteen landed under
$281.25M.

Three consequences worth reporting:
1. **The excess is real, not an FPDS keying error.** It is a systematic consequence of how ICE built the
   ceilings, and it is internally consistent across all fourteen awards. **REFUTED:** "data-entry error."
   **REFUTED:** "superseded by a later amendment" (there is no Amendment 3). **REFUTED:** "cumulative across
   option years" (the ceiling covers both ordering years; the two CLINs are 0001 Order Year 1 and 1001
   Order Year 2, and the maximum is stated per IDIQ, not per year).
2. **ICE gave the largest ceiling in the program to the most expensive bidder.** Capgemini's implied unit
   price is the highest of the fourteen and **139.4× Enprovera's** ($96.3357 vs $0.6910) for the same
   firm-fixed-price per-case service in the same full-and-open competition.
3. **The band is incoherent at the bottom too.** Enprovera's ceiling ($2,631,300) is **below Amendment 2's
   $7,500,000 guaranteed minimum**, and Response AI's ($9,715,500) barely clears it. A contract whose
   maximum is less than the solicitation's stated minimum cannot both be true. *(Open question: if the
   $7,500,000 minimum survived into the awards, ICE has guaranteed **$105,000,000** across fourteen
   IDIQs against **$19,032,607** ordered. The ordering period runs to 2027-12-15 if the option is exercised,
   so nothing is breached yet — but it is a real exposure and a good FOIA/interview question.)*

## b.4 Amendment 2 also stripped the security paragraph — verified by document diff

**CONFIRMED.** Word-level diff of `Statement of Work - Skip Tracing Services.pdf` (2025-11-10) against
`Statement of Work - Skip Tracing Services Amendment 2.pdf` (2025-11-19). Exactly **one substantive
paragraph was deleted** (all other diff hunks are page-boundary drift; string counts confirm it):

> **REMOVED:** "The vendor may be required to use DHS IT case management systems. Where required, the
> government will provide vendor personnel with immediate access to case file information from or within
> DHS/ICE systems (**EARM/EID, ENFORCE, IDENT/HART, ATLAS, NCIC**, etc.) and other approved law enforcement
> systems. Such access may be through file transfers, downloads, or user accounts/permissions. **All vendor
> personnel accessing DHS/ICE IT systems will be required to hold/obtain a Public Trust Security Clearance
> and handle PII.**"

String counts across the two SOWs: `DHS IT case management systems` 2 → **0**; `EARM/EID` 2 → **0**;
`Public Trust Security Clearance` 2 → **0**; `Public Trust` 4 → 2; `85P` 6 → **6** (unchanged);
`physical observation` 2 → 2 (unchanged); `Photographs verifying` 2 → 2 (unchanged).

**Precision matters here — do not overstate.** Amendment 2 removed the paragraph that (i) contemplated
vendor access to ICE law-enforcement systems and (ii) tied a Public Trust clearance to that access.
**The SOW's separate Section 6.0 Security Requirements survives** — SF-85P "Questionnaire for Public Trust
Positions", NBIS eAPP, preliminary fitness determinations, continued eligibility. ICE's Q&A states
*"it takes approximately 5-7 weeks to get a public trust clearance once the paperwork is filed."*
So the correct statement is: **Amendment 2 removed the contractors' contemplated access to EARM/EID,
ENFORCE, IDENT/HART, ATLAS and NCIC — and the clearance requirement that rode on it — five days before
proposals were due**, not that it abolished vetting.

Amendment 2 also removed **FAR 52.228-5 (Insurance — Work on a Government Installation)** and **Service
Contract Act applicability**. ICE's Q&A: *"This procurement is not subject to the Service Contract Act."*
— so no DOL wage determination governs the people doing the door-knocking. Also from the Q&A:
*"Will the individuals working on this contract be allowed to carry firearms?"* → **"No."**

---

# (c) THE FOUR PRE-COMPETITION INSTRUMENTS — FULL RECORDS

All four **CONFIRMED** from FPDS-NG ATOM, pulled 2026-07-27. **Each is stated with its own labelled
measure. Do not sum them.** Note also the structural finding: **two of the four ran off GSA schedules**,
one was a sole-source letter contract, and one was a modification to the incumbent monitoring task order.

## c.1 Capgemini — `70CDCR24FR0000006` mod **P00011**, 2025-10-09

- **Transaction obligation: +$7,372,680.00.** (Cumulative order total after P00011: $24,591,840.43.)
- **Full description, verbatim:** *"THIS MODIFICATION ADDS IN SCOPE WORK IN ACCORDANCE WITH THE SOW DATED
  10-08-2025 PARA. 2.2 SKIP TRACING SERVICES"* — i.e. a statement of work dated **one day before** the mod.
- `reasonForModification = A` (additional work). createdBy **JBOUDREAUX7012**, approvedBy **SWRAY7012** —
  the same officer pair that ran the competitive program six weeks later.
- **The vehicle:** this is a task order under **GSA Federal Acquisition Service IDV `47QTCA18D00A2`**
  (agency 4732) — a **GSA Multiple Award Schedule contract**. NAICS **541512** (Computer Systems Design
  Services), PSC R799. Base description: **"ERO PROGRAM SUPPORT SERVICES (BRIDGE)"**, later "…TO INCLUDE
  DATA ANALYSIS, DATA VIRTUALIZATION, METRICS AND FORECASTING SUPPORT."
- **`extentCompeted = A` but `numberOfOffersReceived = 1` and `fairOpportunity = ONE` (only one source)**
  on every one of its fourteen actions.
- **So:** ICE bought immigration skip tracing by declaring it "in scope" of an IT-services **bridge** order
  on a GSA schedule.

**Full action history (14 actions, cumulative $27,278,124.42 — confirms finding #14387):**

| Mod | Signed | Obligated | PoP end | Note |
|---|---|---:|---|---|
| 0 | 2023-12-28 | $2,700,000.00 | 2024-06-28 | ERO PROGRAM SUPPORT SERVICES (BRIDGE) |
| P00001 | 2024-02-26 | $0.00 | 2024-06-28 | |
| P00002 | 2024-05-01 | $2,478,235.02 | 2024-06-28 | |
| P00003 | 2024-06-28 | $2,398,235.26 | 2024-09-27 | |
| P00004 | 2024-09-20 | $1,061,617.63 | 2024-11-22 | |
| P00005 | 2024-11-18 | $835,000.00 | 2024-12-25 | |
| P00006 | 2024-11-25 | $345,539.21 | 2024-12-25 | |
| P00007 | 2024-12-24 | $2,619,065.90 | 2025-03-25 | |
| P00008 | 2025-03-24 | $211,170.84 | 2026-03-23 | scope reworded to data analysis/virtualization |
| P00009 | 2025-06-11 | $1,132,196.60 | 2025-07-23 | |
| P00010 | 2025-09-11 | $1,142,305.82 | 2025-11-23 | |
| **P00011** | **2025-10-09** | **$7,372,680.00** | 2026-03-23 | **adds skip tracing, SOW dated 10-08-2025 ¶2.2** |
| P00012 | 2026-02-24 | $2,295,794.15 | 2026-03-23 | |
| **P00013** | **2026-04-09** | **$2,686,283.99** | **2026-09-23** | *"ADD AND EXERCISE OPTION PERIOD 8 CLINS"* |

**Two things stand out.** First, the single skip-tracing mod (+$7,372,680) is **27% of everything ever
obligated on this order** and larger than any other action on it. Second, a contract labelled "(BRIDGE)"
at award in December 2023 has now run **2 years 9 months through eight option periods**, most recently
extended on **2026-04-09 to 2026-09-23** — after the competed program went dormant. **2026-09-23 is the live
decision point** (already flagged in #14387; re-confirmed today from the primary record).

## c.2 SOSi — `70CDCR26C00000001`, letter contract, 2025-10-21

- **Award amount at mod 0: $6,954,758.46. Obligation at mod 0: $0.00.** *(The wave's "award total
  $6,954,758.46" is the base-and-all-options value, not an obligation.)*
- **Full description, mod 0, verbatim:** *"TO AWARD A LETTER CONTRACT FOR SKIP TRACING SERVICES IN
  ACCORDANCE WITH THE ATTACHED LETTER CONTRACT AND STATEMENT OF WORK."*
- `contractActionType = D` (definitive contract), `extentCompeted = C` (**NOT COMPETED**),
  `solicitationProcedures = SSS` (**ONLY ONE SOURCE**), 1 offer, `typeOfSetAside = NONE`.
- NAICS **541611** (Administrative Management and General Management Consulting) — **not** an investigation
  NAICS. PSC R799. Funding office 70CRMD.
- **`createdDate = 2025-10-07 16:18:54`** — the FPDS record was opened **two weeks before signature and
  34 days before the competitive solicitation was published**. createdBy JBOUDREAUX7012, approved SWRAY7012.
- **Full transaction history — the money moved after the competition opened:**

  | Mod | Signed | Obligated | Cumulative | Description |
  |---|---|---:|---:|---|
  | 0 | 2025-10-21 | $0.00 | $0.00 | award the letter contract |
  | **P00001** | **2025-11-18** | **$6,954,758.46** | $6,954,758.46 | funds the letter contract |
  | P00002 | 2025-12-05 | $0.00 | $6,954,758.46 | *"TO DEFINITIZE THE LETTER CONTRACT IN ACCORDANCE WITH FAR 52.216-25 CONTRACT DEFINITIZATION"* |

  **CONFIRMED and sharper than previously recorded:** the $6,954,758.46 was **obligated on 2025-11-18 —
  eight days after the solicitation published and six days before proposals were due.** PoP 2025-10-21 →
  2026-01-19. Outlays: **$6,964,593.27** (slightly above obligation, a normal disbursement artifact).

## c.3 Global Recovery Group — `70CDCR26FR0000003`, GSA schedule, 2025-10-27

- **Transaction obligation at mod 0: +$1,288,462.00.** **Base + exercised options: $8,375,000.00.**
  **Base + ALL options: $33,500,000.00** — a **$33.5M ceiling nobody in this investigation had.**
- **Full description, mod 0, verbatim:** *"TO AWARD A TASK ORDER FOR SKIP TRACING SERVICES IN ACCORDANCE
  WITH THE ATTACHED STATEMENT OF WORK."*
- **Vehicle: GSA schedule `GS-23F-0026U`.** NAICS **561440 (Collection Agencies)**, PSC R799.
  `extentCompeted = A`, `solicitationProcedures = MAFO`, **2 offers received**, fair opportunity given.
  **Funding office 70CEMD** — a *different* ICE funding office from the competitive program's 70CRMD.
- PoP: current completion **2026-01-25**, **ultimate completion 2026-10-25** (a full year with options).
- **Mod P00001, 2026-03-06: +$4,390,375.00**, description verbatim *"ADDITIONAL FUNDING FOR THE TASK ORDER
  FOR SKIP TRACING SERVICES THROUGH GLOBAL RECOVERY GROUP UNDER THE CONTRACT GS-23F-0026U."*
  Cumulative obligation **$5,678,837.00**. createdBy EPETERSON7012, approved SWRAY7012.
  Outlays $5,385,728.15.
- **Timing (CONFIRMED):** this +$4.39M landed on **2026-03-06 — four days before ICE extended twelve
  competed delivery orders by 60 days at $0.00.** The off-schedule channel got money; the competed
  channel got calendar.

**Framing caution.** GRG's SAM record shows **primary NAICS 561440**, SAM-registered since **2004-02-18**,
entity start 2003-12-02, Herndon VA, POC Ralph Griffith. It is a genuine collections company, so 561440 is
its natural schedule classification — the anomaly is **the vehicle and the timing**, not that ICE picked an
odd code for this vendor. Describe it as *"ICE bought immigration skip tracing off a GSA collection-agency
schedule two weeks before publishing its own competition"* — that is exact.

## c.4 B.I. Incorporated — ISAP V task order `70CDCR25FR0000127` — **the sharpest fact in the case**

Parent IDV `70CDCR25D00000062`; solicitation `70CDCR25R00000018`; NAICS **561210** (Facilities Support);
PSC **R408**; funding office 70CEMD. **Complete action history, all CONFIRMED from FPDS:**

| Mod | Signed | Obligated | Cumulative | Description (verbatim, truncated at FPDS field length) |
|---|---|---:|---:|---|
| 0 | 2025-09-30 | $21,966,324.91 | $21,966,324.91 | "THIS TASK ORDER FACILITATES THE INTENSIVE SUPERVISION APPEARANCE PROGRAM (ISAP) V…" |
| P00001 | 2025-09-30 | $16,103.09 | $21,982,428.00 | additional funding for ISAP V |
| **P00002** | **2025-10-30** | **$690,000.00** | $22,672,428.00 | **"THIS MODIFICATION ADDS FUNDING FOR SKIP TRACING SERVICES FOR THE INTENSIVE SUPERVISION APPEARANCE PROGRAM (ISAP) V…"** |
| **P00003** | **2025-12-17** | **$9,660,000.00** | $32,332,428.00 | **"THIS MODIFICATION ADDS FUNDING FOR ATTACHMENT 4 PRICING SCHEDULE ITEM 42 SKIP TRACING SERVICES FOR THE INTENSIVE SUPERVISION APPEARANCE PROGRAM (ISAP) V…"** |
| **P00004** | **2026-01-27** | **$76,011,425.00** | **$108,343,853.00** | **same description as P00003 — "ATTACHMENT 4 PRICING SCHEDULE ITEM 42 SKIP TRACING SERVICES"** |

PoP 2025-09-30 → 2026-09-29. P00002/P00003 createdBy **JBOUDREAUX7012**, approved SWRAY7012;
P00004 createdBy VLEONOVA7012, approved SWRAY7012.

### What "Attachment 4" is — ANSWERED

**CONFIRMED from the transaction text itself:** Attachment 4 is the **ISAP V contract's Pricing Schedule**,
and **Item 42 of that schedule is "Skip Tracing Services."** That is not an inference — FPDS quotes it as
*"ATTACHMENT 4 PRICING SCHEDULE ITEM 42 SKIP TRACING SERVICES."*

**The implication is the story.** Skip tracing was already a **pre-priced line item inside the ISAP V
electronic-monitoring contract** — the contract that supervises the same non-detained docket the skip-tracing
program targets. ICE therefore did not need a competition to buy skip tracing from B.I.; it had a CLIN.
It ran a $1.44B competition anyway, awarded fourteen IDIQs, obligated $19.03M against them — and put
**$86,361,425** through Item 42 instead.

**The arithmetic, stated with its own labelled measure (CONFIRMED):**
- Skip-tracing obligations added to the ISAP V task order: **$690,000 + $9,660,000 + $76,011,425 =
  $86,361,425.00**, all three mods within four months.
- Obligations across all fourteen competed skip-tracing delivery orders: **$19,032,607.00**.
- **Ratio: 4.54×.**
- B.I.'s own competed delivery order (`70CDCR26FR0000021`) carries **$1,624,500** — **1.9%** of what B.I.
  received for skip tracing through the ISAP channel.

**Sequence, day by day (CONFIRMED):**
1. **2025-09-30** — ISAP V renewal task order awarded to B.I., $21.98M, PoP to 2026-09-29.
2. **2025-10-30** — P00002 adds **$690,000** of skip tracing. *(11 days before the competition published.)*
3. **2025-12-16** — ICE awards fourteen competed skip-tracing IDIQs, including B.I.'s $121,837,500.
4. **2025-12-17 — the very next day** — P00003 adds **$9,660,000** of skip tracing to the sole-source
   ISAP task order.
5. **2026-01-27** — P00004 adds **$76,011,425** more.

**Cross-profile note:** this instrument is already partly mapped in the `geo-group` profile
(`investigations/geo-group/reports/bi-ice-skip-channel-task-allocation-ledger-2026-07-13.csv`), and
codex-Q independently confirms from the local ledger that `70CDCR26FR0000021` is the **only NAICS 561611 /
PSC R799 award in the entire GEO/B.I. cohort's history** — 561611 is a brand-new FY2026 classification for
that cohort. Cite geo-group findings **#12488** and the ledger rather than re-deriving; **P00004
(+$76,011,425) appears to be new to both profiles** and should be the item written up.

---

# (d) DELANEY HALL

## d.1 The purchase order — every field

**CONFIRMED.** FPDS-NG, `70CDCR26P00000013`, mod 0 (the only action).

| Field | Value |
|---|---|
| Vendor | RESPONSE AI SOLUTIONS, LLC — UEI **ZE2JVFS8ML75** |
| Signed / effective | **2026-05-30 — a Saturday** |
| Obligated | **$250,275.48** |
| Base + all options (ceiling) | **$573,375.48** |
| PoP | 2026-05-30 → current completion **2026-06-30**; ultimate completion **2026-12-31** |
| Description (verbatim) | **"EMERGENCY FENCING AND LIGHTING AT DELANEY HALL DETENTION FACILITY, NEWARK NEW JERSEY."** |
| NAICS | **532490 — Other Commercial and Industrial Machinery and Equipment Rental and Leasing** |
| PSC | **W099 — Lease/Rental of Equipment, Miscellaneous** |
| Competition | `extentCompeted = C` **NOT COMPETED**; `solicitationProcedures = SSS` **ONLY ONE SOURCE**; **1 offer**; `typeOfSetAside = NONE` |
| Justification | **`reasonNotCompeted = URG` — "URGENCY (FAR 6.302-2)"** |
| `fedBizOpps` | **NO** — never publicly posted |
| Place of performance | Newark NJ **07105**, Essex County, congressional district **NJ-08** |
| Workflow | createdBy **JBOUDREAUX7012**, lastModifiedBy **JBOUDREAUX7012**, approvedBy **JBOUDREAUX7012** — created 2026-06-05 20:11:44, approved 2026-06-08 10:37:43 |

**Two things nobody had.** (i) The NAICS/PSC pair makes this unambiguously a **rental**, not construction —
ICE rented fencing and lighting. (ii) It is **another single-person create-and-approve action**, this time
by JBOUDREAUX7012, and it was **signed on a Saturday but not entered into FPDS until the following Friday
evening**.

## d.2 What was happening at Delaney Hall — timeline

Press reporting (**SECONDARY — reporting, not proof**; corroborated across outlets, dates as reported):

| Date | Event | Source |
|---|---|---|
| 2026-05-22 (Fri) | ~300 detainees begin a hunger and labour strike over conditions and due process | CNN, TIME, HRW |
| 2026-05-25/26 | Protests outside the facility; clashes with ICE agents; arrests | CNN, ABC7, 6abc |
| 2026-05-29 (Fri) | ICE reported to have pepper-sprayed hunger strikers; strike leaders transferred; family visitation suspended | The Intercept |
| **2026-05-30 (Sat)** | **ICE signs the emergency fencing-and-lighting purchase order** | **FPDS — PRIMARY** |
| ~early June | Newark police erect protest zones using **metal barriers and concrete blocks**; ICE agents withdraw **inside the building's perimeter fence**; NJ State Police assume security | Gothamist, NBC New York |
| ~June | Mayor Ras Baraka imposes a **9 p.m.–6 a.m. curfew within a half-mile of Delaney Hall**; arrests for curfew violations follow | ABC7, NBC New York, 6abc |
| June | Gov. Sherrill announces designated protest zones; state health inspectors "denied full access" | WHYY, HRW |

**UNCONFIRMED:** the specific claim that **crowd-control barriers were destroyed**. The reporting I could
reach describes barriers being *erected* by Newark police and NJ State Police and ICE retreating behind the
existing perimeter fence; I did not find a primary or contemporaneous report of barriers being destroyed.
Do not publish the "destroyed barriers" detail without a source. *(NBCNews and Gothamist both returned
403/redirect to WebFetch; see NEEDS list.)*

## d.3 Why this is anomalous — GEO's contract already covers it

**CONFIRMED from GEO's FY2025 10-K (CIK 923796, filed 2026-02-25), Item 1 and Note 16, verbatim:**

> "On February 27, 2025, we announced that we have been awarded a 15-year, fixed-price contract by ICE to
> provide support services for the establishment of a federal immigration processing center at the
> company-owned, 1,000-bed Delaney Hall Facility in Newark, New Jersey. **GEO's support services include the
> exclusive use of the Delaney Hall Facility by ICE, along with security, maintenance, and food services**,
> as well as access to recreational amenities, medical care, and legal counsel."

And the 10-K facility table lists: *Delaney Hall Facility · 1,000 · ICE · Federal Detention · Minimum ·
commencement **May 2025** · base period **15 years** · renewal options **None** · **Owned***.

**So: GEO owns the building and holds a 15-year fixed-price contract whose scope expressly includes security
and maintenance — and ICE separately, urgently, and without competition rented perimeter fencing and
lighting for it.** That is the anomaly, stated from GEO's own words.

## d.4 What ICE did with GEO in the same weeks — new, and it sharpens the picture

**CONFIRMED.** FPDS, `70CDCR26FR0000050` (GEO Group; NAICS 561612; PSC S206) — the FY2026 Delaney Hall
detention-and-transportation funding task order:

| Mod | Signed | Obligated | Cumulative | Description (verbatim) |
|---|---|---:|---:|---|
| 0 | 2026-03-18 | $5,670,000.00 | $5,670,000.00 | "…FUNDING NECESSARY FOR DETENTION AND TRANSPORTATION SERVICES FOR HOUSING ICE ALIENS AT THE DELANEY HALL CONTRACT DETENTION FACILITY IN NEWARK NEW JERSEY." |
| **P00001** | **2026-06-10** | **$17,010,000.00** | $22,680,000.00 | same |
| **P00002** | **2026-06-22** | $0.00 | $22,680,000.00 | **"…MODIFICATION P00002 INCREASES RATES I.A.W. AN APPROVED REQUEST FOR EQUITABLE ADJUSTMENT."** |

**Within four weeks of the hunger strike, ICE (i) rented emergency fencing and lighting from a third party
on urgency grounds, (ii) tripled the Delaney Hall funding task order by $17,010,000, and (iii) granted GEO
a rate increase under an approved Request for Equitable Adjustment.** All three are primary-record facts.
The REA is the single most promising FOIA target here — an REA is a written claim by the contractor, and
its file will say what GEO said the crisis cost it.

## d.5 Who physically installed the fencing — still unknown, and the subaward field cannot tell us

**Base rate first (per codex-Q):** across the **228 USAspending-backed ICE prime awards** in the geo-group
archive, **228 of 228 report `reported_subaward_count = 0`** and every `reported_subaward_amount` cell is
blank, in every size band including all fifteen $100M+ awards. **The field has no discriminating power in
ICE contracting.** Response AI's zero is therefore **not evidence of anything** — not pass-through, not
self-performance, not concealment. Any earlier framing of it as suspicious should be dropped.

What I checked and found nothing: `query_usaspending.py subawards "RESPONSE AI SOLUTIONS, LLC"` → **0
records** (consistent with the 100% base rate, i.e. uninformative).

**One weak capability signal, offered as an observation only.** Response AI's SAM registration
(UEI ZE2JVFS8ML75, Great Falls VA, POC James Kraemer, activated 2026-02-04, expires 2027-02-02) lists
**69 NAICS codes** — including 236220 (commercial building construction), 532112 and 532412 (vehicle and
construction-equipment rental) — but **not 532490**, the code on this purchase order. Contracting officers
are not confined to a vendor's self-selected SAM NAICS, so this proves nothing; it is a small indication
that fencing rental is not a line Response AI advertises.

**Evidence routes that would actually answer it (none exhausted):** FSRS first-tier subcontract reports;
the ICE contract file and the FAR 6.302-2 justification; City of Newark / Essex County construction or
temporary-structure permits for 451 Doremus Ave; NJ contractor registrations; and site photography with
visible vendor markings on the fence panels.

---

# (e) GEO SECURITIES FILINGS

## e.1 The FY2025 10-K — two passages, no dollar figure — CONFIRMED

**CONFIRMED.** 10-K for FY2025, CIK 0000923796, accession **0001193125-26-071747**, filed **2026-02-25**
(`https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-20251231.htm`; extracted text at
`work-P/geo_10k_2025.txt`). "Skip trac" appears **4 times** — two passages, each duplicated by the
document's iXBRL text layer: once in **Item 1 "Contract Developments"** and once in **Note 16,
"Commitments, Contingencies and Other Matters — Contract Developments."** The language is identical:

> "On December 22, 2025, we announced that our wholly-owned subsidiary, BI Incorporated ("BI"), has been
> awarded a contract by U.S. Immigration and Customs Enforcement ("ICE") for the provision of skip tracing
> services. Skip tracing services entail enhanced location research with identifiable information,
> commercial data verification, **and physical observation** to verify current address information and
> investigate alternative address information for individuals on the federal government's non-detained
> docket. The new contract has a term of two years, with an initial term of one year, effective
> December 16, 2025, and an additional one-year period."

**The no-dollar-value observation is CONFIRMED for the 10-K** — neither passage states a value, a ceiling,
or an expected revenue contribution.

**But it is much weaker than the strategic review assumed, and I am downgrading it — CHANGED.** Two reasons,
both checked:

1. **GEO quantifies no contract at all in that section.** Reading the whole "Contract Developments" list in
   Item 1: the three Florida DOC managed-only contracts, the North Florida Detention Facility JV, the USMS
   five-region transport contract, Adelanto, D. Ray James, North Lake, Karnes, Delaney Hall and the Lea
   County termination are **all** described without a dollar figure. Dollar amounts appear only under the
   adjacent **"Asset Sale" / "Asset Purchase"** headings (the $312 million Lawton sale, the ~$228 million
   gain, the ~$60 million Western Region purchase). **So the silence on skip tracing is GEO's uniform
   practice for contract awards in the 10-K, not a singling-out.** A hostile editor would hit the original
   framing here, and correctly. **Do not publish "GEO hid the value from investors."**
2. **GEO did give investors a figure — in an SEC-filed exhibit.** **8-K EX-99.1 filed 2026-05-06**
   (accession 0001193125-26-207484, Q1-2026 earnings release), verbatim:
   > "In the fourth quarter 2025, we were also awarded a new two-year contract by ICE for the provision of
   > skip tracing services, **valued at up to $60 million in revenues per year**. We began providing skip
   > tracing services under this new two-year contract in March 2026."

Also note: the **Q4-2025 earnings release (8-K EX-99.1, 2026-02-12) gave no figure either**, and **GEO filed
no 8-K at all for the 2025-12-22 announcement** (its 8-K sequence runs 2025-12-08 → 2026-01-26). The
"$121 million" figure comes from the press release, reported contemporaneously as **"approximately $121
million over the full two-year period"** — **SECONDARY**, via Investing.com, 2025-12-22.

**What survives, and it is still worth reporting:** both public figures are **the FPDS ceiling presented as
revenue**. $121,837,500 is the IDIQ ceiling; $121,837,500 ÷ 2 = $60,918,750 ≈ "up to $60 million in revenues
per year." Against that, B.I.'s competed delivery order has produced **$1,624,500 in orders and $1,481,823.30
in outlays**. **GEO told the market a capacity number and the market read it as revenue.** (The derivation
is an inference; both dollar figures are CONFIRMED.)

## e.2 What GEO tells investors that ICE does not say publicly

Four items, all **CONFIRMED** from filed text:

1. **GEO ran a skip-tracing "pilot" in Q4 2025.** From the **Q4-2025 earnings release, 8-K EX-99.1 filed
   2026-02-12** (accession 0001193125-26-047556), verbatim:
   > "In December 2025, we were awarded a new two-year contract by ICE for the provision of Skip Tracing
   > services… **This two-year contract award follows an initial Skip Tracing pilot contract that we
   > successfully implemented during the fourth quarter of 2025.**"

   and, in guidance:
   > "…**no revenue or earnings assumption for the Skip Tracing services contract as we transition from the
   > pilot contract that was implemented in the fourth quarter** to the new two-year contract."

   **This is the investor-facing name for the ISAP V modification P00002 of 2025-10-30 (+$690,000) — and
   very likely P00003 as well.** GEO told the market it was already running skip tracing for ICE in
   Q4 2025 while ICE's own solicitation Q&A told offerors *"Yes this is a new requirement"* and there was
   no incumbent. Those two statements cannot both be complete. **This is the single strongest new item in
   (e).**

2. **The description of the service is softer in the press release than in the 10-K.** The Q4-2025 release
   says skip tracing entails *"enhanced location research **primarily with identifiable information and
   commercial data verification**"* — **omitting "physical observation."** The 10-K, filed thirteen days
   later, restores *"and physical observation."* Physical observation is the part where someone goes and
   looks at the house. **CONFIRMED** by direct comparison of the two filed texts.

3. **ICE's non-detained docket is being re-weighted toward hard monitoring.** Q1-2026 release, verbatim:
   > "The number of ISAP participants on GPS ankle bracelets has increased to **more than 48,000 currently
   > from 17,000 in early 2025**. Correspondingly, the number of ISAP participants on the SmartLINK mobile
   > application has declined to approximately **131,000 currently from approximately 159,000 in early
   > 2025**. We have also seen an increase in the number of ISAP participants assigned to case management…
   > for approximately **111,000 individuals currently**."

   A **2.8× increase in ankle monitors in about fifteen months** — from the company's own filings, not an
   advocacy estimate.

4. **Skip tracing is an explicit upside lever in guidance.** Q1-2026 release, verbatim: sources of potential
   upside not in guidance include *"additional revenue from **higher utilization of our skip tracing
   services contract**."* GEO raised FY2026 guidance in the same release (net income $153–166M on revenue
   of $2.95–3.10B; Adjusted EBITDA $525–545M), up from initial FY2026 guidance issued 2026-02-12
   ($0.99–1.07 diluted EPS; Adjusted EBITDA $490–510M).

Also of note (**CONFIRMED**, FY2025 10-K MD&A): the **Electronic Monitoring and Supervision Services segment
revenue *fell* $11.9 million in 2025 to $320,919 thousand**, "primarily due to decreases in average
participant counts under ISAP." So the ISAP add-ons documented in (c) had not yet reached revenue as of
2025-12-31 — consistent with GEO's own "began providing skip tracing… in March 2026."

## e.3 The three-step sequence — verified, and it is four steps

**CONFIRMED** with dates from both the primary contract record and GEO's filings:

| # | Date | Event | Source |
|---|---|---|---|
| 1 | **2025-09-30** | ICE renews B.I.'s ISAP contract — two years, initial one-year term **effective 2025-10-01**, plus one option year. Task order `70CDCR25FR0000127`, $21,982,428. | 10-K Item 1 + Note 16, verbatim; FPDS |
| 2 | **2025-10-30** | ICE adds **+$690,000 of skip tracing** to that ISAP task order (P00002) — GEO's "pilot" | FPDS; GEO Q4-2025 8-K EX-99.1 |
| 3 | **2025-12-16 / announced 2025-12-22** | ICE awards B.I. its own skip-tracing IDIQ `70CDCR26D00000005`, ceiling **$121,837,500**, two-year term (1+1) effective 2025-12-16 | FPDS; 10-K; press release |
| 4 | **2025-12-17 and 2026-01-27** | ICE adds **+$9,660,000** and then **+$76,011,425** of "Attachment 4 Pricing Schedule Item 42 Skip Tracing Services" to the ISAP task order | FPDS |

**The 10-K discloses steps 1 and 3 and is silent on 2 and 4.** The $86.4M that actually moved is invisible
in GEO's securities disclosure; the $121.8M ceiling that has produced $1.6M of orders is what investors were
told about. *(Materiality judgment is not mine to make — but the asymmetry is a documented fact and a fair
question for GEO's investor relations and for a securities-law-literate editor.)*

## e.4 Earnings-call transcripts

**UNCONFIRMED.** I read the filed **earnings releases** (8-K EX-99.1, 2026-02-12 and 2026-05-06) in full;
those are primary SEC-filed documents. I did **not** obtain **call transcripts** (Q&A sessions), which are
not filed with the SEC and sit behind Seeking Alpha / Motley Fool / AlphaSense paywalls. The analyst Q&A is
where a skip-tracing volume or margin question would most likely be answered. See NEEDS list.

---

# (f) CURRENT PROGRAM STATE — as of 2026-07-27

**Method:** FPDS-NG ATOM sweep of **every ICE contracting-office 70CDCR action signed 2026-06-15 →
2026-07-27** — **120 transactions**, fully enumerated and parsed (`work-P/rec_*.xml`), plus a USAspending
transaction-keyword sweep on "skip tracing" for all of 2026.

## f.1 Skip tracing — still dormant, and the last competed action was March

**CONFIRMED.** The most recent ICE ERO skip-tracing transaction of any kind is **2026-03-11**
(the twelve $0.00 extensions). The only 2026 skip-tracing transactions anywhere in USAspending after that
are Global Recovery Group's GSA-schedule +$4,390,375 on **2026-03-06**, and an unrelated
LexisNexis/Social Security Administration administrative mod on 2026-05-21.

In the 120-action sweep: **no new skip-tracing delivery orders, no new IDIQ awardees, no terminations, no
de-obligations, no Gravitas activity, and no follow-on solicitation.** Twelve delivery orders expired
2026-05-14, Global Recovery Group's expired 2026-04-16, Gravitas's expired 2026-03-15. **All fourteen
delivery orders are now expired and none has been replaced.**

**The Capgemini bridge extension is CONFIRMED and re-verified today:** `70CDCR24FR0000006` **P00013, signed
2026-04-09, +$2,686,283.99, extending performance to 2026-09-23** by adding and exercising **Option Period
8** CLINs. Cumulative $27,278,124.42 over 14 actions. This is the **only** live ICE skip-tracing-capable
instrument with time left on it, and **2026-09-23 is the decision point to watch.**

Two adjacent instruments surfaced in the sweep, both small but on-theme:
- **2026-07-10** — `70CDCR25P00000028` P00001, **Gold Type Business Machines, Inc., +$12,600**:
  *"THIS AWARD PURCHASES A ONE YEAR SUBSCRIPTION FOR USE OF THE BACKTRACE DATABASE FOR ENFORCEMENT AND
  REMOVAL OPERATIONS **NEWARK FIELD OFFICE** USE FOR INVESTIGATIONS. MODIFICATION P00001 ADDS FUNDING FOR A
  SECOND YEAR OF SERVICE."* Not competed, only one source. A commercial locate-database subscription bought
  directly by the field office.
- **2026-07-07** — `70CDCR21FR0000022` P00023, **Deloitte Consulting, +$1,046,176.14**, *"INTERNET RESEARCH
  AND DATA ANALYTICS SUPPORT SERVICES FOR THE ENFORCEMENT AND REMOVAL…"*

## f.2 UAC Safety Verification Initiative — one new action, and it is a financing event

**CONFIRMED.** The 18 first task orders are fully enumerated and reconcile exactly:

- **18 task orders `70CDCR26FR0000081`–`0098`**, signed **2026-06-16 (8) and 2026-06-17 (10)**, all with the
  description *"THE PURPOSE OF THIS TASK ORDER IS TO MEET THE IDIQ MINIMUM REQUIREMENT OF 1000 CASES FOR
  SAFETY VERI[FICATION]…"*, obligations totalling **$85,376,317.14**; plus **MVM `70CDCR26FR0000052`
  $1,446,000** → **$86,822,317.14** across 19 task orders. **Matches the canonical figure exactly.**
- **New number:** those 18 task orders carry **combined ceilings of $10,108,872,474.05** — each task order's
  ceiling is ≈½ its parent IDIQ ceiling, consistent with one ordering year of a two-year vehicle.
- Per-case first-order rates (obligation ÷ the 1,000-case minimum) span **$1,055.54 (Alpha Recovery) to
  $11,965.00 (Caduceus)** — an **11.3× spread**, as previously recorded.

**The one new action since the last wave pull — and it is significant:**

> **2026-07-24 · `70CDCR26D00000032` mod P00001 · CADUCEUS INC. · $0.00 obligated ·
> `reasonForModification = M` · createdBy JCAPPELLO7012, approvedBy JCAPPELLO7012 ·
> "THE PURPOSE OF THIS CONTRACT IS FOR THE PROVISION SAFETY VERIFICATION AND WELLNESS CHECKS FOR
> UNACCOMPANIED ALIEN CHILDREN AND FORMER UNACCOMPANIED ALIEN CHILDREN. **THIS MODIFICATION INCORPORATES
> THE ASSIGNMENT OF CLAIMS.**"**

**Assignment of claims** (FAR 32.8 / 31 U.S.C. 3727) is the mechanism by which a contractor assigns its
right to be paid by the government to a financing institution. **This is the federal-contract counterpart of
the receivables factoring recorded in finding #14390, which dates the Caduceus factoring to 2026-07-24 —
the same date.** Two independent record systems (a state UCC filing and an FPDS modification) now document
the same financing event, and **ICE formally recognised it three days ago.** This is the first
UAC-family IDIQ modification of any kind. *(Caveat retained from #14390: Caduceus holds $400M+ in prior
CDC/DHA/Army/VA awards, so factoring there is weak evidence of distress. The value here is corroboration of
the mechanism and a clean primary source for it.)*

No other UAC IDIQ or task order has been modified. No new UAC awardees. No terminations. No task orders
beyond the nineteen.

## f.3 Adjacent ICE activity worth carrying (all CONFIRMED, all in the 120-action window)

- **2026-07-09** — `70CDCR26D00000049`, **THE GEO GROUP**, new IDIQ, ceiling **$528,678,643.44**,
  $0 obligated, *"DETENTION AND DETENTION RELATED SERVICES AT THE BIG HORN CONTRACT DETENTION FACILITY IN
  HUDSON, COLORADO"* — **NOT COMPETED, only one source, 1 offer.** createdBy JCAPPELLO7012, approved
  ISOMPPI7012.
- **2026-07-15** — `70CDCR26FR0000101`, GEO, **+$15,654,000**, ceiling $106,502,322.60, Big Horn.
- **2026-07-21** — `70CDCR26FR0000105`, GEO, **+$22,825,000**, North Lake MI detention management support —
  **NOT COMPETED, `reasonNotCompeted = URG` (FAR 6.302-2 urgency)**, PoP to 2027-07-20.
- **2026-06-23** — `70CDCR26FR0000053` P00001, **MVM Inc., +$28,000,000**, and **2026-07-01** —
  `70CDCR25FR0000026` P00007, **MVM, +$19,940,471.62**, both *"NATIONWIDE TRANSPORTATION OF UNACCOMPANIED
  MINORS AND FAMILY UNITS."* MVM is the same firm holding UAC task order `FR0000052`.

## f.4 Protests, litigation, audits, Congress

- **Bid protests — no new activity. CONFIRMED (negative).** opus-K established the complete series:
  **Ballard Green, LLC filed B-424186.1 through .5 against 26-SOL-DCR-01; GAO dismissed all five**
  (2026-01-13 ×2, 2026-01-29 ×2, **2026-03-13**). I found nothing after 2026-03-13 and no protest at all
  against the UAC solicitation `70CDCR26R00000015`. **Caveat:** GAO's docket search returned **HTTP 403** to
  automated fetching today, so this rests on opus-K's earlier docket pull plus web search — it is a
  reasonably strong negative, not an exhaustive one.
- **Litigation — nothing new found.** No CourtListener case involving Gravitas, and none surfaced against
  the skip-tracing or UAC programs. (Delaney Hall itself is heavily litigated, but that is `geo-group`
  territory — see e.g. geo-group findings **#12764** (Third Circuit, NJ AB 5207) and **#12761**.)
- **DHS OIG — the load-bearing prior report. CONFIRMED it exists; it is the innocent explanation for the UAC
  program and the case must state it.** **OIG-25-21 (March 2025), "ICE Cannot Effectively Monitor the
  Location and Status of All Unaccompanied Alien Children After Federal Custody"** found that from FY2019 to
  FY2023 ICE transferred **more than 448,000 UACs to HHS**, and **more than 31,000 release addresses were
  blank, undeliverable, or missing apartment numbers.** A March-2025 OIG finding that ICE cannot locate
  released children is the most defensible reason for a 2026 procurement to go and check on them. **Any
  publication of the UAC program that omits this is unfair.** *(Secondary sourcing today — AILA summary and
  the OIG report URL `https://www.oig.dhs.gov/sites/default/files/assets/2025-03/OIG-25-21-Mar25.pdf`;
  I did not fetch the PDF itself. Pull it before publication.)*
- **No new OIG or GAO audit of the skip-tracing or UAC programs was found.** Reporting indicates DHS OIG has
  an **ongoing audit of ICE's biometric/PII data handling** (scope is data governance, not these
  procurements) and that **DHS OIG lost appropriations for roughly 60% of FY2026**, delaying routine
  reporting. **SECONDARY — reporting only.**
- **Congress.** **H.R.7161, "No Private Bounty Hunters for Immigration Enforcement Act"** (Krishnamoorthi),
  **CONFIRMED** as GovInfo package `BILLS-119hr7161ih`, dated **2026-01-20**, **introduced-in-House version
  only** — no reported or engrossed version exists in the BILLS collection, i.e. no committee action.
  **New oversight activity found (SECONDARY — reporting):** (i) a letter from **Reps. Garamendi and
  Espaillat with ~70 Democrats**, and a parallel Senate effort by **Wyden, Padilla, Schiff and colleagues**,
  demanding investigation of **ICE/DHS warrantless purchases of Americans' location data**; (ii) **Sen.
  Wyden's office requested an ICE briefing after the skip-tracing contract was reported in October 2025;
  ICE scheduled it for 2026-02-10 and cancelled it one day beforehand with no explanation and no offer to
  reschedule.** Both press-office pages returned 403 to automated fetching — **verify from the offices' own
  releases before publishing.**

---

## RELIABILITY NOTES

- **FPDS-NG ATOM is the primary source for everything in §(a), (c), (d), (f)** and for the ceilings in §(b).
  Every figure is `obligatedAmount` / `baseAndAllOptionsValue` read directly off the transaction record.
  Raw XML is preserved in `work-P/`.
- **Ceilings are ceilings; obligations are money.** Observed throughout. Where I state a ceiling
  ($1.44B, $32.06M, $121.8M, $10.1B, $573,375.48) it is labelled as such. Where I state money it is an
  obligation or an outlay, labelled.
- **The four pre-competition instruments are NOT summed.** Each is stated with its own labelled measure —
  Capgemini +$7,372,680 (transaction obligation), SOSi $6,954,758.46 (award value, obligated 2025-11-18),
  GRG +$1,288,462 then +$4,390,375 (transaction obligations on a $33,500,000 ceiling), B.I. +$690,000 /
  +$9,660,000 / +$76,011,425 (transaction obligations).
- **The $86,361,425 B.I. figure IS a legitimate sum** — it is three transaction obligations on one PIID,
  the same measure, which is exactly what FPDS's own `totalObligatedAmount` progression shows
  ($21,982,428 → $108,343,853).
- **HigherGov mirrors the SAM.gov notice text verbatim**; the Amendment-2 quotations in §(b) come from the
  **solicitation PDFs themselves** (text extracts preserved at `work-P/soldocs/`), not from HigherGov's
  summary fields. The `val_est_high = 281250000` field agrees with the PDF.
- **Press is labelled SECONDARY throughout** and used only for context that primary records cannot supply
  (the Delaney Hall protest chronology, congressional letters, the GEO press-release figure).
- **codex-Q's base-rate correction is applied:** the subaward field is treated as having zero discriminating
  power, and the 308/256-row GEO-linked award set is **not** used as an ICE-wide denominator anywhere.

---

## UNCONFIRMED / NEEDS

**Blocked by anti-bot or access controls (all attempted today, 2026-07-27):**
1. **Ohio Secretary of State** business search and UCC search — `businesssearch.ohiosos.gov` returned
   **HTTP 403** on both the HTML and JSON endpoints. Needed for Gravitas Professional Services LLC:
   formation date, officers, current status, and any UCC-1 financing statement / receivables assignment
   (the #14390 question). **Manual lookup for the user.**
2. **Ohio PISGS private-investigator licence register** — verify Gravitas's claimed **Class A licence
   #20152100145022** (currently sourced only from the company's own website). Likewise KY #289229 and
   IN #PI22100013.
3. **GAO bid-protest docket search** — `gao.gov/legal/bid-protests/search` returned **HTTP 403**. Needed to
   confirm no B-424186.6+ and no protest against `70CDCR26R00000015`.
4. **NBCNews, Gothamist, Garamendi.house.gov** — 403 / cross-host redirect. Needed to date the Newark
   curfew precisely and to source the congressional letter directly.
5. **DHS OIG report OIG-25-21 PDF** — not fetched; pull it before publishing the UAC innocent explanation.

**Substantive gaps:**
6. **Whether "crowd-control barriers were destroyed" at Delaney Hall is true.** I could not source it. Do
   not publish it unsourced.
7. **Who physically installed the Delaney Hall fencing.** Subaward data is uninformative by base rate.
   Routes: FSRS first-tier reports; the FAR 6.302-2 justification in the contract file; City of Newark /
   Essex County permits for the 451 Doremus Ave site; NJ contractor registration; site photography.
8. **GEO / B.I. earnings-call transcripts** (Q4-2025 call ~2026-02-12; Q1-2026 call ~2026-05-06) — the
   analyst Q&A is not SEC-filed and sits behind paywalls. Worth one manual pull.
9. **Whether Amendment 2's $7,500,000 guaranteed minimum survived into the awarded contracts.** If it did,
   ICE has guaranteed **$105,000,000** across fourteen IDIQs against **$19,032,607** ordered — and
   Enprovera's **$2,631,300** ceiling would be below its own guaranteed minimum. Resolvable only from the
   award documents (Section B of each signed IDIQ), not FPDS. **FOIA target.**
10. **Capgemini SE (Paris) disclosure.** Its US subsidiary holds the largest skip-tracing ceiling and ran the
    pre-competition GSA-schedule channel. Whether Capgemini SE discloses ICE removal-support work to
    European investors or under CSRD/CS3D human-rights due diligence is untested and is a distinct,
    publishable angle. *(Carried forward from fable-I §1.5 — still not done.)*

**NEEDS MANUAL OPENCORPORATES:**
- **Gravitas Professional Services, LLC** (Ohio) — formation date, registered agent, officers, status,
  and whether **Adam Visnic** controls any other entities.
- **Response AI Solutions, LLC** (Delaware 7453000) — beneficial ownership behind Corporation Service
  Company (fable-N's assignment; noted here because the Delaney Hall PO is its most anomalous instrument).

---

## THREE THINGS I WOULD PUT AT THE TOP OF THE STORY

1. **ICE ran a $1.44 billion competition for skip tracing and then bought the service, at four and a half
   times the scale, from the company that already monitors the same people — through a pre-priced line item
   (Attachment 4, Item 42) in that company's sole-source electronic-monitoring contract.** $86,361,425
   through the ISAP channel versus $19,032,607 across all fourteen competitive awardees. The largest single
   tranche, $76,011,425, went through on 2026-01-27.
2. **The competition was advertised at $180 million with a three-day deadline, and the ceiling was deleted
   five days before proposals were due.** ICE's own published Q&A says it: *"The overall ceiling has been
   removed."* The awards came to $1,442,909,640.02 — eight times the advertised program maximum. In the same
   amendment ICE removed the Service Contract Act, removed the contractors' contemplated access to
   EARM/EID, ENFORCE, IDENT/HART, ATLAS and NCIC and the Public Trust clearance requirement attached to it —
   and told bidders in writing there was no incumbent, while three incumbents were already being paid.
3. **The only firm ICE dropped was the licensed private investigator.** Gravitas Investigations — Ohio Class
   A licensed, ten years in business, the exact trade being procured — disbursed 30.6% of its money and was
   allowed to lapse on a Sunday with no termination and no explanation. Bluehawk and GSS disbursed **$0.00**
   between them, on $3.4 million, and both were extended.
