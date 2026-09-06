# ProPublica Evidence Ontology — Finding Types, Evidence Sources, Acquisition, Provenance

Bottom-up taxonomies re-derived from 107 coded wave-1 stories (8 flagship clusters, reports 01–08 in
`research/patterns/_intake/propublica/`), the methodology corpus (report-09), and the empirical corpus census
(report-10). Wave-2 clusters (reports 11–16) reconcile into the same structure — see §8.

**Derivation rules** (the de-biasing discipline this project was run under):
- The starting taxonomies given to wave-1 coding agents were *hypotheses*. Categories below exist only if
  ≥2 independently cited stories support them; "core" requires ≥3 stories and ≥2 clusters.
- Seeded categories with <2 story support are **retired** (§6), with disposition notes.
- Categories the coding agents invented that recur are **emergent** (§7).
- Wave-2 agents received *no* taxonomy at all (free-form tagging); their tag streams are reconciled in §8.
- Frequencies are story-level counts from the coded entries (`_intake/propublica/tally/`), cross-checked
  against each report's own synthesis tables. Counts are approximate at family boundaries (merges noted inline);
  stories claimed by two clusters (e.g., RealPage, Insult to Injury, TurboTax, Trump inaugural) are flagged
  where they inflate a family.

---

## 1. Finding-type taxonomy

What ProPublica investigations *find*, as families of misconduct/failure. Three strata: core cross-domain
types, domain dialects (heavy use inside one beat), and emergent types (§7).

### 1.1 Core types (≥3 stories, ≥2 clusters)

| Finding type | Stories | Clusters | What it is |
|---|---|---|---|
| extraction-from-captive-population | 24 | 6 | Revenue engineered from people who cannot exit: patients, debtors, prisoners, tenants, temp workers, benefit claimants |
| institutional-coverup / records-suppression | 21 | 6 | Records withheld, sealed, destroyed, or never created to conceal conduct; includes secrecy statutes as active infrastructure |
| fraud-enablement-by-design | 19 | 6 | Program/product design that invites and rewards fraud: absent verification, per-transaction fees, self-declared eligibility, non-enforcement |
| regulatory-capture (family: revolving-door, lobbying-to-preserve-rents, capture-by-defunding, self-regulation) | 16 | 5 | The referee works for the players — by personnel, by statute, by starvation, or by design |
| two-books-asymmetry | 16 | 7 | The same fact stated differently to audiences with opposing incentives (also a signature; as a *finding* it is the misrepresentation itself) |
| disparate-impact-by-race-or-geography | 14 | 3 | Burden or harm concentrating on a protected class or place once denominators are built |
| algorithmic-or-systematic-denial | 12 | 5 | Industrialized adverse decisions: batch denials, scoring gates, quota-driven adjudication |
| charity-mission-inversion (incl. nonprofit-mission-inversion) | 11 | 5 | Tax-exempt entities operating against their beneficiary class or as political/profit vehicles |
| undisclosed-benefit-to-official | 9 | 2 | Gifts, travel, tuition, transactions flowing to officials outside their disclosure filings |
| influence-laundering-via-intermediaries | 9 | 3 | Money/pressure routed through cutouts (c4s, LLCs, advocacy fronts, trusts) to obscure the principal |
| preferential-carve-out | 8 | 4 | Rules, boundaries, or exemptions drawn to fit one beneficiary (statutory eight words; OZ tract lines; hospitality exemptions) |
| self-dealing / related-party | 7 | 5 | Insider-linked vendors, captive subsidiaries, officer-fee arrangements |
| statistical-outlier-practitioner | 10 | 3 | The individual professional/institution whose volume or pattern is peer-impossible |
| dark-pattern / consumer-deception | 5 | 2 | Interface and marketing machinery steering people away from entitlements or into fees |
| concentrated-harm-hotspot | 5 | 2 | Geographic harm clusters (audit counties, toxic blocks) invisible in official aggregates |

### 1.2 Domain dialects (≥3 stories, one cluster — transferable but domain-shaped)

- **wealth-defense-technique** (7, tax): the engineering family — realization-avoidance, paper-loss-manufacturing,
  income-character-conversion, valuation-arbitrage, GRAT-class estate bypasses.
- **donor-anonymization-technique** (7, dark money): the mirror family — c4 layering, ephemeral targeted ads,
  anonymity-as-product.
- **access-brokerage** (5, judicial): officials as fundraising assets; brokers wiring benefactors to bench.
- **due-process-bypass** (5, criminal justice): adjudication without the required process — plea-before-evidence,
  ex parte machinery, civil instruments doing criminal work.
- **anomalous-vendor** (4, gov-spending): no-history vendors landing emergency awards (see entity-genealogy
  signature card).
- **platform-complicity-by-design** (4, tech): the platform's architecture is the discrimination/deception
  delivery vehicle.
- **conduit-network** (3, dark money) and **recusal-failure** (3, judicial): self-explanatory.
- **paper-loss-manufacturing** (4, tax; emergent within wave 1): engineered tax losses against real-world profit.

### 1.3 Structural observation

The core types are not 15 independent categories; they compose. The corpus's repeated composite is:
**captive population + extraction design + enforcement collapse + records suppression** (hospice, dialysis,
assisted living, court debt, temp labor, nursing chains). When one component is confirmed, the platform should
actively test for the other three — in the coded stories they co-occur far more often than chance.

---

## 2. Evidence-source taxonomy

Consolidates report-09's bottom-up 14-category taxonomy with the 8 per-cluster frequency tables. Corpus-level
prevalence (107 wave-1 stories): **interviews incl. insiders 62; court/docket records 33; leaked or insider
documents 25; FOIA/records-law output 19** (classification overlap at family boundaries is real — a FOIA'd
administrative ledger counts in both microdata and FOIA rows of per-cluster tables).

| # | Class | Prevalence | Notes / exemplar systems |
|---|---|---|---|
| 1 | Administrative claims & payment microdata | Dominant | Medicare Part B/D, inpatient claims, ticket/citation ledgers, SBA loan-level, FPDS/USASpending |
| 2 | Mandated disclosure filings | Dominant | 990 family, FEC/state campaign finance, FCC political files, lobbying, pharma payments, financial disclosures |
| 3 | Regulatory inspection & enforcement records | Dominant | CMS surveys/deficiencies, FSIS tests, state licensure discipline, inspection scores |
| 4 | Court & docket records (incl. litigation-derived discovery exhibits) | 33/107 | Bulk local civil dockets; PACER/RECAP; discovery as rulebook source; bankruptcies as archives |
| 5 | Insider/staff human networks | 62/107 incl. all interviews | Service staff (pilots, caterers, lodge staff), ex-employees, franchisees, line adjudicators — the differentiating layer over open records |
| 6 | Leaked / whistleblower datasets & documents | 25/107 | IRS microdata, meth-house files, internal decks; **doctrine: leaks establish intent or serve as index — never scale; every claim re-anchored to an independently generated record** |
| 7 | FOIA / records-law output (incl. documented refusals as evidence) | 19/107+ | Row-level requests, drafting files, security-detail logistics, complaint corpora |
| 8 | Agency internal/operational databases | Common | Gang DBs, CCRB complaints, retest ledgers, personnel files — FOIA or repeal-window acquisitions |
| 9 | Government models & geospatial risk products | Occasional, high-impact | EPA RSEI, FEMA maps, Landsat series — run at full resolution (see dormant-model card) |
| 10 | Algorithmic outputs obtained for audit | Occasional, flagship | COMPAS scores via FOIA; purchased insurance quotes; the government's copy of proprietary outputs |
| 11 | Crowd-constructed cohorts & incident registries | Common, differentiating | Lost Mothers, Documenting Hate, Electionland — the verified-crowd layer an agent platform lacks |
| 12 | Crowd-transcribed document corpora | Occasional | Free the Files ad-buy data |
| 13 | Scraped commercial/web data & subject's own artifacts | Common | Dollars for Docs v1, robots.txt/noindex forensics, earnings calls, vendor marketing |
| 14 | Purchased/partnered commercial datasets | Occasional | CoStar, ADP aggregate runs, Advertising Analytics, Quadrant quotes, Pharmashine |
| 15 | Corporate/state registries | Common | Alias resolution, officer succession, formation dating — the join glue in 5 clusters |
| 16 | Property/deed & county courthouse records | Common | Parcel joins, heirs'-property chains, valuation ground truth |
| 17 | Official statistics & watchdog corpora (GAO/IG/NTSB) | Common | Carry whole stories without leaks (IRS Data Books); the public warning layer before disasters |
| 18 | Field observation / physical verification | 12+ stories | "The universal closer" — site visits, auctions, counting deliverables |
| 19 | Statute/rule text used as data | 8+ | 50-state codifications, statutory-exemption-as-evidence, drafting-diff inputs |
| 20 | Archival collections & personnel directories | Occasional | Justices' papers as dated anchors; directory snapshots diffed over time |
| 21 | Photo/social OSINT & physical artifacts | Occasional | Geotagged posts, plane-spotter video, paintings, branded objects — manifest reconstruction inputs |
| 22 | Expert adjudication panels | 4+ (dark money) | Tax-law professors converting facts into legal significance pre-publication |
| 23 | Wealth/valuation reference lists | 3 (tax) | Forbes lists as the denominator nobody official publishes |
| 24 | Adopted orphan datasets & APIs | Occasional | Sunlight Congress API custody; stewardship as acquisition |

**Corroboration doctrine (stated across clusters):** never single-source; corroboration = *independent
generation process*, not repetition (three copies of one document are redundancy, not corroboration — identical
to this platform's evidence standard); open-data quantification first, insider confirmation second; constructed
evidence (probes, scrapes, purchases) is the strongest tier when the investigator controls collection end-to-end
and the subject's own system is the declarant.

---

## 3. Acquisition playbooks

Eight from the methodology corpus (report-09 §Acquisition, with triggers/steps/failure modes there) plus six
recurring moves observed in cluster reports:

1. **Bulk-FOIA the administrative dataset behind the individual harm story** — request the system, not the case.
2. **Run the regulator's own unused model at full resolution** and publish the map.
3. **Structured callout to assemble the cohort the agency won't name** (verified-crowd; human_action for us).
4. **Crowd-transcribe the disclosure regime that exists on paper but not as data.**
5. **Audit the algorithm with its adversary's own protocol** (their validation window, their definitions).
6. **Diff the live directory** to measure what the institution refuses to report.
7. **Adopt the orphaned civic dataset** and become its steward.
8. **Convert investigation exhaust into standing public infrastructure** (the Nonprofit-Explorer move; equivalent
   here: regenerable sidecar DBs with explicit vintage semantics).
9. **Secrecy-repeal arbitrage** — day-one archive requests when a confidentiality statute falls (50-a).
10. **Request the government's copy** of proprietary outputs (scores, quotes, formulas in agency hands).
11. **Settlement-mandated-disclosure harvest** — consent-decree reporting as structured data.
12. **Watchdog-intermediated documents** — standing brokers (Fix the Court, Documented) whose productions are
    citable primary records.
13. **Defunct-institution docket-mining** — bankruptcy/receivership exhibits as records archives.
14. **Custodian-run denominator** — negotiate an aggregate analysis run by the private chokepoint (ADP-class);
    on this platform, a human_action lead type, never silently substituted with a weaker proxy.

---

## 4. Provenance checklist (adopted from the methodology corpus, report-09 §Provenance)

Before promoting a data-derived finding: (1) source + vintage stated; (2) acquisition mode recorded — leaks
additionally require independent authentication; (3) population and denominator defended; (4) exclusions
enumerated with counts, re-checked for whether they could reverse the finding; (5) definitions borrowed from the
audited party's own standard where one exists; (6) linkage/classification error measured on a sample and
disclosed; (7) model choices and bias direction disclosed; (8) independent expert eyes before publication;
(9) subject response sought — "no surprises"; (10) replication artifact + correction path.

Mapping to platform practice: (1)(2) = evidence refs + claim-type discipline (exists); (3)(4)(6)(7) = no current
field — candidates for findings_tracker metadata; (9) = out of scope (no subject contact per ethics guidelines)
but its function (adversarial check before promotion) maps to review/dispute tooling; (10) = regenerable sidecar
+ corrections table (exists).

---

## 5. Detection-signature taxonomy (summary)

Full operational cards with mechanics, minimum data, tool mappings, failure modes, exemplars:
[detection-signatures.md](detection-signatures.md). Bottom-up frequency backbone (wave 1):

**Tier 1 (≥4 clusters):** two-books-diff (~28 uses / 8 clusters); silo-join-on-hard-identifier (~27 / 7–8);
denominator-construction (~25 / 8); temporal-correlation (~16 / 5–6); internal-rulebook-acquisition (~14 / 4);
**enforcement-gap-ratio (emergent, ~10 / 4)**; named-cohort-tracing (~10 / 4); constructed-corpus-liberation
(~10 / 5); outlier-in-microdata (~11 / 3–4).

**Tier 2 (2–3 clusters or ≥3 stories in one):** disclosure-gap-triangulation (6 / 1 — judicial specialist);
constructed-interaction-audit (~7 / 2); beneficiary-reverse-engineering (~7 / 3); policy-shadow-measurement
(~10 / 3, merges with enforcement-gap at the boundary — no standalone card; folded into cards 3/4/13);
dormant-public-model-operationalization (3 / 2–3); plaintiff-frequency-inversion (3 / 1); entity-genealogy
screens (4 / 2); statutory-parameter screens (2 core + 1 analog / 2–3); authority-validity-audit (3 / 1);
missingness-as-signal (~4 / 3); ground-truth-verification (~4 / 2); grant-chain-tracing (4 / 1 + pass-through
variants); composition-ratio screens (~5 / 2–3); subject-artifact-forensics (~6 uses, ~5 unique stories);
cross-jurisdiction-codification (3 / 2); captive-extraction composite (3 clusters);
guest-manifest-reconstruction (4 / 1).

---

## 6. Retired priors

Seeded categories that failed the ≥2-story bar, with disposition:

| Seeded category | Support | Disposition |
|---|---|---|
| **policy-erosion-across-jurisdictions** (finding type) | 1 story — and that story (workers' comp) was independently coded in the healthcare cluster as benefit-erosion-by-statute: one story, double-clustered | Retired as seeded name; the phenomenon lives as emergent **benefit-erosion-by-statute** with cross-jurisdiction-codification as its signature |
| **undisclosed-financial-conflict** (finding type) | 1 story (Dollars for Docs) | Merged into a broadened **undisclosed-influence-payment** family with undisclosed-benefit-to-official — same mechanics, professional vs official recipient |
| **warning-ignored-before-disaster** (finding type) | 1 story under the exact seeded label (7th Fleet); the adjacent heirs'-property entry carries a near-identical free-form tag ("warning-ignored (decades of USDA/academic documentation)") — the retirement is of the seeded *name*, with the phenomenon absorbed | Absorbed into the **warnings-ledger** variant of two-books-diff (the signature proved more real than the finding type) |
| **litigation-discovery-mining** (signature) | 0 uses as an analytic move | Reclassified: litigation records are a pervasive *evidence class* (~33/107 stories) — dockets are where rulebooks, depositions, and internal documents surface — but "mining discovery" never appeared as the move that surfaced a finding |
| **hotspot-mapping-from-model-data** (signature) | 3 stories / 2 clusters | Survived, but only barely, and only by merging with its stronger emergent reformulation **dormant-public-model-operationalization** — the seed name described the output; the data named the acquisition insight |
| **disclosure-gap-triangulation** (signature) | 6 stories / 1 cluster | *Not* retired (strong support) but demoted from presumed-generalist to **domain specialist**: seeded into 7 clusters, used in exactly one (officials with disclosure regimes). A caution against assuming flagship moves generalize |

Also instructive: 9 of 26 seeded finding types turned out to be **single-cluster dialects** (access-brokerage,
donor-anonymization, due-process-bypass, wealth-defense, anomalous-vendor, conduit-network, recusal-failure,
platform-complicity, dark-pattern at 2) — the seeded taxonomy over-estimated how domain-general the vocabulary
was. The truly cross-domain core is the ~15 types of §1.1. Seed-assignment provenance (which tag was seeded
into which cluster prompt) is preserved in `_intake/propublica/seed-taxonomy-ledger.md` — the reports and tally
files record observed use only, so seeded-vs-emergent claims audit against that ledger.

---

## 7. Emergent categories

Not in any seed list; arose from coding; ≥2 stories (or structurally load-bearing across clusters):

**Finding types**
- **accountability-gap / enforcement-collapse** (4 clusters — the top emergent category): authoritative findings
  of wrongdoing produce no sanction; the regulator's output series trends to zero while violations persist.
  Exemplars: judicial self-policing, FEC deadlock/IRS surrender, prosecutor misconduct without discipline,
  hospice/dialysis deficiency-without-termination.
- **undercount-by-design** (3 stories, criminal justice; adjacent healthcare form): the reporting regime itself
  conceals scale (hate-crime non-reporting; maternal deaths counted but not identified).
- **courts-as-profit-center** (3 stories): the civil judiciary as a subsidized collections department for
  volume plaintiffs; purest form: bail as collection revenue.
- **debt-criminalization / debt-spiral-by-design** (2 clusters): civil debt converted to custodial coercion;
  penalty systems manufacturing the insolvency they punish.
- **public-benefit-interception** (2 stories): profiting by standing between eligible people and a free public
  alternative.
- **evidence-infrastructure** (2 clusters + the whole methodology corpus): building the queryable public dataset
  *is* the journalism (Nonprofit Explorer, bailout tracker, NYPD Files DB).
- **regulatory-data-void** (1 explicit wave-1 story — *Uncovered* — so **below the bar on wave-1 coding alone**;
  wave 2 supplied the independent instances that admit the family: education's *State of Disrepair* (no state
  facilities assessment in 30 years — the synthetic census exists because the void does) and tribal's *BIE
  report card* (mandated performance reporting simply stopped). As a family — "duty-bound measurement never
  operationalized or discontinued" — 3 stories / 3 clusters.
- **rebrand-persistence** (healthcare): an enjoined practice redeployed under a new name in jurisdictions the
  settlement doesn't reach — fingerprint the enjoined thresholds and scan siblings. 1 explicit story; admitted
  only via the sanctioned-actor-migration merge (§8.2).
- **benefit-erosion-by-statute**: honest count is **one investigation double-clustered** (workers' comp, coded
  in both healthcare and environment/labor) — it does **not** meet the two-independent-story bar and is held
  below admission as a finding type; the *signature* it rides on (cross-jurisdiction codification) has
  independent support.

**Signatures** (full cards in detection-signatures.md)
- **enforcement-gap-ratio** family incl. zero-output-enforcement-baseline and sanction-outcome-diff (4 clusters).
- **plaintiff-frequency-inversion** (rank filers, not defendants).
- **guest-manifest-reconstruction** (+ protective-detail-records-reconstruction).
- **vendor-brag-mining** and **procurement-justification-text-mining** (the subject's own sales/filing text as
  confession layer).
- **benefit-cap-clustering**, **entity-age-vs-award-diff**, **address-colocation-clustering** (the emergency-
  spending screen family — independently re-derived by this platform's own DHS/PPP work before this project).
- **per-reviewer-throughput-forensics** (1.2 seconds per denial = no judgment occurred).
- **prior-disclosure-precedent-diff** (the subject's own earlier filings prove rule knowledge).
- **eligibility-recompute + designation-list-diff** (place-based subsidy gaming).
- **missingness-as-signal / zero-report-anomaly** (the absent record as affirmative evidence).
- **secrecy-repeal-arbitrage** (acquisition); **obstruction-as-confirmation** (2 clusters: Facebook blocking the
  Ad Collector; meatpacking companies fighting records release — resistance as signal).
- **archival-collection-anchor** (dated papers as fixed points for reconstructing decades-old conduct).
- **50-state-codification** (statute text as comparable data; erosion waves as lobbying signatures).

---

## 8. Wave-2 reconciliation

Reports 11–16 added ~73 coded entries (immigration 13, education/children 13, military/veterans 12, housing
12+2 cross-refs, democracy/elections 12 covering ~18 stories, tribal 11) over the census-identified uncovered
third of the portfolio — **coded with no seed taxonomy** (free-form tagging). Total coded corpus: ~180 entries
across 14 clusters + methodology. Full per-cluster mapping notes:
`_intake/propublica/` reports 11–16 (each ends in its own Cluster Synthesis).

### 8.1 Convergent validation

The free-form tag streams independently re-derived every Tier-1 wave-1 family under new names — the strongest
evidence the core taxonomy is real rather than seeded:

| Wave-2 agent's own name | Cluster | Maps to |
|---|---|---|
| "promise-ledger vs performance-ledger reconciliation" | tribal | two-books family (obligation variant) |
| "record-vs-record contradiction" (6 stories) | military | two-books family |
| "official-claim vs primary-record diff" (6) | immigration | two-books family |
| "entitlement-roll JOIN obligation-register" (4) | housing | two-books/obligation family |
| "denominator-normalized disparity ratio" (5) | education | denominator-construction |
| "allegation-to-consequence ratio" (214:1) | immigration | enforcement-gap-ratio |
| "enforcement-action census / records-absence-as-evidence" | housing | enforcement-gap-ratio + missingness |
| "violation-census × sanction join" | democracy | enforcement-gap-ratio |
| "mandate-vs-performance census" | tribal | enforcement-gap + denominator |
| "roster-wise ground-truth verification" (CECOT 238) | immigration | named-cohort-tracing |
| "cross-jurisdiction accumulation on a resolved entity" | democracy | silo-join / named-cohort |
| "corpus accumulation + rule-referenced coding" | immigration | internal-rulebook (policy-as-scoring-standard) |

Updated cross-corpus signature standings (14 coded clusters): **two-books-diff family present in all 14;
silo-join ~12; denominator-construction ~12; enforcement-gap-ratio ~10** (the top *emergent* family is now as
well-supported as the seeded cores); named-cohort ~8; constructed-corpus ~8; internal-rulebook ~7;
temporal-correlation ~8; missingness-as-signal ~6; ground-truth-verification ~6.

### 8.2 New categories from wave 2 (cards in detection-signatures.md §26–37 where ≥2-story support exists;
entries marked "variant" or "1 story" are named sub-moves held inside a parent family, not standalone categories)

- **obligation-reconciliation** (~11 stories / 2 clusters, independently derived in both): quantified standing
  obligation joined to the operational record of delivery/compliance — with the residual's *capturer* named.
  The uncovered third's defining move; promoted straight to Tier 1.
- **stratified-outcome-delta** (5 / 2): outcomes stratified by counterparty resources (represented vs not:
  207% vs 33%) or claim severity (denials *rising* with claim cost as the bad-faith fingerprint).
- **queue-forensics** (2 core / 2 clusters, + 1–2 time-to-event analogs): eligibility-vs-exit timestamp gaps,
  mortality-in-queue, the unlegislated filter ordering the line.
- **sworn-answer-registry-diff** (3 explicit / 1 cluster, + 1 housing analog via a stated merge):
  certifications as claim sets; enumerate the registries each one implicitly names, and diff.
- **banned-practice-relay + prohibition-window scan** (4 / 2): prohibition conformance — migration to an
  adjacent unregulated institution, and computable violation sets inside legal pauses.
- **sanctioned-actor-migration** (3 / 2, incl. wave-1 rebrand-persistence): disciplined people/practices
  crossing jurisdictional seams.
- **share-of-program capture** (3 / 1): benefit-ledger × relationship-graph share computation, with
  clients-of-kin's-firms as network edges.
- **shadow-authority-trace** (3 / 1): correspondence counterparties set-differenced against the org chart,
  ranked by deference language and proposal-to-action match.
- **self-contradiction-matrix** (1 explicit story — a *variant* of two-books-diff retained for its zero-access
  property, inside the military cluster's 6-story record-vs-record family): dated official statements about
  one quantity tested pairwise for joint logical possibility.
- **protected-inventory-leak** (2 articles / 1 cluster), **dead-platform-metadata-harvest** (1 investigation —
  variant, below the bar pending a second instance), **deed-chain-flip detection** (2 / 2),
  **classification-as-evasion** (2 / 1: category choice used to escape a duty — "culturally unidentifiable"),
  **measurement-chaos-as-finding** (2 / 1: no agreed success metric as the accountability defect),
  **single-case paper-trail replay** (3 / 1), **peer-institution benchmark diff** (3 / 1),
  **mandate-horizon arithmetic** (1 story — variant of the military cluster's 4-story denominator/throughput
  family: backlog ÷ own throughput = a 600-year horizon).

**Finding-type additions:** trust-obligation-breach + beneficiary-capture-of-undelivered-benefit (tribal/
housing — the obligation-reconciliation finding side); severity/resource-stratified adjudication bias;
prohibition-evasion-by-relay. Wave-2 tags otherwise confirmed the wave-1 core (extraction, coverup/records-
suppression, accountability-gap, disparate-impact, algorithmic-denial all recur heavily).

### 8.3 Evidence-class findings

Every census-predicted distinctive class was confirmed in the field: EOIR records, ICE/CBP row-level
enforcement data, restraint/seclusion incident logs, teacher-licensure databases, mishap/command-investigation
files, courts-martial records, exposure registries, VA claims data, REAC scores, eviction dockets, NAGPRA
inventories, treaty/trust documents, water-rights decrees, Parler-archive platform OSINT. New classes wave 1
had not surfaced:

- **official statements treated as a dataset** (military): the statements archive as a diffable corpus.
- **academic FOIA repositories** (immigration): TRAC, Deportation Data Project, UWCHR — pre-liberated bulk.
- **parallel custodians** (immigration + education): the same evidence held by institutions with weaker
  secrecy shields (local PD video, 911 logs, foreign courts, county files).
- **legal-notice streams as data** (tribal): Federal Register completion notices as a compliance ledger leg.
- **litigation as acquisition instrument** (military: 4 stories budgeted FOIA/access suits as the unlock).
- **dueling expert assessments** and **journalist-commissioned measurement** (tribal): the proponent-paid
  assessment re-counted independently.
- **IRB research access** (military): partnering into academic restricted-use registries.
- **probative refusals**: FOIL denials and instrument-blocking documented as evidence, not just failure.

The census's evidence-type bias warning (§ README) was correct in direction: wave 2 runs far heavier on
state/local agency records, mass-parallel FOIA (100–500 requests per story is the education-cluster norm),
and access litigation, and far lighter on leaks — in the military cluster the decisive artifact in 8 of 12
entries was the government's own record turned against its public statements; the tribal agent's summary was
"almost never rests on leaks."

### 8.4 Effect on retired priors

No wave-1 retirement was reversed: wave 2 produced zero uses of litigation-discovery-mining-as-signature
(litigation appears as acquisition instrument and evidence class instead — confirming the reclassification),
and the policy-erosion/benefit-erosion merge held (wave 2 added no new cross-jurisdiction erosion stories
outside the codification family). One demotion was *confirmed* in the other direction:
disclosure-gap-triangulation stayed judicial-only — no wave-2 cluster used it despite six having officials
with disclosure regimes in scope.
