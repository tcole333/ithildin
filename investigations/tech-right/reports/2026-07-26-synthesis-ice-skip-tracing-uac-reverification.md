# SYNTHESIS — ICE skip-tracing small-contractor cluster, re-verification wave
**Date:** 2026-07-26 · **Profile:** tech-right (threads 11/15/16)
**Wave:** 3 Opus 5 agents + 1 Codex gpt-5.6-sol agent, orchestrator-supervised, + user-supplied OpenCorporates records
**Inputs:** `claude-C-report.md` (contract re-pull + FPDS), `codex-D-report.md` (local SAM/registry), `opus-A-report.md` (WI cluster reporting), `opus-B-report.md` (program + newcomers), orchestrator spot-verification, Travis's manual OpenCorporates pulls.

---

## 0. HEADLINE

Three things came out of this wave:

1. **The original findings were mostly right on facts, wrong on some arithmetic and framing.** Every per-firm
   ceiling in #4647 matched the live record to the dollar. The errors were a ceiling swap, an unreproducible
   obligations figure, two mis-worded entity claims, and one product conflation.
2. **The most serious allegation is now PROVEN.** The JABYAD7012 separation-of-duties claim — one person creating
   *and* approving delivery orders — is confirmed against the FPDS-NG primary record.
3. **The program metastasized.** ICE stood up a **new 16-firm IDIQ family worth ~$19.44 BILLION** — roughly
   **13× the skip-tracing program** — to perform "safety verification and wellness checks" on unaccompanied
   migrant children, reusing the same residential-address newcomers. This was invisible to the original scan.

---

## 1. THE SKIP-TRACING PROGRAM, NOW FULLY PINNED

Structural key (new): the awards sit under HigherGov **vehicle 8760 "DHS ICE Skip Tracing Services."** Each awardee
holds one IDIQ (`70CDCR26D00000###`) and exactly one delivery order (`70CDCR26FR00000##`).

**14 IDIQs confirmed** (the "12+" in #4621 was an undercount — the earlier scan caught the program mid-award).
**Combined ceiling $1,442,909,640.** **Current obligated: $19,032,607 = 1.32%.**

| # | Awardee | UEI | IDIQ | Ceiling | Obligated | DO perf. loc |
|---|---|---|---|---:|---:|---|
| 1 | Capgemini Government Solutions | DR6MQ56MGFA5 | D00000015 | $365,821,219 | $4,816,782 | McLean VA |
| 2 | Global Recovery Group | PDG7UND3CWN8 | D00000014 | $217,265,625 | $2,812,500 | Washington DC |
| 3 | Bluehawk LLC | LJ93K5X4BJN7 | D00000013 | $201,443,062 | $2,656,328 | Washington DC |
| 4 | SOS International (SOSi) | L3VCKMD7J585 | D00000012 | $123,166,969 | $1,642,226 | Washington DC |
| 5 | B.I. Incorporated (GEO) | PKK6L9KLMYR5 | D00000005 | $121,837,500 | $1,624,500 | **Boulder CO** |
| 6 | Omniplex World Services | K87GBMDQNEX8 | D00000016 | **$113,242,028** | $1,487,580 | Herndon VA |
| 7 | National Protective Services | W4AUG3SNRTL6 | D00000021 | $68,231,250 | $909,750 | San Antonio TX |
| 8 | Constellation Inc | F93GMYJCTJR8 | D00000020 | $57,848,438 | $767,469 | McLean VA |
| 9 | GSS – Government Support Svcs | EMNSGMGP3CP8 | D00000019 | $55,575,000 | $741,000 | Milton FL |
| 10 | AI Solutions 87 LLC | RXFLA65SEJL9 | D00000006 | $48,491,250 | $636,500 | **Boulder CO** |
| 11 | Gravitas Professional Services | EJB9AHGV8BD1 | D00000018 | **$32,062,500** | $427,500 | Kings Mills OH |
| 12 | Fraud Inc | D13LLJJZYH64 | D00000017 | $25,578,000 | $348,000 | Washington DC |
| 13 | Response AI Solutions | ZE2JVFS8ML75 | D00000008 | $9,715,500 | $127,920 | McLean VA |
| 14 | Enprovera Corp | XWMMKN745MS5 | D00000003 | $2,631,300 | $34,552 | Tampa FL |

**Modification wave (new):** 13 of 14 delivery orders received a **P00001 modification ~2026-03-11 obligating $0.00
and extending performance +60 days** to 2026-05-14. **Gravitas Professional Services was the lone exception** — its
DO lapsed 2026-03-15. That non-renewal is worth a look.

---

## 2. ~~CONFIRMED: the separation-of-duties failure~~ — SUPERSEDED 2026-07-27 (#4620)

> **THE INTERPRETATION IN THIS SECTION DOES NOT SURVIVE. Read this box before citing anything below.**
>
> The FPDS records are accurate and unchanged. What fails is the inference that they show an
> irregularity specific to these programs.
>
> **Single-user create-and-approve is the ordinary practice at ICE contracting office 70CDCR.**
> Across **1,249** FPDS actions at that office in a 15-month baseline window containing neither
> program, `createdBy == approvedBy` on **37.4%** of actions, rising to **48.7%** of 1,035
> contemporaneous non-program actions. An independent orchestrator pull of **400** further actions
> signed 2024-06-01 → 2024-12-31 — entirely before either program existed — returns **42.5%**.
> **Both target programs sit inside that distribution, and in their award windows were BELOW the
> surrounding office rate.**
>
> Supporting detail: Jimmy Abyad approved **22 of 22** actions he created, including 9 unrelated to
> either program. Ian Somppi has shown the pattern since 2018. And the contrast this section drew —
> "the March extensions were properly split" — is explained by an **authority change, not by
> instrument type**: Jason Boudreaux split duties on **52 of 52** actions through 2026-03-11 and
> self-approved **5 of 5** from 2026-05-21, cleanly across four vendors and four contract types.
>
> **Do not publish this as a "documented internal-control failure, proven from FPDS."** Restate as:
> data-entry and approval are concentrated in single users at this office, which is its norm.
> Note also that FPDS workflow fields record the **data-entry** workflow, which is not the FAR
> contracting-officer approval chain. Findings #4620 (now `medium`) and #14384 carry the correction.
>
> The complete sweep did confirm the underlying counts exactly (13 of 14 base delivery orders), and
> named five officials from primary records. See `2026-07-27-fpds-workflow-sweep.md`.

## 2. (superseded) CONFIRMED: the separation-of-duties failure (#4620)

Neither USASpending nor HigherGov exposes FPDS workflow fields (HigherGov has `created_by`/`approved_by` columns but
they return null — orchestrator verified this directly). The **FPDS-NG ATOM feed at fpds.gov does** expose them:

| Delivery order | Vendor | createdBy | lastModifiedBy | approvedBy | Timestamp |
|---|---|---|---|---|---|
| 70CDCR26FR0000014 | Fraud Inc | **JABYAD7012** | **JABYAD7012** | **JABYAD7012** | 2026-01-22 16:11–16:13 |
| 70CDCR26FR0000015 | AI Solutions 87 | **JABYAD7012** | **JABYAD7012** | **JABYAD7012** | 2026-01-22 15:47–15:54 |
| 70CDCR26FR0000018 | GSS | **JABYAD7012** | **JABYAD7012** | **JABYAD7012** | 2026-01-22 16:16–16:17 |

One FPDS user created, modified, and approved all three base delivery orders within minutes on the same day.
**Contrast:** the March extensions used properly segregated duties — created by **JBOUDREAUX7012** (Jason Boudreaux,
the named procurement officer for 26-SOL-DCR01), approved by **SWRAY7012**. So the single-person pattern is specific
to the January base awards. Only 3 of 14 were checked; the pattern is likely uniform and should be swept.

---

## 3. THE BIG NEW DEVELOPMENT: the UAC "safety verification" program

> **CORRECTED 2026-07-26 — the figures in this section were wrong. Orchestrator-verified corrections:**
> - **18 IDIQs, not 16.** Add **70CDCR26D00000046 = SOS INTERNATIONAL (SOSi)**, ceiling $559,578,059.16, and
>   **70CDCR26D00000047 = THE BAPTISTE GROUP** (UEI GEGMCJMMZ634), ceiling $580,475,000. Corrected combined
>   ceiling ≈ **$20.58B**. The previously "UNCONFIRMED" ">$20B / 18 companies" claim is therefore **CONFIRMED**.
>   **SOSi — the pre-solicitation letter-contract firm — is in BOTH programs.**
> - **"$0 obligated" was WRONG and is withdrawn.** That was an artifact of reading obligations at the parent-IDV
>   level; obligations live on the child task orders. **19 task orders totalling $86,822,317** are already out —
>   18 signed 2026-06-16/18 (70CDCR26FR0000081–0098) plus **MVM Inc 70CDCR26FR0000052, $1,446,000, signed
>   2026-03-20 under a pre-existing FY24 vehicle (70CDCR24D00000002)**. Verified samples: Caduceus $11,965,000;
>   Compass United $8,916,301.74; Septimo $8,686,250; Lemoine $7,690,000; Security Insights $5,507,232;
>   Savvy Professor $4,727,750; Response AI $3,670,800; Alpha Recovery $1,055,544.
> - **METHOD LESSON (important):** for IDIQ families, obligations must be summed from **child task orders**,
>   never read off the parent IDV. The skip-tracing 1.32% figure and the UAC "$0" came from the same class of
>   query; only one was checked properly.
> - **18 offers received AND 18 awards — every offeror won**, `extent_competed=A`, `type_set_aside=NONE`.
>   Contrast: skip tracing was 51 offers → 14 awards. Note these are two different facts that happen to share
>   the number 18; state them separately.
> - **Savvy Professor's widely-cited "~$200M first order" (Project Saltbox) matches neither** the obligation
>   ($4,727,750) nor the task-order ceiling ($737,001,500). Treat that secondary figure as suspect.


ICE ERO stood up a **new IDIQ family, D00000030–D00000045 — 16 awards, all performance starting 2026-06-01,
combined ceiling ≈ $19,443,875,145, $0 obligated at time of pull** — for *"safety verification and wellness checks
for unaccompanied alien children and former unaccompanied alien children."* Solicitation **70CDCR26R00000015**
(posted 2026-04-09), **same NAICS 561611** (investigation/background checks) as skip tracing, PSC R799. The
solicitation cites 479,000+ UAC released FY2021–FY2024; tasks are to confirm location via databases, make a site
visit, observe for abuse/neglect/trafficking, and notify an ERO point of contact. Advocates and (per The Guardian)
an internal ICE document describe it as a locate-and-deport pretext.

| IDIQ | Awardee | Location | Ceiling |
|---|---|---|---:|
| D00000043 | Septimo Solutions LLC | Severna Park MD | $3,105,250,000 |
| D00000042 | Security Insights LLC | Rancho Viejo TX | $1,982,235,852 |
| D00000038 | Lemoine Disaster Recovery LLC | Lafayette LA | $1,734,450,000 |
| D00000032 | Caduceus Inc. | Marietta GA | $1,623,930,000 |
| D00000045 | **Savvy Professor LLC** | Spotsylvania VA | $1,596,251,500 |
| D00000033 | Compass United | — | $1,567,890,829 |
| D00000036 | Delta Point LLC | — | $1,510,186,884 |
| D00000037 | EagleGrace Global LLC | — | $1,080,860,000 |
| D00000031 | Applied Intellect LLC | — | $1,040,372,408 |
| D00000034 | Continuity Global Solutions LLC | — | $1,015,420,918 |
| D00000044 | Severance Security Services LLC | — | $779,000,000 |
| D00000035 | Critical Response Strategies LLC | — | $650,378,000 |
| D00000040 | Origin Investigations Inc | Los Angeles CA | $536,620,000 |
| D00000041 | **Response AI Solutions LLC** | Great Falls/McLean VA | $489,158,780 |
| D00000039 | **National Protective Services LLC** | San Antonio TX | $415,134,000 |
| D00000030 | Alpha Recovery LLC | — | $316,735,974 |
| | **TOTAL (16)** | | **$19,443,875,145** |

**Two skip-tracing newcomers carried straight over:** Response AI Solutions (residential Great Falls VA) at $489M
and National Protective Services (first federal contract was Dec 2025) at $415M. Both have already taken a first
task order "TO MEET THE IDIQ MINIMUM REQUIREMENT OF 1000 CASES" — Response AI 70CDCR26FR0000092 ($3,670,800),
NPS 70CDCR26FR0000090 ($1,166,500). Orchestrator independently confirmed Response AI's IDIQ: potential total
value **$489,158,780**, signed 2026-06-02, 18 offers received, Full and Open Competition, ordering period to
2027-05-31, description verbatim as quoted above.

**Caution flags:** "18" in that record is the **number of offers received**, not 18 awardees. A search-sourced claim
of ">$20B / 18 companies" remains unconfirmed. And these ceilings are maximums, not obligations — $0 obligated so
far across the family. Verify the actual SOW before characterizing what the visits are.

---

## 3b. WHAT THE UAC SOW ACTUALLY REQUIRES — ORCHESTRATOR-VERIFIED VERBATIM

Two agents conflicted on this; the orchestrator resolved it directly against the primary text
(`work-L/sol-A0005_Attachment 01-Performance Work Statement Clean.pdf.txt`, current version).
**Do not re-litigate this from agent summaries — this is the checked list.**

The PWS data-element list, quoted verbatim:
> • (F)UAC First and Last Name • **A#** • Address, City, State, Zip • Located (Y/N) • Safety (Y/N) •
> School Enrollment (Y/N) • Contact Information (phone, email) • **Sponsor First and Last Name,
> Relationship, Contact Information, Address if different from (F)UAC** • **(F)UAC Living with Sponsor** •
> **(F)UAC Working**

Resolution of the conflict:
- **"A#" IS collected.** An agent reported "A-number appears zero times" — true as a string, but the document
  uses **`A#`**. That was a **search-term artifact, not an absence.** The alien registration number is collected.
- **"photograph" and "biometric" genuinely appear ZERO times in all three PWS versions** — correctly refuted for
  the UAC program. Time-stamped photographs belong to the **skip-tracing** PWS; do not attribute them to the
  child-visit program.
- **"household" is NOT the requirement.** The actual field is the narrower **"(F)UAC Living with Sponsor"**.
  Describing this as "identify everyone living with the child" **overstates it** — do not publish that.
- **"(F)UAC Working" is collected** — employment status of the child/young adult. Newly noted; significant in an
  enforcement context and not previously flagged.
- School enrollment and attendance, sponsor identity/relationship/contact/address: all **confirmed**.

Other verified operational requirements: site visits "no later than 7pm local time"; multiple visits if needed;
notification to ICE "within 48 hours of receipt"; ICE Portal updates "within 24 hours"; address must be confirmed
as **"a residence, not a commercial location or PO box"**; if the subject has moved, the vendor must identify and
confirm the new address from databases and records. Contractor staff must currently reside in the US/Territories
and have resided there 3+ of the last 5 years (a background-investigation coverage rule — this is **not** a
professional qualification, so it does not contradict the finding that ICE set no minimum field-staff quals).

### The security-requirements gap (verified by the exposure agent, worth carrying)
Section I carries a real regime — **HSAR 3052.204-72 Alt I**: ATO required, independent NIST SP 800-53 assessment,
FIPS 140-2/3 for CUI email, **1-hour PII incident reporting**, 180-day packet capture, NIST 800-88 sanitization.
But the **PWS contains zero technical security requirements** (encrypt/CUI/PII/FedRAMP/SSP/ATO all = 0) and the
**QASP measures none of it**. The regime attaches only to systems "operated on behalf of the agency," so a
four-person firm holding this data on its own laptops arguably never triggers it. **The structural gap, not a
missing clause, is the story.**

## 4. THE WISCONSIN SHELL CLUSTER IS NOW REGISTRY-CONFIRMED (refutes a baseline negative)

Findings #4658/#4659 recorded that **"Gregory Behm is NOT listed as officer or registered agent in WI DFI for any
entity,"** and Codex D could not resolve agent data from the local snapshot. **Travis's OpenCorporates pulls refute
that outright.** Behm is the registered agent for all three Wisconsin entities, all at the same house:

| Entity | WI No. | Organized | Status | Agent | Agent address |
|---|---|---|---|---|---|
| AI Solutions 87 LLC | A114809 | 2025-01-08 | Organized | **Gregory Behm** | 4067 Sleeping Dragon Rd, West Bend WI |
| DC Gravity LLC | D082686 | 2025-05-27 | Organized | **Gregory P Behm** | 4067 Sleeping Dragon Rd, West Bend WI |
| SDNexus DataOps LLC | S161072 | 2025-05-28 | Organized | **Gregory P Behm** | 4067 Sleeping Dragon Rd, West Bend WI |

This upgrades the shell cluster from "reportedly shares the address" to **one person, one house, three LLCs, two of
them batch-filed on consecutive days** — a documented fact rather than an inference. Behm is the sole listed
director/officer on all three.

### Other registry results from Travis's pulls
- **GSS – Government Support Services LLC** (FL L25000325793, 2025-07-15, Active): agent **Jeffrey I Hodrick**,
  manager **Gwendolyn I Hodrick** (confirms Codex D). **NEW:** head-office and mailing address is
  **1992 Lewis Turner Blvd, Ft Walton Beach FL 32547** — a *different* address from the Milton house used in SAM.
- **Fraud Inc** (TX 0804377209, 2022-01-06, In Existence): registered address is the **Houston commercial suite**
  (17350 State Hwy 249 Ste 220 #33447), not the Conroe apartment used in SAM. **Two officers we did not have:
  Allan Clary (VP/director) and Pretra Loomer (secretary/director)**, alongside Richard Leslie (president) and
  Kelley Leslie (treasurer). **Change of Registered Agent filed 2026-01-17.**
- **Response AI Solutions LLC** (DE 7453000, 2023-05-10): agent is **Corporation Service Company** — a commercial
  agent, so Delaware yields no ownership. Ownership must come from another route (see plan).
- **Cyber Intel Service LLC — five entities, and the shape is telling:**
  | Jurisdiction | Number | Dates | Address |
  |---|---|---|---|
  | Wyoming (inactive) | 2022-001173308 | 2022-10-18 → 2023-12-09 | 5830 E 2nd St Ste 7000 #6747, Casper WY |
  | Florida | L23000354944 | 2023-07-27 → | — |
  | New York (branch) | 7230696 | 2023-12-18 → | 87 Hale Hill Ln Ste 200, Lewis NY |
  | California (branch) | 202464213102 | 2024-10-14 → | 2412 Irwin St Ste 255, Melbourne FL |
  | **Washington (branch)** | 606253867 | **2026-07-14 →** | 2412 Irwin St Ste 255, Melbourne FL |
  Started at a **Casper, Wyoming registered-agent-mill address**, let that lapse, re-based to **Melbourne FL**
  (a defense/space-corridor town), and has been adding state branches — including one registered **twelve days ago**.

**Post-exposure behavior pattern (new):** AI Solutions 87 changed its registered agent on **2026-01-08** and Fraud
Inc changed its registered agent on **2026-01-17** — both within weeks of the December 2025 press. AI Solutions 87's
website was scrubbed to a bare 301 redirect to google.com in the same window.

---

## 5. CORRECTIONS TO STORED FINDINGS

| Finding | Problem | Correct position |
|---|---|---|
| #4648 | Says combined ceiling **$1.1B** and Omniplex **~$32.1M** | **REFUTED.** Ceiling is **$1.44B** (#4647 is right). The $32.1M is **Gravitas's** ceiling, mis-attributed to Omniplex; Omniplex is **$113.2M**. |
| #4648 | "Total obligated $27.3M (2.5%)" | **Not reproducible.** Real: **$19,032,607 (1.32%)**. The 2.5% was computed against the wrong $1.1B denominator. No de-obligations occurred. The $27.3M likely bundled the SOSi $6.95M letter contract and/or Capgemini's separate +$7.4M skip-tracing mod. |
| #4621 | "12+ IDIQs" | **14** — the scan caught the program mid-award. |
| #4619 | "Wisconsin LLC started Mar 19, 2019" | That's the SAM entity-start/Florida date. WI entity organized **2025-01-08** by **Certificate of Conversion** domesticating the 2019 FL LLC. |
| #4657 | "Registered in BOTH FL and WI" | **One company that moved**, not two registrations. |
| #4658/#4659 | "Behm is NOT listed as officer or agent in WI DFI" | **REFUTED** — Behm is registered agent on all three WI entities (§4). |
| #5041 | SDNexus = AI surveillance | sdnexus.app is a **surplus-property compliance SaaS**. The mobile-device-scanning drone belongs to **CIS Labs / Cyber Intel Service (CAGE 9JLR6)**. |
| #4617 | "Response AI holds a $67.85B WEXMAC ceiling" | Figure is **real but shared** — it's the WEXMAC 2.0 program ceiling stamped on all **88** awardee IDVs, not Response AI's capacity. Its actual WEXMAC usage is ~$19.3M across ~10 task orders. |
| #4617/#4650 | Response AI "woman-owned" | Absent from its SAM registration (only self-certified small disadvantaged). Needs an award-level source or drop. |
| #4665 | Boulder/B.I. co-location | **Place of performance = Boulder CO 80301 is a confirmed procurement fact.** Subcontracting to B.I. remains an inference. |
| #4656 | Framing | **Constellation, Gravitas, Enprovera are NOT shells** (established firms; Enprovera is an SBA 8(a) participant). The shell pattern is **AI Solutions 87 / Fraud Inc / GSS / National Protective Services**. National Protective's "former firearms-training" claim is **unconfirmed**. |
| #4613 framing | Fraud Inc as empty shell | It is a **live, licensed TX P&C insurance-fraud PI firm** (license A22991201) at a Houston commercial suite. The anomaly is the *timing* of its federal registration, not that the business is fake. |
| Multiple | Papercut-stripped `$` figures | Re-state from the verified table in §1. |

**Also confirmed against primary sources:** all 14 awardees and every named principal are **clean on the SAM
exclusions list** (zero UEI, legal-name, or full-name hits in the March 2026 snapshot). SOSi's pre-award letter
contract **70CDCR26C00000001, $6,954,758.46, signed 2025-10-21** — three weeks before the solicitation was
published and five weeks before it closed. National Protective Services registered in SAM **2025-11-19**, nine
days *after* the solicitation issued. Fraud Inc registered **2025-11-08**, two days *before* it issued. The GSS
SAM record literally contains `GOVT_BUS_POC_CITY=OUAGADOUGOU` with state FL, zip 32570.

---

## 6. WHY THIS IS A MUCH STRONGER STORY NOW

1. **The vehicle became a template, at 13× the scale.** Same ICE office, same investigation NAICS, same
   newcomer-at-a-residential-address profile — now buying home visits to migrant children under a **$19.4B**
   ceiling family.
2. **One firm bridges both programs and conceals it.** Response AI Solutions holds detention, skip tracing, surge
   logistics, Delaney Hall work, *and* a $489M child-visit IDIQ across **≥6 vehicles** — while its own website
   discloses only defense/logistics work and **no ICE/DHS work at all**. No journalism has named it as a UAC awardee.
3. ~~**A documented internal-control failure**, proven from FPDS, not inferred.~~
   **WITHDRAWN 2026-07-27 — see the box in §2.** The office base rate (37.4–48.7%, independently
   42.5% pre-program) shows single-user create-and-approve is normal practice at office 70CDCR and
   that both programs fell below it. This is not a point in favour of the story and must not be
   published as one.
4. **Confirmed procurement-timing anomalies:** SOSi paid before the competition closed; Capgemini was already
   selling ICE skip tracing under an older vehicle (+$7.4M mod, 2025-10-09) before this solicitation existed;
   Capgemini's $365.8M ceiling exceeds the Amendment-2 per-IDIQ maximum of $281.25M.
5. **Documented post-exposure cleanup** — two registered-agent changes in January 2026 and a scrubbed website.
6. **A documented oversight vacuum** — no bid protest, no SBA protest, no OIG/GAO audit, no litigation. The only
   response is one introduced bill (H.R.7161, Krishnamoorthi, 2026-01-20) plus the Salon-reported police
   deputization scheme ($100K stipends + $7,500/officer, graded by ICE; Minnesota AG found the Mille Lacs County
   agreement initially violated state law).
7. **The shell layer is still OSINT-original** — no outlet has named DC Gravity, SDNexus DataOps, Guercini, Behm,
   or the West Bend cluster. Scripps came closest ("residences as their main office addresses").

---

## 7. CONTINUATION PLAN (ranked)

**Tier 1 — the $19.4B UAC program is now the main story**
1. **Full UAC-SVI workup.** Pin the 8 unpinned UEIs (Compass United, Delta Point, EagleGrace Global, Applied
   Intellect, Continuity Global, Severance Security, Critical Response Strategies, Alpha Recovery). For each of the
   16: formation date, address type, officers, prior federal history, set-aside status. Expect more
   residential-address newcomers holding billion-dollar ceilings (Septimo $3.1B, Security Insights $2.0B, Savvy
   Professor $1.6B). Pull the actual **SOW** — the visits' scope is the story's ethical core.
2. **Response AI Solutions beneficial ownership.** Delaware is a dead end (Corporation Service Company). Route
   around it: the **Global Emergency Response Inc** twin (UEI FE98C4148NH3 — same address, same mailing suite, same
   POCs James Kraemer/Natalia Vela, *identical* NAICS and PSC strings), VA SCC filings, property records on 843
   Constellation Dr, and who Kraemer and Vela are. This is the publishable scoop.
3. **FPDS sweep of the remaining 11 base delivery orders** for the JABYAD7012 pattern, plus the same check across
   the 16 UAC IDIQs and their task orders. Resolve JABYAD7012 to a named individual.

**Tier 2 — close remaining gaps**
4. **Build a reusable FPDS-NG ATOM tool** (infra request). The agent hit fpds.gov directly; the repo has no tool,
   so this capability isn't reproducible. It's the only source for workflow/approval fields.
5. **Gravitas non-renewal** — the only one of 14 not extended. Quiet termination or de-scoping?
6. **Capgemini ceiling excess** — $365.8M vs the $281.25M per-IDIQ max in Amendment 2.
7. **Cyber Intel Service LLC (CAGE 9JLR6)** federal footprint; the Melbourne FL base; why a Casper WY shell-mill
   start; what the brand-new Washington branch (2026-07-14) is for.
8. **Wisconsin shells' purpose** — DC Gravity and SDNexus DataOps have zero federal awards and no web presence.
   With Behm confirmed as agent, the question is what they were formed *for*, in the same window as the contracting
   ramp-up.
9. **Roberto Guercini** identity/role; **Allan Clary** and **Pretra Loomer** (new Fraud Inc officers);
   the **Ft Walton Beach** GSS head office; **Habari Inc** (FL F24000000300, Hodrick-controlled, now inactive).
10. **FOIA:** the SOSi J&A for the pre-close letter contract; the UAC-SVI evaluation record; the Delaney Hall
    emergency-procurement file.

**Tier 3 — DB housekeeping**
11. Apply every correction in §5 via `findings_tracker.py correct` (never direct UPDATE); re-state papercut figures;
    add the confirmed primary figures as new findings with proper claim types and confidence ceilings.
12. Add entities: Global Emergency Response Inc, Habari Inc, Cyber Intel Service LLC, DC Gravity, SDNexus DataOps,
    Savvy Professor/SIVS, Septimo Solutions, Security Insights, plus persons Todd Thompson, James Kraemer,
    Natalia Vela, Gwendolyn Hodrick, Allan Clary, Pretra Loomer, Jason Boudreaux.
