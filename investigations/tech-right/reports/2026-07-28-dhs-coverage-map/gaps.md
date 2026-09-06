# DHS contracting coverage gaps

**Coverage window:** 2025-01-20 through 2026-07-28  
**Search cutoff/access time:** 2026-07-28 22:30 EDT

## Bottom line

| Unreported candidate | Verdict | Why |
|---|---|---|
| ICE UAC Safety Verification Initiative, 70CDCR26R00000015 | **PARTIALLY REPORTED** | Project Salt Box reported the 18-company/$20B-plus portfolio and one anomalous award; earlier Project Salt Box and Guardian pieces covered the RFP and MVM. No reviewed publication gave the exact PIID range, exact ceiling/obligations, nineteen-order reconciliation, or 18-offers-to-18-awards result. |
| ICE skip tracing, 26-SOL-DCR-01; B.I./ISAP V | **PARTIALLY REPORTED** | Intercept, WIRED, 404 Media, Scripps, and Washington Post reported the program, vendors, incentives, and large potential values. The separate approximately $86.4M sole-source B.I. buy inside ISAP V and Amendment 2 ceiling deletion were not found. |
| Compass United, approximately $1.57B ICE child-visit ceiling | **NOT FOUND** | Exact-name searches produced award databases and unrelated results, not journalism or an oversight report. The company is unnamed in the Project Salt Box portfolio story. |
| FPDS single-official create-and-approve workflow pattern | **NOT FOUND** | Exact user-ID and field-name searches produced no relevant journalism, NGO report, or oversight publication. |

## Candidate 1 — UAC Safety Verification Initiative

### Verdict: PARTIALLY REPORTED

The program and even the top-line portfolio are public:

- **Project Salt Box, 2026-03-12/26:** [ICE Turns to Private Industry to Track Down 100,000 Unaccompanied Children](https://www.projectsaltbox.com/p/ice-turns-to-private-industry-to) analyzed the RFP, 100,000 initial cases, commercial-data searching, in-person visits, 1,000-case batching, speed incentives, and pre-existing MVM work.
- **The Guardian, 2026-05-02:** [‘Deplorable’: ICE hires firm accused of ‘torture’ to track down undocumented children](https://www.theguardian.com/us-news/2026/may/02/ice-contracter-torture-allegations-undocumented-children) reported an interim MVM contract and stated that eighteen firms had offered. Price and case volume were redacted; the story presented MVM as the firm with the necessary field infrastructure.
- **Project Salt Box, 2026-06-23:** [ICE awards nearly $200 million in migrant-child location work to a Virginia firm with no prior federal contracts](https://www.projectsaltbox.com/p/ice-awards-nearly-200-million-in) reported that ICE awarded open-ended agreements to **18 companies** with combined potential value **above $20 billion**. It profiled **Savvy Professor LLC/SIVS**, distinguishing its roughly **$1.6B ceiling**, nearly **$200M order estimate**, and approximately **$4.7M then obligated**.

### Still unreported in the reviewed coverage

- solicitation number **70CDCR26R00000015** printed in the narrative;
- the complete base-IDIQ sequence **70CDCR26D00000030–70CDCR26D00000047**;
- the exact reconciled ceiling **$20,583,928,204** and **$86,822,317** obligated;
- all nineteen delivery orders and their obligation dates;
- the key competition result: **18 offers → 18 awards**;
- a full vendor table including **Response AI Solutions, National Protective Services, SOSi, MVM, Compass United**, and cross-program firms;
- the contracting-officer create/modify/approve metadata.

The Guardian’s “eighteen firms offered” line refers to the interim MVM justification and does not establish that the later competition awarded every offeror. Project Salt Box establishes eighteen eventual companies but does not make the offers-to-awards comparison.

Federal News Network did cover a useful **different-vehicle precedent** on 2025-12-05: winning vendor Active Deployment Systems challenged an ICE detention IDIQ for allegedly awarding too many contracts, and the Court of Federal Claims rejected the post-award challenge as untimely. That establishes that ICE’s broad-award IDIQ design has received some legal/press scrutiny, but it does not identify or analyze SVI’s 18-offers-to-18-awards result.

### Exact checks

- Google News RSS:
  - `"70CDCR26R00000015" after:2025-01-20 before:2026-07-29` → **0 items**
  - `"UAC Safety Verification Initiative" ICE after:2025-01-20 before:2026-07-29` → **10 items**, of which the Guardian and Project Salt Box were procurement-relevant
  - `"18 companies" "wellness checks" ICE after:2025-01-20 before:2026-07-29` → Project Salt Box award story found through web search
- Google News endpoint used:

```text
https://news.google.com/rss/search?q=%2270CDCR26R00000015%22+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
https://news.google.com/rss/search?q=%22UAC+Safety+Verification+Initiative%22+ICE+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
```

- General web searches:
  - `ICE "20 billion" "unaccompanied" contractors June 2026 safety verification`
  - `ICE "18 companies" "wellness checks" children contract June 2026`
  - `ICE "70CDCR26D000000" child welfare contractor`
  - `ICE "Safety Verification Initiative" awards June 2026 contractors`
  - `"Response AI Solutions" "Safety Verification" ICE`
- DocumentCloud: `uv run python tools/query_documentcloud.py search '"70CDCR26R00000015"' --output …` → **0**
- MuckRock: `uv run python tools/query_muckrock.py search '"70CDCR26R00000015"' --output …` → **0**
- GDELT DOC 2.0 query for `"safety verification" ICE`, limited to its rolling three-month window, returned HTTP 429/non-JSON during the shared rate-limit period. It is **not** counted as a negative result; Google News and direct web search supplied the relevant hits.

## Candidate 2 — ICE skip tracing, B.I. Incorporated, and ISAP V

### Verdict: PARTIALLY REPORTED

The main skip-tracing program is well reported:

- **The Intercept, 2025-10-31:** pre-award case bundles, commercial-data searches, field verification, and speed incentives.
- **WIRED, 2025-11-25:** cap deletion, potential per-vendor value, guaranteed minimum, and recurring monthly volumes.
- **404 Media, 2025-12-18:** AI Solutions 87 and its “bounty hunter” automation.
- **The Intercept, 2025-12-19 and 2025-12-23:** B.I./GEO’s award and ten early vendors.
- **Scripps News, 2026-01-28:** thirteen-firm/$1.2B snapshot and small/inexperienced vendors.
- **Washington Post, 2026-01-30:** the mature **fourteen-vendor** program, Capgemini’s initial action/ceiling, the roughly 1.5-million-person target pool, photographs, and incentives.

### Still unreported in the reviewed coverage

- a clean, reproducible crosswalk from **solicitation 26-SOL-DCR-01** to all fourteen IDIQs;
- the exact **$1,442,909,640 combined ceiling** and **$19,032,607 obligated** snapshot from the wave-3 brief;
- **51 offers → 14 awards** and the implication for competition;
- dormant/no-new-order status after 2026-05-14;
- the earlier **approximately $86.4M sole-source skip-tracing purchase inside B.I. Incorporated’s ISAP V contract**;
- **ISAP V Amendment 2’s ceiling deletion**, its rationale, and whether it expanded ordering flexibility;
- the procurement-workflow concentration around user **JABYAD7012**.

The Intercept’s B.I. piece covers a roughly **$1.6M paid / $121M potential** skip-tracing award in the new program. That is not the earlier approximately $86.4M ISAP V sole-source action.

### Exact checks

- Google News RSS:
  - `"26-SOL-DCR-01" after:2025-01-20 before:2026-07-29` → **0 items**
  - `"ICE skip tracing" after:2025-01-20 before:2026-07-29` → **4 indexed items**; broader “bounty hunter” searches were needed to recover the principal coverage
  - `"ISAP V" "B.I. Incorporated" after:2025-01-20 before:2026-07-29` → **0 items**
- Google News endpoint used:

```text
https://news.google.com/rss/search?q=%2226-SOL-DCR-01%22+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
https://news.google.com/rss/search?q=%22ICE+skip+tracing%22+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
https://news.google.com/rss/search?q=%22ISAP+V%22+%22B.I.+Incorporated%22+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
```

- General web searches:
  - `ICE "skip tracing" ISAP V B.I. Incorporated`
  - `"B.I. Incorporated" "ISAP V" skip tracing`
  - `"ISAP V" "Amendment 2" ceiling ICE`
  - `ICE B.I. Incorporated sole source skip tracing 86.4 million`
  - `"26-SOL-DCR-01" ICE`
- DocumentCloud: exact `"26-SOL-DCR-01"` → **0**
- MuckRock: exact `"26-SOL-DCR-01"` → **0**
- GDELT query `"skip tracing" ICE` hit the same HTTP 429/non-JSON limit and is not treated as a negative.

## Candidate 3 — Compass United

### Verdict: NOT FOUND

The reviewed award databases show **Compass United** as awardee on **70CDCR26D00000033**, with a potential base-IDIQ ceiling of approximately **$1.568 billion** for SVI child-location/wellness work. That is primary award data, not press coverage.

Project Salt Box’s 2026-06-23 story reports the aggregate eighteen-company portfolio but does **not** name Compass United. AP’s 2026-07-06 Alexandria story names **Compass Connections**, not Compass United, and concerns a Louisiana facility, not the SVI IDIQ. No reviewed story traced Compass United to the BCFS/Compass Connections/ORR network.

### Exact checks

- Google News RSS:
  - `"Compass United" ICE after:2025-01-20 before:2026-07-29` → **0 items**
- Exact endpoint:

```text
https://news.google.com/rss/search?q=%22Compass+United%22+ICE+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
```

- General web searches:
  - `"Compass United" ICE contract`
  - `"Compass United" "70CDCR26D00000033"`
  - `"Compass United" child visits BCFS`
  - `"Compass United" "Safety Verification Initiative"`
  - `"70CDCR26D00000033" journalism`
- GDELT DOC 2.0:

```text
https://api.gdeltproject.org/api/v2/doc/doc?query=%22Compass%20United%22%20ICE&mode=artlist&maxrecords=250&format=json&startdatetime=20260428000000&enddatetime=20260728235959
```

  Result: **2 items, both irrelevant** (one lunar-resources item and one Iran-vessels item).
- DocumentCloud: `"Compass United"` → **4 records**, all irrelevant co-occurrences and none about DHS/ICE.
- MuckRock local index: `"Compass United"` → **0**.
- Direct outlet/domain searches across ProPublica, Washington Post, AP, Reuters, NOTUS, Intercept, POGO, Miami Herald, Government Executive, Federal News Network, and Defense One returned no relevant coverage.

## Candidate 4 — FPDS creator/approver workflow patterns

### Verdict: NOT FOUND

No journalism or oversight publication was found using award-workflow metadata to show one official creating/modifying and approving a concentrated set of ICE awards. The wave-3 brief’s examples — including **JABYAD7012** on thirteen of fourteen skip-tracing base delivery orders — appear to be unclaimed.

This is a workflow anomaly, not by itself evidence of illegality. A publishable story would need to explain the normal FPDS/contract-writing-system population rules, distinguish a data-entry user from the warranted contracting officer, test whether “created by” and “approved by” fields reflect separate real-world approvals, and compare with a baseline.

### Exact checks

- Google News RSS:
  - `"JABYAD7012" after:2025-01-20 before:2026-07-29` → **0 items**
  - `"Created By" "Approved By" FPDS ICE after:2025-01-20 before:2026-07-29` → **0 items**
- Exact endpoints:

```text
https://news.google.com/rss/search?q=%22JABYAD7012%22+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
https://news.google.com/rss/search?q=%22Created+By%22+%22Approved+By%22+FPDS+ICE+after%3A2025-01-20+before%3A2026-07-29&hl=en-US&gl=US&ceid=US%3Aen
```

- General web searches:
  - `journalist FPDS "approved by" contracting officer DHS awards`
  - `DHS contracts "Created By" "Approved By" FPDS`
  - `ICE contracts single official created approved awards FPDS`
  - `"JABYAD7012"`
  - `FPDS contracting officer workflow pattern journalism`
- DocumentCloud: combinations of `FPDS`, `"Created By"`, `"Approved By"`, `ICE`, and `JABYAD7012` produced no relevant file.
- MuckRock: `JABYAD7012` and the field-name combinations produced **0 relevant records**.

## Coverage-domain negative and boundary ledger

These are the meaningful negatives after cataloging the positive stories. Result counts are raw index counts; they are not all relevant.

| Domain | Positive baseline | Negative/boundary result | Representative exact query |
|---|---|---|---|
| 1. Noem-linked spending | Ads, political vendors, Ashwood income, jets, and approval threshold are heavily covered. Google News broad query returned up to 100 items. | No complete recruiting-vs-self-deportation ad ledger, subcontract invoices, commission rates, or campaign performance. No documentary link from Ashwood income to a particular award. | `Noem DHS ad contract vendor People Who Think recruiting after:2025-01-20 before:2026-07-29` |
| 2. Lewandowski | SGE status, $100K gate, routing sheets, alleged payment requests, and OIG probe are covered; broad query returned 11 items. | No public 278e, complete client/recusal list, or reviewed coverage naming Bossie/Turnberry as a paying DHS-vendor link. | `Lewandowski DHS contract vendor client Turnberry Bossie after:2025-01-20 before:2026-07-29` |
| 3. Detention surge | Fort Bliss, GEO, CoreCivic, Deployed Resources, Acquisition Logistics, Amentum, and letter contracts are covered; broad query returned 86 items. | No normalized per-bed/day portfolio or common metric for MTC, LaSalle, Target Hospitality, Akima, Loyal Source, and SLSCO. | `ICE detention contract GEO CoreCivic Fort Bliss letter contract after:2025-01-20 before:2026-07-29` |
| 4. State facilities | Florida vendor/donor and FEMA-reimbursement reporting is extensive; broad query returned 77 items. Louisiana has some cost reporting. | No cross-state reimbursement/IGSA comparison; Indiana and Nebraska coverage is local and largely facility-level. | `"Alligator Alcatraz" contractor donor FEMA after:2025-01-20 before:2026-07-29` |
| 5. Deportation logistics | CSI, Avelo, GlobalX, Salus, Daedalus, and protests are covered; broad query returned 42 items. | No broker→carrier→aircraft→guard/medical subcontract map or comparable per-flight costs. Acquisition Logistics coverage found was detention/Fort Bliss, not flight brokerage. | `ICE deportation flight contract CSI Avelo Salus protest after:2025-01-20 before:2026-07-29` |
| 6. Tech/surveillance | Palantir, ImmigrationOS, Bi2, TRSS/CLEAR, social monitoring, and skip tracing are covered; broad query returned 50 items. | Earlier B.I./ISAP V sole-source action and Amendment 2 were not found; no unified vendor-overlap map. | `ICE surveillance contract Palantir biometrics location data skip tracing after:2025-01-20 before:2026-07-29` |
| 7. Border wall | Fisher/Barnard concentration and political ties are covered; broad query returned 38 items. | No normalized per-mile/terrain/type/change-order comparison and no workflow-field analysis. | `border wall contract Fisher Sand Gravel per mile after:2025-01-20 before:2026-07-29` |
| 8. Guardrails/process | CRCL/OIDO gutting, Cuffari/OIG issues, specific protests, and $9B less-than-full-competition total are covered; broad query returned 23 items. | No DHS-specific protest-volume/time-series story, contract-type distribution, or corrective-action tracker. Government-wide FY2025 protest count is not a substitute. | `DHS OIG Cuffari contract Noem Lewandowski competition GAO protest after:2025-01-20 before:2026-07-29` |
| 9. DOJ/GAO/OIG actions | Zephyr Aviation FCA settlement, Praetorian Shield settlement, Fort Bliss GAO audit, and Noem/Lewandowski OIG inquiry found. | No targeted DOJ settlement/indictment/debarment found for GEO, CoreCivic, Salus, Palantir, CSI, MVM, SOSi, or the other headline surge vendors in the local 2025–2026 release corpus or direct web sweep. | local corpus: `DHS contractor`; `ICE contractor`; `Homeland Security False Claims Act`; `Zephyr Aviation`; `Praetorian Shield`; web: `DHS vendor suspension debarment ICE contractor 2025 2026` |
| 10. UAC/ORR edge | Welfare checks, MVM, SVI RFP, Savvy/SIVS, Compass Connections' Louisiana facility role, and TRSS/CLEAR are covered. | Compass United and the full 18-award vendor/network table are not. Google News broad ORR-vendor query returned 0. | `ORR contractor MVM BCFS Compass Connections after:2025-01-20 before:2026-07-29` |

## Oversight letters and attachments worth harvesting

These are coverage sources or evidence leads, not independent proof of the underlying allegations:

- **Garcia, 2025-09-05:** OGE disclosure demand; press page links the signed letter:  
  https://oversightdemocrats.house.gov/news/press-releases/ranking-member-robert-garcia-demands-public-release-corey-lewandowskis
- **Welch and colleagues, 2025-11-19:** request for DHS OIG review of the ad campaign and Noem-linked subcontracting; the press page/PDF should be retained with attachments.
- **Joint House/Senate OIG letter, March 2026:**  
  https://oversightdemocrats.house.gov/imo/media/doc/joint_letter_to_dhs_oig_re_noem_lewandowski.pdf
- **Blumenthal and Welch, 2026-03-26:** asks Secretary Mullin for Lewandowski contract-role records and references the March 3 Stackhouse memorandum:  
  https://www.blumenthal.senate.gov/newsroom/press/release/blumenthal-and-welch-demand-answers-from-secretary-mullin-over-lewandowoskis-role-in-dhs-contracts
- **Senate Finance, 2026-05-12, ORR letter:**  
  https://www.finance.senate.gov/imo/media/doc/051226_letter_to_hhs_on_orr.pdf
- **Senate Finance, 2026-06-03, Compass Connections/Alexandria letter:**  
  https://www.finance.senate.gov/imo/media/doc/060326_letter_to_compass_connections_re__alexandria_la_facility.pdf

## Corpus and endpoint ledger

### Google News RSS systematic sweep

All queries used the same endpoint and date limits:

```text
https://news.google.com/rss/search?q=QUERY+after:2025-01-20+before:2026-07-29&hl=en-US&gl=US&ceid=US:en
```

Raw item counts from the principal query set:

- `"70CDCR26R00000015"` — 0
- `"UAC Safety Verification Initiative" ICE` — 10
- `"26-SOL-DCR-01"` — 0
- `"ICE skip tracing"` — 4
- `"ISAP V" "B.I. Incorporated"` — 0
- `"Compass United" ICE` — 0
- `"JABYAD7012"` — 0
- `"Created By" "Approved By" FPDS ICE` — 0
- `Noem DHS ad contract vendor People Who Think recruiting` — 100 (feed cap)
- `Lewandowski DHS contract vendor client Turnberry Bossie` — 11
- `ICE detention contract GEO CoreCivic Fort Bliss letter contract` — 86
- `"Alligator Alcatraz" contractor donor FEMA` — 77
- `ICE deportation flight contract CSI Avelo Salus protest` — 42
- `ICE surveillance contract Palantir biometrics location data skip tracing` — 50
- `border wall contract Fisher Sand Gravel per mile` — 38
- `DHS OIG Cuffari contract Noem Lewandowski competition GAO protest` — 23
- `ORR contractor MVM BCFS Compass Connections` — 0

### GDELT DOC 2.0

GDELT’s DOC endpoint was queried only inside the API’s rolling three-month availability window:

```text
https://api.gdeltproject.org/api/v2/doc/doc?query=QUERY&mode=artlist&maxrecords=250&format=json&startdatetime=20260428000000&enddatetime=20260728235959
```

- `"Compass United" ICE` — 2, both irrelevant.
- `"Alligator Alcatraz" contractor` — 22, with relevant Florida coverage.
- `"safety verification" ICE`, `"skip tracing" ICE`, `Noem contract Lewandowski`, and `ICE detention contract` — shared HTTP 429/non-JSON rate-limit responses despite spacing. These attempts were not used as negative evidence; Google News/direct searches were the fallback.

### DocumentCloud and MuckRock

Exact searches run through the repository tools:

- `70CDCR26R00000015` — DocumentCloud 0; MuckRock 0
- `26-SOL-DCR-01` — DocumentCloud 0; MuckRock 0
- `Compass United` — DocumentCloud 4 irrelevant; MuckRock 0
- `Corey Lewandowski DHS contracts` — DocumentCloud returned older/mixed documents, no undiscovered 2025–2026 award table; MuckRock 0 relevant
- `Alligator Alcatraz contract` — DocumentCloud returned relevant handbooks, estimates, and Senate material; MuckRock local index 0
- `Acquisition Logistics ICE` — DocumentCloud results were mostly phrase-noise; MuckRock 0

DocumentCloud’s authenticated request returned 401 and the tool fell back to anonymous search. This is a coverage limitation, not a substantive negative.

### Government release corpus

Read-only searches against `datasets/government_releases.db` through `tools/government_release_corpus.py`:

- `DHS contractor`
- `ICE contractor`
- `Homeland Security False Claims Act`
- `Zephyr Aviation`
- `Praetorian Shield`

Material DHS-vendor hits in the period were the Zephyr Aviation and Praetorian Shield settlements cataloged above. A GSA bribery matter was excluded as outside DHS.

Additional direct searches — `DHS vendor suspension debarment ICE contractor 2025 2026`, `site:sam.gov DHS ICE contractor debarred 2025 2026`, `site:justice.gov DHS contractor indictment fraud 2025 2026 ICE vendor`, and `site:oig.dhs.gov contractor fraud procurement 2025 2026` — returned general FAR material and unrelated agency/criminal matters, not a suspension, debarment, or indictment of the headline DHS surge vendors.

## Structural angles that appear untouched

1. **Ceiling-to-obligation forensics.** A single table separating base IDIQ ceilings, delivery-order potential values, current award amounts, obligations, outlays, and cancellations across SVI, skip tracing, detention, and flights.
2. **The all-offerors-win SVI competition.** Why 18 offers produced 18 awards; whether qualification gates, guaranteed minima, or ordering design made the competition nominal; and how prices were evaluated when non-price factors dominated.
3. **Workflow concentration.** Contract-writing-system user IDs and “created/modified/approved” fields across award families, compared with a component baseline and validated against warrants/delegations.
4. **Vendor overlap graph.** GEO/B.I., SOSi, MVM, Response AI, National Protective Services, Palantir/data vendors, detention vendors, and ORR-linked organizations across surveillance, child visits, transport, detention, and monitoring.
5. **Compass United’s lineage and capacity.** Ownership, managers, address, related Compass/BCFS entities, prior child-welfare work, licenses, staffing, subcontractors, and how it supports a $1.57B ceiling.
6. **B.I./ISAP V amendment history.** The approximately $86.4M sole-source skip-tracing addition, Amendment 2 ceiling deletion, contemporaneous justification, and relationship to the later fourteen-vendor competition.
7. **Normalized detention economics.** Per available/occupied bed-day, mobilization, transport, health care, guard staffing, vacancy guarantee, change orders, and termination costs across every major operator and soft-sided site.
8. **State reimbursement comparison.** IGSAs, FEMA or other account authority, state cash-flow exposure, rejected costs, political donations, and vendor payment timing beyond Florida.
9. **Deportation supply chain.** Prime broker, operating carrier, aircraft owner, crew, guards, medical support, route, seat utilization, deadhead legs, and cost per completed removal.
10. **DHS-wide competition and protest dashboard.** Less-than-full-competition dollars by component/office, bridge and letter contracts, solicitation periods, protest outcomes, corrective action, and repeat justifications.
11. **Near-threshold actions.** Whether the cluster of $99,999.xx awards reflects task scoping, system rounding, or intentional avoidance of Noem’s review gate; no reviewed article tested the transactions end-to-end.
12. **Oversight attrition as procurement risk.** Whether dissolution of acquisition oversight, CRCL/OIDO reductions, and Cuffari’s disputed OIG posture correlate with faster awards, weaker inspections, cost growth, or fewer corrective actions.

## Caution for the next phase

The gaps above are novelty opportunities, not allegations. The most promising findings — all-offerors-win, single-user workflows, near-threshold awards, and ceiling deletions — require comparison groups and primary acquisition files before they can support a fraud, favoritism, or control-breakdown claim.
