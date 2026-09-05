---
name: Permission After Entry
slug: permission-after-entry
domain: legal-regulatory
source: "ICIJ 'Uber Files' (2022); ICIJ tobacco investigations (2000–2012); pattern-library cross-outlet synthesis (2026-07-29)"
status: candidate
created: 2026-07-29
grounding_findings: []
related_models: [sovereign-exception, regulatory-replacement, exit-cost-escalation, infrastructure-lock-in, temporal-arbitrage]
detection_keywords:
  - ["launch", "pilot", "rollout", "market entry", "expansion"]
  - ["cease and desist", "injunction", "raid", "suspension", "impound", "shut down"]
  - ["exemption", "carve-out", "pilot program", "regulatory sandbox", "special category"]
  - ["ballot measure", "model legislation", "user petition", "driver petition"]
  - ["unlicensed", "operating without", "pending authorization", "grey area"]
minimum_trigger: "Documented operation at scale in a jurisdiction BEFORE the authorization that governs it, in 2+ jurisdictions — a single grey-area launch is a compliance dispute, a repeated sequence is a strategy"
anti_pattern: "Genuine legal ambiguity resolved in the firm's favor (no applicable rule existed, and the firm sought guidance before or during entry); a novel product that regulators had simply not classified yet. The pattern requires either a known prohibition or a deliberate choice not to seek authorization — evidenced by internal sequencing, repeated pattern across jurisdictions, or contemporaneous enforcement the firm absorbed as a cost."
canonical_example: "ICIJ Uber Files (2022): entry before authorization across many jurisdictions, then mobilization of users, investors, and former officials to convert enforcement pressure into bespoke legal categories — https://www.icij.org/investigations/uber-files/"
---

## Definition

Permission After Entry is a market-entry strategy in which a firm deliberately establishes operations *before*
obtaining the legal authority to operate, treats the resulting enforcement as an operating cost, and then
converts the dependency it has built into the legal permission it skipped. The sequence is the mechanism:
launch → subsidize adoption until a constituency exists → absorb fines, injunctions, and raids → mobilize
users, drivers, investors, academics, and former officials → obtain a bespoke exemption, a new legal category,
or simple non-enforcement. Legalization arrives last, and arrives shaped by the firm.

The pattern inverts the ordinary compliance sequence, and that inversion is what makes it detectable: an
authorization dated after the operations it authorizes is a public, joinable fact. It differs from
[[sovereign-exception]] (where a *state* actor invokes emergency to suspend normal rules) and from
[[regulatory-replacement]] (where the industry staffs the agency): here a private firm neither captures nor
becomes the regulator — it renders the regulator's decision moot by making prohibition costly to the public
before the decision is made. The leverage is not influence over officials but the *installed base*: riders
without alternatives, drivers with car payments, a public that has already reorganized around the service.

Physical-goods precursors exist and are useful for calibration. ICIJ's tobacco work documented a small
duty-paid "umbrella" market operating alongside a far larger untaxed channel — establish presence and demand
first, formalize (or never formalize) later. The mechanism generalizes wherever adoption is cheap, reversal is
politically expensive, and the penalty for unauthorized operation is a fine rather than an existential bar.

## Detection Markers

- **The dated inversion**: service/product launch date precedes the licence, permit, tariff, or statutory
  category that governs it — computed across every jurisdiction the firm entered, not one.
- Enforcement actions (cease-and-desist, injunctions, vehicle impounds, raids, suspensions) that do not stop
  operations; fines paid and booked as cost of entry.
- Steep, unsustainable subsidies concentrated in the pre-authorization window, ending after legalization.
- User/worker mobilization campaigns (in-app petitions, prompted emails to legislators, ballot measures)
  appearing immediately after an enforcement event.
- Former regulators, ministers, or enforcement officials hired during an active investigation of the firm.
- Investors or local partners selected for political reach rather than capital.
- A bespoke legal category, pilot programme, sandbox, or exemption created for one firm's business model —
  and near-identical asks appearing in multiple jurisdictions (evidence of a template, not local adaptation).
- Post-legalization enforcement vacuum: the new rules exist but no agency is resourced or assigned to enforce
  them (The Markup's California gig-work finding is this end-state).
- Internal or disclosed communications sequencing entry ahead of authorization deliberately ("launch first",
  "ask forgiveness") — decisive when available, but the public dated sequence usually carries the finding alone.

## Boundary Conditions

- **Ambiguity is the main innocent explanation.** Genuinely novel products often precede their categories. The
  pattern requires either an applicable prohibition at entry or evidence the firm chose not to seek
  authorization it knew was needed. Repetition across jurisdictions is the strongest available discriminator
  from records alone.
- Does not apply where the firm sought and awaited authorization, entered under an explicit regulator-granted
  pilot, or where the regulator affirmatively declined to assert jurisdiction before entry.
- **Distinguish lobbying-as-usual from this pattern**: every regulated firm lobbies. What marks this pattern is
  that the lobbying follows entry and enforcement rather than preceding entry, and that the ask is a *new
  category* rather than a favourable interpretation of an existing one.
- Sequence is not causation. That contacts cluster in an enforcement window and a bill then stalls establishes
  access and timing — not that the contacts caused the outcome. ICIJ's own aid-lobbying entries hold this line
  explicitly; so should any application of this lens.
- The pattern needs an *installed base*. A firm with no adopted constituency that simply operates illegally is
  running an ordinary illegal business, not this strategy.

## Limitations

- Retrospective narrative fit is easy: once a firm is legalized, almost any messy entry can be re-described as
  strategy. Require the dated inversion in a majority of entered jurisdictions before naming it.
- The lens can flatten real regulatory failure into corporate agency — sometimes states were slow, indifferent,
  or captured for unrelated reasons, and the firm merely benefited.
- It risks moralizing about products the public genuinely wanted; the analytical claim is about *who decided*
  and in what order, not whether the service was good.
- Enforcement records are unevenly public across jurisdictions, so the measured inversion rate is a floor and
  the comparison across countries is biased toward transparent ones.

## Cross-outlet grounding (pattern-library corpus, pending live validation)

Corpus support, not investigation findings — no `grounding_findings` yet; adoption requires live grounding:

- **ICIJ Uber Files** — the complete sequence, including the enforcement-window contact clustering and the
  bespoke-category asks. `research/patterns/_intake/icij/report-17-lobbying-regulatory-capture.md`
- **ICIJ tobacco investigations** — the physical-goods precursor: a small lawful channel alongside a much
  larger unauthorized one; lobbying pivots into emerging markets. Same report.
- **The Markup, platform labor** — the end-state: industry-drafted law followed by an enforcement vacuum;
  algorithmic pay changes imposed on an entrenched workforce.
  `research/patterns/_intake/markup/report-19-platform-labor-worker-surveillance.md` and
  `report-14-elections-political-influence.md` (Prop 22 campaigning).
- Detection mechanics: [detection-signatures.md](../../patterns/detection-signatures.md) card 6/F5 (event-window
  alignment), card 12 (beneficiary reverse-engineering), card 34 (prohibition conformance); family F5/F10 in
  [cross-outlet-ontology.md](../../patterns/cross-outlet-ontology.md).
