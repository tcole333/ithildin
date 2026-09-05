# fable-N — Response AI Solutions LLC: beneficial ownership, the GER twin, Kraemer/Vela, website forensics

**Wave 3 · 2026-07-27 · profile tech-right · read-only DB, no repo writes**
Work products: `/tmp/osint-FRmkNLeM/work-N/`

> ## ORCHESTRATOR VERIFICATION NOTE (2026-07-27)
>
> Two load-bearing claims were independently re-pulled from FPDS-NG. Both hold on substance; one needs a
> corrected window.
>
> **§5(a) woman-owned — conclusion CONFIRMED, window WRONG (sampling artifact).** This report read only the
> **first page** of the FPDS feed (10 of 30 actions; the feed pages 10 at a time). Across **all 30** Response
> AI contract actions, `isWomenOwned` / `isWomenOwnedSmallBusiness` are **true on 15 actions**, not 4, and
> the range runs **2025-04-02 → 2026-04-20**, not "2024-12-31 → 2025-12-02" (that end-date came from mixing
> in GER's records). The latest true stamps — `N0018926FL072` P00001 (2026-04-01) and `M6845026FB001` mod 0
> (2026-04-20) — are **after** the March 2026 SAM extract that lacks the code. So the "certification may have
> lapsed before March 2026" reading is **not supported**; sporadic field non-population is the better
> explanation, which is exactly what the report's own lockstep observation implies.
> **Confirmed unchanged:** `isSmallBusiness` moves in perfect lockstep with the two women-owned flags on all
> 30 rows, and **neither ICE instrument is flagged** — `70CDCR26D00000008` (mod 0 and P00001),
> `70CDCR26FR0000020` P00001, and `70CDCR26P00000013` are all false.
> **Use this wording instead of §5's:** *recorded in FPDS as a women-owned small business on fifteen contract
> actions signed between 2025-04-02 and 2026-04-20, while the March 2026 SAM registration carries no
> women-owned code; neither ICE instrument is flagged. Whether the certification lapsed or the records were
> simply not populated cannot be determined from FPDS alone.*
>
> **§5(b) Delaney Hall — fully CONFIRMED.** Re-pulled: PSC **W099** (LEASE OR RENTAL OF EQUIPMENT —
> MISCELLANEOUS), NAICS **532490** (equipment rental and leasing), `extentCompeted=C` NOT COMPETED,
> `solicitationProcedures=SSS` ONLY ONE SOURCE, `reasonNotCompeted=URG` FAR 6.302-2, 1 offer, and
> createdBy = lastModifiedBy = approvedBy = **JBOUDREAUX7012**. The rental reframe stands: the premise that
> an installation subcontractor was structurally required is wrong.
>
> **Cross-check from codex-Q (base rates):** "zero reported subawards" carries **no** evidentiary weight in
> ICE contracting at all — **228 of 228** ICE prime awards in the geo-group archive report zero subawards
> with blank amounts, including every award over $100M. This independently reinforces §5(b)'s caution and
> generalizes it beyond the rental coding.
>
> Method note for future waves: **always page the FPDS feed** (`tools/query_fpds.py` follows `rel=next`
> automatically). A first-page-only read silently truncates at 10 actions and will understate any pattern.

---

## 0. BOTTOM LINE

1. **Finding #14392 is CONFIRMED, and now confirmed from federal data rather than the company's own website.**
   HigherGov's SAM-derived awardee record for Global Emergency Response Inc carries
   `awardee_key_parent = 509623647 = Response AI Solutions` / `parent_flag: false`. GER's FPDS vendor
   address history independently traces the ownership chain Augusta GA → Lowell AR (Central Research) →
   Arlington/Great Falls VA (Response AI). This is a **disclosed parent-subsidiary relationship, not a
   concealed twin.** #14392 did not overstate.

2. **Beneficial ownership of Response AI Solutions LLC itself is NOT established and I could not establish
   it.** SAM records **no parent entity at all** (`parent_flag: true`, parent = itself). Delaware gives only
   Corporation Service Company. Virginia's registry is reCAPTCHA-gated. Fairfax deed images sit behind a
   MyFairfax login I am not permitted to create. **What is established is control, not ownership**: James
   Kraemer is President and government POC of both companies and personally connected to the registered
   address.

3. **A third Kraemer entity was previously unrecorded: CYBER DI LLC** (UEI W4MQH3KFHYR7, CAGE 96VT2, Great
   Falls VA, POC "JAMES KRAEMER, CEO"). It is **Cyber Data Intelligence**, named in 2020 trade press as a
   subsidiary of Kraemer's Data Intelligence Technologies — i.e. a piece he kept after selling DIT to
   Axiologic. Its own website's contact address is **1530 Wilson Blvd Suite 650** — the exact suite Response
   AI and GER use for mail.

4. **The "woman-owned" open item is RESOLVED — and the current DB position needs correcting.** SYNTHESIS §5
   says the descriptor needs "an award-level source or drop." **There is an award-level source.** FPDS-NG
   stamps `isWomenOwned=true` and `isWomenOwnedSmallBusiness=true` on **four** Response AI contract actions
   and **three** GER contract actions, all signed between 2024-12-31 and 2025-12-02. It is absent from the
   March 2026 SAM extract and from later award records. Do not drop it; restate it with the window.

5. **#14394 is materially right on the man and materially overstated on the capability.** Kraemer founded
   Data Intelligence Technologies (2010), took it to #1 on the 2020 Washington Technology Fast 50, sold it to
   Axiologic in May 2022 — all confirmed. But DIT was a **data-engineering/analytics services firm for DoD and
   the IC** (SIGINT/RF, geospatial, open source, cyber). I found **no source** describing it as
   "entity-analytics and link-analysis," and nothing tying it to person-location or skip tracing. The claim
   "the same capability ICE later bought from him" is not supported by any source I could find.

6. **Two new separation-of-duties instances, both on Response AI ICE instruments** (found while working
   Task 4b — flagging for opus-O to fold into the sweep rather than double-count):
   - **70CDCR26P00000013** (Delaney Hall fencing PO): created + modified + approved by **JBOUDREAUX7012**.
   - **70CDCR26FR0000092** (the $3,670,800 UAC first task order): created + modified + approved by
     **ISOMPPI7012** — who had himself approved the parent IDIQ two weeks earlier.

7. **New agency thread: HHS/ACF.** Response AI holds an **Administration for Children and Families** case-
   management contract, awarded through Interior's franchise acquisition shop. $4,072,037 obligated,
   $21,223,448.29 base-and-all-options. So the same firm sells child-related case management to ACF **and**
   child-visit services to ICE ERO.

---

## 1. CORPORATE STRUCTURE (as established; unknowns marked)

```
                    ???  UNKNOWN BENEFICIAL OWNER(S)             <-- NOT ESTABLISHED
                     |   (DE agent = Corporation Service Company;
                     |    SAM records NO parent for RAI;
                     |    VA SCC reCAPTCHA-gated; deeds behind login)
                     v
     +-------------------------------------------------------------+
     |  RESPONSE AI SOLUTIONS, LLC          UEI ZE2JVFS8ML75        |
     |  CAGE 9MFB2 · DE LLC · entity start 2023-05-10               |
     |  SAM reg 2023-05-30 · DE entity 7453000                      |
     |  Physical: 843 Constellation Dr, Great Falls VA 22066-2501   |
     |            (single-family house, parcel 0131 03  0060)       |
     |  Mail:     1530 Wilson Blvd Ste 650, Arlington VA 22209      |
     |            (= Office Evolution Arlington-Rosslyn coworking/   |
     |               virtual-office suite; 21 SAM registrants)      |
     |  Primary NAICS 541614 · business_types 27~2X                 |
     |  POCs: JAMES KRAEMER (govt, PRESIDENT) · NATALIA VELA (elec) |
     |        COLBY FARROW (past performance)                       |
     |  HigherGov parent_flag = TRUE  -> NO PARENT IN SAM           |
     +-------------------------------------------------------------+
                     |
                     | 100% — disclosed; acquired 2023-10-01 from Central Research Inc
                     v
     +-------------------------------------------------------------+
     |  GLOBAL EMERGENCY RESPONSE INC       UEI FE98C4148NH3        |
     |  CAGE 7R7C1 · DE corp · entity start 2018-07-18              |
     |  SAM reg 2021-06-03 · product: HC Standard(R)                |
     |  Same physical + same mailing address as RAI                 |
     |  Primary NAICS 513210 (software publishers)                  |
     |  POCs: JAMES KRAEMER (govt, PRESIDENT) · NATALIA VELA (elec) |
     |        STAN KUZIA (past performance) · KRAEMER (alt elec)    |
     |  HigherGov awardee_key_parent = 509623647 (Response AI)      |
     |  Business founded 2004 in Augusta GA                         |
     |  Ownership chain (from FPDS vendor addresses):               |
     |     Augusta GA (2017-2021) -> Lowell AR / Central Research   |
     |     (2022-2025) -> Arlington + Great Falls VA (2024-12 on)   |
     |  Interim step: "GER becomes division of Pro-Sphere Tek"      |
     |     (ger911.com blog, 2016-09-14) — UNVERIFIED beyond blog   |
     +-------------------------------------------------------------+

     SIBLING (not a subsidiary — no ownership link found, only shared control person):
     +-------------------------------------------------------------+
     |  CYBER DI LLC                        UEI W4MQH3KFHYR7        |
     |  CAGE 96VT2 · VIRGINIA LLC · entity start 2021-09-01         |
     |  SAM reg 2021-09-29 (expires 2026-04-26)                     |
     |  Physical: 9890 Windy Hollow Rd, Great Falls VA 22066-3551   |
     |  Website contact addr: 1530 Wilson Blvd Ste 650 Arlington VA |
     |  POC: JAMES KRAEMER, title CEO · NAICS 541511                |
     |  Business: CMMC / AI-security certification training (ISACA  |
     |            Approved Training Organization), sells courses    |
     |  ZERO federal prime awards                                   |
     +-------------------------------------------------------------+

     FORMER (sold — no current link):
        DATA INTELLIGENCE TECHNOLOGIES INC  UEI KN34NSTNM2A5, CAGE 6GJ47
        founded 2010 · #1 on 2020 WT Fast 50 · $8.5M FY2019 revenue
        SOLD TO AXIOLOGIC SOLUTIONS LLC, May 2022 (terms undisclosed)
        SAM now shows DIT at 8280 Willow Oaks Corporate Dr Ste 600, Fairfax VA
        — the SAME address and SAME POC (ANDY BARATTA) as Axiologic. Integration confirmed.

     OUTSOURCED BACK OFFICE (inference, see §4):
        GL-SOLUTIONS INC. UEI J2CLFENPWL52, 1530 Wilson Blvd Ste 650, NAICS 541611,
        president Gregory Llinas — accounting/financial/contract administration for
        federal contractors. Natalia Vela's LinkedIn lists her as a GL-Solutions consultant
        who does "setup and maintenance of Government contracts."
```

---

## 2. TASK 1 — the Global Emergency Response "twin": VERIFIED, #14392 stands

### CONFIRMED — the shared-identity facts are real
Source: **local SAM March 2026 Public Extract** (`datasets/sam.db`, from
`SAM_PUBLIC_UTF-8_MONTHLY_V2_20260301.dat`), records id 854317 and id 151861. Retrieved 2026-07-27.
(SAM.gov live API returned HTTP 429 rate-limit all session; the monthly bulk extract is the same
authoritative source.)

| Field | Response AI Solutions LLC | Global Emergency Response Inc |
|---|---|---|
| UEI / CAGE | ZE2JVFS8ML75 / 9MFB2 | FE98C4148NH3 / 7R7C1 |
| Physical | 843 CONSTELLATION DR, GREAT FALLS VA 22066-2501 | **identical** |
| Mailing | 1530 WILSON BLVD STE 650, ARLINGTON VA 22209 | **identical** |
| Govt POC | JAMES KRAEMER, PRESIDENT | **identical** |
| Alt govt POC | NATALIA VELA | **identical** |
| Electronic POC | NATALIA VELA | **identical** |
| Past-perf POC | COLBY FARROW | STAN KUZIA |
| Alt electronic POC | — | JAMES KRAEMER |
| `naics_codes` string | 559 chars, 69 codes | **byte-identical (verified `==` in Python)** |
| `psc_codes` string | `5820~5821~5825~5826~L035~R499~R699~R706` | **byte-identical** |
| `business_types` | `27~2X` | `2X` |
| State of incorporation | DE | DE |
| Entity start | 2023-05-10 | 2018-07-18 |
| SAM registration | 2023-05-30 | 2021-06-03 |
| Primary NAICS | 541614 | 513210 |

### CONFIRMED — it is a disclosed parent-subsidiary, by three independent routes

**(a) Federal entity data (strongest, and new).** HigherGov awardee API, UEI FE98C4148NH3, retrieved
2026-07-27 → `/tmp/osint-FRmkNLeM/work-N/hg-ger.json`:
```
"awardee_key_parent": { "awardee_key": 509623647, "clean_name": "Response Ai Solutions",
                        "uei": "ZE2JVFS8ML75", "cage_code": "9MFB2" },
"parent_flag": false
```
The same call for UEI ZE2JVFS8ML75 returns `parent_flag: true` with itself as parent — **Response AI
reports no parent of its own.** This is SAM immediate/ultimate-parent data surfaced through HigherGov, i.e.
the relationship is declared to the government, not merely marketed.

**(b) FPDS vendor-address history traces the ownership chain physically.** FPDS-NG ATOM,
`VENDOR_UEI:"FE98C4148NH3"`, 10 entries, retrieved 2026-07-27
(`https://www.fpds.gov/ezsearch/FEEDS/ATOM?FEEDNAME=PUBLIC&q=VENDOR_UEI%3A%22FE98C4148NH3%22`):

| Award | Signed | FPDS vendor street address |
|---|---|---|
| 70FA2018P00000012 mod 0 | 2017-10-30 | 159 E CRAIG SIMS PKWY, **AUGUSTA** (GA) |
| 70FA2018P00000012 P00003 | 2020-10-29 | 159 E CRAIG SIMS PKWY, AUGUSTA |
| 70FA2018P00000012 P00004 | 2021-10-28 | 159 E CRAIG SIMS PKWY, AUGUSTA |
| 70FA2023P00000001 mod 0 | 2022-10-24 | 122 N BLOOMINGTON ST STE I, **LOWELL** (AR = Central Research HQ) |
| 70FA2023P00000001 P00002 | 2024-11-12 | 122 N BLOOMINGTON ST STE I, LOWELL |
| N0017825D7393 mod 0 | 2024-12-31 | **1530 WILSON BLVD STE 650, ARLINGTON** |
| N0017825D7393 P00002 | 2025-03-06 | 1530 WILSON BLVD STE 650, ARLINGTON |
| N0017825D7393 P00003 | 2025-04-23 | 1530 WILSON BLVD STE 650, ARLINGTON |
| 15A00025PAQA00205 mod 0 | 2025-08-04 | **843 CONSTELLATION DR, GREAT FALLS** |
| 70FA2023P00000001 P00003 | 2025-12-16 | 122 N BLOOMINGTON ST STE I, LOWELL |

The Augusta → Lowell → Arlington/Great Falls progression is exactly the announced chain. (The stale Lowell
address persisting on the FEMA line item in Dec 2025 is ordinary FPDS record hygiene, not a contradiction.)

**(c) The company's own live site.** responseai.us homepage, "About Us" section, fetched 2026-07-27 —
verbatim: *"We are backed by our wholly owned subsidiary Global Emergency Response, Inc. (GER) and its HC
Standard® platform."*

> **Small correction to #14392's provenance line:** there is **no separate `/about` page.** The live
> `pages-sitemap.xml` (lastmod 2026-07-12) lists exactly nine pages: `/casemanagement`, `/` , `/vendors`,
> `/contract-vehicles`, `/logistics`, `/careers`, `/emergency-tech`, `/contact-5`, `/news`. Fetching
> `/about` returns the homepage. The disclosure is an **"About Us" section on the homepage**. Cite it that
> way.

### CHANGED — the October 2023 newsroom post is **not** a contemporaneous 2023 publication

This matters because #14392 leans on "an October 2023 newsroom post documents the acquisition."
The post exists and says what #14392 says it says. But it was **published to the site after 2026-05-11**.

Evidence — archived `/news` listings, all with **no pagination control present** (so each capture shows the
site's complete post list at that moment):

| Wayback capture of `/news` | posts listed | oldest post | GER-acquisition post present? |
|---|---|---|---|
| `20251008041740` (2025-10-08) | **3** | Jul 1 2025 | **NO** |
| `20260122233007` (2026-01-22) | **6** | Jul 1 2025 | **NO** |
| `20260511061815` (2026-05-11) | **8** | Jul 1 2025 | **NO** |
| live, fetched 2026-07-27 | **11** (per `blog-posts-sitemap.xml`) | Oct 1 2023 | **YES** |

The live post carries the byline *"Response AI Solutions, LLC · Oct 1, 2023 · 2 min read · Updated: Jul 7"*
and `blog-posts-sitemap.xml` has `lastmod 2026-07-07`.
URL: `https://www.responseai.us/post/response-ai-solutions-acquires-global-emergency-response-inc-expanding-its-emergency-tech-and-she`

**Corroborating pattern — the newsroom backdates routinely, and this is documentable:**
- In the 2025-10-08 capture, **all three** posts (datelined July 1, Sept 5, Sept 25 2025) carry the byline
  date **"Sep 24"** — the blog was stood up ~2025-09-24 and seeded with backdated releases.
- In the 2026-01-22 23:30:07 capture, the CMMC post datelined **"January 15, 2026"** carries the byline
  **"13 minutes ago"** — actually published ~2026-01-22 23:17 UTC.
- The DCAA post's byline moved from **"Aug 4, 2025"** (Jan 2026 capture) to **"Aug 5, 2025"** (May 2026
  capture) — post dates are edited after publication.

**Fact vs inference, stated plainly:** *Fact* — the post is absent from every archived complete post list
through 2026-05-11 and present now with a 2026-07-07 lastmod. *Inference (high confidence)* — it was
written and posted in ~July 2026 and given an Oct 1 2023 dateline. *This does not impeach the acquisition
itself*, which is independently confirmed by SAM parent data, FPDS addresses, and the March 2020 Central
Research acquisition press. It does mean **the post is not usable as contemporaneous 2023 evidence**, and
it is itself a small piece of the site-management pattern in §6.

### Verdict on the "concealed twin" framing
**REFUTED for this pair.** Response AI owns GER, says so publicly, and the relationship is in federal entity
data. The residual, still-true observation is narrower and worth keeping: **byte-identical NAICS and PSC
strings across a parent and a subsidiary with completely different businesses** (logistics consulting vs
software publishing) means one person filled in both SAM profiles by copy-paste, and GER's SAM profile
therefore advertises capability GER does not have — including NAICS 561611/561612/561613 (investigation,
security guards, armored car), which its 20-year patient-tracking software business plainly does not
perform.

### GER's actual federal footprint is tiny — worth stating for scale
USASpending, retrieved 2026-07-27: **6 awards, lifetime.**
- `70FA2023P00000001` FEMA, HC Standard patient tracking, $189,978 (2022-11-01 → 2026-10-31)
- `70FA2018P00000012` FEMA, HC Standard patient tracking, $149,806 (2017-11-01 → 2022-10-31)
- `HT001521P0007` Defense Health Agency, "standard tracking surveillance software," $237,760 (2021-01-19)
- `15A00025PAQA00205` ATF, deployment tracking software maintenance, $97,375 (2025-09-30)
- `15A00024PAQA00260` ATF, deployment tracking software, $95,000 (2024-09-30)
- `N0017825F7393` Navy Seaport-NxG **minimum-guarantee** task order, **$500** (2025-03-06 → 2029-01-01)

**CONFIRMED — #14393's Seaport-NxG point.** The Seaport-NxG IDV `N0017825D7393` that responseai.us lists as
its own vehicle #6 is held by **the subsidiary**, and the only order under it is GER's $500 minimum
guarantee.

---

## 3. TASK 2 — beneficial ownership: what I established, and what I could not

### NOT ESTABLISHED — no public record names the owners of Response AI Solutions LLC
I want to be unambiguous: **I did not determine who owns Response AI Solutions LLC.** Every route was tried
and each is reported below with its outcome.

| Route | Result |
|---|---|
| **SAM parent fields** (via HigherGov) | **CONFIRMED NEGATIVE.** `parent_flag: true`, parent = itself. No immediate or ultimate parent CAGE. Ownership is held by natural persons or a non-registered vehicle. |
| **Delaware** (entity 7453000) | Dead end as briefed — agent is Corporation Service Company. |
| **Virginia SCC** | **BLOCKED — reCAPTCHA.** `https://cis.scc.virginia.gov/EntitySearch/Index` redirects to `/Cookie/CookieConsent` and the page contains `recaptcha-response`. The undocumented `api/BusinessEntity/Search` path 404s. Added to manual list. |
| **Foreign-entity registrations in other states** | **CHECKED, NOTHING FOUND.** Local `registry.db` (5.99M entities, FL/NY/CO/DC/OH/TX/NM/WY/NJ/PA/MA/MI/CA/VI/UK) returns **0 entities** for "Response AI Solutions" and **0** for "Global Emergency Response". No officer named Kraemer in any Great Falls/Arlington VA entity. |
| **Fairfax County deed images (CPAN)** | **BLOCKED — authentication.** `https://ccr.fairfaxcounty.gov/cpan/Document/LandRecords/27700/2112` 302s to the MyFairfax portal login. I did not create an account (prohibited). |
| **Fairfax County iCare (owner name)** | **BLOCKED — site down.** `icare.fairfaxcounty.gov/ffxcare/` returns "The System is currently unavailable due to maintenance," verified twice on 2026-07-27. |
| **FPDS vendor fields** | No ownership fields beyond socio-economic flags (§5) and address. |
| **CourtListener** | **CHECKED, ZERO.** Party searches for "Response AI Solutions", "Global Emergency Response", "Cyber DI" → **0 results** each. No litigation that would expose members. |
| **OpenSanctions / GLEIF / ICIJ / LittleSis** (`selector_pivot.py run "James Kraemer" --type name`, free adapters only) | **CHECKED, NOTHING RELEVANT.** 6 nodes, all ICIJ string noise ("Kraemer Boulevard, Brea CA", "Kraemer Contractors", Barbados addresses). No hit on the subject. |
| **SEC EDGAR** | Not applicable — the DIT→Axiologic sale was private-to-private, terms undisclosed; Axiologic is privately held. No registrant to search. |
| **OpenCorporates** | API dead per brief — see §8. |

### CONFIRMED — 843 Constellation Dr is a house, and the 2022 purchase price in #14394 is right
**Primary source: Fairfax County ArcGIS, `GIS/ParcelPlusSales` and `GIS/ParcelPlusAssessedValues`,
parcel `0131 03  0060`, retrieved 2026-07-27.**
Endpoint: `https://www.fairfaxcounty.gov/mercator/rest/services/GIS/ParcelPlusSales/MapServer/0/query`

Complete recorded sales history:

| Sale date | Type | Price | Validity | Deed book/page |
|---|---|---:|---|---|
| 1967-04-03 | — | $29,950 | Valid and verified sale | 02878 / 0223 |
| 2003-09-29 | — | $0 | No consideration | 15197 / 1635 |
| 2010-09-27 | Land & Building | $530,000 | Non-representative price based on comps | 21262 / 1594 |
| 2013-03-25 | Land & Building | $600,000 | Valid and verified sale | 23011 / 1622 |
| 2015-06-12 | — | $0 | No consideration | 24157 / 1897 |
| 2020-06-30 | Land & Building | $790,000 | Valid and verified sale | 26329 / 1023 |
| 2021-12-13 | — | $0 | No consideration | 27479 / 0906 |
| **2022-07-01** | **Land & Building** | **$975,000** | **Valid and verified sale** | **27700 / 2112** |

Tax year 2026 assessment: land $562,000 + building $475,650 = **$1,037,650**; land use code **011**
(residential). This **CONFIRMS #14394's "purchased 2022-07-01 for $975,000."**

**UNCONFIRMED: the grantee names.** The county's public GIS layers carry no owner field, iCare is down, and
the deed image needs a login. #14394's "recorded in Fairfax County deed records as Kraemer James and Kraemer
Elisabeth" is **plausible and consistent** with everything else but **I could not independently verify the
names.** A tertiary source (city-data, 2014 tax roll) shows the prior owner as **DAVID SU** with living area
**1,352 sq ft**, land **23,094 sq ft**, built 1965 — matching #14394's house description and consistent
with the 2013 $600,000 sale. Commercial listing sites give 2,172 sq ft / 4 bed / 3 bath, presumably
post-renovation (the assessed building value rose from $194,020 in 2014 to $475,650 in 2026).
**Deed book 27700 page 2112 is the exact document to pull manually.**

### CONFIRMED — 1530 Wilson Blvd Ste 650 is a coworking/virtual-office suite, and it is not evidence of anything
- **Suite 650 = Office Evolution Arlington-Rosslyn**, resold as a virtual address by Davinci Virtual,
  Alliance Virtual Offices, and Preferred Office Network. Per Preferred Office Network, "Suite 650 has 44
  executive style offices" with mailing and notary services.
- The March 2026 SAM extract has **33 registrants** at 1530 Wilson Blvd, of which **21 are in Suite 650**,
  including entities as unrelated as the Society of Research Administrators International, DT Global LLC,
  and Police2Peace Corp — the last of which spells it out as `SUITE 650 PMB 069` (private mail box).
- **Therefore: co-registration at Ste 650 carries no evidentiary weight.** #14392 already flagged this;
  I confirm it and reinforce it. The load-bearing links in this cluster are the **house** and the **named
  people**, not the suite.
- Worth noting for tone, not for allegation: every Response AI press release is datelined "Arlington, VA"
  and the homepage says "headquartered in Northern Virginia." The Arlington address is a mailbox; the
  operating address of record is a house in Great Falls.

---

## 4. TASK 3 — Kraemer and Vela

### JAMES KRAEMER

**CONFIRMED (primary, SAM March 2026 extract) — controls three federally-registered entities, all Great Falls VA:**

| Entity | UEI | CAGE | Title | Physical address | State of inc. | Entity start |
|---|---|---|---|---|---|---|
| Response AI Solutions, LLC | ZE2JVFS8ML75 | 9MFB2 | PRESIDENT | 843 Constellation Dr | DE | 2023-05-10 |
| Global Emergency Response Inc | FE98C4148NH3 | 7R7C1 | PRESIDENT | 843 Constellation Dr | DE | 2018-07-18 |
| **Cyber DI LLC** | **W4MQH3KFHYR7** | **96VT2** | **CEO** | **9890 Windy Hollow Rd** | **VA** | **2021-09-01** |

I swept every POC field in the 33-field SAM entity table for `KRAEMER` (43 unrelated hits, mostly farms,
credit unions and construction firms) and then narrowed to `first='JAMES'`: exactly these three.

**CONFIRMED (trade press + SAM) — Cyber DI = "Cyber Data Intelligence", a Data Intelligence Technologies
subsidiary Kraemer retained.** The 2020 Washington Technology Fast 50 profile of Data Intelligence
Technologies names its subsidiaries as **"Blur Search (big data search engine)"** and **"Cyber Data
Intelligence (CMMC consulting and training)."** Cyber DI LLC's live site (`https://www.cyberdi.us/`,
fetched 2026-07-27) sells exactly that: CMMC CCP/CCA and ISACA AI-security certification courses, as an
"ISACA Approved Training Organization." Its footer reads *"©2026 by Cyber DI LLC"* and its contact block
reads **"1530 Wilson Blvd, Suite 650, Arlington, VA 22209 · hello@cyberdi.us"** — independently linking
Cyber DI to the Response AI mailing suite. Named team on site: Brett Cox, Raj Narayan, Linda Rust, Paul
Netopski, Tiffany Laitola, Vincent Scott. **Kraemer's name appears zero times on cyberdi.us** (he is
disclosed only in SAM). Cyber DI holds **zero federal prime awards** (the single USASpending name-match is
"Cyber Diligence, Inc.", a 2014 FBI software renewal — a different company).
"Blur Search": **CHECKED, no SAM registration, no federal awards.**

**CONFIRMED (secondary/trade press) — the Data Intelligence Technologies arc:**
- Founded **2010**; Kraemer founder, later President & CEO.
- **#1 on the 2020 Washington Technology Fast 50**, 310.3% five-year CAGR, **$8.5M FY2019 revenue**,
  still a small business.
  (`https://washingtontechnology.com/articles/2020/09/24/fast-50-data-intelligence-1.aspx`)
- Kraemer, verbatim: *"We worked on an analytical platform for big data analytics and then pivoted to being
  more of a services company."*
- **Acquired by Axiologic Solutions, announced May 2022.** Kraemer was President and CEO at closing.
  DIT was represented by DLA Piper and Monument Capital Partners; Axiologic by Rees Broome, Pipaya and
  Atlantic Union Bank. **Financial terms not disclosed** — so there is no public sale price, and none
  should be asserted.
- **Integration confirmed from SAM:** DATA INTELLIGENCE TECHNOLOGIES INC (UEI KN34NSTNM2A5, CAGE 6GJ47) now
  sits at **8280 Willow Oaks Corporate Dr Ste 600, Fairfax VA** with POC **ANDY BARATTA** — the identical
  address and identical POC as AXIOLOGIC SOLUTIONS LLC (UEI L3HZTJCG4XL5, CAGE 5JLC2).

**CHANGED — #14394's capability claim is not supported.**
#14394 says DIT was "an intelligence-community **entity-analytics and link-analysis** firm — the same
capability ICE later bought from him." Every source I found describes something adjacent but different:
data engineering, analytics, data science, data visualization, data security, big data; moving data from
**RF/SIGINT, open source, cyber intelligence and geospatial** sources to analysts and warfighters; and
(per the acquisition release) 5G, SIGINT, RF, AI/ML, analytics and visualization, and software development.
**Nothing describes entity resolution, link analysis, person location, or skip tracing.**
Recommended restatement: *Kraemer built and sold a DoD/IC data-engineering and analytics services firm,
then founded a logistics and case-management company that ICE later bought person-locating services from.*
The adjacency is real and worth a sentence; the identity of capability is not evidenced.
(Separately: Response AI's live Case Management page does now market *"Identity resolution and coordinated
case records"* and an *"AI-BOSS"* address-verification engine — see §6 — so the capability claim is
supportable **about Response AI today**, just not about DIT then.)

**CONFIRMED NEGATIVE — political money.** `query_fec.py donor "KRAEMER, JAMES"` returns 20 records, **all**
of them a Cambridge MA 02139 postdoctoral fellow at MIT giving $0.10–$1.00 to ActBlue — not the subject.
`employer "Response AI Solutions"` → **0 results.** `employer "Global Emergency Response"` → **0 results.**
`employer "Data Intelligence Technologies"` → 16 records, all two rank-and-file employees (Andrew Poloni,
engineer, Purcellville VA; Laura Foster, consultant, Ashburn VA), $3–$75 each, 2018–2020 — **no principal
contributions.** This **CONFIRMS #14394's "no FEC contributions were found."**

**CONFIRMED NEGATIVE — litigation.** CourtListener party search: 0 results for all three companies.
A general search for "James Kraemer" returns 20 unrelated matches.

**NOT PURSUED / UNCONFIRMED:**
- **Security clearances** — no public statement found; not publicly discoverable. Do not speculate.
- **Prior federal contracting roles / revolving door** — none found. #14394's "no revolving-door link to
  ICE" is consistent with my results.
- **Patents** — not run (`query_patents.py` available). Given DIT was a services company with no product
  IP surfaced in any source, low expected yield. Listed in §8 as a residual.
- **Maigret** — not run. Username enumeration on a named private individual is disproportionate here and
  adds nothing to a corporate-ownership question; the FEC/court/registry negatives already cover it.

### STAN KUZIA
**CONFIRMED (SAM):** past-performance POC for Global Emergency Response Inc. Also past-performance POC for
**GLOBAL MEDICAL TECHNOLOGY PARTNERS, INC.** (UEI Y5GYTKCW2AA5, 4115 Hammonds Ferry, **Evans GA**, SAM
registered 2025-07-29). Evans GA is a suburb of **Augusta GA — GER's founding city.** That is a coherent
picture: Kuzia is the legacy GER (Augusta) principal, retained as the past-performance contact after
acquisition, with a separate Georgia venture. #14394's "founded the HC Standard business in 2004 and is a
former Smith Barney banker" was **not independently re-verified** by me and is not load-bearing.

### COLBY FARROW
**CONFIRMED (SAM):** past-performance POC for Response AI Solutions. Swept all SAM POC fields for `FARROW`
— 38 hits, none with first name Colby, none in VA/DC/MD govcon. **No other entity association found.**

### NATALIA VELA — the most useful correction in this section
**CONFIRMED (SAM):** Natalia Vela is the **electronic POC of exactly two entities in all of SAM** —
Response AI Solutions and Global Emergency Response. She is also alt-government POC of both. I swept every
POC field for `first='NATALIA' AND last='VELA'` across the full March 2026 extract: **two hits, no others.**
So she is not a serial registrant-of-record across unrelated firms.

**LIKELY, NOT CONFIRMED — she is an outsourced contract administrator, not a Response AI insider.**
A LinkedIn profile for a Natalia Vela (`linkedin.com/in/nataliav1/`) lists her as **Consultant at
GL-Solutions Inc.**, with a 15-year accounting/finance background, "responsible for the setup and
maintenance of Government contracts throughout their lifecycle."

Why this is more than a name coincidence — **GL-Solutions Inc. sits at the exact suite**:
- SAM UEI **J2CLFENPWL52**, GL SOLUTIONS INC., physical **and** mailing **1530 WILSON BLVD STE 650,
  ARLINGTON VA**, VA corporation, entity start 2009-10-09, primary NAICS **541611** (administrative and
  general management consulting), president/POC **Gregory Llinas**, CAGE 6R2F3.
- Publicly described as providing "accounting assistance, financial management and human resources support
  to **federal contractors**."
- Two affiliated entities share the suite and the Llinas POC: **GLIST LLC** (UEI HJ25MTRYMS97, a 2020 JV of
  GL Solutions and Summit Technologies) and **SUMMIT GL JV LLC** (UEI ETKQYCSLGK89).

**The honest reading, and I think the important one:** the shared electronic POC across Response AI and GER
is most likely **outsourced back-office contract administration bought from a firm in the same
virtual-office suite** — not concealment, not a nominee, not a broker network. Any wave narrative that
treats "same POC on two entities" as evidence of a shell structure should not use this pair as an example.
**Needs one confirmation step** (see §8) before publishing her name in any role: the LinkedIn identification
is a single tertiary source and I did not fetch the profile itself.

---

## 5. TASK 4 — the two open items

### 4(a) "Woman-owned" — RESOLVED. An award-level source exists. Do not drop the claim; restate it.

**The current SAM registration does not carry it — CONFIRMED.** March 2026 extract, Response AI
`business_types = 27~2X`. Decoded against `datasets/sam/SAM_Master_Extract_Layout.xlsx`
("STRING Clarification" sheet): **`27` = Self Certified Small Disadvantaged Business**, **`2X` = For Profit
Organization**. None of the women-owned codes (`8W`, `8E`, `8C`, `8D`) and neither SBA certification code
(`A9` SBA Certified WOSB, `A0` SBA Certified EDWOSB) is present. `sba_business_types` is empty.

**But FPDS award records do carry it — CONFIRMED, and this is the award-level source SYNTHESIS §5 asked
for.** FPDS-NG ATOM, `VENDOR_UEI:"ZE2JVFS8ML75"`, 10 entries, retrieved 2026-07-27:

| PIID | Mod | Signed | `isWomenOwned` | `isWomenOwnedSmallBusiness` | `isSmallBusiness` | `isSelfCertifiedSmallDisadvantagedBusiness` |
|---|---|---|---|---|---|---|
| 47QTCA25D007Q | PO0001 | 2025-04-02 | **true** | **true** | true | true |
| 47QTCA25D007Q | PSA897 | 2025-05-03 | **true** | **true** | true | true |
| 47QTCA25D007Q | PS0005 | 2025-05-28 | **true** | **true** | true | true |
| 140D0425F1000 | 0 | 2025-09-24 | false | false | false | true |
| 47QTCA25D007Q | PSA907 | 2025-12-14 | false | false | false | true |
| **70CDCR26D00000008** (ICE skip tracing IDIQ) | 0 | 2025-12-16 | false | false | false | true |
| W9124J26FA004 | P00002 | 2025-12-02 | **true** | **true** | true | true |
| 140D0425F1000 | P00002 | 2026-01-28 | false | false | false | true |
| 47QTCA25D007Q | PSA915 | 2026-04-19 | false | false | false | true |
| 47QTCA25D007Q | PSA917 | 2026-06-30 | false | false | false | true |

**And the subsidiary shows the same pattern.** GER's three Seaport-NxG records (`N0017825D7393` mod 0
2024-12-31, P00002 2025-03-06, P00003 2025-04-23) all carry `isWomenOwned = true`; its FEMA and ATF records
carry false.

**Method caution I want on the record.** `isSmallBusiness` moves in lockstep with the two women-owned flags
(true on exactly the same four rows). Response AI is unambiguously a small business — the DOI order was a
`SMALL BUSINESS SET ASIDE - TOTAL`. So `isSmallBusiness=false` on six rows is almost certainly **field
non-population**, which means the six "false" rows are probably **silent, not negative.** Read that way, the
four "true" rows are the ones where the socio-economic block was actually populated from SAM, and the
company **was** self-certified WOSB at least between 2024-12-31 and 2025-12-02, while its March 2026 SAM
profile is not.

**Recommended position for #4617/#4650 (replacing "WITHDRAWN"):**
> Response AI Solutions and its subsidiary Global Emergency Response are recorded in FPDS as
> women-owned small businesses on seven contract actions signed between 2024-12-31 and 2025-12-02
> (Response AI: GSA MAS 47QTCA25D007Q PO0001/PSA897/PS0005 and Army W9124J26FA004 P00002; GER: Seaport-NxG
> N0017825D7393 mod 0/P00002/P00003). The company's March 2026 SAM registration carries only Self Certified
> Small Disadvantaged Business (`27`) and For Profit Organization (`2X`), with no women-owned code and no
> SBA certification. **Neither ICE instrument — the skip-tracing IDIQ nor the UAC IDIQ — is flagged
> women-owned.** Whether the certification lapsed or the later FPDS records simply were not populated cannot
> be determined from FPDS alone.

**Open question this raises, which I am flagging rather than answering:** the sole disclosed principal of
both firms is James Kraemer, President. A WOSB self-certification requires majority ownership by one or more
women. **That is exactly the question the Virginia SCC filing or the deed grantee names would settle,** and
both are blocked (§8). I am not naming a presumed owner.

### 4(b) Delaney Hall — reframed by the procurement codes, and one new control failure

**CONFIRMED — it is an equipment RENTAL, not a construction job.**
FPDS-NG record for `70CDCR26P00000013`, retrieved 2026-07-27:

| Field | Value |
|---|---|
| Description | `EMERGENCY FENCING AND LIGHTING AT DELANEY HALL DETENTION FACILITY, NEWARK NEW JERSEY.` |
| **PSC** | **W099 — LEASE OR RENTAL OF EQUIPMENT: MISCELLANEOUS** |
| **NAICS** | **532490 — Other Commercial and Industrial Machinery and Equipment Rental and Leasing** |
| Contract action type | B (PURCHASE ORDER) · pricing J (FIRM FIXED PRICE) |
| Extent competed | **C — NOT COMPETED** |
| Solicitation procedures | **SSS — ONLY ONE SOURCE** |
| Reason not competed | **URG — URGENCY (FAR 6.302-2)** |
| Offers received | **1** |
| Set-aside | NONE |
| Signed / period | 2026-05-30 · 2026-05-30 → 2026-06-30 (ultimate 2026-12-31) |
| Obligated | $250,275.48 · base-and-all-options $573,375.48 |
| Contracting office | 70CDCR (ICE) · office name **DETENTION COMPLIANCE AND REMOVALS** |
| Funding requesting office | **70CRMD** |
| Place of performance | Newark NJ 07105-0002, Essex County |

**This answers the premise of the question.** The task assumed a fencing *installation* contract, which
would need a fencing contractor. The instrument ICE actually wrote is a **firm-fixed-price rental of
equipment** — temporary fence panels and light towers — from a logistics broker. That is squarely inside
Response AI's declared line of business (primary NAICS 541614, logistics consulting; its vendor-intake page
solicits "Temporary Structures", "Construction Equipment, Material Handling Services & Supplies" and
"Security / Force Protection Services & Equipment"). **No fencing contractor is structurally required as a
subcontractor for a rental.**

**CONFIRMED — zero subawards, on this and everything else.**
`query_usaspending.py subawards "RESPONSE AI SOLUTIONS"` → **0 results, 0 total.** The award record itself
carries `subaward_count: 0`, `total_subaward_amount: null`. Note the reporting rule honestly: FFATA/FSRS
requires reporting first-tier **subcontracts** ≥$30,000. A rental or purchase of equipment from a supplier
is generally **not** a reportable subcontract. So zero subawards here is **consistent with the rental
coding and is not by itself evidence of concealment.**

**UNCONFIRMED — who physically supplied or installed it.** I could not identify the equipment supplier.
- Subaward data: zero (above).
- FPDS: prime-only, no supplier field.
- Public reporting: **CHECKED, NOTHING.** No outlet has reported emergency fencing or lighting at Delaney
  Hall. Coverage in the window is about the New Jersey AG / City of Newark litigation over inspector access
  and permits, not about perimeter work.
- Newark municipal permit records: **NOT REACHED.** Newark does not expose a queryable public permit API I
  could find; this needs a manual search of Newark's construction-permit portal or an OPRA request.

**NEW — the same single-person create/approve failure appears on this PO.**
FPDS workflow fields for `70CDCR26P00000013`:
```
createdBy       JBOUDREAUX7012   createdDate       2026-06-05 20:11:44
lastModifiedBy  JBOUDREAUX7012   lastModifiedDate  2026-06-08 10:37:43
approvedBy      JBOUDREAUX7012   approvedDate      2026-06-08 10:37:43
```
One person created, modified and approved a **non-competed, urgency-justified, sole-source** purchase order.
This is the same official (Jason Boudreaux, the named 26-SOL-DCR01 procurement officer) whose March
skip-tracing extensions were **properly** split JBOUDREAUX7012 → SWRAY7012. So the pattern is not
person-specific; it recurs across officials and across instrument types.

**And a second instance, in the UAC program.** I checked all four Response AI ICE instruments:

| PIID | Signed | Obligated | createdBy | lastModifiedBy | approvedBy | Split? |
|---|---|---:|---|---|---|---|
| 70CDCR26D00000041 (UAC IDIQ) | 2026-06-02 | $0.00 | RROBINSON7012 | ISOMPPI7012 | ISOMPPI7012 | **yes** |
| **70CDCR26FR0000092** (UAC first TO) | **2026-06-17** | **$3,670,800.00** | **ISOMPPI7012** | **ISOMPPI7012** | **ISOMPPI7012** | **NO** |
| 70CDCR26P00000013 (Delaney Hall) | 2026-05-30 | $250,275.48 | JBOUDREAUX7012 | JBOUDREAUX7012 | JBOUDREAUX7012 | **NO** |
| 70CDCR26P00000016 (detainee meals) | 2026-06-29 | $99,000.00 | VLEONOVA7012 | TROSS7012 | TROSS7012 | **yes** |

**ISOMPPI7012 approved the parent IDIQ on 2026-06-02, then created and self-approved the $3.67M task order
under it on 2026-06-17.** Two of four Response AI ICE instruments show the failure.
*Handoff note: this is opus-O's sweep territory — these four rows are offered as input, not as a competing
count. Note also the UAC task order's FPDS `signedDate` is **2026-06-17**, one day earlier than the
2026-06-18 start date shown in USASpending; use 2026-06-17 for the signature.*

---

## 6. TASK 5 — website forensics: exact dates, exact language

All captures below are Wayback Machine, UTC timestamps. Live pages fetched **2026-07-27**.
Raw HTML retained in `/tmp/osint-FRmkNLeM/work-N/` (`cv-*.html`, `news-*.html`, `live-*.html`, `post-*.html`).

### 6.1 The Contract Vehicles page — the ICE detention IDIQ's demotion and removal

**#14393 is CONFIRMED. Here are the pinned dates and verbatim text.**

**A. 2025-08-13 16:25:39 UTC** — `web.archive.org/web/20250813162539/https://www.responseai.us/contract-vehicles`
Four vehicles. Nav: Home / Careers / Contract Vehicles / Contact. ICE detention listed **second of four**:
> *"2 / DHS SSV — Emergency Services Strategic Sourcing Vehicle Contract No. 70CDCR25D00000024, DHS ICE &
> DoD, $145M IDIQ providing services including facilities, medical care, transportation, legal access, &
> case management."*

(A second same-day capture, `20250813151100`, renders empty — Wix partial capture. Use 162539.)

**B. 2025-10-08 03:49:45 UTC** — `.../20251008034945/...`
Five vehicles. Nav gains Vendors and News. ICE detention **still second**, text now reads **"DHS ICE &
DoW/DoD"** (the Department of War renaming). Seaport-NxG added as #5. WEXMAC ceiling restated from
**"$1.425 Billion"** to **"$20 Billion."**

**C. 2026-01-22 23:01:29 UTC** — `.../20260122230129/...`
Six vehicles. **MDA SHIELD inserted at #2 with a "$151B" ceiling; the ICE detention IDIQ is demoted to #5**,
now prefixed "Department of Homeland Security":
> *"5 / DHS SSV — Department of Homeland Security, Emergency Services Strategic Sourcing Vehicle Contract
> No. 70CDCR25D00000024, DHS ICE & DoW/DoD, $145M IDIQ..."*

**D. LIVE, 2026-07-27** — `https://www.responseai.us/contract-vehicles`
Six vehicles: **01 WEXMAC 2.2** ($55 Billion), **02 Navy LIIS CMDS** (N6852026D1061, $249.9M), **03 MDA
SHIELD** (HQ085926DF487, $151B), **04 AI Talent 2.0** (W519TC-25-G-0048, $250M), **05 GSA MAS**
(47QTCA25D007Q), **06 Navy Seaport NxG** (N0017825D7393).
**The DHS SSV entry is gone. Not one of the six is an ICE vehicle.**

**What is now absent, stated precisely.** The live vehicles page omits all three ICE IDIQs the company
actually holds:
- `70CDCR25D00000024` — ICE emergency detention (removed from the page between 2026-01-22 and 2026-07-27)
- `70CDCR26D00000008` — ICE skip tracing (never listed in any capture)
- `70CDCR26D00000041` — ICE UAC safety verification (never listed in any capture)

The homepage "About Us" likewise names only *"WEXMAC 2.2 / TITUS, MDA SHIELD, NAVAIR LIIS CMDS, GSA MAS,
Army AI Talent 2.0 and GSA MAS"* — GSA MAS listed twice, ICE not at all.

**Also note, for figure discipline:** the site's own WEXMAC ceiling claim moved $1.425B → $20B → $55B across
these captures, and it claims a "$151B" MDA SHIELD ceiling. These are **shared multiple-award program
ceilings**, exactly like the $67.85B WEXMAC figure already corrected in #4617. None is Response AI's
capacity. Its actual WEXMAC-routed obligations are in the low millions per order.

### 6.2 The Case Management page — the UAC work, described without naming ICE

`https://www.responseai.us/casemanagement` is in `pages-sitemap.xml` (lastmod **2026-07-12**) and has
**never been captured by the Wayback Machine** — confirmed against the full domain CDX
(`matchType=domain`, 68 unique URLs; `/casemanagement` does not appear). Live text, 2026-07-27, verbatim:

> **"03/ Child Welfare and Safety Verification** — Case management and safety verification for federal
> programs serving children, including address verification, sponsor and household checks, and well-being
> follow-up across jurisdictional lines. Built for the federal initiatives requiring rigorous accountability
> and a single coordinated record for every child served."

> **"05/ AI-BOSS Decision Support and Address Verification** — AI-assisted decision support for case
> prioritization, eligibility determination, and address verification, powered by ResponseAI's AI-BOSS
> platform with **Data Bulldog** data acquisition across health, public safety, and government records."

> **"06/ Cross-Agency Coordination and Records Management** — Identity resolution and coordinated case
> records across health, social services, public safety, and benefits-delivery systems..."

Also named on the page: **MCMS ("Mission Case Management System")**, and *"01/ Lifecycle Case Management"*,
*"02/ Financial Support Services"*, *"04/ Language Interpretation and Communication Services."*

**Three things worth carrying:**
1. **CONFIRMED — #14393's core claim.** This describes the $489,158,780 ICE UAC contract
   (70CDCR26D00000041) without the words ICE, DHS, immigration, or enforcement appearing anywhere on the
   page.
2. **The vendor's marketing is broader than the contract's data-element list.** SYNTHESIS §3b established
   that the PWS field is the narrow **"(F)UAC Living with Sponsor"** and that "identify everyone living with
   the child" **overstates** it. Response AI's own page nonetheless markets **"sponsor and household
   checks."** State this as what it is: *the contractor's marketing language is broader than the PWS
   requires.* Do not use the vendor's wording to re-characterise the contract.
3. **"Data Bulldog" is a new, unexamined name** — a commercial data-acquisition source pointed at "health,
   public safety, and government records," in the same product as address verification for children. Not
   investigated here; see §8.

### 6.3 Newsroom publication forensics
Covered in §2 (the backdated GER acquisition post, the "13 minutes ago" CMMC post, the shifting byline
dates). The blog itself was created ~**2025-09-24** and seeded with three backdated releases.

### 6.4 DNS / certificates / infrastructure — thin, and I'll say so
- **crt.sh, `responseai.us`: FAILED — HTTP 502** from crt.sh, twice. Not retried further.
- **crt.sh, `cyberdi.us`:** 3 names (`cyberdi.us`, `www.cyberdi.us`, `a3.cyberdi.us`), 69 certs. Nothing.
- **crt.sh, `ger911.com`:** a large operational estate — 40+ subdomains including `hcsdodweb`,
  `dha-ncrmd`, `gerdod`, `healthchart-demo/-dev/-jomisv1`, `arcgis-dev`, `awssandbox`, `openemr`,
  `gahcs`, `exercises`. **This corroborates that GER is a genuine, long-running healthcare-software
  operation** (DoD/DHA-facing), not a shell — the opposite of the cluster's other newcomers.
- **urlscan.io `responseai.us`:** 1 public scan. Nothing of note.
- Both responseai.us and cyberdi.us are **Wix** sites (`_partials/wix-thunderbolt/`, `parastorage.com`),
  which is why Wayback captures are partial and why per-page CDX coverage is uneven.
- **No shared hosting/certificate infrastructure links the three domains** — they are on Wix (RAI, CyberDI)
  and a separate estate (GER). Infrastructure gives no independent ownership signal here.

---

## 7. NEW MATERIAL NOT IN THE BRIEF

### 7.1 HHS / Administration for Children and Families — the same firm, the other side of the child-welfare system
**CONFIRMED (USASpending award detail + FPDS + company press release).** Award **140D0425F1000**:

| Field | Value |
|---|---|
| Awarding agency | **Department of the Interior**, Departmental Offices, office **IBC ACQ SVCS DIRECTORATE (00004)** |
| **Funding agency** | **Department of Health and Human Services — Administration for Children and Families (ACF)** |
| Description | `OHSEPR SEEKS A CONTRACTOR TO STAFF, FACILITATE, AND SUPPORT ROUTINE PROGRAM ACTIVITIES TO INCLUDE END-TO-END CASE MANAGEMENT SUPPORT SERVICES, FINANCIAL SUPPORT SERVICES, AND GRANTS MANAGEMENT...` |
| Obligated | **$4,072,037.00** (outlayed $889,501.17) |
| **Base and all options** | **$21,223,448.29** |
| Signed / period | 2025-09-24 · through 2026-12-22, potential end 2030-12-22 |
| Vehicle | GSA MAS 47QTCA25D007Q · NAICS 541519 · PSC R499 |
| Competition | Full and open, **SMALL BUSINESS SET ASIDE — TOTAL**, **2 offers** |

Response AI's own release (dated Sep 25 2025, published ~Sep 24 2025): *"Under this award, **Team GER** will
provide nationwide Repatriation Case Management and Financial Support Services to U.S. citizens and their
dependents returning from overseas... intake and eligibility verification, case management, financial
assistance and reimbursement processing, housing and transportation coordination, medical and behavioral
health referrals, and transition planning."*

**Why this matters, stated carefully.** OHSEPR is the ACF office running the **Repatriation Program** for
returning **U.S. citizens** — it is *not* the Office of Refugee Resettlement and this contract is *not* UAC
work. The significance is structural, not scandalous: **Interior's franchise acquisition shop bought
HHS/ACF case management from the same small firm that ICE ERO later bought child-visit services from**, and
that contract is the *"end-to-end case management"* past performance underpinning the Case Management
product line now pointed at migrant children. It also means Response AI's Wave-1 obligation profile was
understated: DOI/HHS is its **third**-largest funder.

### 7.2 Full obligation profile (USASpending, 18 award records, retrieved 2026-07-27)

| Sub-agency | Awards | Obligated |
|---|---:|---:|
| Department of the Army | 6 | $13,911,676.54 |
| U.S. Immigration and Customs Enforcement | 6 | $9,182,531.47 |
| Departmental Offices (Interior/IBC, funded by HHS ACF) | 1 | $4,072,037.00 |
| Department of the Navy | 4 | $458,006.64 |
| Missile Defense Agency | 1 | $500.00 |
| **TOTAL** | **18** | **$27,624,751.65** |

ICE detail: `70CDCR25FR0000072` $250 (2025-05-17, detention minimum) · `70CDCR26FR0000020` $127,920
(2025-12-16, skip tracing) · `70CDCR26FR0000040` $5,034,285.99 (2026-02-09, St. Paul surge) ·
`70CDCR26P00000013` $250,275.48 (2026-05-30, Delaney Hall) · `70CDCR26FR0000092` $3,670,800 (UAC first
order) · `70CDCR26P00000016` $99,000 (2026-06-29, detainee meals).
The **$27,624,751.65** lifetime figure matches #14393 exactly — independent reproduction, no drift.

Two Army orders worth a line: **W9124J26FA004**, $8,621,946.80, *"comprehensive support services, including
housing, food, and wrap around services, to members of the Department of Defense (DoD) in response to an
urgent need for service member support **in the vicinity of Chicago, IL**"* (2025-10-15), and
**W9124J25FA077**, $1,123,693.68, *"ice storage solutions at various locations throughout the southern
border"* (2025-07-21). Both are WEXMAC-routed.

### 7.3 The identical-NAICS artifact, restated as a usable observation
GER's SAM profile advertises **NAICS 561611 (investigation and background check services), 561612 (security
guards), 561613 (armored car)** — copy-pasted from its parent. A patient-tracking software publisher does
not perform any of those. This is worth one sentence in print as an illustration of how thin SAM NAICS
self-declaration is as a capability signal — the same self-declaration mechanism that let residential-address
newcomers qualify for a 561611 skip-tracing solicitation.

---

## 8. UNCONFIRMED / BLOCKED / NEEDS — the honest ledger

### NEEDS MANUAL OPENCORPORATES
1. **Response AI Solutions LLC** — Delaware 7453000. Officers/managers, all filings, any name history,
   and specifically **whether any member is disclosed**. (The known answer is CSC as agent; worth pulling
   the filing list anyway for formation/amendment dates.)
2. **Global Emergency Response Inc** — Delaware. Formation date (SAM says entity start 2018-07-18) and
   filing history spanning the Central Research and Response AI periods.
3. **Cyber DI LLC** — **Virginia** (state of incorporation per SAM, entity start 2021-09-01). Members,
   managers, registered agent. Best single shot at a Kraemer-linked entity in a state that names managers.
4. **GL-Solutions Inc.** (VA, entity start 2009-10-09) and **GLiST LLC** (VA, 2020) — officers, to confirm
   the Gregory Llinas back-office firm and, if listed, any Vela association.
5. **Central Research Inc** (Arkansas) — to date the GER divestiture from the seller's side.
6. **Global Medical Technology Partners, Inc.** (Georgia, SAM reg 2025-07-29) — the Stan Kuzia entity.

### CAPTCHA-GATED / LOGIN-GATED — for the user, not worth fighting
1. **Virginia SCC** (`cis.scc.virginia.gov/EntitySearch/Index`) — reCAPTCHA confirmed in page source.
   Search: **Response AI Solutions LLC** (foreign LLC registration), **Global Emergency Response Inc**
   (foreign corp), **Cyber DI LLC** (domestic — most likely to name a manager), **GL-Solutions Inc.**
2. **Fairfax County CPAN** (`ccr.fairfaxcounty.gov/cpan/`) — requires a MyFairfax account, which I am not
   permitted to create. **Pull deed book 27700, page 2112** (2022-07-01, $975,000, parcel 0131 03 0060) for
   the grantee names. This is the single highest-value manual lookup in this report: it would confirm or
   refute #14394's "Kraemer James and Kraemer Elisabeth," and an Elisabeth Kraemer on title would bear
   directly on the WOSB question in §5.
3. **Fairfax County iCare** (`icare.fairfaxcounty.gov/ffxcare/`) — down for maintenance on 2026-07-27,
   verified twice. Retry for the current owner-of-record name; no login needed when it is up.

### CHECKED AND EMPTY — recorded so nobody repeats them
- CourtListener party search: Response AI Solutions **0**, Global Emergency Response **0**, Cyber DI **0**.
- FEC: no contributions by or attributable to the subject James Kraemer; no Response AI or GER employer
  contributions at all.
- `selector_pivot.py` (GLEIF / ICIJ / LittleSis / OpenSanctions, free adapters only, no `--enable-paid`):
  nothing on James Kraemer.
- Local `registry.db`: 0 entities for either company; no relevant Kraemer officer.
- SAM POC sweeps: **Natalia Vela** appears on exactly two entities (both these); **James Kraemer** on
  exactly three; **Stan Kuzia** on two; **Colby Farrow** on one.
- SAM: no entity named "Blur Search"; no federal awards for Cyber DI LLC.
- Public reporting on Delaney Hall emergency fencing/lighting: none found.
- SAM.gov live API: HTTP 429 rate-limited for the entire session (10/day cap on a personal key). All SAM
  facts above come from the March 2026 bulk extract instead — equivalent authority, one month stale.

### RESIDUAL LEADS I did not run
1. **"Data Bulldog"** — the named data-acquisition source behind Response AI's AI-BOSS address verification
   for children. Who sells it, what records it aggregates, whether it is a licensed CRA. **This is the
   highest-value unexamined thread in this report.**
2. **AI-BOSS and MCMS** — trademark/USPTO check; whether either is a real platform or a marketing name.
3. **Colby Farrow** — identity unresolved.
4. **The Kraemer↔Cyber DI↔CMMC adjacency.** Response AI announced CMMC Level 2 certification on
   2026-01-15 (post published ~2026-01-22); Kraemer's other company sells CMMC assessor training. CMMC
   Level 2 certification must be issued by an accredited C3PAO, which a training provider is not — so this
   is **an observation about adjacency, not an allegation**, and it needs the C3PAO name from the CMMC
   Enterprise Mission Assurance Support Service record before anyone writes a word about it.
5. **Pro-Sphere Tek** — GER's own blog post *"GER becomes division of Pro-Sphere Tek"* (2016-09-14,
   `ger911.com/blog/2016/09/14/ger-attend-138th-ngaus-conference/` neighbourhood) is the only source for
   that step in the chain; the Central Research acquisition press (March 2020) does not mention it.
6. **Newark construction-permit records** for Delaney Hall, May–June 2026 — the only remaining route to the
   fencing supplier. Likely an OPRA request.
7. **USPTO** — not run for Kraemer; low expected yield for a services-company founder.

---

## 9. FINDINGS THE ORCHESTRATOR SHOULD ACT ON

| Finding | Action |
|---|---|
| **#14392** | **CONFIRM as written**, upgrade the evidence: cite HigherGov/SAM `awardee_key_parent` and the FPDS address chain, not the website. Fix the provenance line: it is the homepage "About Us" section, **not** an `/about` page. Add that the Oct-2023 newsroom post is **backdated** (published after 2026-05-11) and must not be cited as contemporaneous. |
| **#14393** | **CONFIRM and pin.** Substitute the exact capture timestamps and verbatim quotes in §6.1–6.2. Add that the live page lists **six vehicles, none of them ICE**, and that all three ICE IDIQs are absent. |
| **#14394** | **CORRECT.** Keep: Kraemer, DIT founded 2010, #1 on 2020 WT Fast 50, sold to Axiologic May 2022, 843 Constellation Dr bought 2022-07-01 for $975,000 (now confirmed from Fairfax County GIS), no FEC, no revolving door. **Drop or rewrite** "entity-analytics and link-analysis firm — the same capability ICE later bought from him" — unsupported by any source. **Downgrade** the deed grantee names to unverified pending deed 27700/2112. **Add** Cyber DI LLC as a third Kraemer entity. |
| **#4617 / #4650 "woman-owned"** | **REINSTATE with the window and the caveat** (§5 recommended wording). SYNTHESIS §5's "withdrawn / needs an award-level source" is superseded — the source exists in FPDS. |
| **New entity** | **Cyber DI LLC** (UEI W4MQH3KFHYR7, CAGE 96VT2) — third Kraemer entity, zero federal awards, CMMC training. |
| **New persons** | Colby Farrow (RAI past-perf POC), Gregory Llinas (GL-Solutions), Andy Baratta (Axiologic/DIT). |
| **New agency thread** | HHS/ACF OHSEPR via Interior IBC, award 140D0425F1000, $4,072,037 obligated / $21,223,448.29 ceiling. |
| **For opus-O** | Two new separation-of-duties instances: `70CDCR26P00000013` (JBOUDREAUX7012 ×3) and `70CDCR26FR0000092` (ISOMPPI7012 ×3, $3,670,800). Clean splits on `70CDCR26D00000041` and `70CDCR26P00000016`. Also: `70CDCR26FR0000092` FPDS signedDate is **2026-06-17**, not 2026-06-18. |
| **De-escalate** | The shared Vela POC and the shared Arlington suite are **not** evidence of a shell network. Ste 650 is Office Evolution coworking with 21 SAM registrants; Vela is most likely a GL-Solutions contract administrator. Do not use this pair as a "concealed twin" exemplar in print. |
