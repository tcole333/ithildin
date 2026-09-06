# Promotion Candidates — Pattern Cards → Analytical Frameworks

**Assessed 2026-07-29** at the close of the cross-outlet integration pass (ProPublica + ICIJ + OCCRP +
The Markup). This file records what was promoted, what was held, and the reason for each, so a later session
does not re-litigate the same calls.

## The bar

Two distinctions govern promotion, from [README.md](README.md) ("Extension path") and
`research/craft-research/frameworks/README.md`:

1. **Detection signatures are analytic moves; Tier-2 lenses are explanatory models.** A card that says "join
   X to Y and diff" is not a lens no matter how well supported — it belongs in
   [detection-signatures.md](detection-signatures.md). A lens claims something about *why* actors behave as they
   do and predicts co-occurring features.
2. **Adoption requires live grounding.** A framework advances from `candidate` → `evaluated` → `adopted` by
   accumulating grounding findings with evidence chains in a real investigation, not by appearing in many
   published stories. Cross-outlet corpus convergence justifies `status: candidate`; it cannot justify
   `adopted`.

A third constraint applied to this pass specifically: **no investigation.db writes were permitted**, so the
`/discover-frameworks` steps that enqueue `hypothesis_tracker` framework candidates and companion leads were
deliberately skipped. That registration is the outstanding follow-up (see §4).

## 1. Promoted to Tier-2 candidate lenses

| Lens | File | Why it qualified | Outlet convergence |
|---|---|---|---|
| **Purchased Assurance** | `research/craft-research/frameworks/purchased-assurance.md` | Explanatory (the payer–assessee incentive structure predicts clearance regardless of auditor honesty) and genuinely absent from the 42 existing lenses — [[compliance-theater]] covers *internal* apparatus, this covers *third-party commercial* assurance the state has delegated to | ICIJ (Deforestation Inc., bluefin traceability, Implant Files notified bodies), OCCRP (Uighur PPE test purchase) |
| **Permission After Entry** | `research/craft-research/frameworks/permission-after-entry.md` | Explanatory strategy model with a falsifiable dated signature; distinct from [[sovereign-exception]] (state invokes emergency) and [[regulatory-replacement]] (industry staffs the agency) — here the regulator is rendered moot by an installed base | ICIJ (Uber Files as the complete sequence; tobacco as physical-goods precursor), The Markup (Prop 22 + the post-legalization enforcement vacuum) |

Both are `status: candidate` with `grounding_findings: []`, boundary conditions, and limitations sections, and
both cite corpus support explicitly as corpus support rather than as investigation findings.

## 2. Held — belongs in the card layer, not the lens layer

These had strong cross-outlet support but are *moves*, and were instead minted or reinforced as cards
(see [detection-signatures.md](detection-signatures.md) 38–41 and the `Cross-outlet:` lines on cards 1–5,
6, 9, 11, 18, 19, 20, 22):

- **Beneficial-control rollup** → card 38. A resolution procedure, not a theory of behavior. The *explanatory*
  claim adjacent to it (control is deliberately dispersed across nominees to defeat aggregation) is already
  carried by Tier-1 model #7 Enabler Gradient and the existing hidden-ownership lenses.
- **Regulated-chain mass balance** → card 39. Pure measurement. **Validated 2026-07-29 and narrowed:** its
  claimed payment-chain variant was refuted (0 of 53,100 rows resolved to adjacent payment stages), the
  surviving single-ledger tests were split into card 42, and the monetary form now carries a closed-ledger
  precondition. Memo: `_validation/card39-mass-balance-payment-variant.md`.
- **Remediation diff** → card 40. Method, and partly an ethics/sequencing decision about outreach.
- **Sentinel-input egress join** → card 41. Instrument design.
- **Missingness as signal** → card 18, now with four-outlet support. It is a stance toward evidence, not a
  model of conduct.
- **Enforcement-gap-ratio** → card 4, whose status was *upgraded* from ProPublica-emergent to confirmed
  universal (all four outlets). No lens needed: [[compliance-theater]] and
  [[oversight-architecture-demolition]] already explain the mechanism. **Validated 2026-07-29 and blocked:** the
  four-outlet graduation holds as a claim about the finding-*family*, but the card's ratio is un-executable on
  held data (empty SEC bodies; zero admissible independent adjudications; proxy circularity was the fatal
  unlisted failure mode). The card now carries the discipline fields it was missing. Memo:
  `_validation/card04-enforcement-gap-ratio.md`. **Lesson for future graduations: cross-outlet convergence
  evidences that a pattern is real, never that this platform can compute it — those are separate claims and
  should be stated separately.**

## 3. Held — reinforces an existing model rather than adding one

- **Intermediary-enablement** is ICIJ's single most frequent finding tag (10 uses), and OCCRP's
  formation-agent/bank enabler findings run throughout its canon. This is strong independent confirmation of
  **Tier-1 model #7, The Enabler Gradient** — recorded here as evidence for the existing model. If that model
  is ever revised, this cross-outlet support is the reason to strengthen rather than narrow it.
- **Substance–form gap** (ICIJ letterbox tests, OCCRP capacity/role mismatch at 10/11 state-capture stories)
  reinforces **Complexity as Credential** (#8) and **Jurisdictional Arbitrage** (#5).
- **Platform-era undisclosed data flows** (The Markup's largest family) is the data-substrate sibling of
  **undisclosed-benefit-to-official**; it may deserve its own lens once the platform runs a live
  instrumentation investigation, but with no first-party HAR-capture harness in `tools/` (adapter-gaps
  cross-outlet row 2) there is no near-term path to grounding findings. Held explicitly on capability grounds.

## 4. Outstanding follow-ups

1. **DB registration (blocked by design this pass).** Register both candidate lenses through
   `/discover-frameworks` so they enter `hypothesis_tracker` as `framework_candidate` rows with companion
   evaluation leads. Requires a session permitted to write investigation.db.
2. **Live validation.** 6 of 42 cards now have executed validation memos (`_validation/`: cards 15, 16, 30, 39,
   plus 4 and 38 from the 2026-07-29 run). The first validation of a cross-outlet card immediately amended it,
   which is the argument for continuing: **card 39's payment claim was refuted outright** and the card was
   narrowed + split. Next highest-value, given held data: cards 40/41 (blocked — no instrumentation harness, so
   validating them *is* the adapter case), card 1 (two-books-diff, the most-used move in the corpus and still
   unvalidated), and cards 3/5/14/21/29, which produce computed statistics but still lack discipline fields.
3. **Detector wiring.** Neither candidate lens has been added to `model_detector.py`; per the lens lifecycle
   that step belongs at `adopted`, not `candidate`.
4. **`framework-references.md`** could take Power's *The Audit Society* (1997) as Tier-3 grounding for
   Purchased Assurance; not added in this pass to keep the diff scoped to the pattern library.
