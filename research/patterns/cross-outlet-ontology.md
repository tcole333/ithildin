# Cross-Outlet Ontology — Merged Finding-Type, Evidence-Source, and Signature-Family Layer

**Built 2026-07-29** over four profiled outlets. This file merges the per-outlet extraction layers into shared
families with per-outlet frequencies; it does not replace the per-outlet ontologies/indexes, which remain the
citation layer. Every frequency below traces to a tally file or a report synthesis table (paths in §7).

| Outlet | Coded entries | Coding provenance | Dependency coding |
|---|---:|---|---|
| ProPublica | 217 index entries (~180 stories; wave-1 107 + wave-2 ~73) | `propublica-story-index.md`, reports 01–16 | none (predates the field); leak usage measured separately (25/107 wave-1 stories) |
| ICIJ | 107 (33 leak-canon + 43 wave-2 stories + 31 methodology units) | `icij-story-index.md`, reports 01/09/12/13/15/17 | canon via `_intake/access-substitution-analysis.md`; wave-2 inline |
| OCCRP | 100 (30 laundromat-canon + 43 wave-2 stories + 27 methodology units) | `occrp-story-index.md`, reports 01/09/11/13/14/16 | canon via access-substitution; wave-2 inline |
| The Markup | 83 (9 clusters, full-portfolio extraction) | `markup-story-index.md`, reports 11–19 | inline, incl. runnable-today status per class-(a) entry |

**Unit caveats (read before using any number).** Outlets were coded in different waves with free-form tagging,
so identical mechanics carry different local names; this file maps local names onto shared families rather than
recounting stories. Frequencies are story-uses within one outlet's coded sample — cross-outlet sums are not
meaningful (sampling depth differs: ProPublica ~1.5% of its corpus, The Markup ~10%). A family's strength is
**how many outlets independently converged on it**, then its within-outlet frequency. All coding is
single-keyed by LLM agents from published stories; quoted-methodology vs [inferred] is marked per entry in the
source reports.

---

## 1. Merged finding-type families

### 1.1 Universal families (independently coded in ≥3 outlets)

| Family | ProPublica | ICIJ | OCCRP | The Markup |
|---|---|---|---|---|
| **Claim–conduct misrepresentation** (two-books-asymmetry; the stated fact differs from the recorded fact) | two-books-asymmetry 16/107 | disclosure-gap 5; compliance-knowledge-gap 6 | paper-versus-performance findings throughout canon + state capture | policy–packet contradiction 9; policy-enforcement gap 3 |
| **Obligation-performance gap** (a safeguard/condition/mandate exists; execution fails) | fraud-enablement-by-design 19 (design half) | safeguard-performance-gap; conditionality-misalignment (R15) | spec-to-delivery failure; vendor-arrears service collapse (R16) | promise-outcome latency; update-obligation-gap |
| **Regulatory capture / state capture** (the referee works for the players) | regulatory-capture family 16/107 | public-private-conflict 6; policy-arbitrage 4 | the entire state-capture cluster (R11: chokepoint concentration, insider tenders) | Prop-22 "wrote their own law, no one enforces it"; weak-regulatory-perimeter |
| **Beneficial-ownership concealment** (control hidden behind nominees/layers) | donor-anonymization-technique 7 (dialect) | hidden-beneficial-ownership 7; networked-asset-concealment 7 | hidden-beneficiary/nominee findings 9/11 in R11; proxy vehicles throughout | — (absent; platform-era corpus) |
| **Professional-enabler industry** (intermediaries as the machinery of concealment/harm) | influence-laundering-via-intermediaries 9 | **intermediary-enablement 10 — ICIJ's top tag**; high-risk-client-servicing 7 | formation-agent/bank enabler findings across canon | operator-blind vendor cascade 3 (school-filter vendors as unaccountable intermediaries) |
| **Extraction from captive population** | 24/107 — ProPublica's top core type | trafficking/labor entries (canon C6 work) | Steward hospital extraction; payday-lender chatroom justice | gig-labor pay opacity; tenant-screening lock-outs |
| **Disparate impact once denominators are built** | 14/107 | elite-cohort-penetration inversions | unlicensed-recipient concentration | sensitive-context inference 8; spatial pricing/service disparities (ISP, insurance) |
| **Missingness/undercount as a finding** | institutional-coverup/records-suppression 21 (overlap) | administrative-undercount 3; compliance-after-the-fact 3 | transparency missingness; warning-system non-use | unused-process-data gap; transparency-without-response |
| **Algorithmic/systematic adverse decision** | algorithmic-or-systematic-denial 12 | — | — (pre-platform corpus) | the outlet's founding subject: scoring, ranking, moderation, allocation |

### 1.2 Registry-outlet families (ICIJ + OCCRP intensive; ProPublica echoes; Markup absent)

- **Substance–form gap**: ICIJ letterbox-substance-gap 5, corporate-profit-shifting 6; OCCRP capacity/role
  mismatch (10/11 of state-capture stories); ProPublica echo in wealth-defense-technique. The registry-world
  question "does the paper entity have employees, premises, operations?" is the same move as ProPublica's
  anomalous-vendor and The Markup's volume-inflated apparent coverage — a shared *substance test* underlies all.
- **Deadline-adjacent restructuring**: ICIJ 4 (sanctions-eve transfers); OCCRP sanctions/event-aligned state
  diff. ProPublica echo: OZ-boundary and statute-eve timing plays.
- **State-asset conversion**: OCCRP state-to-private asset drift, state-company value transfer; ICIJ
  state-linked-benefit 2. No US-outlet equivalent at family strength.
- **Security-assistance harm chain** (ICIJ R15, 4 stories): donor programs resolved to abusive recipient
  units. Dialect of the universal funding-to-harm join.

### 1.3 Platform-era families (Markup-distinctive; earliest echoes elsewhere)

- **Undisclosed data flows**: sensitive-context inference 8, latent-surveillance infrastructure 7,
  identity-relinkable hashing 4, authenticated-space exfiltration 3. The platform-era sibling of
  undisclosed-benefit-to-official: the hidden transfer is data, not money.
- **Enforcement theater at platform scale**: ban-to-alias-delivery mismatch, unverifiable moderation
  suspicion, viewpoint-asymmetric restriction — enforcement-gap findings where the enforcer is a platform.
- **Zombie records**: expunged/corrected source records persisting in downstream commercial copies
  (tenant screening). ProPublica echo in background-check reporting; a growing family as data brokers
  intermediate more adjudications.

### 1.4 Composite structure

ProPublica's composite (captive population + extraction design + enforcement collapse + records suppression)
survives contact with the other three corpora and generalizes: the registry outlets' recurring composite is
**hidden control + enabler industry + jurisdiction arbitrage + missing registry fields**, and The Markup's is
**opaque automated decision + affected captive cohort + policy–conduct contradiction + vendor blame-shifting**.
In all three composites, confirming one component predicts the others; agents should test for the full
composite whenever one lands.

---

## 2. Merged evidence-source classes

### 2.1 Universal core (all four outlets, dominant tier)

1. **Government/administrative program records and microdata** — awards, claims, licenses, project files,
   case ledgers. The base layer everywhere: 10/10 stories in ICIJ R15, 9/11 in ICIJ R12, 10/10 in OCCRP R16,
   dominant in ProPublica, 6/11 in Markup C6.
2. **Court, enforcement, and adjudicative records** — 33/107 ProPublica wave-1; 22/33 ICIJ canon;
   OCCRP canon 22/30; Markup uses PACER for tenant-screening/gig-labor litigation corpora.
3. **Corporate/ownership registries** — the join glue: 25/30 OCCRP canon, 27/33 ICIJ canon (public half),
   ProPublica alias-resolution layer, Markup seller/vendor tracing.
4. **Interviews and human sources** — 62/107 ProPublica wave-1; all 12 ICIJ R13 entries; all 11 OCCRP R14;
   10/10 Markup C4. Across outlets the stated doctrine is identical: humans interpret and validate;
   records quantify.
5. **Mandated disclosure filings** — 990s/FEC/lobbying (ProPublica, ICIJ R15/R17, Markup elections);
   financial-disclosure anti-joins (ICIJ canon 3).
6. **FOIA / records-law output, including refusals-as-evidence** — 19/107 ProPublica; ICIJ R15's
   litigation-forced PEPFAR data; OCCRP FOI denominators; Markup school-filter logs and Maryland's
   "does not exist" denial. All four outlets treat the denial itself as evidence.
7. **Statute/rule/policy text as data** — the normative baseline for every conformance diff (all outlets).

### 2.2 Outlet-stratified layers

| Layer | Where it lives | Notes |
|---|---|---|
| Leaked provider/bank/FIU corpora | ICIJ (33/33 canon), OCCRP (dominant discovery layer) | The discovery layer of the leak canons; ProPublica uses leaks in 25/107 wave-1 stories under an explicit re-anchor doctrine; The Markup effectively never (3/83 class-c) |
| Sanctions/PEP/risk reference data | ICIJ, OCCRP core; growing ProPublica use | Time-aware designation vintage is the recurring discipline |
| Cross-border member/partner local records | OCCRP (member centers), ICIJ (consortium) | The consortium itself is an evidence-acquisition instrument; no US-outlet equivalent |
| Platform interface/API output as the observed system | The Markup 10/10 in C1 | The subject's own rendered behavior is the primary record |
| Instrumented network telemetry + sentinel inputs | The Markup (11/11 in C2) | Constructed evidence at industrial scale; ProPublica's cards 9/11 are the ancestral form |
| Volunteer/panel telemetry | The Markup (Citizen Browser, Rally, Ad Observer) | The crowd layer ProPublica built as registries, rebuilt as instrumentation; heavily decayed since (see §5) |
| Open code/data releases as evidence artifacts | The Markup (10/11 C2 stories ship a package; 84 org repos) | Makes third-party replay a corroboration mode — unique among the four |
| Trade/customs/shipment ledgers | OCCRP R14 (8/11), ICIJ R12 (teak/bluefin) | Largest shared *gap* in this platform's holdings (see adapter-gaps) |
| Physical/laboratory evidence | ICIJ (hake DNA), OCCRP (test purchases, hard identifiers) | The "physical closer" generalizes ProPublica's field-observation closer |

### 2.3 Acquisition-mode observation

Across outlets, the same four-step acquisition grammar recurs: **(1)** enumerate the universe from an
official structure; **(2)** acquire the row-level records (bulk download, FOIA, litigation, leak, or
constructed instrument); **(3)** resolve identity across systems (registries as glue); **(4)** close with an
independent-generation-process corroboration (field visit, lab test, subject response, second ledger).
Corroboration doctrine is verbatim-compatible across all four outlets and with this platform's evidence
standards: independent generation, not repetition.

---

## 3. Merged detection-signature families

Local coined names mapped onto shared families. Within-outlet frequencies in parentheses;
citations live in the per-outlet indexes and tally files.

| # | Shared family | ProPublica (cards) | ICIJ | OCCRP | The Markup |
|---|---|---|---|---|---|
| F1 | **Two-ledgers diff / claim-vs-conduct** | two-books-diff (card 1, ~28 uses); sworn-answer-registry-diff (28) | CROSS-LEDGER-MISMATCH (9/33); record-to-reality reconciliation (5/11); expected-versus-observed gap (6/10); mandate-or-predicate contradiction (7/12); obligation-to-execution-diff (4/10) | paper-versus-performance (13/30 canon; 10/11 R11); regulator-rule/practice diff (7/11); reference-price/rate/terms diff (5/10) | policy–packet contradiction (10/11); normative-output diff (3/6); policy-to-catalog conformance (2/7); rule-to-practice loophole diff (2/11) |
| F2 | **Silo join on hard identifier** | silo-join-on-hard-identifier (card 2) | ENTITY-EXTERNAL-JOIN (23/33 — top canon move) | identity-anchor join (22/30 — top canon move) | input-to-egress sentinel join (9/11 — planted identifier variant); same-event-across-silos (3/10) |
| F3 | **Denominator / corpus construction** | denominator-construction (card 3) | corpus enumeration (7/12); fragmented-ledger reconstruction (3/10); cohort/denominator construction (5/10) | purpose-built normalized corpora (2.5M-doctor DB, 37.8K-row procurement tracker) | jurisdiction/site census (4/11); record-corpus construction with row-level coding (4/10); cohort-to-scan prevalence (9/11) |
| F4 | **Missingness as signal** | missingness-as-signal (card 18) | missingness-as-signal (6/10 R15 — top wave-2 move); procurement-identity-gap ranking | institutional non-use / missingness gap (4/10) | missing-demographic survey substitution; unused-procurement signal |
| F5 | **Timeline / event-window alignment** | temporal-correlation (card 6) | EVENT-TIMELINE-DIFF (14/33); temporal policy reconstruction (8/10); influence-or-warning-to-funding sequence (3/10) | time-window alignment (16/30); transaction/event-window alignment (6/11); sanctions/event-aligned state diff (4) | timeline/change-point (5/10); **before/after remediation diff (10/11 — novel: the subject's response to the inquiry is itself evidence)** |
| F6 | **Beneficial-control rollup / proxy graph** | grant-chain-tracing (card 20); share-of-program (card 30) — partial forms | beneficial-control rollup (3/11); GRAPH-PATH-RECONSTRUCTION (16/33) | hidden-beneficiary/nominee graph (9/11); proxy-control graph join (6); shared-infrastructure clustering (10/30); entity/control continuity join (5/12) | — |
| F7 | **Mass balance / conservation audit** | composition-ratio-screen (card 21) — ratio cousin | regulated-chain mass balance (3/11) | supply-demand/absorption gap (6/11); corridor reconstruction (8/11); price/excise arbitrage feasibility (4) | capacity-accountability denominator gap (1) |
| F8 | **Constructed-instrument probe** | constructed-corpus-liberation (card 9); constructed-interaction-audit (card 11) | physical identity diff (hake DNA, 1/11) | record-to-field contradiction (7/11); undercover validation | **the outlet's dominant mode**: controlled input/output differential (5/10); adversarial-submission bypass; consent-branch invariant; feature-ablation importance; matched-hypothetical rule diff; authenticated panel reach-through |
| F9 | **Substance / capacity test** | entity-genealogy-screen (card 15) — adjacent | SUBSTANCE-GAP-TEST (5/33); letterbox tests | capacity/role mismatch (10/11 R11; core canon move) | volume-inflated apparent coverage |
| F10 | **Benefit-after-adverse-action / enforcement gap** | enforcement-gap-ratio (card 4); prohibition-conformance (card 34) | benefit/assurance-to-adverse-record join (3/11); compliance-after-the-fact | smuggler-customer overlap; unlicensed-recipient concentration | ban-to-alias-delivery mismatch; Prop-22 enforcement vacuum |
| F11 | **Flow-chain / asset reconstruction** | grant-chain-tracing (card 20) | RULE-TO-FLOW-MAP (6/33); origin-legality chain (1/11) | flow-chain reconstruction (18/30); flow-to-asset (4/11); transaction-to-asset (4) | campaign-ledger-to-captive-channel reconstruction (1) |
| F12 | **Cohort risk overlay / prevalence** | named-cohort-tracing (card 8) | COHORT-PREVALENCE (8/33) | property-owner risk overlay (3) | binned-price geographic cohort audit |
| F13 | **Ground-truth validation** | ground-truth-verification (card 19) | field/lab verification layer | direct physical or current-status check (3/10); hard-identifier chain of custody (3) | output-to-observed-outcome validation (2 — predictions vs actual crime) |
| F14 | **Rule-writer / drafting-provenance diff** | beneficiary-reverse-engineering (card 12) — adjacent | rule-writer-document-diff (1/10); policy/contract input-output reconstruction (2/11) | — | contract-scope unbundling diff (1) |
| F15 | **Coded-language / template decoding** | subject-artifact-forensics (card 22) — adjacent | coded-document semantics (3/10); REPEATED-TEMPLATE/CONTROL-CLUSTER (5/33) | repeated court templates (canon); OCCRP template clustering | policy or semantic pair diff (3/10 — mutated-vocabulary probes) |

**Convergence findings.** F1–F5 appear at high frequency in all four outlets under independently coined names —
these are the load-bearing universals of investigative method, and their ProPublica cards gain four-outlet
support. F6/F7/F11 are the registry-outlet core (new cards minted — see detection-signatures.md 38–40).
F8 is where The Markup industrializes what ProPublica did occasionally: cards 9/11 gain their deepest exemplar
sets plus new sub-moves. The Markup's remediation-diff (F5 variant) and sentinel-join (F2 variant) are genuinely
new mechanics contributed to old families.

**Divergence findings.** No outlet contradicts another's mechanics; divergence is in *dependency*, not method.
The same F1 diff runs on leaked bank ledgers (OCCRP), public certification registries (ICIJ wave-2), FOIA'd
lab retests (ProPublica), or instrumented network traffic (Markup) — the move survives every substrate.

---

## 4. Input-dependency profile across outlets

Classes: (a) open-record-runnable end-to-end; (b) re-anchoring (leak/insider discovery, public verification
half); (c) leak-dependent; (d) closed-platform-dependent. ProPublica predates the coding; its qualitative
profile is FOIA/public-records-dominant with a leak minority governed by an explicit re-anchor doctrine.

| Corpus | n | a | b | c | d | End-to-end public | Usable (a+b) |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICIJ leak canon (2013–2022 flagships) | 33 | 15 | 7 | 11 | 0 | 45% | 67% |
| ICIJ wave-2 (open-records clusters) | 43 | 27 | 7 | 8 | 1 | **63%** | **79%** |
| OCCRP (canon + wave-2 stories) | 73 | 23 | 23 | 27 | 0 | 32% | 63% |
| The Markup (full portfolio) | 83 | 65 | 6 | 3 | 9 | **78%** | **86%** |

Three structural results:

1. **The wave-2 inversion held.** ICIJ's skipped-over open-records clusters are ~1.4× more end-to-end
   reproducible than its famous leak canon (63% vs 45%) — the census-driven scope choice (take the residual
   clusters, skip the R4 leak families) was correct, and the aid/development cluster hit a=8/10 with zero
   leak-dependency.
2. **The dependency ladder is an outlet-identity fact:** Markup 78% > ICIJ wave-2 63% > ICIJ canon 45% >
   OCCRP 32% end-to-end public. OCCRP's methods are excellent but its decisive ledgers mostly never publish;
   The Markup publishes the instrument itself.
3. **Openness decays on a new axis.** The Markup coding adds runnable-today status: **20 of its 65 class-(a)
   entries (31%) are already degraded**, leaving 45 runnable — and only 38 of those cleanly, with 7 carrying
   caveats (access friction, countermeasures, or "fresh acquisition degraded but exact reproduction possible").
   The degradation is by platform countermeasures, API closures,
   and product shutdowns (CrowdTangle-class losses, Rally archived, PredPol/Geolitica dead, search-layout
   parsers obsolete). Records-based openness (ICIJ R15's 2001–2007 aid work; SRTR; HMDA) does not decay this
   way — **instrument-based reproducibility has a half-life; record-based reproducibility has archives.**
   Partial compensation: released code/data packages keep degraded detectors *artifact-replayable* (the
   original analysis re-runs on preserved inputs even when fresh acquisition is dead) — a third
   reproducibility state between runnable and lost, and an argument for the platform to snapshot instrument
   outputs at collection time.

---

## 5. What the merged layer changes operationally

- **Screening order:** F1 (two-ledgers), F2 (hard-identifier join), F3 (denominator), F4 (missingness), F5
  (event-window) are confirmed as the universal standing questions for any new investigation, in any domain,
  on any substrate. F6 (control rollup) and F9 (substance test) join them whenever the subject has a corporate
  graph; F8 (instrument probe) whenever the subject is an interactive system.
- **The enabler layer is a first-class target:** ICIJ's top finding tag (intermediary-enablement), OCCRP's
  formation-agent work, ProPublica's influence-laundering, and Markup's vendor-cascade findings all say the
  professional intermediary is where concealment concentrates — and enabler records (registries, licensing,
  engagement disclosures) are usually more public than principal records.
- **Missingness doctrine:** all four outlets independently converged on treating absent records, null
  identities, non-use of mandatory systems, and refusals as findings with their own distribution. The platform
  should log "expected-but-absent" as a structured observation, not a dead end.
- **Instrument snapshots:** given the Markup decay result, any constructed-instrument detector this platform
  runs should persist raw collected inputs (offers, rendered pages, API responses) at run time — the archive
  is what keeps the card replayable after the platform moves.

---

## 6. Retired-prior check against the merged corpus

The ProPublica ontology's retired priors (§6 there) were re-tested against the three new corpora: none is
resurrected — no new outlet shows the seeded-but-unsupported categories at family strength either. One
ProPublica emergent category is *upgraded* by cross-outlet evidence: enforcement-gap-ratio (card 4, emergent
in the ProPublica pass) now has independent support in all four outlets (§3 F10) and graduates from
"emergent" to a confirmed universal family. The wave-2/census de-biasing discipline (frame from the outlet's
own site structure; free-form second-wave tags) held up in both new applications and is adopted as the
standard extension method.

## 7. Provenance

- Per-outlet indexes: [propublica-story-index.md](propublica-story-index.md), [icij-story-index.md](icij-story-index.md),
  [occrp-story-index.md](occrp-story-index.md), [markup-story-index.md](markup-story-index.md).
- Mechanical tallies: `_intake/<outlet>/tally/` (story headers, finding-type lines, signature lines,
  dependency lines, systems lines, synthesis rows).
- Extraction reports with per-claim citations: `_intake/propublica/` 01–16, `_intake/icij/` 01/09/10/12/13/15/17,
  `_intake/occrp/` 01/09/10/11/13/14/16, `_intake/markup/` 10–19.
- Dependency methodology and the (a)/(b)/(c)/(d) classes: [_intake/access-substitution-analysis.md](_intake/access-substitution-analysis.md).
- Scope decisions for the ICIJ/Markup waves: `_intake/HANDOFF-icij-markup.md`.
- Nothing here was written to investigation.db; no infra requests were enqueued.
