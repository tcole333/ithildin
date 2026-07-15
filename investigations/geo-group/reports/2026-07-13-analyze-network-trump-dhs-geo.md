# Trump–DHS–GEO network analysis

**Analysis run:** `analyze-network` #81  
**Profile:** `geo-group`  
**Focus:** threads 110, 111, and 112 within the full profile graph  
**As of:** 2026-07-13  
**Source boundary:** persisted findings, connections, hypotheses, and durable reports/ledgers only; no new factual sourcing

## Result

> **Superseded identity topology (July 14 correction):** Run #81 collapsed
> Trump campaign adviser Chris LaCivita with his son, Checkmate/GEO lobbyist
> Christopher LaCivita Jr. Finding #12710 and corrected connections
> #6384/#6385/#6397 now separate them; connection #6408 preserves the documented
> father-son relationship. The counts and LaCivita centrality/articulation
> values below are retained as historical run output and must not be used as
> current metrics. Corrected Tier-2 runs #89/#90 are complete; see
> `2026-07-13-analyze-network-generate-hunches-trump-dhs-corrected-run89-90.md`
> and verified synthesis finding #12735.

After the relationship, holdings, and procurement ledgers were represented without multiplying transaction rows into social edges, historical run #81 computed **60 connection records, 40 nodes, and 59 undirected simple edges**. Those totals predate the Jr./father correction and are superseded. The only parallel pair in that historical run was David Venturella–GEO: one employment edge and one later proposal/renewal consulting edge.

The most defensible substantive result remains negative: no documented non-GEO edge joins the Homan/Venturella/Ragsdale/Albence/Guidepost side to the Bondi/Ballard/Checkmate side. The corrected political/lobbying component contains separate father and son nodes joined by a family edge; it does not contain the direct campaign-adviser-to-GEO-lobbyist identity edge used by run #81. The historical component sizes are therefore superseded, while the absence of a documented bridge to the ICE/professional side remains.

Homan and Ballard become the highest-ranked non-subject intermediaries in the corrected graph. Homan has degree 6, exact normalized betweenness 0.147458, and clustering 0. Ballard has degree 5, betweenness 0.073549, and clustering 0.2. These are metric observations about the current evidence model. Homan's score is driven by six heterogeneous neighbors that currently lack lateral edges; Ballard's score is driven partly by institutional-contact leaves from one lobbying account. Neither score establishes gatekeeping, influence, coordination, or procurement authority.

No new hypothesis was registered. Every candidate mechanism reduced to the existing `geo-ice-expertise-channel` competition (#337/#338), a pre-existing bounded lead, or a simple coverage artifact. Ten new findings were scored against both existing hypotheses. H0 #338 remains least inconsistent with 0 of 27 evaluated findings inconsistent, compared with 4 of 27 for #337. That result is not confirmation of H0; it means the present record has less evidence against ordinary regulated-sector role separation.

## Method and data-quality controls

Run #81 followed the native workflow: active-profile context, connections graph, coverage matrix, thread summary, findings dump, degree and betweenness, bridges, holes, cliques, components, open triads, clustering, statistics, pillar dump, orchestrator score, cross-pillar, institutional graph, and legal/banking/government pillar subgraphs.

The native metric files are not the final profile metrics. `graph_tools.build_graph` adds global `entity_relations` when only one endpoint intersects a profile node. It therefore expanded the 60 profile connection records into a 49-node/70-edge graph and elevated Pamela Bondi through unrelated Maxwell/Clinton/Waitt relationships. Papercut #840 records that active-profile leak. The final calculation instead used only the profile-scoped connection export, keyed nodes by canonical entity ID, merged duplicate Albence entity #4865 into #4804 as documented in run #78, collapsed only true parallel relationships for simple-graph metrics, and computed exact betweenness with NetworkX.

Institutional conclusions are excluded. The orchestrator-score command repeated the prior `person_id=0` foreign-key failure (papercut #799). Cross-pillar and institutional-graph outputs again contained unrelated profiles (papercut #800). Legal, banking, and government pillar subgraphs returned zero rows. Those outputs cannot support a GEO-specific institutional finding.

## Ledger and finding representation

Thirteen supported connections that existed only in findings or durable ledgers were added before final metrics:

- #6387: Trump 2026 OGE disclosure household–GEO financial edge;
- #6388: GEO–CBP direct-prime contracting edge;
- #6389: Checkmate–White House Office institutional lobbying-contact edge;
- #6390–#6392: Albence, Homan, and Ragsdale–ICE Presidential Transition Office response;
- #6393: Homan–Homeland Strategic Consulting;
- #6394–#6396 and #6398–#6399: Ballard–GEO, Bondi, Sayfie, DHS, and White House Office;
- #6397: Christopher LaCivita Jr.–Checkmate (corrected after run #81; the
  original run mislabeled this edge as the father).

All 22 direct or institutional rows in the 23-row Trump–DHS edge ledger now map to a canonical simple edge. The remaining row, Wood–Homan, is explicitly second-degree through Guidepost and was correctly not converted into a direct connection.

Findings #12505–#12534 are represented in typed layers:

| Findings | Representation | Reason |
|---|---|---|
| #12505–#12513 | relationship graph | Direct compensated, employment, appointment, lobbying, and agency-response edges |
| #12514–#12516 | household–GEO edge plus 16-row holdings event layer | Fifteen purchase/sale dates plus year-end asset/dividend row; event multiplicity does not increase degree |
| #12517–#12518 | bounded-negative/attribute layer | SEC threshold and named-lender negatives are not relationship edges |
| #12519–#12525 | political-money/legal event layer | PAC, corporate, inaugural, individual, enforcement, denominator, and control facts remain legally separated; aggregating them into one donor node would distort topology |
| #12526–#12529 | relationship plus identity/negative layer | Homan consulting and employer edge are graphed; payment route, B.I. scope, and exact GEO Care entity remain unresolved attributes |
| #12530–#12532 | GEO–ICE/GEO–CBP edges plus 1,416-row procurement event layer | Awards/actions weight the contracting relationships without becoming social nodes |
| #12533–#12534 | bounded-negative/identity layer | Component zeros, subaward failure, and unresolved legal-name variants are coverage limits, not missing-edge proof |

The corrected procurement layer preserves 1,416 unique DHS actions and $6,356,699,228.62 in net action obligations: 1,362 ICE actions/$6,354,097,259.08 and 54 CBP actions/$2,601,969.54. Those amounts weight two component relationships; they are not graph edge counts, revenue, payments, or evidence of political influence.

## Canonical graph statistics

| Metric | Full profile | GEO removed | Threads 110–112 induced focus |
|---|---:|---:|---:|
| Nodes | 40 | 39 | 32 |
| Simple edges | 59 | 35 | 44 |
| Density | 0.075641 | 0.047233 | 0.088710 |
| Component sizes | 37, 3 | 21, 10, 3, 1, 1, 1, 1, 1 | 29, 3 |
| Highest non-subject degree | ICE, 16 | ICE, 15 | ICE, 8 |
| Highest non-subject betweenness | ICE, 0.262438 | ICE | ICE, 0.196918 |

### Top 20 degree and exact betweenness

| Rank | Node | Degree | Betweenness | Clustering |
|---:|---|---:|---:|---:|
| 1 | The GEO Group, Inc. | 24 | 0.595412 | 0.057971 |
| 2 | U.S. Immigration and Customs Enforcement | 16 | 0.262438 | 0.108333 |
| 3 | Thomas D. Homan | 6 | 0.147458 | 0 |
| 4 | Ballard Partners | 5 | 0.073549 | 0.2 |
| 5 | Chris LaCivita *(historical collapsed node; superseded)* | 3 | 0.047233 | 0.333333 |
| 6 | Justin J. Sayfie | 3 | 0.047233 | 0.333333 |
| 7 | Pamela Bondi | 3 | 0.047233 | 0.333333 |
| 8 | Checkmate Government Relations | 3 | 0.020918 | 0.333333 |
| 9 | B.I. Incorporated | 3 | 0.017454 | 0.333333 |
| 10 | Daniel Ragsdale | 3 | 0.017454 | 0.333333 |
| 11 | Julie Myers Wood | 3 | 0.017454 | 0.333333 |
| 12 | Matthew T. Albence | 3 | 0.017454 | 0.333333 |
| 13 | Guidepost Solutions LLC | 3 | 0.006298 | 0 |
| 14 | ICE Presidential Transition Office response | 3 | 0.006298 | 0 |
| 15 | George C. Zoley | 2 | 0.001350 | 0 |
| 16 | White House Office | 2 | 0.001350 | 0 |
| 17 | Cornell Companies, Inc. | 2 | 0 | 1 |
| 18 | Correctional Services Corporation | 2 | 0 | 1 |
| 19 | Charlton County, Georgia | 2 | 0 | 1 |
| 20 | Clearfield County, Pennsylvania | 2 | 0 | 1 |

Venturella ranks 21st by the same tie ordering: degree 2, betweenness 0, clustering 1. His apparent low position is a limitation of a simple graph. The graph correctly collapses his GEO employment and later proposal/renewal consultancy into two parallel role records on the same GEO relationship; it then observes that GEO and ICE already have a direct edge, making Venturella one vertex of a closed triangle rather than a shortest-path bridge.

The household and CBP nodes each have degree 1 and betweenness 0. Their incident edges are graph bridges only because they are leaves. “Bridge edge” in this setting means removal isolates the node; it does not mean the household or CBP brokered a relationship.

## Bridges, holes, cliques, and open triads

Run #81 reported GEO, ICE, Homan, Ballard, Bondi, Sayfie, the collapsed LaCivita node, and George Zoley as articulation points. The LaCivita result is invalid after separating father and son and adding the family edge; it is retained only as historical output. The remaining articulation results also await the corrected Tier 2 rerun before being quoted as current.

Structural-hole output gives Homan a brokerage score of 1.0 because none of his six neighbors has a documented lateral edge to another neighbor. Guidepost and the transition-response record also score 1.0 at degree 3. GEO scores 0.942029 and ICE 0.891667 because their star-like buyer/parent roles produce many neighbors without lateral edges. These scores describe missing documented adjacency; they do not show control of information.

The graph contains sixteen maximal three-node cliques and no larger clique. Twelve are procurement/personnel forms of `GEO–ICE–X`; three are the Ballard/Checkmate lobbying triangles `GEO–firm/person`; one additional direct-prime triangle is included after normalization. Relationship types within a clique are heterogeneous, so clique count is not evidence of a dense social group.

The strongest open triads are:

1. **B.I.–Julie Myers Wood**, with common neighbors Guidepost, GEO, and ICE. This is expected from the documented corporate, board, former-agency, and consulting structure. It does not establish direct B.I.–Wood operational contact; lead #59112 already seeks the engagement records.
2. **Ragsdale–Albence**, with common neighbors the ICE response record, GEO, and ICE. The missing direct-person edge is not surprising because shared agency work and later employment do not require a separate personal-relationship record.
3. **Guidepost–ICE**, with common neighbors B.I., Wood, and Homan. The current graph does not establish a direct Guidepost–ICE contract or common project. Finding #12528 specifically failed to tie Homan to Guidepost's B.I. engagement.

The many remaining two-common-neighbor open triads are combinations of GEO affiliates, public IGSA counterparts, former officials, and ICE around the same GEO/ICE hubs. They are projection artifacts of a two-hub procurement graph, not surprising missing social links.

## Non-subject intermediaries and coverage gaps

| Node | Degree / betweenness | Finding-text coverage | Assessment and next test |
|---|---:|---:|---|
| Thomas D. Homan | 6 / 0.147458 | 7 findings, thread 112 | Highest non-subject person because six heterogeneous edges are attached. Exact scopes, payment path, last-service dates, and screening remain under lead #59112. |
| Ballard Partners | 5 / 0.073549 | 2 findings, thread 112 | Highest-centrality under-covered institution. Both findings derive from one Q3 2019 account. New lead #59423 seeks registrant work papers and named-contact records. |
| Pamela Bondi | 3 / 0.047233 | 1 finding | Canonical rank is far below the leaked native 0.3063 score. Her edges form a Ballard/GEO triangle plus a Trump-role leaf; no named DHS/White House contact is established. Covered by #59423. |
| Chris LaCivita *(historical collapsed node)* | 3 / 0.047233 | 1 finding | **Superseded.** This row merged father and son. Finding #12710 separates them; do not use this centrality value. |
| Checkmate Government Relations | 3 / 0.020918 | 4 findings | Historical run joined Checkmate to the collapsed node. The corrected edge is to Christopher LaCivita Jr.; aggregate LDA fields remain non-person-specific. Completed lead #59358 and findings #12718–#12723 found no public award-specific bridge. |
| Daniel Ragsdale | 3 / 0.017454 | 4 findings across 111/112 | GEO–ICE–response triangle; direct transition timing is documented, procurement intervention is not. Existing #337/#338 research plan remains applicable. |
| Matthew T. Albence | 3 / 0.017454 | 6 findings across 110/111/112 | Same triangle after merging duplicate entity IDs. GrindStone non-overlap remains ordinary-course counterevidence. |
| Julie Myers Wood | 3 / 0.017454 | 3 findings across 111/112 | GEO–ICE–Guidepost junction; no Trump role or Homan project established. Lead #59112 covers the unresolved scope. |
| Guidepost Solutions | 3 / 0.006298 | 11 findings across 110/111/112 | B.I., Wood, and Homan edges; Homan–B.I. common-project attribution remains unsupported. |
| David Venturella | 2 / 0 | 9 findings | Two parallel GEO roles plus current ICE role. Findings #12541/#12545 provide role-separation counterevidence; leads #59228, #59230, and #59360 seek the appointment and ethics boundary. |
| Trump OGE household | 1 / 0 | 2 directly targeted findings plus event analysis | Sixteen holdings-matrix rows collapse to one properly caveated edge. Existing lead #59356 tests the decision-maker and timing; finding #12543 calls current proximity non-discriminating. |
| CBP | 1 / 0 | 4 findings, thread 110 | The only direct DHS component outside ICE in the 14-UEI action universe. No personnel/lobbying edge is documented. Subaward coverage remains unresolved under infrastructure request #154. |

Connection-supported cross-thread nodes remain sparse, but the run #81
LaCivita row is an entity-resolution artifact. Current work must track Chris
LaCivita and Christopher LaCivita Jr. separately.

## ACH update and novelty review

The ten newly scored findings were #12505, #12506, #12507, #12509, #12510, #12528, #12537, #12541, #12544, and #12545. Every one was scored against both #337 and #338.

| Competition group | Hypothesis | Evaluated | Inconsistent | Diagnostic | Ratio |
|---|---|---:|---:|---:|---:|
| `geo-ice-expertise-channel` | #338 H0 — ordinary regulated-sector practices without a coordinated channel | 27 | 0 | 11 | 0.0000 |
| `geo-ice-expertise-channel` | #337 — distributed ICE expertise channel | 27 | 4 | 11 | 0.1481 |

The most diagnostic additions weigh against collapsing documented proximity into one channel:

- #12528 found no primary link between Homan and the Guidepost–B.I. engagement;
- #12541 publicly places ICE acquisition under Management and Administration rather than assigning Venturella an operational procurement role;
- #12544 found Checkmate timing non-discriminating because base-action counts were unchanged and relevant awards predated the engagement;
- #12545 records a 472-day gap between the scheduled end of Venturella's consultancy and first public ICE leadership appearance, while leaving screening records unresolved.

H0 is least inconsistent, not confirmed. Direct scopes, contacts, recusals, and matter-participation records could still change the matrix.

Candidates rejected as non-novel or unsupported:

- **“Homan is the gatekeeper.”** Rejected. His high score is a heterogeneous leaf-star, and the mechanism duplicates #337/#338 and lead #59112.
- **“Venturella closes a procurement influence loop.”** Rejected. The simple topology is a closed GEO–ICE triangle, not a bridge; exact authority remains open under #59228/#59230/#59360, and current records contain role-separation counterevidence.
- **“Ballard and Checkmate prove a recurring White House channel.”** Rejected as a new hypothesis. They are two time-separated firm-mediated filing paths; aggregate LDA fields do not identify named contacts. Lead #59358 completed the bounded public-source test; unavailable work descriptions and agency/private contact records remain the decisive gap alongside #59423.
- **“Guidepost links Homan to B.I.”** Rejected. It is an open triad/second-degree path, directly bounded by #12528 and existing lead #59112.
- **“The Trump household edge bridges procurement.”** Rejected. It is a degree-1 financial-disclosure edge; dense DHS action cadence makes date proximity non-discriminating, and lead #59356 already tests the lawful record gap.
- **“CBP extends the political network.”** Rejected. CBP is a degree-1 procurement node supported by ten awards; no personnel, lobbying, or household edge connects it to the political subgraph.

Because no distinct mechanism survived duplicate and evidence tests, run #81 created **zero new hypotheses**. It updated 20 ACH cells across existing hypotheses #337/#338 and created one coverage lead, #59423.

## Tags, writes, and audit trail

- Added connections #6387–#6399 from existing findings/ledgers.
- Applied 54 finding-tag records across six clusters: consulting intermediaries, personnel transitions, lobbying intermediaries, holdings/procurement event layers, political-money events, and bounded negatives/identity gaps.
- Created coverage lead #59423 for Ballard account work papers and contact attribution.
- Created synthesis findings #12546–#12547 from run outputs; created no new primary finding and gathered no new factual source.
- Updated hypotheses #337/#338 with 20 reasoned evidence-matrix cells; created no new hypothesis.
- Papercut #840: active-profile `graph_tools` expands cross-profile `entity_relations`.
- Prior papercuts #799/#800 recurred for pillar scoring and institutional profile isolation.

## Premortem

Assume this analysis is wrong. The likeliest failure is treating documentation topology as relationship topology. Adding Ballard, Checkmate, household, transition-response, and CBP nodes from the commissioned ledgers makes Homan and Ballard look structurally prominent because leaf records were attached to them, while uncollected calendars, firm staffing, contracting officials, peer lobbyists, and non-GEO contractors remain absent. The fastest corrective check is a typed peer-denominator graph: all ICE/CBP detention contractors, their lobbying registrants, former officials, public ethics screens, and award decision chains, with transaction counts kept as weights and with profile-safe entity relations. Until then, centrality is a coverage diagnostic, not evidence of influence.

## Durable inputs

- `investigations/geo-group/reports/2026-07-13-trump-dhs-edge-list.csv`
- `investigations/geo-group/reports/2026-07-13-trump-geo-holdings-relationship-matrix.csv`
- `investigations/geo-group/reports/2026-07-13-dhs-wide-geo-award-actions.csv`
- `investigations/geo-group/reports/2026-07-13-dhs-wide-geo-component-summary.json`
- `investigations/geo-group/reports/2026-07-13-trump-dhs-relationship-map.md`
- `investigations/geo-group/reports/2026-07-13-trump-geo-investment-ownership-report.md`
- `investigations/geo-group/reports/2026-07-13-lead-58983-homan-geo-guidepost-consulting.md`
- `investigations/geo-group/reports/analyze-network-geo-group-2026-07-13.md`
- `investigations/geo-group/reports/generate-hunches-initial-synthesis-2026-07-13.md`
- `investigations/geo-group/reports/generate-hunches-wave3-2026-07-13.md`
