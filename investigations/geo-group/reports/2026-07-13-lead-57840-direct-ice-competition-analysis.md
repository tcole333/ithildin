# Lead 57840 — Competition and one-offer patterns across major GEO ICE awards

**Profile:** `geo-group`  
**Thread:** 110 — Procurement Vehicles, Entities & Money Flow  
**As of:** 2026-07-13  
**Disposition:** bounded public-record review completed; unresolved acquisition files converted to infra request #152

## Bottom line

The public record supports a mixed procurement story, not a blanket steering or sole-source story. The stable denominator contains **228 unique USAspending-backed prime awards with $7,774,205,537.65 in award obligations**. Of those, **206 are orders or BPA calls** and only **22 are standalone awards**. The orders account for **99.77% of denominator dollars**, so transaction- or order-level competition fields cannot be read as if they described competition for the parent vehicle.

Offer-count coverage is also incomplete: **107 of 228 awards (46.93%) lack a reported offer count**, while **90 (39.47%) report one offer**. A deliberately broad screen combining one-offer records with sole-source/not-competed records returns **100 awards and $1,468,017,982.93**, but that screen is not an allegation set. It combines distinct acquisition facts and includes 79 orders whose parent vehicles need separate review.

Once those 79 orders are normalized to their parent IDVs, their parent-vehicle competition posture splits into **15 orders under full-and-open/multiple-offer vehicles, 32 under full-and-open/one-offer vehicles, 10 under sole-source/not-competed vehicles, and 22 under vehicles with missing competition metadata**. The first group is direct evidence that a one-offer order record does not necessarily mean the underlying vehicle lacked competition.

The strongest ordinary explanation in the bounded top cohort is North Lake: SAM notice **JA-20-0057** identifies FAR 6.302-2 unusual and compelling urgency for three detention contracts supporting the President's national-emergency declaration. Big Horn remains the highest-priority unresolved case: its parent award reports one offer, not competed, and sole source, with a $528.7 million potential value, but the bounded exact-ID/title search found no indexed official solicitation or J&A/JOFOC explaining the acquisition choice. That gap supports a targeted records request, not an inference of steering.

## Layered denominator

| Layer | Records | Included in 228-award competition denominator? | Proper use |
|---|---:|---|---|
| USAspending-backed prime awards | 228 | Yes | Unique-award competition and obligation denominator |
| Parent IDVs | 51 | No | Underlying vehicle competition, offer count, solicitation, and order-family context |
| USAspending transaction actions | 1,864 | No | Modification/payment/action chronology; never a unique-award count |

The 51 parent-IDV ledger reports linked-order obligations, which substantially overlap the 228 prime-award dollars. Those amounts are not additive. Three small orders totaling $702.60 point to external GSA/USMS vehicles not represented among the 51 GEO-family IDVs; the matrix leaves their parent competition fields blank rather than fabricating a match.

## Unique-award competition matrix

The award-denominator buckets use the latest USAspending contract competition fields while preserving parent-vehicle fields in separate columns.

| Award-level bucket | Unique awards | USAspending award obligations |
|---|---:|---:|
| Full and open — multiple offers | 25 | $402,622,746.25 |
| Full and open — one offer | 41 | $950,680,363.48 |
| Full and open — offer count missing | 97 | $5,864,566,754.40 |
| Sole source or not competed | 29 | $282,822,261.53 |
| Simplified acquisition — one offer | 23 | $78,827,913.04 |
| Simplified acquisition — offer count missing | 2 | $200.16 |
| Order competition — one offer | 3 | $133,643,753.04 |
| Other or ambiguous | 8 | $61,041,545.75 |

The largest numerical limitation is not an adverse competition code; it is missingness. The 97 full-and-open records without an offer count alone represent $5.865 billion. Treating blank offer fields as zero, one, or noncompetition would materially distort the result.

At the parent-IDV layer, the 51 vehicles divide into **22 full-and-open/multiple-offer, 16 full-and-open/one-offer, 11 sole-source/not-competed, and 2 with competition metadata missing**. These counts are analytically useful, but their linked-order dollars overlap the prime-award denominator and are therefore not summed into it.

## Bounded top-cohort document audit

The public-document pass stopped after nine major/recent acquisition families because the remaining questions require acquisition files rather than broader searching.

| Acquisition family | Public competition evidence | Ordinary explanation test | Result |
|---|---|---|---|
| Big Horn, `70CDCR26D00000049` | HigherGov award metadata: one offer, not competed, sole source; no indexed official rationale found | Facility availability, urgency, statutory authority, prior competition | **Unresolved.** No steering inference; obtain J&A/market research/award decision. |
| North Lake, `70CDCR25D00000009` | [SAM JA-20-0057](https://sam.gov/opp/f9ed1ff98e9e47f091ae5aaa75ff6ac2/view) | FAR 6.302-2 urgency; national-emergency activation; later definitization | **Ordinary urgency rationale supported at authority level.** Market research and definitization file remain unavailable. |
| Tacoma bridge, `70CDCR26D00000026` | Secondary procurement mirror summarizes a redacted J&A; official page not retrieved | Seven-month bridge, four RFI responses, incumbent facility ownership, timing/security/location constraints | **Plausible but not primary-verified.** Obtain official J&A and RFI evaluation. |
| California LA/SF, `70CDCR20D00000009` / `...08` | Official [LA](https://www.usaspending.gov/award/CONT_IDV_70CDCR20D00000009_7012) and [SF](https://www.usaspending.gov/award/CONT_IDV_70CDCR20D00000008_7012) award pages: full and open, one offer | Open solicitation exposure, facility/geographic requirements, market concentration, price reasonableness | **One-offer outcome confirmed; cause unresolved.** One offer is not proof of restriction or steering. |
| Denver/Aurora, `70CDCR22D00000001` | Official [USAspending award page](https://www.usaspending.gov/award/CONT_IDV_70CDCR22D00000001_7012): full and open, one offer | Capacity/location specifications, market concentration, price reasonableness | **One-offer outcome confirmed; cause unresolved.** Obtain acquisition file before causal claims. |
| Delaney Hall, `70CDCR25D00000007` | [SAM solicitation](https://sam.gov/opp/5cf4af3e829a465b83efaa9942a765a3/view) and [presolicitation](https://sam.gov/opp/870e7205f3974426858f4b94abf272fa/view); parent reports two offers | Full-and-open follow-on, approximately 600 beds within 50 driving miles, continuity from expiring contract | **Ordinary competitive process supported.** Counterexample to a blanket sole-source narrative. |
| ISAP V, `70CDCR25D00000062` | [SAM solicitation](https://sam.gov/opp/548da70d66394aa88734a82efa69e620/view); parent reports two offers | Public national competition for next ISAP iteration | **Ordinary competitive process supported.** |
| Western ground transportation, `70CDCR25D00000002` | [SAM solicitation](https://sam.gov/opp/d43e89701bd44de6bb73e7f4f54c8f94/view); parent reports eight offers | Multi-AOR requirement and broad vendor pool | **Strong ordinary-competition counterexample.** |
| Nationwide skip tracing, `70CDCR26D00000005` | [SAM sources-sought notice](https://sam.gov/workspace/contract/opp/ba672b1263504509be2fa823ee9b6725/view); parent ledger reports 51 offers | Public market research and broad commercial vendor pool | **Strong ordinary-competition counterexample.** Preserve the RFI/award identifier-normalization caveat. |

## Negative results and limits

- Exact contract-ID, facility-title, J&A/JOFOC, and solicitation searches found **no indexed official acquisition rationale for Big Horn** as of 2026-07-13. This is a scoped search negative, not proof the record does not exist.
- Exact Tacoma searches found a secondary summary of a redacted J&A but **not the official SAM J&A page or attachment** in the indexed results used here.
- Exact cohort solicitation/contract searches found **no relevant published GAO bid-protest decision**. GAO's public decision index does not exhaust agency-level protests, active/nonpublished dockets, or Court of Federal Claims litigation.
- Exact Big Horn, Tacoma, and JA-20-0057 searches found **no matching document in ICE's indexed FOIA contract library** during this pass.
- The SAM opportunities CLI produced no file or diagnostic while a separate repair was underway; papercut #805 preserves the reproduction. This review used indexed official SAM pages where available and did not silently treat the failed API calls as negative results.
- Secondary procurement mirrors are discovery aids, not primary proof. Tacoma's ordinary bridge explanation remains provisional until the official J&A and RFI evaluation are obtained.

## Hypothesis assessment

**H0 — ordinary acquisition explanations:** supported in several major families. North Lake has an explicit urgency authority; Tacoma has a plausible but secondary-only bridge/facility explanation; Delaney, ISAP V, Western transport, and skip tracing show open or multiple-offer competition. California and Aurora show full-and-open procedures that yielded one offer, which is compatible with facility-market concentration but does not establish the cause.

**H1 — unexplained restriction or preferential design:** remains a records-dependent question for Big Horn and for the one-offer California/Aurora procurements. The public aggregate does not support a steering inference. The appropriate next test is acquisition-level market research, source-selection, one-offer adequacy, J&A, and price-negotiation records—not more award-counting.

## Exact next records

Infra request **#152** packages the bounded files needed for Big Horn, Tacoma, North Lake, California, and Aurora: sources-sought/RFI responses, market research, acquisition plans, J&As/JOFOCs, IGCEs, source-selection and award decisions, one-offer adequacy/price-reasonableness determinations, responsibility determinations, undefinitized-letter-contract definitization records, and price-negotiation memoranda. A structured `--related-lead 57840` link failed with a foreign-key error; papercut #806 records that defect, and an infra note preserves the manual association.

## Durable artifacts

- `direct-ice-competition-matrix-2026-07-13.csv` — 279 rows with prime-award and parent-IDV layers separated; parent competition fields joined to orders.
- `direct-ice-competition-summary-2026-07-13.json` — counts, dollar buckets, missingness, and parent-normalized broad-screen results.
- `direct-ice-top-cohort-document-audit-2026-07-13.csv` — source-by-source rationale test and exact missing-file target for nine acquisition families.
- `direct-ice-usaspending-action-rows-2026-07-13.csv` — 1,864 transaction actions, preserved separately.

