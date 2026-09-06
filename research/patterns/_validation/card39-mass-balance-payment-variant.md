# Card-validation memo — card 39 `regulated-chain-mass-balance`, payment-chain variant

**Card under test:** `research/patterns/detection-signatures.md`, card 39.
**Test bed:** `datasets/epstein_derived.db`, financial build run 3 completed
2026-07-04 21:35:47: **53,100 `financial_transaction` rows**, dated-record
window **1985-08-26..2024-06-25** (1,037 rows have no usable sidecar date).
The `query_fin` default-active population is 32,022 rows; the pre-registered
`txn_type IN ('wire','transfer')` subset is 2,189 rows.
**Posture:** read-only against every database; zero database writes. No lead,
finding, connection, hypothesis, infra request, or profile change. Exactly this
memo was written in the repository.
**Scratch:** `/tmp/osint-qEMfjM8N/`.

---

## 1. EXECUTABILITY, field by field

### Mechanics — **partially sufficient; conservation is locally definable but there is no chain to conserve**

The card says to *"model the regulated flow as stages"* and *"join adjacent
stages on lot/shipment/case IDs and dates"*. That is the right discipline. The
payment mapping fails before the arithmetic:

- `financial_transaction` is one normalized table of extracted ledger lines,
  not an instruction ledger joined to a transfer ledger joined to a receiving
  ledger.
- `source_native_id` identifies an extraction row, `canonical_ref` identifies
  an evidence page, and `dedupe_key` hashes page + date + amount + description.
  None is a stable payment identifier carried across independently observed
  stages.
- `account → entity → counterparty` is not a stage chain. Those are attribution
  dimensions on one record. Summing them as though they were adjacent ledgers
  would double-count internal transfers and money that re-enters the perimeter.
- The held sidecar has **0 `financial_account` rows, 0
  `financial_statement` rows, 0 transaction `account_id` values, and 0
  transaction `statement_id` values**. Its 590 balance snapshots are unlinked
  owner-text snapshots, not boundary balances for transaction groups.

Money does obey a conservation identity inside a closed account and one
currency:

```
ending balance = beginning balance + signed inflows/outflows
residual = ending balance - (beginning balance + Σ signed transactions)
```

Fungibility does not invalidate that equation. It invalidates item-level
lineage and any naive entity-wide equation when the account perimeter,
window-boundary balances, currencies, fees, FX legs, reversals, and internal
transfers are not complete. For an individual transfer, the defensible equation
would be `receipt = instruction − explicit fees ± explicit FX adjustment`, but
only with the same transfer ID on independent sending and receiving records.
This data has neither requirement.

Therefore the card's central commodity invariant, *"output ≤ input"*, is not
well-defined on this test bed. The valid payment invariant is narrower—a
closed-account reconciliation—and its required stages have zero coverage.

What survives the substrate translation:

| listed test | survives conceptually? | runnable here? | result |
|---|---|---|---|
| duplicate identifiers | yes | partly | source-row IDs: 0 duplicates; extraction hashes: 801 repeated groups |
| exact-threshold bunching | yes | yes as a declared sensitivity screen | strong round-number heaping, but no card-specified lawful threshold or valid regulatory inference |
| impossible timing | yes | no paired stages | 0 reversed row-local date intervals, which is not the card's test |
| output-before-input | yes | no paired stages | un-executable |
| output-exceeds-input / systematic shrinkage | only inside a closed ledger | no | un-executable |
| destination capacity | no generic payment analogue | no | un-executable |

The honest payment variant is thus not mass balance on this platform today. It
is, at most, a payment-record integrity screen comprising stable-identifier
reuse, threshold discontinuities, and stage-order checks when the necessary
fields exist.

### Minimum data — **partially sufficient; the payment-specific minimum is understated**

Card 39 asks for *"two adjacent stage ledgers with quantities + timestamps + a
joinable identifier; a lawful capacity/quota/demand baseline."* The first clause
correctly describes what is missing. For payments it must be strengthened to
require:

1. independently observed sending and receiving stages, not two OCR
   representations of the same page;
2. a persistent transfer/confirmation identifier at both stages;
3. account identifiers and a declared closed-system perimeter;
4. currencies, gross/net treatment, explicit fees and FX adjustments;
5. opening and ending balances for account reconciliation;
6. date precision plus instruction, value, posting, and settlement semantics;
7. a named lawful threshold and effective date for any threshold-bunching test;
8. operator/route labels and an externally defined compliance status for the
   control.

The sidecar has signed integer cents and mostly usable dates, but none of the
stage, perimeter, account, or control requirements. The underlying LMSBAND
source has only sparse identifiers that the builder does not preserve as
structured sidecar fields: 35 DS09 rows have a `confirmation_number` (32
distinct; 3 repeated groups), 31 DS09 rows have a `reference`, and 300 DS10 rows
have a `reference`. `confirmation_number` is dropped; `reference` is folded
into free-text `raw_description`. Even preserving them would not create an
independent receipt ledger.

### Pre-registration — **partially sufficient; commodity conversion loss is the wrong payment parameter**

The card requires *"conversion-loss bounds and unit normalizations, fixed from
industry/scientific references before computing."* That is appropriate for
fish or timber. Money needs no generic shrinkage allowance. It needs explicit
fees and FX legs; an analyst-selected “loss” range would normalize away the
anomaly.

Before computing, I wrote `/tmp/osint-qEMfjM8N/preregistration.md` and fixed:

- the full, query-tool-active, and `wire|transfer` populations;
- the candidate instruction → transfer → receipt and
  opening-balance → transactions → ending-balance stage models;
- `statement_id` as the only schema-declared candidate reconciliation join;
- exact cents and a ±1 cent arithmetic tolerance;
- day precision as the requirement for strict temporal order;
- the definitions of amount, date, and both-stage coverage;
- the source-ID and dedupe-hash duplicate tests;
- a threshold sensitivity set of **$1,000, $5,000, $10,000, $50,000, and
  $100,000**, with the ten adjacent exact-dollar values as the local baseline;
- `recon_status='ok'` statements as the proposed compliant control, if any
  existed.

No row counts or distributions had been computed when those parameters were
written. The card itself should require payment analysts to pre-register the
closed perimeter, stage semantics, transfer key, currency treatment, fee/FX
policy, internal-transfer and reversal policy, timing field and allowed lag,
named legal threshold, and control construction.

### Coverage statement — **partially sufficient; volume alone hides the binding zero**

The card asks for the *"fraction of flow volume with both stages resolvable."*
That is necessary but not enough for payments. Coverage must be stated both by
record count and by absolute amount, and it must separately disclose join,
amount, date, currency, and account coverage. Otherwise a high amount-parse
rate can disguise a zero stage-join rate.

The requested combined ceiling is:

```
both stages resolvable
AND amount parseable
AND ordering date usable
= 0 of 53,100 rows = 0.000%
= $0 of $26,336,020,071.84 gross absolute amount = 0.000%
```

Excluding flagged outliers changes the amount denominator to
$12,447,711,508.77 but not the numerator: still $0 and 0.000%.

The component coverages are materially better, which isolates the gap:

| population | rows | amount parseable | source-backed day date | amount + day date | both stages + amount + day |
|---|---:|---:|---:|---:|---:|
| all transactions | 53,100 | 52,549 (98.962%) | 52,063 (98.047%) | 51,527 (97.038%) | **0 (0.000%)** |
| `query_fin` active | 32,022 | 31,704 (99.007%) | 31,028 (96.896%) | 30,714 (95.915%) | **0 (0.000%)** |
| `wire|transfer` | 2,189 | 2,181 (99.635%) | 2,189 (100.000%) | 2,181 (99.635%) | **0 (0.000%)** |

Date precision required a source-backed audit because
`financial_transaction` stores neither `date_precision` nor the raw date.
Across all 53,100 native source rows:

- 52,063 are full day dates;
- **0 are bare-year or month-precision dates**;
- 948 have a blank/null raw date;
- 89 are unusable month/day strings without a year;
- no source native row was missing, and every parseable normalized day matched
  the stored epoch day.

The sidecar contains 2,775 first-of-month dates and 127 January 1 dates, but the
source audit shows they are recorded as full day values, not detectable
year/month anchors. Thus the equivalent of the main database's known coarse
dates is **zero recoverable coarse values here**, with 1,037 unusable dates
instead. The builder nevertheless discards precision, so this conclusion could
not be established from the sidecar alone.

### Control — **un-executable as written**

The card requires *"the residual distribution across compliant
operators/routes"* and warns that *"a route is a finding only against that
base."* That discipline is correct. No such population can be constructed:

- `financial_statement`: 0 rows;
- source `ds10_statement_recon`: 0 rows;
- source DS10 transactions with a non-null `statement_id`: 0 rows;
- linked account/operator/route labels: 0;
- independently defined compliant/non-compliant status: absent.

There is therefore no residual distribution, no compliant baseline, and no
lift figure for the mass-balance move. The neighboring-dollar comparison used
for the separate heaping sensitivity test is not a substitute: it controls for
nearby exact amounts, not for compliant operators or routes.

### Preconditions — **un-executable as written; the field is absent**

Card 39 has an `Input-dependency` field but no explicit `Preconditions` field.
For the payment claim, that omission is outcome-determining. The go/no-go gate
must ask whether the analyst holds a closed account perimeter, independent
adjacent ledgers, a stage-persistent key, currency/FX/fee fields, boundary
balances, stage-specific precise dates, and a control population.

On this test bed every decisive payment precondition fails except integer
amounts and mostly day-level dates. A future agent following the current card
would see “payment-chain variants run” and compute a false residual from
unclosed one-sided records.

### Ithildin mapping — **un-executable as written; “run … today” is false**

The card says: *"payment-chain variants run on datasets/epstein_derived
(query_fin) ... today."* `query_fin` does run spend, text-party flow,
balance-snapshot, and outlier queries. I exercised `spend` and `review
--outliers`, both with `--output`. It does not expose:

- an instruction or receipt stage;
- a payment/confirmation identifier;
- transaction-to-account or transaction-to-statement joins;
- statement reconciliation;
- date precision;
- currencies/FX/fees as linked legs;
- a compliant-route baseline.

`query_fin flows` groups `cardholder_raw` and `counterparty_raw`; it does not
reconstruct a transfer across independent books. The platform assertion is
therefore not merely missing a convenience command. The held model lacks the
minimum relational structure.

Two lineage checks matter because the brief identified prior bugs:

- **Amount TEXT-sort fix holds for the relied field.** Of 53,100 rows, 52,549
  store `amount_minor` as SQLite `integer`; 551 are null because the raw amount
  is blank/null; **0 non-null amounts have a non-integer storage type**, and 0
  nonblank raw amounts failed into null. Numeric ordering and aggregation on
  `amount_minor` are safe. Forty-one rows are separately flagged as outliers.
- **EFTA truncation is still present in the held lineage.** All 53,100 derived
  refs exactly match their source-layer refs, but 116 LMSBAND rows carry
  syntactically truncated values: `EFTA00` (95 rows), `EFTA0013` (20), and
  `EFTA001` (1). Those are 3.483% of the 3,330 LMSBAND transaction rows. A total
  of 131 LMSBAND transaction rows have no `evidence_item` link. Among resolved
  links there are 0 ref mismatches. Kabasshouse also has 840 non-EFTA alternate
  document labels; those are heterogeneous source IDs, not the same truncation
  family.

The truncated refs were not used as payment join keys. They do, however, make
`canonical_ref` unsafe even as a provenance/dedupe key for those 116 rows and
confirm that the prior defect cannot be assumed fixed across both layers.

### Failure modes — **partially sufficient; commodity warnings omit the dominant payment failures**

The current list—*"unit and lot-splitting errors; legitimate inventory
buffering read as diversion; the residual treated as proven diversion; survivor
bias when seizure data defines the universe"*—is sensible for commodities. Only
the warning against treating a residual as proven wrongdoing transfers cleanly.

Payment-specific failure modes missing from the card:

1. an open account perimeter mistaken for a closed system;
2. gross flows compared where settlement is net;
3. internal transfers and re-entry double-counted as new input/output;
4. fees, FX conversions, reversals, chargebacks, and timing lags omitted;
5. posting date compared with instruction or value date;
6. two representations of one released page mistaken for independent stages;
7. page/source IDs mistaken for payment IDs;
8. direction inferred inconsistently from signs or descriptions;
9. ordinary round-number preference mistaken for regulatory-threshold
   avoidance;
10. truncated provenance IDs causing false merges or missed deduplication.

Direction quality illustrates the risk: 26,204 of 52,549 amount-bearing rows
(49.866%) have `direction='unknown'`; another 258 (0.491%) have a debit-positive
or credit-negative sign/direction combination. These facts do not make the
amount unusable, but they preclude a naive conserved-flow equation.

The `Input-dependency` discussion is likewise **partially sufficient**. It
correctly distinguishes public and private decisive ledgers, but the payment
case must add a stricter rule: one party's statement or multiple extractions of
one page do not count as two adjacent ledgers.

---

## 2. THE RUN

### Pre-registered models and parameters

The pre-registration fixed these stage models before results:

| model | adjacent stages | proposed join | invariant | run decision |
|---|---|---|---|---|
| payment event | instruction → transfer → receipt | stable transfer/confirmation ID | receipt = instruction − explicit fees ± explicit FX | run only if independent stages and key exist |
| account reconciliation | opening balance → signed transactions → ending balance | `statement_id` | residual = ending − (beginning + Σ signed transactions), tolerance ±1 cent | run if statements and linked transactions exist |
| attribution path | account → entity → counterparty | none | none; these are dimensions, not stages | reject as mass balance |

The payment-event model had no join key or receipt stage. The account model had
no statement rows or transaction links. Both mass-balance runs therefore
returned **not computable**, not a numeric residual.

### Stage and timing results

| test | numerator | denominator | result |
|---|---:|---:|---:|
| transaction rows resolving to instruction + receipt | 0 | 53,100 | **0.000%** |
| transaction rows resolving to a complete statement | 0 | 53,100 | **0.000%** |
| linked transactions outside statement period | 0 | 0 linked rows | **not computable** |
| output-before-input pairs | 0 | 0 paired events | **not computable** |
| row-local `txn_day_min > txn_day_max` | 0 | 52,063 dated rows | 0, but not a chain test |

A tempting proxy—same page, same day, same absolute amount, opposite signs—finds
681 groups containing 1,467 active rows and $1,543,619,333.10 of one-sided
absolute amount. I did **not** count those as instruction/receipt pairs. They
are not independently observed stages; using them would manufacture perfect
conservation from reversals, internal book entries, or duplicate
representations.

### Duplicate-identifier test

The substrate-independent duplicate test ran, but only the extraction identity
layer exists:

| measure | result |
|---|---:|
| duplicate `(source_system_id, source_native_id)` groups | **0** (also schema-unique) |
| null `source_native_id` | 0 |
| repeated `dedupe_key` groups | **801** |
| rows in repeated `dedupe_key` groups | **1,819** |
| excess rows above one per hash | **1,018** |
| rows flagged `is_duplicate_of` | **1,005** |
| flagged within Kabasshouse | 970 |
| flagged Kabasshouse → LMSBAND cross-source | 35 |
| LMSBAND-only repeated-hash groups left unflagged | **42 groups, 90 rows, 48 excess rows** |
| orphan duplicate pointers | 0 |

The 48 uncollapsed LMSBAND excess rows are consistent with the builder's
documented asymmetry: it collapses within-Kabasshouse duplicates and marks
Kabasshouse copies against LMSBAND, but does not perform a within-LMSBAND pass.
This is a real duplicate-record screen result, not evidence of repeated payment
identifiers.

`canonical_ref` repeats heavily—51,767 rows across 3,954 multi-row refs—because
it is a document/page identifier. Treating that reuse as duplicate payments
would be a category error, amplified by the 116 truncated LMSBAND refs.

### Exact-threshold sensitivity

The pre-registered screen excludes duplicate/structural rows and flagged
outliers. Denominators are 31,676 active amount rows and 2,180 `wire|transfer`
amount rows. “Neighbor mean” is the mean count at the ten exact-dollar values
`T−5..T−1,T+1..T+5`.

| exact amount | active count (rate) | neighbor mean | active lift | `wire|transfer` count (rate) | neighbor mean | payment lift |
|---:|---:|---:|---:|---:|---:|---:|
| $1,000 | 159 (0.502%) | 0.8 | 198.75× | 10 (0.459%) | 0 | undefined |
| $5,000 | 193 (0.609%) | 0.1 | 1,930× | 35 (1.606%) | 0 | undefined |
| $10,000 | 228 (0.720%) | 0.1 | 2,280× | 31 (1.422%) | 0 | undefined |
| $50,000 | 487 (1.537%) | 0 | undefined | 98 (4.495%) | 0 | undefined |
| $100,000 | 401 (1.266%) | 0 | undefined | **117 (5.367%)** | 0 | undefined |

This screen proves that exact round amounts are common and that the immediate
exact-dollar comparator is often degenerate. It does **not** prove bunching at
a regulatory threshold. Card 39 supplies no threshold, jurisdiction, effective
date, transaction class, or below/above bandwidth, and ordinary wires are
strongly round-number heaped. A valid threshold test would pre-register a real
rule and compare the distribution immediately below versus above it against a
matched payment-class baseline.

### Headline

**The mass-balance move returned no residual because 0 of 53,100 records resolve
to two adjacent payment stages.** Amount/date completeness is 97.038% jointly,
so the binding failure is not parsing. It is the absence of a second ledger,
stable payment key, account boundary, and control population.

---

## 3. CONTROL / BASELINE

The card-faithful control could not be constructed. There are no recomputable
statement residuals and no compliant operator/route labels. Consequently:

```
test residual distribution:       not computable
compliant residual distribution:  not computable
residual lift:                     not computable
```

The source contains a `ds10_statement_recon` schema with the right conceptual
fields—beginning balance, ending balance, parsed inflow/outflow totals,
recomputed ending balance, residual, eligibility, and status—but it contains
**0 rows**. Schema potential is not a held baseline.

The threshold screen's neighboring-dollar counts are reported because they
were pre-registered, but their many zero means make lift undefined and they do
not satisfy the card's null-population discipline. A future payment card needs
one of:

- independently audited/reconciled accounts from the same institution and
  period;
- matched routes/operators with an externally determined compliance status;
- for a named legal threshold, matched transaction classes and a
  discontinuity design around the threshold, with non-round placebo points.

Without one of those, a raw residual or exact-amount rate is a data-quality
observation, not an investigative finding.

---

## 4. AMENDMENTS REQUIRED

1. **Remove “payment chain” from card 39's title and remove the claim that
   `epstein_derived (query_fin)` runs the variant today.** The held sidecar has
   no adjacent payment stages, stable transfer key, account links, statement
   rows, or residual control. Keeping the claim invites a false mass balance.

2. **Split the surviving payment tests into a separate
   `payment-record-integrity` card.** Its mechanics should be stable payment-ID
   reuse, named-threshold discontinuities, and impossible stage timing. These
   are useful and substrate-independent, but they are not commodity
   mass-balance invariants.

3. **Permit payment conservation only under an explicit closed-ledger
   precondition.** Suggested text: “Within one account and currency, reconcile
   `ending = beginning + signed transactions`; across a transfer, compare
   independent instruction and receipt records on a persistent transfer ID,
   subtracting only explicit fees and applying recorded FX. Do not infer
   conservation from aggregated entity/counterparty text.”

4. **Replace “conversion-loss bounds” for payments.** Require exact cents,
   declared gross/net treatment, explicit fees, recorded FX rate/leg, reversal
   policy, internal-transfer policy, and a pre-registered settlement lag. There
   is no defensible generic monetary shrinkage range.

5. **Add a payment Preconditions field.** It must gate execution on independent
   adjacent ledgers, a stage-persistent key, account/currency boundaries,
   opening/ending balances for reconciliation, precise stage-specific dates,
   and a constructible compliant control. If any gate fails, the result is
   “not computable,” not zero residual.

6. **Expand Coverage statement.** Require count and absolute-value coverage for
   stage join, amount, currency, account, and ordering date; report their
   intersection. Preserve `date_raw` and `date_precision` in
   `financial_transaction` so coarse dates can be quantified without reopening
   source corpora.

7. **Specify duplicate-identifier semantics.** A payment duplicate test must
   name the business identifier (`confirmation_number`, bank reference,
   end-to-end ID), not `source_native_id`, `canonical_ref`, or an extraction
   hash. Add a warning that page-ID reuse is expected. Extend the builder's
   dedupe audit to disclose the 42 LMSBAND-only repeated-hash groups rather than
   assuming all repeated hashes are collapsed.

8. **Specify threshold tests completely.** Require jurisdiction, rule,
   effective dates, covered transaction class, exact threshold, below/above
   bandwidth, matched control, and placebo thresholds. Warn that round-number
   heaping can produce enormous or undefined exact-dollar lift without
   threshold avoidance.

9. **Define the payment control before the mapping can be called runnable.**
   State how “compliant” is determined independently of the residual, which
   account/route population forms the null, and which statistic reports lift.
   A `recon_status` produced by the same residual calculation would be circular
   unless independently validated.

10. **Amend the Ithildin mapping with the actual gaps.** Preserve structured
    `confirmation_number`, `reference`, sender/receiver account, statement ID,
    currency, and stage dates in the sidecar; ingest an independent receipt or
    settlement ledger; populate account/statement joins; expose reconciliation
    and coverage in `query_fin`. Until then, label `query_fin` as a one-sided
    transaction/amount screen.

11. **Add payment-specific failure modes.** Open perimeters, netting, re-entry,
    internal transfers, fees/FX, reversals, posting-versus-value dates,
    duplicate representations, missing direction, provenance truncation, and
    ordinary round-number preference must be explicit.

12. **Add a provenance gate for the known EFTA defect.** Before any page-based
    dedupe or join, reject or quarantine truncated refs. This build still holds
    116 LMSBAND rows under `EFTA00`, `EFTA001`, or `EFTA0013`; 131 LMSBAND rows
    lack an evidence-item link.

---

## 5. VERDICT

**blocked-on-paired-payment-stages-and-stable-transfer-identifiers.** Card 39
overreaches when it presents a “commodity/payment chain” as one conserved-flow
move and states that the Epstein sidecar runs the payment variant today. A
monetary invariant is valid only inside a closed account reconciliation or
across independently observed transfer stages with explicit fee/FX treatment.
This sidecar has 53,100 transaction rows but zero account rows, zero statement
rows, zero stage links, and no payment ID carried across stages; the combined
coverage ceiling is therefore **0.000%** and the demanded compliant residual
control does not exist.

The claim should be **split**, not merely softened. Keep card 39 as commodity or
closed-ledger mass balance. Create a separate payment-record-integrity card for
the tests that genuinely survive: business-ID duplicates, named-threshold
discontinuities, and impossible stage timing. On the current platform, only an
extraction-duplicate audit and an uncalibrated round-amount sensitivity screen
ran. A future agent invoking the present payment variant should expect **no
mass-balance result, even when amounts and dates are mostly complete**.

---

### Scratch artifacts (not persisted to the repository)

`/tmp/osint-qEMfjM8N/preregistration.md`,
`/tmp/osint-qEMfjM8N/analyze_card39.py`,
`/tmp/osint-qEMfjM8N/card39-results-final.json`,
`/tmp/osint-qEMfjM8N/query-fin-spend.txt`, and
`/tmp/osint-qEMfjM8N/query-fin-outliers.txt`.

---

## ADDENDUM — 2026-07-29: the closed-ledger form is now runnable

Three of the extraction gaps this memo identified were closed in
`tools/build_financials.py` + `tools/epstein_derived.py`. **The memo's verdict on
the payment-chain variant is unchanged and still correct** — there is still no
second ledger, no stage-persistent transfer identifier, and no compliant-route
control, so `output <= input` across a transfer remains un-executable and
`blocked-on-paired-payment-stages-and-stable-transfer-identifiers` still stands.
What changed is the narrower **closed-account reconciliation** this memo named as
the only defensible monetary invariant. It is no longer at zero coverage.

### What is now populated

| table / field | before | after |
|---|---:|---:|
| `financial_account` | 0 | **566** (`source_account_number` 87, `owner_digits` 165, `digits` 30, `owner` 284) |
| `financial_statement` | 0 | **4,759** |
| `financial_transaction.account_id` | 0 | **43,554 (82.02%)**; digit-anchored 11,115 (20.93%) |
| `financial_transaction.statement_id` | 0 | **49,859 (93.90%)** |
| `balance_snapshot.account_id` | 0 | **565 of 590** |
| `counterparty_raw` | 684 (1.3%) | **6,481 (12.21%)** |
| `intermediary_bank_raw` | (no column) | **8,248 (15.53%)** |

`key_basis` is stored on every account precisely because the memo was right that
volume hides the binding constraint: the 82% account-link rate is mostly the
`owner` tier, which groups one party's statements and is **not** one account.
Only the 20.93% digit-anchored tier is account identity.

### The reconciliation result

```
computed_ending = beginning_balance + charges + payments
residual        = ending_balance - computed_ending      (tolerance +/-1 cent)
```

**605 of 4,759 statements (12.71%) are computable; 319 reconcile to within 1 cent
(52.7% of computable), 286 carry a residual.** Coverage by basis:

| recon_basis | computable / total | reconciles |
|---|---:|---:|
| `boundary_markers` (kabass Beginning/Ending Balance rows) | 557 / 557 | 290 |
| `declared_totals` (card statements' own totals) | 9 / 74 | 0 |
| `fund_totals` (ds09 fund statements) | 39 / 42 | 29 |
| `none` (no boundary balance extracted) | 0 / 4,086 | — |

The transaction-level intersection the memo asked for — amount parseable AND
ordering date usable AND member of a computable statement — is **7,630 of 53,100
rows (14.369%)** and **$1,983,931,559.66 of $26,336,020,071.84 gross absolute
amount (7.533%)**, up from 0 / 0.000% on both measures. Reproduce with
`uv run python tools/query_fin.py coverage`.

A missing boundary balance or any unparseable member amount yields
`recon_status='not_computable'`, never a zero residual — the memo's central
warning, enforced in code.

### The residuals are, first, a data-quality screen

This is *not* a diversion signal, and the card must not be read as though it
were. Of the 286 residuals:

- **111** have `ending_balance_minor = 0` — the Ending Balance row's amount
  failed OCR. In the Haze Trust series the computed ending of each month equals
  the *declared beginning* of the next to the cent, which independently confirms
  the arithmetic and localizes the error to the ending-balance extraction.
- **14** are exactly round dollar amounts, the signature of a digit/decimal OCR
  slip rather than an economic gap.
- **All 9** computable `declared_totals` card statements fail their own internal
  identity, **5** of them with `|payments| > 10x` the previous balance (e.g.
  $96,613.00 paid against a $2,429.04 balance on a $35,000 credit line) and one
  with a residual of exactly $5,000.00. The LMSBAND `ds09_cc_statements` declared
  totals should be treated as unreliable until re-extracted.

So the honest reading is that the closed-ledger move now runs, and what it
currently measures is extraction fidelity. The memo's demand for a control
population is still unmet: `recon_status` is produced by the same residual
calculation, so it cannot serve as its own compliant baseline.

### Amendments now satisfied, and those still open

Satisfied: **#6** (coverage by count and amount, per dimension and intersected —
`query_fin coverage`); **#7** (the builder now runs a within-LMSBAND dedupe pass;
the 42 unflagged groups / 48 excess rows are collapsed, and page-ID reuse is
documented as expected); **#10** in part (account and statement joins populated,
reconciliation and coverage exposed in `query_fin`); **#12** (truncated refs are
detected, their `dedupe_key` is salted with the source row id so they cannot
false-merge, and `query_fin review --truncated-refs` surfaces all 116).

Still open: **#1–#5, #8, #9, #11** — the card's own title, the split into a
separate `payment-record-integrity` card, the payment Preconditions field, the
threshold-test specification, the control definition, and the payment-specific
failure modes. `date_raw` / `date_precision` are still not preserved on
`financial_transaction` (part of #6). `confirmation_number` is still dropped and
`reference` still folded into `raw_description` (part of #10), so the
business-identifier duplicate test #7 asks for remains unavailable.

Two defects surfaced while closing these gaps, both fixed in the builder:

1. **The dedupe was creating false duplicates.** `description` and `merchant_raw`
   are mutually exclusive in kabass (49,680 rows carry exactly one, 0 carry
   both), and the builder read only `description` — so the 25,815 rows whose
   statement line lived in `merchant_raw` all hashed with an empty description.
   **723 of the 1,005 previously flagged duplicates were distinct transactions**:
   different check numbers ("Check 1158" vs "Check 1152", same page, same date,
   same $600) and, in one case, an $8,000,000 inflow and an $8,000,000 outflow
   collapsed into a single row. 722 of the 723 have a same-page/date/amount
   sibling with a demonstrably different statement line; 0 remain true
   duplicates. Any prior `query_fin spend` or duplicate-rate figure computed
   before this fix is affected.
2. `financial_transaction.is_duplicate_of` is a self-FK with no index, so with
   `PRAGMA foreign_keys=ON` the builder's delete-and-reinsert rebuild scanned the
   whole table per deleted row (~10 minutes at 53K rows). Indexed.
