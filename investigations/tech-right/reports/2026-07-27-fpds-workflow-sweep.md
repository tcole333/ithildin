# opus-O — FPDS workflow sweep completion + contracting-official resolution

**Agent:** opus-O (Wave 3) · **Date of pull:** 2026-07-27 · **Profile:** tech-right (threads 11/15/16)
**Scope:** all 14 skip-tracing delivery orders + 14 parent IDIQs; all 18 UAC IDIQs + 19 UAC task orders;
office-level base-rate comparison at ICE ERO contracting office **70CDCR**; identification of the FPDS users.
**Discipline:** read-only `investigation.db` (no tracker writes, no repo file changes). Throwaway scripts and
raw XML in `/tmp/osint-FRmkNLeM/work-O/`.

---

## 0. HEADLINE — the strongest claim in this investigation does not survive the base rate

**Every factual element of finding #14384 is CONFIRMED against the FPDS-NG primary record.** The "13 of 14"
count is exactly right, the exception is now identified, and the "different official" on the UAC side is now
named. All four canonical dollar figures in WAVE3.md reproduce to the cent from FPDS independently.

**But the interpretation is REFUTED.** Single-user create-and-approve is not an anomaly at this office — it is
the office's ordinary practice, driven by role. Across **1,249 contract actions at office 70CDCR in a 15-month
baseline window that contains neither program**, `createdBy == approvedBy` on **37.4%** of actions, rising to
**48.7%** in the contemporaneous period. The two target programs sit **inside** that distribution, and on two of
five measured segments they are **better** segregated than the office norm.

Decisive individual-level facts:

- **JABYAD7012 approved 22 of the 22 FPDS actions he created — 100% — including 9 of 9 on contracts unrelated
  to either program** (ICE detention/ground-transport work, Aug–Dec 2025). His conduct on the skip-tracing
  delivery orders is identical to his conduct on everything else he touches.
- **JABYAD7012 is Jimmy Abyad, and his published title is _Contracting Officer_** — i.e. the warranted role.
  A warranted CO keying and releasing his own Contract Action Report is the expected pattern, not a breach.
- **ISOMPPI7012 is Ian Somppi, ICE ERO _Section Chief_**, and he has been create-and-approving his own FPDS
  actions **continuously since December 2018** — 54 consecutive solo mods on one contract (70CDCR18C00000003)
  from 2018 to 2024, and 34 of 35 solo in the 2024–25 baseline. The UAC pattern is his 8-year habit.

- **JBOUDREAUX7012 is Jason Boudreaux, and his record settles the question outright.** Of the 57 actions he
  created, **the first 52 (2025-06-20 → 2026-03-11) were approved by someone else — zero exceptions. The last
  5 (2026-05-21 → 2026-06-30) were all self-approved — zero exceptions.** A clean break with no overlap. His
  behaviour is **date-dependent, not instrument-dependent**: the signature of an authority change (a warrant
  granted or a promotion) between 2026-03-11 and 2026-05-21, not of discretionary rigour applied to some
  contracts and withheld from others. See §4e.

**Verdict on the Task-3 question: the data supports "office-wide/role-driven FPDS data-entry practice," NOT
"these two programs were pushed through by one person."** Detail and numbers in §4.

**On denominators (per the base-rate agent's caution):** the base rates below are *real* denominators for the
question actually asked — 1,249 and 1,035 enumerated FPDS actions from the same contracting office, counted the
same way. They are not extrapolated or modelled. That is a legitimate comparison for *FPDS workflow behaviour*.
It is **not** a denominator for competitive questions (offers per solicitation, awardees per competition), and
nothing here should be carried across to those. Throughout I describe what the records show and avoid the word
"anomalous" except where a like-for-like segment comparison supports it (§4b).

What survives as genuinely reportable is narrower and should be stated as a **concentration** observation, not a
control failure: a single warranted CO was the sole FPDS releasing user on 13 of 14 base delivery orders of a
$1.44B program, twelve of them released inside one 37-minute batch five weeks after the award signature date.
That is unusual in degree (92.9% vs a 26.7% same-record-type baseline) but entirely ordinary in kind.

---

## 1. METHOD, AND WHAT THE FPDS WORKFLOW FIELDS DO AND DO NOT PROVE

**Source.** FPDS-NG public ATOM feed, `https://www.fpds.gov/ezsearch/FEEDS/ATOM?FEEDNAME=PUBLIC&templateName=1.5.3&q=…`,
queried by `PIID:"…"`, `REF_IDV_PIID:"…"`, and `CONTRACTING_OFFICE_ID:"70CDCR" SIGNED_DATE:[…]`, paging 10
entries at a time via `start=N`. Fields live at `ns1:transactionInformation/{createdBy,createdDate,lastModifiedBy,
lastModifiedDate,status,approvedBy,approvedDate}` under namespace `https://www.fpds.gov/FPDS`. Rate-limited to
~1 request/second; no throttling encountered. **CONFIRMED: this is the only public source for these fields** —
HigherGov exposes `created_by`/`approved_by` columns that return null, and USASpending has no equivalent.

**CRITICAL CAVEAT — carry this into any published text.**
`createdBy` / `approvedBy` record **who keyed the Contract Action Report into FPDS-NG and who released that data
record**. They are a *data-entry and data-release* workflow. They are **not** the FAR contracting-officer
approval chain:

- The FAR award signature lives on the SF-1449/SF-30 contract document. **FPDS-NG's 1.5.3 public schema carries
  no contracting-officer name field at all** — I checked the full element inventory of the award and IDV records.
- The FPDS record is frequently keyed **weeks or months after** the award is signed. In this program the base
  delivery orders were signed 2025-12-16/18 and keyed on **2026-01-22 — 37 days later**. The minute-level
  intervals below therefore measure **typing speed during a backlog-clearing session**, not decision speed.
- Consequently: these fields **can** show that one user account created and released a CAR. They **cannot** show
  that one person made the award decision unreviewed, that no separate official signed the contract, or that any
  FAR or DHS internal control was violated. I could not locate any public ICE/DHS policy stating whether the same
  user may create and approve a CAR — **UNCONFIRMED**, and it matters, because that policy is what would convert
  this observation into a violation.

Any published sentence should say *"one FPDS user account created and released the contract-action reports"*, not
*"one person approved the contracts."*

---

## 2. TASK 1 — COMPLETE SKIP-TRACING WORKFLOW TABLE (46 actions, all pulled)

### 2a. The 14 base delivery orders — the "13 of 14" claim is CONFIRMED, exception identified

| Delivery order | Vendor | createdBy | createdDate | lastModifiedBy | approvedBy | approvedDate | elapsed | signed | obligated |
|---|---|---|---|---|---|---|---:|---|---:|
| 70CDCR26FR0000013 | ENPROVERA CORP | **JABYAD7012** | 2026-01-16 11:03:59 | JABYAD7012 | **JABYAD7012** | 2026-01-16 11:28:47 | 24.8 m | 2025-12-16 | $34,552.00 |
| 70CDCR26FR0000021 | B.I. INCORPORATED | **JABYAD7012** | 2026-01-20 15:31:59 | JABYAD7012 | **JABYAD7012** | 2026-01-22 15:45:27 | 2,893.5 m | 2025-12-18 | $1,624,500.00 |
| 70CDCR26FR0000015 | AI SOLUTIONS 87 LLC | **JABYAD7012** | 2026-01-22 15:47:47 | JABYAD7012 | **JABYAD7012** | 2026-01-22 15:54:07 | 6.3 m | 2025-12-16 | $636,500.00 |
| 70CDCR26FR0000020 | RESPONSE AI SOLUTIONS, LLC | **JABYAD7012** | 2026-01-22 15:55:13 | JABYAD7012 | **JABYAD7012** | 2026-01-22 15:59:07 | 3.9 m | 2025-12-16 | $127,920.00 |
| 70CDCR26FR0000017 | SOS INTERNATIONAL LLC | **JABYAD7012** | 2026-01-22 15:59:50 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:02:23 | 2.5 m | 2025-12-18 | $1,642,226.25 |
| 70CDCR26FR0000019 | BLUEHAWK LLC | **JABYAD7012** | 2026-01-22 16:04:32 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:06:30 | 2.0 m | 2025-12-18 | $2,656,327.50 |
| 70CDCR26FR0000024 | CAPGEMINI GOVERNMENT SOLUTIONS | **JABYAD7012** | 2026-01-22 16:07:11 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:08:42 | 1.5 m | 2025-12-18 | $4,816,782.50 |
| 70CDCR26FR0000025 | OMNIPLEX WORLD SERVICES CORP | **JABYAD7012** | 2026-01-22 16:09:10 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:11:10 | 2.0 m | 2025-12-18 | $1,487,580.00 |
| 70CDCR26FR0000014 | FRAUD INC | **JABYAD7012** | 2026-01-22 16:11:41 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:13:22 | 1.7 m | 2025-12-16 | $348,000.00 |
| 70CDCR26FR0000016 | GRAVITAS PROFESSIONAL SERVICES | **JABYAD7012** | 2026-01-22 16:13:57 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:15:37 | 1.7 m | 2025-12-16 | $427,500.00 |
| 70CDCR26FR0000018 | GSS – GOVERNMENT SUPPORT SVCS | **JABYAD7012** | 2026-01-22 16:16:12 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:17:42 | 1.5 m | 2025-12-16 | $741,000.00 |
| 70CDCR26FR0000023 | CONSTELLATION INC | **JABYAD7012** | 2026-01-22 16:18:18 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:19:52 | 1.6 m | 2025-12-18 | $767,468.75 |
| 70CDCR26FR0000022 | NATIONAL PROTECTIVE SERVICES | **JABYAD7012** | 2026-01-22 16:20:22 | JABYAD7012 | **JABYAD7012** | 2026-01-22 16:22:01 | 1.6 m | 2025-12-18 | $909,750.00 |
| **70CDCR26FR0000032** | **GLOBAL RECOVERY GROUP, LLC** | **JBOUDREAUX7012** | 2026-01-16 14:12:10 | SWRAY7012 | **SWRAY7012** | 2026-01-21 09:33:57 | 6,921.8 m | 2026-01-16 | $2,812,500.00 |

**CONFIRMED — 13 of 14 exactly, as #14384 states.** The lone exception is **70CDCR26FR0000032, Global Recovery
Group, LLC** (parent IDIQ 70CDCR26D00000014). Its record shows the *segregated* pattern instead: created by
JBOUDREAUX7012, last-modified and approved by SWRAY7012, **4.8 days** later rather than minutes.

**Why Global Recovery differs is structural, not remedial.** Its IDIQ was approved a month after the other 13
(2026-01-16 vs 2025-12-16), its DO was signed 2026-01-16 rather than 2025-12-16/18, and it therefore never
entered Abyad's 2026-01-22 backlog batch — it was keyed contemporaneously by the normal preparer→approver pair.
This is an artifact of the award being late, not of anyone applying a stricter control to it.

**The 2026-01-22 batch, precisely:** JABYAD7012 released **12 delivery orders between 15:45:27 and 16:22:01 —
36 minutes 34 seconds — obligating $16,185,555.00**. **Eleven of the twelve were also *created* inside that same
window**, at a median create→approve interval of **1.7 minutes**; the twelfth (B.I. Incorporated, FR0000021) had
been created two days earlier. A thirteenth (Enprovera, FR0000013) was handled on 2026-01-16 and the fourteenth
is the Global Recovery exception. Read against the caveat in §1, this is a data-entry backlog session for awards
already signed five weeks earlier — the minutes measure typing, not deliberation.

### 2b. The 14 parent IDIQs — fully segregated, BETTER than the office baseline

| IDIQ | Vendor | createdBy | createdDate | lastModifiedBy | approvedBy | approvedDate | ceiling |
|---|---|---|---|---|---|---|---:|
| 70CDCR26D00000003 | ENPROVERA CORP | NNGUYEN7012 | 2025-11-26 09:18:37 | LROWAN7012 | **SWRAY7012** | 2025-12-16 13:51:24 | $2,631,300 |
| 70CDCR26D00000005 | B.I. INCORPORATED | NNGUYEN7012 | 2025-11-26 14:09:52 | JABYAD7012 | **SWRAY7012** | 2025-12-16 16:49:52 | $121,837,500 |
| 70CDCR26D00000006 | AI SOLUTIONS 87 LLC | VLEONOVA7012 | 2025-11-26 11:50:48 | JABYAD7012 | **SWRAY7012** | 2025-12-16 15:47:30 | $48,491,250 |
| 70CDCR26D00000008 | RESPONSE AI SOLUTIONS | JBOUDREAUX7012 | 2025-11-26 14:53:48 | JABYAD7012 | **SWRAY7012** | 2025-12-16 18:56:30 | $9,715,500 |
| 70CDCR26D00000012 | SOS INTERNATIONAL LLC | JBOUDREAUX7012 | 2025-12-05 19:03:58 | JABYAD7012 | **SWRAY7012** | 2025-12-16 17:13:29 | $123,166,969 |
| 70CDCR26D00000013 | BLUEHAWK LLC | JBOUDREAUX7012 | 2025-12-06 16:32:55 | JABYAD7012 | **SWRAY7012** | 2025-12-16 18:28:05 | $201,443,062 |
| 70CDCR26D00000014 | GLOBAL RECOVERY GROUP | JBOUDREAUX7012 | 2025-12-06 17:31:53 | SWRAY7012 | **SWRAY7012** | **2026-01-16** 13:32:25 | $217,265,625 |
| 70CDCR26D00000015 | CAPGEMINI GOVT SOLUTIONS | JBOUDREAUX7012 | 2025-12-06 18:40:42 | JABYAD7012 | **SWRAY7012** | 2025-12-16 22:12:21 | $365,821,219 |
| 70CDCR26D00000016 | OMNIPLEX WORLD SERVICES | JBOUDREAUX7012 | 2025-12-06 20:17:40 | JABYAD7012 | **SWRAY7012** | 2025-12-17 09:24:14 | $113,242,028 |
| 70CDCR26D00000017 | FRAUD INC | JBOUDREAUX7012 | 2025-12-06 20:57:07 | JABYAD7012 | **SWRAY7012** | 2025-12-16 15:09:23 | $25,578,000 |
| 70CDCR26D00000018 | GRAVITAS PROFESSIONAL SVCS | JBOUDREAUX7012 | 2025-12-08 15:05:30 | JABYAD7012 | **SWRAY7012** | 2025-12-16 16:28:37 | $32,062,500 |
| 70CDCR26D00000019 | GSS – GOVT SUPPORT SVCS | JBOUDREAUX7012 | 2025-12-08 15:39:26 | JABYAD7012 | **SWRAY7012** | 2025-12-16 18:18:51 | $55,575,000 |
| 70CDCR26D00000020 | CONSTELLATION INC | JBOUDREAUX7012 | 2025-12-09 11:28:29 | JABYAD7012 | **SWRAY7012** | 2025-12-16 20:29:51 | $57,848,438 |
| 70CDCR26D00000021 | NATIONAL PROTECTIVE SVCS | JBOUDREAUX7012 | 2025-12-09 11:36:34 | JABYAD7012 | **SWRAY7012** | 2025-12-16 20:09:11 | $68,231,250 |

**0 of 14 IDIQs are single-user** — every one was created by a preparer and approved by SWRAY7012, at intervals of
7 to 41 days. Against a 70CDCR baseline of 18.2% solo on base IDVs, the **skip-tracing IDIQ layer was more
tightly segregated than the office norm.** This is important and cuts directly against the "pushed through by one
person" reading: the $1.44B ceiling decisions ran through the normal chain; only the $19.0M of delivery-order
paperwork was batch-keyed by Abyad.

Note JABYAD7012 appears as `lastModifiedBy` on 10 of 14 IDIQs but as `approvedBy` on **none**.

### 2c. The 18 modifications

| PIID | mod | signed | createdBy | approvedBy | note |
|---|---|---|---|---|---|
| 12 × delivery orders (FR0000013/14/15/17/18/19/20/21/22/23/24/25) | P00001 | 2026-03-10/11 | **JBOUDREAUX7012** | **SWRAY7012** | +60-day PoP extension to 2026-05-14, $0.00 |
| 70CDCR26D00000005 | P00001 | 2026-03-24 | EPETERSON7012 | RONUMA7012 | $0.00 |
| 70CDCR26D00000008 / 17 / 19 / 20 | P00001 | 2026-03-19 | EPETERSON7012 | SWRAY7012 | $0.00 |
| **70CDCR26D00000021** (National Protective Services) | **P00001** | **2026-05-21** | **JBOUDREAUX7012** | **JBOUDREAUX7012** | **single-user — created and approved by Boudreaux, approved 2026-05-26** |

**CHANGED — a correction to SYNTHESIS §1 and claude-C §3.** Those documents say *"13 of 14 DOs extended +60d…
Gravitas alone not renewed."* **FPDS shows only 12 of 14 delivery orders carry a P00001.** Two have no
modification of any kind: **70CDCR26FR0000016 (Gravitas)** and **70CDCR26FR0000032 (Global Recovery Group)**.
Verified independently via `REF_IDV_PIID:"70CDCR26D00000014"`, which returns exactly one entry (mod 0,
currentCompletionDate 2026-04-16). Global Recovery's absence is benign — its DO was signed a month later and ran
to 2026-04-16 on its own terms, so it did not need the March extension. Gravitas remains the substantive
non-renewal. **The correct sentence is "12 of 14 delivery orders were extended; Gravitas was the only awardee
whose order lapsed without extension; Global Recovery was on a later, independent schedule."**

Also note the sole single-user *modification* in the whole skip-tracing program is **JBOUDREAUX7012 on
D00000021 (National Protective Services), 2026-05-21** — a second official doing create-and-approve, one week
after the program otherwise went dormant. This weakens any "it was only Abyad" framing further.

---

## 3. TASK 2 — COMPLETE UAC WORKFLOW TABLE (38 actions, all pulled)

**The "different official" in #14384 is ISOMPPI7012 = Ian Somppi.** He is `approvedBy` on **37 of the 38** UAC
contract actions — the entire $20.58B IDIQ family and all 18 of its task orders. The one exception is MVM's
task order on the older FY24 vehicle.

### 3a. The 18 UAC IDIQs (D00000030–D00000047), all signed 2026-06-02

| IDIQ | Vendor | createdBy | createdDate | lastModifiedBy | approvedBy | approvedDate |
|---|---|---|---|---|---|---|
| D00000030 | ALPHA RECOVERY LLC | **ISOMPPI7012** | 2026-05-28 10:32:35 | ISOMPPI7012 | **ISOMPPI7012** | 2026-06-02 06:52:22 |
| D00000031 | APPLIED INTELLECT LLC | **ISOMPPI7012** | 2026-05-28 12:16:05 | ISOMPPI7012 | **ISOMPPI7012** | 2026-06-02 06:53:45 |
| D00000032 | CADUCEUS INC. | **ISOMPPI7012** | 2026-05-28 12:51:03 | ISOMPPI7012 | **ISOMPPI7012** | 2026-06-02 06:55:37 |
| D00000033 | COMPASS UNITED | **ISOMPPI7012** | 2026-05-28 13:25:17 | ISOMPPI7012 | **ISOMPPI7012** | 2026-06-02 07:08:49 |
| D00000034 | CONTINUITY GLOBAL SOLUTIONS | **ISOMPPI7012** | 2026-05-29 07:17:35 | ISOMPPI7012 | **ISOMPPI7012** | 2026-06-02 06:57:55 |
| D00000035 | CRITICAL RESPONSE STRATEGIES | **ISOMPPI7012** | 2026-05-29 08:03:18 | ISOMPPI7012 | **ISOMPPI7012** | 2026-06-02 06:59:22 |
| D00000036 | DELTA POINT LLC | JCAPPELLO7012 | 2026-06-01 11:00:19 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:00:53 |
| D00000037 | EAGLEGRACE GLOBAL LLC | JCAPPELLO7012 | 2026-05-29 10:21:34 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:03:27 |
| D00000038 | LEMOINE DISASTER RECOVERY | JCAPPELLO7012 | 2026-05-29 09:50:44 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:14:08 |
| D00000039 | NATIONAL PROTECTIVE SERVICES | RROBINSON7012 | 2026-05-28 13:40:50 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:48:10 |
| D00000040 | ORIGIN INVESTIGATIONS INC | RROBINSON7012 | 2026-05-28 14:18:13 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:17:00 |
| D00000041 | RESPONSE AI SOLUTIONS, LLC | RROBINSON7012 | 2026-05-29 09:20:39 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:20:13 |
| D00000042 | SECURITY INSIGHTS LLC | RROBINSON7012 | 2026-05-29 09:56:33 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:22:11 |
| D00000043 | SEPTIMO SOLUTIONS, LLC | JCAPPELLO7012 | 2026-05-28 21:00:32 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:26:15 |
| D00000044 | SEVERANCE SECURITY SERVICES | JCAPPELLO7012 | 2026-05-28 20:30:23 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:28:44 |
| D00000045 | SAVVY PROFESSOR LLC | JCAPPELLO7012 | 2026-05-28 19:53:13 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:31:41 |
| D00000046 | SOS INTERNATIONAL LLC | JCAPPELLO7012 | 2026-05-28 12:41:16 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:34:31 |
| D00000047 | THE BAPTISTE GROUP, LLC | JCAPPELLO7012 | 2026-05-28 13:22:03 | ISOMPPI7012 | ISOMPPI7012 | 2026-06-02 07:36:57 |

Plus one modification: **D00000032 (Caduceus) P00001, signed 2026-07-24, created AND approved by JCAPPELLO7012,
2.6 minutes apart** — three days before this pull. The UAC program is actively being administered right now.

**Timestamp clustering — CONFIRMED and it is tighter than the skip-tracing side.** All **18 IDIQ approvals fell
inside 55 minutes 48 seconds on the morning of 2026-06-02, 06:52:22 → 07:48:10** — one release every 3.1 minutes,
starting before 7 a.m. **A combined ceiling of $20,583,928,204.05 was released to FPDS by one user account in
under an hour.**

### 3b. The 19 UAC task orders

| Task order | Vendor | signed | createdBy | createdDate | approvedBy | approvedDate | obligated |
|---|---|---|---|---|---|---|---:|
| 70CDCR26FR0000081 | ALPHA RECOVERY LLC | 2026-06-16 | **ISOMPPI7012** | 2026-06-10 09:02:07 | **ISOMPPI7012** | 2026-06-16 07:37:26 | $1,055,544.00 |
| 70CDCR26FR0000084 | COMPASS UNITED | 2026-06-16 | **ISOMPPI7012** | 2026-06-10 10:00:51 | **ISOMPPI7012** | 2026-06-16 07:38:38 | $8,916,301.74 |
| 70CDCR26FR0000085 | CONTINUITY GLOBAL SOLUTIONS | 2026-06-16 | **ISOMPPI7012** | 2026-06-11 07:05:06 | **ISOMPPI7012** | 2026-06-16 07:39:45 | $6,270,128.00 |
| 70CDCR26FR0000087 | DELTA POINT LLC | 2026-06-16 | **ISOMPPI7012** | 2026-06-11 10:15:26 | **ISOMPPI7012** | 2026-06-16 07:40:57 | $3,910,774.24 |
| 70CDCR26FR0000088 | EAGLEGRACE GLOBAL LLC | 2026-06-16 | **ISOMPPI7012** | 2026-06-11 13:33:34 | **ISOMPPI7012** | 2026-06-16 07:43:19 | $5,236,600.00 |
| 70CDCR26FR0000090 | NATIONAL PROTECTIVE SERVICES | 2026-06-16 | JCAPPELLO7012 | 2026-06-10 13:40:25 | ISOMPPI7012 | 2026-06-16 07:44:47 | $1,166,500.00 |
| 70CDCR26FR0000095 | SEVERANCE SECURITY SERVICES | 2026-06-16 | JCAPPELLO7012 | 2026-06-15 10:13:02 | ISOMPPI7012 | 2026-06-16 07:46:57 | $4,770,000.00 |
| 70CDCR26FR0000098 | THE BAPTISTE GROUP, LLC | 2026-06-16 | JCAPPELLO7012 | 2026-06-15 12:08:31 | ISOMPPI7012 | 2026-06-16 07:49:06 | $2,073,250.00 |
| 70CDCR26FR0000082 | APPLIED INTELLECT LLC | 2026-06-17 | **ISOMPPI7012** | 2026-06-10 11:59:35 | **ISOMPPI7012** | 2026-06-17 07:42:54 | $3,080,158.00 |
| 70CDCR26FR0000083 | CADUCEUS INC. | 2026-06-17 | **ISOMPPI7012** | 2026-06-10 12:58:34 | **ISOMPPI7012** | 2026-06-17 07:44:38 | $11,965,000.00 |
| 70CDCR26FR0000086 | CRITICAL RESPONSE STRATEGIES | 2026-06-17 | **ISOMPPI7012** | 2026-06-11 09:32:55 | **ISOMPPI7012** | 2026-06-17 07:45:03 | $1,614,000.00 |
| 70CDCR26FR0000089 | LEMOINE DISASTER RECOVERY | 2026-06-17 | **ISOMPPI7012** | 2026-06-12 10:17:42 | **ISOMPPI7012** | 2026-06-17 07:46:14 | $7,690,000.00 |
| 70CDCR26FR0000091 | ORIGIN INVESTIGATIONS INC | 2026-06-17 | **ISOMPPI7012** | 2026-06-15 07:39:58 | **ISOMPPI7012** | 2026-06-17 07:48:20 | $1,812,000.00 |
| 70CDCR26FR0000092 | RESPONSE AI SOLUTIONS, LLC | 2026-06-17 | **ISOMPPI7012** | 2026-06-15 07:59:21 | **ISOMPPI7012** | 2026-06-17 07:49:26 | $3,670,800.00 |
| 70CDCR26FR0000093 | SECURITY INSIGHTS LLC | 2026-06-17 | **ISOMPPI7012** | 2026-06-15 09:15:10 | **ISOMPPI7012** | 2026-06-17 07:49:51 | $5,507,232.00 |
| 70CDCR26FR0000094 | SEPTIMO SOLUTIONS, LLC | 2026-06-17 | JCAPPELLO7012 | 2026-06-15 10:06:39 | ISOMPPI7012 | 2026-06-17 07:50:17 | $8,686,250.00 |
| 70CDCR26FR0000096 | SAVVY PROFESSOR LLC | 2026-06-17 | JCAPPELLO7012 | 2026-06-15 12:59:34 | ISOMPPI7012 | 2026-06-17 07:50:42 | $4,727,750.00 |
| 70CDCR26FR0000097 | SOS INTERNATIONAL LLC | 2026-06-17 | JCAPPELLO7012 | 2026-06-15 13:47:30 | ISOMPPI7012 | 2026-06-17 07:51:58 | $3,224,029.16 |
| **70CDCR26FR0000052** | **MVM, INC.** | 2026-03-20 | JCAPPELLO7012 | 2026-03-19 10:22:07 | **ASTOUGHT7012** | 2026-03-20 08:29:01 | $1,446,000.00 |

**Approval clustering — CONFIRMED, and it is the tightest in either program.**
- 2026-06-16: **8 task orders released in 11 minutes 40 seconds** (07:37:26 → 07:49:06), 1.7 min apart.
- 2026-06-17: **10 task orders released in 9 minutes 4 seconds** (07:42:54 → 07:51:58), **1.0 min apart**.
- **$85,376,317.14 across 18 task orders released to FPDS in ~21 minutes of combined wall-clock, across two
  mornings, all before 8 a.m., by one user account.**

### 3c. How the UAC pattern differs from skip tracing

| Measure | Skip tracing | UAC |
|---|---|---|
| Single approver for the whole family | No — SWRAY7012 on IDIQs, JABYAD7012 on DOs | **Yes — ISOMPPI7012 on 37 of 38 actions** |
| Base IDIQs single-user | 0 / 14 (0.0%) | 6 / 18 (33.3%) |
| Base DOs/TOs single-user | 13 / 14 (92.9%) | 12 / 19 (63.2%) |
| Whole program single-user | 14 / 46 (30.4%) | **19 / 38 (50.0%)** |
| Approval window | 11 DOs in 36.6 min | **18 IDIQs in 55.8 min; 18 TOs in 20.8 min** |
| Entry lag behind signature | 37 days | **5–7 days (contemporaneous)** |

**This is not the same shape.** On skip tracing, one official batch-keyed the delivery orders long after the fact
while the ceiling decisions ran through a normal chain. On UAC, one official — the **Section Chief** — is the
release point for the entire $20.58B family at both the IDIQ and task-order layers, and did so contemporaneously.
The UAC concentration is *broader* (both layers, 50% of all actions) but *less* deviant from that individual's
lifetime baseline (§4c).

---

## 4. TASK 3 — BASE RATE: IS THIS OFFICE-WIDE OR PROGRAM-SPECIFIC?

**It is office-wide and role-driven. Stated plainly: the data does NOT support "these two programs were pushed
through by one person."**

### 4a. Office-level base rates, 70CDCR, `createdBy == approvedBy`

Samples pulled by `CONTRACTING_OFFICE_ID:"70CDCR" SIGNED_DATE:[…]`, deduplicated on (PIID, mod, createdDate),
with the two target programs excluded from every "base rate" row.

| Window | n (non-program) | single-user | rate |
|---|---:|---:|---:|
| 2023-12-01 → 2024-01-31 | 133 | 34 | **25.6%** |
| **2024-01-01 → 2025-03-31 (15-month baseline)** | **1,249** | **467** | **37.4%** |
| 2024-12-01 → 2025-01-31 | 182 | 80 | **44.0%** |
| 2025-06-01 → 2025-06-30 | 59 | 13 | **22.0%** |
| **Apr 2025 → Jun 2026, short-ID era, all non-program** | **1,035** | **504** | **48.7%** |
| 2025-12-01 → 2026-01-31 *(skip-tracing award window)* | 149 | 79 | **53.0%** |
| 2026-06-01 → 2026-06-30 *(UAC award window)* | 69 | 43 | **62.3%** |
| — *(the two target programs, same 2 windows)* | 64 | 31 | *48.4%* |

In both award windows, **the target programs were LOWER than the surrounding office base rate** (46.4% vs 53.0%
in Dec–Jan; 50.0% vs 62.3% in June). Contract actions unrelated to skip tracing or UAC were single-user *more*
often than the ones under investigation.

### 4b. Segmented by record type — the only place the programs stand out

Comparing like with like, because mods and base awards behave differently:

| Record type | 70CDCR baseline (2024-01→2025-03) | Skip tracing | UAC |
|---|---:|---:|---:|
| Base delivery/task order | 20/75 = **26.7%** | **13/14 = 92.9%** | **12/19 = 63.2%** |
| Base IDV/IDIQ | 2/11 = **18.2%** | **0/14 = 0.0%** | 6/18 = **33.3%** |
| Modification | 434/1,120 = **38.8%** | **1/18 = 5.6%** | 1/1 |

**One cell is genuinely elevated: skip-tracing base delivery orders at 92.9% against a 26.7% baseline.** Two
cells are *better* than baseline (skip-tracing IDIQs 0.0% vs 18.2%; skip-tracing mods 5.6% vs 38.8%). The UAC
task orders at 63.2% are elevated but within the range the office shows contemporaneously (50–62%).

### 4c. The explanation: role, not program — the individual data is decisive

The office's users are sharply **bimodal**, exactly as you would expect from warranted contracting officers
versus unwarranted contract specialists. Baseline window (2024-01 → 2025-03), per creator:

| ~Always solo (warranted profile) | | ~Never solo (preparer profile) | |
|---|---:|---|---:|
| GENNA.BRADEN@ICE.DHS.GOV | 86/86 = 100% | ERIC.PETERSON@ICE.DHS.GOV | 0/81 = 0% |
| PAUL.PREVICH@DHS.GOV | 30/30 = 100% | SHEREEN.DEMARAIS@ICE.DHS.GOV | 0/69 = 0% |
| COREY.SOILEAU@ICE.DHS.GOV | 25/25 = 100% | ANTHONY.ELMORE@ICE.DHS.GOV | 0/67 = 0% |
| DIANA.BROZI@ICE.DHS.GOV | 18/18 = 100% | BRIANA.JONES@ICE.DHS.GOV | 0/57 = 0% |
| MARLAND.CLARK@ICE.DHS.GOV | 65/67 = 97.0% | VALERIE.LEONOVA@ICE.DHS.GOV | 0/55 = 0% |
| **IAN.SOMPPI@ICE.DHS.GOV** | **34/35 = 97.1%** | DONNELL.SAM@ICE.DHS.GOV | 0/54 = 0% |
| NATASHA.NGUYEN@DHS.GOV | 57/62 = 91.9% | ANDREW.HADDEN@ICE.DHS.GOV | 0/46 = 0% |
| BRITTANY.TOBIAS@ICE.DHS.GOV | 21/22 = 95.5% | MUSA.KAMARA@DHS.GOV | 0/43 = 0% |

And for the six people at the centre of this investigation, measured on work **outside both programs**:

| FPDS user | Actions created | Actions approved | Solo rate on NON-PROGRAM work |
|---|---:|---:|---|
| **JABYAD7012** (Jimmy Abyad) | 22 | 30 | **9 / 9 = 100.0%** |
| **ISOMPPI7012** (Ian Somppi) | 36 | 69 | **16 / 18 = 88.9%** (and 34/35 = 97.1% in 2024–25) |
| **JCAPPELLO7012** (John Cappello) | 48 | 38 | 21 / 32 = 65.6% |
| **SWRAY7012** (Shayla Wray) | 1 | 67 | pure approver — created only 1 action in the entire sample |
| **JBOUDREAUX7012** (Jason Boudreaux) | 54 | 5 | **2 / 29 = 6.9%** — pure preparer |
| **RROBINSON7012** | 5 | 0 | 0 / 1 — pure preparer |

**Jimmy Abyad create-and-approves 100% of everything he touches, program or not.** His nine non-program actions
(Aug–Dec 2025: GEO Transport, G4S Secure Solutions, Spectrum Security, Asset Protection & Security, Starside
Security, Colt Services, Low Kountry Ink) are all solo. The skip-tracing delivery orders are not a deviation
from his practice; they *are* his practice.

**Ian Somppi has done this since 2018.** On PIID **70CDCR18C00000003** he created and approved **54 consecutive
modifications, P00008 through P00061, from 2018-12-14 to 2024-11-01**, then continued as ISOMPPI7012 on P00062
(2025-12-30). Same on 70CDCR23D00000006 (mods 0, P00001, P00002 as email-format; P00003 as short-format). The
UAC releases in June 2026 are the 8-year continuation of an unbroken personal pattern.

### 4e. The Boudreaux longitudinal test — the cleanest evidence in this report

The orchestrator relayed from fable-N that JBOUDREAUX7012 both splits duties (the March skip-tracing extensions)
and self-approves (the Delaney Hall PO 70CDCR26P00000013), and asked whether that reads as instrument-dependent
discretion or an office-wide control weakness. **I pulled every action he ever created. It is neither — it is a
role change, and the break is absolute.**

| Period | Actions created | Self-approved | Approvers used |
|---|---:|---:|---|
| 2025-06-20 → 2026-03-11 | **52** | **0** | DBROZI7012, SWRAY7012, NNGUYEN7012, JABYAD7012 |
| 2026-05-21 → 2026-06-30 | **5** | **5** | himself |

His five self-approved actions are **70CDCR26D00000021 P00001** (2026-05-21, National Protective Services),
**70CDCR24FR0000046 P00010** (2026-05-25, G4S), **70CDCR26P00000013** (2026-06-05, Response AI, Delaney Hall
fencing, $250,275.48), **70CDCR26FR0000040 P00001** (2026-06-16, Response AI, St. Paul surge) and
**70CDCR26FR0000030 P00003** (2026-06-30, CoreCivic) — five consecutive, spanning four unrelated vendors and
four different contract types. Everything he touched before 2026-03-11 went to another approver, including the
entire skip-tracing IDIQ set and all 12 delivery-order extensions.

**There is no instrument-dependent pattern.** The Delaney Hall PO is not an exception carved out for a
sole-source urgency buy; it simply falls after the break, like everything else after the break. The same
transition is visible elsewhere in the office — SHEREEN.DEMARAIS ran 0/69 solo in the 2024–25 baseline and
40/59 = 67.8% afterwards. **This is the strongest single confirmation of the role-based explanation in the
report:** the variable that predicts self-approval is the person's authority at that date, not the contract.

Boudreaux's updated figures with the adjacent instruments folded in: **4 of 32 non-program actions = 12.5%**
(was 2/29 before these pulls), **5 of 57 overall = 8.8%** — still far below the 37.4%/48.7% office base rate,
because 91% of his career at this office predates his break.

### 4f. Adjacent Response AI instruments (from fable-N, independently re-pulled and confirmed)

| PIID | Vendor | createdBy | createdDate | lastModifiedBy | approvedBy | approvedDate | obligated |
|---|---|---|---|---|---|---|---:|
| 70CDCR26P00000013 (Delaney Hall fencing) | RESPONSE AI SOLUTIONS | **JBOUDREAUX7012** | 2026-06-05 20:11:44 | JBOUDREAUX7012 | **JBOUDREAUX7012** | 2026-06-08 10:37:43 | $250,275.48 |
| 70CDCR26P00000016 (detainee meals) | RESPONSE AI SOLUTIONS | VLEONOVA7012 | 2026-06-29 10:08:12 | TROSS7012 | **TROSS7012** | 2026-06-29 14:37:18 | $99,000.00 |

Both **CONFIRMED** against FPDS-NG, values identical to fable-N's. Note 70CDCR26P00000013's signed date is
**2026-05-30**, six days before the FPDS record was keyed. New user observed: **TROSS7012** (unresolved; not in
the email-era roster).

fable-N's other two points are already in my tables and **agree exactly**: 70CDCR26FR0000092 (Response AI UAC
first task order) is ISOMPPI7012 solo, and its parent IDIQ 70CDCR26D00000041 was created by RROBINSON7012 and
approved by ISOMPPI7012 two weeks earlier. **Signed-date correction accepted and already applied** — my §3b
table carries FR0000092 as signed **2026-06-17**, matching FPDS `signedDate`, not the 2026-06-18 start date
USASpending shows.

**Method cross-check:** re-ran 70CDCR26FR0000092 through the new repo tool
`uv run python tools/query_fpds.py piid 70CDCR26FR0000092`. Its output — createdBy/createdDate/lastModifiedBy/
approvedBy/approvedDate/signed_date — is **identical to my hand-rolled parser's**, so every table in this report
is reproducible with the repo tool. Confirming the orchestrator's warning: the workflow keys are camelCase
(`createdBy`, `lastModifiedBy`, `approvedBy`) while the rest are snake_case.

### 4g. Verdict

**"ICE has permissive FPDS data-entry practice office-wide" is the story the data supports.** 37.4% of 1,249
baseline actions and 48.7% of 1,035 contemporaneous non-program actions are single-user. The pattern predates
both programs by years, is concentrated in specific individuals regardless of what they are buying, and tracks
warranted-versus-unwarranted role rather than program.

**The residual, defensible observation** — worth one paragraph, not a headline:
> Within that permissive environment, the concentration on these two programs is still notable in degree. One
> contracting officer keyed and released 13 of 14 base delivery orders of a $1.44B program, twelve of them inside
> a single 37-minute session; one section chief was the release point for an entire $20.58B IDIQ family and all 18 of its first task
> orders, releasing 18 billion-dollar-ceiling awards in 56 minutes before 7 a.m. Neither is a violation on this
> evidence. Both mean that if a reviewer wanted a second set of eyes on the FPDS record of these awards, there
> wasn't one.

**#14384's characterisation as a "separation-of-duties failure" and SYNTHESIS §6.3's "a documented internal-control
failure, proven from FPDS, not inferred" are not supportable and should be withdrawn.** They were derived from a
3-of-14 sample with no base rate. This is precisely the error the base rate was there to catch.

---

## 5. TASK 4 — RESOLVING THE OFFICIALS

### 5a. The method that worked (reusable, and worth recording)

FPDS-NG changed its workflow user-ID format in **March 2025**: records keyed before then carry the official's
**full government email address**; records keyed after carry a short `FLASTNAME` + office-code ID. Measured:
2025-02 = 40/40 email format, 2025-03 = 17 email / 23 short, 2025-04 = 3 / 37, 2025-05 = 0 / 40.

Because the stamp is applied at *data-entry* time, long-running contracts carry **both formats for the same
person on the same PIID**, straddling the change. That is a direct primary-record identity proof. The cleanest
single example — **70CDCR20D00000006 mod P00019 was created by `DIANA.BROZI@ICE.DHS.GOV` (2025-02-18) and
approved by `DBROZI7012` (2025-04-15): one contract action, one person, both formats.**

### 5b. Identifications

| FPDS user | Name | Title | Confidence | Evidence |
|---|---|---|---|---|
| **JABYAD7012** | **Jimmy Abyad** | **Contracting Officer**, ICE ERO | **CONFIRMED** | Named `primary_contact` on ICE ERO solicitation **70CDCR24R00000007** ("Western Ground Transportation Solicitation (RFP)"), `jimmy.abyad@ice.dhs.gov`, title "Contracting Officer" (HigherGov opportunity record, SAM-derived). That is the solicitation behind IDIQs 70CDCR25D00000001–005, on which **JABYAD7012 created and approved the mods in Sept 2025** — same office, same contract family, matching ID construction. |
| **ISOMPPI7012** | **Ian Somppi** | **Section Chief**, ICE ERO | **CONFIRMED** | Straddle on **3 PIIDs**: 70CDCR18C00000003 (P00061 `IAN.SOMPPI@ICE.DHS.GOV` → P00062 `ISOMPPI7012`), 70CDCR23D00000006 (P00002 → P00003), 70CDCR24D00000002 (mod 0 approved by email format, P00002 by short). **Independently:** named `primary_contact` on the UAC solicitation **70CDCR26R00000015**, `ian.somppi@ice.dhs.gov`, title **"Section Chief"**, agency ICE ERO. |
| **JCAPPELLO7012** | **John Cappello** | **Procurement Officer**, ICE ERO | **CONFIRMED** | Straddle on 70CDCR24D00000002 (P00001 `JOHN.CAPPELLO@ICE.DHS.GOV` → P00002 `JCAPPELLO7012`), plus 70CDCR20C00000001, 70CDCR20P00000057, 70CDCR21P00000033. **Independently:** named `secondary_contact` on UAC solicitation 70CDCR26R00000015, `john.cappello@ice.dhs.gov`, title "Procurement Officer". |
| **JBOUDREAUX7012** | **Jason Boudreaux** | **Procurement Officer**, ICE ERO | **CONFIRMED** | Named `primary_contact` on skip-tracing solicitation **26-SOL-DCR-01**, `jason.boudreaux@ice.dhs.gov`, title "Procurement Officer" (HigherGov/SAM; corroborated by the SAM.gov opportunity page). Belief in SYNTHESIS confirmed. No email-era straddle exists — his first FPDS appearance at 70CDCR is **2025-06-20**. |
| **SWRAY7012** | **Shayla B. Wray** | **Procurement Officer**, ICE ERO | **CONFIRMED** | Straddle on **70CDCR20D00000011**: P00042/P00043 created by Peterson/Leonova and approved by `SHAYLA.B.WRAY@ICE.DHS.GOV` (Jan–Feb 2025); P00044–P00046 created by `VLEONOVA7012` and approved by `SWRAY7012` (Mar–Jul 2025) — identical creator↔approver pairing across the format flip. **Independently:** named `secondary_contact` on 70CDCR24R00000007, `shayla.b.wray@ice.dhs.gov`, title "Procurement Officer". |
| **RROBINSON7012** | — | — | **UNCONFIRMED** | See 5c. |
| EPETERSON7012 | Eric Peterson | Contract Specialist (inferred from 0%-solo profile) | CONFIRMED (name) | Straddle on 70CDCR20D00000006, 70CDCR20D00000007, 70CDCR20FR0000070, 70CDCR25FR0000002. |
| NNGUYEN7012 | Natasha Nguyen | **Contract Specialist**, ICE ERO | CONFIRMED | Straddle on 70CDCR20D00000006/08/09; named on 70CDCR24R00000007, `natasha.t.nguyen@ice.dhs.gov`, title "Contract Specialist". |
| RONUMA7012 | Roberta O. Onuma | — | CONFIRMED (name) | Straddle on 70CDCR25FR0000004 (P00002 email → P00004 short, same approver role), 70CDCR20D00000007, 70CDCR24FR0000007. |
| VLEONOVA7012 | Valerie Leonova | — | CONFIRMED (name) | Straddle on 70CDCR25FR0000004 (P00003 → P00004), 70CDCR20D00000011, 70CDCR23FC0000016. |
| ASTOUGHT7012 | Amanda Stought | — | CONFIRMED (name) | Straddle on 70CDCR24FR0000034, 70CDCR25FR0000005, 70CDCR25FR0000029. |
| SWEST7012 | Sarah A. West | **Section Chief**, ICE ERO | CONFIRMED | Named on 70CDCR24R00000007, `sarah.a.west@ice.dhs.gov`, title "Section Chief". |
| AELMORE7012 | Anthony Elmore | — | CONFIRMED (name) | Straddle on 70CDCR21D00000004, 70CDCR21P00000049, 70CDCR23C00000001. |
| DBROZI7012 | Diana Brozi | — | CONFIRMED (name) | Intra-action straddle, 70CDCR20D00000006 P00019. |
| PPREVICH7012 | Paul Previch | — | HIGH (no straddle) | `PAUL.PREVICH@DHS.GOV` is the only "PREVICH" among 44 distinct email-era users at this office; ID construction rule verified on 10 others. No same-PIID straddle found in sample. |
| NZDANUK7012 / EKIRKSEY7012 / GBRADEN7012 / MCLARK7012 / CSOILEAU7012 / BTOBIAS7012 / EEZEALA7012 / TWANG7012 / NCARR7012 / SDEMARAIS7012 / LGARLAND7012 / MKAMARA7012 / SABUBAKER7012 / AHADDEN7012 / BJONES7012 | Nicholas Zdanuk / Edward Kirksey / Genna Braden / Marland Clark / Corey Soileau / Brittany Tobias / Ejikeme Ezeala / Tasha R. Wang / Natalie Carr / Shereen Demarais / Lisa Garland / Musa Kamara / Sayed Abubaker / Andrew Hadden / Briana Jones | — | HIGH (roster + rule) | All appear in the email era at 70CDCR with matching surnames and identical roles; several have straddles. Listed for completeness; none is load-bearing. |

### 5c. UNCONFIRMED — say so plainly

- **RROBINSON7012 — NOT IDENTIFIED.** What I tried: (1) the 1,249-action email-era 70CDCR corpus (2024-01 →
  2025-03) contains **no "ROBINSON"** among its 44 distinct users; (2) no same-PIID straddle exists; (3) the user
  has only **5 actions in the entire FPDS record I sampled** — four UAC IDIQs (D00000039/40/41/42) and one mod on
  70CDCR22P00000016 — and **their first-ever appearance is on the UAC award itself, 2026-05-28 13:40:50**, so
  there is no prior contract whose solicitation POC could name them; (4) web/LinkedIn searches returned nothing.
  **Do not guess a first name.** Resolvable later if ICE ERO publishes a solicitation naming them as POC.
  *(Worth noting on its own terms: a user whose FPDS debut is a $415M–$1.98B UAC IDIQ award.)*
- **TROSS7012 — NOT IDENTIFIED.** Surfaced on 70CDCR26P00000016 (Response AI detainee meals, 2026-06-29) as
  lastModifiedBy/approvedBy. No "ROSS" appears among the 44 distinct email-era users at 70CDCR, so no straddle
  is available. Not load-bearing for any claim here.
- **Whether ICE/DHS policy permits the same user to create and approve an FPDS CAR — UNCONFIRMED.** Searched
  ICE OAQ pages, DHS OIG contracting reports, and the FPDS-NG user manual; found no public statement. This is
  the missing piece that would decide whether any of this is a policy breach. Good FOIA target.
- **GAO protest B-424186 (Ballard Green, five protests against 26-SOL-DCR-01) — NOT RETRIEVED.** Search surfaced
  only a docket reference to **B-424186.4, dismissed 2026-01-29**; no decision text, and GAO decisions name
  agency counsel rather than the contracting officer, so this route was unlikely to add a name. Low priority.
- **JABYAD7012's and JBOUDREAUX7012's arrival dates** are bounded, not exact: their earliest appearance anywhere
  in my 70CDCR sample is **JBOUDREAUX7012 2025-06-20** (70CDCR24FR0000050 P00002) and **JABYAD7012 2025-07-24**
  (70CDCR25FR0000004 P00007, as approver of a GEO Group mod). Neither appears in the 15-month email-era corpus.
  **Inference, clearly labelled:** both are likely new to this contracting office in mid-2025, roughly four to
  five months before the skip-tracing solicitation issued. Not proof of a transfer date — FPDS records activity,
  not employment.

### 5d. Ethics note

All five confirmed individuals are named here from **public federal procurement records, in their official
capacity**: SAM.gov solicitation points of contact and the FPDS-NG public feed. No personal information beyond
name, government title, government email, and official actions is recorded. No individual was contacted.

---

## 6. CORRECTIONS REQUIRED

| Finding / doc | Current text | Required correction |
|---|---|---|
| **#14384** (confidence `confirmed`) | Characterises the JABYAD7012 pattern as a separation-of-duties failure covering 13 of 14 skip-tracing base DOs, repeating in UAC under a different official | **The factual core is CONFIRMED and should be retained** — 13/14 exact, exception = 70CDCR26FR0000032 (Global Recovery Group), UAC official = ISOMPPI7012 / Ian Somppi. **The characterisation must be corrected.** Single-user create-and-approve runs at **37.4%** across 1,249 non-program actions at this office (48.7% contemporaneously); both programs are *below* the surrounding base rate; Abyad is 100% solo on non-program work; Somppi has done this since 2018. Re-state as a **concentration** observation with the FPDS-is-data-entry caveat. Confidence for any "control failure" language should drop to **`medium` at most, claim type `inference`**. |
| **#4620** | Separation-of-duties concern | Same correction. What is confirmed is *who keyed and released which CARs*; the control-failure inference is not supported by the base rate. |
| **SYNTHESIS §2** | "the most serious allegation is now PROVEN… one person creating *and* approving delivery orders" | Retain the table (all values verified correct) and add the exception row + base rate. Remove "PROVEN"/"most serious allegation". Note that the *IDIQ* layer was **more** segregated than the office norm (0% vs 18.2%). |
| **SYNTHESIS §6 item 3** | "A documented internal-control failure, proven from FPDS, not inferred" | **Withdraw.** Replace with the concentration paragraph in §4g. |
| **SYNTHESIS §1 / claude-C §3 / WAVE3.md canonical numbers** | "13 of 14 DOs extended +60d… Gravitas alone not renewed" | **CHANGED — 12 of 14.** Both 70CDCR26FR0000016 (Gravitas) *and* 70CDCR26FR0000032 (Global Recovery) have no modification. Global Recovery's is benign (signed 2026-01-16, ran to 2026-04-16 independently); **Gravitas remains the only substantive non-renewal.** |
| **SYNTHESIS §2** | "the single-person pattern is specific to the January base awards, not the later mods" | **Refine.** True for the 12 P00001 delivery-order mods, but **70CDCR26D00000021 P00001 (National Protective Services, signed 2026-05-21) was created AND approved by JBOUDREAUX7012** — a later single-user mod by a second official. |
| **Any "one rogue official" or "same official splits on one instrument and self-approves on another" framing** | Suggested by the Delaney Hall PO sitting beside the properly-split March extensions | **REFUTED by the longitudinal record (§4e).** Boudreaux split 52/52 through 2026-03-11 and self-approved 5/5 from 2026-05-21 — a clean date break across four unrelated vendors and four contract types. The predictor is his authority at the date, not the instrument. |

---

## 7. INDEPENDENT CORROBORATION OF THE CANONICAL NUMBERS (unplanned, but useful)

Summed directly from FPDS-NG, entirely independently of HigherGov and USASpending:

| Figure | WAVE3.md canonical | FPDS-NG (this pull) | Match |
|---|---:|---:|---|
| Skip-tracing combined IDIQ ceiling (14) | $1,442,909,640 | **$1,442,909,640.02** | ✓ |
| Skip-tracing obligated (14 DOs) | $19,032,607 | **$19,032,607.00** | ✓ exact |
| UAC combined IDIQ ceiling (18) | ~$20,583,928,204 | **$20,583,928,204.05** | ✓ |
| UAC obligated (19 TOs incl. MVM) | $86,822,317 | **$86,822,317.14** | ✓ |

All four canonical figures are now confirmed against a **third** independent primary source. Also confirmed from
the FPDS records themselves: skip tracing `numberOfOffersReceived = 51`; UAC IDIQs stamp `18`.

---

## 8. THINGS I CHECKED THAT PRODUCED NOTHING

- **HigherGov `opportunity --agency-key 904` bulk enumeration** (to sweep every ICE ERO solicitation POC and
  resolve RROBINSON7012): returns 0 records with `--since`, and **ReadTimeout** at page sizes 100, 50, and 25.
  Targeted `--source-id` lookups work fine. Worth a repo-side note.
- **`query_sam.py`** not exercised — basic tier is 10 requests/day and the HigherGov POC route answered the same
  question for free.
- **Web/LinkedIn searches for "Abyad" + ICE** returned nothing; the identification came entirely from the
  HigherGov/SAM solicitation POC record for 70CDCR24R00000007. Generic search was a dead end for all six users —
  **every confirmed identification in §5b came from primary procurement records, not from search.**
- **No CO-name field exists in FPDS-NG 1.5.3.** I inventoried every element in the award and IDV schemas. Anyone
  looking for the FAR signatory in FPDS will not find it there.

---

## 9. NEEDS MANUAL OPENCORPORATES

None — this assignment was entirely FPDS/SAM procurement-record work and required no corporate registry lookups.

---

## APPENDIX — reproduction

Working directory `/tmp/osint-FRmkNLeM/work-O/` (throwaway; no repo files written):
- `fpds.py` — ATOM fetcher/parser (`piids <file>` and `q '<query>' <max_pages>` modes)
- `skip_dos.json` (26 actions), `skip_idiqs.json` (20), `uac_idiqs.json` (19), `uac_tos.json` (19)
- `email_era_2024.json` (1,249 baseline actions), `post_2025.json` (762), `base_70CDCR_*.json` (5 windows)
- `st_*.json`, `straddle_*.json` — identity-straddle evidence records
- `hg_{ian.somppi,john.cappello,jason.boudreaux}.json`, `opp_{70CDCR26R00000015,26-SOL-DCR-01,70CDCR24R00000007}.json`
- `raw/` — raw FPDS ATOM XML for every per-PIID query

Query forms that work: `PIID:"…"`, `REF_IDV_PIID:"…"`, `CONTRACTING_OFFICE_ID:"70CDCR" SIGNED_DATE:[YYYY/MM/DD,YYYY/MM/DD]`,
`CONTRACTING_AGENCY_ID:"7012"`. Paging via `&start=N`, 10 entries per page; stop when a page returns <10 entries.
