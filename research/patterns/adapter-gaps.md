# Adapter Gaps — Missing Data Sources Ranked by Observed Usage

Diff of the evidence sources ProPublica's coded corpus actually runs on (reports 01–16,
`_intake/propublica/`) against this platform's existing source→tool inventory
(`_intake/propublica/coverage-inventory.md`, verified against `tools/` on 2026-07-29).

**Cross-outlet extension (2026-07-29).** A second ranked section below covers the three further profiled
outlets — ICIJ (107 coded entries), OCCRP (100), The Markup (83) — derived from the `systems-lines.txt` tallies
in each `_intake/<outlet>/tally/`. The two sections are kept separate rather than merged into one ranking
because sampling depth differs by outlet (ProPublica ~1.5% of its corpus, The Markup ~10%), so a single summed
frequency column would be misleading. Rows 1–5 of the ProPublica ranking remain the enqueued set (infra
requests #218–222); nothing in the cross-outlet section has been enqueued.

**Ranking discipline (user directive):** primary sort = observed source-usage frequency in the coded corpus
(story counts, with clusters cited), not hypothesis. Secondary = number of detection-signature cards the
source unlocks ([detection-signatures.md](detection-signatures.md)). Access notes and build difficulty are
engineering judgment, marked as such. **Queue status:** rows 1–5 were seeded into infra_tracker with user
approval on 2026-07-29 (requests #218 Census/ACS, #219 CMS institutional, #220 GAO/IG, #221 ed/child-welfare
collections, #222 ADS-B); rows 6+ remain unenqueued candidates.

**QA provenance:** the observed-usage counts below were corrected after an adversarial Codex (gpt-5.6-sol)
audit of a first draft found 11 rows that had relabeled broad evidence-class counts (e.g., a cluster's whole
"FOIA productions" row) as usage of one narrow adapter, or counted analogous/prospective sources as observed.
Counts now reflect per-story source attribution; two zero-observed candidates were moved to a separate
analog-ranked section rather than deleted.

## Coverage corrections first (hypotheses that died on verification)

- **Judicial financial disclosures: NOT a gap.** `query_courtlistener.py disclosures` already wraps
  CourtListener's financial-disclosures endpoint (`cmd_disclosures` → `get_financial_disclosures`, paginated
  client) — the exact corpus ProPublica anti-joined in 8 of 12 judicial stories. The gap is only the
  *congressional* side (see analog-ranked section) and the habit of using the judicial endpoint as an
  anti-join target.
- **Nonprofit Explorer parity: already strong.** The 990 stack (query_990, bulk/XML ingest, ProPublica API
  client) covers the corpus's single most-load-bearing disclosure family.
- **Court dockets: covered in architecture, partial in reach.** CourtListener/RECAP + NYSCEF + state-court
  router match the acquisition pattern; bulk *county-level civil* coverage (the docket-denominator/
  plaintiff-inversion fuel) depends on the in-flight property/local-courts work.
- **`public_records_census.py` is not a Census Bureau adapter** (it's the internal source-census queue) —
  demographic denominators are genuinely absent.
- **`query_medicare.py` scope:** dedicated logic is limited to the CMS Physician & Other Practitioners
  provider-spending schema (plus an enrollment alias and arbitrary-UUID passthrough); no Part D
  prescriber-level or institutional (Care Compare/deficiency/cost-report) support.

## Ranked adapter candidates (observed usage)

| # | Source | Observed usage (stories / clusters) | What it unlocks | Access | Build |
|---|---|---|---|---|---|
| 1 | **Census/ACS demographic denominators** (tract/county population by race, income, age) | ~13 / 4 — criminal-justice 4 (population denominators), corporate-consumer 3 (demographic join layers), gov-spending 3 (eligibility recomputation), environment/tech 3 (climate migration, Poison in the Air, Tiger Mom). (Education's five disparity ratios ride on CRDC-class enrollment denominators — counted in row 4, not here.) | denominator-construction, disparate-impact rates, geocoded-disparity-join, queue-forensics overlays | Free API, stable | Low |
| 2 | **CMS institutional layer**: Care Compare + inspection/deficiency files (nursing home, hospice, home health), HCRIS cost reports, **Part D prescriber PUF** | ~8–10 / 1 heavy (healthcare: government transactional microdata 6 + inspection/survey records 4, with overlap) | outlier-practitioner at prescriber grain, captive-population-extraction screen, enforcement-gap-ratio | Free (data.cms.gov) | Low–Med (extends query_medicare) |
| 3 | **GAO/IG/oversight.gov corpus as structured data** (findings, repeat-finding density, recommendation status) | ~7 class instances / 2 — gov-spending 2 (public warning layer) + military 5 (combined IG/GAO/unpublished-audit class; the unpublished internal studies and command investigations within it are FOIA-process acquisitions, not adapter reach) | warnings-ledger construction, repeat-finding density as pre-failure signal, two-books internal-vs-public | Free APIs | Low–Med |
| 4 | **Federal education/child-welfare collections**: CRDC, NCANDS, AFCARS, CCD, EDFacts (+SEDA crosswalk) | ~5–6 / 2 (education 4 explicit; tribal BIE via EDFacts) | zero-report audit, shadow-report-card rebuilds, disparity ratios by district | Free bulk | Low–Med per collection |
| 5 | **Flight movement history** (ADS-B Exchange / OpenSky historical; FAA registration already covered) | 4 / 1 (judicial: flight records in 4 of 12 stories) + this platform's own prior need (Epstein/tech-right travel) | benefactor-shadow-ledger placement leg, guest-manifest-reconstruction, asset-movement temporal joins | Paid API (ADS-B Exch) / research access (OpenSky) | Med |
| 6 | **HUD family**: REAC inspection scores + LIHTC property database (FHA/servicing unobserved) | 4 / 1 (housing: REAC 2, LIHTC 2) | certification-theater audit, obligation-reconciliation housing legs | Free | Low–Med |
| 7 | **State licensure & discipline registries** (teachers first — then medical boards, bar) | ~4 / 3 (education: Unfit to Teach + credential migration; healthcare: license-mill/medical-board legs; criminal-justice: bar-discipline leg) | sanction-outcome diff (dead-referral pipeline), sanctioned-actor migration, license-mill address clustering | Fragmented, some CAPTCHA | High (per-state) — the typology-library work independently ranked bar rosters #1 |
| 8 | **EPA family**: RSEI model output, TRI (ECHO: 0 observed uses) | 3 / 1 — RSEI/TRI explicit in 1 (Poison in the Air); other EPA records in 2 (Buried Secrets EPA studies; Fuel to the Fire EPA docket) | dormant-public-model-operationalization (the flagship), hotspot-mapping | Free bulk | Low–Med |
| 9 | **Immigration-enforcement row-level data**: EOIR case data, ICE detention/arrest extracts, + academic FOIA repositories (TRAC, Deportation Data Project, UWCHR) | 3 / 1 (No Sanctuary, 11,000-kids, EOIR minors; the cluster's broader 8-story FOIA class is process capacity, not this adapter) | counterparty-stratified outcome delta, two-stream joins, denominator audits of enforcement metrics | EOIR bulk free; TRAC part-paywalled; DDP/UWCHR free | Med |
| 10 | **National NAGPRA database (NPS)** + Federal Register completion-notice join | 3 / 1 (tribal: flagship census, Harvard, destructive-research) | mandate-vs-performance compliance census exemplar | Free | Low |
| 11 | **Bankruptcy dockets at denominator scale** (extend RECAP usage; Chapter 13 by county) | 3 / 3 (judicial defunct-institution mining; Ticket Trap insolvency join; Debt Inc.) | fines-to-insolvency join, defunct-institution docket-mining | PACER fees via RECAP | Med (extends existing) |
| 12 | **FCC political files (OPIF API)** | 2 / 2 (dark money: Free the Files; corporate-consumer: medical-staffing political ad buys) | ad-buy two-books vs FEC, local-market spend concentration | Free API (structured now) | Low–Med |
| 13 | **Remote sensing time series** (Landsat/Sentinel via public COGs) | 2 / 1 (Losing Ground; Fuel to the Fire) | remote-sensing-time-series, ground-truth at landscape scale | Free | Med–High (specialized) |
| 14 | **WHOIS history** (front-group/astroturf verification) | 2 / 1 (democracy: Hidden Hands; CA astroturf) | persona/front verification; complements crt.sh/urlscan | Paid (DomainTools-class) | Low (API) |
| 15 | **State campaign-finance + state lobbying** (followthemoney-class aggregation) | ~2–3 / 2 — manual per-entry estimate; the synthesis tables bundle federal+state in single classes, so this row is not table-recoverable | state-level share-of-program and conduit tracing | Fragmented | Med–High |
| 16 | **Workers' comp claims microdata** (state FROI/SROI) | 1 / 1 (Temp Land's 3.5M-claim rate ratio; Comp Demolition instead supports a statute/benefit-schedule corpus — a different, cheaper build) | captive-population rate ratio (labor tiers) | State-fragmented, request-gated | High |
| 17 | **OSHA**: inspections, violations, severe-injury reports | 1 / 1 observed (Temp Land's OSHA/EEOC enforcement files; dollar stores and meatpacking are unlock candidates, not observed uses) | captive-population rate ratio, zero-report audit vs claims, two-books (safety awards vs logs) | Free (DOL enforcement API) | Low |
| 18 | **IRS 527 disclosures (Forms 8871/8872)** | 1 / 1 (the 2024 527-mill wave; the 2019 scam-PAC story rode FEC data we already cover) | composition-ratio screens + operator clustering where FEC doesn't reach | Free IRS bulk | Low–Med |

## Validation-derived platform gaps (2026-07-29) — these outrank every source adapter below

Three card validations blocked on platform-internal defects rather than on missing external sources. A new
adapter cannot fix any of these, and they gate whole card families, so they belong at the top of any build queue.

| # | Gap | Blocks | Evidence | Build |
|---|---|---|---|---|
| **V1** | **Semantic, directed, effective-dated control edges.** `connections.relationship_type` stores relationship *domains*, not edge *semantics*; edges lack direction reliability, an evidence floor, and `valid_from`/`valid_until`. Needs either a typed sub-vocabulary (equity / board-seat / client / alumni / competitor) or a separate dated ownership table with identifier provenance. | Cards 30, 38, and every future control-path or beneficial-ownership move | Card 30 memo (hub isolated under the disciplined edge set; alumni+competitor edges admitted under the loose one); card 38 memo (one admitted dated edge = `$636,500` of `$75.86B`; **99.999% historically unresolved**; 53 UEIs / `$2.687B` with conflicting parents; a `subsidiary_of` edge stored backwards) | Med — schema + backfill; the backfill is the real cost. **Design proposal: [`docs/CONTROL_EDGES_SPEC.md`](../../docs/CONTROL_EDGES_SPEC.md)** (two additive tables; direction is provably alphabetical sort order platform-wide, not merely unreliable; alias resolution in `graph_tools` is silently dead) |
| **V2** | **Body text for SEC action records in `datasets/sec_enforcement.db`** (misattributed to `government_releases.db` in this row's first draft). 100% of the 5,464 selected action rows had empty bodies — an index-only ingester, not a source limit. **REPAIRED 2026-07-29:** `ingest_sec_enforcement.py fetch-bodies` backfills verbatim text with per-row provenance; window coverage 5,464/5,464 (the pre-registered searches now hit: `10b-5` 1,884 rows, `Section 10(b)` 1,657), corpus-wide backfill in flight (~7.9K/37,592 at last check). Residual output-side gap: `file_number` absent on 33.4% of window rows, so releases still cannot be collapsed to underlying matters. | Card 4 and any card classifying regulator output | Card 4 memo §Denominator + §6 addendum | Body leg **done**; the matter-key gap remains |
| **V3** | **A UEI/EIN/CIK/LEI ↔ registry-number crosswalk with alias provenance.** Every ownership resolution currently degrades to name matching; 3 of 13 exact-normalized registry matches were immediately false. | Cards 2, 38, and all cross-source entity resolution | Card 38 memo §Minimum data | Med |
| **V4** | **Paired payment stages / a stable transfer identifier.** No held corpus has two independently observed payment stages, so card 39's monetary form has no test bed at all (0 of 53,100 rows). The OCCRP Azerbaijani ledger (row 13 below) is the cheapest way to acquire one. | Card 39 monetary form; card 42's timing screen | Card 39 memo | Low (via row 13) |

Two smaller data-quality defects surfaced in passing and are logged rather than ranked: `query_registry`'s local
corpus is ~99.99% Florida (so "20+ registries" overstates *local* ownership coverage), and the epstein derived
sidecar leaves 42 within-LMSBAND repeated-hash groups uncollapsed (48 excess rows) plus 116 truncated refs.

## Cross-outlet ranked candidates (ICIJ + OCCRP + The Markup observed usage)

Counted from `_intake/<outlet>/tally/systems-lines.txt` (413 ICIJ rows, 361 OCCRP, 315 Markup). Ranked by
observed story-uses across the three outlets, then by how many cards the source unlocks. Access/build columns
are engineering judgment. **None of these is enqueued.**

| # | Source | Observed usage | What it unlocks | Access | Build |
|---|---|---|---|---|---|
| 1 | **Customs / bill-of-lading / trade-flow data** (import-export rows with shipper, consignee, HS code, volume) | ~11 — OCCRP illicit-trade 8/11 (corridor reconstruction), ICIJ extractives 3 (teak, bluefin, coltan) | **cards 39 (mass-balance), 38, 11** — the decisive missing leg for every physical-commodity chain; also origin-laundering detection | Paid (PIERS/Panjiva-class); some national customs open | Med–High |
| 2 | **Instrumentation / HAR-capture harness** (headless browser scans, network-request capture, sentinel-value probes) | ~20 Markup entries (11/11 privacy telemetry, 9/10 platform constructed instruments) | **cards 41, 40, 11, 9** — the single capability class the platform entirely lacks; Blacklight is open source and directly adaptable | Free (Playwright already in-repo for tests) | Med |
| 3 | **Certification / assurance registries with validity history** (FSC, PEFC, MSC, organic, ESG auditors — holder, standard, auditor, validity window, suspensions) | ~6 — ICIJ Deforestation Inc. 2 + teak 1 + bluefin chain 1; OCCRP product-verification legs 2 | **card 38 assurance-conduct engine**, benefit-after-adverse-action (F10) | Free web, no bulk API; auditor identity often buried | Med |
| 4 | **Normalized FARA + LDA + state-lobbying influence layer** (contact events with date, principal, target office) | ~6 — ICIJ R15 2 (Ethiopia/Windfalls), R17 4 (tobacco/Uber/Merck lobbying) | **F5 influence-to-decision sequence**, card 12, card 30 — ICIJ R15 named this the specific blocker for rerunning its Windfalls signature | Free (FARA eFile, Senate LDA) | Med |
| 5 | **Multilateral development-bank project corpus** (World Bank/IFC/ADB project docs, resettlement plans, completion reports, Inspection Panel/CAO files) | 3 — ICIJ R15 Evicted and Abandoned entries | **card 26 obligation-reconciliation**, card 3 fragmented-ledger denominators, card 18 | Free web; versioned attachments disappear (archival capture needed) | Med |
| 6 | **Land/title registries beyond current US property coverage** (Dubai-class, EU cadastral, historic snapshots) | ~10 — OCCRP asset-tracing 8/11 + Dubai property work 4; ICIJ hidden-property canon | cards 36, 38, 11 | Mostly closed/request-gated; the access-substitution analysis rules out a public UAE title feed | High (per-jurisdiction) |
| 7 | **HMDA Loan/Application Register + FFIEC panel** | 2 Markup (mortgage disparity regressions, both class a with released code) | **card 29 stratified-outcome-delta**, controlled disparity tests, card 3 | Free bulk (CFPB) | Low |
| 8 | **Insurance rate/territory filings (SERFF) + state DOI records** | 2 Markup (Allstate suckers-list, Michigan territories) | spatial-proxy-join disparity screens; card 1 (filed rationale vs charged price) | State-fragmented, some paywalled | Med–High |
| 9 | **Fisheries/extractives allocation ledgers** (quota holders, catch/landing records, subsidy registers, mining licenses/fatality records) | ~7 — ICIJ extractives cluster | cards 38, 39; public-benefit-after-adverse-action | Mixed (EU subsidy data open; national quota data varies) | Med |
| 10 | **Transplant/health-allocation data (SRTR/OPTN + CMS OPO performance)** | 2 Markup organ-failure entries (class a, all runnable today) | policy-shock flow reconstruction, need-normalized allocation audits | Free (SRTR) + request-gated microdata | Low–Med |
| 11 | **Meta Ad Library + political-ad archives** (pricing, targeting, delivery) | 3 Markup elections entries | binned-price cohort audits, ban-to-alias delivery mismatch | Free API, coverage-limited; researcher tooling decayed | Low–Med |
| 12 | **Latvia BO bulk CSV + Poland CRBR API** (the two live public EU beneficial-ownership feeds) | 0 direct story-uses — carried forward from the access-substitution analysis as the strongest public BO substitutes post-CJEU | card 38 control rollup where EU BO is otherwise closed | Free/bulk (Latvia daily CSV; Poland browse API) | Low |
| 13 | **OCCRP Azerbaijani Laundromat JSON** (16,940 payments, frozen 2012–14) | 3 OCCRP canon signatures run on it | cards 39/11/42 test corpus. **Raised in priority by the 2026-07-29 card-39 validation:** no held corpus has paired payment stages, so card 39's monetary form currently has *no* test bed — this ledger carries payer/beneficiary accounts, amounts, currencies, dates, and purpose text, making it the one available substrate for building and calibrating payment-flow detectors | Free single fetch | Low |
| 14 | **OCCRP ID catalogue** (1,030 country/type/access-tagged source cards) | discovery layer, not evidence | seeds this file's future rows + jurisdiction coverage audits | Public page; terms restrict copying — **permission-gated** | Low (parser) + editorial |

**Reading the two rankings together.** Rows 1 and 2 are the genuine cross-outlet additions: no ProPublica-derived
row implies either. Customs data is the shared blocker of both registry outlets; the instrumentation harness is
the shared blocker of everything The Markup does — and it is the cheapest high-value build on either list
(Blacklight is open source, Playwright is already a project dependency). Rows 4 and 7–11 are US-federal or
US-state sources that the ProPublica pass did not surface because its clusters used different beats; they are
low-build and directly unlock validated cards. Row 6 (foreign title registries) is the honest
"expensive and partly impossible" row — the access-substitution analysis established there is no public UAE
title feed and no anonymous EU BO register, so parts of OCCRP's asset-tracing corpus are permanently
out of reach rather than merely unbuilt.

## Analog-ranked candidates (0 observed uses of the missing source itself)

Held out of the main ranking to honor the observed-usage rule; ranked by transferability of a proven pattern.

| Source | Basis | What it unlocks | Access | Build |
|---|---|---|---|---|
| **Congressional financial disclosures + PTRs** (House Clerk XML, Senate eFD) | 0 observed — direct analog of the 8-story judicial disclosure anti-join, whose judicial leg is already covered by query_courtlistener | disclosure-gap-triangulation beyond the judiciary; law-to-asset clock on trading windows | Free, scraping-hostile | Med |
| **USCG documented vessels (+ state boat registries)** | 0 observed — vessel registries appear only in the judicial cluster's minimum-data recommendations; the two yacht stories used crew testimony, USPTO files, and IRS microdata instead | asset leg of shadow-ledger and sham-enterprise cards (complements FAA) | Free | Low |

## Not adapters (capability classes observed in the corpus)

- **Commercial/partnered datasets** (CoStar, ADP aggregate runs, Advertising Analytics, Quadrant quotes,
  RoboKiller/TelTech telemetry, PitchBook/NMHC, Pharmashine): partnership/purchase decisions per
  investigation — `custodian-run-denominator` is a human_action lead type, not a tool.
- **Mass parallel FOIA (100–500 requests/story), records-request litigation, and parallel-custodian routing**:
  process capacity, not adapters. The education cluster demonstrates the scale norm; request *operational
  logs*, not summary reports (housing); map every institution that touched an event and hit the weakest
  disclosure shield (immigration). Tracked as acquisition moves in detection-signatures.md.
- **Verified-crowd infrastructure** (callouts, tip verification): report-09's conclusion stands — the one
  structural ProPublica capability an agent platform lacks; treat crowd-dependent patterns as human_action.
- **Foreign-court/foreign-registry records** (CECOT-style roster verification): case-by-case acquisition,
  though existing international registry adapters partially serve this.
- **DoD mishap/command-investigation files and DBA/Longshore claims extracts** (military cluster): FOIA-process
  acquisitions rather than adapters; the platform's BCMR/BCNR + CAAF tooling already covers the courts-martial
  leg.

## Cross-check against the platform's independent experience

Three of the top candidates were independently flagged before this analysis (typology-library data-gap
roadmap: bar rosters #1; coverage-inventory hypotheses on disclosures/census/CMS) — and the PPP/DHS
procurement work already *re-derived* benefit-cap-clustering and entity-age screens without these gaps
blocking it. The observed-frequency ranking mostly confirms the platform's felt pain points, with two upgrades
the hypotheses underweighted — the CMS institutional layer (inspection/deficiency data powering
captive-extraction screens) and academic FOIA repositories (TRAC/DDP/UWCHR) as pre-liberated bulk sources —
and two downgrades the adversarial audit forced: OSHA and congressional disclosures are high-transferability
but near-zero *observed* usage in this corpus, so their case rests on pattern analogy, not frequency.
