# Tier 2 systemic analysis — GEO ICE contract architecture

Date: 2026-07-13  
Profile: `geo-group`  
Skill: `systemic-analysis`  
Analysis run: `86`  
Companion ACH ledger: `2026-07-13-tier2-systemic-contract-architecture-ach.csv`

## Executive verdict

The completed evidence establishes a recurring procurement topology, not a uniform economic or control effect.

Nine GEO SEC facility rows resolve to six independent chains in which ICE contracts with a local public prime and GEO occupies the documented operator, subcontractor, or economic role beneath it. The six chains do not share a single recoverable pricing or control template. Two disclose same-federal-rate pass-throughs, three expose some form of local fee or retained value, two document GEO-initiated equitable-adjustment activity, and only one supplies a near-complete annual ICE-to-local-to-GEO waterfall. Those features overlap, but their terms, periods, current status, and attribution limits differ materially.

The strongest disconfirmation is affirmative, not merely missing data:

- LaSalle's local agreement expressly says neither the State nor LEDD guarantees a minimum.
- Joe Corley makes ICE liable only for actual detainee days; its 1,050-bed exclusive-use allocation is not a guaranteed payment.
- Tacoma's contemporaneous population exceeded its historical minimum, yielding a zero-unused snapshot.
- Torrance, a non-GEO comparator, shows ICE imposing a 25 percent billing reduction and cutting a minimum, whereas Folkston records attempted penalties that were not enforced.
- Numeric or redacted guarantee architecture appears in at least five GEO direct-prime contract/source families, so it is not distinctive to the public-prime layer.

The recipient-visibility gap is real as a mechanism and still unquantified as a six-chain financial total. Verified exact Joe Corley queries returned no HigherGov award record and no USAspending Montgomery/DHS prime record. LaSalle's audited fiscal-2023 waterfall is financially substantial in one chain. But Joe Corley's $43.19 million county fund combines ICE and USMS and does not name GEO as payee; Evangeline and Clearfield amounts have unresolved payer/payee or accounting direction; Charlton and Karnes remain unquantified. The evidence therefore does not support a system-wide dollar estimate or a claim that the structured gap is financially material across most of the six chains.

## Denominator discipline

| Plane | Correct denominator | Analytical use |
|---|---:|---|
| SEC IGSA facility rows | 9 | Physical facility-row coverage only |
| Independent public-prime chains | 6 | Economic, control, and hypothesis context count |
| Identity search manifest rows | 75 | Search inputs, not subsidiaries |
| Canonical legal identities | 62 | Normalized legal-entity denominator |
| Federal recipient registrations | 14 | 12 current registrations plus 2 legacy recipients |
| Legal identities used as ICE prime recipients | 6 | Bounded verified direct-recipient universe |

Three facility pairs share one chain and one set of chain-level economics: Alexandria/Central Louisiana, D. Ray James/Folkston, and Pine Prairie/South Louisiana. Multiple findings, documents, or structured-source queries within one chain are not independent contexts.

## Six-chain comparison

| Independent chain | Repeated topology | Recovered economic/control effect | Disconfirmation or attribution limit |
|---|---|---|---|
| Karnes County | ICE public prime; subcontract flow-down required; GEO facility role in SEC crosswalk | Funded annual task orders; invoice-to-CLIN substantiation | Base action is $0; downstream agreement, fee, funded orders, and GEO payment are missing |
| LaSalle EDD | ICE → LEDD → GEO for Alexandria/Central Louisiana | Same federal per diem and adjustments passed to GEO; tiered $5k/$10k/$15k monthly fee; ICE/LEDD inspection; fiscal-2023 ICE revenue $39.803m and GEO expenditure $39.803m | Local agreement expressly disclaims a State/LEDD minimum; the $232 revenue/expenditure difference prevents an exact same-dollar characterization |
| Charlton County | ICE → county → GEO for Folkston/D. Ray James | Quarterly county audit and bilateral 30-day convenience termination | Operator rate and county fee are redacted; Folkston full funding continued despite attempted penalties; downstream dollars are absent |
| Clearfield County | ICE → county; GEO submitted the REA | Fiscal-2024 budget shows a $4.687m GEO/ICE account and $166,667 fee-from-GEO account | The $4.687m sign/direction and task-order mapping are unresolved; local operator agreement is missing |
| Evangeline Parish Sheriff | ICE → sheriff → GEO for Pine Prairie/South Louisiana | Fiscal-2024 GEO-agreement-linked fund reports equal $39.455m additions and reductions | The lines do not identify ICE payer or GEO payee; local agreement and current pricing are missing |
| Montgomery County | ICE/USMS → county → GEO for Joe Corley | Same federal per diem passed to GEO net of a historical $500k annual fee; GEO submitted current REA; written orders and actual detainee days govern ICE liability | County fund combines ICE and USMS; later fee amendments and GEO payment split are missing; exact HigherGov and USAspending queries returned no record |

### What recurs across three or more chains

- The public-prime/private-operator topology recurs in all six chains.
- A public-body fee or fee-like retained-value record appears in LaSalle, Clearfield, and Montgomery, but the forms are not comparable: tiered monthly, a budget revenue account, and a historical fixed annual fee.
- No other economic or control mechanism is presently verified in three independent chains with comparable current terms.

The three-chain fee observation is not a new phenomenon. Administrative fees are already an explicit prediction of hypothesis #333 and are already covered by leads #57966 and #57974. It therefore does not justify a duplicate hypothesis pair or lead.

## Direct-recipient concentration versus IGSA visibility

The direct-recipient plane is fragmented in registration but concentrated in use:

- The manifest's 75 rows normalize to 62 canonical identities.
- Fourteen federal recipient registrations resolve to 12 current and 2 legacy registrations.
- Only six GEO legal identities appear as ICE prime recipients in the bounded verified scan.
- The GEO parent and B.I. account for 1,240 of 1,362 ICE action rows, or 91.0 percent. This is an action-row concentration, not a dollar share.
- The corrected direct-prime ledger contains $6.354 billion in ICE net action obligations for 2015-01-01 through 2026-07-13. It is a flow of action obligations, not payments, revenue, ceilings, or guarantees.

Alias resolution therefore materially improves direct-prime coverage, but it does not solve IGSA attribution. The six IGSA public primes sit on a different legal-recipient plane. At the same time, the large verified direct-prime ledger is a base-rate caution: recurring public-prime topology does not by itself show that the omitted downstream layer is large relative to GEO's visible direct channel.

## ACH reassessment

Forty verified GEO-profile findings were assessed against every hypothesis in both canonical pairs. The full finding-by-hypothesis ledger records independence groups so raw finding counts are not mistaken for independent contexts.

Unverified findings #12394, #12395, #12403, #12409, #12411-#12416, #12443, #12474, and #12483 were excluded. All retracted findings, including #12630-#12641 and #12649, were excluded. Prior evaluations of prohibited rows were set to `not_applicable` for run 86 and do not enter the run's scores.

| Competition | Hypothesis | Evaluated | Inconsistent | Diagnostic | Ratio | Least-evidence-against verdict |
|---|---|---:|---:|---:|---:|---|
| `geo-igsa-intermediary-layer` | #333 — recurring local intermediary economics | 40 | 0 | 21 | 0.00 | Tie |
| `geo-igsa-intermediary-layer` | #334 H0 — ordinary facility-specific public-owner arrangements | 40 | 0 | 21 | 0.00 | Tie |
| `geo-igsa-recipient-visibility` | #341 — material GEO IGSA exposure gap | 40 | 0 | 20 | 0.00 | Least evidence against, with materiality caveat |
| `geo-igsa-recipient-visibility` | #342 H0 — accurate legal-prime reporting creates no material gap | 40 | 2 | 20 | 0.05 | More evidence against |

### Pair #333 / #334

Formal ACH remains tied. The hypotheses are not cleanly exclusive: a recurring intermediary layer can simultaneously consist of ordinary, facility-specific arrangements. None of the verified evidence contradicts the broad statement that economics run through public primes, and none contradicts the null's prediction of varied local terms.

For the narrower question posed in this run—common economic/control effect versus repeated topology—the evidence favors repeated topology with materially varied terms. That is not a formal refutation of #333 because #333 does not require one universal fee, guarantee, remedy, or allocation rule.

### Pair #341 / #342

#341 has the least evidence against because two verified Joe Corley records are inconsistent with #342's prediction of straightforward structured recoverability. Those are two source results for one chain, not two independent facility contexts. They demonstrate a bounded recovery failure, not system-wide financial materiality.

The financial-materiality component of #341 remains unresolved:

- LaSalle is one quantified chain.
- Joe Corley is a large but mixed ICE/USMS fund with no identified GEO payment.
- Clearfield and Evangeline are partial or ambiguous accounts.
- Charlton and Karnes lack downstream dollars.
- The excluded five-chain structured-search finding #12443 cannot be used to multiply the Joe Corley result across the sample.

The precise verdict is therefore: **#341 is least evidence against for the existence of a structured attribution blind spot; neither #341 nor the evidence proves that the blind spot is financially material across the six-chain system.**

## Base-rate and selection limits

1. The six chains were selected because they are GEO-linked IGSAs. They are not a random or complete sample of all ICE IGSAs.
2. Direct-prime guarantee records were selected for guaranteed-minimum analysis. Their frequency cannot be converted into an industry prevalence rate.
3. A local public prime with a private operator is not inherently opaque or unusual; ICE's IGSA authority and facility ownership can generate the topology without coordination.
4. Exact-query zero results can reflect indexing, recipient normalization, task-order hierarchy, or endpoint coverage. They establish failed recovery under the recorded query, not absence of the underlying contract.
5. Dollars in the bundle are not compatible for summing: action obligations, local fund inflows/outflows, unit rates, fees, task adjustments, and unused-capacity payments are different accounting objects and periods.
6. No evidence shows lateral coordination among the six public primes, a GEO-designed common template, deliberate concealment, improper influence, or procurement causation.

## Novelty and Layer-1 routing

No genuinely new phenomenon survived the three-independent-context and novelty gates. No new hypotheses and no new leads were created.

Existing nonduplicate Layer-1 coverage is sufficient:

- #57966 — compare IGSA control, fee, procurement, and risk-allocation terms; currently blocked after partial completion.
- #57974 — measure structured attribution and downstream dollars; currently blocked after partial completion.
- #60026 — obtain current Joe Corley task orders, invoices, agency split, and county-GEO amendments; open.
- #60204 — reconcile Golden State minimum revision and unused-capacity invoices; open.
- #60206 — recover current Adelanto/Desert View, Aurora, and Tacoma schedules and invoices; open.
- #60208 — recover South Texas and Folkston guarantee, occupancy, invoice, and remedy records; open.

The fastest discriminator for #341/#342 remains #60026 plus a repaired primary subaward/FSRS workflow. The fastest discriminator for the common-effect question is completion of #57966 across all six chains with a non-GEO IGSA baseline.

## Database outputs and audit

- New verified synthesis finding: #12668 (`claim_type=synthesis`, `confidence=medium`).
- New hypotheses: none.
- New leads: none.
- New tag: finding #12668 tagged `systemic=ICE IGSA public-prime/private-operator architecture` by `agent:systemic-analysis:run-86`.
- New entities, relations, or graph connections: none.
- ACH writes: 40 verified findings scored against #333, #334, #341, and #342; prohibited/non-independent prior rows explicitly marked `not_applicable` for this run.
- Provenance: finding #12668 has 11 evidence rows and 11 non-empty source quotes; verification completed by `agent:systemic-analysis:run-86`.

## Source bundle

- `2026-07-13-geo-federal-recipient-identity-map.md`, `.csv`, `.json`
- `ice-igsa-nine-facility-chain-2026-07-13.md`, `.csv`, `.json`
- `2026-07-13-geo-ice-guaranteed-minimum-economics-report.md`
- `2026-07-13-geo-ice-guaranteed-minimum-facility-matrix.csv`, `.json`
- `systemic-analysis-ice-igsa-pass-through-2026-07-13.md`
- `2026-07-13-dhs-wide-geo-procurement-scan.md`
- `audit-contracts-2026-07-13.md`

This report uses the completed artifacts only as a routing and denominator layer. Every ACH row and the new synthesis finding are grounded in verified database findings; unverified and retracted records are not used in the verdict.
