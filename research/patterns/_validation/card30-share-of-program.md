# Card-validation memo — card 30 `share-of-program-capture (ledger × relationship graph)`

**Card under test:** `research/patterns/detection-signatures.md`, card 30 (Wave-2 additions).
**Test bed:** DHS procurement census `investigations/tech-right/reports/2026-07-28-dhs-census/` (16,722 awards,
window 2025-01-20..2026-07-28, $75.86B kept obligations = 99.0% of the $76.60B full universe) ×
`investigation.db` `connections WHERE profile_id='tech-right'` (1,049 non-retracted edges, 709 node strings).
**Posture:** read-only. Zero writes. All scratch in `/tmp/osint-cO2q39JK/`.

---

## 1. EXECUTABILITY, field by field

### Mechanics — **partially sufficient; the edge-definition step is the failure point**

The card's four-beat move (ledger → hub → edges → share vs peer) is legible and I could run it end to end.
Three of the four beats survived contact. The edge-definition beat did not.

**The pre-registration guidance was not usable as written.** The card says: *"ownership, board seats, kinship,
and (the New Jersey innovation) clients of the hub's family's professional firms counted as network edges"* and,
in Failure modes, *"pre-register the edge types."* I pre-registered exactly that set, mapped onto the platform's
`connections.relationship_type` CHECK vocabulary, before computing anything:

| card concept | Ithildin `relationship_type` |
|---|---|
| ownership | `owns`, `controls`, `subsidiary_of` |
| board seats | `shares_officer` |
| kinship | `familial` |
| clients of kin's professional firms | **no representation** |

Result for the hypothesized hub (Peter Thiel — chosen because Palantir + Anduril are the tech-right graph's
DHS-ledger-bearing firms):

```
STRICT (owns/controls/subsidiary_of/shares_officer/familial)
  depth 1 = 1 node   depth 2 = 1 node   depth 3 = 1 node   vendors matched = 0   share = 0.00%
```

**Peter Thiel is an isolated node under the card's own pre-registered edge set.** He has 23 edges in the graph
and not one of them is typed `owns`, `controls`, `subsidiary_of`, `shares_officer`, or `familial`. His Palantir
chairmanship is `corporate`; his Founders Fund control is `financial`; Founders Fund's Anduril lead investment
is `funds`. The move returns zero.

This is not a data-poverty story — the relationships are documented, with descriptions. It is a **vocabulary
mismatch**: Ithildin's `relationship_type` encodes *relationship domains* (corporate / financial / political),
while card 30 presumes *edge semantics* (equity stake vs board seat vs client relation). The card's pre-registration
instruction is therefore un-executable on this platform without a translation layer the card does not supply.

Worse, the naive repair inverts the analysis. Widening to a **CARD-PROXY** set
(`+corporate, employment, advisory` — the types whose free text actually carries founder/chairman/officer
semantics) makes the network computable but admits edges whose semantics are the *opposite* of network
membership. Traced paths from the hub:

```
Peter Thiel --[corporate]--> Palantir Technologies --[corporate]--> Forterra --[corporate]--> Anduril Industries
```

The `Palantir–Forterra` edge is an **alumni** edge ("Scott Philips (Forterra CIO) is early Palantir Forward
Deployed Engineer alumnus"). The `Forterra–Anduril` edge is alumni **plus "Both compete for DoD ground autonomy
programs"** — a *competitor* relation. So under the card-faithful edge set the hub reaches Anduril through a
competitor edge while the true relationship (Thiel → Founders Fund → Anduril, lead investor) is **excluded**,
because investment is typed `financial`/`funds`, not `owns`. Card 30's gerrymander warning fires in the direction
the card does not anticipate: the disciplined edge set produced the *wrong* network, and the loose one produced
the right answer for the wrong reason.

Second structural defect the card does not anticipate: **programs and statutes are graph nodes.** GEO Group
enters the "Thiel network" at depth 3 via

```
Peter Thiel --[corporate]--> Palantir Technologies --[corporate]--> ICE Skip Tracing Program --[corporate]--> GEO Group
```

`ICE Skip Tracing Program` is a *program* node. Traversing it means the network is defined through the very
program whose capture is being measured — a tautology that mechanically inflates share. The graph also holds
`Department of Homeland Security`, `U.S. Customs and Border Protection`, `Proclamation 10886 (Border Emergency)`,
`One Big Beautiful Bill (H.R. 1)`, `Laken Riley Act`, `WEXMAC TITUS Program` as nodes. There is no node-type
attribute on `connections` to exclude them (nodes are bare TEXT strings), and only 52.3% of graph nodes resolve
to an `entities` row at all — and `entities.entity_type` has no `program` or `statute` value, so they could not be
typed out even if resolution were complete.

Third: the card gives **no stopping rule for traversal depth**, and depth dominates the answer more than the
edge set does. Same hub, same ledger, CARD-PROXY edges: 0.32% (d1) → 1.08% (d2) → 2.51% (d3). Add types and
depth together and one hub yields anything from **0.00% to 5.76%**. The analyst picks the answer.

### Minimum data — **incomplete; understates by two required inputs**

Card says: *"the complete award ledger; registry/board/lobbying edges; drafting correspondence via records requests."*

- **Complete award ledger** — accurate, and we hold one. The census is reconciled (83,240 transactions, 0
  duplicates across the window split, canonical-number validation exact on both the skip-tracing and UAC families).
- **Registry/board/lobbying edges** — accurate only as a description of *what you need*, not of what exists.
  We hold 1,049 hand-curated edges. There are **10** `familial`, **10** `shares_officer`, **24** `owns`, **36**
  `controls`, **6** `subsidiary_of` in the entire tech-right profile. No lobbying edge type exists (`political`
  is the nearest, semantically different).
- **Missing from the field #1 — a join key.** The card never says the ledger and the graph must be joined on a
  resolvable identifier. They must. `connections` is a name-string graph with no UEI/EIN/CIK; the census carries
  `recipient_uei` and `recipient_parent_uei`. The join is therefore fuzzy name matching, and it fails in both
  directions: `Anduril Industries` / `Anduril Industries LLC` / `Anduril` are three nodes for one firm; `Palantir`
  / `Palantir Technologies` / `Palantir Technologies Inc` / `Palantir Technologies Inc.` / `Palantir USG Inc` are
  five. Against the ledger the same matcher produces `Tesla` → `TESLA LABORATORIES INC.`, `The Boring Company` →
  `MACK BORING & PARTS CO`, and `The Foundation` → ten unrelated university foundations. Card 20
  (grant-chain-tracing) names alias resolution in its own title; card 30 omits it entirely.
- **Missing from the field #2 — a coverage estimate.** See Friction #1.
- **Drafting correspondence** — correctly labelled an aggravator, correctly flagged as records-request dependent.
  Not held. But see Amendments: our graph carries a *weaker, already-held* substitute (revolving-door personnel
  edges: five ex-ICE officials typed `employment` into GEO Group, including `Tom Homan`, `Matthew Albence`,
  `Daniel Ragsdale`, `David Venturella`, `Julie Myers Wood`).

### Ithildin mapping — **overstated; "directly runnable today" is the single most misleading clause on the card**

Card says: *"graph_tools (the platform's network layer is purpose-built for this), query_990 + registries for
edges, query_usaspending for ledgers — directly runnable today."*

What worked:
- `uv run python tools/graph_tools.py --profile tech-right neighbors "Peter Thiel" --depth 2 --output FILE` — clean,
  honors `--profile`, honors `--output`, returns `{center, depth, nodes[{name,distance,degree}], edges, counts}`.
- `graph_tools paths "Peter Thiel" "GEO Group"` — works, and was the fastest way to expose the tautological route.
- `query_usaspending` for the ledger — not exercised; the census artifacts already exist and are richer
  (competition fields, ceiling ledger, pre-window baselines) than the tool's default output.

What failed or is absent:
- **`neighbors` has no `--rel-type` filter.** The card's core discipline is edge-type pre-registration; the tool the
  card names cannot filter by edge type. Only `triangles` accepts `--rel-type`. I had to hand-roll BFS in
  `/tmp/osint-cO2q39JK/hubnet.py` to execute the card's own instruction.
- **`paths` is the one subcommand with no `--output`** (audited all 12: every other subcommand has it). It errors
  with `unrecognized arguments: --output`, which conflicts with the project's bulk-results convention.
- **`sqlite3 -readonly` cannot open `investigation.db`** — WAL mode, `unable to open database file (14)`, same for
  `file:...?mode=ro`. Read-only discipline requires a normal connection plus `PRAGMA query_only=ON`. Worth a line
  in CLAUDE.md; it will bite every read-only auditor.
- **"query_990 + registries for edges" describes work, not a capability.** No tool materializes registry, 990, or
  lobbying relationships into `connections`. `tools/connection_inference.py` looks like the missing adapter but
  its `shared_officer` / `shared_address` / `corporate_chain` rules emit **leads**, not edges (`INSERT INTO leads`
  only). The only writers of `connections` are `findings_tracker`, `lead_tracker`, `dispatcher`,
  `ingest_epstein_exposed`, and `query_fl_dor_property`. **Every edge in this graph was hand-entered by an agent as
  a byproduct of findings work.** That is the true precondition for card 30 and it is invisible on the card.
- **Provenance is thin.** 1,030 of 1,049 tech-right edges are `unverified`; 19 are `verified` (1.8%); 299 have no
  `finding_id` at all. A share statistic computed on this graph is a statistic about unverified assertions.
- Edge direction is unreliable: `owns` rows appear as both `GEO Group -- George Zoley` and `Elon Musk -- Musk
  Foundation`. Ownership direction cannot be recovered from the schema.

### Failure modes — **right instincts, wrong two warnings, four missing**

The card names two: gerrymandered edge definitions, and programs legitimately concentrated by design.

- *Gerrymandered edges* — correct and it fired, but the card's own remedy ("pre-register") is the thing that broke.
- *Legitimately concentrated by design* — correct, and the census makes it checkable: one vendor, Fisher Sand &
  Gravel, holds **18.83%** of the ledger on border-barrier work. Against that reference, every hub-network share
  I computed (0.32%–5.76%) is *smaller than a single vendor's ordinary concentration*. The card would be stronger
  if it told you to compute the top-1-vendor share as the calibration reference; without it, "1.08%" has no scale.

Missing:
1. **Coverage bias in the numerator.** The 22 matched vendors are 9.23% of the ledger's dollars. That is the hard
   ceiling on any hub-network share, and it reflects how much of DHS we happened to document, not how much the
   network captured. Numerator = curated; denominator = complete. The ratio is a coverage statistic wearing a
   capture statistic's clothes.
2. **Peer non-independence.** The card says "against any peer network" as if peers are separable. They are not.
   Jaccard(Thiel, Lonsdale) = 0.60 at CARD-PROXY d2 and 0.68 at d3 — at d3 the two hubs produce *identical*
   vendor sets. Under all edge types at d3 the Thiel network is 48% of the graph and the Musk network 52%
   (Jaccard 0.64), and the Thiel network swallows GEO Group, i.e. the peer's own hub firm.
3. **Value-measure ambiguity → rank inversion.** Procurement has ≥4 value measures. On window obligations the
   Musk network (d3) is 1.71% and the Thiel network 2.51%; on no-double-count ceiling the Musk network is 3.12%
   and the Thiel network 2.55% — the ranking flips with the measure. The card says "share of total program value"
   and never picks one.
4. **Ceiling double-counting.** Summing `current_ceiling` across a multi-award IDIQ family double-counts a shared
   ceiling. Naive summation put the Thiel d2 network at $4.06B of ceiling; the census's own
   `ceiling_sum_no_double_count` puts it at $3.18B — a 22% overstatement from one unflagged step.

---

## 2. FRICTION LOG (every point the card left me guessing)

1. **Share of *what*?** The card's exemplar denominator is a single program (Grow NJ credits, $1.6B). Our ledger is
   an agency-wide census with **no program field**. Candidate denominators, all defensible, all different:
   full universe $76.60B; kept awards $75.86B; ceiling-NDC $460.75B; ICE component $8.89B. The same Thiel network
   at d3 is **2.51%** of DHS obligations and **14.63%** of ICE obligations. A 5.8× swing from the denominator alone.
   The card gives no rule for constructing "the program" out of a procurement ledger (candidate keys exist —
   `solicitation_id`, `parent_idv_piid`, `awarding_office_name`, NAICS/PSC — but the card does not say to use them).
2. **Which value measure?** window obligations / total obligations to date / current ceiling / current total value.
   Unspecified, and outcome-determining (see Failure mode 3 above).
3. **How deep do you traverse?** Unspecified. Dominates the result (0.32% → 2.51% for one hub, one edge set).
4. **How is a peer network constructed?** Unspecified. "Any peer network" is not a construction rule. I had to
   invent one (other high-degree hubs in the same profile), and it turned out the peers are not disjoint from the
   hub, which invalidates the comparison the card asks for.
5. **How do graph nodes join to ledger rows?** Unspecified. This is an entity-resolution problem the card does not
   acknowledge. 25 exact normalized-name matches; a prefix/substring matcher adds real hits (`Leidos Security
   Detection`, `BAE Systems` subsidiaries) and obvious garbage (`Tesla`→`TESLA LABORATORIES`) in the same pass.
   I excluded three ambiguous exact matches (`FRAUD INC`, `ORACLE`, `BOEING`) by hand; the card offers no rule.
6. **Which edge types exist here at all?** I had to read the CHECK constraint to find out. The card's four named
   edge concepts map to five platform types, one of which (clients-of-kin's-firms) has **no representation** and
   one of which (board seats) is conflated with employment and advisory roles.
7. **Recipient vs parent rollup.** GEO Group is $1.076B as recipient and $1.334B rolled to parent; AMI Metals rolls
   to Reliance Steel. Rollup choice moves the numerator ~24% on the biggest matched vendor. Card is silent.
8. **Does an unverified edge count?** 98.2% of the edges are `unverified`. The card sets no evidentiary floor for
   edge admission, though the platform has `strength` and `verification_status` columns ready to enforce one.

---

## 3. RESULT (secondary — numbers only, no leads or findings created)

**Denominators** (from census artifacts; the census agent's own reconciliation is CONFIRMED-grade):

| denominator | value |
|---|---:|
| DHS window net obligations, full universe | $76,596,473,325 |
| Kept awards (≥$250K), the working ledger | $75,858,618,179 |
| Ceiling, no-double-count (`s6-concentration.csv`) | $460,753,653,099 |
| ICE component only (kept awards) | $8,886,796,126 |
| **Graph coverage of the ledger** | 22 of 4,155 recipients = **$6,998,331,601 = 9.23%** |
| Calibration reference: top-1 vendor (Fisher Sand & Gravel) | $14,281,092,256 = **18.83%** |

**Hub network — Peter Thiel.** Edge set CARD-PROXY = `owns, controls, subsidiary_of, shares_officer, familial,
corporate, employment, advisory` (pre-registered as the closest faithful rendering of the card's
ownership/board/kinship set; the literal rendering returns a 1-node network).

| depth | nodes | vendors matched | window obligations | share | ceiling-NDC | share | ICE-only | share of ICE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 11 | 1 (Palantir) | $243,261,962 | 0.32% | $1,176,496,224 | 0.26% | $224,608,710 | 2.53% |
| 2 | 54 | 2 (+Anduril) | $816,803,886 | **1.08%** | $3,176,496,224 | 0.69% | $224,608,710 | 2.53% |
| 3 | 105 | 4 (+GEO Group, goTenna) | $1,901,043,564 | 2.51% | $11,743,509,527 | 2.55% | $1,300,536,888 | 14.63% |

**Strict card-faithful edge set (ownership + board + kinship only): 1 node, 0 vendors, $0, 0.00% at every depth.**

**Peer baselines, identical edge set and depth:**

| hub network | d2 obligations | share | d3 obligations | share | d3 vendor set |
|---|---:|---:|---:|---:|---|
| George Zoley (GEO Group) | $1,076,452,013 | **1.42%** | $1,319,713,975 | 1.74% | GEO, Palantir |
| Elon Musk (Musk/DOGE) | $243,261,962 | 0.32% | $1,298,940,045 | 1.71% | Leidos, Palantir |
| Joe Lonsdale (8VC/Cicero) | $816,803,886 | 1.08% | $1,901,043,564 | 2.51% | **identical to Thiel** |

**Headline:** at the pre-registered depth-2 CARD-PROXY definition, the Thiel network holds **$816.8M = 1.08%** of
the $75.86B DHS ledger — **below** the private-detention peer network (Zoley/GEO, 1.42%) and far below the single
top vendor (18.83%). The full answer space for that one hub, across edge sets × depths × denominators, is
**0.00% to 14.63%**.

**Caveat set (all binding):**
- The numerator is capped at 9.23% by graph coverage; this is as much a coverage measurement as a capture one.
- 98.2% of the edges carrying the network are `unverified`; 28.5% have no `finding_id`.
- The d3 network is contaminated by a tautological route through the `ICE Skip Tracing Program` node and by an
  alumni/competitor route through `Forterra`.
- Thiel and Lonsdale are not independent networks (Jaccard 0.60–0.68), so that pair is not a valid peer test.
- Vendor matching is fuzzy name matching without a UEI join; three ambiguous matches excluded by hand.
- Ceilings use the census's `ceiling_sum_no_double_count`; naive ceiling sums overstate by ~22%.
- **No lead, finding, connection, or infra record was created. `investigation.db` was opened `PRAGMA query_only=ON`.**

---

## 4. AMENDMENTS

### 4a. Card 30 — proposed replacement text

**Mechanics** (replace the existing paragraph):

> **Mechanics:** Take a discretionary public-benefit ledger (tax credits, grants, contracts, variances) and a
> relationship graph around a hypothesized hub — ownership, board seats, kinship, and (the New Jersey innovation)
> *clients of the hub's family's professional firms* counted as network edges. **Before computing anything, write
> down four parameters: (i) the admitted edge types, (ii) the traversal depth, (iii) the denominator — the specific
> program, not the whole agency, and (iv) the value measure (awarded / obligated / ceiling — procurement ledgers
> carry all three and they rank networks differently). Then report the share at every depth from 1 to your chosen
> stop: the sensitivity curve is the result, a single share is not.** Compute the hub network's share of total
> program value against a peer network **that is node-disjoint from the hub network — verify disjointness (Jaccard
> ≈ 0) rather than assuming it; hubs in the same milieu routinely resolve to the same network at depth ≥ 2**
> (Camden = 4× all other growth zones combined; $1.1B of $1.6B). **Calibrate with the top-single-recipient share of
> the same ledger; a network share below the largest ordinary vendor's share is not a finding.** Aggravator: the
> program's rules were drafted by the network's own agents — get the drafting correspondence. **Weaker but
> records-request-free substitute: personnel flow between the awarding office and the network's firms.**

**Minimum data** (replace):

> **Minimum data:** the complete award ledger **with a hard recipient key (UEI/EIN) and a stated coverage
> estimate — what fraction of ledger dollars your graph can even resolve to a node; that fraction is the ceiling on
> any share you can report**; registry/board/lobbying edges **typed by semantics, not by domain, and carrying
> direction**; **node-type labels sufficient to exclude program, statute, and agency nodes from traversal**;
> drafting correspondence via records requests.

**Ithildin mapping** (replace):

> **Ithildin mapping:** query_usaspending / query_fpds for ledgers; graph_tools `neighbors` / `paths` for
> traversal (`--profile`, `--output`; note `paths` currently lacks `--output`). **Edges are the binding
> constraint, not the ledger: `connections` is a hand-curated name-string graph with no UEI/EIN key and no tool
> that materializes registry, 990, or lobbying relations into edges — `connection_inference.py` emits leads, not
> connections. Budget an edge-construction pass before the move is runnable. `relationship_type` encodes
> relationship *domains* (corporate/financial/political), not edge *semantics*: equity stakes land in
> `financial`/`funds`, and `corporate` also carries alumni and outright competitor relations, so a literal
> ownership-only edge set can return an empty network while a widened one imports competitors. Read
> descriptions before admitting a type. `investigation.db` is WAL — read-only auditing needs
> `PRAGMA query_only=ON`; `sqlite3 -readonly` cannot open it.** GAP: no UEI/EIN column on entities; no
> `board_seat` or `client_of` relationship type; no node-type attribute on graph nodes.

**Failure modes** (replace):

> **Failure modes:** edge definitions that gerrymander the "network" (pre-register the edge types **— and then
> check that the pre-registered set actually returns the relationships you know exist; on a domain-typed schema
> the disciplined set can exclude the real ownership edge and admit a competitor edge**); programs legitimately
> concentrated by design (compare against the statute's stated intent **and against the top single recipient's
> share**). **Coverage bias — a curated numerator over a complete denominator measures documentation effort as
> much as capture; state the coverage fraction beside every share. Peer non-independence — networks that overlap
> cannot test each other; report pairwise Jaccard. Tautological traversal — if the graph holds the program,
> statute, or awarding agency as a node, every awardee is one hop from every other; exclude them. Ceiling
> double-counting — shared multi-award IDIQ ceilings must be deduplicated before summing. Edge provenance — a
> share computed over `unverified` edges is a claim about assertions, not about dollars; state the verified
> fraction.**

### 4b. Library-schema amendment

Add two fields to the card schema and to the "How to read a card" header, for every card whose result is a
computed statistic rather than a retrieved document:

- **Pre-registration:** the parameters the analyst must fix *before* computing, because varying them varies the
  answer. Card 30's would read: admitted edge types, traversal depth, denominator, value measure. (Card 3
  denominator-construction, card 5 outlier-in-microdata, and card 21 composition-ratio-screen have the same
  property and would each carry one.)
- **Coverage statement:** the fraction of the denominator the analyst's own data can resolve, reported beside the
  result. Applies to every ledger × curated-graph join in the library.

Suggested header sentence: *"Pre-registration = the parameters that must be fixed before computing, because the
result moves with them; report the sensitivity across those parameters, not a point estimate. Coverage statement
= what fraction of the denominator your data can resolve — the ceiling on any share you can claim."*

One cross-card note: card 20 (`grant-chain-tracing with alias resolution`) carries alias resolution in its own
title. Card 30 performs the same join and omits it. Either card 30 gains the requirement or the library gains a
shared "resolution key" precondition applied to both.

---

## 5. VERDICT

**needs-amendment.** The analytic move is sound and the platform holds enough to run it — a complete, reconciled
award ledger and a real relationship graph — but card 30 as written cannot be executed correctly by an agent
following it literally. Its one procedural safeguard, "pre-register the edge types," maps onto a vocabulary
(ownership / board seats / kinship) that Ithildin's domain-typed `relationship_type` does not express, and
following it literally returned a **one-node network and a 0.00% share for a hub whose two flagship firms hold
$816.8M of the ledger**; the naive widening then imported an alumni-and-competitor path and a tautological route
through a program node. The card also leaves four outcome-determining parameters undefined — denominator, value
measure, traversal depth, peer construction — which together span a 0.00%–14.63% answer range for a single hub,
and it never asks for the two numbers that make any such share interpretable: graph coverage of the ledger
(9.23% here, the hard ceiling on the numerator) and the top single recipient's share (18.83%, which exceeds every
network share computed). None of this is fatal — every gap has a concrete edit, given above, and the amended card
would run today on held data. But an agent handed the current card and this dataset would produce either a null
result or an inflated one, and in both cases would not know which.

---

### Artifacts (scratch, not persisted to repo)
`/tmp/osint-cO2q39JK/` — `hubnet.py` (edge-set reachability), `match.py` (exact name join), `nearmiss.py`
(fuzzy-join hazard), `card30.py` + `card30-results.json` (share matrix), `overlap.py` (peer Jaccard),
`final.py` (headline table), `coverage.py` (ledger coverage), `path2.py` (traversal provenance),
`thiel-ego2.json` (graph_tools output), `techright-edges.tsv`.
