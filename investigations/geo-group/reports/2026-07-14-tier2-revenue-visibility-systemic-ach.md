# Tier 2 systemic/ACH audit — GEO CY2025 revenue visibility

**Date:** 2026-07-14  
**Profile:** `geo-group`  
**Systemic-analysis run:** `109`  
**Generate-hunches run:** `110`  
**Scope:** verified findings only; no external queries; no HigherGov use

## Exact bounded verdict

Finding `#12964` is **not new IGSA-specific evidence of financial materiality**. It is a bounded, companywide public contract-to-ledger visibility result: the reviewed filing and award record does not supply a CY2025 ICE customer subledger joining recognized revenue to contracts, facilities, invoices, receivables, outlays, or local remittances.

The finding adds **zero independent IGSA-chain contexts** and **zero compatible IGSA downstream-dollar observations**. Its reference to six public-prime chains carries forward the already-verified architecture in findings `#12668` and `#12727`; it does not measure those chains. It therefore cannot assign any amount—especially the `$553,279,205.03` different-metric arithmetic gap—to IGSAs, pass-throughs, or recipient-attribution loss.

Context-normalized ACH remains unchanged from the prior Tier 2 result: hypothesis `#341` is least evidence against for the existence of a recipient-name visibility mechanism, while its financial-materiality clause remains unresolved. Hypothesis `#342` retains more verified evidence against it, but the five adverse matrix rows reduce to two independent contexts—Joe Corley and Val Verde—not five chains or five dollar observations. Neither hypothesis is confirmed or refuted.

## Measurement-plane comparison

| Plane | Verified Wave 8 observation | What it can establish | What it cannot establish |
|---|---|---|---|
| Issuer revenue | GEO reported consolidated CY2025 revenue and a rounded 47.6% ICE share | A mechanical ICE-revenue point/range estimate | Contract, facility, prime, invoice, cash, or IGSA allocation |
| Direct-prime actions | 124 CY2025 ICE actions across 34 GEO/B.I. task/order PIIDs total `$699,338,118.97` in action-date obligations | Bounded direct-recipient obligation flow for CY2025 | Recognized revenue, CY2025 cash, or downstream public-prime receipts |
| Award-life snapshots | 34 awards show `$2,124,471,883.77` cumulative obligations; 32 report `$1,939,034,265.44` cumulative outlays | Current award-life context | A CY2025 flow; the two unreported outlay fields are not zero |
| Mixed activation disclosure | Quarterly change residuals reconcile to `$152.4m` | Internal arithmetic consistency of the issuer's mixed change bundle | ICE-only, facility-level, contract-level, or IGSA revenue |
| Public-prime chains | Six ICE chains lack one compatible CY2025 downstream GEO total | A known public-prime visibility boundary | Six-chain financial materiality or a share of GEO revenue |
| Internal customer ledger | No such schedule appeared in the fully parsed filing sequence | A bounded public-disclosure limit | Proof that an internal or nonpublic ledger does not exist |

Recognized revenue, action-date obligations, current cumulative obligations, current cumulative outlays, invoices, public-prime remittances, and cash are different accounting objects. The `$553,279,205.03` subtraction is only the rounded ICE-revenue point estimate minus CY2025 direct action obligations. It is not missing money and is not an IGSA residual.

## Audit of Wave 8 findings

### Finding #12962 — mixed activation/transport sequence

The quarterly residuals are correctly bounded as a mixed recognized-revenue change bundle. Because the bundle is not ICE-only and does not allocate a public-prime channel, it is neutral to both `#341` and `#342`.

### Finding #12963 — award-snapshot boundary

The finding correctly separates current award-life obligations and outlays from CY2025 flows and preserves two missing outlay values as missing. Those direct-prime snapshots neither identify nor quantify downstream IGSA economics, so they are neutral to both hypotheses.

### Finding #12964 — customer-to-contract ledger coverage

Tier 1 rows `#793` and `#794` over-scoped the finding by treating a companywide ledger absence as directionally diagnostic of the narrower IGSA materiality pair. That inference does not survive context normalization:

- Absence of a public GEO customer subledger is not evidence that the legal-recipient layer caused the absence.
- The source set does not supply matched-period federal obligations, public-prime receipts, GEO invoices/remittances, and retained fees for the six-chain denominator.
- Ordinary accrual timing, service-period differences, entity scope, direct-prime activity, transportation, and other categories remain nonexclusive explanations for the companywide bridge failure.
- The six-chain statement is inherited from prior verified findings rather than a new independent context.

Tier 2 replacement rows `#803` and `#804` therefore score `#12964` **neutral** to both hypotheses while preserving the original Tier 1 rows. Rows `#799`–`#802` add the same measurement-control treatment for findings `#12962` and `#12963`.

## ACH before and after context normalization

| State | Hypothesis | Consistent | Inconsistent | Neutral | Not applicable | Inconsistency ratio |
|---|---|---:|---:|---:|---:|---:|
| Before Wave 8 Tier 2 audit | `#341` material GEO IGSA exposure gap | 21 | 0 | 28 | 10 | 0.0000 |
| Before Wave 8 Tier 2 audit | `#342` accurate legal-prime reporting/no material gap | 8 | 6 | 35 | 10 | 0.1224 |
| After Wave 8 Tier 2 audit | `#341` material GEO IGSA exposure gap | 20 | 0 | 31 | 10 | 0.0000 |
| After Wave 8 Tier 2 audit | `#342` accurate legal-prime reporting/no material gap | 8 | 5 | 38 | 10 | 0.0980 |

The formal counts use the latest assessment for each finding-hypothesis cell. All consistent, inconsistent, and neutral cells in the post-audit matrix are verified findings; seven unverified rows per hypothesis remain expressly `not_applicable`.

The five remaining `#342` inconsistent cells are findings `#12660`, `#12661`, `#12668`, `#12713`, and `#12714`. They normalize to two independent contexts:

1. **Joe Corley / ICE:** two structured-query results plus their aggregate synthesis.
2. **Val Verde / CBP:** the direct-GEO-to-county replacement and its route synthesis.

This is evidence against straightforward recipient-level recovery in two contexts, not evidence that the visibility loss is financially material across six ICE chains.

## Systemic result

Wave 8 adds a useful layer distinction but no new system-level causal mechanism. The public record has three observable disclosure planes—issuer revenue, federal award transactions, and selected local/public-prime records—with no common service-period key or complete downstream payment join. That is a contract-to-ledger observability boundary. It does not show that public-prime routing created the entire boundary, that GEO designed the boundary, or that the boundary has a uniform financial effect.

The relevant base-rate control remains visible direct contracting: GEO and B.I. appear as direct ICE recipients in the CY2025 action ledger, and prior CBP review found direct-GEO comparator chains. Public-prime routing is therefore a demonstrated mechanism in some chains, not a universal architecture.

## Generate-hunches novelty decision

No new hunch passed the required novelty and independence gates.

| Candidate pattern | Gate result | Decision |
|---|---|---|
| Multi-plane contract-to-ledger observability gap | Already captured by `#341/#342`, `#12668`, and `#12727`; Wave 8 adds one bounded filing/ledger context | No new hypothesis pair |
| Different-metric arithmetic gap as hidden pass-through value | Fails measurement validity; revenue and obligations are not interchangeable | Reject, not a hunch |
| Mixed activation disclosure as deliberate channel concealment | No intent evidence, no three independent contexts, standard issuer aggregation is an adequate alternative | Reject |
| Public-prime routing explains most of unallocated ICE revenue | No compatible six-chain downstream total and no allocation rule | Reject |

No new synthesis finding, hypothesis, lead, tag, entity, or connection was created. Existing lead `#57974` remains the nonduplicate Layer 1 route.

## Next best discriminator

Build a **matched-service-period six-chain reconciliation**, one chain at a time, with four linked records for the same facility and period:

1. funded ICE task-order obligation and dated federal outlay;
2. public-prime receipt and any administrative fee retained;
3. GEO invoice and public-prime-to-GEO remittance;
4. structured subaward/award-description fields available for that same transaction.

Predefine two measures before interpreting the result: (a) GEO identity recovery rate across the six chains, and (b) structured-dollar recovery as compatible structured downstream dollars divided by verified local GEO remittances. Do not use companywide revenue minus federal obligations as the denominator. A complete matched reconciliation across most chains would discriminate `#341/#342`; another filing search or award-database copy would not.

## Database outputs

- Replacement/control ACH rows: `#799`–`#804`.
- Hypothesis statuses: `#341` and `#342` remain `proposed`.
- New findings: none.
- New hypotheses: none.
- New leads: none.
- New tags/connections/entities: none.
- External queries: zero.

The companion evidence matrix records the original and replacement assessments. The source/finding manifest records the exact input artifacts, hashes, finding snapshots, database writes, and integrity checks.
