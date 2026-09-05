# Card-validation memo — card 38 `beneficial-control-rollup (nominal holders → resolved concentration)`

**Card under test:** `research/patterns/detection-signatures.md`, card 38 (cross-outlet additions).
**Primary test bed:** DHS procurement census
`investigations/tech-right/reports/2026-07-28-dhs-census/`: 16,722 kept award rows and 41,400
kept-award transaction rows, 2025-01-20..2026-07-28; $75,858,618,178.57 kept net obligations
(99.0% of the $76,596,473,325 full-universe total). The kept rule is window obligations >= $250,000
**or** current ceiling >= $250,000.
**Resolution test bed:** `investigation.db` `connections WHERE profile_id='tech-right'` (1,049
non-retracted edges, 709 node strings), `entities`, and `name_aliases`; local `registry.db`;
GLEIF Level 2; local OpenSanctions; ICIJ Offshore Leaks reconciliation; and the
OpenCorporates credential precondition.
**Posture:** read-only database access; zero database records, leads, findings, connections,
search-log rows, or infra records written. Exactly one repository file written: this memo.
**Scratch:** `/tmp/osint-XMsEk4tO/` (including the pre-registration frozen before computation).

---

## 1. EXECUTABILITY, field by field

### Mechanics — **partially sufficient; the current-state arithmetic runs, the advertised historical move does not**

The core move is intelligible: *"Resolve every nominal holder ... through parents, mergers, family
ties, shared formation agents, directors, addresses, and offshore vehicles — as of the award/event
date, not today — then recompute concentration and top-N share pre- vs post-resolution."* I could
compute all of the following:

1. nominal top-10 concentration from exact ledger vendor strings;
2. a current-parent proxy from the census's `recipient_parent_uei` and
   `recipient_parent_name`;
3. a strict, effective-dated rollup from the tiny set of graph edges that meet the
   pre-registered control test;
4. unresolved shares; and
5. an equal-cluster-size random-grouping control.

The move's essential clause — *"as of the award/event date, not today"* — did not run at useful
coverage. The census builder takes parent UEI/name from the **last** in-window transaction, while
`census-transactions.csv` omits those parent fields entirely. The local registry is overwhelmingly a
current snapshot. GLEIF's wrapper returns current parent `lei-record` objects, not the relationship
record and its periods. The tech-right graph has only four non-retracted edges with `valid_from`,
zero with `valid_until`, and only one effective-dated edge in the pre-registered semantic control
set.

The distinction changes the verdict:

- **current-parent sensitivity:** top-10 share moves from **45.3207% to 45.5998%**
  (**+0.2791 percentage points**);
- **card-compliant, effective-dated strict rollup:** top-10 remains **45.3207%**
  (**0.0000-point delta**), but only **$636,500 = 0.000839%** of obligations has a
  historically admissible controller edge.

The current-state number therefore does not validate the card's promised historical finding. It
quantifies what a present-day parent proxy would do while demonstrating that the named precondition
is binding.

One conceptual ambiguity also needs repair. The card says to resolve *through* directors, formation
agents, addresses, and family ties, but its own Failure modes warn against *"treating co-occurrence
as control."* Those are compatible only if officers/agents/addresses/family are candidate-generation
pivots, not admitted control edges. The card does not say that. I made that distinction explicitly
before computing.

### Minimum data — **partially sufficient; it omits the join, time, direction, and completeness requirements**

Card text: *"an allocation/asset ledger; entity identifiers; dated ownership/officer edges; family or
control links where corporate edges stop."*

What was sufficient:

- The award ledger reconciles exactly to its transaction ledger:
  **$75,858,618,178.57** in both files.
- `recipient_uei` is a usable nominal-holder key, and `recipient_parent_uei` provides a broad
  present-day legal/accounting-parent proxy.
- The two ICE families have canonical PIID lists and independently validated obligation totals.

What the field omits:

1. **A cross-system identifier bridge.** UEI does not join to the core `entities` table, registry
   record IDs, LEI, ICIJ node ID, or OpenSanctions ID. Core `entities` has EIN but no UEI or LEI.
   Only 27 of 4,165 normalized census holder names exactly match a core entity name; only two match
   `name_aliases`.
2. **Effective-dated relationship records, not merely dated entity records.** A formation date or
   registry filing date does not establish when parent control began or ended.
3. **Edge direction and control threshold.** "Equity %" is not a rule until the card says whether
   control means >50%, plurality, contractual control, accounting consolidation, or a disclosed
   beneficial owner.
4. **An evidentiary floor.** The graph exposes `verification_status` and `strength`; the card never
   says whether an unverified edge may move dollars.
5. **A complete allocation ledger at the selected population level.** The kept census is 99.0% of
   DHS dollars, but its threshold drops two of 14 skip-tracing child orders. The family CSV holds
   $18,870,135 of the canonical $19,032,607, leaving **$162,472 = 0.8537%** unallocated by holder in
   the primary file.
6. **A conflict rule.** Fifty-three UEIs map to multiple parent UEIs across awards and carry
   **$2,686,821,756.49**. Selecting a convenient "latest" parent would manufacture a rollup.

The registry stack's apparent scale also overstates its relevant breadth. It holds 5,994,330 entity
rows, but **5,993,885 (99.9926%) are Florida rows**; the next-largest jurisdiction has 286. The
bounded 42-name probe returned 13 exact-normalized entity rows for 12 names. Three of the 13 were
demonstrably false pairs: a 1925 Florida `B & I Incorporated` for GEO subsidiary `B.I.
Incorporated`, plus two inactive Florida `Spencer Construction LLC` records for the DHS wall
contractor. Exact normalized names alone therefore had an immediate **3/13 rejected-pair rate in
this bounded result set**; that is a diagnostic sample, not a population estimate.

### Pre-registration — **un-executable as written on the platform vocabulary; card 38 inherits card 30's defect**

Card text: *"which edge types count as 'control' (equity %, shared director, same agent+address,
family) — fixed before computing; report sensitivity across edge definitions."*

This repeats card 30's schema mistake. The platform's graph is mostly typed by **relationship
domain**, while the card asks the analyst to pre-register **edge semantics**:

| non-retracted tech-right type | rows | what the type can establish by itself |
|---|---:|---|
| `corporate` | 199 | domain only; may describe ownership, alumni, competition, or another corporate link |
| `employment` | 182 | employment, not equity control |
| `financial` | 171 | financial relation, not necessarily control |
| `political` | 151 | political relation |
| `funds` | 74 | financing, not necessarily control |
| **pre-registered semantic set:** `owns`, `controls`, `subsidiary_of`, `successor_to` | **69** | potentially usable, subject to direction, evidence, and date |

Of those 69 potentially semantic rows:

- only **3 are verified**;
- only **1 has `valid_from`**;
- none has `valid_until`;
- only **3 touch a ledger holder or parent name**; and
- only **one** passes type + verification + direction + effective-date tests and actually resolves a
  holder (`AI Solutions 87 LLC` → Gregory P. Behm).

The descriptions carry facts the types cannot safely express, and direction is not reliable.
`Palantir Technologies Inc. --[subsidiary_of]--> Palantir USG Inc` is stored in the opposite
direction from its own description, which says Palantir USG is the subsidiary. A type-only
traversal would reverse control.

The card's suggested control concepts are also internally overbroad:

- a shared director is governance overlap, not necessarily terminal control;
- a registered agent serves thousands of unrelated firms;
- a shared address may be a formation service, coworking site, or coincidence;
- kinship does not prove ownership; and
- a minority stake is not control without a separate contractual or voting-rights fact.

I therefore froze the following **before any result** in
`/tmp/osint-XMsEk4tO/preregistration.md`:

| parameter | frozen value |
|---|---|
| N | top **10** |
| value and denominator | signed `window_obligations`; fixed kept-ledger denominator |
| nominal vendor key | nonblank `recipient_uei`; exact trimmed vendor name only as fallback; exact vendor-string grouping as the published control |
| event date | each transaction's `action_date` |
| graph control types | `owns`, `controls`, `subsidiary_of`, `successor_to` only |
| graph evidence floor | `verification_status='verified'` for the primary result |
| registry control | explicit >50% owner, UBO/controller, accounting-consolidation parent, or completed merger/successor |
| excluded as control | officer/director alone, agent, address, family, `corporate`, `financial`, `funds`, employment, and other co-occurrence |
| date admission | edge valid on the transaction date; missing needed bounds = current-only |
| ambiguity | cycles, conflicting parents, 50/50 control, and unclear direction remain unresolved |
| unresolved treatment | retained as singleton clusters; never dropped |
| null | preserve observed cluster-size multiset; 10,000 permutations; seed 380038 |

That is a workable pre-registration, but it is mostly an amendment to the card rather than an
execution of its words. The most important edit is to say that officer/agent/address/family links
generate candidates and require separate proof of control.

### Coverage statement — **partially sufficient; the discipline is right but the metric is underspecified**

Card text: *"share of holders resolvable to a terminal controller; unresolved share reported, not
dropped."* This is the strongest field on the card, and its stated failure mode was avoided: every
unresolved holder remained a singleton in every denominator.

The field still needs to specify what "resolvable" means. Four materially different coverages exist:

| coverage definition | holders | obligations | interpretation |
|---|---:|---:|---|
| unambiguous current parent assignment (self or external) | 4,207 / 4,270 = **98.5246%** | $73.172B = **96.4583%** | present-day SAM/USASpending parent proxy; conflicts excluded |
| **unresolved even in current-parent proxy** | **63 / 4,270 = 1.4754%** | **$2.6867B = 3.5417%** | no parent or conflicting parent keys; retained as singletons |
| external current parent (parent UEI differs from holder UEI) | 889 / 4,270 = **20.8197%** | $16.274B = **21.4525%** | legal/accounting consolidation; not necessarily a beneficial owner |
| strict historically effective control | **1 / 4,270 = 0.0234%** | **$0.6365M = 0.000839%** | card-compliant dated-control coverage |
| **historically unresolved** | **4,269 / 4,270 = 99.9766%** | **$75.8580B = 99.999161%** | cannot support award/event-date control |

Reporting only the first row would imply the card is almost fully covered. Reporting only the third
would imply one-fifth coverage. The fourth row is the coverage relevant to the card's historical
claim. A self-reported/self-parent SAM record may identify the terminal registered contractor, but
it does not establish the human beneficial controller of a private company.

The coverage metric also needs a procurement sign rule. At the award-row level, the ten missing
parent rows net to **-$158,186.43**, so signed "covered dollars" exceed 100%. I avoided presenting
that misleading percentage and reported unambiguous resolution after aggregating to the holder
key. A robust card should request holder count, award count, signed net obligations, and gross
absolute obligations.

### Control — **partially sufficient; it names the right control but not how to construct it**

Card text: *"the ledger's official/published concentration, and concentration under random grouping
of equal cluster sizes."*

I ran both:

- official/exact vendor-string top-10 = **45.3207%**;
- current-parent observed top-10 = **45.5998%**;
- 10,000 random regroupings preserving the exact current-parent cluster-size multiset:
  mean **45.3551%**, median **45.3207%**, 95% interval **45.3206%–45.6838%**;
- observed minus null mean = **+0.2447 percentage points**;
- observed / null mean = **1.0054×**;
- empirical one-sided p = **0.0339**.

The small p-value should not be confused with a large change. The observed current-parent rollup is
only 0.54% above the null mean and 0.2791 percentage points above the published-string result. The
dominant ledger structure — Fisher Sand & Gravel alone at 18.8259% — survives almost every grouping.

The card leaves all null-construction choices unstated: randomize award rows or holders; include
singletons; preserve signed deobligations; use the observed cluster-size multiset or only
non-singletons; choose iterations, seed, and test tail. Those choices must be pre-registered because
they determine the baseline.

For the strict historical result, every controller cluster is still a singleton: the one dated edge
renames one holder but does not combine holders. Its equal-cluster-size null is therefore
**degenerate and identical to the official result**. The two ICE family controls are also
degenerate because every current controller is unique inside each family.

### Preconditions — **partially sufficient; the warning is correct, but it must be a hard execution gate**

The card says: *"historical effective-date ownership needs snapshots — most registries expose only
current state."* This was not a caveat at the margins; it was the result.

Concrete historical audit:

- `census-awards.csv` uses the last in-window transaction's parent fields.
- `census-transactions.csv` has action dates but no recipient or parent fields.
- **0 of 889 external current-parent holder assignments** can be proven award-date-correct from the
  two primary CSVs.
- **0 of 78 current multi-holder parent clusters** (250 member holder keys) can be proven
  award-date-correct.
- Tech-right `connections`: 4/1,049 non-retracted edges have `valid_from`; 0/1,049 have
  `valid_until`; the strict set has one dated edge.
- Bounded local-registry probe: 25 officer rows and 12 agent rows; **0 effective dates and 0 end
  dates**; no filing-history rows for the matched entities.
- GLEIF: 42 names queried, six exact names/seven LEI records, **zero direct or ultimate parent
  responses**. The returned entity records were last updated from 2023 through July 2026, not
  award-date snapshots.
- The GLEIF wrapper's parent endpoint exposes the parent entity record and sets `relationship` to
  null; it does not return relationship periods for historical testing.
- OpenCorporates `account-status` returned **HTTP 401** for the configured key. Per the user's prior
  memo and this live check, it is a **Precondition failure**, not live coverage.

The only historically admissible graph resolution was `AI Solutions 87 LLC` → Gregory P. Behm,
`valid_from=2019-03-19`, covering three transaction rows in two awards and $636,500. It changes a
label, not a concentration cluster.

Thus the number of current parent assignments that are actually award-date-correct **cannot be
determined from held data**. The quantified cost is that the +0.2791-point current-parent result is
supported by **zero historically certified multi-holder clusters**. A future agent should stop
there unless it acquires dated filings/snapshots or a relationship source with effective periods.

### Ithildin mapping — **un-executable as written; every named layer has a material limitation**

Card text: *"query_registry stack + UK CH + OpenCorporates + GLEIF Level 2
(accounting-consolidation parents), OpenSanctions + ICIJ OLDB (hidden-vehicle edges),
person_resolution/name_aliases, graph_tools; asset ledgers via query_property, ingest_faa, USPTO,
query_fpds."*

What worked:

- The DHS ledger is complete enough for the full kept-population arithmetic and reconciles to the
  cent.
- UEI and parent UEI make a broad current legal-parent sensitivity possible without fuzzy joins.
- GLEIF, ICIJ, and OpenSanctions can be queried in bounded form.
- Read-only SQL over `connections` supports a transparent semantic/date audit.

What failed or was absent:

1. **The graph has the same vocabulary defect as card 30.** Domain labels contain many control facts,
   but wholesale admission would import financing, employment, competition, and other non-control
   relations. The sparse semantic types contain only one usable dated ledger edge.
2. **`query_registry.py` has no ownership/control table.** Its unified schema contains entities,
   officers, agents, filings, and name history. Officers and addresses can generate candidates but
   cannot execute a beneficial-control rollup.
3. **Registry breadth is effectively Florida breadth.** The bounded probe's exact-name collisions
   show why the absent UEI/EIN crosswalk matters.
4. **The generated address index is stale relative to `registry.db`.** Rebuilding it would write a
   SQLite sidecar and was prohibited in this read-only run. Even a fresh address hit would remain a
   candidate, not control proof.
5. **Read commands are not strict-read-only by construction.** `query_registry.py` and
   `query_opensanctions.py` open ordinary SQLite connections and set WAL pragmas; for the actual
   bounded searches I used `mode=ro` plus `PRAGMA query_only=ON`. The `stats --output` routes also
   ignored their requested files and printed to stdout.
6. **GLEIF Level 2 yielded no parent for any exact match in the 42-name frame.** It did verify six
   entity names, but entity verification is not a controller edge.
7. **ICIJ and OpenSanctions yielded no exact or API-confirmed match** across those 42 names. Their
   absence is a null, not evidence that no offshore vehicle exists.
8. **ICIJ's CLI search/reconcile path logs to `investigation.db`.** The no-write test used the same
   tool's read-only batch reconciliation function directly instead.
9. **`person_resolution.py` is not a general corporate resolver.** Its own help identifies it as an
   Epstein-corpus candidate-person builder writing `epstein_derived.db`. It cannot resolve DHS vendor
   entities. Core `name_aliases` has 168 rows (101 entity variants) and exactly two census-holder
   name matches.
10. **OpenCorporates is blocked** by a stale/rejected credential (HTTP 401), as the test
    specification anticipated.

The mapping names useful sources, but it describes a research plan rather than an executable
resolution layer. There is no orchestrator that accepts UEIs, emits semantically typed/directed
controller edges with effective periods, resolves conflicts, and returns terminal controllers
without database writes.

### Failure modes — **partially sufficient; all four named modes fired, and five important ones are missing**

The card's four warnings were well chosen:

- **Current-ownership anachronism:** binding; the current-only sensitivity is the only broad rollup.
- **False merges on common names/addresses:** binding; 3/13 exact-normalized registry rows were
  demonstrably wrong, before any address expansion.
- **Manual family/control research silently capping coverage:** binding; strict historical coverage
  is 0.000839% of dollars.
- **Treating co-occurrence as control:** binding; the card's own pre-registration examples would do
  exactly this if applied literally.

Missing failure modes:

1. **Relationship-vocabulary mismatch.** A domain-typed graph cannot implement a semantic
   pre-registration by type name.
2. **Conflicting parent identifiers.** Fifty-three nominal UEIs have multiple parent UEIs. Examples
   include Amentum Services pointing to both Delta Bridge and PAE-Parsons; GDIT pointing to WICO
   Limited and General Dynamics; and CGI Federal pointing to CGI Federal and The Timken Company.
   I left all conflicts unresolved.
3. **Self-parent inflation.** A nonblank SAM parent field can make coverage look near-complete while
   adding no information about human or group beneficial control.
4. **Population truncation.** A ledger keep threshold can preserve 99% of dollars while dropping
   small members of the exact program under study.
5. **Top-N saturation in small frames.** Top-10 is 95.0718% of a 14-holder family and 79.2726% of an
   18-holder family before resolution. That is largely arithmetic. The card needs top-1/top-3, HHI,
   or an N rule relative to population size.
6. **Joint-venture control.** A 50/50 or multi-member JV cannot always be assigned to one terminal
   controller; the card needs a fractional or joint-control rule.
7. **Signed-flow coverage artifacts.** Deobligations can make a covered signed-dollar share exceed
   100% even when rows are missing.

---

## 2. THE RUN

### 2a. Pre-registered parameters — frozen before results

The complete frozen record is in scratch. The outcome-determining choices were:

- **N = 10**;
- **measure = signed window net obligations**;
- **denominator = all 16,722 kept award rows**, unchanged between nominal and resolved views;
- **published holder = exact trimmed `recipient_name`**;
- **resolution holder key = `recipient_uei`**, exact name only when UEI is blank;
- **event date = transaction `action_date`**;
- **strict graph types = `owns`, `controls`, `subsidiary_of`, `successor_to`**;
- **primary evidence floor = verified**;
- **officer/agent/address/family links = candidate signals only**;
- **ambiguous/conflicting direction and parents = unresolved singleton**;
- **unresolved holders never dropped**; and
- **null = 10,000 equal-cluster-size permutations, seed 380038**.

The current census parent was pre-labelled **CURRENT-PARENT PROXY** because it has no effective
period. It was never eligible to prove the historical headline.

### 2b. Nominal concentration

Exact vendor strings and UEIs produce the same top ten:

| rank | nominal vendor | window obligations | kept-ledger share |
|---:|---|---:|---:|
| 1 | Fisher Sand & Gravel Co | $14,281,092,255.70 | 18.8259% |
| 2 | Barnard Construction Company | $4,543,151,503.70 | 5.9890% |
| 3 | BCCG A Joint Venture | $3,248,042,850.70 | 4.2817% |
| 4 | SLS Federal Services LLC | $2,379,100,930.00 | 3.1362% |
| 5 | Spencer Construction LLC | $2,359,541,157.42 | 3.1104% |
| 6 | Southwest Valley Constructors Co | $2,243,969,041.00 | 2.9581% |
| 7 | AMI Metals, Inc | $1,474,828,685.83 | 1.9442% |
| 8 | CSI Aviation, Inc | $1,393,809,472.23 | 1.8374% |
| 9 | Bollinger Shipyards Lockport, LLC | $1,333,453,559.00 | 1.7578% |
| 10 | Rauma Marine Constructions Oy | $1,122,648,775.26 | 1.4799% |
|  | **top 10** | **$34,379,638,230.84** | **45.3207%** |

This exactly reproduces the census's ranking and demonstrates that vendor-string vs UEI identity
does not drive the headline.

### 2c. Current-parent proxy rollup

The current parent proxy produces 4,098 controller clusters from 4,270 nominal holder keys:

| observed cluster size | number of clusters |
|---:|---:|
| 1 | 4,020 |
| 2 | 44 |
| 3 | 14 |
| 4 | 7 |
| 5 | 4 |
| 6 | 2 |
| 7 | 4 |
| 9 | 2 |
| 14 | 1 |

There are 78 multi-holder clusters containing 250 nominal holder keys. Illustrative consolidations:

- `The GEO Group, Inc.` = GEO parent $1,076.452M + B.I. Incorporated $247.522M + GEO Transport
  $10.384M + GEO Care $0 = **$1,334.359M**;
- `CACI International Inc` = four UEIs = **$751.321M**;
- `Leidos Holdings, Inc.` = nine UEIs = **$472.266M**;
- `Deloitte & Touche LLP` = three firms = **$461.455M**; and
- `OSI Systems, Inc.` = Rapiscan/S2 Global/Rapiscan Government = **$213.921M**.

The rolled top ten:

| rank | current parent/controller label | window obligations | kept-ledger share |
|---:|---|---:|---:|
| 1 | Fisher Sand & Gravel Co | $14,281,092,255.70 | 18.8259% |
| 2 | Barnard Construction Company | $4,543,151,503.70 | 5.9890% |
| 3 | BCCG A Joint Venture | $3,248,042,850.70 | 4.2817% |
| 4 | SLS Federal Services LLC | $2,379,100,930.00 | 3.1362% |
| 5 | Spencer Construction LLC | $2,359,541,157.42 | 3.1104% |
| 6 | Southwest Valley Constructors Co | $2,243,969,041.00 | 2.9581% |
| 7 | Reliance Steel & Aluminum Co. (AMI parent) | $1,474,828,685.83 | 1.9442% |
| 8 | CSI Aviation, Inc | $1,393,809,472.23 | 1.8374% |
| 9 | **The GEO Group, Inc.** | **$1,334,358,826.12** | **1.7590%** |
| 10 | Bollinger Shipyards Lockport, LLC | $1,333,453,559.00 | 1.7578% |
|  | **top 10** | **$34,591,348,281.70** | **45.5998%** |

Rauma drops out; consolidated GEO enters. The top-ten numerator rises
**$211,710,050.86**, or **0.2791 percentage points**. This is a visible ranking change, not a
materially different concentration picture.

All 78 multi-holder clusters are **today/latest-state correct only** on the held evidence. None can
be certified on its members' obligation dates.

### 2d. Strict historical rollup and unresolved share

Applying the pre-registered semantic, verification, direction, and date rules returns one admitted
resolution:

```
Gregory P. Behm --[controls; verified; valid_from 2019-03-19]--> AI SOLUTIONS 87 LLC
```

That edge covers one holder, two awards, three transaction rows, and $636,500. It creates no
multi-holder cluster. Therefore:

| view | top-10 obligations | top-10 share | delta vs nominal |
|---|---:|---:|---:|
| exact vendor strings | $34,379,638,230.84 | 45.3207% | — |
| strict effective-dated controller | $34,379,638,230.84 | 45.3207% | **0.0000 pp** |

**Historical unresolved share:** **$75,857,981,678.57 = 99.999161%** of kept obligations, covering
4,269 of 4,270 nominal holders. This is the card's required Coverage statement and the decisive
result of the validation.

### 2e. ICE skip-tracing and UAC sub-populations

These are better frames for manual beneficial-control research than the full DHS census:

- every holder competes in one defined procurement family;
- membership is bounded at 14 and 18 rather than 4,270;
- family PIIDs and canonical obligation totals were independently validated; and
- the denominator does not mix wall construction, cutters, detention, aviation, software, and
  hundreds of unrelated markets.

I ran both:

| family | holders | allocation coverage in kept CSV | nominal top-10 | current-parent top-10 | delta | strict historical control coverage | equal-size null |
|---|---:|---:|---:|---:|---:|---:|---|
| ICE skip tracing, `26-SOL-DCR-01` | 14 | 12/14 child orders; $18.870M / $19.033M = **99.1463%** | $18.095M = **95.0718%** | **95.0718%** | **0.0000 pp** | AI Solutions $0.6365M = **3.3443%** | degenerate; all 14 clusters size 1 |
| ICE UAC, `70CDCR26R00000015` | 18 | 18/18; $85.376M = **100%** | $67.680M = **79.2726%** | **79.2726%** | **0.0000 pp** | **0%** | degenerate; all 18 clusters size 1 |

The skip-tracing keep-rule loss is explicit: EnProVera and Response AI Solutions have child orders
below the census threshold; their combined $162,472 is present in the canonical family total but
not allocable from the kept award file. Both are below the 10th-ranked holder's $636,500, so they
cannot alter the top-ten numerator, but the omission prevents a fully covered holder ledger.

The current parent proxy does resolve three skip-tracing holders to a different parent UEI
(including B.I. → GEO and Omniplex → Constellis) and two UAC holders to a different parent UEI.
None shares that parent with another holder inside its family, so concentration does not change.

These sub-populations are therefore the right **research frame**, but not yet a better
**resolution-data frame**. UAC is the cleaner executable population because its allocation ledger
is complete. Top-10 is poorly calibrated for both; a revised card should also require top-1,
top-3, and HHI.

---

## 3. CONTROL / BASELINE

### Official/published baseline

The pre-resolution control is the exact ledger vendor-string top-ten:

```
$34,379,638,230.84 / $75,858,618,178.57 = 45.3206756%
```

This equals the UEI-keyed result. Entity-key choice does not explain the observed delta.

### Equal-cluster-size random grouping

I held fixed:

- all 4,270 nominal holder obligation totals;
- the exact 4,098-cluster size multiset shown above;
- all singleton and unresolved clusters;
- signed obligations;
- N=10; and
- the fixed denominator.

I then randomly permuted holder identities into those slots 10,000 times using seed 380038:

| statistic | random-group top-10 share |
|---|---:|
| mean | **45.3551%** |
| median | **45.3207%** |
| 2.5th percentile | **45.3206%** |
| 97.5th percentile | **45.6838%** |
| observed current-parent | **45.5998%** |
| observed − null mean | **+0.2447 pp** |
| observed / null mean | **1.0054×** |
| empirical one-sided p | **0.0339** |

The current parent grouping sits toward the upper tail because GEO's related vendors combine around
an already-large holder. Its effect size remains slight. Under the only historically admissible
edge set, every cluster is a singleton, so equal-size regrouping cannot change the statistic; that
null is correctly reported as degenerate.

---

## 4. AMENDMENTS REQUIRED

1. **Replace the Pre-registration field with a semantic control contract.**
   Require N, value measure, denominator, holder key, event date, equity/control threshold,
   direction convention, evidence/verification floor, traversal stop, cycle/conflict rule, and
   joint-control treatment. State explicitly: shared officer, formation agent, address, or family
   link generates a candidate only; it does not move value without a separate admitted control
   fact. This fixes the card30 vocabulary defect and the card's co-occurrence contradiction.

2. **Turn historical ownership from a warning into a gate.**
   Require every admitted controller edge to carry `valid_from` and, where applicable,
   `valid_until`, or a dated filing/snapshot proving the relation at the event. If dated coverage is
   below a pre-registered threshold, label the result `current-state sensitivity` and prohibit the
   phrase "as of award/event date." This run's broad result has 0/78 historically certified
   multi-holder clusters.

3. **Expand Coverage statement into four mandatory rows.**
   Report (a) identifier match, (b) unambiguous legal/accounting parent, (c) external or beneficial
   controller, and (d) historically effective controller — by holder count, award count, signed
   dollars, and gross absolute dollars. Self-parent must not count as external beneficial-control
   coverage. Unresolved holders stay singleton.

4. **Require a hard crosswalk.**
   The minimum data must include UEI/EIN/CIK/LEI/registry-number crosswalks with alias provenance,
   not merely "entity identifiers." Name-only candidates require a rejected-pair review sample.
   Here 3/13 exact-normalized registry rows were immediately false.

5. **Specify the null construction.**
   State that the randomization unit is the nominal holder key; preserve the complete observed
   cluster-size multiset including singletons and unresolved holders; retain signed values; fix
   iterations and seed; report mean, 95% interval, lift, ratio, and empirical p. State that an
   all-singleton resolution has a degenerate null rather than a missing control.

6. **Add a conflicting-parent rule.**
   If one holder key maps to multiple parents, leave it unresolved unless dated evidence selects the
   valid parent at each event. Report the conflict mass. Fifty-three UEIs and $2.687B triggered this
   rule here.

7. **Correct the Ithildin mapping.**
   Say that `connections.relationship_type` mixes domains and semantics; `query_registry` has no
   ownership table and its local corpus is presently 99.9926% Florida; the address index must be
   fresh but addresses remain pivots; `person_resolution.py` is Epstein-person-specific;
   OpenCorporates is credential-gated; and GLEIF/ICIJ/OpenSanctions require an explicit
   UEI-to-source reconciliation layer. Remove any implication that these tools already emit a
   dated terminal-controller map.

8. **Require full population completeness at the selected frame.**
   A family rollup must start from every family member and allocation, not an agency-wide
   dollar-threshold extract. Report missing holder rows and dollars. The skip-tracing frame lost two
   child orders and 0.8537% of its allocation despite 99.0% agency-wide dollar coverage.

9. **Calibrate N to the population.**
   Pre-register N, require `N < holder_count`, and report top-1, top-3, top-N, and HHI (or a
   justified alternative). Top-10 in 14- and 18-holder populations is mechanically high and weakly
   diagnostic.

10. **Add a joint-venture/fractional-control rule.**
    A jointly controlled entity must either remain its own terminal controller, be assigned to a
    disclosed controlling member under a fixed rule, or be fractionally allocated. The analyst may
    not choose one sponsor after seeing which rollup raises concentration.

11. **Separate current legal parent from beneficial owner in the Mechanics sentence.**
    `recipient_parent_uei` and GLEIF accounting consolidation are valuable legal-parent evidence but
    do not necessarily identify the human/group beneficial controller of a private contractor. The
    card title and coverage labels must preserve that distinction.

---

## 5. VERDICT

**blocked-on-historical-effective-date control data.** Card 38's arithmetic is runnable, its
Coverage and random-control disciplines are valuable, and a current SAM/USASpending parent
sensitivity can be computed today. But the card's defining promise is not "roll up using today's
parent": it is terminal control **as of the award/event date**. The platform cannot presently
establish that at meaningful coverage. Its semantic graph returns one dated ledger resolution;
registry officer/agent records lack effective periods; GLEIF yields no parent in the bounded frame;
the offshore layers return nulls; OpenCorporates is HTTP-401 blocked; and 53 ledger holder keys have
conflicting current parents.

The data does **not** show that resolution materially changes DHS concentration. Nominal top-10 is
45.3207%; current-parent top-10 is 45.5998% (+0.2791 pp, 1.0054× the equal-size null mean); the only
card-compliant dated rollup is unchanged with 99.999161% of dollars historically unresolved. The
ICE families are better manual-research frames and were run, but both returned zero rollup delta.

A future agent invoking the current card on this platform should expect a present-day legal-parent
sensitivity and a near-total historical-coverage failure — not an award-date beneficial-control
finding — until a semantically typed, directed, identifier-linked, effective-dated ownership layer
exists.

---

### Scratch artifacts (not persisted to the repository)

`/tmp/osint-XMsEk4tO/`: `preregistration.md`; `audit_resolution.py` /
`graph-audit.json`; `compute_rollup.py` / `rollup-results.json`;
`registry_resolution.py` / `registry-resolution.json`; `gleif_resolution.py` /
`gleif-resolution.json` plus per-query outputs; `icij_resolution.py` /
`icij-resolution.json`; `opensanctions_resolution.py` /
`opensanctions-resolution.json`.
