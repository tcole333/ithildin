# opus-M — UAC 18-awardee cohort workup + cross-connection matrix
**Wave 3 · 2026-07-27 · profile `tech-right` (threads 11/15/16) · read-only DB, no repo writes**
**Program:** ICE ERO "Safety Verification Initiative", solicitation **70CDCR26R00000015** (posted 2026-04-09,
responses due 2026-04-17), IDIQs **70CDCR26D00000030–D00000047**, all signed **2026-06-02**, ordering period
to **2027-05-31**. Combined ceiling **$20,583,928,204** (my per-firm sum reproduces the canonical figure to the
dollar). **$86,822,317.14 obligated** across **19 task orders** (verified independently below).
**Ceilings below are ordering capacity, not money spent.**

---

## 0. HEADLINE — three results, one of them large

**1. The central hypothesis is REFUTED on every SAM-visible attribute.** I compared all 27 cohort firms present
in the March-2026 SAM extract (18 UAC + 14 skip-tracing, 5 shared/overlapping) pairwise on entity address,
mailing address, all six POC name slots, all six POC street addresses, the complete NAICS string and the complete
PSC string. **Zero pairwise matches.** Not one pair of UAC awardees shares an address, a person, or a code string.
The Wave-1 twin-detection method was re-run at full scale and it found nothing new *between awardees*. That is a
real negative and it should be published as one: on the available evidence these are 18 separately-sourced firms,
not a brokered slate.

**2. The same scan found each firm's *own* concealed satellite — and one of those satellites is the story.**
**Compass United (D00000033, $1,567,890,829 ceiling)** declares **BCFS Health and Human Services** as its parent in
its own SAM registration. BCFS holds **$2,989,436,081** in HHS/ACF grants for **residential shelter services for
unaccompanied children**; its sibling **Compass Connections** holds **$1,756,170,565** in ACF grants including
**$291,227,302 for "HOME STUDY AND POST RELEASE SERVICES FOR UNACCOMPANIED CHILDREN."** Compass United shares
Compass Connections' registered agent, suite, and PO box, and eight of nine of its directors. Compass United itself
had **zero federal awards of any kind** before this ICE IDIQ. The organisation that sheltered these children and ran
their post-release case files stood up an award-less affiliate to sell ICE in-person visits to the same population.
Combined with Applied Intellect (a **current** ORR post-release-services holder) and The Baptiste Group (a former ORR
shelter grantee), **3 of the 18 ICE awardees carry direct ORR child-welfare lineage.**

**3. The newcomer pattern is dominant, and it is now the only source for that claim.** **12 of 18 awardees had
zero federal prime awards of any kind before 2025-01-01**; a 13th (EagleGrace Global) had a single $53,268 Army
award. Only five are established federal contractors. **Severance Security Services first registered in SAM on
2026-03-23 — seventeen days before the solicitation posted** — and holds a $779,000,000 ceiling. Per the
orchestrator's codex-Q note, no held dataset supplies an ICE-wide newcomer base rate, so the per-firm formation and
SAM-registration timeline below is load-bearing; every date carries its source and I state plainly what I could not pin.

---

## 1. PER-FIRM PROFILE TABLE (all 18)

Sources, uniform across the table unless noted:
- **Award facts** — USASpending `/api/v2/search/spending_by_award/` filtered on the exact PIID, and
  `/api/v2/awards/CONT_IDV_<PIID>_7012/`, retrieved **2026-07-27** (`work-M/uac_idiqs_raw.json`,
  `work-M/uac_idiq_detail.json`). Every record: `number_of_offers_received=18`, `extent_competed=A`,
  `type_set_aside=NONE`, `solicitation_identifier=70CDCR26R00000015`, `date_signed=2026-06-02`.
- **Ceilings** — canonical SYNTHESIS §3 as corrected; not re-derived. My sum of all 18 = **$20,583,928,204.16**, matching.
- **SAM fields** — local March-2026 public extract `datasets/sam/SAM_PUBLIC_UTF-8_MONTHLY_V2_20260301.dat`
  (874,711 rows, ingested 2026-03-03) plus HigherGov `/awardee` (live SAM mirror, retrieved 2026-07-27).
  16 of 18 are in the March extract; **Critical Response Strategies and Severance Security Services are not**,
  and their SAM facts come from HigherGov only.
- **Prior federal history** — USASpending prime contracts + IDVs (`work-M/prior_history.json`) and assistance
  awards `award_type_codes 02–05` (`work-M/orr_crossover.txt`), FY2008–FY2026, filtered to the exact UEI.

**All 18 UEIs are CONFIRMED** from the award records — including the eight that were unpinned.

| # | IDIQ | Firm | **UEI** | CAGE | Ceiling | 1st task order (obl.) | Physical address | Address type | Formed / entity start | SAM initial reg | Officers / POCs | Prior federal $ (pre-2025-01-01) | Certifications | Employees | Website |
|---|---|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|---|
| 1 | D00000030 | **Alpha Recovery LLC** | `R8JUHEXBCZB9` | 9XQ66 | $316,735,974 | FR0000081 $1,055,544 | 1080 W Peachtree St NW **Unit 2101**, Atlanta GA 30309 | Unit in residential high-rise; **2** SAM registrants | entity start 2022-10-15; GA | **2024-06-18** | **Deion Hackworth** — sole name in all six POC slots; POC address **8735 Dunwoody Pl #6828, Atlanta** = **148 SAM registrants** (mail-drop) | **$0** (0 awards) | minority-owned, SDB, veteran-owned, small | "<500" (bucket) | alpharecovery.org — live; domain has Wayback captures back to **2001** (predates the 2022 LLC); first TLS cert **2023-08-30**. Claims "3,000+ Fugitives Located or Apprehended" |
| 2 | D00000031 | **Applied Intellect LLC** | `SKDNFVJ9K8U3` | 630X6 | $1,040,372,408 | FR0000082 $3,080,158 | 43457 Bettys Farm Dr Ste 100, Chantilly VA 20152 | Suburban address, "Ste 100"; **3** SAM registrants (self + 2 own JVs) | entity start 2010-07-26; VA | 2010-08-02 | **Sanjeev K Sharma** (President), **Ajit Louis** (alt, at 25737 Howerton Dr Chantilly) | **$41,943,064** (105 awards) — ACF $15.6M, HHS ASA $10.2M, Forest Service $6.7M | **SBA 8(a)** (`A620230215`), Asian-Pacific-American-owned, **not** small | "<500" | ap-in.com — live |
| 3 | D00000032 | **Caduceus Inc.** | `ZX23KR32ZH32` | 5AQA8 | $1,623,930,000 | FR0000083 **$11,965,000** (highest) | 1850 Parkway Pl SE Ste 725, Marietta GA 30067 | Office tower; **4** SAM registrants | entity start 2008-05-15; GA | 2009-01-21 | **Carlos M. Lopez** (CEO), **Linda Mitchell** (alt) | **$280,137,468** (260 awards) — CDC $104M, Army $67M, DHA $39M, VA $23M | HUBZone, SDVOSB, Hispanic-American-owned, SDB, small | "<500" | caduceusstaffing.com — **fetch failed** (connection reset), unverified |
| 4 | D00000033 | **Compass United** | `LB2PEHVPDGB2` | 9C2A0 | $1,567,890,829 | FR0000084 $8,916,302 | 2330 N Loop 1604 W (Ste 300), San Antonio TX 78248 | Office suite shared with Compass Connections; **2** SAM registrants | TX SoS **0160062501**, effective **2000-10-02** | 2022-07-29 | **Sonya (L) Thompson** — President, SAM POC, **and TX registered agent of both Compass United and Compass Connections** | **$0 contracts, $0 grants** | **Nonprofit (A8)**; **not** small | "<500" | none in SAM/HigherGov |
| 5 | D00000034 | **Continuity Global Solutions LLC** | `FAQYB9J9EA36` | 3BJZ6 | $1,015,420,918 | FR0000085 $6,270,128 | 101 Reid Ave Ste 106, Port Saint Joe FL 32456 | Small-town office; **5** SAM registrants (own CGS family) | DE; entity start 2002-06-26; FL foreign **M23000013422** (2023-10-18) | 2004-10-14 | **Tauqeer Khalid** (CFO, SAM POC + FL manager), **Stephen Hartsuff** (FL manager). Agent: Incorporating Services Ltd | **$565,386,270** (5,082 awards) — State Dept $414M, Army $118M | not small | **">1500"** | continuitygs.com — live |
| 6 | D00000035 | **Critical Response Strategies, LLC** | `ZDN8V5GKJ959` | 9DVK2 | $650,378,000 | FR0000086 $1,614,000 | 6440 Southpoint Pkwy Ste 300, Jacksonville FL 32216 (**FL registry says Ste 320**) | Office park; **5** SAM registrants | **FL L21000178383, formed 2021-04-16**; EIN 87-1014108 | 2022-09-23 (**last updated + reactivated 2026-04-09**) | **Will Adkins** (FL manager); SAM POC **Ethan LeVoy, "Account Executive"**. Agent: **CT Corporation System** | **$0** (0 awards) | SDB, small | "<500" | criticalresponsestrategies.com — live; first cert 2021-04-16, 105 certs |
| 7 | D00000036 | **Delta Point LLC** | `YPABB25UK1L3` | 88Z51 | $1,510,186,884 | FR0000087 $3,910,774 | 38 Windy Walkway, King Cove AK 99612 (March-26 SAM physical was 10633 Washington Cir, Anchorage) | ANC village office; **11** SAM registrants at the King Cove address | entity start 2018-11-26; AK | 2019-01-11 | **Braxton Apperson** (VP), **Tyrone Kosa** (EVP), **Jamie Kosa** (elec) — all three also POCs for **The King Cove Corporation** | **$72,430,668** (11 awards) — Air Force $105M lifetime | **SBA 8(a)** (`A620290713`), **Alaska Native Corporation-owned**, DoT DBE, small | "<500" | deltapointak.com — live since 2021 |
| 8 | D00000037 | **EagleGrace Global LLC** | `SW56UKW28L15` | 02E44 | $1,080,860,000 | FR0000088 $5,236,600 | 60 Twin Lakes Dr, Covington GA 30016 | **Single-family residence — sole SAM registrant at the address** | entity start **2024-08-28**; GA | **2024-09-10** | **Sandra Ofili** — sole name in both populated POC slots | **$53,268** (1 Army award, 2024) | WOSB, Black-American-owned, SDB, small | **"Not Available"** | **NONE.** No URL in SAM or HigherGov; `eaglegraceglobal.com` does not resolve and has **zero Wayback captures** |
| 9 | D00000038 | **Lemoine Disaster Recovery LLC** | `C182PM2K1463` | 7ZDT9 | $1,734,450,000 | FR0000089 $7,690,000 | 1906 Eraste Landry Rd Ste 200, Lafayette LA 70506 | Office; **5** SAM registrants (own Lemoine family) | entity start 2017-10-04; **incorporated TX** | 2017-10-16 | **Seth Lemoine** (COO), **Amanda Messa** (General Counsel, at 1200 Brickyard Ln Ste 300 Baton Rouge). SAM parent = **The Lemoine Company LLC** | **$0** under this UEI (parent is an established contractor) | not small | **"751-1000"** | no URL in HigherGov; lemoinecompany.com → 1lemoine.com (parent) |
| 10 | D00000039 | **National Protective Services, LLC** | `W4AUG3SNRTL6` | 16ZC5 | $415,134,000 | FR0000090 $1,166,500 | 6858 Ingram Rd, San Antonio TX 78238 | **Sole SAM registrant at the address** | entity start 2008-02-04; TX | **2025-11-19** (9 days after skip-tracing sol.) | **Wesley Swearingen** (VP), **Jason W McLendon** (CEO) | **$0** (0 awards) | SDVOSB, veteran-owned, small | "<500" | nationalprotectiveservices.com — live (see #14395 on its TLS failure) |
| 11 | D00000040 | **Origin Investigations Inc** | `VSF3D5VZABZ5` | 7R8N0 | $536,620,000 | FR0000091 $1,812,000 | 515 S Flower St **Fl 18**, Los Angeles CA 90071 | **Shared 18th floor — 16 SAM registrants**, incl. its own twins | entity start 2016-01-01; CA | 2016-11-14 (**not refreshed since 2025-07-29**) | **Jayden R Brant** (Owner), **Abram Popham** (Dir. Client Relations) | **$0** — ten years SAM-registered, **zero federal awards until 2026** | SDB, small | **"Not Available"** | origininvestigations.com — live since 2018 |
| 12 | D00000041 | **Response AI Solutions, LLC** | `ZE2JVFS8ML75` | 9MFB2 | $489,158,780 | FR0000092 $3,670,800 | 843 Constellation Dr, Great Falls VA 22066 | **Residence, 2 SAM registrants**; mailing 1530 Wilson Blvd Ste 650 Arlington = **49 SAM registrants** | entity start 2023-05-10; **DE** | 2023-05-30 | **James Kraemer** (Pres.), **Natalia Vela** (CFO), **Colby Farrow**, **Aaron Colvin** (Logistics Mgr — *new, not in prior waves*) | **$0** pre-2025; $18.2M in 2025 (Army-led) | SDB, small | "<500" | responseai.us — live; discloses **no ICE/DHS work** |
| 13 | D00000042 | **Security Insights LLC** | `GS9LV7EPJQ74` | 01P01 | **$1,982,235,852** | FR0000093 $5,507,232 | 305 Escandon Ave, Rancho Viejo TX 78575 | **Residence — sole SAM registrant**; TX agent address 1304 E Adams St, Brownsville | **TX 0803343173, effective 2019-06-13** | 2024-09-04 (**not refreshed since 2025-08-27; expires 2026-08-25**) | **Jaime Salazar** — sole managing member (TX), sole SAM POC | **$0** (0 awards) | SDVOSB, Hispanic-American-owned, SDB, small; **SAM entity_structure `2J` = Sole Proprietorship** | "<500" | **securityinsights-s.com returns HTTP 404** (Wayback captures 2021–2025, then dark) |
| 14 | D00000043 | **Septimo Solutions, LLC** | `SL5DUHMP9163` | 9ZC44 | **$3,105,250,000** (largest) | FR0000094 $8,686,250 | 21 Magothy Bridge Rd, Severna Park MD 21146 | Residence; 3 SAM registrants | entity start 2023-03-22; **state of incorporation VA** (address MD) | 2024-07-02 | **Miguel Howe** (Managing Partner), **Erica Howe** (Office Mgr) — both at **620 Tower Bank Rd, Severna Park** | **$0** (0 awards) | SDVOSB, SDB, **Small Business Joint Venture (JS)**, small | "<500" | septimosolutions.com — live but **first Wayback capture 2025-04-08, only 2 captures ever** |
| 15 | D00000044 | **Severance Security Services LLC** | `DKFGF41MVR41` | 7YB98 | $779,000,000 | FR0000095 $4,770,000 | 18740 County Road 12 S, Foley AL 36535 | **Rural residential — the home address of officer Timothy W Harry**; 0 SAM registrants in March-26 | **AL, 2017-10-23** (via FL foreign M17000009010); EIN 81-5186985 | **2026-03-23 — 17 days before the solicitation posted** | SAM POC **"Tracy Harris, Owner"**; FL registry officers **Tracey Matthews** (majority) and **Timothy W Harry** (minority) | **$0** (0 awards) | small, LLC only — **no socioeconomic certifications** | "<500" | severancesecurity.us — live since 2017; sells **executive protection, secure transportation, HOA/POA and event security** |
| 16 | D00000045 | **Savvy Professor LLC** (dba **SIVS LLC**) | `HHZZRGNWPL44` | 18UR9 | $1,596,251,500 | FR0000096 $4,727,750 | 8401 Old Mill Ln, Spotsylvania VA 22551 | **Residence — sole SAM registrant**; mailing 10408 Courthouse Rd **Unit 570** = 4 SAM registrants (mailbox store) | entity start **2024-07-17**; VA | **2026-02-05** | **Todd M Thompson** — sole name in all six POC slots | **$0** (0 awards) | SDB, JS, small; PSC codes **1005 / 6350 / 7J20 / R615** | "<500" | sivs.us — live; site says led by "a licensed Virginia investigator and **retired FBI Cyber Intelligence Technician** with 17 years of federal technical-operations experience" |
| 17 | D00000046 | **SOS International LLC (SOSi)** | `L3VCKMD7J585` | 6QG06 | $559,578,059.16 | FR0000097 $3,224,029 | 1881 Campus Commons Dr Ste 500, Reston VA 20191 | Corporate HQ; 14 SAM registrants (own family) | entity start 2011-01-27; **DE** | 2012-04-11 | **Brett Surbey**, **Elizabeth Caldera** | **$1,928,579,812** (717 awards) — Army $976M, DOJ $554M, DISA $283M | not small | **"1001-1500"** | sosi.com — bot-walled (212-byte response) |
| 18 | D00000047 | **The Baptiste Group, LLC** | `GEGMCJMMZ634` | 7B0E0 | $580,475,000 | FR0000098 $2,073,250 | 1510 Pennsylvania Ave, McDonough GA 30253 | **Sole SAM registrant**; mailing 945 Donegal Dr **"LOT"**, Locust Grove GA (also sole registrant) | entity start 2015-01-01; GA | 2015-01-02 | **Kevin Baptiste** (CEO) — sole POC. Elec-POC street address is **"15610 Pennsylvania Ave"**, a digit-level mismatch with the entity's 1510 | **$0 contracts**; **$17,666,320 in ACF grants** (ORR shelter, 2019–2022) | minority/Black-American-owned, SDB, small; **not** small on the award record | "<500" | SAM lists **thebaptistegroupgov.com — dead** (one Wayback capture, 2018). Live site thebaptistegroup.co is **2,591 bytes**, unarchived, titled "Government Contractor & Facilities Services" |

### Per-case first-order rates (obligation ÷ the stated 1,000-case minimum)
Every one of the 18 first task orders (FR0000081–0098, all performance 2026-06-18 → 2027-06-17) reads
*"THE PURPOSE OF THIS TASK ORDER IS TO MEET THE IDIQ MINIMUM REQUIREMENT OF 1000 CASES."*
Caduceus **$11,965.00** · Compass United **$8,916.30** · Septimo **$8,686.25** · Lemoine **$7,690.00** ·
Continuity **$6,270.13** · Security Insights **$5,507.23** · EagleGrace **$5,236.60** · Severance **$4,770.00** ·
Savvy Professor **$4,727.75** · Delta Point **$3,910.77** · Response AI **$3,670.80** · SOSi **$3,224.03** ·
Applied Intellect **$3,080.16** · Baptiste **$2,073.25** · Origin **$1,812.00** · Critical Response **$1,614.00** ·
NPS **$1,166.50** · Alpha Recovery **$1,055.54**. **Spread 11.33×** for an identically-worded deliverable.
Independently reproduced: **$86,822,317.14** across 19 orders (the 18 above + MVM Inc **70CDCR26FR0000052**,
$1,446,000, 2026-03-20, under FY24 vehicle 70CDCR24D00000002).

### Two award-record anomalies worth carrying
- **Caduceus alone** is typed **"INDEFINITE DELIVERY / DEFINITE QUANTITY"**; the other 17 are IDIQ. It also has the
  only IDIQ whose record was modified after award (`last_modified_date 2026-07-24` vs 2026-06-02 for all others).
- **`subaward_count = 0` on all 18.** Per codex-Q's base-rate memo this field is **uninformative** in ICE
  contracting (228/228 ICE prime awards report zero) — **I am not treating it as a pass-through signal**, and no
  one else should.

---

## 2. CROSS-CONNECTION MATRIX

**Method.** Full-corpus scan of the 874,711-row March-2026 SAM public extract (`work-M/xconnect.py`,
output `work-M/xconnect.txt`, `work-M/addr_density.txt`). Cohort = 18 UAC + 14 skip-tracing awardees;
**27 distinct UEIs resolved in the extract**, 2 absent (Critical Response Strategies, Severance Security Services —
both post-date the snapshot; tested against HigherGov instead, no matches).

### 2A. Attributes tested — and the result

| Attribute | Tested how | Result **between awardees** |
|---|---|---|
| Entity physical address | normalised street+city+state+zip, unit-agnostic | **CLEAN — 0 matches** |
| Entity mailing address | same | **CLEAN — 0 matches** |
| Government business POC (name) | all 6 SAM POC slots × 27 firms | **CLEAN — 0 matches** |
| Alternate govt POC, past-performance POC, alt past-perf POC, electronic POC, alt electronic POC (names) | same | **CLEAN — 0 matches** |
| POC street addresses (all 6 slots) | normalised | **CLEAN — 0 matches** |
| Complete NAICS code string (tilde-delimited, exact) | exact string equality | **CLEAN among the 18**; the only exact match in the entire cohort is the already-known Response AI ↔ Global Emergency Response pair |
| Complete PSC code string (exact) | exact string equality | **CLEAN among the 18**; same single known pair |
| CAGE code clustering | sorted issuance | **No cluster.** Codes span `01P01`…`9ZC44`; adjacency (e.g. 01P01/02E44) tracks the *registration month*, not any shared filer. Not evidence of coordination. |
| SAM registration/activation date batching | see §3 | **No same-day batch.** 11 of 18 refreshed SAM between 2026-03-23 and 2026-06-01, but SAM requires an active registration to receive an award, so pre-award renewal is expected behaviour, not a signal |
| Registered agent | FL/TX registry records where available | **CLEAN** — CT Corporation (Critical Response), Incorporating Services Ltd (Continuity), Jason D Collins (Severance/FL), Sonya Thompson (Compass United), Jaime Salazar (Security Insights). No agent serves two awardees |
| Organisers / incorporators | not obtainable from SAM; state filings gated | **NOT TESTED** — see §6 |
| Email domains / phone numbers | **not present in the SAM public extract** (fields 47–112 carry POC name/title/address only) | **NOT TESTABLE from this source** |
| Website registrar / host / template | fetched 19 sites; crt.sh timelines (mostly 502) | **No shared template or host observed**; see §2D |

**Bottom line: negative.** Applying exactly the method that exposed Response AI ↔ Global Emergency Response and
GSS ↔ Habari to the full 32-firm two-program cohort produces **no new awardee-to-awardee link of any kind**. There
is no evidence of a shared broker, shared filer, or coordinated slate visible in SAM.

### 2B. What the same scan DID find — one concealed affiliate per firm

Every positive hit is a firm's own corporate family, not a link to a competitor.

| Awardee | Concealed / undisclosed affiliate found | Shared attribute | Affiliate's federal awards |
|---|---|---|---|
| **Compass United** | **BCFS Health and Human Services** (`MA2ZMFR58156`), **Compass Connections** (`L9L8GC2LJNP1`) | SAM parent field; identical address 2330 N Loop 1604 W; identical TX PO Box 791090; **same registered agent Sonya Thompson**; 8 shared directors | **$2.99B** and **$1.76B** in ACF grants (see §2C) |
| **Origin Investigations** | **Origin Intelligence Inc** (`YKEVSKQNHJ46`), **ZeroFour Inc** (`NBVQHS3SZAW1`) | same 18th floor; **Jayden Brant is POC on all three** | **$0** and **$0** |
| **Septimo Solutions** | **Aurelian Group LLC** (`G7UPJRAN3NC9`) | **Miguel Howe** is POC on both; both use 620 Tower Bank Rd | **$4,607,514** — FEMA 70FA2023C00000015, "EMI Transformation Management Consulting Services", 2023-09-29 |
| **Response AI Solutions** | **Global Emergency Response Inc** (known) + **Cyber DI LLC** (`W4MQH3KFHYR7`, Kraemer) + **GL Solutions Inc** (`J2CLFENPWL52`, Vela) — *both new this wave* | POC names + 1530 Wilson Blvd Ste 650 | GER **$532,659** (FEMA/ATF patient- and deployment-tracking); Cyber DI **$0**; GL Solutions **$500** |
| **Caduceus Inc.** | **Caduceus LLC** (`L1MGDJ33KPV5`), **Southern Crescent Personnel Inc** (`P5K1TGEHKB78`) | Linda Mitchell POC; 1850 Parkway Pl Ste 725 | $0 and **$52,069,684** (Navy dental staffing) |
| **Delta Point** | **The King Cove Corporation** (`ZNL6W4MQBTU3`) + 8 "Delta"/"Cape" JV entities | 38 Windy Walkway; Apperson/Kosa POCs | ANC 8(a) JV family; King Cove Corp itself $0 |
| **Continuity Global** | 14-entity CGS/Torres family (CGS-OPCL, CGS-Omega, CGS Sentry, Torres-Arkhe, Torres-Avarn, Torres-Armobil, Command Security Honduras SA, Armobil CJSC…) | Tauqeer Khalid POC; 101 Reid Ave Ste 106 | established security family |
| **Applied Intellect** | Applied Intellect–Trihydro 8(a) JV I & II | Sanjeev Sharma POC; Bettys Farm Dr | 8(a) JVs |
| **Lemoine DR** | The Lemoine Company, Matrix Building Systems, Lemoine-Manhattan JV, Tunica-Biloxi Lemoine | Seth Lemoine / Amanda Messa POCs | established parent |
| **Security Insights** | **Security Insights Solutions LLC** (TX **0806663033**, formed **2026-06-22**) — same agent Jaime Salazar, same 1304 E Adams St | TX registry | **formed 20 days after the IDIQ award and 4 days after the first task order** |
| Alpha Recovery · EagleGrace · Baptiste · Savvy Professor · NPS · Severance · Critical Response · SOSi | **none found** | — | — |

### 2C. The one connection that changes the story — the ORR channel

Three of eighteen ICE awardees come out of the HHS/ORR unaccompanied-children system. This extends stored finding
**#14383** (which flagged Applied Intellect and Baptiste, and correctly warned that Compass United is a *different legal
entity* from Compass Connections). **My work resolves what the relationship actually is: distinct entities under
common control.**

**Compass United — CONFIRMED affiliate of BCFS, not merely "shared officer network":**
1. **SAM's own corporate-hierarchy field** names **BCFS HEALTH AND HUMAN SERVICES (`MA2ZMFR58156`, CAGE 3PUK2)**
   as Compass United's parent, with `parent_flag=false` on Compass United's record. HigherGov `/awardee`,
   record last updated **2026-05-29** (`work-M/hg/aw-LB2PEHVPDGB2.json`). Compass Connections carries the
   identical parent.
2. **Texas Comptroller / SoS primary records** (retrieved 2026-07-27, `work-M/tx-compass-united.json`):
   - Compass United — TX file **0160062501**, effective **2000-10-02**, ACTIVE; agent **SONYA L THOMPSON**,
     2330 N Loop 1604 Ste 300; mailing **PO Box 791090, San Antonio 78279-1090**.
   - Compass Connections — TX file **0801676933**, effective **2012-10-30**, EIN 46-1394166; agent
     **SONYA THOMPSON**, **the same suite**; **the same PO Box 791090**.
   - **Eight of Compass Connections' nine listed directors also sit on Compass United's board**, at identical home
     addresses: Claudia Oliveira, David Sprouse, George Cowden III, Karen Simmons, **Kevin Dinnin**, Martha Morse,
     Matt Orwig, Scott Sharman. Compass United director **Asenmet Segura** is listed at **1506 Bexar Crossing,
     San Antonio 78232 — BCFS Health and Human Services' own SAM address**.
   - **CAVEAT, stated plainly:** the TX officer lists carry report years **2002** (Compass United) and **2014**
     (Compass Connections) — these are the most recent public-information reports in the Comptroller feed and may be
     stale. The registered agent, address, PO box and active status are current fields; **the SAM parent field is
     current as of 2026-05-29 and is the load-bearing evidence.**
3. **What the family does with unaccompanied children** (USASpending assistance awards, `work-M/bcfs.txt`):
   - **BCFS HHS — $2,989,436,081** total; **$2,962,096,761 from HHS/ACF**. Largest: 90ZU0224 **$495,367,571**
     (2017-02-01) *"STANDING ANNOUNCEMENT FOR RESIDENTIAL (SHELTER) SERVICES FOR UNACCOMPANIED CHILDREN"*;
     90ZU0334 **$438,286,807**; 90ZU0208 **$409,335,568**; 90ZU0102 **$357,826,098**.
   - **Compass Connections — $1,756,170,565**, all ACF. Includes **90ZU0628 $291,227,302** (2024-01-01)
     *"HOME STUDY AND POST RELEASE SERVICES FOR UNACCOMPANIED CHILDREN"* and a live **90ZU0682 $65,183,688**
     beginning **2026-04-01** — five days before the ICE solicitation posted.
   - **Compass United — $0 grants, $0 contracts, ever.** Its entire federal history is this ICE IDIQ.
4. **Applied Intellect LLC** holds ACF **90ZU0581, $84,526,776.83, 2023-09-29 → 2026-09-28**, *"HOME STUDY AND POST
   RELEASE SERVICES FOR UNACCOMPANIED CHILDREN"* — a **currently-running** ORR post-release contract, held
   simultaneously with the ICE IDIQ.
5. **The Baptiste Group LLC** held ACF **90ZU0278 ($15,467,873, 2019-02-01 → 2022-04-01)**, **90ZU0285
   ($2,198,447)** and **90ZU0391** — residential shelter services for unaccompanied children.

**Why this matters, stated as inference and labelled as such:** the child-welfare side of the UAC system (ORR
shelters, home studies, post-release services) is the origin of the address, sponsor and family data that the ICE
"safety verification" visits are designed to confirm. Three firms sit on both sides of that line, and the largest of
the three routes its ICE work through an affiliate with no prior federal record at all. **That is a documented
structural conflict; it is not, on this evidence, proof of data transfer, and I found none.** The PWS data list
(SYNTHESIS §3b) is the thing to test it against.

### 2D. Capability disclosure — a clean, uniform negative
I fetched all 18 awardee sites (`work-M/web/`) and word-boundary-scanned the rendered text.
**Not one awardee website mentions ICE, DHS, immigration, "unaccompanied", "safety verification", "wellness check",
sponsors, or child welfare.** The only "child"/"sponsor" hits in the whole set are on **compassconnections.org** —
the ORR affiliate, not the awardee. What the sites *do* advertise: executive protection and bodyguarding
(Severance), fugitive recovery — "3,000+ Fugitives Located or Apprehended" (Alpha Recovery), facilities services
(Baptiste), IT/consulting (Applied Intellect, Septimo), healthcare staffing (Caduceus), disaster construction
(Lemoine), and skip tracing/surveillance/address verification (SIVS). **Three of the eighteen have no usable web
presence at all**: EagleGrace Global (**no domain, no captures ever**), Security Insights (**404**), The Baptiste
Group (SAM URL dead; live site a 2.6 KB stub).

### 2E. Address-type test — objective, not eyeballed
I counted SAM registrants at each cohort street address (unit-agnostic) across the whole extract:

- **8735 Dunwoody Place, Atlanta GA — 148 registrants.** Alpha Recovery's sole POC uses mailbox **#6828** here.
  This is a **mail-drop/agent mill**, definitively (co-tenants: hauling, snacks, counselling, film LLCs).
- **1530 Wilson Blvd, Arlington VA — 49 registrants** (Response AI's mailing suite; virtual-office layer).
- **515 S Flower St, Los Angeles — 16 registrants** (Origin's 18th floor, mixed real tenants + virtual layer).
- **1881 Campus Commons Dr, Reston — 14** (SOSi's genuine HQ + its own subsidiaries).
- **38 Windy Walkway, King Cove AK — 11** (the King Cove ANC family).
- **10408 Courthouse Rd, Spotsylvania VA — 4** (Savvy Professor's "Unit 570" mailbox).
- **Single-registrant addresses (genuine premises or a residence): EagleGrace, Security Insights, NPS, Savvy
  Professor (physical), Baptiste (both), Compass United (Wurzbach).** Severance: **0** in March-26 — it had not yet
  registered.

### 2F. Cross-program overlap — exactly three firms, no more
Intersecting the 14 skip-tracing UEIs with the 18 UAC UEIs: **National Protective Services (`W4AUG3SNRTL6`),
Response AI Solutions (`ZE2JVFS8ML75`), SOS International (`L3VCKMD7J585`)** — **3 firms, and no others.**
**B.I. Incorporated / GEO is NOT a UAC awardee**; its cross-program presence is via the separate skip-tracing IDIQ
and ISAP V, per the geo-group profile (cited, not re-derived). Beyond UEI identity, the §2A scan found **no
corporate-family bridge** between any skip-tracing awardee and any UAC awardee.

---

## 3. TASK 3 — pattern-match against the Wave-1 newcomer profile

The Wave-1 profile: recently formed, thin/no federal history, residential or nondescript address, SAM-registered
close to the solicitation. Scoring all 18 (each criterion sourced above):

| Firm | Zero federal $ pre-2025 | Residential / mail-drop | SAM reg within 12 mo of solicitation | Entity <3 yrs at award | **Score** |
|---|:--:|:--:|:--:|:--:|:--:|
| **Severance Security Services** | ✅ | ✅ residence | ✅ **initial reg 2026-03-23** | ✗ (2017) | **3/4** |
| **Savvy Professor LLC** | ✅ | ✅ residence + mailbox | ✅ **initial reg 2026-02-05** | ✅ (2024) | **4/4** |
| **EagleGrace Global LLC** | ~ ($53,268) | ✅ residence | ✅ 2024-09-10 (19 mo) | ✅ (2024) | **3.5/4** |
| **Alpha Recovery LLC** | ✅ | ✅ **148-tenant mail drop** | ~ 2024-06-18 | ✅ (2022) | **3.5/4** |
| **Septimo Solutions LLC** | ✅ | ✅ residence | ~ 2024-07-02 | ✅ (2023) | **3.5/4** |
| **Response AI Solutions** | ✅ | ✅ residence + 49-tenant suite | ~ 2023-05-30 | ✅ (2023) | **3.5/4** |
| **Security Insights LLC** | ✅ | ✅ residence | ~ 2024-09-04 | ✗ (2019) | **3/4** |
| **National Protective Services** | ✅ | ~ single-tenant | ✅ 2025-11-19 | ✗ (2008) | **3/4** |
| **Origin Investigations Inc** | ✅ | ~ shared 18th floor | ✗ (2016) | ✗ (2016) | **2/4** |
| **Critical Response Strategies** | ✅ | ✗ office park | ✗ (2022) | ✗ (2021) | **1.5/4** |
| **Compass United** | ✅ | ✗ office suite | ✗ (2022) | ✗ (2000) | **1/4** — *but zero-history affiliate of a $3B ORR grantee* |
| **The Baptiste Group** | ✅ contracts (has ORR grants) | ~ residence-ish | ✗ (2015) | ✗ | **1.5/4** |
| **Lemoine Disaster Recovery** | ✅ under this UEI | ✗ | ✗ (2017) | ✗ | **1/4** — subsidiary of an established parent |
| Delta Point · Applied Intellect · Caduceus · Continuity Global · SOSi | ✗ | ✗ | ✗ | ✗ | **0/4** — genuinely established |

**Counts:**
- **12 of 18 had ZERO federal prime awards before 2025-01-01**: Alpha Recovery, Compass United, Critical Response
  Strategies, Lemoine DR, National Protective Services, Origin Investigations, Response AI, Security Insights,
  Septimo, Severance, Savvy Professor, The Baptiste Group. A 13th, EagleGrace, had $53,268.
- **5 are established federal contractors**: SOSi ($1.93B), Continuity Global ($565M), Caduceus ($280M),
  Delta Point ($72M), Applied Intellect ($42M).
- **8 of the 13 newcomers operate from a residence, a mailbox, or a virtual-office suite.**

**Timing against the 2026-04-09 solicitation posting — the precise, checkable facts:**
- **Severance Security Services: initial SAM registration 2026-03-23, activated 2026-04-10.** The firm had never
  been in SAM before; it activated **one day after** the solicitation posted and holds a **$779,000,000** ceiling.
  **This is the tightest timing in either program.**
- **Savvy Professor: initial SAM registration 2026-02-05 — 63 days before posting** (see the correction in §5).
- **National Protective Services: initial SAM registration 2025-11-19**, nine days after the *skip-tracing*
  solicitation issued (previously established, restated here for the cohort view).
- **Critical Response Strategies' SAM record was last updated and reactivated on 2026-04-09 — the exact day the
  solicitation posted.** Its expiration is 2027-03-30, so this falls in its normal annual renewal window; **I read
  this as coincidence, not signal**, and flag it only so nobody else mistakes it for one.
- **11 of 18 refreshed SAM between 2026-03-23 and 2026-06-01.** An active SAM registration is a precondition of
  award, so pre-award renewal is expected. **Do not publish this as clustering.**
- **Three did NOT refresh**: Origin Investigations (last activated 2025-07-29), Security Insights (2025-08-27,
  **expires 2026-08-25**), Continuity Global (2025-08-14, expired 2026-08-12 on the snapshot's terms).

---

## 4. RANKED — which firms warrant a full workup

1. **Compass United / BCFS / Compass Connections** — the strongest new lead in the wave. An ORR shelter-and-
   post-release family routing ICE child-visit work through a zero-history affiliate. Next: current TX
   public-information report (post-2002 board), Compass United's IRS determination and Form 990s, BCFS↔FirstDay
   Foundation restructuring, and whether any ORR-derived data touches the ICE work.
2. **Severance Security Services LLC** — $779M ceiling to an executive-protection firm that entered SAM 17 days
   before the solicitation, from a rural residence, with no certifications and no federal history. Next: Alabama SOS
   filing, the Tracy Harris / Tracey Matthews / Timothy W Harry identity question, AL security-guard licensure.
3. **Septimo Solutions LLC** — the **largest ceiling in the program ($3,105,250,000)** held by a 2023 Virginia LLC
   operating from a Maryland house, with zero federal awards and a website first archived in April 2025. Next:
   identify **Miguel Howe** (Aurelian Group's FEMA/EMI contract is his only visible federal performance), VA SCC
   filing, and what the "Small Business Joint Venture" flag refers to.
4. **Security Insights LLC** — $1,982,235,852 ceiling to a **sole proprietorship** at a Rancho Viejo house whose
   website now 404s, and which formed **Security Insights Solutions LLC on 2026-06-22**, twenty days after award.
   Next: TX DPS investigator/guard licensure for Jaime Salazar; purpose of the new entity.
5. **EagleGrace Global LLC** — $1,080,860,000 to a **2024** Georgia LLC at a single-family home with **no website
   in existence** and no employee count in any source. Next: GA SOS filing; who Sandra Ofili is.
6. **Alpha Recovery LLC** — $316,735,974 to a fugitive-recovery firm whose entire SAM contact surface is one person
   at a **148-tenant mail drop**, on a domain that predates the company by two decades. Next: GA SOS; provenance of
   the "3,000+ fugitives" claim; who owned alpharecovery.org before 2023.
7. **Origin Investigations Inc** — ten years in SAM, **zero federal awards**, then $536,620,000; shares a virtual
   18th floor with two same-owner shells (Origin Intelligence, ZeroFour) that have never won anything. Next: CA SOS
   for all three; CA PI licence for Jayden Brant.
8. **The Baptiste Group LLC** — the only awardee flagged **DEBT SUBJECT TO OFFSET = Y** in the SAM extract, with a
   dead official website and a former ORR shelter grant history. Next: nature and status of the federal debt; GA SOS.
9. **Delta Point LLC** — the ANC 8(a) route into a $1.5B ceiling. Not a shell, but the King Cove Corporation JV
   lattice (9 sibling entities, most with zero awards) is the classic ANC pass-through geometry and deserves a
   look at who actually performs.
10. **Critical Response Strategies LLC** — real office, CT Corporation agent, zero federal history, $650M ceiling,
    factored receivables (#14390). Lower priority: it looks like a genuine small firm out of its depth.

**Explicitly deprioritised as normal:** SOSi, Continuity Global, Caduceus, Applied Intellect (its ORR
crossover is the interesting part, not the firm), Lemoine Disaster Recovery.

---

## 5. CORRECTIONS AND EXTENSIONS TO STORED FINDINGS

| Finding | Status | Correction / extension |
|---|---|---|
| **#14391** (Savvy Professor) | **CORRECTION — arithmetic** | Says Savvy Professor "SAM-registered 2026-02-05, **35 days** before the solicitation posted." **2026-02-05 → 2026-04-09 is 63 days.** Either the interval or one date is wrong; the registration date 2026-02-05 is confirmed in both the March SAM extract (`registration_date=20260205`) and HigherGov (`initial_registration_date 2026-02-05`). Use **63 days**. |
| **#14383** (ORR crossover) | **EXTENSION** | Its name-collision warning is correct — Compass United and Compass Connections are distinct legal entities. But they are **under common control**: Compass United's own SAM registration names **BCFS Health and Human Services** as its parent, and the TX Comptroller record shows the same registered agent, suite, PO box and eight shared directors. The right formulation is "distinct entities in the same corporate family," not "do not conflate them" alone. |
| **#14388** (no employee headcount) | **CORROBORATED, with a caveat** | HigherGov exposes a coarse `employee_count` bucket absent from the SAM extract. It is **not** a headcount: 14 of 18 read "<500", two read "Not Available" (EagleGrace, Origin). Only four carry meaningful buckets — Continuity ">1500", SOSi "1001-1500", Lemoine "751-1000", Compass Connections ">1500". The finding stands for the small firms. |
| **Todd Thompson exclusion** | **REFUTED (name collision) — checked and clean** | The SAM exclusions extract contains **Todd *A.* Thompson**, FEMA, Ineligible (Proceedings Completed), active 2024-06-27, cross-referenced to *Trailblazer Financial Corporation* and *Christolyst Properties*. Savvy Professor's principal is **Todd *M.* Thompson**. **Not the same person.** |
| **SAM exclusions, whole cohort** | **CONFIRMED CLEAN** | Zero hits on all 18 awardee UEIs plus BCFS and Compass Connections, and zero substantiated hits across 36 named principals, in `SAM_Exclusions_Public_Extract_V2_26062.CSV` (167,862 rows, 2026-03-03). |
| **"18 offers / 18 awards"** | **WORDING** | Per the orchestrator: *"each of the eighteen UAC award records reports eighteen offers received, and ICE issued eighteen IDIQ awards."* No anomaly claim — no held dataset enumerates awardees per ICE solicitation. |
| **Subaward counts** | **DO NOT USE** | All 18 report `subaward_count = 0`. Per codex-Q, 228/228 ICE prime awards do; the field has **no discriminating power** and must not be cited as a front/pass-through signal. |

---

## 6. UNCONFIRMED / NOT DONE — stated plainly

**Could not pin (checked, failed):**
- **Live SAM entity records for Critical Response Strategies (`ZDN8V5GKJ959`) and Severance Security Services
  (`DKFGF41MVR41`).** The SAM API key hit its **10-request/day cap (HTTP 429)** on the first two calls. Both firms'
  SAM facts above come from **HigherGov's live SAM mirror only** and are unverified against sam.gov directly.
  Their full POC blocks (alternate/past-performance/electronic slots) and complete NAICS/PSC strings are therefore
  **untested in the cross-connection matrix**. This is the one real gap in the §2A negative result.
- **Georgia SOS** (ecorp.sos.ga.gov) — HTTP 403 to both the guest-logon and search endpoints. **Alpha Recovery,
  EagleGrace Global, The Baptiste Group, Caduceus** have no state-registry confirmation.
- **Alaska DCCED** bulk corporations download — HTTP 403. Delta Point's ANC ownership is inferred from SAM business
  type `05` + shared POCs with The King Cove Corporation, **not** from a registry filing.
- **crt.sh** returned HTTP 502 for six of eight domains; only alpharecovery.org and criticalresponsestrategies.com
  produced timelines.
- **caduceusstaffing.com** and **sosi.com** could not be read (connection reset; 212-byte bot wall).
- **Employee counts** — no authoritative headcount exists for any small awardee (corroborates #14388).
- **Email addresses and phone numbers** — the SAM public extract does not contain them. The POC email/phone leg of
  the cross-connection matrix **cannot be run from this source at all**; it needs live SAM entity API pulls
  (`--sections all`) once the rate limit resets.
- **Organiser/incorporator comparison** — requires state filing documents, all gated (below).
- **OpenSanctions and CourtListener** — **not run** on this cohort; out of my assignment's scope and I did not want
  to claim coverage I do not have.

**NEEDS MANUAL OPENCORPORATES** (API is dead; these are the lookups that would close the biggest gaps):
1. **Severance Security Services LLC** — Alabama, formed 2017-10-23 (EIN 81-5186985). Members, organiser, and
   whether "Tracy Harris" (SAM POC) = Tracey Matthews or Timothy W Harry.
2. **EagleGrace Global LLC** — Georgia, formed ~2024-08-28. Organiser, members, registered agent. *(highest value —
   $1.08B ceiling, no website, no registry record at all)*
3. **Alpha Recovery LLC** — Georgia, entity start 2022-10-15. Organiser and members; is Deion Hackworth sole member?
4. **The Baptiste Group, LLC** — Georgia, 2015-01-01. Members; and the nature of the federal debt behind
   `DEBT SUBJECT TO OFFSET = Y`.
5. **Septimo Solutions, LLC** — **Virginia** (SAM `state_of_incorporation = VA`, physical address MD). Organiser,
   members, and the identity of **Miguel Howe**; also **Aurelian Group LLC**.
6. **Savvy Professor LLC** — Virginia, 2024-07-17. Members; and resolve the second Savvy Professor UEI
   **`HJ14W736NFM1`**, which HigherGov shows as the SAM "parent" with no CAGE and no registration — probably a
   duplicate registration, but it should be confirmed rather than assumed.
7. **Origin Investigations Inc**, **Origin Intelligence Inc**, **ZeroFour Inc** — California. Officers/directors of
   all three; confirm Jayden Brant controls all three.
8. **Compass United** — Texas nonprofit 0160062501: the **current** public-information report (the feed's is 2002),
   plus its IRS determination letter and any Form 990.
9. **Security Insights Solutions LLC** — Texas 0806663033, formed 2026-06-22. Members and stated purpose.
10. **Cyber DI LLC** and **GL Solutions Inc** — the two new Response AI-adjacent entities (hand to fable-N).

**CAPTCHA / gated registries for the user to run by hand:**
- **Georgia SOS** (ecorp.sos.ga.gov) — 403 to automated access. Four firms.
- **Alaska** (commerce.alaska.gov) — 403. Delta Point + King Cove Corporation.
- **Maryland SDAT** — reCAPTCHA v2. Septimo Solutions' Severna Park presence.
- **Virginia SCC** (cis.scc.virginia.gov) — Applied Intellect, Savvy Professor, Septimo (VA-incorporated), RCA Funding.
- **Delaware** — SOSi, Continuity Global, Response AI.
- **Alabama SOS** — Severance Security Services.
- **California SOS BizFile** — the three Origin/ZeroFour entities.

---

## 7. ARTEFACTS (all under `/tmp/osint-FRmkNLeM/work-M/`)
`uac_idiqs_raw.json`, `uac_idiq_detail.json` (18 IDIQ award records) · `task_orders.json` / `.txt` (19 task orders,
$86,822,317.14) · `prior_history.json` / `.txt` (per-UEI federal history) · `orr_crossover.txt` (assistance awards)
· `bcfs.json` / `.txt` (BCFS/Compass family) · `sam_local_18.txt`, `sam_raw_18.txt` (SAM extract rows + full POC
blocks) · `xconnect.py` / `.txt` / `.json` (cross-connection scan, 3,530 lines) · `addr_density.txt`
(SAM-registrants-per-address) · `satellites.txt` · `hg/aw-*.json` (HigherGov awardee records) · `web/*.html`
(19 fetched sites) · `tx-compass-united.json`.
