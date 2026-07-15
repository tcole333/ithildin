# Corrected Trump–DHS–GEO network and hunch reassessment

**Analysis runs:** #89 (`analyze-network`) and #90 (`generate-hunches`)  
**Profile:** `geo-group`  
**Scope:** thread 112 plus verified DHS, ICE, personnel, contract, lobbying, political-money, and household-investment findings  
**Status:** completed; supersedes the identity topology and centrality values reported by run #81
**Verified synthesis finding:** #12735

## Result

The corrected evidence graph documents several forms of access and professional adjacency around GEO, ICE, and the Trump administrations. It does **not** establish a coordinated channel or procurement causation.

Two corrections materially changed the topology. First, Trump campaign adviser Chris LaCivita (the father) and GEO lobbyist Christopher LaCivita Jr. remain separate people connected by a family edge. Second, `Guidepost Solutions` is merged into canonical entity #4807, `Guidepost Solutions LLC`. The latter produces real non-GEO two-edge paths from Thomas Homan through Guidepost to B.I. Incorporated and Julie Myers Wood. Those edges concern distinct disclosed relationships, however; they do not show that Homan and Wood or Homan and B.I. worked on the same project or coordinated.

The ACH reassessment favors the two null hypotheses as the least-inconsistent explanations. That ranking is not proof of either null; it means the current evidence is more compatible with ordinary regulated-sector hiring, consulting, and general detention-capacity advocacy than with a coordinated expertise channel or identifiable award-specific tasking.

## Input rule and corrections

The final graph includes a connection only when both the connection and its attributed source finding are verified. Of 69 profile connections, 67 pass that rule. Connections #6347 and #6348 are excluded because their source findings #12391 and #12393 remain unverified. Forty connections derived from already-verified findings were explicitly verified during this run with attribution to those findings.

Canonicalization applied three known variants: the two GEO parent-name strings were collapsed to `The GEO Group, Inc.`; `Matthew Albence` was resolved to `Matthew T. Albence`; and `Guidepost Solutions` was resolved to `Guidepost Solutions LLC`. Connection #6346 was relinked to verified finding #12462 because that finding's SEC proxy quotation supports the agreement, the $420,000 paid in 2025, and the December 31, 2025 end date. The missing dollar signs in connections #6346, #6374, and #6375 and three ACH notes were restored from preserved source text.

The repository's native graph export returned 64 nodes and 95 edges because it admitted cross-profile entity relations and unresolved variants. Those metrics are rejected under papercut #840. The institutional/pillar export was also excluded from conclusions because it is cross-profile; its cache mode failed on a synthetic `person_id=0` marker, logged as papercut #893. All reported metrics below come from the verified, profile-scoped connection export.

## Corrected network metrics

| Graph | Connection records | Nodes | Simple edges | Density | Component sizes |
|---|---:|---:|---:|---:|---|
| Verified full profile | 67 | 45 | 66 | 0.066667 | 45 |
| Full profile, GEO removed | — | 44 | 35 | 0.036998 | 22, 11, and eleven isolates |
| Thread-112/DHS focus | 52 | 36 | 51 | 0.080952 | 36 |
| Focus, GEO removed | — | 35 | 34 | 0.057143 | 21, 11, 1, 1, 1 |

Selected focus-graph metrics:

| Node | Degree | Betweenness | Clustering | Articulation? |
|---|---:|---:|---:|---|
| The GEO Group, Inc. | 17 | 0.626583 | 0.080882 | yes |
| U.S. Immigration and Customs Enforcement | 16 | 0.493333 | 0.066667 | yes |
| Thomas D. Homan | 6 | 0.181317 | 0 | yes |
| Ballard Partners | 5 | 0.088235 | 0.2 | yes |
| Christopher LaCivita Jr. | 3 | 0.110924 | 0.333333 | yes |
| Guidepost Solutions LLC | 3 | 0.008263 | 0 | no |
| Chris LaCivita | 2 | 0.057143 | 0 | yes |

The father and son's articulation status should not be read as gatekeeping. The father is an articulation because removing him isolates the campaign leaf; Jr. is an articulation because removing him disconnects the father/campaign chain from Checkmate and GEO. This is a structural property of the sparse graph, not evidence of influence.

Run #81's 40-node/59-edge graph and its collapsed-LaCivita centrality are historical only. Direct comparison is further limited because run #89 adds later verified contract, personnel, lobbying, household, and DHS findings and applies a stricter verification rule.

## Non-GEO paths and what they mean

Removing GEO leaves two principal components in the focus graph.

The 21-node ICE/professional component contains a direct `Second Trump Administration → Thomas D. Homan` appointment edge and the documented `Homan → Guidepost Solutions LLC → B.I. Incorporated` and `Homan → Guidepost Solutions LLC → Julie Myers Wood` paths. The Guidepost paths are genuine shared-firm adjacency. They are not shared-project evidence: Wood's Guidepost role is documented from 2012 through at least July 2014, the B.I. agreement is separately disclosed through 2025, and Homan's 2025 disclosure provides only the source name and consulting-services category.

The 11-node political/lobbying component contains this six-edge route:

`Donald J. Trump 2024 campaign → Chris LaCivita → Christopher LaCivita Jr. → Checkmate Government Relations → White House Office → Ballard Partners → Department of Homeland Security`

That route is graph adjacency, not an interaction chain. It combines a 2024 campaign role, a family relationship, Jr.'s 2025–2026 Checkmate role, Checkmate's 2026 activity-level White House field, and Ballard's 2019 activity-level White House and DHS fields. The LDA government-entity arrays do not attribute a contact to a named lobbyist or prove a meeting. The route spans different firms, accounts, and years and does not reach the ICE/procurement component without GEO.

The Trump household-disclosure node has degree zero after GEO is removed. Political-money findings remain an event layer rather than person-to-person graph edges and therefore do not create an inferred bridge.

Evidence supports describing the direct Homan appointment as administration access and the Guidepost structure as professional adjacency. It does not support describing either as coordination, procurement intervention, or causation.

## ACH reassessment

ACH totals are deduplicated by finding. The database retains earlier assessor rows for auditability, so raw row counts are not the number of evaluated findings.

| Competition | Hypothesis | Evaluated | Inconsistent | Diagnostic | Ratio |
|---|---|---:|---:|---:|---:|
| `geo-ice-expertise-channel` | #337 coordinated distributed channel | 37 | 11 | 22 | 0.2973 |
| `geo-ice-expertise-channel` | #338 ordinary regulated-sector practices (H0) | 37 | 0 | 22 | 0 |
| `geo-checkmate-detention-tasking` | #353 identifiable award-specific tasking | 12 | 5 | 8 | 0.4167 |
| `geo-checkmate-detention-tasking` | #354 general detention-capacity advocacy (H0) | 12 | 0 | 8 | 0 |

For comparison, run #81 reported 27 evaluated findings for #337/#338, with four inconsistencies for #337 and none for #338. The corrected run incorporates findings #12710 and #12718–#12726 and revised assessments of #12507–#12509. The broadened evidence makes #337 more—not less—inconsistent. Findings such as the father/son correction, activity-level LDA fields, pre-engagement policy and funding, and the lack of a named procurement record weigh against the more specific coordination mechanisms. The Guidepost merge adds a valid shared-firm path, but its records still do not identify a common project.

## Hunch novelty filter

Run #90 tested four patterns against a three-independent-context gate and the existing hypothesis, tag, finding, and lead corpus:

1. campaign/family–Checkmate–White House–Ballard–DHS path;
2. former-ICE personnel and consulting expertise channel, including corrected Guidepost topology;
3. household investment plus political-money and DHS award timing; and
4. Ballard OMB access as a hidden procurement route.

All four met the minimum context count but failed novelty. They are already tested by hypothesis pairs #337/#338, #351/#352, #353/#354, or #355/#356 and their associated leads. The Guidepost correction strengthens the accuracy of pattern two but does not supply a shared project, contemporaneous contact, or a mechanism distinct from the existing expertise-channel competition. Run #90 therefore created no new hypothesis pair and no duplicate Layer-1 lead.

## Limitations

- Activity-level LDA government-entity fields cannot identify which lobbyist contacted which office.
- A graph edge records a sourced relationship, not necessarily contemporaneity, communication, or influence.
- Centrality is sensitive to selection and entity resolution and is descriptive, not causal.
- The finding set does not include nonpublic calendars, communications, ethics recusals, or procurement-integrity records.
- No live SAM query, headless worker, subject contact, or nonpublic-system access was used in these runs.

## Artifacts

- `2026-07-13-trump-dhs-corrected-network-metrics.json` — corrected full/focus metrics and input rule
- `2026-07-13-trump-dhs-corrected-focus-edges.csv` — 52-record focus input
- `2026-07-13-trump-dhs-non-geo-path-test.json` — exact paths, edge provenance, components, and caveats
- `2026-07-13-trump-dhs-run81-run89-network-comparison.json` — historical/current comparison boundaries
- `2026-07-13-trump-dhs-run81-run89-ach-comparison.json` — deduplicated ACH matrices and totals
- `2026-07-13-trump-dhs-hunch-novelty-filter.json` — candidate/context/novelty decisions
