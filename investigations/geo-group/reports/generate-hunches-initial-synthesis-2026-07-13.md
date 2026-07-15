# Hunch Generation Report — 2026-07-13

## Run Context

- Analysis run: #74
- Active profile: `geo-group` (verified before database writes and never changed)
- Findings scanned: 30
- Entities scanned: 22
- Connections scanned: 17
- Open leads checked: 25
- Existing hypotheses checked: 100 globally; no pre-existing hypotheses were attached to a GEO thread
- Pillar broker scores checked: 20

All three patterns below are provisional inferences. Each is paired with the best innocent explanation, a falsification criterion, and a concrete Layer-1 research lead. ACH rankings mean *least evidence against*, not most evidence for.

## Hunches Generated

### 1. ICE detention economics repeatedly run through local public intermediaries

**Pattern type:** emerging structural theme

**Evidence:** The direct-recipient reconstruction explicitly excludes county/state pass-throughs (#12403); Karnes requires funded task orders beneath a zero-dollar base IGSA (#12404); independent ICE instruments name Charlton County, Evangeline Parish Sheriff, LaSalle Economic Development District, and Clearfield County while identifying GEO as subcontractor or economic actor (#12405–#12408); and the facility crosswalk classifies nine of 22 ICE-linked facilities as verified IGSAs (#12410).

**Working hypothesis #333:** The recurring public-prime/GEO-operator layer is economically material and makes direct federal recipient records a poor measure of GEO's ICE exposure. It may place pricing, adjustments, audit rights, and termination terms in local agreements.

**Null hypothesis #334:** IGSAs are ordinary, facility-specific public-owner arrangements with no material common visibility or economic effect.

**Falsification:** The working hypothesis fails if full contracts and payment chains show that these IGSAs are immaterial exceptions, materially dissimilar, confer little pricing/adjustment authority on GEO, and leave direct federal award records nearly complete. The null fails if several independent IGSAs reveal similar GEO economic control, local administrative pass-throughs, or substantial ICE-linked revenue missing from direct-recipient data.

**ACH result:** #333 has 0 inconsistent assessments across seven findings; #334 has one inconsistent, four consistent, and two neutral. #333 is currently the least inconsistent explanation, but several facility documents are compatible with both explanations. The decisive missing evidence is the local operator agreements and money flow.

**Layer-1 search plan:** Obtain complete GEO operator/subcontract agreements, amendments, invoices, local-government receipts, administrative fees, audit/termination/indemnity terms, and equitable-adjustment records for the five named intermediary systems. Reconcile every federal task order to local-to-GEO payments, then benchmark against direct GEO primes and non-GEO IGSAs.

**Lead:** #57968, high priority, `analyze-contract`

**Tag:** `theme:geo-igsa-intermediary-layer` on findings #12403–#12408 and #12410

### 2. A possible cross-program gap between performance problems and financial consequences

**Pattern type:** emerging financial/oversight theme

**Evidence:** GAO reports an ICE space-approval control still open (#12396) and incomplete BI assessment against ISAP contract standards (#12397). Separate DHS OIG reports document approximately $25.3 million paid for unused Golden State bed space (#12398) and unsanitary/dilapidated conditions at Folkston (#12399).

**Working hypothesis #335:** Across detention and electronic monitoring, ICE contract design or monitoring may weaken the link between deficient/underused performance and proportional financial consequences. This does not establish favoritism or improper influence.

**Null hypothesis #336:** These are separate operational episodes; unused beds purchased legitimate readiness and deficiencies were handled through ordinary contract remedies not visible in the report summaries.

**Falsification:** The working hypothesis fails if CPARS, cure notices, deductions, award-fee actions, corrective-action closure, terminations/recompetes, and occupancy forecasts show routine proportional remedies and cost-effective readiness purchasing. The null fails if multiple programs show absent or nominal consequences, unresolved corrections, or extensions/capacity increases despite persistent failures.

**ACH result:** #335 has 0 inconsistent assessments across four independent oversight contexts; #336 has one inconsistent, one consistent, and two neutral. #335 is currently least inconsistent, largely because GAO directly found incomplete BI assessment. This is weakly diagnostic: the present findings do not contain the consequence records needed to test either explanation.

**Layer-1 search plan:** For BI, Golden State, and Folkston, collect QASPs, monthly performance reports, CPARS, cure/show-cause notices, deduction logs, award-fee records, invoices, corrective-action closure, occupancy/readiness forecasts, and subsequent option/modification actions. Build a matched dated ledger and benchmark against non-GEO contractors.

**Lead:** #57970, high priority, `analyze-contract`

**Tag:** `theme:geo-performance-consequence-gap` on findings #12396–#12399

### 3. A distributed ICE expertise channel spanning leadership, BI consulting, and lobbying

**Pattern type:** emerging organizational theme

**Evidence:** GEO discloses former senior ICE officials Matthew Albence, Daniel Ragsdale, and Julie Myers Wood in its leadership/governance orbit (#12385–#12387); Wood's employer Guidepost had a $420,000 consulting relationship with BI (#12388–#12389); GAO identifies BI as the ISAP contractor whose performance was incompletely assessed (#12397); and two separate lobbying filings cover ICE/alternatives to detention and detention-center contracts (#12400–#12401).

**Working hypothesis #337:** These functions may operate as a distributed ICE policy/procurement expertise channel across detention and electronic monitoring.

**Null hypothesis #338:** Former-official hiring, disclosed consulting, and lobbying are ordinary regulated-sector practices; Guidepost's work was unrelated and the functions were not coordinated around ICE procurement or policy.

**Falsification:** The working hypothesis fails if scopes, timelines, recusals, and peer benchmarks show no functional overlap with ICE matters and an ordinary sector baseline. The null fails if primary work scopes, communications, lobbying contacts, or decision timelines show linked assignments or interventions on the same ICE matters.

**ACH result:** Both #337 and #338 have zero inconsistent assessments across eight findings. Neither is less inconsistent. Most evidence is consistent with both explanations, so the present record does **not** establish coordination, procurement intervention, or improper influence.

**Layer-1 search plan:** Obtain Guidepost-BI scopes, amendments, invoices, deliverables, conflicts, recusals, and approvals. Build a day-level timeline for Albence, Ragsdale, Wood, Guidepost, GEO/BI, and Checkmate against solicitations, awards, and lobbying. Benchmark former-ICE hiring and lobbying against CoreCivic and other ICE contractors, and actively seek procurement losses and non-ICE work.

**Lead:** #57972, high priority, `search-all-sources`

**Tag:** `theme:geo-ice-expertise-channel` on findings #12385–#12389, #12397, and #12400–#12401

## Patterns Checked but Filtered Out

- **GEO ICE scale ($7.749 billion direct obligations; 22 ICE-linked facilities):** filtered because it is a documented baseline, not a novel explanatory pattern.
- **Zoley family compensation:** filtered because the current record contains only one disclosure context and no cross-thread mechanism.
- **North Florida joint venture:** filtered because one unresolved disclosure cannot satisfy the three-context rule; the existing entity-resolution lead is the correct next step.
- **Air transport / skip tracing / ISAP V as an integrated platform:** filtered because current leads mention these areas, but the 30 findings do not yet provide three independent evidentiary contexts.
- **Lobbying-to-award timing:** filtered because the current filings establish lobbying subjects and amounts but do not yet supply a sufficiently resolved procurement chronology.
- **Address, formation-date, nonprofit-flow, and alumni-dispersal patterns:** filtered because the current GEO entity export has no address, formation-date, 990, role, or alumni data adequate for those scans.

## Scan Statistics

- Scan families reviewed: 12
- Candidate patterns considered: 8
- Patterns surviving novelty and independence filters: 3
- Hypotheses created: 6 (3 working + 3 null)
- Finding evaluations created: 38
- Leads created: 3
- Finding tags created: 19
- Findings created: 0

