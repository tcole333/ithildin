# Detection Signatures — Operational Pattern Cards

Derived bottom-up from 107 coded ProPublica stories (wave 1, 8 flagship clusters + methodology corpus) plus
second-wave clusters (immigration, education/children, military/veterans, housing, democracy/elections, tribal).
**Unified cross-outlet on 2026-07-29:** the card layer now carries exemplars and input-dependency from three
further profiled outlets — ICIJ (107 coded entries), OCCRP (100), The Markup (83). Cards reinforced by the new
corpora carry a **Cross-outlet:** line (per-outlet exemplars + the entry's input-dependency class a/b/c/d, where
(a) = open-record-runnable end-to-end, (b) = public verification half after leak discovery, (c) = leak-dependent,
(d) = closed-platform-dependent); cards 38–41 were minted where the new outlets contributed genuinely new
mechanics. The local-name → shared-family map with per-outlet frequencies is
[cross-outlet-ontology.md](cross-outlet-ontology.md) §3.
Evidence base: [propublica-story-index.md](propublica-story-index.md), [icij-story-index.md](icij-story-index.md),
[occrp-story-index.md](occrp-story-index.md), [markup-story-index.md](markup-story-index.md); taxonomy and
frequencies: [propublica-ontology.md](propublica-ontology.md) + [cross-outlet-ontology.md](cross-outlet-ontology.md);
sampling frames and their biases: [README.md](README.md) and the per-outlet census reports (report-10 in each
`_intake/<outlet>/`).

**How to read a card.** *Observed* = story-uses / clusters in the coded corpus (the bottom-up support for the
card's existence — every card required ≥2 independently cited stories). *Mechanics* = the analytic move.
*Minimum data* = the least you need before the move is runnable. *Ithildin mapping* = concrete platform tools;
"GAP:" marks a missing adapter (see [adapter-gaps.md](adapter-gaps.md)). *Failure modes* = how the move produces
false findings, from ProPublica's own stated method caveats where available.

**Discipline fields (added 2026-07-29 after live validation of cards 15/16/30 — see `_validation/`).** Cards
whose result is a computed statistic rather than a retrieved document additionally carry: *Pre-registration* =
the parameters that must be fixed before computing, because the result moves with them; report the sensitivity
across those parameters, not a point estimate. *Coverage statement* = what fraction of the denominator your
data can resolve — the ceiling on any share you can claim. *Control* = the null-hypothesis population the
screen's output must be measured against, constructed from the same held data; report the screen's lift over
its control, never its raw rate. Any card may carry *Preconditions* = credentials, CAPTCHA/browser-helper
dependencies, jurisdictional coverage limits, and known-stale adapters that gate the move ("BLOCKED:" marks a
currently-unavailable leg). Conventions: numeric parameters carry their derivation alongside the value (and
dollar literals are written shell-safe — under zsh a pasted `$20,833` loses its digits); multi-screen cards tag
domain-scoped screens (e.g. `[procurement]`, `[nonprofit]`). These fields are rolled out on validated cards
first; treat their absence on other statistic-producing cards (3, 5, 14, 21, 29) as a to-do, not an exemption.

**Two platform-level blockers found by validation (2026-07-29) — read before invoking any graph or
enforcement card.** Six cards have now been executed against held data (`_validation/`: 4, 15, 16, 30, 38, 39),
and three of the six failed for two shared reasons that are *infrastructure* problems, not card problems:

1. **The graph-vocabulary blocker (cards 30, 38, and any future control-path card).**
   `connections.relationship_type` encodes relationship **domains** (`corporate`, `financial`, `political`,
   `employment`, `funds`) while every control-rollup card asks the analyst to pre-register edge **semantics**
   (equity stake vs board seat vs client vs alumni). The consequences measured twice: a disciplined
   semantic edge set returns near-zero (Thiel is an isolated node under it; card 38 admitted one dated edge
   covering `$636,500` of a `$75.86B` ledger), while the loose domain set admits edges whose meaning is the
   *opposite* of control — alumni and competitor relations. Direction is also unreliable
   (`Palantir Technologies --[subsidiary_of]--> Palantir USG` is stored inverted relative to its own
   description). Until edges carry semantics, direction, an evidence floor, and `valid_from`/`valid_until`,
   control-path cards produce present-day sensitivities at best. **Any such card must state a dated-coverage
   figure or label its output `current-state sensitivity`.**
2. **The empty-body blocker (card 4 and any card classifying regulator output) — repaired for the validated
   window 2026-07-29.** All 5,464 selected SEC action records lacked body text — in
   `datasets/sec_enforcement.db`, not `government_releases.db` as an earlier revision of this note said —
   because the ingester was index-only and never fetched the text its own `release_url` column pointed at.
   A `fetch-bodies` pass now backfills it: 5,464/5,464 window rows carry verbatim text (re-verified
   2026-07-29: `10b-5` → 1,884 rows, `Section 10(b)` → 1,657, both previously 0); the corpus-wide backfill
   is still in flight (~7.9K of 37,592 rows at last check). The lesson is unchanged: **verify text presence
   before treating a release corpus as classifiable.** This repair does not unblock card 4 — its
   independent-numerator blocker stands (see the card and the memo's §6 addendum).

The wider lesson for card authors: **coverage must be reported as an intersection, not per-field.** Card 39's
payment claim survived review because amount and date coverage were 97%; it died on the intersection with stage
coverage, which was 0%.

Tier 1 = ≥4 clusters (domain-general). Tier 2 = 2–3 clusters, or ≥3 stories concentrated in one domain
(domain dialects that still transfer).

---

## Tier 1 — core cross-domain signatures

### 1. two-books-diff
**Observed:** ~28 story-uses / 8 of 8 wave-1 clusters — the single most-used move in the corpus.
**Mechanics:** The same economic or factual claim is filed with two audiences whose incentives point in opposite
directions (lender vs assessor; IRS vs FEC; investor vs customer; internal after-action vs public statement).
Join the two channels on a hard key (property, EIN, docket, asset-year, KPI), diff shared fields, and score gaps
by whether their *direction* matches the filer's incentive in each channel — incentive-aligned gaps are intent,
random gaps are noise. Variants: attestation-vs-conduct (application says "no politics", spending says otherwise);
mission-vs-conduct ledger (990 charity-care posture vs collection dockets); temporal (same loss claimed in two
eras); warnings-ledger (dated internal warnings joined to the later failure and to who received them).
**Minimum data:** two independent filing channels covering the same entity/asset/period with ≥1 shared field.
**Ithildin mapping:** query_edgar + query_990 + query_fec (channel pairs); query_property / query_state_courts
(assessor + docket legs); government_release_corpus (enforcement leg); findings_tracker `finding_relations`
contradicts-links for recording the diff.
**Failure modes:** fields that legitimately diverge (different accounting bases, timing rules); fixed-fact rows
(contractual ground rent, insurance premiums) are the checksums — anchor on those first. A gap without an
incentive story is noise.
**Exemplars:** [Trump two-books](https://www.propublica.org/article/trump-inc-podcast-never-before-seen-trump-tax-documents-show-major-inconsistencies);
[nonprofits' 990-vs-FEC](https://www.propublica.org/article/how-nonprofits-spend-millions-on-elections-and-call-it-public-welfare);
[Methodist Le Bonheur mission-vs-docket](https://www.propublica.org/article/how-nonprofit-hospitals-are-seizing-patients-wages);
[Red Cross internal-vs-public](https://www.propublica.org/article/the-red-cross-secret-disaster).

**Cross-outlet (F1 — the universal):** confirmed at high frequency in all four outlets under independent names.
ICIJ: CROSS-LEDGER-MISMATCH 9/33 canon + mandate-or-predicate contradiction 7/12 + obligation-to-execution diff
4/10 (Wintris disclosure anti-join; World Bank safeguard-vs-outcome). OCCRP: paper-versus-performance 13/30
canon and 10/11 state-capture stories (contract/invoice/judgment vs observed movement). The Markup:
policy–packet contradiction 10/11 privacy stories (site's stated policy vs observed network egress) — fully
instrument-built, class (a). The move survives every substrate: leaked ledgers, public certification registries,
FOIA'd retests, instrumented traffic.

### 2. silo-join-on-hard-identifier
**Observed:** ~27 story-uses / 7–8 of 8 clusters.
**Mechanics:** Two record systems that never talk to each other share a hard key — NPI, EIN, parcel ID, tail
number, name+DOB, UEI, address, officer-of-record. The join surfaces what neither silo shows alone. Its most
productive specialization is the **influence-payment × behavior join**: normalize a mandated influence-disclosure
stream (industry payments, gifts, donations) into a per-recipient ledger, join to the recipient's decision stream
(prescribing, rulings, votes, awards) on the registry key, and test dose-response by payment tier.
**Minimum data:** two datasets sharing one resolvable identifier; a match-error estimate on a sample.
**Ithildin mapping:** trace_provider (NPI pipeline), query_registry + registry_address_index (entity/address keys),
query_property (parcel), ingest_faa (tail number), person_resolution + entity_resolution (name keys), graph_tools
(post-join network). GAP: census/ACS layers for geo-keyed joins; flight-movement history for tail-number joins.
**Failure modes:** name-collision joins (measure and disclose linkage error — ProPublica's COMPAS disclosure was
3.75% on n=400); identifier reuse over time; the join proving association, not mechanism — pair with interviews
or rulebook evidence before promoting confidence.
**Exemplars:** [Dollars for Docs](https://projects.propublica.org/docdollars/);
[IRS microdata × SEC filings (Thiel)](https://www.propublica.org/article/lord-of-the-roths-how-tech-mogul-peter-thiel-turned-a-retirement-account-for-the-middle-class-into-a-5-billion-dollar-tax-free-piggy-bank);
[phone-number → principal (Fillakit)](https://www.propublica.org/article/the-trump-administration-paid-millions-for-test-tubes-and-got-unusable-mini-soda-bottles).

**Cross-outlet (F2):** the top single move of both registry outlets — ICIJ ENTITY-EXTERNAL-JOIN 23/33 canon
(leak entity → registry/sanctions/court/property), OCCRP identity-anchor join 22/30 (account, passport, DOB,
registration number, address). The Markup contributes the *planted*-identifier variant (see card 41): when you
control the input value, join error collapses to ~0. Class (a) whenever both silos are public — the offshore
graph side is public for OLDB-published vintages.

### 3. denominator-construction
**Observed:** ~25 story-uses / 8 of 8 clusters.
**Mechanics:** The story-killing question is "out of how many?" — and the base the subject publishes is the base
the subject controls. Build the universe nobody publishes (every civil filing in a county; every member of the
Forbes 100; the full roster of a justice's trips; all exempt orgs), then compute rates against it. The
**denominator-substitution** variant swaps a subject-controlled denominator (taxable income, declared value) for
an independent one (wealth growth, market valuation, deed price): if the figure moves an order of magnitude, the
gap is the finding. The **docket-denominator** variant bulk-acquires court filings and geocodes defendants for
per-capita, per-demographic rates.
**Minimum data:** an enumerable universe from any authoritative source + the outcome numerator; for rate claims,
a defensible population layer.
**Ithildin mapping:** query_state_courts / query_courtlistener (docket universes), ingest_990_bulk (org universe),
query_usaspending / query_fpds (award universe), datasets/*.db sidecars as maintained ledgers. GAP: census/ACS
demographic denominators — required by every disparity-rate pattern in the corpus.
**Failure modes:** universe-completeness bias (missing courts/years silently deflate rates); denominators that
embed the harm (auditing "per return filed" hides non-filers); ProPublica's stated discipline: defend the
population definition and enumerate exclusions with counts.
**Exemplars:** [true tax rate](https://www.propublica.org/article/the-secret-irs-files-trove-of-never-before-seen-records-reveal-how-the-wealthiest-avoid-income-tax);
[The Color of Debt](https://www.propublica.org/article/debt-collection-lawsuits-squeeze-black-neighborhoods);
[EITC audit map](https://projects.propublica.org/graphics/eitc-audit).

**Cross-outlet (F3):** ICIJ corpus enumeration 7/12 conflict cluster (build the universe before selecting
examples: all U.N.-accredited NGOs, all 2010 Red Notices, all ICE solitary incidents) + fragmented-ledger
reconstruction (the 3.35M-person World Bank displacement denominator, class a); OCCRP purpose-built corpora
(2.5M-record doctor DB, 37.8K-row COVID procurement tracker); The Markup jurisdiction/site censuses 4/11 and
cohort-to-scan prevalence 9/11 (Tranco/HHS/IRS lists as scan denominators, class a).

### 4. enforcement-gap-ratio (captured self-regulator) — *emergent*
**Observed (emergent — not in the seed taxonomy):** ~10 story-uses / 4 of 8 clusters.
**Mechanics:** Measure the regulator, not just the regulated. Construct the violation base rate independently
(journalist-found violations, substantiated complaints, deficiency counts, deadlocked votes), obtain the
regulator's own output series (referrals, investigations, sanctions, penalty totals), and publish the ratio.
Near-zero output against nontrivial intake is itself the finding; it also *predicts* where misconduct migrates
next. Variants: **zero-output-enforcement-baseline** (decades of the body's own annual stats ≈ 0 — the judiciary
had never referred a judge to DOJ); **sanction-outcome diff** (join adjudicated wrongdoing in ledger A to the
discipline/license registry in ledger B; systematic absence of consequences is computable).
**Validated 2026-07-29 — BLOCKED; the aggregate ratio as originally written is un-executable here.** Tested on
the fairest held pair (SEC §10(b)/Rule 10b-5, nationwide, 2021–2025). The platform could count 5,464 SEC action
releases but **100% lacked body text**, so conduct-classifiability was 0%; the independent CourtListener leg
funnelled 92 hits → 28 non-government federal dockets → 14 substantively relevant private securities matters →
**zero final-merits violations**. The ratio was undefined, with no null, lift, or lag adjustment constructible.
Memo: `_validation/card04-enforcement-gap-ratio.md`. The cross-outlet graduation below stands as a claim about
the *finding-family* (enforcement gaps recur in all four outlets); it is **not** a claim that this card computes.
**Output-side blocker cleared 2026-07-29 (numerator blocker stands).** The empty body text was our ingestion
defect, not a source limit: `ingest_sec_enforcement.py` was index-only and never fetched the release text its own
`release_url` column pointed at. A `fetch-bodies` pass now backfills it, and **all 37,793 rows corpus-wide carry
verbatim text, 0 unresolved** — including all 5,464 window rows (`10b-5` → 1,884 rows, `Section 10(b)` → 1,657,
both previously 0). Conduct-classifiability in this cell is no longer 0%, and no source-side text gap remains. **This does not unblock the card.** The two blockers the memo identifies as fatal are untouched:
the aggregate ratio still has no fixed event unit, and the independent numerator still cannot be *enumerated*
(CourtListener searches, it does not census), so no base rate, control, or lift is constructible. Re-testing the
amended case-linked statistic below still needs a matter/respondent key on the output side — `file_number` is
absent on 33.4% of window rows — and an enumerable independent cohort the platform does not hold.
**Mechanics (amended to a case-linked statistic):** aggregate "base rate ÷ output series" mixes incompatible
units and can compare disjoint matters. Instead: build an enumerable independent violation cohort in a fixed
regulator × population × conduct × jurisdiction cell, and join **each event/subject** to the regulator's
matter-level output within a pre-registered lag. Primary statistic = qualifying responses / eligible independent
violations; companion gap multiple = the inverse, with zero responses reported as an *unbounded gap* rather than
silently divided. Deduplicate releases, orders, AAERs, and announcements to one underlying matter. **Do not call
an aggregate count ratio "capture" when the event-level join cannot be made.**
**"Independent" defined operationally:** the event entered the numerator without using this regulator's action,
referral, investigation, or announcement — or a parallel enforcement body's case — as the discovery predicate.
Private audit/inspection/journalist measurement is the strict numerator; another agency's adjudication is a
*jurisdiction-split sensitivity*, reported separately.
**Minimum data:** (i) an enumerable independent violation cohort with an at-risk population or documented event
census, reviewed final-merits/substantiation labels, and event dates; (ii) regulator output with **full text**,
action/outcome type, stable matter key, respondent key, and complete annual coverage; (iii) a hard or audited
entity/matter join; (iv) complaint/referral/intake counts for composition checks; (v) official versioned
statute/rule text establishing jurisdiction and the exact available remedies.
**Pre-registration:** fix the regulator, population, conduct category, jurisdiction, eligible violation event and
evidentiary threshold, independence exclusions, numerator/output units, window and date fields, qualifying
outputs, matter-dedup and entity-resolution rules, enforcement lag and right-censor rule, severity strata,
control population, and sensitivities — before retrieving results. Register whether the primary measure is
event-linked follow-through or an aggregate gap multiple, and never switch after seeing counts.
**Coverage statement:** report separately (a) independent-cohort recall or why it is unknowable, (b) the fraction
of regulator outputs with full text and matter/respondent keys, (c) the fraction of numerator events resolved to
regulator subjects, (d) the fraction with a completed lag window. **A located zero with unknown recall is "no
qualifying event located," not a zero violation rate.** Do not publish the ratio when cohort or join coverage is
unquantified.
**Control:** a matched regulator/statute, historical period, or comparable-severity cohort built from the same
pipeline; report lift against it, never the raw ratio alone.
**Ithildin mapping:** query_sec_enforcement + government_release_corpus (federal output series — validation found
the SEC action bodies empty in `sec_enforcement.db`; **repaired 2026-07-29** via `fetch-bodies`, window fully
covered; the verify-text-presence discipline stands),
query_courtlistener for the adjudicated-misconduct leg (CL v4: use `__istartswith`; `contains`/`icontains` now
400), source_reliability discipline for self-reported stats. **GAPs:** state licensing/discipline registries; any
complaint/referral intake census; versioned statute/rule text.
**Failure modes:** **(0) proxy circularity — the fatal one:** a conviction, substantiated complaint, or
adjudication may exist only *because* an enforcement body investigated and published it; "independent of this
regulator's release index" is much weaker than "independently ascertained." (1) enforcement lag misread as
absence (an opinion's filing date is already years downstream of the conduct); (2) jurisdiction splits — 20 of 48
federal phrase-hit dockets were government matters, and counting DOJ prosecutions as independent violations makes
parallel jurisdiction look like SEC non-use; (3) intake composition shifts, indistinguishable from enforcement
shifts without an intake census; (4) **literal outcome-phrase matching is unsafe** — validation found "found
liable," "pleaded guilty," and "convicted" hits that all described *unrelated or prior* proceedings while the
securities claim under review was dismissed. Confirm the powers exist on paper from official law text, not from
the agency's own announcements.
**Exemplars:** [The Judiciary Has Policed Itself…It Doesn't Work](https://www.propublica.org/article/judicial-conference-scotus-federal-judges-ethics-rules);
[Regulators in Retreat (FEC/IRS)](https://www.propublica.org/article/as-political-donors-push-envelope-fec-gridlock-gives-de-facto-green-light);
[Out of Order (prosecutor misconduct)](https://www.propublica.org/article/who-polices-prosecutors-who-abuse-their-authority-usually-nobody);
[Hospice enforcement gap](https://www.propublica.org/article/hospice-healthcare-aseracare-medicare).

**Cross-outlet (F10) — emergent status GRADUATED 2026-07-29:** independent support in all four outlets.
ICIJ: benefit/assurance-to-adverse-record join 3/11 (subsidies to firms with fishing judgments; FSC
certificates active across adjudicated harms — both class a) + compliance-after-the-fact tags. OCCRP:
smuggler-customer overlap, unlicensed-recipient concentration. The Markup: ban-to-alias-delivery mismatch
(QAnon ads), the Prop-22 wrote-own-law/no-enforcement finding. The family is now a confirmed universal, not a
ProPublica emergent.

### 5. outlier-in-microdata (licensed-practitioner screening)
**Observed:** ~11 story-uses / 3–4 clusters (story-heavy where it appears).
**Mechanics:** Any system logging transactions per licensed professional or per capped instrument supports
peer-group outlier detection: aggregate per actor per product, compare within specialty × jurisdiction peer
cells, flag ≥2σ with minimum-denominator guards (≥20–50 events, ≥20 peers) and small-n shrinkage, then interview
the outlier — innocent explanations (shared IDs, niche practice) are enumerable and checkable. The special cases
that carried whole stories: zero-value years among the ultra-rich; impossible balances; the outlier *institution*
(28 of 34 officers disciplined).
**Minimum data:** transaction microdata with a hard actor ID + a registry for peer grouping.
**Ithildin mapping:** query_medicare + trace_provider (provider spending), financial_ratios (screening variant),
query_990 (officer comp outliers), FINRA BrokerCheck. GAP: Medicare Part D prescriber-level PUF (the Prescriber
Checkup source).
**Failure modes:** outliers without denominators are anecdotes; specialty mix confounds peer cells; publishing
individual scores demands the strongest methodology (ProPublica issued a white paper and still took heavy
methodological criticism on Surgeon Scorecard).
**Exemplars:** [Prescriber Checkup](https://www.propublica.org/article/part-d-prescriber-checkup-mainbar);
[Surgeon Scorecard](https://projects.propublica.org/surgeons/);
[$0-tax years](https://www.propublica.org/article/the-secret-irs-files-trove-of-never-before-seen-records-reveal-how-the-wealthiest-avoid-income-tax).

### 6. temporal-correlation
**Observed:** ~16 story-uses / 5–6 clusters.
**Mechanics:** Put two dated event streams on one axis and read the intervals. Money-in → provision-out (donation
windows around a tax amendment); benefit ↔ docket timing (gift dates vs cases filed by the giver's interests);
application-to-approval velocity anomalies (8 days from beneficiary contact to designation); policy-date natural
experiments (outcome series diffed across a statute's effective date); election-cycle revenue ramps.
**Minimum data:** two independently dated event series touching the same actor or instrument.
**Ithildin mapping:** event_timeline + tools/date_normalize (the platform's ISO-date layer exists for exactly
this), timeline-analysis skill, query_fec (donation dates), query_courtlistener (docket dates).
**Failure modes:** correlation-as-intent is the classic overreach — ProPublica pairs every timing hit with a
mechanism witness or document before alleging causation; seasonal/cyclical confounds; backdated instruments.
**Exemplars:** [199A donors → provision](https://www.propublica.org/article/secret-irs-files-reveal-how-much-the-ultrawealthy-gained-by-shaping-trumps-big-beautiful-tax-cut);
[OZ marina designation](https://www.propublica.org/article/superyacht-marina-west-palm-beach-opportunity-zone-trump-tax-break-to-help-the-poor-went-to-a-rich-gop-donor);
[Alito trip vs Singer cases](https://www.propublica.org/article/samuel-alito-luxury-fishing-trip-paul-singer-scotus-supreme-court).

**Cross-outlet (F5):** ICIJ EVENT-TIMELINE-DIFF 14/33 (service dates vs sanctions/warnings/appointments) +
temporal policy reconstruction 8/10 in lobbying (corporate action ↔ official access ↔ rule change ↔ commercial
result) + influence-or-warning-to-funding sequence (FARA contacts vs bill milestones vs aid decisions — class a).
OCCRP: time-window alignment 16/30; sanctions-eve state diffs. The Markup adds the *remediation-diff* variant —
re-running the identical probe after contacting the subject, 10/11 privacy stories — now minted as card 40.

### 7. internal-rulebook-acquisition
**Observed:** ~14 story-uses / 4 clusters.
**Mechanics:** The institution's own operating document — the SOP, threshold matrix, auto-denial list, training
script, score weights, playbook — converts observed behavior from anecdote into policy. Detection of industrial
misconduct then reduces to: obtain the rulebook (leak, discovery exhibit, FOIA of the government's copy), and
corroborate with output data showing the rule executing (denial rates, throughput arithmetic). The rulebook also
supplies intent: a tunable dial with revenue attached is a decision, not an accident.
**Minimum data:** one internal operating artifact + any output series it should explain.
**Ithildin mapping:** court-filing exhibit mining via query_courtlistener/RECAP (discovery is where rulebooks
surface publicly), MuckRock/FOIA corpus (query_muckrock), DocumentCloud search (query_documentcloud).
**Failure modes:** stale versions (rulebooks change; date the artifact); drafts vs adopted policy; a rulebook
without output data proves design, not execution.
**Exemplars:** [Cigna PxDx lists](https://www.propublica.org/article/cigna-pxdx-medical-health-insurance-rejection-claims);
[EviCore "the dial"](https://www.propublica.org/article/evicore-health-insurance-denials-cigna-unitedhealthcare-aetna-prior-authorizations);
[HomeVestors training materials](https://www.propublica.org/article/ugly-truth-behind-we-buy-ugly-houses);
[COMPAS questionnaire](https://www.propublica.org/article/machine-bias-risk-assessments-in-criminal-sentencing).

### 8. named-cohort-tracing
**Observed:** ~10 story-uses / 4 clusters.
**Mechanics:** Fix a definite, enumerable cohort — 416 drug-test convictions, 37 cases touched by one informant,
the membership roll of a giving club, 11 jailed children, every parcel in an heirs'-property county — and follow
every member to an outcome. The named-cohort form defeats the "isolated incident" defense arithmetically and
generates the human exemplars simultaneously. The **career-file assembly** variant aggregates every case one
recurring intermediary touched across decades and time-aligns their benefit ledger with their cooperation ledger
— undisclosed exchange becomes visible even though no single file discloses it.
**Minimum data:** a cohort definition with names/IDs + at least one outcome system to trace members through.
**Ithildin mapping:** pillar_tracker (cohort/alumni/dispersal machinery is purpose-built for this),
lead_tracker batch leads per member, person_resolution for identity threading.
**Failure modes:** cohort-definition gerrymandering (define before tracing, disclose exclusions); survivorship
(members you can't trace aren't absent, they're unknown); scale limits — tracing is expensive, so ProPublica
pairs it with a bulk-data screen that nominates the cohort.
**Exemplars:** [Busted (416 convictions)](https://www.propublica.org/article/common-roadside-drug-test-routinely-produces-false-positives);
[False Witness](https://www.propublica.org/article/hes-a-liar-a-con-artist-and-a-snitch-his-testimony-could-soon-send-a-man-to-his-death);
[Thomas' 38 vacations](https://www.propublica.org/article/clarence-thomas-other-billionaires-sokol-huizenga-novelly-supreme-court);
[heirs' property parcels](https://features.propublica.org/black-land-loss/heirs-property-rights-why-black-families-lose-land-south/).

### 9. constructed-corpus-liberation (crowd/scrape/instrumentation)
**Observed:** ~10 story-uses / 5 clusters (plus the entire methodology corpus).
**Mechanics:** When disclosure exists as unstructured PDFs, hostile dumps, or platform-internal state, the
investigative act is *building the dataset*: crowd-transcription with multi-volunteer agreement (Free the Files),
edge instrumentation of consenting users' browsers (Political Ad Collector), scraping the subject's own public
interfaces (Dollars for Docs v1), structured callouts that assemble the cohort the agency can't name (Lost
Mothers). The corpus then feeds every other signature — and compounds across investigations once published.
**Minimum data:** a legally public but practically inaccessible record class + a validation scheme
(multi-reviewer consensus, classifier + human loop, or authoritative identifiers).
**Ithildin mapping:** PDF ingest+OCR pipeline, ingest_* corpus builders, datasets/*.db sidecars, DocumentCloud;
the verified-crowd layer is the one structural piece an agent platform lacks (report-09's conclusion) — treat
crowd-dependent variants as human_action leads.
**Failure modes:** volunteer attention decays after the news peak; self-selection presented as prevalence;
platform retaliation (Facebook blocked the Ad Collector — see obstruction-as-confirmation, card 22); format churn.
**Exemplars:** [Free the Files](https://projects.propublica.org/free-the-files/);
[Facebook Political Ad Collector](https://www.propublica.org/article/how-we-are-monitoring-political-ads-on-facebook);
[Nonprofit Explorer](https://projects.propublica.org/nonprofits/).

---

## Tier 2 — established signatures (2–3 clusters, or ≥3 stories in one)

**Cross-outlet (F8):** The Markup runs this at industrial scale and adds the decay caveat: volunteer/panel
telemetry (Citizen Browser, Rally, Ad Observer) produced 3 of its strongest platform findings but every panel
instrument is now dead or archived — of the outlet's 65 class-(a) entries, 20 are already degraded by platform
changes (31%), and 7 more run only with caveats.
**Precondition for any constructed-corpus card: snapshot raw collected inputs at run time** (the released
data/code packages are what keep degraded detectors artifact-replayable). OCCRP analog: purpose-built
normalized corpora from FOI + scraping (class a).

### 10. disclosure-gap-triangulation (benefactor shadow ledger)
**Observed:** 6 stories / 1 cluster (judicial) — seeded in 7 clusters but used in one: a *specialist* anti-join
for classes of officials with disclosure regimes, not the generalist move the seed taxonomy assumed.
**Mechanics:** Reconstruct the official's benefit ledger from the outside — benefactors' registered assets (tail
numbers, vessels, parcels), movement data, staff/vendor testimony, geotagged photos, protective-detail logistics
— then anti-join every dated benefit against the disclosure filings. Disclosed items prove the channel works;
the subject's own earlier filings of similar benefits (**prior-disclosure-precedent-diff**) defeat the ignorance
defense.
**Minimum data:** the disclosure corpus for the official class; benefactor asset registries; one placement source.
**Ithildin mapping:** query_courtlistener `disclosures` (judicial financial disclosures — already wired),
ingest_faa (tail numbers), query_property (parcels), ingest_propublica_disclosures (Trump appointees). GAP:
flight-movement history (ADS-B) — registration alone doesn't place the asset; congressional eFD/PTR corpus.
**Failure modes:** hospitality exemptions genuinely covering some benefits (know the rule's vintage — the
personal-hospitality exemption was itself engineered); presence ≠ payment (confirm who paid).
**Exemplars:** [Thomas and the Billionaire](https://www.propublica.org/article/clarence-thomas-scotus-undisclosed-luxury-travel-gifts-crow);
[Alito/Singer](https://www.propublica.org/article/samuel-alito-luxury-fishing-trip-paul-singer-scotus-supreme-court).

### 11. constructed-interaction-audit (platform probes)
**Observed:** ~7 stories / 2 clusters.
**Mechanics:** When the subject is a live commercial interface, evidence is *manufactured, not found*: buy the ad
containing the illegal exclusion; request quotes from many ZIPs with a fixed persona; run the eligibility-matching
synthetic shopper through the funnel logging every screen. Controlled variation (paired probes differing in one
protected attribute) converts the platform's responses into a dataset proving its decision rule from outside the
black box. Force multipliers: **remediation-audit** (re-run the identical probe after the announced fix) and
**mystery-shopper price fixing** (same product, different demographics).
**Minimum data:** none preexisting — an account, a small budget, a variant matrix, rigorous logging (receipts,
screenshots, timestamps).
**Ithildin mapping:** requires explicit human sign-off (ethics/ToS/legal exposure) — emit as human_actions,
never auto-execute; browser tooling can *prepare* variant designs and archive results.
**Failure modes:** probe designs that confound variables; platform A/B noise mistaken for discrimination
(replicate over time); entrapment-adjacent designs — ProPublica publishes the full probe protocol.
**Exemplars:** [Facebook ethnic-affinity ad exclusion](https://www.propublica.org/article/facebook-lets-advertisers-exclude-users-by-race);
[Tiger Mom Tax](https://www.propublica.org/article/asians-nearly-twice-as-likely-to-get-higher-price-from-princeton-review);
[TurboTax dark patterns](https://www.propublica.org/article/turbotax-just-tricked-you-into-paying-to-file-your-taxes).

**Cross-outlet (F8, instrument dialect):** The Markup is this card's richest exemplar set — controlled
input/output differentials 5/10 in platform work (fresh-inbox Gmail placement, Keyword Planner identity seeds,
Instagram visibility experiments), adversarial-submission bypass (same product, altered metadata, different
gate result), matched-hypothetical rule testing (benefit-eligibility probes across jurisdictions), and the
consent-branch invariant (accept vs decline flows compared on identical dummy accounts — the decline path
transmitting anyway IS the finding). All instrument-built class (a), but check runnable-today: 3 of 6 platform
probes are degraded (layout parsers obsolete, API surfaces closed). ICIJ physical analog: blind DNA tests
binding retail labels to species ground truth (class a). See also cards 40/41 for the two Markup sub-moves
minted as standalone cards.

### 12. beneficiary-reverse-engineering (rule → who wins)
**Observed:** ~7 story-uses / 3 clusters (incl. the eligibility-recompute variants).
**Mechanics:** Run the rule backwards. Diff successive drafts of statutory or regulatory text to isolate inserted
language, convert the insertion into a predicate describing exactly who newly qualifies, then search
beneficiary-side data for matching entities (**legislative-diff-to-beneficiary**). For place-based subsidies:
recompute every designated unit's eligibility from the primary statistical source, diff versions of the
designation list to catch quiet insertions, and map parcel ownership inside designated units by single-owner
concentration (**boundary-drawn-for-beneficiary**). Overlay donor/lobbying timelines on the insertion window.
**Minimum data:** ≥2 versions of the rule text (or designation list); any beneficiary-side dataset.
**Ithildin mapping:** query_federal_register + govinfo (rule versions), query_usaspending (beneficiary side),
query_property + registries (parcel ownership), query_fec (influence overlay). The platform's ISAP V
ceiling-deletion finding is this exact pattern on contract mods.
**Failure modes:** predicates matching broad classes (the narrower the matching class, the stronger the carve-out
inference); drafts that never took effect; coincidental qualification.
**Exemplars:** [199A eight words → Bechtel](https://www.propublica.org/article/secret-irs-files-reveal-how-much-the-ultrawealthy-gained-by-shaping-trumps-big-beautiful-tax-cut);
[OZ designations](https://www.propublica.org/article/trump-inc-podcast-one-trump-tax-cut-meant-to-help-the-poor-a-billionaire-ended-up-winning-big).

### 13. dormant-public-model-operationalization
**Observed:** 3 stories / 2–3 clusters.
**Mechanics:** Regulators possess risk models and screening datasets built for internal triage and never
operationalized where harm is experienced (EPA's RSEI; FEMA flood maps; OSHA targeting). Obtain the model's
outputs or inputs+method, run it at full resolution, perform the aggregation the agency skips (cumulative,
cross-facility, multi-year), and join the risk surface to population layers. The finding is double: the harm
map, and proof the agency could have produced it and didn't.
**Minimum data:** the agency model or self-reported microdata with geo keys; a population join layer.
**Ithildin mapping:** GAP: EPA RSEI/TRI/ECHO family — nothing EPA-side exists on the platform; census layer also
a GAP. The pattern generalizes to any regulator's "screening tool" found in budget docs, IG reports, FOIA logs.
**Failure modes:** screening models aren't measurement — label estimates, state bias direction; the agency will
disown its own model under scrutiny (ProPublica pre-validated with former agency insiders).
**Exemplars:** [Poison in the Air / Sacrifice Zones](https://www.propublica.org/article/toxmap-poison-in-the-air);
[The Great Climate Migration (commissioned variant)](https://features.propublica.org/climate-migration/model-how-climate-refugees-move-across-continents/);
[EITC audit map](https://projects.propublica.org/graphics/eitc-audit).

### 14. plaintiff-frequency-inversion
**Observed:** 3 stories / 1 cluster; high transferability.
**Mechanics:** Invert the docket: instead of asking who gets sued, rank *filers*. A single plaintiff with
four-digit annual filing counts in one county is an industrial operation wearing a legal process as a collections
department. Resolve top filers through registries and 990s — the sharpest variant intersects the two populations
(a nonprofit hospital suing its own employees). Attach **procedural-artifact-forensics**: count contempt orders,
bail-in-civil-cases, garnishments, lis pendens as instruments per filer.
**Minimum data:** bulk civil dockets with party names + case type; registry/990 resolution for filer identity.
**Ithildin mapping:** query_state_courts + county docket tools (bulk acquisition), query_990 (nonprofit filers),
registry_address_index (filer resolution). Buildable as a standing screen on any docket corpus the platform holds.
**Failure modes:** filer-name fragmentation (one operation, many entity names — resolve before ranking);
volume ≠ abuse without the process-artifact layer.
**Exemplars:** [Methodist Le Bonheur](https://www.propublica.org/article/how-nonprofit-hospitals-are-seizing-patients-wages);
[The Color of Debt / So Sue Them](https://www.propublica.org/article/debt-collection-lawsuits-squeeze-black-neighborhoods);
[Coffeyville](https://features.propublica.org/medical-debt/when-medical-debt-collectors-decide-who-gets-arrested-coffeyville-kansas).

### 15. entity-genealogy-screen (age, formation, first-filing)
**Observed:** ~4 story-uses / 2 clusters.
**Mechanics:** An entity's registry lifecycle is a fraud clock, and it runs in both directions. Screens:
`[procurement]` award recipients whose identifier has zero prior history (**first-time-vendor flag**);
`[procurement]` **formation-date-vs-award-date** — flag both tails: a short gap (a fresh entity, illustratively
<90 days, date the threshold to the program) and, more productively at procurement base rates, a **dormancy
gap** (an entity aged >3 years with zero prior federal history, then a large ceiling — the aged shell is better
tradecraft than the fresh one); `[nonprofit]` **new-entity-first-filing-watch** (a new trust/nonprofit whose
*first* filing shows 8–10-figure revenue matching a contemporaneous M&A deal); **officer-succession-registry-
diff** (control handoffs timed against corporate events). State the lookback bound and which date you are using
(state incorporation vs SAM entity-start vs SAM registration — they diverge by years). The flag alone is
near-useless at agency base rates: **the required second stage is the cross-tab** against sole-source/urgency
authority, offers-received, and category mismatch, which sorts nominees into anomalous, explained-by-authority,
and ordinary competed-vehicle winners.
**Minimum data:** the award/filing stream with a stated lookback + incorporation registry with dates + a
base-rate denominator (how many first-time vendors a normal period produces) + officer-of-record data, which is
what actually resolves a nominee. All identifiers the entity has used, not one.
**Preconditions:** FPDS and query_texas are keyless. query_wyoming/query_nevada-class registries need the Node
browser helper. BLOCKED as of 2026-07-29: Delaware/OpenCorporates-routed lookups (OPENCORPORATES_API_KEY
returns HTTP 401); ingest_maryland needs manual reCAPTCHA; no Virginia adapter exists.
**Ithildin mapping:** query_fpds UEI search with --output for the history leg (it returns no competition
fields — take extent-competed/offers from query_usaspending or a census extract; and it currently drops IDV
entries to nulls, so re-read titles before scoring a zero — infra #223-adjacent chip filed). The registry leg
**routes by state** — query_texas (formation date + officers), query_wyoming (browser helper), Delaware via
OpenCorporates (credentialed), ingest_florida/ingest_newyork/ingest_colorado/ingest_dc (bulk, local);
query_registry only searches jurisdictions already ingested — check its jurisdictions listing before assuming
coverage. GLEIF gives LEI-registration dates, not incorporation dates, and name-collides across countries —
not a formation-date source. query_990 first-filings for the nonprofit variant.
**Failure modes:** **identifier multiplicity is the primary false-positive engine** — one entity can hold
several UEIs with non-overlapping eras (validated on a control: a 44-year incumbent's history split cleanly
across two UEIs), so re-run every zero-history hit on vendor name and parent identifier before it counts; JV
shells and new subsidiaries of experienced parents look new (officer-of-record disproves it in one call); shelf
companies defeat naive formation dates *and* are themselves a signal; emergency and treaty contexts
legitimately produce new vendors (public-interest vs urgency authority codes distinguish them); parser nulls
and silent paging truncation both manufacture false "zero history". The flag nominates, the principal's history
convicts.
**Validated:** 2026-07-29 against the DHS census + live FPDS — 18/18 concordance with the independently derived
flag, 0 false positives on 4 incumbent controls; the dormancy tail fired on 6/12 vendors vs 1/12 for the
<90-day screen. Memo: [_validation/card15-entity-genealogy.md](_validation/card15-entity-genealogy.md).
**Exemplars:** [COVID first-time contractors](https://www.propublica.org/article/a-closer-look-at-federal-covid-contractors-reveals-inexperience-fraud-accusations-and-a-weapons-dealer-operating-out-of-someones-house);
[Marble Freedom Trust](https://www.propublica.org/article/dark-money-leonard-leo-barre-seid).

### 16. statutory-parameter-screen (impossible values, cap clustering)
**Observed:** 2 core stories / 2 clusters (Thiel; PPP), plus one arguable analog (hospice cap-proximity churn).
Ghost-recipient and address-colocation checks are additional tests on the PPP story, not additional stories.
**Mechanics:** Legal instruments have hard parameters — contribution caps, benefit maxima, eligibility
ceilings. Two screens, and which one is available depends on *where the cap is enforced*. (a)
**impossible-value-vs-legal-limit** — only fires where the cap is *self-reported* rather than machine-enforced
at entry: a wrapper whose observed contents could not have arisen from compliant inputs (5 billion USD in a
2K-per-year Roth) proves a non-market entry event without observing it. Where the cap is enforced at
origination (PPP's E-Tran ceilings; most benefit-disbursement systems) this screen returns exactly zero and is
not evidence of compliance — substitute a **derived cap** (a ceiling that follows from a composite of held
fields rather than the program maximum, e.g. a one-employee Schedule C filer above 2.5 × 100,000/12) and treat
exceedances as data-quality or eligibility-misstatement nominations, not proof. (b) **benefit-cap-clustering**
— mass points *near* statutory maxima betray inputs reverse-engineered from the cap. Screen a **band**, not a
point: the observed mass sits at the filer's or originator's rounding of the parameter, not at the parameter.
Enumerate **every** parameter in the program (sector- and tranche-conditional ones included) and screen each;
score the spike by its ratio to adjacent bins on both sides, then decompose the at-cap population by
originator, entity type, and month before interpreting. Pair with **ghost-recipient checks** (recipients absent
from registries *legally required to contain their entity type* — filter to registerable forms first) and
**address-colocation** (always against the full-population colocation base rate, with commercial
registered-agent addresses excluded).
**Minimum data:** instrument-level values **plus, for each value, the fields that determine which parameter
applies** — entity/beneficiary type, sector code, tranche/draw discriminator, origination date, originator. The
statutory parameter itself, with its derivation and effective-date range, is authored input (the platform holds
no cap table). For the paired tests: a registry with bulk coverage of the relevant jurisdiction, an address
field, and a control population for measuring match error. *PPP instantiation (verified): caps = first-draw
10,000,000; second-draw 2,000,000; sole-proprietor 100,000/12 × 2.5 = 20,833.33 (both draws); second-draw
NAICS-72 100,000/12 × 3.5 = 29,166.67. Screen the band [cap − 40, cap], not the point.*
**Control:** the same screen run on a matched population where the signal should be absent — for cap
clustering, the same entity types outside the cap band; for the registry check, entities whose type is legally
required to be registered but which are *not* at the cap (this measures the matcher, not the subject); for
colocation, the colocation distribution of the full jurisdiction. Report the screen's lift over its control,
never its raw rate.
**Ithildin mapping:** the local PPP parquet via query_ppp sql with --output (11,365,188 PPP/PPS loans, 2020-04
→ 2021-07; full-scan aggregates in under a second). **No EIDL data is held** (processing methods are PPP/PPS
only) — do not plan an EIDL leg without ingesting it. Registry nonexistence via the root registry.db (the
data/ and datasets/ stubs are empty) — single-selector CLI, so bulk anti-joins need a DuckDB read-only ATTACH;
bulk depth is **Florida only** (~5.99M entities; every other jurisdiction under 300 rows — infra #224).
Recipient-side colocation is a plain GROUP BY on the normalized address; registry-side colocation depends on
the address-index sidecar, which fails closed when stale (#224). Generalizes to ERTC, FEMA IA, crop insurance,
state relief. GAP: a dated statutory-parameter table.
**Failure modes:** legitimate cap-seeking — caps attract honest maximizers, and on PPP the at-cap band is ~12%
of the whole book, so the cluster's *existence* is not the finding. Parameter histories change: date the cap
and cut by period (PPP's first-draw at-cap share ran 2.4% in 2020-04 and 32.8% in 2021-05 — two eligibility
regimes in one file). **Rounding is per-originator** (20,833.00 / 20,832.00 / 20,833.33 are one cap through
three lenders' arithmetic — screening one literal silently selects one lender's book). **Registry absence is
mostly matcher error, not ghost status** (on a must-be-registered control, exact normalized-name matching still
reported 58.7% absent — raw absence is uninterpretable without the control). **Colocation needs its own base
rate and a registered-agent exclusion** (at-cap PPP loans measured *less* colocated than baseline, 0.16% vs
0.90%, and the top cluster was a commercial agent address hosting 3,787 entities). Currency literals in shell
contexts lose digits under zsh — the platform's documented papercut; this card is the most exposed to it.
**Validated:** 2026-07-29 against the local PPP parquet — the cap mass point replicated at 65× adjacent-bin
density (1,206,127 loans in the cap band); both paired checks required the Control field to avoid false
findings. Memo: [_validation/card16-statutory-parameter.md](_validation/card16-statutory-parameter.md).
**Exemplars:** [Lord of the Roths](https://www.propublica.org/article/lord-of-the-roths-how-tech-mogul-peter-thiel-turned-a-retirement-account-for-the-middle-class-into-a-5-billion-dollar-tax-free-piggy-bank);
[PPP fake farms](https://www.propublica.org/article/ppp-farms).

### 17. authority-validity-audit
**Observed:** 3 stories / 1 cluster (criminal justice); generalizes widely.
**Mechanics:** For each enforcement action in a bulk ledger, verify the legal and physical predicates actually
exist: the charged statute exists and applies (Rutherford County jailed children for a crime that doesn't exist),
the required infrastructure exists (pedestrian tickets requiring signal pairs that aren't there — checkable via
imagery), a conviction underlies the punishment (nuisance-abatement defendants never convicted). Generalizes to
billing-code validity (upcoding), fee-schedule conformance, license-condition enforcement.
**Minimum data:** enforcement ledger with statute/code fields and locations; the authoritative code table;
imagery or docket access for predicates.
**Ithildin mapping:** query_state_courts (charge codes vs statute tables), Street View-class imagery is manual;
CMS code tables for the billing variant.
**Failure modes:** code-table vintage mismatches; local ordinances not in state tables; predicates that changed
since the enforcement date.
**Exemplars:** [Kids of Rutherford County](https://www.propublica.org/article/black-children-were-jailed-for-a-crime-that-doesnt-exist);
[Walking While Black](https://features.propublica.org/walking-while-black/jacksonville-pedestrian-violations-racial-profiling);
[Nuisance abatement](https://www.propublica.org/article/nypd-nuisance-abatement-evictions).

### 18. missingness-as-signal (undercounts, zeros, data voids)
**Observed:** ~4 story-uses / 3 clusters.
**Mechanics:** Treat the absent record as the finding. Three forms: **two-ledger undercount** (mandated
self-reports vs an independent estimate — FBI hate-crime counts vs NCVS victimization); **zero-report anomaly**
(rank reporting units per-capita; large agencies reporting zero are flags, and mapping them is publishable);
**regulatory-data-void** (a transparency statute mandates collection that was never operationalized — the
50-state canvass documenting that no one knows insurers' denial rates IS the story). Discontinued data series
and "unknown"-heavy fields are affirmative flags.
**Minimum data:** official counts by reporting unit; any independent proxy; population denominators.
**Ithildin mapping:** search_log discipline (the platform's own missingness ledger), source_report for dead
sources; FOIA-refusal documentation as evidence (query_muckrock). Note CLAUDE.md methodology point 5 — this card
is its operationalization.
**Failure modes:** genuine zero-incidence units (small populations); proxy measures with different definitions;
survey vs administrative-count gaps that are definitional, not concealment.
**Exemplars:** [Documenting Hate](https://projects.propublica.org/graphics/hatecrime-map);
[Uncovered: "No One Knows"](https://www.propublica.org/article/how-often-do-health-insurers-deny-patients-claims);
[Lost Mothers](https://www.propublica.org/series/lost-mothers).

**Cross-outlet (F4):** the strongest wave-2 confirmation of any card. ICIJ: missingness-as-signal is the TOP
aid-cluster move (6/10 — missing outcome files clustering on highest-risk World Bank projects; the $20.4B
unidentified-vendor bucket ranked as a finding; trainees with no vetting records) and the R12 FOIA-denial
doctrine (a denied landing-database request changes the dependency class — the denial is evidence). OCCRP:
institutional non-use gaps 4/10 (IMI alerts never used; procurement black holes). The Markup: registry
missingness filled by bounded surveys; unused-process-data gaps. All-outlet doctrine: log expected-but-absent
records as structured findings with their own distribution.

### 19. ground-truth-verification (count the deliverable)
**Observed:** ~4 story-uses / 2 clusters (+ field observation as "universal closer" in a third).
**Mechanics:** Independently reconstruct the outcome the subject claims. The Red Cross claimed 130,000 Haitians
housed; counting the actual homes built found six. Retest the evidence (lab re-analysis of drug-test convictions);
visit the site (test-tube factory shipping soda bottles); attend the auctions. One physical observation repeatedly
converted statistical anomalies into publishable findings — the cheapest decisive step in the corpus.
**Minimum data:** the claimed output figure + any independently countable trace of the real output.
**Ithildin mapping:** mostly human_action leads (site visits); satellite/imagery variants partially automatable.
GAP: remote-sensing time-series (Landsat) for the land-change variants.
**Failure modes:** partial visibility (you can count what's visible, not what's claimed elsewhere); definitional
games ("supported" vs "built") — force the subject to define the unit before comparing.
**Exemplars:** [Red Cross Haiti six homes](https://www.propublica.org/article/how-the-red-cross-raised-half-a-billion-dollars-for-haiti-and-built-6-homes);
[Fillakit](https://www.propublica.org/article/the-trump-administration-paid-millions-for-test-tubes-and-got-unusable-mini-soda-bottles);
[Busted retests](https://www.propublica.org/article/common-roadside-drug-test-routinely-produces-false-positives).

**Cross-outlet (F13):** OCCRP direct physical/current-status checks 3/10 (test purchases of Uighur-made PPE
with packaging as evidence; hospital equipment inspection; doctors verified actively practicing) and
hard-identifier chain-of-custody (container numbers, serials, tax stamps tying physical items to paperwork).
ICIJ: substance-gap field tests 5/33. The Markup: output-to-observed-outcome validation — predictive-policing
forecasts joined to later actual crime on type/place/time (~0.5% success), the algorithmic version of counting
the deliverable (class a, from obtained prediction logs + public crime data).

### 20. grant-chain-tracing with alias resolution
**Observed:** 4 stories / 1 cluster (dark money) + pass-through variants in gov-spending; platform-native.
**Mechanics:** Build the directed graph from 990 Schedule I grants reconciled against recipients' reported
revenue; resolve disregarded-entity LLC/DBA grant names to parents via registries and footnotes; score hubs by
throughput/program-expense ratio, address type (P.O. box), officer-vendor fee overlap, and election-cycle timing.
The hub with maximal throughput and minimal substance is the operational center. The **pass-through-fee-stacking**
variant reconstructs the full subaward chain and computes cumulative per-layer extraction vs the headline
overhead claim.
**Minimum data:** 990 e-file grant schedules for 2+ tiers; registry access for alias resolution; terminal-node
spending data.
**Ithildin mapping:** trace-grants skill + query_990 + graph_tools — this is the platform's most mature
ProPublica-parallel capability; ingest_990_xml for Schedule I depth.
**Failure modes:** fiscal-sponsorship structures mimicking conduits legitimately; year-boundary mismatches
between grantor and grantee reporting; aliases that never resolve (report as unresolved, don't guess).
**Exemplars:** [The Dark Money Man / CPPR](https://www.propublica.org/article/the-dark-money-man-how-sean-noble-moved-the-kochs-cash-into-politics-and-ma);
[Red Cross Haiti fee stacking](https://www.propublica.org/article/how-the-red-cross-raised-half-a-billion-dollars-for-haiti-and-built-6-homes).

**Cross-outlet (F11):** flow-chain reconstruction is OCCRP's core competency — 18/30 canon uses (source →
layering → beneficiary/asset ordering), flow-to-asset joins 4/11 (money/credit followed into capital, property,
collateral, then rescue/transfer events). ICIJ: RULE-TO-FLOW-MAP 6/33 (treaty/tax effects attached to
transaction edges vs the direct-route counterfactual). Dependency warning from the access-substitution
analysis: the decisive transaction legs are the single most leak-dependent element in both registry outlets —
public endpoints (deeds, filings) verify; private ledgers generate.

### 21. composition-ratio-screen (mills and self-dealing)
**Observed:** ~5 story-uses / 2–3 clusters.
**Mechanics:** An organization's spending composition betrays its real purpose. **Fundraising-mill ratio**:
programmatic output ÷ total spending < ~5%, residual concentrated in professional-fundraiser fees — then cluster
flagged entities on shared treasurers, accountants, vendors, processors, addresses, and web templates to reveal
one enterprise wearing many sympathetic masks. **Related-party price benchmarking**: nonprofit/committee spend
routed to officer-linked vendors at above-market rates (registry join + a price comparable converts overpricing
into self-dealing; contemporaneous internal dissent converts it into knowledge).
**Minimum data:** committee/org-level receipts and disbursements with vendor/treasurer fields; registries for
officer overlap; one price benchmark for the related-party variant.
**Ithildin mapping:** query_fec (scam-PAC screens ran on this platform), query_990 Schedule L/R, registry joins;
the tech-right profile's fundraising-vendor analyses are this card in production.
**Failure modes:** startup-year ratios legitimately skewed; joint-cost accounting hiding fundraising in
"education"; market-rate defenses (get real comparables, not list prices).
**Exemplars:** [Scam PACs](https://www.propublica.org/article/conservative-majority-fund-political-fundraising-pac-kelley-rogers);
[Trump inaugural × Trump hotel](https://www.propublica.org/article/trump-inc-podcast-trumps-inauguration-paid-trumps-company-with-ivanka-in-the-middle);
[True the Vote insiders](https://www.propublica.org/article/true-the-vote-donations-irs-engelbrecht-phillips).

### 22. subject-artifact-forensics (their own output testifies)
**Observed:** ~6 story-uses across 4 reports (TurboTax is double-clustered in two of them; ~5 unique stories).
**Mechanics:** The subject's own published surfaces carry confessions. **Vendor-brag-mining**: sales decks,
earnings calls, user conferences, patents, and case studies document the mechanism (pooled nonpublic competitor
data + above-market outperformance + adoption share = the RealPage cartel story assembled from marketing).
**Site-forensics / compliance-artifact inspection**: robots/noindex directives on obligated pages beside polished
revenue paths; segmentation variable names in page code (NONFFA); the paid/free asymmetry within one operator
supplies intent. **Procurement-justification text-mining**: FPDS free-text fields as a confession layer ("ordered
by the White House"). **Obstruction-as-confirmation**: the subject breaking your instrument is itself evidence.
**Minimum data:** the subject's public web/filing surfaces + an archive for historical states.
**Ithildin mapping:** Wayback CDX tooling, query_edgar full-text (earnings calls/filings), analyze_git_repo,
URLScan/crt.sh for infrastructure artifacts, query_fpds free-text fields.
**Failure modes:** marketing puffery vs operative claims (corroborate with outcome data); web artifacts change
silently (archive immediately, cite the snapshot).
**Exemplars:** [RealPage YieldStar](https://www.propublica.org/article/yieldstar-rent-increase-realpage-rent);
[TurboTax robots.txt](https://www.propublica.org/article/turbotax-deliberately-hides-its-free-file-page-from-search-engines);
[FEMA no-bid justification](https://www.propublica.org/article/the-white-house-pushed-fema-to-give-its-biggest-coronavirus-contract-to-a-company-that-never-had-to-bid).

**Cross-outlet (F15):** ICIJ's coded-document semantics 3/10 — the tobacco "DNP/GT/transit" dialect decoded by
clustering unexplained internal terms against shipment ledgers and enforcement events until operational meaning
stabilized (litigation-archive substrate, class a); template/control clustering 5/33 (shared provider
boilerplate converting cases into institutional pattern). OCCRP: repeated court-template clustering across
laundromat judgments. The Markup: mutated-vocabulary probes (paired/misspelled blocklist terms revealing
moderation semantics). Generic rule: a stable in-house term absent from public materials + co-occurring with
quantities/routes = a codebook worth cracking; require ≥3-document operational consistency before assigning
meaning.

### 23. cross-jurisdiction-codification (the 50-state table)
**Observed:** 3 story-uses / 2 clusters (workers' comp; the two healthcare statute-diff instances). The
fracking "state patchwork" is a cousin (case-accumulation against a federal exemption), not a codification
table — excluded here.
**Mechanics:** Take one standardized case — a lost arm, an unemployment claim, a records request — and
price/process it through every jurisdiction's statutory formula, verifying computations with local
practitioners. The single comparable table exposes spatial outliers; re-run over legislative history, it exposes
synchronized erosion waves that trace to model-bill campaigns (bill-text similarity clustering identifies
coordinated drafting).
**Minimum data:** statute/benefit-schedule texts (open); amendment histories with dates.
**Ithildin mapping:** govinfo/state-code retrieval is manual today; event_timeline for erosion waves;
cross-jurisdiction property/court routers (query_property, query_state_courts) embody the comparison
infrastructure for records access.
**Failure modes:** formula inputs that aren't comparable across states (verify with practitioners — ProPublica
did); nominal-vs-real value drift over long histories.
**Exemplars:** [Demolition of Workers' Comp](https://www.propublica.org/article/the-demolition-of-workers-compensation);
[fracking regulation patchwork](https://www.propublica.org/article/buried-secrets-is-natural-gas-drilling-endangering-us-water-supplies-1113).

### 24. captive-population-extraction-screen
**Observed:** finding-family in 24 stories / 6 clusters; as a composite *screen*, assembled from 3 clusters.
**Mechanics:** Wherever a payer funds a per-diem or fee-per-event service for a population that cannot exit
(patients, prisoners, tenants, debtors, temp workers), extraction structures evolve. Composite screen: payer
generosity × chain/PE concentration; **enforcement-gap ratio** (deficiencies ÷ sanctions); **outcome-inversion
metrics** (live-discharge rates where terminality is the eligibility premise; "too-well" patients in therapy);
registry red flags (license address colocation, rapid churn, owners with no operating history); **fines-to-
insolvency join** (assessment ledger → bankruptcy/garnishment/suspension systems, with any price hike as a
natural experiment); **captive-rate-ratio** (incident rates for the subordinate tier vs the standard tier within
matched work — temp workers at 6x).
**Minimum data:** provider/operator registry with addresses and ownership; payer utilization aggregates or
assessment ledgers; inspection or incident records; the benefit's eligibility rule.
**Ithildin mapping:** query_medicare + Medicaid T-MSIS, query_990, registry_address_index, query_state_courts
(garnishment/bankruptcy legs); directly relevant to detention-medical and shelter-contract investigations on
this platform. GAP: CMS Care-Compare/deficiency data; OSHA severe-injury; workers' comp claims microdata.
**Failure modes:** acuity mix explaining outcome differences (match populations first); per-diem ≠ predatory
without the inspection/outcome leg; PE ownership as prior, not proof.
**Exemplars:** [Hospice Hustle](https://www.propublica.org/article/hospice-healthcare-aseracare-medicare);
[Temp Land](https://www.propublica.org/article/the-expendables-how-the-temps-who-power-corporate-giants-are-getting-crushe);
[Ticket-debt spiral](https://www.propublica.org/article/debt-collection-lawsuits-squeeze-black-neighborhoods).

### 25. guest-manifest-reconstruction
**Observed:** 4 stories / 1 cluster; generalizes to any closed-venue presence question.
**Mechanics:** Rebuild who-was-there at closed venues from the periphery: staff and vendor interviews (chefs,
pilots, caterers, lodge employees), geotagged and background-of-photo artifacts, hunting/fishing licenses,
marina and airport logs, protective-detail and advance-logistics records (**protective-detail-records-
reconstruction** — security agencies' files are a shadow itinerary), embroidered/branded physical objects dating
attendance. Then join reconstructed presence against the subject's obligations (disclosure, recusal) or claimed
whereabouts.
**Minimum data:** venue + date window; any two independent periphery sources.
**Ithildin mapping:** largely human-sourcing (human_actions); FOIA templates for protective details (USMS-class
records); Maigret/social OSINT for artifact discovery; the kabasshouse flight-log corpus work is the platform's
own exemplar of manifest reconstruction.
**Failure modes:** photo dating errors (EXIF stripped — corroborate with two artifacts); staff recollection
drift; licenses proving presence in a state, not at the venue.
**Exemplars:** [Thomas/Crow travel](https://www.propublica.org/article/clarence-thomas-scotus-undisclosed-luxury-travel-gifts-crow);
[38 vacations](https://www.propublica.org/article/clarence-thomas-other-billionaires-sokol-huizenga-novelly-supreme-court);
[Koch donor events](https://www.propublica.org/article/clarence-thomas-secretly-attended-koch-brothers-donor-events-scotus).

---

## Acquisition moves (not detection signatures, but repeatedly load-bearing)

These recurred across clusters as the step that *obtained* the decisive records (full playbooks:
[propublica-ontology.md §Acquisition](propublica-ontology.md)):

- **secrecy-repeal arbitrage** — when a confidentiality statute falls, file day-one for the entire historical
  archive before litigation re-seals it (the NYPD Files' 12,000-officer database).
- **request the government's copy** — proprietary systems' outputs are public records in the government's hands
  (COMPAS scores via FOIA when the algorithm itself was a trade secret).
- **settlement-mandated-disclosure harvest** — consent decrees and settlements force periodic disclosures
  nobody reads; harvest them as structured data.
- **watchdog-intermediated documents** — Fix the Court, Documented, Property of the People as standing document
  brokers whose productions are citable primary records.
- **defunct-institution docket-mining** — bankruptcies and receiverships dump internal records (tuition ledgers,
  donor files) into public dockets.
- **directory-diffing** — archive a public roster on a cadence and diff snapshots to measure what the
  institution won't report (workforce purges).
- **orphan-dataset adoption** — take custody of dying civic data assets (Sunlight's Congress API) and become
  the steward.
- **bulk-FOIA behind the anecdote** — every individual-harm story implies an administrative system logging all
  such cases; request the system, not the case.

## Wave-2 additions (reports 11–16: immigration, education/children, military/veterans, housing, democracy/elections, tribal — ~73 further coded stories)

Wave-2 agents coded with **no seeded taxonomy** (free-form tagging). Their independent re-derivation of the
Tier-1 families is the strongest validation this library has: the tribal agent invented "promise-ledger vs
performance-ledger reconciliation," the military agent "record-vs-record contradiction," the immigration agent
"official-claim vs primary-record diff" — all two-books-diff under new names; the housing and democracy agents
re-derived the enforcement-gap ratio ("2 benefit withholdings in 40 years," "1,200 bills/yr vs ~4 recusals/yr").

**Frequency updates to wave-1 cards** (clusters using the move, out of 14 coded clusters total):
two-books-diff → all 14; silo-join → 12 (adds two-stream joins, registry-vs-registry: "the government's left
hand documenting what its right hand denies" was housing's single richest vein); denominator-construction → 12
(adds mandate-horizon arithmetic: backlog ÷ own-reported throughput = a 600-year completion horizon at JPAC);
enforcement-gap-ratio → ~10 (adds the 214:1 allegations-to-discipline ratio, the dead-referral pipeline:
local misconduct findings joined by name to an inactive central licensing registry); named-cohort-tracing → 8
(adds roster-wise verification of a collective label — all 238 CECOT deportees checked person-by-person against
US and foreign record systems — and the gatekeeper career-trace); internal-rulebook-acquisition → 7 (adds
policy-text-as-scoring-standard: 40+ chokehold videos coded against CBP's own use-of-force policy; and
algorithm forensics — reading DOGE's contract-"munching" AI code, where identical repeated output values were
the hallucination fingerprint); constructed-corpus → 8 (Electionland institutionalized; mass callouts);
temporal-correlation → 8 (adds the law-to-asset clock from report-15: deeds acquired inside the
drafting-to-public-awareness window by drafter-connected parties); ground-truth-verification → 6 (adds single-case paper-trail replay —
re-running one MIA identification from held records to prove the system could have succeeded — and the
certification-theater audit with its policy-shock inflection read: a failure-rate step-change when scoring
tightens retroactively proves prior inflation); missingness-as-signal → 6 (adds the audit-from-below: sample
the zero-reporters in a central self-report collection and records-request their raw local logs — 66 expulsions
found where the state's collection showed 12); plaintiff-frequency-inversion → 3 clusters as
**channel-concentration inversion** (six activists filed 89% of 100,000 Georgia voter challenges — same move,
different channel); authority-validity-audit → 3 (education's standard-vs-record audits).

### 26. obligation-reconciliation (promise-ledger vs performance-ledger) — *new Tier 1*
**Observed:** ~11 stories / 2 clusters (tribal + housing), independently derived by both agents; the
census-predicted evidence classes (treaty/trust documents, REAC, LIHTC) all feed it.
**Mechanics:** A law, treaty, subsidy, or covenant creates a *quantified standing obligation* to a defined
beneficiary class; a separate operational system records what was actually delivered. The investigation is the
join. Variants: **conditioned-benefit anti-join** (recipients of a benefit vs the compliance register its
conditions require — NYC landlords taking 421-a tax breaks while 50,000 units were missing from rent
registration); **paper-entitlement vs physical delivery** (decreed water rights vs actual diversion records —
then trace who quietly consumes the undelivered residual); **mandate-vs-performance census** (every institution
subject to a duty, ranked by percent-complete — the NAGPRA database). "Ask who has ever lost the benefit; if
the answer is roughly nobody, run the join."
**Minimum data:** the obligation's text with quantities; the recipient/entitlement roll; the operational
delivery or compliance dataset; a joinable key (parcel, EIN, grantee ID).
**Ithildin mapping:** query_990 + query_usaspending (grant conditions), query_property (covenants/parcels),
query_federal_register (completion notices), event_timeline. GAP: HUD REAC/LIHTC, National NAGPRA DB.
**Failure modes:** obligations with genuine compliance lags; registries that under-record compliance rather
than over-record it (verify the register's own completeness first); pipeline-stage imprecision — define
exactly which legal stage the metric measures ("made available" ≠ "returned").
**Exemplars:** [NAGPRA compliance census](https://www.propublica.org/article/repatriation-nagpra-museums-human-remains);
[Chemehuevi water entitlement](https://www.propublica.org/article/chemehuevi-tribe-reservation-water-colorado-river-california);
[421-a tax breaks vs rent registration](https://www.propublica.org/article/affordable-housing-investors-loophole-rent-tenants);
[Living Apart (2 fund withholdings in 40 years)](https://www.propublica.org/article/living-apart-how-the-government-betrayed-a-landmark-civil-rights-law).

### 27. queue-forensics (timestamp gaps in benefit lines)
**Observed:** 2 core stories / 2 clusters (Promised Land; Stuck Kids) — the exact eligibility-vs-exit
detector — plus 1–2 broader time-to-event analogs (education's removal-to-termination duration rankings).
Both clusters produced timestamp-gap moves without a shared taxonomy, though under different tag names.
**Mechanics:** Queue-based systems log when a person becomes *eligible* and when they actually *exit*; the gap
distribution is the finding. Join applicant log to award log on person+date; compute wait durations and
person-days; price them at the payer's daily rate; geocode awardees and overlay demographics to test whether
winners resemble the intended beneficiary class; scan status fields for death markers (mortality-in-queue);
look for the unlegislated filter that actually orders the line (mortgage qualification on a program "for the
poor"). Education's variant: psychiatric clearance vs discharge, with the agency's own "beyond medical
necessity" table flagging its failures.
**Minimum data:** two administrative logs with a linkage key and timestamps; the per-diem cost; a census
overlay for the demographic test.
**Ithildin mapping:** date_normalize + event_timeline (the ISO-date layer), person_resolution for log linkage.
GAP: census/ACS overlay.
**Failure modes:** eligibility dates that get administratively reset; queue-order rules that are legal but
unpublished (get the rule before alleging skipping); survivor bias in who remains findable.
**Exemplars:** [Hawaiian homestead waitlist](https://www.propublica.org/article/hawaii-native-land-homesteads-department-of-hawaiian-home-lands);
[Stuck Kids](https://features.propublica.org/stuck-kids/illinois-dcfs-children-psychiatric-hospitals-beyond-medical-necessity/).

### 28. sworn-answer-registry-diff
**Observed:** 3 explicit stories / 1 cluster (democracy), plus one analog in housing (Living Apart's false
compliance certifications — coded there under obligation-reconciliation; counting it here is a stated family
merge). PPP ghost-recipient checks are the wave-1 cousin.
**Mechanics:** Every application containing yes/no certifications ("never debarred," "no related-party
interest," "no prior denials") implicitly names the registry that could falsify it. Enumerate the implied
registries and diff systematically. One false sworn answer converts a policy story into a legal-exposure story
and gives officials a nondiscretionary reason to act — New Jersey froze $260M on one checkbox.
**Minimum data:** the application text (records request); the external registries the certifications imply.
**Ithildin mapping:** query_sam (debarment), query_sec_enforcement, query_courtlistener (litigation history),
OpenSanctions, registries — the platform's standard stack IS the falsification layer; the move is reading
applications as claim sets.
**Failure modes:** certification wording with materiality qualifiers; registry lag; name-match false positives
on common principals.
**Exemplars:** [Holtec false certification](https://www.propublica.org/article/holtec-international-tax-break-application-false-answer-new-jersey-on-hold);
[PPP fake farms (registry-nonexistence variant)](https://www.propublica.org/article/ppp-farms).

### 29. stratified-outcome-delta (bargaining-power and severity strata)
**Observed:** ~5 stories / 2 clusters (immigration + military), independently derived.
**Mechanics:** In any mass of similar state-vs-individual transactions, build the case-level table and stratify
outcomes by an attribute the system claims not to see. Two load-bearing strata: **counterparty resources**
(represented landowners got 207% uplift on border-wall condemnations vs 33% for unrepresented — the state
exploiting bargaining asymmetry as policy) and **claim severity/cost** (a good-faith adjudicator denies weak
claims; a throughput- or profit-driven one contests the *costliest* — AIG protested ~half of serious-injury
contractor claims vs a fraction of minor ones, and appeal reversals ran ~75%). High reversal-on-appeal beside
high initial denial is the confirming second join.
**Minimum data:** case-level offer/outcome pairs + one stratum attribute; docket systems usually suffice.
**Ithildin mapping:** query_courtlistener/query_state_courts (case tables), financial_ratios logic for rate
comparisons; representation status is often inferable from docket counsel fields.
**Failure modes:** strata that proxy legitimate legal differences (injury complexity, venue); selection into
representation.
**Exemplars:** [The Taking](https://features.propublica.org/eminent-domain-and-the-wall/the-taking-texas-government-property-seizure/);
[Disposable Army](https://www.propublica.org/article/injured-war-zone-contractors-fight-to-get-care-from-aig-416);
[Army Chapter 10 separations](https://www.propublica.org/article/military-army-administrative-separation).

### 30. share-of-program-capture (ledger × relationship graph)
**Observed:** 3 stories / 1 cluster (democracy); the political-ethics analog of grant-chain tracing.
**Mechanics:** Take a discretionary public-benefit ledger (tax credits, grants, contracts, variances) and a
relationship graph around a hypothesized hub — ownership, board seats, kinship, and (the New Jersey
innovation) *clients of the hub's family's professional firms* counted as network edges. Compute the hub
network's share of total program value against a peer network **that is node-disjoint from the hub network —
verify disjointness (Jaccard ≈ 0) rather than assuming it; hubs in the same milieu routinely resolve to the
same network at depth ≥ 2** (Camden = 4× all other growth zones combined). **Calibrate with the
top-single-recipient share of the same ledger: a network share below the largest ordinary vendor's share is
not a finding.** Report the share at every depth from 1 to your chosen stop — the sensitivity curve is the
result; a single share is not. Aggravator: the program's rules were drafted by the network's own agents — get
the drafting correspondence. Weaker but records-request-free substitute: personnel flow between the awarding
office and the network's firms.
**Pre-registration:** fix, before computing: (i) the admitted edge types, (ii) traversal depth, (iii) the
denominator — the specific program, not the whole agency, and (iv) the value measure (awarded / obligated /
ceiling — procurement ledgers carry all three and they rank networks differently).
**Minimum data:** the complete award ledger with a hard recipient key (UEI/EIN); registry/board/lobbying edges
**typed by semantics, not domain, and carrying direction**; node-type labels sufficient to exclude program,
statute, and agency nodes from traversal; drafting correspondence via records requests.
**Coverage statement:** report, beside any share, the fraction of ledger dollars your graph can resolve to a
node — that fraction is the ceiling on any share you can claim (9.23% on the validation run: the binding
constraint, not the analysis).
**Ithildin mapping:** query_usaspending / query_fpds for ledgers; graph_tools neighbors/paths for traversal
(--profile, --output; paths lacks --output and neighbors lacks a rel-type filter — infra #223). **Edges are
the binding constraint, not the ledger:** `connections` is a hand-curated name-string graph with no UEI/EIN
key, and `relationship_type` encodes relationship *domains* (corporate/financial/political), not edge
*semantics* — equity stakes land in financial/funds while corporate also carries alumni and competitor
relations, so a literal ownership-only edge set can return an empty network while a widened one imports
competitors. Read edge descriptions before admitting a type, and budget an edge-construction pass before the
move is runnable. investigation.db is WAL — read-only auditing needs PRAGMA query_only=ON (sqlite3 -readonly
cannot open it). GAP: no UEI/EIN column on entities; no board_seat or client_of relationship type; no
node-type attribute on graph nodes.
**Failure modes:** edge definitions that gerrymander the "network" — pre-register the edge types, **then check
the pre-registered set actually returns relationships you know exist** (on a domain-typed schema the
disciplined set can exclude the real ownership edge and admit a competitor edge); programs legitimately
concentrated by design (compare against the statute's stated intent and the top single recipient's share);
**coverage bias** (a curated numerator over a complete denominator measures documentation effort as much as
capture); **peer non-independence** (overlapping networks cannot test each other — report pairwise Jaccard);
**tautological traversal** (if the graph holds the program, statute, or awarding agency as a node, every
awardee is one hop from every other — exclude them); **ceiling double-counting** (shared multi-award IDIQ
ceilings deduplicated before summing); **edge provenance** (a share computed over unverified edges is a claim
about assertions, not dollars — state the verified fraction).
**Validated:** 2026-07-29 against the DHS ledger × tech-right graph — literal execution returned a one-node
network/0.00% for a hub whose flagship firms hold $816.8M; with pre-registered parameters the hub network
measured 1.08% of the ledger at depth 2, below the private-detention peer (1.42%) and the top single vendor
(18.83%), at 9.23% graph coverage. Memo:
[_validation/card30-share-of-program.md](_validation/card30-share-of-program.md).
**Exemplars:** [The Real Bosses of New Jersey / Norcross network](https://www.propublica.org/article/george-norcross-democratic-donor-tax-breaks);
[Hidden Hands in Redistricting / REDMAP](https://www.propublica.org/article/hidden-hands-in-redistricting-corporations-special-interests).

### 31. shadow-authority-trace
**Observed:** 3 stories / 1 cluster (military/VA); generalizes to any captured institution.
**Mechanics:** Acquire correspondence/calendar corpora for an institution's leadership; extract all
counterparties; set-difference against the formal org chart and appointment records; rank outsiders by
officials' deference language ("for your review/approval," "as you directed") and by proposal-to-subsequent-
action match rate. The Shadow Rulers finding was not that Mar-a-Lago members had opinions — it was that
officials *reported to them in writing* and their personnel lists were executed. Dr. Orange is the slow
variant: one consultant's recommendations matched to four decades of adoptions, plus undisclosed funding.
**Minimum data:** FOIA-able email/calendar sets for named officials; a staff directory; a decision timeline.
**Ithildin mapping:** the platform's email-corpus tooling (search_emails, entity extraction) built for the
Epstein corpus does exactly this; graph_tools for counterparty ranking.
**Failure modes:** advisory contact that is disclosed and lawful (the finding is deference + execution +
non-appointment, not contact); deference language conventions varying by agency culture.
**Exemplars:** [Shadow Rulers of the VA](https://www.propublica.org/article/ike-perlmutter-bruce-moskowitz-marc-sherman-shadow-rulers-of-the-va);
[Dr. Orange](https://www.propublica.org/article/alvin-young-agent-orange-va-military-benefits).

### 32. self-contradiction-matrix
**Observed:** 1 explicit story (Drone War) inside the military cluster's 6-story record-vs-record family —
**below the 2-story bar as a standalone category**; retained as a named *variant* of two-books-diff (card 1)
for its unique zero-access property, not as an independent category. (Leahy is a recommendation-vs-decision
gap and Shadow Rulers an org-chart mismatch — same family, different mechanics.)
**Mechanics:** Collect every dated official statement about a single quantity (casualties, costs, counts),
each with its coverage window; test all pairs for joint logical possibility (interval vs cumulative,
monotonicity). The drone-figures story never adjudicated between government and NGOs — the government's
"about 30 in one year" and later "single digits total" impeached each other. External counts serve only as
bounding context. Works on opaque programs where no records access exists at all.
**Minimum data:** a statements archive with dates and scopes — nothing privileged.
**Ithildin mapping:** government_release_corpus + GDELT (statement streams), event_timeline for the windows;
reporting_corpus discipline (attributed claims with dates) is the storage layer.
**Failure modes:** definitional drift between statements (scope each quote precisely); paraphrase treated as
quote.
**Exemplars:** [Drone death figures](https://www.propublica.org/article/obama-drone-death-figures-dont-add-up).

### 33. protected-inventory-leak-detection
**Observed:** 2 stories / 1 cluster (housing); generalizes to any protected stock.
**Mechanics:** A legally protected stock (affordable units, controlled goods, preserved assets) leaks into the
open market — where sellers must advertise. The protected roster is a watchlist; marketplaces are the sensor.
Continuously match roster entries against commercial listing surfaces (fuzzy-matching names, addresses,
imagery when platforms mask locations), confirm in official records, and look for the second government
registry that *officially records the prohibited use* (hotel-tax certificates for protected residential
hotels rented as tourist rooms).
**Minimum data:** the protected-asset register; listing data; ideally the tax/licensing registry of the
prohibited activity.
**Ithildin mapping:** query_property (rosters), Wayback for listing archives; scraping legality per source.
**Failure modes:** listing-to-asset matching errors (confirm before naming); grandfathered exemptions.
**Exemplars:** [Checked Out (LA residential hotels)](https://www.propublica.org/article/how-la-failed-stop-landlords-turning-low-cost-housing-hotels).

### 34. prohibition-conformance screens (extends card 17)
**Observed:** +4 stories / 2 new clusters (education + housing) on top of card 17's base.
**Mechanics:** Two additions to the authority-validity family. **Banned-practice relay:** a practice prohibited
for institution A migrates to adjacent institution B the ban doesn't reach — schools barred from fining
students had police write the tickets at their request; detection = obtain both sides' records and join on
incident/person/date to show A initiating what B executes (a reform that "succeeds" on A's metrics while B's
volume rises is the cue). **Prohibition-window scan:** when law pauses an activity, the violation set is
computable — collect the activity stream, join to the covered-entity list, filter to the window (evictions
filed at CARES-covered parcels; HOA foreclosures through the moratorium's carve-out).
**Minimum data:** the prohibition's text and dates; both institutions' (or the covered list's) records; a join
key.
**Ithildin mapping:** query_state_courts (filing streams), event_timeline (windows), registries (coverage
lists).
**Failure modes:** coverage-list ambiguity (the CARES property list was itself the hard part); lawful
carve-outs mistaken for violations.
**Exemplars:** [The Price Kids Pay](https://www.propublica.org/article/illinois-school-police-tickets-fines);
[The Eviction Ban Worked](https://www.propublica.org/article/the-eviction-ban-worked-but-its-almost-over-some-landlords-are-getting-ready).

### 35. dead-platform-metadata-harvest
**Observed:** 1 investigation / 1 cluster (the Parler archive, multiple articles + a methodology essay) —
**below the 2-story bar**; retained as an acquisition/analysis variant pending a second coded instance. (The
Facebook lexicon census is the report's text-domain analog, not dead-platform metadata work.)
**Mechanics:** When a platform dies, purges, or leaks, its archive plus retained media metadata (GPS,
timestamps, device info) supports geofence × time-window reconstruction of physical events. The Parler
pipeline: ~1M videos → ~2,500 machine-filtered to the Capitol polygon and Jan 6 window → 500+ human-verified.
Human review is the conversion step from data dump to evidentiary archive; publish the verified corpus itself.
**Minimum data:** the archive; metadata extraction; a defined event polygon/window; reviewer capacity.
**Ithildin mapping:** the corpus-ingest + OCR/metadata pipeline generalizes; kabasshouse-style local corpus
with evidence_items provenance is the storage pattern.
**Failure modes:** stripped or spoofed metadata (verify a sample against visual content); archives of
contested provenance (document chain of custody).
**Exemplars:** [The Insurrection / Parler archive](https://projects.propublica.org/parler-capitol-videos/);
[the methodology essay](https://www.propublica.org/article/why-we-published-parler-users-videos-capitol-attack).

### 36. deed-chain-flip-detection
**Observed:** 2 stories / 2 clusters (housing + corporate-consumer cross-ref).
**Mechanics:** Same-parcel rapid resale at markup, seller-financed second leg, clustered by seller-entity
family: pull deed chains, compute holding periods and price deltas, flag < N-month flips with >X% markup where
the second leg is a contract-for-deed or wrap mortgage, then resolve seller entities to a common family
(shared agents/addresses). Detects predatory-acquisition mills feeding on distressed or unsophisticated
sellers/buyers.
**Minimum data:** deed/recorder chains with dates, prices, parties; entity resolution.
**Ithildin mapping:** query_property + county recorder tools + registry_address_index — among the most
directly runnable cards on existing infrastructure.
**Failure modes:** legitimate rehab flips (inspect permits/rehab spend); intra-family transfers at nominal
prices polluting price-delta stats.
**Exemplars:** [Contracts for deed (Sahan Journal partnership)](https://www.propublica.org/article/minnesota-attorney-general-investigation-contract-for-deed-real-estate);
[HomeVestors](https://www.propublica.org/article/ugly-truth-behind-we-buy-ugly-houses).

### 37. sanctioned-actor-migration-tracking
**Observed:** 3 stories / 2 clusters (education + healthcare's rebrand-persistence).
**Mechanics:** Follow disciplined actors — people or practices — across the jurisdictional seams their
sanction doesn't reach. People: teachers with local misconduct findings surfacing in new districts/states
(reconstruct the input stream from employers when the central registry is sealed; join by name to license
status and new employment). Practices: an enjoined algorithm redeployed under a new name where the settlement
doesn't apply (fingerprint the enjoined thresholds/scripts and scan sibling jurisdictions).
**Minimum data:** local adjudication records from a sample of reporting institutions; the public license/
employment surface; stable identifiers.
**Ithildin mapping:** person_resolution + name_aliases (identity threading is platform-native); GAP: state
licensure/discipline registries at scale.
**Failure modes:** name collisions (the platform's entity-resolution discipline applies); sealed records
creating survivorship illusions.
**Exemplars:** [Unfit to Teach](https://www.propublica.org/article/california-fired-teacher-sexual-harassment);
[EviCore rebrand-persistence](https://www.propublica.org/article/evicore-health-insurance-denials-cigna-unitedhealthcare-aetna-prior-authorizations).

## Cross-outlet additions (2026-07-29)

Minted from the ICIJ/OCCRP/Markup corpora where the mechanics are absent from cards 1–37. Same bar as the
original set: ≥2 independently cited stories, here additionally requiring ≥2 outlets or one outlet at ≥3 uses.

### 38. beneficial-control-rollup (nominal holders → resolved concentration)
**Observed:** ICIJ 3/11 extractives + GRAPH-PATH-RECONSTRUCTION 16/33 canon; OCCRP hidden-beneficiary/nominee
graph 9/11 state-capture + shared-infrastructure clustering 10/30 canon; ProPublica partial forms in cards
20/30.
**Mechanics:** Resolve every nominal holder of an allocation or asset ledger (quotas, licenses, contracts,
concessions, property, patents, aircraft) through parents, mergers, family ties, shared formation agents,
directors, addresses, and offshore vehicles — **as of the award/event date, not today** — then recompute
concentration and top-N share pre- vs post-resolution. The published concentration is the subject-controlled
number; the resolved concentration is the finding (ICIJ's exemplar: Chile's jack-mackerel quota, nominally
dispersed, resolved to eight groups holding 87%).
**Validated 2026-07-29 — runnable as a present-day sensitivity, BLOCKED as written.** Executed against the DHS
census (4,270 holders, $75.86B kept obligations). Nominal top-10 = 45.3207%; current-parent top-10 = 45.5998%
(+0.2791 pp, only 1.0054× the equal-size null mean). The card's *defining* promise — terminal control **as of the
award date** — returned exactly one admitted dated edge covering `$636,500`, leaving **99.999161% of dollars
historically unresolved**. Memo: `_validation/card38-beneficial-control-rollup.md`.
**Minimum data:** an allocation/asset ledger; a **hard identifier crosswalk** (UEI/EIN/CIK/LEI/registry number
with alias provenance — "entity identifiers" is too weak; name-only candidates require a reviewed rejected-pair
sample, and 3 of 13 exact-normalized registry matches were immediately false in validation); dated *and directed*
ownership edges; family or control links where corporate edges stop.
**Pre-registration (semantic control contract):** fix N, the value measure, the denominator, the holder key, the
event date, the equity/control threshold, the **direction convention**, an evidence/verification floor, the
traversal stop, a cycle/conflict rule, and joint-control treatment — before computing. **State explicitly: a
shared officer, formation agent, address, or family link generates a *candidate only* and does not move value
without a separate admitted control fact.** A registered agent serves thousands of unrelated firms; a shared
address may be a formation service; a minority stake is not control absent a voting-rights fact.
**Preconditions (hard gate, not a warning):** every admitted controller edge must carry `valid_from` (and
`valid_until` where applicable) or a dated filing/snapshot proving the relation at the event. **If dated coverage
falls below the pre-registered threshold, label the output `current-state sensitivity` and do not use the phrase
"as of award/event date."** Validation had 0 of 78 historically certified multi-holder clusters.
**Coverage statement (four mandatory rows):** report (a) identifier match, (b) unambiguous legal/accounting
parent, (c) external/beneficial controller, (d) historically effective controller — each by holder count, award
count, signed dollars, and gross absolute dollars. **Self-parent must not count as external beneficial-control
coverage;** unresolved holders stay singletons.
**Control:** the ledger's official/published concentration, plus concentration under random grouping at equal
cluster sizes — randomize on the nominal holder key, preserve the full observed cluster-size multiset including
singletons, retain signed values, fix iterations and seed, and report mean, 95% interval, lift, ratio, and
empirical p. An all-singleton resolution has a *degenerate* null, not a missing control.
**Conflicting parents:** where one holder key maps to multiple parents, leave it unresolved unless dated evidence
selects the valid parent per event, and report the conflict mass (53 UEIs / `$2.687B` in validation).
**Ithildin mapping (corrected against validation):** `connections.relationship_type` **mixes relationship domains
with edge semantics** — see the header note on the graph-vocabulary blocker. `query_registry` has no ownership
table and its local corpus is ~99.99% Florida; `registry_address_index` addresses are pivots only;
`person_resolution.py` is Epstein-person-specific; **OpenCorporates is credential-blocked (HTTP 401)**;
GLEIF/ICIJ OLDB/OpenSanctions each need an explicit UEI-to-source reconciliation layer and returned no parent in
the bounded DHS frame. Ledgers via query_fpds/USASpending, query_property, ingest_faa, USPTO. **None of these
tools emits a dated terminal-controller map today.**
**Failure modes:** current-ownership anachronism (award-date control differed); false merges on common
names/addresses (measure a rejected-pair sample); family/control edges needing manual research that silently
caps coverage; treating co-occurrence as control (the access-substitution G-discipline); **reversed edge
direction** (validation found `Palantir Technologies --[subsidiary_of]--> Palantir USG` stored opposite to its
own description — a type-only traversal inverts control); self-parent rows inflating apparent coverage;
unresolved holders silently dropped from the denominator.
**Better frames:** bounded procurement families (the ICE skip-tracing 14-holder and UAC 18-holder sets) beat a
4,270-holder mixed-market census for manual control research — though both returned zero rollup delta here.
**Input-dependency:** (a) on public registries for the corporate layer; family/nominee edges may need
reporting. **Exemplars:** [Lords of the fish](https://www.icij.org/investigations/looting-seas-iii/) (Chile);
Fatal Extraction's ASX parent rollup; OCCRP customs-empire and president's-family nominee graphs.

### 39. regulated-chain-mass-balance (conservation audit on a commodity or closed-ledger chain)
**Observed:** ICIJ 3/11 extractives (bluefin chain, Myanmar teak, Peru's paired landing weights); OCCRP
supply-demand/absorption gap 6/11 + corridor reconstruction 8/11 illicit-trade; Markup
capacity-accountability gap 1; ProPublica's card 21 is the ratio cousin.
**Validated 2026-07-29 — scope narrowed.** The card originally claimed a "payment chain" variant running on
`datasets/epstein_derived.db`. Live validation refuted that: **0 of 53,100 transaction rows resolved to
adjacent payment stages (coverage ceiling 0.000%)** despite 97.0% joint amount/date coverage, because the
sidecar holds no account rows, no statement rows, no stage links, and no transfer ID carried across stages.
Money is fungible and nets, so a monetary invariant is well-defined **only** inside a closed account
reconciliation or across independently observed transfer stages. The surviving substrate-independent tests
(ID reuse, threshold discontinuity, impossible stage timing) moved to **card 42**. Memo:
`_validation/card39-mass-balance-payment-variant.md`.
**Mechanics:** Model the regulated flow as stages (catch→landing→plant→export; production→domestic
sales+exports; program budget→disbursement→delivery). Join adjacent stages on lot/shipment/case IDs and
dates, normalize units, apply a defensible conversion-loss range, then test invariants: output ≤ input;
declared destination capacity ≥ shipped volume; residual = production + imports − lawful consumption −
exports − inventory-change. Flag output-exceeds-input and systematic shrinkage at one operator.
**Monetary form (conditional):** permitted only under the closed-ledger precondition below — within one account
and currency, reconcile `ending = beginning + Σ signed transactions`; across a transfer, compare independent
instruction and receipt records on a persistent transfer ID, subtracting only explicit fees and applying the
recorded FX leg. **Never infer conservation from aggregated entity/counterparty text** — same-day
same-absolute-amount opposite-sign pairs manufacture perfect conservation out of reversals, internal book
entries, and duplicate representations of one event (the validation found 681 such tempting groups and
correctly refused them).
**Minimum data:** two *independently observed* adjacent stage ledgers with quantities + timestamps + a
stage-persistent joinable identifier; a lawful capacity/quota/demand baseline. Dimensions
(account → entity → counterparty) are **not** stages — a table that only widens attribution cannot be
mass-balanced.
**Pre-registration:** for commodities, conversion-loss bounds and unit normalizations fixed from
industry/scientific references before computing; report the residual across the bound range, never a point
estimate. For money there is **no defensible generic shrinkage range** — instead fix exact cents, declared
gross/net treatment, explicit fees, recorded FX rate and leg, reversal policy, internal-transfer policy, and a
settlement lag.
**Coverage statement:** report count *and* absolute-value coverage separately for stage join, quantity/amount,
currency, account, and ordering date — then their intersection. Volume coverage alone hides a binding zero: the
validation had 97% amount/date coverage and 0% stage coverage, and only the intersection revealed the card was
inert.
**Control:** the residual distribution across compliant operators/routes — a route is a finding only against
that base. If no compliant comparator can be constructed, the move does not run.
**Preconditions:** independent adjacent ledgers; a stage-persistent key; explicit account/currency boundaries;
opening and ending balances for any reconciliation; stage-specific precise dates; a constructible compliant
control. **If any gate fails the result is "not computable" — never a zero residual.**
**Failure modes:** unit and lot-splitting errors; legitimate inventory buffering read as diversion; the
residual treated as *proven* diversion rather than a bounded anomaly (ICIJ/OCCRP both bound it);
survivor bias when seizure data defines the universe; **reading a dimensional join as a stage join** (the
defect that made the payment claim false); netting and reversals mistaken for conservation.
**Ithildin mapping:** commodity/closed-ledger form only. USASpending/FPDS mod-ledgers are the nearest held
substrate (obligation → modification → outlay, where outlay data exists). **GAP:** customs/bill-of-lading and
commodity-origin data — the largest shared missing layer across ICIJ and OCCRP (see adapter-gaps). **BLOCKED:**
no held corpus has paired payment stages; the OCCRP Azerbaijani ledger (adapter-gaps cross-outlet row 13) is
the candidate substrate for building this, and until it is ingested the monetary form has no test bed.
**Input-dependency:** (a) where stage ledgers are public (EU quota/subsidy data, the published Azerbaijani
ledger); degrades to (b)/(c) where the decisive ledger is private (Peru's denied landing data became a leak).
**Exemplars:** [The Mediterranean feeding frenzy](https://www.icij.org/investigations/looting-the-seas/);
[Peru's vanishing fish](https://www.icij.org/investigations/looting-seas-iii/); OCCRP "Made To Be Smuggled"
capacity-vs-market residual.

### 40. remediation-diff (the subject's response to the probe is evidence)
**Observed:** The Markup 10/11 privacy stories run a before/after-contact rescan; echoes in ProPublica
post-publication retests and OCCRP archived-page diffs, but only The Markup institutionalized it.
**Mechanics:** Snapshot the observable behavior (network egress, rendered page, ranking, policy text,
filter list) with an identical, versioned probe BEFORE contacting the subject for comment; re-run the probe
after contact and after publication. The delta serves three distinct evidentiary jobs: causal attribution
(the practice was theirs to change and they changed it when asked), an admission proxy where the subject
declined to answer, and quantified impact. Requires a preserved pre-state — which makes this card the
operational answer to instrument decay: **snapshot raw collected inputs at run time, every run.**
**Minimum data:** a repeatable probe; versioned snapshots with timestamps; the contact/publication timeline.
**Control:** an uncontacted cohort scanned on the same schedule — platforms change things constantly; the
finding is differential change, not change.
**Failure modes:** coincidental change or A/B tests read as remediation (the control cohort is mandatory);
alerting subjects early has editorial implications (sequence outreach deliberately); snapshot integrity
(hash and archive at collection).
**Ithildin mapping:** public_records_monitor re-scans, Wayback/urlscan snapshots, re-runnable query tools
with `--output` archives; applies to any monitored source, not just websites.
**Input-dependency:** (a) — fully instrument-built.
**Exemplars:** [Meta Pixel hospital study](https://themarkup.org/pixel-hunt/2022/06/16/facebook-is-receiving-sensitive-medical-information-from-hospital-websites)
(33 of 33 flagged hospitals changed configurations, tracked pre/post); the Blacklight remediation series.

### 41. sentinel-input-egress-join (plant a known value, watch where it surfaces)
**Observed:** The Markup 9/11 privacy stories + form-testing work; the zombie-record variant in tenant
screening; ProPublica's card 11 is the ancestral interaction audit without the planted-key discipline.
**Mechanics:** Inject a unique, attributable value into the subject system — a sentinel name, condition,
income, click, or per-recipient canary variant — then observe all egress channels (outbound requests, exports,
mail, downstream commercial records) for its reappearance: exact, rounded, encoded, hashed, or time-adjacent.
Joining on a value you planted collapses linkage error to ~0 and converts an opaque flow into an attributable
transfer. The **consent-branch invariant** sub-move runs identical accept vs decline flows and diffs egress —
transmission that ignores the branch is the finding. The **zombie-record** sub-move plants nothing but tracks
a corrected/expunged source record into downstream copies on the same key.
**Minimum data:** a controllable input; observable egress (HAR/network capture, account export, purchased
report); an encoding dictionary (hash/rounding candidates for the planted value).
**Failure modes:** missed encodings (salted hashes defeat naive matching — test known transformations);
cross-contamination between test identities; authorization bounds on probing third-party systems (document
the legal basis per run; CFAA/ToS exposure is real).
**Ithildin mapping:** urlscan/investigate-infra for passive layers. GAP: no first-party
instrumentation/HAR-capture harness in tools/ — the one capability class The Markup's corpus demands that the
platform entirely lacks.
**Input-dependency:** (a) — instrument-built; check runnable-today per target (platform countermeasures).
**Exemplars:** [How We Built a Meta Pixel Inspector](https://themarkup.org/show-your-work/2022/04/28/how-we-built-a-meta-pixel-inspector);
tax-prep sites transmitting income data; [Access Denied](https://themarkup.org/locked-out/2020/05/28/access-denied-faulty-automated-background-checks-freeze-out-renters)
(zombie records).

### 42. payment-record-integrity (ID reuse, threshold discontinuity, impossible stage timing)
**Provenance:** split out of card 39 on 2026-07-29 after validation showed these tests survive on payment data
while conservation does not. They are substrate-independent — they need one ledger, not two.
**Observed:** the mechanics are OCCRP's (velocity pairing, same-day matched pass-through, structuring-threshold
work on the Azerbaijani ledger) and ProPublica's (card 16's cap-clustering); the split is validation-driven
rather than newly observed.
**Mechanics:** Three single-ledger integrity screens. **(1) Business-ID reuse:** distinguish the extraction
identity layer (source system + native ID, dedupe hashes) from *business* identifiers (transfer/confirmation
IDs, invoice numbers). Repeated business IDs across distinct events are the finding; repeated extraction hashes
are a pipeline artifact. **(2) Named-threshold discontinuity:** for a *real, cited* reporting or approval
threshold, compare the amount distribution immediately below versus above it against a matched
transaction-class baseline. **(3) Impossible stage timing:** where a row carries multiple stage timestamps,
flag receipt-before-instruction and approval-before-submission.
**Minimum data:** one transaction ledger with parsed amounts, a transaction-class field, and either a business
identifier or ≥2 stage timestamps per row.
**Pre-registration:** the exact threshold value, its statutory or policy source, its effective date, the
transaction class it governs, and the below/above bandwidth — all fixed before computing.
**Coverage statement:** share of rows with a business ID (not just an extraction ID), a usable class label, and
parsed amounts.
**Control:** a matched payment-class baseline for the threshold test. **Round-number heaping is the null, not
the signal** — the validation measured 401 exact-`$100,000` rows at up to 5.4% of wire/transfer rows with
degenerate neighbor comparators, which demonstrates only that round amounts are common. Without a cited
threshold and a matched baseline this screen produces spectacular meaningless lift ratios.
**Preconditions:** a real threshold must exist and be cited; document/page identifiers (`canonical_ref`-class
fields) must be excluded from ID-reuse tests — treating a page ID as a payment ID is a category error.
**Ithildin mapping:** runs today on `datasets/epstein_derived.db` via `query_fin.py` for the duplicate screen
(it found 42 unflagged within-LMSBAND repeated-hash groups / 48 excess rows, a real data-quality result); the
threshold and timing screens await a cited threshold and stage timestamps respectively. Dollar literals in any
persisted output must be written shell-safe.
**Failure modes:** extraction duplicates read as business-ID reuse; round-number heaping read as structuring;
truncated identifiers inflating apparent reuse (116 truncated LMSBAND refs were found in the test corpus).
**Input-dependency:** (a) on any held ledger — these are integrity screens, not access-gated moves.

### Additional acquisition moves (wave 2)

- **parallel-custodian records route** (immigration 3–4 + education 2, independently derived): when the target
  agency stonewalls, map every institution that necessarily touched the event — local PD, county district,
  foreign court, university clinic, 911 dispatch — and extract the same evidence through the custodian with
  the weakest secrecy shield (the cell-death video came from the local police department under the Texas
  Public Information Act after CBP refused; 911 logs substituted for refused police reports).
- **mass-parallel FOIA fan-out** (education 7/13 stories at 100–500 requests each; housing 7/12): the scale
  norm for state/local records work — request *operational logs* (inspections, storage inventories,
  correspondence), not summary reports.
- **litigation as acquisition instrument** (military 4): FOIA suits and access suits as the standard unlock
  for mishap files, claims databases, and sealed court records — budget for it as a lead type.
- **IRB research access** (military 1): partnering into an academic institution's IRB to reach a
  restricted-use registry (Agent Orange) — a route an agent platform flags as human_action.
- **academic FOIA repositories** (immigration): TRAC, the Deportation Data Project, UWCHR as pre-liberated
  bulk sources — check them before filing.
- **refusal-as-evidence**: a probative FOIL denial (housing) and documented obstruction (meatpacking, Facebook)
  are findings, not just failures — record them as such.
