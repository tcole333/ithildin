# STRATEGIC REVIEW — ICE skip-tracing / UAC "safety verification" case
**Reviewer:** fable-I · **Date:** 2026-07-26 · Read-only DB, no repo files modified.
**Inputs read:** `SYNTHESIS.md`, `WAVE2.md`, all four Wave-1 reports, `docs/TOOL_REFERENCE.md`,
all of `docs/modules/*.md`, `research/OSINT_RESOURCES.md`, `research/INVESTIGATIVE_METHODOLOGY.md`,
plus a live survey of the repo's own prior work.

**Discipline note.** Everything marked **[V]** I ran and saw output for during this review; source and
exact value given. **[U]** = proposal I did not test. **[T]** = tested that the *tool/endpoint* works but
did not complete the substantive query. I have flagged four places where I believe the current case state
is **wrong**, in §0. Ceilings are labelled as ceilings throughout.

---

## 0. FOUR THINGS I THINK WE HAVE WRONG RIGHT NOW

These are ahead of the recommendations because they affect what the wave is about to publish.

### 0.1 The UAC program is NOT "$0 obligated." $86.8M in task orders is already out. **[V]**

`WAVE2.md` instructs agents to describe the UAC family as "**$0 obligated**… capacity, not money," and
the reframe is built on that. The $0 is an **artifact of reading obligations at the IDV level**. The
obligations live on the child task orders. USASpending transaction/award search on keyword
`"safety verification"` (assistance-excluded, contracts A/B/C/D, 2026):

**19 task orders, $86,822,317.14 total.** 18 of them signed **2026-06-18**; the 19th is MVM's
**70CDCR26FR0000052, $1,446,000, 2026-03-20**, under a *pre-existing FY24 vehicle* `70CDCR24D00000002`.

| Task order | Awardee | Amount |
|---|---|---:|
| 70CDCR26FR0000083 | Caduceus Inc. | $11,965,000 |
| 70CDCR26FR0000084 | Compass United | $8,916,301.74 |
| 70CDCR26FR0000094 | Septimo Solutions | $8,686,250 |
| 70CDCR26FR0000089 | Lemoine Disaster Recovery | $7,690,000 |
| 70CDCR26FR0000085 | Continuity Global Solutions | $6,270,128 |
| 70CDCR26FR0000093 | Security Insights | $5,507,232 |
| 70CDCR26FR0000088 | EagleGrace Global | $5,236,600 |
| 70CDCR26FR0000095 | Severance Security Services | $4,770,000 |
| 70CDCR26FR0000096 | Savvy Professor | $4,727,750 |
| 70CDCR26FR0000087 | Delta Point | $3,910,774.24 |
| 70CDCR26FR0000092 | Response AI Solutions | $3,670,800 |
| **70CDCR26FR0000097** | **SOS International (SOSi)** | **$3,224,029.16** |
| 70CDCR26FR0000082 | Applied Intellect | $3,080,158 |
| **70CDCR26FR0000098** | **The Baptiste Group** | **$2,073,250** |
| 70CDCR26FR0000091 | Origin Investigations | $1,812,000 |
| 70CDCR26FR0000086 | Critical Response Strategies | $1,614,000 |
| 70CDCR26FR0000052 | MVM, Inc. (2026-03-20) | $1,446,000 |
| 70CDCR26FR0000090 | National Protective Services | $1,166,500 |
| 70CDCR26FR0000081 | Alpha Recovery | $1,055,544 |

This is *better* for the story, not worse: it means the program is operating, not notional, and it gives
you a real, defensible money number to lead with (~$85M in day-one orders) instead of a ceiling you have
correctly decided not to lead with. **Fix `WAVE2.md` before the wave reports.**

### 0.2 The UAC family is **18** IDIQs, not 16. Two awardees are missing — and one is SOSi. **[V]**

`70CDCR26D00000030`–`70CDCR26D00000047` = 18. The wave has 16. Missing:

- **70CDCR26D00000046 — SOS INTERNATIONAL LLC**, UEI L3VCKMD7J585, ceiling **$559,578,059.16**,
  signed 2026-06-02, sol 70CDCR26R00000015, PSC R799. (USASpending `CONT_IDV_70CDCR26D00000046_7012`.)
- **70CDCR26D00000047 — THE BAPTISTE GROUP, LLC**, UEI GEGMCJMMZ634, ceiling **$580,475,000**,
  signed 2026-06-02, same solicitation.

Corrected family ceiling ≈ **$20,583,928,204** (the ">$20B / 18 companies" claim SYNTHESIS §3 flagged as
UNCONFIRMED is **CONFIRMED**; our $19.44B was the undercount). And **SOSi — the firm with the
pre-solicitation letter contract — is in BOTH programs.** The cross-program set is not two firms; it is at
minimum four (Response AI, National Protective Services, SOSi, and B.I. via §0.3).

### 0.3 The "SOSi got paid before the competition closed" anomaly is one of **four** pre-competition instruments. **[V]**

Award-level keyword search misses scope added by modification. Running the same keyword at
**transaction level** (`/api/v2/search/spending_by_transaction/`, keyword `"skip tracing"`, 2015→now)
returns a three-week burst in October 2025, *before the solicitation was even published on 2025-11-10*:

| Date | Instrument | Vendor | Transaction | Mechanism |
|---|---|---|---:|---|
| 2025-10-09 | 70CDCR24FR0000006 **mod P00011** | Capgemini | **+$7,372,680** | in-scope add to a FY24 ICE IDIQ |
| 2025-10-21 | 70CDCR26C00000001 **mod 0** | SOSi | $0 at award; award total $6,954,758.46 | sole-source **letter contract** |
| 2025-10-27 | **70CDCR26FR0000003** | **Global Recovery Group** | **+$1,288,462** (award amount $5,678,837) | task order under **GSA schedule GS23F0026U**, NAICS **561440 Collection Agencies**, PoP → 2026-01-25 |
| 2025-10-30 | **70CDCR25FR0000127 mod P00002** | **B.I. Incorporated** | **+$690,000** | funding added to the **ISAP V** task order |

Two of these four are new to the case. The **Global Recovery Group order off a GSA schedule** is a
different evasion route than SOSi's letter contract — worth its own paragraph. The **B.I. ISAP V mod** is
the sharpest fact in the set: ICE added skip-tracing funding to the electronic-monitoring task order of the
company that supervises the same non-detained docket. (`70CDCR25FR0000127` is the ISAP V TO under
`70CDCR25D00000062` — confirmed against the repo's own
`investigations/geo-group/reports/bi-ice-skip-channel-task-allocation-ledger-2026-07-13.csv`.) A further
**mod P00003, 2025-12-17, +$9,660,000** on the same ISAP TO also matched the keyword ("ADDS FUNDING FOR
ATTACHMENT 4 PR…") — pull the full description before characterizing it.

Do **not** blend these into a single total: they mix award amounts with transaction obligations, which is
exactly the class of error that produced the unreproducible "$27.3M." State each instrument with its own
labelled measure. (They are collectively on the order of $20M, which is a far better explanation of the
mystery $27.3M than the current guess.)

### 0.4 On the UAC family, **18 offers were received and 18 IDIQs were awarded.** **[V]**

Every UAC IDIQ record I pulled reports `number_of_offers_received = 18`, `extent_competed = A`,
`type_set_aside = NONE` (checked D00000030 Alpha Recovery, D00000045 Savvy Professor, D00000046 SOSi,
D00000047 Baptiste). There are 18 awardees. **Every offeror won.** Contrast: the skip-tracing IDIQs report
**51 offers** (checked D00000006 AI Solutions 87, D00000017 Fraud Inc) for 14 awards.

This is the strongest single structural fact available on the UAC program and nobody has it. Caveat to
state in print: FPDS offer counts on multiple-award families are stamped identically on each award and are
sometimes entered loosely, so phrase it as "each of the eighteen award records reports eighteen offers
received" and corroborate from the award notice / an unsuccessful-offeror record before hardening it.

---

## 1. SOURCES AND TOOLS WE OWN AND ARE NOT USING

### 1.1 The repo already contains a 439-artifact ICE/GEO investigation nobody is drawing on **[V]**

> **CORRECTED 2026-07-27 (codex-Q, computed from the files themselves) — read before using §1.1 as a baseline.**
> The claim below that `direct-ice-prime-award-universe-2026-07-13.csv` is "a ready-made denominator for
> every 'is this normal for ICE?' question" is **WRONG and must not be relied on.**
> - The file is **not ICE-wide**. It covers only **six GEO-linked recipients** (The GEO Group, B.I.
>   Incorporated, GEO Care Services, GEO Transport, Correctional Services Corporation, Cornell Companies).
>   It is a GEO-family reconstruction, so every rate derived from it is a GEO/B.I.-cohort rate.
> - It holds **256 logical instruments, not 308** (228 USAspending-backed awards + 28 HigherGov-only
>   supplements). The 308 came from counting physical lines in a CSV with embedded newlines.
> - The **UAC program is entirely absent** from all five CSVs — zero rows match solicitation
>   70CDCR26R00000015, IDIQ 70CDCR26D00000030, or "safety verification".
> - Consequently **18-offers-to-18-awards cannot be called statistically anomalous** from held data; no
>   file enumerates all awardees per ICE solicitation. Use: "each of the eighteen UAC award records reports
>   eighteen offers received, and ICE issued eighteen IDIQ awards."
> - **Most consequential:** "zero reported subawards" has **no discriminating power** — **228 of 228**
>   GEO-linked ICE primes report `reported_subaward_count = 0` with blank amounts, including every award
>   over $100M. Do not treat a zero subaward count as evidence of pass-through or concealment anywhere.
>
> Still valid from §1.1: the archive is genuinely useful for GEO/B.I. context, the IGSA pass-through
> analysis is a good method template, and the skip-channel ledger independently reproduces the
> $19,032,607 skip-tracing obligation total. See `2026-07-27-ice-procurement-base-rates-codex.md`.

`investigations/geo-group/` is a full profile (config.yaml, AGENTS.md, 439 report artifacts) whose thread 2
is *"Electronic Monitoring & ISAP — BI Incorporated."* It contains, among others:

- `direct-ice-prime-award-universe-2026-07-13.csv` — **308 ICE prime awards** with NAICS, PSC,
  `extent_competed`, `offers_received`, `solicitation_identifier`, **`reported_subaward_count`** and
  **`reported_subaward_amount`**. This is a ready-made denominator for every "is this normal for ICE?"
  question the wave is asking by intuition.
- `direct-ice-competition-matrix-2026-07-13.csv`, `direct-ice-idv-task-order-families-2026-07-13.csv`
- `bi-ice-skip-channel-task-allocation-ledger-2026-07-13.csv` — already maps the B.I. skip channel
- `isap-v-skip-privacy-source-matrix-2026-07-13.csv` — the **PIA / records-schedule control layer**
  (DHS/ICE/PIA-062 ATD, NARA schedule DAA-0567-2018-0001). See §2.6.
- `systemic-analysis-ice-igsa-pass-through-2026-07-13.md` — a worked pass-through analysis *with explicit
  base-rate and innocent-explanation sections*. This is the house method for exactly the hypothesis
  WAVE2 lists as "secondary: pass-through." Reuse the structure; do not reinvent it.
- `ballard-geo-lobbying-contact-audit.*`, `geo-trump-political-money-ledger.csv`,
  `courtlistener-litigation-universe.*`, `timeline-analysis-2024-2026-ice-activations.md`

**Action:** before dispatching more agents, have one read `direct-ice-prime-award-universe` and the IGSA
pass-through analysis. Also note the **profile-scoping hazard**: skip-tracing findings are in `tech-right`
(threads 11/15/16) while all the ICE/B.I./GEO work is in `geo-group`. Per the standing lesson in memory
(Ehud Barak duplication), query for existing findings on B.I./GEO/ICE before documenting them again.

### 1.2 USASpending **transaction-level** search — the highest-yield unused method **[V]**

No repo tool wraps `POST /api/v2/search/spending_by_transaction/`. `query_usaspending.py transactions`
takes a recipient name, not a keyword, and `awards` has no NAICS/PSC filter. Award-level description
search **cannot see scope added by modification** — which is how both the Capgemini add and the B.I. ISAP
add stayed hidden. Working payload (verified):

```bash
curl -s -X POST https://api.usaspending.gov/api/v2/search/spending_by_transaction/ \
 -H 'Content-Type: application/json' -d '{"filters":{
   "time_period":[{"start_date":"2015-10-01","end_date":"2026-07-26"}],
   "award_type_codes":["A","B","C","D"],"keywords":["skip tracing"]},
   "fields":["Award ID","Recipient Name","Transaction Amount","Action Date","Mod",
             "Awarding Sub Agency","naics_code","Transaction Description"],
   "sort":"Action Date","order":"asc","limit":100,"page":1}'
```

Run the same for: `"locate"`, `"address verification"`, `"non-detained docket"`, `"wellness check"`,
`"safety verification"`, `"home visit"`, `"absconder"`, `"fugitive operations"`, `"bounty"`. **Build a tool
for this** (`query_usaspending.py keyword-transactions --naics --psc --agency`) — infra request, higher
priority than the FPDS-ATOM tool in the current plan because it is free, unrated, and covers all agencies.

### 1.3 NAICS-filtered spend queries → the comparison class, in two queries **[V]**

`spending_by_award` accepts `naics_codes`. Verified: **DHS's historical use of NAICS 561611 is employee
background investigations**, not locating people. Top pre-2025 DHS 561611 awards: CACI $50.4M and $32.2M
(CBP background investigative services), **Omniplex $33.2M (USCIS Tier 4/5 background investigations)**,
CACI $29.9M (ICE), Peraton Risk Decision $26.5M / $19.8M / $15.5M, Anasec $25.9M.

Note the irony worth reporting: **Omniplex's own 561611 track record is vetting DHS's own staff.** The
code ICE chose for "find this person for removal" and "visit this child at home" is, in DHS's own history,
the personnel-clearance code.

### 1.4 Federal skip tracing before ICE was a **data product**, not a surveillance service **[V]**

Government-wide keyword sweep, 2005→2026. Every pre-2025 buyer was a debt-collection or benefits shop and
every vendor was a data broker:

| Buyer | Vendor | NAICS | Scale |
|---|---|---|---|
| Treasury Bureau of the Fiscal Service | Data & Analytic Solutions; SJ Tech | 541519 / 541511 | $3.92M (2010, largest pre-2025); most under $300K |
| Social Security Administration | **LexisNexis Special Services** | **561450 Credit Bureaus** | $208K |
| Rural Housing Service | **Experian** | 561450 | $9K–$25K |
| Dept. of Veterans Affairs | **TransUnion**; NCO Financial | 561450 / 523999 | $2.6K–$232K |
| Dept. of Education | PHEAA; Maximus Federal | — | servicing line items |
| Air Force | West Publishing | — | $3.4K "skip tracing software" |
| HHS | DEVAL LLC | 541611 | $28K |

**DHS appears nowhere before 2025-10-09.** So the before/after is: a $20K–$3.9M credit-bureau data
product, bought under the *credit bureau* code, becomes a $1.44B-ceiling program of "physical observation"
bought under the *investigations* code. That is a checkable, quotable structural break and it is the
single best framing device available to this story.

### 1.5 Securities: GEO's 10-K and 8-Ks discuss skip tracing. Nobody has read them. **[V]**

`query_edgar.py search "skip tracing" --start 2025-09-01` returns 68 hits; the top three are GEO:

- **10-K filed 2026-02-25 (FY2025)**, CIK 923796 — describes the ICE skip-tracing award **twice**
  (Recent Developments and Note-level Contract Developments). GEO's own words: skip tracing "entail[s]
  enhanced location research with identifiable information, commercial data verification, and physical
  observation" for people "on the federal government's non-detained docket." Two-year term (1+1),
  effective 2025-12-16. **No dollar value is given in either passage** — the "$121M" lives only in the
  Dec-22 press release. That asymmetry is itself reportable.
  Same passage discloses the **ISAP renewal (announced 2025-09-30, two-year, effective 2025-10-01)** —
  i.e. ICE renewed B.I.'s monitoring contract, then added skip tracing to that task order (§0.3), then
  gave B.I. its own skip-tracing IDIQ. Three steps, one company, one docket.
- **8-K EX-99.1, 2026-02-12** and **8-K EX-99.1, 2026-05-06** (Q4-25 and Q1-26 earnings releases) both
  contain "skip tracing" — read these for revenue attribution, segment commentary, and guidance language.
- Governance in the same window: CEO J. David Donahue retired 2026-02-28; **George Zoley resumed CEO
  1 March 2026**; Donahue gets **$104,167/month through 2028-02-28** as a consultant on "secure services
  business opportunities." Probably a separate story, but it belongs on the timeline.

Untested but obvious next steps **[U]**: `query_edgar.py sections GEO --section risk` and `--section mda`;
`query_market.py correlate GEO --events events.json --window 5` against the award dates; CoreCivic (CXW)
for comparison; and Capgemini SE — a **French-listed** parent whose US subsidiary holds the largest
skip-tracing ceiling ($365.8M). Does Capgemini disclose ICE removal-support work to European investors or
under CSRD/CS3D human-rights due diligence? Nobody has looked. That is a distinct, publishable angle with
a European audience.

### 1.6 Lobbying: a live hit on the first query **[V]**

`query_lobbying.py client "The Lemoine Company"` → **Cornerstone Government Affairs**, registered 2025,
issue codes **Homeland Security** and **Disaster Planning/Emergencies**, activity described as
"Introductory meetings on company disaster response and other capabilities":

| Filing | Income |
|---|---:|
| 2025 Q3Y | $40,000 |
| 2025 Q4 | $60,000 |
| 2026 Q1 | $60,000 |
| 2026 Q2 | $60,000 |

**$220,000 of introductory meetings on homeland security, then a $1.73B ICE UAC ceiling (2026-06-02) and a
$7.69M day-one task order (2026-06-18).** Caveat: the LDA client is *The Lemoine Company, LLC*; the awardee
is *Lemoine Disaster Recovery LLC*. Establish the corporate relationship from the Louisiana registry before
publishing the sequence.

Other confirmed registrations: SOSi ↔ Signal Group Consulting; Omniplex ↔ Akin Gump (1999, $60K) and
Monument Advocacy; Capgemini Inc ↔ Johnston & Associates; MVM Technologies ↔ J M Burkman; Caduceus
Occupational Medicine ↔ small shops. **Zero LDA registrations for Bluehawk and Global Recovery Group.**

Not yet run **[U]**: `query_lobbying.py client` for all 18 UAC awardees and all 14 skip-trace awardees;
`registrant "Cornerstone Government Affairs"` filtered to 2025–26 DHS/ICE issue codes to see who *else*
they walked in; `contributions` (LD-203) for the registrants; and `query_fara.py` for any awardee with
foreign ownership (Capgemini is French-owned — FARA is the wrong statute but the check is cheap).

### 1.7 HHS/ORR grants: the sources nobody thought to open, and they are decisive **[V]**

`spending_by_award` with `award_type_codes ["02","03","04","05"]` (assistance, not contracts). Two hits
that change the shape of the story:

1. **APPLIED INTELLECT LLC** — ICE UAC awardee D00000031 ($1.04B ceiling, $3,080,158 day-one TO) — holds
   HHS/ACF award **90ZU0581, $84,526,776.83, 2023-09-29 → 2026-09-28**, described as **"HOME STUDY AND
   POST RELEASE SERVICES FOR UNACCOMPANIED CHILDREN."** It is the ORR post-release-services incumbent, and
   it is the only *for-profit LLC* in a field of child-welfare nonprofits.
2. **THE BAPTISTE GROUP, LLC** — the 18th UAC awardee we did not know existed (D00000047, $580.5M ceiling)
   — is a **former ORR unaccompanied-children shelter grantee**: 90ZU0278 **$15,467,872.78** (2019-02-01),
   90ZU0285 $2,198,446.83 (2019-08-01), 90ZU0391 (2021, single-source). PPP records put it in McDonough,
   GA with 42 jobs (2020) and 71 jobs (2021) under NAICS **623990 Other Residential Care Facilities**.

And the comparison class itself, which is devastating in its plainness. Keyword `"POST RELEASE SERVICES"`,
assistance awards, 2015→now: **25 awards visible (more paginated), $2,251,473,937**, all to child-welfare
organizations — U.S. Committee for Refugees and Immigrants $308.4M; Compass Connections $291.2M; Family
Endeavors $238.1M; Lutheran Immigration and Refugee Service $201.3M; Church World Service $147.9M;
National Youth Advocate Program $121.5M; Bethany Christian Services $91.5M; International Rescue
Committee $46.9M; Cayuga Home for Children; Heartland Human Care; Morrison Child and Family Services;
Board of Child Care of the UMC; Southwest Key; BCFS; Rite of Passage; Urban Strategies. **Zero contracts
under that keyword — the lawful channel is grants to nonprofits.**

So: home visits to unaccompanied children have been bought for a decade as **child welfare**, from
**nonprofits**, on **grants**, at roughly **$2.25B cumulative**. ICE has now created a parallel channel
buying the same physical act as **investigation** (NAICS 561611, PSC R799), from **security and PI firms**,
on **IDIQ contracts**, with **~$20.6B of ceiling** and **100% of offerors awarded** — and it has recruited
the incumbent ORR home-visit contractor and a former ORR shelter operator into it.

**Name-collision trap, flagged now:** ICE awardee "**Compass United**" is *not* ORR grantee "**Compass
Connections**" ($291M). Do not conflate. Same for Alpha Recovery LLC vs Alpha Recovery Corp (Aurora CO,
NAICS 561440), and the several unrelated Delta Point entities.

### 1.8 PPP as a **staffing/capacity** test **[V, with a caveat]**

`query_ppp.py sql` over ~11M SBA records is a primary-source answer to "could this firm possibly do the
work," for any entity that existed in 2020–21:

- **ORIGIN INVESTIGATIONS INC** (Los Angeles): **1 job reported**, $20,800 (2020-07-19 and again
  2021-04-14, NAICS 541990/541199). Now holds a **$536.6M** UAC ceiling and a $1.81M task order.
- **APPLIED INTELLECT, LLC** (Wexford PA): 20 jobs, $211,200 (2020-04-16).
- **THE BAPTISTE GROUP, LLC** (McDonough GA): 42 jobs (2020) → 71 jobs (2021), NAICS 623990.

Caveat that matters: `query_ppp.py search` is fuzzy and prints only a tail summary; several apparent hits
(GRAVITAS at Glacier Bank/NAICS 812990, "AMERICAN NATIONAL PROTECTIVE SERVICES LLC" in Capitol Heights MD,
Delta Point Inc in Scottsdale AZ) are **different companies**. Use `query_ppp.py sql` with
`borrowername LIKE` **plus** city/state/NAICS, and pin against the SAM address. `query_ppp.py address
"6858 Ingram"` returned 0 — National Protective Services LLC of San Antonio has no PPP loan, which is
itself informative.

### 1.9 Certificate transparency did real work in two queries **[V]**

- `query_crtsh.py search sdnexus.app --subdomains` → **237 certificates** and a full multi-environment
  SaaS estate: `api.`, `dev-portal.`, `uat-portal.`, `demo-portal.`, `community.`, `analytics.portal.`,
  `alertmanager.dev-portal.`, and **`brokerbuster.dev.portal.sdnexus.app`**. This *strongly* corroborates
  the SYNTHESIS §5 correction that SDNexus is a genuine product, not a shell website — a shell does not
  run staging environments and an alertmanager. It also hands over "brokerbuster" as a name to chase.
- `query_crtsh.py search cyberintelservice.com --subdomains` → 54 certs including
  **`cyberintelservice.com.shadowsecrecy.com`**, plus `cpanel.`/`webdisk.`/`webmail.` = shared cPanel
  hosting. **`shadowsecrecy.com` is a brand-new selector** (resolves 104.21.70.195, Cloudflare). A SAN
  that nests one brand inside another domain is a genuine shared-control signal, unlike a shared
  Cloudflare IP.

DNS spot check **[V]**: ais87.com → 15.197.225.128; fraudinc.us → 173.255.202.67; gssglobal.org →
82.197.80.81; responseai.us → 185.230.63.186; cislabs.org / sdnexus.app / cyberintelservice.com → Cloudflare.
**Do not read shared Cloudflare IPs as shared control** — that is a naive tell.

Untested and worth doing **[U]**: `query_crtsh.py timeline ais87.com` (83 certs — dates the site's
transformation and the scrub precisely, independent of Wayback); `query_urlscan.py technologies` on each
awardee domain to compare **Google Analytics / GTM IDs, favicon hashes, and template fingerprints** —
that, not IP sharing, is the real "same builder / same broker" test for the coordinated-bidding
hypothesis; `query_shodan.py search "ssl:<domain>"` for co-hosted siblings.

### 1.10 Court records: federal is thin, and we have almost no state coverage **[V/U]**

`query_courtlistener.py party` returns exactly two hits across the UAC cohort: **The Baptiste Group**
(D. E.D. Tenn.) and **Origin Investigations** (C.D. Cal.); zero for Savvy Professor, Septimo Solutions,
Applied Intellect. Both hits should be pulled. **[V]**

But federal court is the wrong forum for the traces small-entity principals actually leave. The repo has
`query_nyscef.py` and nothing else for state courts, which is a real gap for this cohort **[U]**:

- **Wisconsin Circuit Court Access (wcca.wicourts.gov)** — free statewide name search, full case history.
  This is the right place for **Gregory P Behm** and **Roberto Guercini** (Washington County).
- **Texas** — Harris County District Clerk and **Montgomery County** (Conroe = Fraud Inc's SAM address);
  Bexar County (National Protective Services).
- **Virginia OCIS** (Spotsylvania for Todd Thompson / Savvy Professor; Fairfax for Great Falls / Kraemer).
- **Florida** Okaloosa/Santa Rosa clerks (Hodrick / GSS / Habari).
- **Georgia** Henry County (Baptiste, McDonough).
- Case types that matter here and are invisible federally: debt collection, evictions, small-claims,
  divorce (asset schedules), mechanics' liens, employment/wage claims, and **PI-license disciplinary
  appeals**.

### 1.11 Occupational licensing — the check that could kill the program, and we have no tool **[U]**

Skip tracing and in-person "safety verification" are, in most states, **regulated private-investigator
activity**. Fraud Inc holds TX PI licence A22991201. The obvious and unasked question: **do the other 31
awardees hold PI/security licences in the states where they must perform, and does ICE's own SOW require
it?** A single unlicensed awardee performing home visits on children is a concrete legal exposure, and
these registries are public and searchable by company name:

- **Texas DPS Private Security Bureau**; **Virginia DCJS**; **Florida Dept. of Agriculture & Consumer
  Services Division of Licensing (Class "A"/"C"/"MA")**; **California BSIS**; **Georgia Board of Private
  Detective and Security Agencies**; **Maryland State Police Licensing**; **Wisconsin DSPS**;
  **Ohio Dept. of Public Safety PISG**; **Colorado (no state PI licence — note the gap)**.
- Related and equally unexamined: **bail-recovery / bounty-hunter licensing** (the frame the press is
  using), and **FAA Part 107 / state UAS rules** for CIS Labs' drone claims.

This is worth an infra request: `query_state_licensing.py` covering the top 8 states' PI/security
registries. It is also the most under-priced angle in the whole case.

### 1.12 Smaller ones, each verified as usable

- **Federal Register** `query_federal_register.py` **[V, tool works]** — two "Privacy Act of 1974; System
  of Records" notices published 2026-04-22 and 2026-05-21 sit inside the window. Check whether either is
  ICE and whether it covers this collection. See §2.6.
- **DocumentCloud** `query_documentcloud.py` **[V]** — works anonymously (the configured auth 401s, which
  is worth fixing). Notable hit: **DC id 4380794, "Community Safety Initiative for the Unaccompanied Alien
  Children Program," 2018-02-16, 4pp** — a possible 2018 precursor to the 2026 "Safety Verification
  Initiative." Pull it.
- **MuckRock is broken** **[V]** — `MUCKROCK_USERNAME`/`MUCKROCK_PASSWORD` are set in `.env` but the API
  returns "username and password are incorrect." opus-A hit the same wall. Fix the credential; MuckRock is
  the natural home for the FOIA items in the plan and for finding requests others have already filed.
- **USPTO** `query_patents.py` **[V]** — **no patents assigned to "Response AI Solutions" or
  "AI Solutions 87."** The "AI agent" marketing has zero patent backing. Useful negative for a story that
  turns on AI claims. Note a genuine gap: **the repo has no trademark tool** — USPTO TSDR/`tmsearch` would
  show whether "SIVS," "Response AI," or "AI Solutions 87" filed marks, their first-use-in-commerce dates,
  and the specimen images (often the clearest evidence of what a firm actually claimed to sell, and when).
- **`query_sam.py opportunities`** **[U]** — pull `70CDCR26R00000015` and `26-SOL-DCR01` with all
  amendments and Q&A attachments. The Q&A file usually reveals the incumbent, the licensing requirements,
  and the evaluation weighting. Ration the calls: 10/day on the basic tier.
- **`ingest_sam.py naics 561611`** **[U]** — enumerate every SAM registrant claiming 561611 and cross it
  against the 32 awardees; also `ingest_sam.py address` on each cohort address for co-registrants (Codex D
  did this for four of them; do the other 28).
- **`query_990.py`** **[U]** — mostly a miss for this cohort, but run it on the ORR nonprofit side: the
  HS/PRS grantees' 990s (officers, Schedule J compensation, related orgs) are the comparison for what
  child home-visit capacity actually costs and who staffs it.
- **`query_opensanctions.py pep-check`** **[U]** — near-certain miss for these principals, but it is a
  local DB and costs nothing. Same for `query_gleif.py` (Capgemini SE / GEO LEI hierarchies) and
  `ftm_bridge.py` if you want to export the cohort graph.
- **`selector_pivot.py`** **[U]** — the right tool for `shadowsecrecy.com`, `jhodrick@gssglobal.org`,
  `james.kraemer@…`, and Behm's email once you have it. Dehashed is live per memory; keep leak-derived
  claims capped at `medium`.
- **`graph_tools.py` / `analysis_export.py`** **[U]** — after Wave 2, the cohort is 32 firms and ~40
  named people; run bridge/centrality detection rather than eyeballing the overlaps.
- **`ingest_faa.py`** **[U]** — cheap, and CIS Labs sells drones; also worth checking whether any
  principal registers aircraft (a common small-security-firm asset).

---

## 2. ANGLES NOBODY HAS TAKEN

### 2.1 The headline is no longer skip tracing — it is the **care-to-enforcement crossover**

Ranked first because it is the most newsworthy, the most defensible, and entirely primary-source. The
government has run child home visits for a decade through HHS/ORR as social work, on grants, to
nonprofits. ICE has now stood up a parallel channel that buys the same physical act as investigation, from
security firms, and has pulled **the ORR post-release incumbent (Applied Intellect, $84.5M) and a former
ORR shelter operator (Baptiste Group, $15.5M)** across the line. The story writes itself from award
records: two systems, one child, opposite purposes, overlapping vendors. Add the SOW (already Tier 1 in the
plan) and you have the ethical core with documents underneath it.

The sharp sub-question: **what happens to a family's ORR-collected sponsor information when the
enforcement channel hires the same contractor?** That is a Privacy Act question with a factual answer
(§2.6).

### 2.2 The demand side: profile the buyers, not just the sellers

The plan mentions resolving JABYAD7012 and nothing else. `query_highergov.py people --email` works **[V]**
— it returned a complete record for **Jason Boudreaux, "Procurement Officer," ICE Enforcement and Removals
(ERO), agency_key 904, last seen 2026-06-04**. Do the same for `ian.somppi@ice.dhs.gov`,
`john.cappello@ice.dhs.gov`, and every contact on both solicitations. Then:

- **What else did these officials buy, and how?** The local wrapper only supports
  `opportunity --source-id`, so mapping official → solicitation history needs either the HigherGov UI or a
  tool enhancement (**infra request:** add `--contact-email` / `--agency-key` / date filters to
  `query_highergov.py opportunity`). The pattern to test: does the same small group of ERO procurement
  officers stand up letter contracts, GSA-schedule workarounds, and everyone-wins IDIQ families
  repeatedly? If yes, that is a systemic finding about an office, not an anecdote about a contract.
- **Resolve JABYAD7012 to a person** via the FPDS user prefix convention (`<initials><surname><office>`,
  cf. JBOUDREAUX7012 / SWRAY7012) cross-referenced against ICE staff directories, `query_congress.py`
  hearing witness lists, and GovInfo. Then check whether that person also entered the UAC awards.
- **Sweep the remaining 11 skip-trace base DOs plus all 18 UAC IDIQs and 19 task orders** for
  creator==approver. Three of fourteen is not a pattern claim; nineteen of nineteen would be.
- **Revolving door:** run the ICE ERO names and the awardees' principals against
  `ingest_propublica_disclosures.py` (1,573 Trump-administration appointees, 116K assets) and
  `query_littlesis.py`. Also check the reverse: are any awardee principals former ICE/ERO/HSI?
  (Savvy Professor's Todd Thompson is ex-FBI; Bluehawk's advisers are ex-DIA. That is a pattern worth
  quantifying rather than noting anecdotally.)

### 2.3 Ceiling-stuffing as an appropriations story

$20.6B of ceiling with ~$85M ordered is not a scandal by itself — IDIQ ceilings are routinely set far
above expected volume. The story is **why this much, and what it enables**. Testable:

- **The arithmetic of the ask.** The solicitation cites 479,000+ UAC released FY21–FY24 and the wave's
  figure is ~100,000 children. Work out the implied per-visit price from the day-one task orders (each
  "MEET THE IDIQ MINIMUM REQUIREMENT OF 1000 CASES"): Caduceus $11.965M/1,000 = **$11,965 per case**;
  Alpha Recovery $1.056M/1,000 = **$1,056 per case**. **An 11× spread for the same nominal deliverable**
  is a first-order anomaly nobody has computed. Confirm the 1,000-case denominator from the SOW, then
  publish the table. Compare against ORR HS/PRS per-child costs from the grantees' own reporting.
- **Ceiling vs. appropriation.** Cross the family ceiling against ICE's actual ERO appropriation and the
  FY26 reconciliation plus-up (`query_congress.py`, `query_govinfo.py --collection CRPT/GAOREPORTS`,
  DHS congressional budget justifications). A ceiling structure far exceeding available appropriation is
  how surge capacity gets pre-authorized outside the annual scrutiny cycle — and that framing is
  checkable rather than rhetorical.
- **Guaranteed minimums.** The repo's geo-group work already built
  `geo-ice-guaranteed-minimum-economics-report.md`. Apply the same method: what is the guaranteed minimum
  on each of the 18 UAC IDIQs, and what does the government owe if it orders nothing?

### 2.4 The ideology-to-procurement translation layer

opus-B correctly flags Erik Prince's 2USV blueprint as context. Nobody has tried to trace **the actual
translation path**, which is a documentary question, not a speculative one:

- `query_govinfo.py search --collection CHRG` and `CRPT` for 2025–26 hearings using the blueprint's
  vocabulary ("skip tracing," "bounty," "deputize," "non-detained docket").
- `query_congress.py` for the DHS authorization/appropriations report language authorizing
  "location verification" or contractor "locating services."
- `query_federal_register.py` for the rulemaking and notices that had to precede a program of this shape.
- The 2018 **"Community Safety Initiative for the Unaccompanied Alien Children Program"** document
  (DocumentCloud 4380794) — is the 2026 "Safety Verification Initiative" a renamed revival of a Trump-I
  era initiative? If so, that is the translation path, with a paper trail.
- Personnel: who moved from the advocacy layer into ERO procurement or policy in 2025?
  (`ingest_propublica_disclosures.py`, `query_littlesis.py`.)

### 2.5 Consequences: what did the locates actually produce?

The weakest documented part of the case, and the part a general reader cares most about.

- **TRAC Immigration (Syracuse)** and ICE's own published detention/ATD statistics: does the arrest or
  ATD-enrollment curve inflect after 2025-12-16? Correlate with `event_timeline.py`.
- **The March 2026 facial-recognition misidentification** the Inquirer mentions: get the underlying case.
  `query_courtlistener.py recap-search` + `fjc --nos 440/540` (civil rights / habeas) for 2026 filings
  naming ICE contractors; habeas petitions are where wrongful-locate facts surface first.
- **Tort claims:** FTCA administrative claims against DHS and Bivens suits naming contractors. Also state
  court — a contractor knocking on the wrong door produces trespass and harassment claims locally.
- **The children's side:** any ORR/HHS OIG or ACF review of the interaction between ICE visits and the
  HS/PRS caseload; state child-protective referrals generated by contractor visits.
- **`query_gdelt.py`** for local-news reports of unidentified people asking about migrant children — the
  ground-level signal that precedes litigation.

### 2.6 The Privacy Act / PIA compliance angle — cheap, concrete, and unexamined

The repo's own `isap-v-skip-privacy-source-matrix-2026-07-13.csv` already maps this control layer for
ISAP (DHS/ICE/PIA-062; NARA schedule DAA-0567-2018-0001). Nobody has applied it to the new programs. A
federal program that collects location and household data on ~100,000 children through private
contractors requires a **Privacy Impact Assessment** (E-Government Act §208) and, if it maintains a
system of records, a **Privacy Act SORN** in the Federal Register.

Verified starting point **[V]**: two "Privacy Act of 1974; System of Records" notices published
2026-04-22 and 2026-05-21. Check whether either is DHS/ICE and whether it covers this. Then check
dhs.gov/privacy-documents for a PIA naming the Safety Verification Initiative or skip tracing.
**If neither exists, that is a documented compliance gap** — a clean, hard, non-inferential finding.

### 2.7 Contract-vehicle laundering as a named mechanism

Assemble what is now four separate observations into one mechanism story: the **Navy WEXMAC 2.0**
task order for the St. Paul surge; the **GSA MAS schedule** order to Global Recovery Group; the **letter
contract** to SOSi; the **in-scope modification** onto Capgemini's FY24 IDIQ and onto B.I.'s ISAP V task
order; and MVM's UAC work run through a **FY24 ICE vehicle** (`70CDCR24D00000002`) months before the new
family existed. That is six distinct ways of buying immigration-enforcement services without running a
competition first, by one office, inside one year. The repo's geo-group
`direct-ice-idv-task-order-families` and `direct-ice-competition-matrix` give you the denominator to say
whether that is unusual for ERO.

### 2.8 The losers, and the 100%-award-rate question

51 offers → 14 awards on skip tracing; 18 → 18 on UAC. **Who were the 51, and who were the 18?**
Unsuccessful-offeror identities are obtainable (award notices, debriefing records via FOIA, and
occasionally the solicitation Q&A). If the UAC pool was 18 firms and all 18 won, the interesting question
is not who won but **how the pool got to exactly 18** — was there an industry day, a sources-sought
notice, a pre-qualification step, or a broker assembling bidders? `query_sam.py opportunities` plus the
solicitation attachments will show the sources-sought / RFI lineage. This is the most direct available
test of WAVE2's central coordinated-bidding hypothesis, and it approaches it from the buy side rather
than trying to prove lateral links between sellers.

### 2.9 Two angles I would add that are not on anyone's list

- **The insurance and bonding layer.** PI licensure typically requires a surety bond and E&O coverage;
  home visits to children in most states require background checks and sometimes child-abuse-registry
  clearance for personnel. Who underwrites 32 firms doing this? Bond and insurance requirements are
  usually stated in the solicitation's Section H — and an awardee that cannot obtain the bond cannot
  perform. This is a quiet, checkable capacity constraint.
- **Gravitas's non-renewal as the natural experiment.** The plan treats it as a curiosity (Tier 2, #5).
  It is better than that: it is the only case where ICE declined to continue, so it is the only place the
  government has revealed a performance standard. Whatever Gravitas failed to do defines what the other
  13 were required to do. Get the mod/termination record and, if needed, FOIA the CPARS entry.

---

## 3. METHODOLOGICAL CRITIQUE

### 3.1 The IDV-vs-task-order obligation artifact nearly caused a repeat of the original error

§0.1 is not a detail. The team burned itself once on an unreproducible obligations total and responded by
adopting a rule ("ceilings are not obligations") — then applied that rule to a number ($0) that was itself
an artifact of querying the wrong level. **The general lesson: for IDIQ families, obligations must always
be summed from child task orders, never read off the parent IDV.** Both the 1.32% skip-tracing figure and
the "$0" UAC figure come from the same class of query and only one of them was checked properly.

### 3.2 "Residential address" is a weak tell on its own — treat it as a base-rate question

I think the case is over-reading this. A great many legitimate small federal contractors — especially
SDVOSB/8(a) consultancies — register their SAM address at the owner's home. It is normal, not deviant.
What is *actually* anomalous is the combination, and the combination should be stated as a conjunction, not
a vibe:

1. residential/PO-box registered address, **and**
2. SAM registration or entity formation within weeks of the solicitation, **and**
3. no prior prime federal history in the relevant NAICS, **and**
4. a ceiling three or more orders of magnitude above any prior award, **and**
5. no evidence of licensed personnel in the states of performance.

Get the denominator before publishing any of it: `ingest_sam.py naics 561611` gives you every registrant
claiming the code — what fraction are at residential addresses? The repo's
`direct-ice-prime-award-universe` (308 ICE prime awards) tells you what ERO's normal offers-received and
new-entrant rates look like. Without those two denominators, a hostile editor kills the paragraph, and
should. The geo-group `systemic-analysis-ice-igsa-pass-through` report already models this discipline with
explicit "base-rate and innocent explanation" sections — use that template.

### 3.3 Where we are currently most at risk of being wrong

- **Name collisions.** Compass United ≠ Compass Connections (ORR, $291M). Alpha Recovery LLC ≠ Alpha
  Recovery Corp (Aurora CO). "Delta Point" matches at least four unrelated companies. National Protective
  Services LLC (TX) ≠ National Protective Services Inc (VA) ≠ American National Protective Services LLC
  (MD) — Codex D got this right, but the same discipline has not been applied to the 18 UAC firms. Every
  UAC awardee must be pinned by **UEI**, and UEIs for the newly discovered two are: SOSi L3VCKMD7J585,
  Baptiste Group GEGMCJMMZ634.
- **"18" means two different things.** `number_of_offers_received = 18` and *18 awardees* are both true
  and are different facts. SYNTHESIS §3 warns about exactly this and then the coincidence turns out to be
  load-bearing. State both, separately, with sources.
- **FPDS workflow fields.** The JABYAD7012 finding is strong but rests on 3 of 14 records and on the
  assumption that `createdBy`/`approvedBy` mean what they appear to mean. Before publishing, establish
  from FPDS documentation (or an FPDS user-manual citation) what the approval field represents, and note
  that a small contracting office may legitimately have one warranted officer entering data with approval
  authority delegated in the system while a separate paper review occurred. The March contrast
  (Boudreaux → Wray) is what makes the January pattern meaningful — lead with the contrast.
- **"Zero subawards reported" proves little.** I checked: `query_usaspending.py subawards` for Global
  Recovery Group, Response AI, Septimo, and Baptiste returns nothing. But FSRS reporting is chronically
  delinquent, small businesses are exempt from subcontracting plans, and reports lag by months. Absence of
  reported subawards is **not** evidence against the pass-through hypothesis. (Bluehawk, SOSi and Caduceus
  do appear — as *subawardees* of BAE, Jacobs, GDIT, DirectViz and **Booz Allen** ($7.68M to Caduceus,
  2026-04-07) — which is a different and useful fact.)
- **Cloudflare IPs and shared site builders** (`*.vivitiapp.com`) are not evidence of common control.
  GoDaddy templates are not evidence of common control. Only shared certificate SANs, shared analytics
  IDs, shared registrant contacts, or shared filing agents are.
- **Wayback gaps are not scrubbing.** The AI Solutions 87 timeline is genuinely strong (content capture
  Aug 2025 → 301 to google.com), but the aggressive bounty-hunter copy 404 Media quoted was *never
  captured*. Say "the quoted language does not appear in any archived capture; it was added and removed
  between captures," not "they scrubbed it" — unless you can produce the capture.

### 3.4 What a hostile editor, or the contractors' lawyers, hits first

In order of danger:

1. **"You are treating a ceiling as a program size."** Already partly addressed; §0.1 gives you the real
   money figure so you never have to lean on the ceiling.
2. **"Being small and new is not illegal, and set-aside programs exist precisely to award to new small
   businesses."** True, and these awards were *not* set aside (`type_set_aside = NONE`), which cuts both
   ways: no small-business preference was invoked, so the firms won on full and open competition. You need
   the licensing and capacity gap (§1.11, §1.8) to make smallness matter.
3. **"Your separation-of-duties claim rests on three records and your reading of a database field."**
   Sweep all of them; get the field definition.
4. **"'Wellness checks' are a child-welfare good; you are implying sinister motive from a NAICS code."**
   This is the most dangerous line, and §2.1 is the answer: the comparison class shows the same act was
   bought as child welfare for a decade and is now bought as investigation, from investigators. Let the
   contrast carry the implication.
5. **"You conflated two companies."** See §3.3. One error here discredits everything.
6. **"You are quoting a marketing website that no longer exists."** Anchor every characterization to a
   procurement record or an archived capture with a timestamp.

### 3.5 The strongest innocent explanation, and how to distinguish it

State it fairly, because it is not weak: **ICE faced a step-change in required removal volume in 2025–26,
had no in-house capacity to locate people on a non-detained docket of millions, and did what a surging
agency does — bought bridge capacity fast on existing vehicles, then competed a broad multiple-award IDIQ
with a deliberately generous ceiling and a wide awardee pool so that it could distribute work without
re-competing. Awarding to all 18 qualified offerors maximizes surge capacity and is defensible on its own
terms. Small new firms won because the incumbents' capacity was already committed, and the residential
addresses simply reflect that small consultancies register where their owners live. NAICS 561611 was
chosen because it is the closest existing code for investigative field work; there is no code for "locate
a person," and PSC R799 is the standard catch-all.**

Evidence that would **distinguish** this from the sinister reading:

| Test | Innocent | Sinister |
|---|---|---|
| The 18-firm pool's origin | sources-sought/RFI open to all; many bidders self-selected | pool assembled or steered; bidders share an agent, consultant, or template |
| Per-case pricing | narrow band; differences explained by geography/scope | 11× spread with no scope explanation (currently observed — needs SOW to interpret) |
| Licensing | awardees licensed in states of performance; SOW requires it | unlicensed firms performing regulated activity; SOW silent |
| Capacity build-out | hiring, subcontracts, licensure filings after award | no hiring, no subawards, no licences — work flowing to incumbents |
| Pre-award instruments | documented urgent-need J&As on file | J&As absent, thin, or retrospective |
| Gravitas non-renewal | ordinary performance decision | de-scoping to conceal a problem |
| Privacy compliance | PIA and SORN published before performance | neither exists |

Every one of those rows is checkable. That is the shape a defensible investigation should take from here.

### 3.6 Process observations

- **The wave is running against a snapshot** (SAM March 2026) for status questions that are now four
  months stale. Any "as of" claim about registration status, exclusions, or addresses needs a live check.
- **Verification burden is being spent on re-confirming figures already confirmed.** Every per-firm ceiling
  in #4647 matched to the dollar in Wave 1. Stop re-pulling ceilings; spend the budget on the seven
  sources in §1 that have never been touched.
- **Nobody is looking at assistance awards.** Two of the three most important facts I found this session
  came from flipping `award_type_codes` from contracts to grants. That flag should be in the standing
  checklist for any procurement investigation touching social services.

---

## 4. PRIORITIZATION

### Do first — each produces a publishable fact

1. **Fix the record: 18 IDIQs, $86.8M obligated, ceiling $20.58B, SOSi and Baptiste added.** (§0.1–0.2)
   Half a day. Blocks everything downstream because the current framing is wrong.
2. **The HHS/ORR crossover.** Confirm Applied Intellect's 90ZU0581 and Baptiste's 90ZU0278/0285/0391 at
   award-record level; check whether ORR's HS/PRS contract with Applied Intellect is still live while it
   holds the ICE IDIQ; enumerate the full ORR HS/PRS grantee list with amounts; check every one of the 18
   UAC awardees for ORR/ACF history. **This is the story.** (§1.7, §2.1)
3. **The comparison class, written up.** Pre-2025 federal skip tracing = credit-bureau data products under
   NAICS 561450; DHS's own 561611 history = employee background investigations; child home visits = ORR
   grants to nonprofits. Three queries, already run, produce a before/after that no outlet has. (§1.3–1.4, §1.7)
4. **Per-case pricing table from the 19 task orders + the SOW.** $1,056 to $11,965 per case for the same
   nominal deliverable. Needs the SOW to confirm the 1,000-case denominator — which is already Tier 1 in
   the plan. (§2.3)
5. **Transaction-level keyword sweep, all nine terms**, and the four pre-competition instruments written
   up as a single mechanism. (§0.3, §1.2, §2.7)
6. **GEO's 10-K and the two 8-Ks.** GEO's own SEC language ("physical observation" of people on the
   non-detained docket), the ISAP-renewal → ISAP-mod → own-IDIQ sequence, and whether GEO quantifies the
   line for investors. Half a day, all primary. (§1.5)
7. **Licensing sweep, top 8 states.** Manual now, tool later. Potentially the hardest-hitting compliance
   finding in the case. (§1.11)
8. **PIA/SORN check.** One Federal Register query plus dhs.gov/privacy-documents. Cheap; a null result is
   itself the finding. (§2.6)

### Do next — infrastructure and depth

9. **Two infra requests, in this order:** (a) USASpending transaction/NAICS/PSC keyword tool; (b) FPDS-NG
   ATOM tool (already in the plan). Add (c) HigherGov opportunity filters by contact/agency/date. Fix the
   **MuckRock credential** and the **DocumentCloud auth** while you are in there.
10. **Full FPDS creator/approver sweep** across all 14 skip-trace base DOs, 18 UAC IDIQs, and 19 UAC task
    orders — plus the field-definition citation. (§2.2, §3.3)
11. **Demand-side profiles** for Boudreaux, Somppi, Cappello, S. Ray, and JABYAD7012-resolved; then their
    other solicitations. (§2.2)
12. **Response AI beneficial ownership** — keep it, but demote it from #2 to here. It is a good scoop and
    the Global Emergency Response twin is real, but it is one firm, and the ORR crossover is bigger.
13. **Lobbying sweep across all 32 awardees**, starting from the verified Lemoine/Cornerstone hit, plus
    the Capgemini SE European-disclosure angle. (§1.6, §1.5)
14. **State court + PPP capacity work** on the cohort, with strict entity pinning. (§1.8, §1.10)
15. **Gravitas non-renewal** as the natural experiment; **the losing-bidder / pool-formation question**
    as the buy-side test of coordinated bidding. (§2.9, §2.8)

### Deprioritize or drop

- **Drop: proving lateral links among the newcomers by inspecting each one.** WAVE2's central hypothesis is
  worth testing but the current approach — 32 separate entity workups hoping overlaps emerge — is
  expensive and low-yield. Two mechanical tests do the same job better: shared analytics/GTM IDs and cert
  SANs across their domains (§1.9), and the pool-formation record on the buy side (§2.8). If neither
  shows anything, accept "independently spawned" and move on.
- **Drop: the Wisconsin satellite shells** (DC Gravity, SDNexus DataOps) as a priority. The cert evidence
  shows SDNexus is a real product with a real engineering estate; the surplus-property business is
  unrelated to ICE; and "two more LLCs at the same house with no federal awards" is a curiosity, not a
  fact about this program. Keep Behm's registered-agent role (already confirmed) and move on.
- **Drop: Cyber Intel Service's new Washington branch, the Casper WY origin, Roberto Guercini's identity.**
  Interesting, unconnected to the money. The one exception: `shadowsecrecy.com` (§1.9) is a five-minute
  check because it is a genuine shared-control signal.
- **Deprioritize: re-verifying ceilings and per-firm figures.** Done, matched to the dollar.
- **Deprioritize: the "$27.3M" reconciliation** as a standalone task. §0.3 supersedes it — the
  pre-competition instruments explain the neighbourhood, and the exact figure came from a discredited
  finding. Note it and stop.
- **Deprioritize: blockchain, sanctions/PEP, ICIJ, FinCEN, patents-beyond-the-null.** Cheap enough to run
  as a batch for completeness, but I would not spend an agent on any of them. The null on USPTO is already
  useful; the rest will be nulls that tell you nothing.

---

## APPENDIX A — Verification status of every claim in this review

| § | Claim | Status | Source |
|---|---|---|---|
| 0.1 | 19 UAC task orders, $86,822,317.14 | **[V]** | USASpending `spending_by_award`, keyword "safety verification", 2026 |
| 0.2 | 18 UAC IDIQs incl. SOSi $559,578,059.16 / Baptiste $580,475,000 | **[V]** | USASpending `awards/CONT_IDV_70CDCR26D00000046_7012`, `…047_7012` |
| 0.3 | Four pre-competition instruments incl. GRG GSA order + B.I. ISAP mod | **[V]** | `spending_by_transaction`, keyword "skip tracing" |
| 0.4 | 18 offers / 18 awards (UAC); 51 offers / 14 (skip trace) | **[V]** | USASpending IDV records D30, D45, D46, D47, D6, D17 |
| 1.1 | geo-group profile with 439 artifacts | **[V]** | `investigations/geo-group/reports/` |
| 1.2 | transaction-level keyword endpoint works | **[V]** | live POST |
| 1.3 | DHS 561611 history = background investigations | **[V]** | `spending_by_award` + `naics_codes:["561611"]`, DHS, FY18–FY25 |
| 1.4 | pre-2025 skip tracing = 561450 data products | **[V]** | keyword sweep 2005–2026 |
| 1.5 | GEO 10-K/8-K skip-tracing language | **[V]** | `query_edgar.py search` + `read --find` |
| 1.6 | Lemoine ↔ Cornerstone $220K, HS/Disaster issue codes | **[V]** | `query_lobbying.py client "The Lemoine Company"` |
| 1.7 | Applied Intellect 90ZU0581 $84.5M ORR; Baptiste ORR shelter; $2.25B HS/PRS class | **[V]** | `spending_by_award`, assistance types 02–05 |
| 1.8 | PPP job counts (Origin 1, Applied Intellect 20, Baptiste 42→71) | **[V]** | `query_ppp.py sql` |
| 1.9 | sdnexus 237 certs / brokerbuster subdomain; `cyberintelservice.com.shadowsecrecy.com` | **[V]** | `query_crtsh.py --subdomains`; `query_shodan.py dns-resolve` |
| 1.10 | CourtListener: 2 hits across UAC cohort | **[V]** | `query_courtlistener.py party` |
| 1.11 | state PI licensing registries | **[U]** | no repo tool; URLs named |
| 1.12 | MuckRock creds fail; DocumentCloud auth 401s but works anon; DC 4380794; no USPTO patents; 2 FR SORN notices in window | **[V]** | respective tools |
| 2.2 | HigherGov `people --email` returns full contact record | **[V]** | Jason Boudreaux, ERO, last seen 2026-06-04 |
| 2.3 | per-case spread $1,056–$11,965 | **[V]** arithmetic on **[V]** figures; denominator **[U]** | task-order amounts ÷ 1,000 |
| — | FEC: no donations by Behm/Guercini/Hodrick/Visnic/Swearingen/Kraemer | **[V]**, fuzzy | `query_fec.py donor` (tool matching is loose — confirm with `--employer`) |
| — | Subawards: none reported for GRG/Response AI/Septimo/Baptiste; Caduceus ← Booz Allen $7.68M | **[V]** | `query_usaspending.py subawards` |

## APPENDIX B — Tooling gaps this case exposed

1. No USASpending **transaction-level / NAICS / PSC** keyword search wrapper. *(highest value)*
2. No **FPDS-NG ATOM** tool (already in the plan).
3. No **trademark** tool (USPTO TSDR / tmsearch) — a real gap for firms whose claims are marketing.
4. No **state occupational-licensing** tool (PI/security/bail recovery).
5. No **state court** tools beyond NYSCEF — WCCA (WI), Texas county clerks, Virginia OCIS are all free.
6. No **GAO bid-protest docket** tool; the plan's "no protest found" negative rests on web search.
7. `query_highergov.py opportunity` cannot filter by contact/agency/date — blocks demand-side profiling.
8. **MuckRock credentials broken**; **DocumentCloud auth 401s** (falls back to anonymous, so it is easy
   to miss).
9. `query_fec.py donor` name matching is loose and unsorted — easy to misread a null as a null.
10. `query_ppp.py search` prints a tail-only summary; use `sql` for anything load-bearing.
