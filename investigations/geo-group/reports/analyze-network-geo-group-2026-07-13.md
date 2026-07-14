# GEO Group network analysis — 2026-07-13

## Run, scope, and result

- Analysis run: `analyze-network` #78
- Active profile: `geo-group`
- Evidence boundary: the profile-scoped `connections` export and existing factual findings/reports through #12484; no broad source expansion
- Final synthesis finding: #12486. Draft finding #12485 was retracted and superseded after two missing primary-source connections were added during the audit.

The defensible structure is a sparse two-hub procurement graph, not a hidden social network. After canonicalizing aliases and adding five evidence-backed omitted edges, the profile graph has **23 nodes and 34 simple edges**. GEO and ICE dominate because the corpus was commissioned around a GEO–ICE contracting question and because hundreds of awards are collapsed to recipient–agency edges. Removing GEO leaves ICE as the only substantive articulation point in the main component. The documented B.I.–Guidepost–Julie Myers Wood links form a small multi-path consulting/governance subgraph; B.I. is not a sole broker once Wood's documented Guidepost employment and GEO board role are represented.

These are properties of the investigation's connection table. A missing edge is not evidence that two actors lack a real-world relationship, and a high centrality score is not evidence of influence or control.

## Method and data-quality controls

The native exports were run as required: connection graph, coverage matrix, thread summary, findings dump, degree/betweenness, bridges, holes, cliques, components, open triads, clustering, and graph statistics. The native graph was profile-scoped, but its alias loader queried a stale column and therefore split `The GEO Group, Inc.` from `The GEO Group Inc.` and split two Matthew Albence entity records. Papercut #798 records the resulting centrality distortion.

For the final metrics, the analysis used the 34 `geo-group` connection rows only, keyed endpoints by exported canonical entity ID, normalized GEO entity #1290, and manually merged duplicate Albence entity #4865 into #4804. The calculation used an undirected, unweighted simple graph and exact normalized betweenness. Parallel award actions, modification rows, and repeated documentary support did not create extra edges.

The institutional/pillar commands were excluded. They returned unrelated Epstein, DOGE, and election-network records despite the active GEO profile. Papercut #800 records that profile leak. The cached pillar score also failed on an invalid `person_id=0` run marker; papercut #799 records the foreign-key failure.

## Canonical graph statistics

| Metric | Full profile graph | GEO removed |
|---|---:|---:|
| Nodes | 23 | 22 |
| Edges | 34 | 17 |
| Density | 0.134387 | 0.073593 |
| Component sizes | 20, 3 | 15, 3, 1, 1, 1, 1 |
| Highest degree | GEO, 17 | ICE, 13 |
| Highest exact betweenness | GEO, 0.449495 | ICE, 0.421429 |
| Articulation points | GEO, ICE, George C. Zoley | ICE, George C. Zoley |

### Top 20 degree and betweenness ranks

| Rank | Node | Degree | Exact betweenness |
|---:|---|---:|---:|
| 1 | The GEO Group, Inc. | 17 | 0.449495 |
| 2 | U.S. Immigration and Customs Enforcement | 14 | 0.241703 |
| 3 | B.I. Incorporated | 3 | 0.036797 |
| 4 | Julie Myers Wood | 3 | 0.036797 |
| 5 | CORNELL COMPANIES, INC. | 2 | 0 |
| 6 | CORRECTIONAL SERVICES CORPORATION | 2 | 0 |
| 7 | Charlton County, Georgia | 2 | 0 |
| 8 | Clearfield County, Pennsylvania | 2 | 0 |
| 9 | Daniel Ragsdale | 2 | 0 |
| 10 | Evangeline Parish Sheriff's Office | 2 | 0 |
| 11 | GEO CARE SERVICES, LLC | 2 | 0 |
| 12 | GEO Transport, Inc. | 2 | 0 |
| 13 | George C. Zoley | 2 | 0.004329 |
| 14 | Guidepost Solutions LLC | 2 | 0.001443 |
| 15 | LaSalle Economic Development District | 2 | 0 |
| 16 | Matthew T. Albence | 2 | 0 |
| 17 | Checkmate Government Relations | 1 | 0 |
| 18 | Chris Zoley | 1 | 0 |
| 19 | David O. Meehan | 1 | 0 |
| 20 | GEO REENTRY SERVICES LLC | 1 | 0 |

Tied degree ranks are shown alphabetically. Betweenness, not tie order, is the more relevant comparison.

## Bridges, structural holes, and components

### Articulation and edge bridges

In the full graph, removing GEO, ICE, or George Zoley increases the component count. George Zoley is an artifact of the separate three-node family component: he connects Chris Zoley and David Meehan, but that component has no recorded edge to the main procurement graph. GEO and ICE are the only articulations with contracting significance.

After GEO is removed, ICE is the only articulation in the 15-node procurement/personnel component. The ICE–local-body and ICE–affiliate edges then become bridges because the graph records no lateral relationships among the public bodies or affiliates. That topology is expected from a buyer–recipient dataset and does not show that ICE controls information between otherwise interacting organizations.

The full graph's seven edge bridges are:

- GEO–Checkmate Government Relations
- GEO–GEO Reentry Services
- GEO–GEO Secure Services
- GEO–GrindStone Strategic Consulting
- ICE–Karnes County
- George Zoley–Chris Zoley
- George Zoley–David Meehan

The B.I.–Guidepost edge is not a bridge after adding Wood–Guidepost and Wood–GEO. The small subgraph has two documented paths to the core: `Guidepost → B.I. → GEO/ICE` and `Guidepost → Wood → GEO/ICE`.

### Structural-hole scores

| Node | Degree | Neighbor density | Brokerage score (`1-density`) | Interpretation limit |
|---|---:|---:|---:|---|
| GEO | 17 | 0.088235 | 0.911765 | Parent-company and commissioned-subject hub |
| ICE | 14 | 0.131868 | 0.868132 | Common federal buyer/employer hub |
| B.I. | 3 | 0.333333 | 0.666667 | Subsidiary/contractor/consulting junction |
| Julie Myers Wood | 3 | 0.333333 | 0.666667 | Former ICE/Guidepost/GEO-board junction |

The scores identify where the current graph's neighbors lack documented lateral edges. They do not establish gatekeeping, coordination, or information control.

### Components and algorithmic communities

The main component has 20 nodes. The only disconnected nontrivial component is the three-node Zoley/Meehan family structure. Greedy modularity divides the main star into a GEO-heavy set, an ICE-heavy set, and a B.I.–Guidepost–Wood set. The first two assignments are unstable partitions of a sparse two-hub graph and should not be treated as substantive communities. The B.I.–Guidepost–Wood triangle-like multi-path structure is documentary and meaningful as a coverage unit, but its scopes and procurement roles remain unknown.

The 12 maximal three-node cliques are all `GEO–ICE–X` triangles. `X` is B.I., Cornell, Correctional Services Corporation, Charlton County, Clearfield County, Daniel Ragsdale, Evangeline Parish Sheriff, GEO Care Services, GEO Transport, LaSalle EDD, Matthew Albence, or Julie Myers Wood. These triangles mix contract, employment, subsidiary, and board relations. Counting them as homogeneous dense clusters would be a category error.

## Substantive structures and model artifacts

### IGSA public-intermediary layer

Charlton, Evangeline, LaSalle, and Clearfield each form a recorded `ICE–local public body–GEO` triangle. Karnes currently has only the ICE–Karnes edge because the reviewed federal base did not name GEO and the county–operator agreement was not recovered. That asymmetry is a documented evidence gap, not proof that Karnes lacks a private operator relationship.

The repeated triangles support the already registered mechanism in hypotheses #333/#334 and #341/#342. They do not show lateral coordination among the counties/parish/district. The terms report documents material variation between Charlton and LaSalle, and the payment report quantifies only LaSalle's full annual waterfall.

### Direct-prime and vehicle families

The corrected official baseline is 228 unique direct ICE awards and $7.774 billion in cumulative net award obligations across six affiliated legal recipients. The connection graph intentionally compresses those instruments to recipient–ICE edges. Three such edges were missing and were added as connections #6369–#6371 for GEO Care Services, Correctional Services Corporation, and Cornell Companies.

The vehicle ledger contains **51 IDVs and 219 linked orders/calls** across five legal recipients:

| Recipient | IDVs | Linked orders/calls | Linked-order obligations |
|---|---:|---:|---:|
| The GEO Group, Inc. | 34 | 174 | $5.269bn |
| B.I. Incorporated | 7 | 25 | $2.486bn |
| GEO Care Services, LLC | 5 | 10 | $19.003m |
| Correctional Services Corporation | 4 | 9 | $14.053m |
| GEO Transport, Inc. | 1 | 1 | $10.384m |

Cornell's direct awards do not resolve to one of the 51 IDVs. Award and IDV identifiers are instruments, not independent actors. A parent IDV's high order count measures procurement hierarchy, not social brokerage.

B.I.'s seven IDVs cover six ISAP/electronic-monitoring generations/records plus the separate skip-tracing vehicle. ISAP V's first task carries $86.361 million of skip-tracing modifications, while the separate 2026 skip-tracing competition produced 14 prime IDIQ awardees and generally 51 offers. The other 13 awardees, task allocation, and commercial supplier chain are not represented in the entity graph, so the current topology cannot measure B.I.'s centrality within that market. This is a bounded coverage gap, not evidence that B.I. acted alone or received predetermined work.

### Guidepost/former-ICE/lobbying chronology

Connections #6372 and #6373 add Wood's documented Guidepost CEO role and GEO board service. Their addition materially changed the graph: B.I. ceased to be an articulation point. This is an example of why connection completeness must be audited before interpreting centrality.

The chronology also supplies ordinary-course counterevidence. The Guidepost–B.I. agreement existed before Wood joined the GEO board; GEO disclosed Audit and Finance Committee review; GrindStone stopped providing GEO services after Albence joined; Checkmate's filed issue was detention-center contracts rather than ISAP; and ISAP/skip-tracing competitions had multiple offers. Scopes, minutes, recusal records, and procurement contacts remain unknown. Those gaps do not themselves support coordination.

### Performance-consequence evidence

Thread 113 has 23 factual findings but no facility/remedy nodes in the current connection graph. This is a schema/coverage limitation: the graph records person/entity relationships, while remedy authority, invoice deductions, OIG findings, task continuation, and closure status are attributes/events. Centrality cannot adjudicate hypotheses #335/#336. The dedicated ACH ledger remains the correct analytic representation.

## Cross-thread actors and coverage gaps

Canonical finding-entity links identify GEO across four threads (108, 110, 111, 112) and B.I. across three (109, 110, 113). No other entity is linked to findings in two or more threads. That low cross-thread count reflects target/entity resolution choices as much as the underlying evidence.

Highest-priority coverage gaps are already represented by bounded work rather than new speculative leads:

1. Existing leads #57966 and #57974: recover missing IGSA bases, operator agreements, task orders, invoices, and structured-subaward joins; add a non-GEO denominator.
2. Existing lead #57970 / infrastructure request #150: obtain remedy decisions, invoice deductions, revised minimums, and closure packages.
3. Completed lead #57972's record requests: Guidepost scope/invoices, Wood recusal or committee minutes, and procurement-role records.
4. ISAP/skip-tracing records: item 42, modification approvals, the 14-award task allocation, subcontracting plans, suppliers, and a current privacy-compliance record.
5. Vehicle graph: primary validation of 28 pre-2007 instruments and three unresolved parent vehicles.

No new lead was created because every defensible graph gap duplicates one of these existing bounded tests.

## ACH updates

Run 78 added 58 reasoned evidence-matrix cells and did not create a new hypothesis.

| Competition | Least inconsistent | Rival | Result |
|---|---|---|---|
| `geo-igsa-intermediary-layer` | #333: 0/17 inconsistent, ratio 0.00 | #334: 0/17, ratio 0.00 | Tie; evidence is mostly non-diagnostic |
| `geo-performance-consequence-gap` | #336 H0: 3/22, ratio 0.14 | #335: 4/22, ratio 0.18 | H0 remains least inconsistent, not confirmed |
| `geo-ice-expertise-channel` | #338 H0: 0/17, ratio 0.00 | #337: 2/17, ratio 0.12 | H0 least inconsistent; pre-existing Guidepost agreement and GrindStone non-overlap weigh against #337 |
| `geo-igsa-recipient-visibility` | #341: 0/18, ratio 0.00 | #342 H0: 1/18, ratio 0.06 | #341 least inconsistent; five bounded structured-search failures weigh against effortless recovery, but materiality is not established |

The #333/#334 tie is important: recurring intermediary economics and materially varied local terms are both documented. The #341 lead is least inconsistent because a local audited waterfall and budget lines are visible where exact structured searches failed, but only one facility has a near-complete quantified waterfall. None of these verdicts is confirmation.

## Writes and audit trail

- Added direct-prime connections #6369–#6371.
- Added Wood–Guidepost and Wood–GEO connections #6372–#6373.
- Added synthesis finding #12486 (`claim_type=synthesis`, `confidence=medium`, source quote and report/run evidence). Retracted draft #12485 and recorded #12486 as superseding it after the final edge correction.
- Applied cluster tags to 49 active findings across IGSA, direct-prime/vehicle, Guidepost/former-ICE, performance-consequence, and final network clusters.
- Created no hypothesis and no lead.
- Papercut #798: graph alias/canonicalization split.
- Papercut #799: pillar score cache foreign-key failure.
- Papercut #800: institutional/pillar profile leak.
- Papercut #801: connection #6351 retains the superseded #12403 award total because the supported connection workflow is insert-only. The edge itself remains valid; its dollar description must not be used. Finding #12474 and the durable prime-universe report are canonical.

## Premortem

Assume this analysis is wrong. The most likely failure is mistaking a commissioned, sparse connection table for the real network: GEO and ICE appear central partly because every award, facility, public intermediary, and former official was selected around them, while competitors, contracting officers, suppliers, task-order evaluators, and peer operators are mostly absent. The fastest check is to build a typed bipartite graph from a complete ICE award/IGSA/contractor universe, including non-GEO peers, then recompute centrality with award IDs treated as instruments and dollar/order weights reported separately. Until that baseline exists, centrality is a coverage diagnostic, not an influence measure.
