# Systemic Analysis Report — 2026-07-13

## Run and Scope

- Analysis run: `systemic-analysis` #75
- Active profile verified before every database write: `geo-group`
- Requested scope: global thread 110, Procurement Vehicles, Entities & Money Flow
- Analytical focus: the ICE IGSA/pass-through system around GEO
- Evidence boundary: existing primary-source findings and reviewed ICE/SEC instruments. No claim here establishes coordination among the public intermediaries, improper influence, or deliberate concealment.

## Target Group

Eight structured actors were selected:

1. The GEO Group Inc. — entity #1290, Florida corporation
2. GEO Secure Services, LLC — entity #4811, Florida LLC and documented GEO subsidiary
3. U.S. Immigration and Customs Enforcement — entity #4813, federal agency
4. Charlton County, Georgia — entity #4825, county government
5. Evangeline Parish Sheriff’s Office — entity #4826, Louisiana public law-enforcement body
6. LaSalle Economic Development District — entity #4827, Louisiana public development district
7. Clearfield County, Pennsylvania — entity #4828, county government
8. Karnes County, Texas — entity #4829, county government

The first seven existing entity records were type/jurisdiction-enriched through the canonical resolver. Karnes County was newly registered. The repository currently does not backfill authoritative `source` or `notes` onto pre-existing `auto:connect` stubs; papercut #765 records that provenance limitation. Authoritative support is instead preserved on the ten new entity relations and the underlying findings.

## Comparison Matrix

| Actor | Public ICE counterparty | GEO explicitly named subcontractor | Other GEO economic/operating evidence | Current jurisdiction/type evidence |
|---|---:|---:|---:|---|
| Charlton County | Yes | Yes | Folkston/D. Ray James path | Georgia county |
| Evangeline Parish Sheriff’s Office | Yes | Yes | Pine Prairie/South Louisiana path | Louisiana sheriff’s office |
| LaSalle Economic Development District | Yes | Yes | Alexandria/Central Louisiana path | Louisiana development district |
| Clearfield County | Yes | Not in reviewed excerpt | GEO submitted the equitable-adjustment request | Pennsylvania county |
| Karnes County | Yes | Not established by reviewed base action | Base obligates no funds; funded task orders required | Texas county |
| ICE | Federal buyer | N/A | Common federal hub | United States agency |
| The GEO Group | Direct primes elsewhere | N/A | Subcontractor in three reviewed IGSAs; REA actor in a fourth | Florida corporation |
| GEO Secure Services | Not established in reviewed IGSA excerpts | Not established | SEC Exhibit 21 establishes subsidiary relationship only | Florida LLC |

## System Patterns Found

### 1. Repeated public-prime/private-operator star architecture

**Members involved:** ICE, GEO, Charlton County, Evangeline Parish Sheriff’s Office, LaSalle Economic Development District, and Clearfield County.

**Evidence:** ICE instruments identify the local public body as contractor while naming GEO as subcontractor for Charlton, Evangeline, and LaSalle. The Clearfield modification names the county as contractor and says GEO submitted the request for equitable adjustment. Finding #12411 records the synthesis at medium confidence; source findings are #12405–#12408.

**Significance:** The strongest current network pattern is a repeated star, `ICE → local public prime → GEO operating/economic role`, across three states and three public-body forms. The local bodies are structurally similar nodes but there is no evidence they connect laterally, share decision-makers, or coordinate. The pattern therefore supports a procurement mechanism, not an intent or coordination claim.

**Base-rate and innocent explanation:** ICE IGSAs are an established administrative channel. Facility locality, state/local statutory authority, facility ownership, and standard ICE forms could independently generate the same topology. The current corpus lacks the denominator: the share and terms of all GEO and non-GEO ICE IGSAs. Without that baseline, recurrence cannot be called anomalous.

### 2. Recipient-attribution visibility gap

**Members involved:** GEO, ICE, and the four public primes above; Karnes is a task-order-structure comparator.

**Evidence:** Finding #12403’s direct-prime reconstruction expressly excludes county/state pass-throughs. Findings #12405–#12408 show GEO below a named public contractor. Finding #12412 records the system-level measurement consequence at medium confidence.

**Significance:** A recipient-name query can miss GEO’s downstream economic role even when the federal prime record is correct. This is a structural attribution problem: the federal obligation belongs to the legal prime, while operator identity and downstream economics may require PDFs, local agreements, task orders, invoices, or subaward records.

**Base-rate and innocent explanation:** Legal-prime reporting is not concealment. The untested question is whether ordinary structured joins to FSRS/subaward data and award descriptions recover the amounts. Until downstream dollars and coverage rates are measured, the gap is established as a mechanism but not established as financially material.

## Non-Subject System Structure

Independent of GEO, the public bodies share one demonstrated relationship: each can serve as ICE’s public counterparty for detention services. They differ in form and jurisdiction, and the current evidence shows no shared board, counsel, advisor, address, political donor, or inter-government communication. This absence is not proof that none exists, but it makes a coordinated-intermediary theory unnecessary at present. A tightly coupled procurement system with aligned incentives and standard forms can generate the observed repetition without explicit coordination.

GEO Secure Services is included because SEC Exhibit 21 establishes it as a wholly owned GEO subsidiary, but the reviewed IGSA excerpts do not establish that this subsidiary—rather than the parent or another operating entity—held the downstream agreements. Resolving the exact GEO legal counterparty remains a Layer-1 task.

## ACH Competing Sets

### A. IGSA intermediary layer — canonical pair #333 / #334

- **Working #333:** ICE detention economics repeatedly run through local public intermediaries.
  - Falsification: complete payment and agreement reconstruction shows the IGSAs are immaterial exceptions, GEO lacks meaningful pricing/adjustment authority, and direct awards capture nearly all GEO ICE economics.
  - Prediction: recurring per-diem, administrative-fee, guaranteed-minimum, adjustment, and payment-flow terms in local GEO agreements.
- **Null #334:** IGSAs are ordinary facility-specific public-owner arrangements.
  - Falsification: several independent IGSAs reveal materially similar GEO economic control, nonstandard local pass-through terms, or substantial downstream revenue absent from direct federal records.
  - Prediction: materially varied local terms, independently documented authority and approvals, and a reasonably complete picture after normal direct/subaward joins.
- **Layer-1 lead:** #57966, comparison of control, fee, procurement, and risk-allocation terms across five IGSAs, with non-GEO IGSA and GEO direct-prime baselines.
- **Evaluation:** findings #12403–#12408, #12410, and #12411 were scored against both hypotheses. Current competition: both have an inconsistency ratio of `0.00`; neither rival has been refuted. Most recurring-structure evidence is consistent with both. Assessor disagreements remain on findings #12404, #12408, and #12410, reinforcing that the current set is not decisively diagnostic.
- **Verdict:** inconclusive. The pair is tied on least evidence against. Agreement terms, payment flows, and a non-GEO base rate are required.

Systemic-analysis hypotheses #339/#340 were superseded by #333/#334 after deduplication because they covered the same phenomenon. This leaves one canonical competing set.

### B. Recipient visibility — pair #341 / #342

- **Working #341:** Federal recipient attribution leaves a material GEO IGSA exposure gap.
  - Falsification: structured subaward and award-description records consistently identify GEO and reconcile downstream amounts, making recipient-only omissions immaterial.
  - Prediction: material public-prime obligations with GEO identifiable only in PDFs or local payment data and incomplete structured subaward coverage.
- **Null #342:** Legal-prime reporting is accurate and creates no material visibility gap.
  - Falsification: local invoices and contracts show substantial GEO payments absent from structured federal data across most sampled IGSAs.
  - Prediction: standard structured joins recover GEO identity and amounts and reconcile closely to local payments.
- **Layer-1 lead:** #57974, quantify structured coverage and downstream dollars across the five IGSAs.
- **Evaluation:** findings #12403–#12408, #12410, and #12412 were scored against both hypotheses. Current competition: both have an inconsistency ratio of `0.00`. The working theory has more `consistent` cells, but ACH does not choose the theory with the most confirming evidence; no current finding is inconsistent with the null.
- **Verdict:** inconclusive. The existence of a recipient-name limitation is established; its materiality and recoverability through normal structured joins are not.

## New Findings

- #12411 — repeated ICE public-prime/GEO-operator architecture, synthesis, medium confidence
- #12412 — recipient-attribution visibility gap, synthesis, medium confidence
- Both tagged `systemic=ICE IGSA public-prime/private-operator architecture`

## New Leads

- #57966 — compare IGSA control, fee, procurement, payment-waterfall, and risk terms across the five public intermediaries; include non-GEO and direct-prime null cases
- #57974 — quantify the recipient-attribution gap using federal obligations, FSRS/subawards, local invoices/check registers, administrative fees, GEO payments, and SEC revenue
- #57968 — closed as a duplicate of #57966 and #57974, with an explicit stop reason

## Entities and Relations

Ten authoritative entity relations were added: #817–#826. They cover GEO Secure Services’ subsidiary relationship, each public body’s ICE relationship, GEO’s documented downstream role for Charlton/Evangeline/LaSalle, Clearfield’s GEO-initiated REA, and Karnes’ task-order IGSA relationship with ICE.

Five graph connections were added: #6357–#6361, linking Charlton, Evangeline, LaSalle EDD, Clearfield, and Karnes to ICE through their reviewed IGSA findings.

## Premortem

**Assume this synthesis is wrong.** The most likely failure is selection bias: the investigation started with GEO-linked documents and therefore made a routine, industry-wide ICE procurement practice look GEO-specific. A second failure is conflating operator identification in a PDF with economic materiality. The fastest checks are (1) a random or complete non-GEO ICE IGSA baseline and (2) five award-to-invoice reconciliations that quantify the public-prime-to-GEO payment share and structured-data recoverability.

## Strongest Network Pattern

The strongest defensible pattern is a repeated hub-and-spoke procurement topology: ICE contracts with heterogeneous local public bodies, while GEO occupies the documented subcontractor or economic-operator position beneath at least four of them. The evidence establishes the mechanism and a measurement risk. It does not establish local-body coordination, a GEO-designed scheme, deliberate opacity, or the dollar materiality of the pass-through layer.
