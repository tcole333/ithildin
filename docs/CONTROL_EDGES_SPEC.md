# Control Edges — schema proposal for semantic, directed, dated control relationships

**Status:** proposal, revision 2. Nothing in this document has been applied. `investigation.db` was
opened read-only (`mode=ro` + `PRAGMA query_only=ON`) for every measurement below; zero writes.
**Rev 2 (2026-07-29, decisions confirmed with the user):** control edges are globally scoped with
discovery provenance, not profile-scoped; `entity_relations` is migrated and retired, with
`control_edges` as its disciplined successor; `connection_semantics` ships its table in phase 1 but
its query tooling is deferred; endpoints anchor on entity ids, not name strings; `control_tier` is
predicate-gated via `tier_basis`.
**Gap tracked as:** V1 in `research/patterns/adapter-gaps.md`.
**Evidence:** `research/patterns/_validation/card30-share-of-program.md`,
`research/patterns/_validation/card38-beneficial-control-rollup.md`, plus the direct measurements
in §1, which are new to this document.

---

## 1. The defect, measured

Both card memos concluded that `connections.relationship_type` encodes relationship *domains*
(`corporate`, `financial`, `political`) rather than edge *semantics* (equity stake vs board seat vs
client vs alumni vs competitor). That is correct, and it is the top-line problem. Measuring the
whole table rather than one profile turned up five further defects that change what the fix has to
look like.

Population: **5,710** rows in `connections`; **5,679** non-retracted; **3,654** distinct node
strings; 16 profiles.

### 1.1 One domain type carries at least six different semantics

Running a keyword lexicon over the `description` column, within `relationship_type='corporate'`
(n=1,578) alone:

| latent semantic | rows |
|---|---:|
| officer of | 245 |
| board seat | 189 |
| investor in | 179 |
| equity stake | 130 |
| founder of | 114 |
| parent/subsidiary | 77 |

`financial` (n=1,005) splits the same way: investor 170, equity 73, officer 37, donor 34, founder 34.
Equity stakes land in `financial` and `funds`; chairmanships land in `corporate`. A traversal keyed
on type name cannot separate them.

### 1.2 Direction is alphabetical sort order, not semantics

This is the finding that most constrains the design. `person_a < person_b` holds for:

| type | rows | stored a<b |
|---|---:|---:|
| `subsidiary_of` | 44 | **44 (100%)** |
| `successor_to` | 15 | **15 (100%)** |
| `contracts_with` | 101 | **101 (100%)** |
| `shares_officer` | 25 | **25 (100%)** |
| `owns` | 75 | 73 (97%) |
| `controls` | 116 | 114 (98%) |

`findings_tracker.add_connection()` alphabetises endpoints for dedup. The exemption that preserves
caller order for directional verbs (`DIRECTIONAL_RELATIONSHIP_TYPES`,
[findings_tracker.py:87](tools/findings_tracker.py:87)) landed in commit `16a39b1` on **2026-07-28** —
after all but **7** directional rows had already been written. So for essentially the entire corpus,
column order is a sort artifact.

This reframes the card-38 observation. `Palantir Technologies Inc. --[subsidiary_of]--> Palantir USG
Inc` ([conn #3744](investigation.db)) is not a data-entry slip; it is what the write path
deterministically produces, because `"Palantir Technologies Inc." < "Palantir USG Inc"`. **Direction
was never stored.** No amount of care in future writes recovers it for existing rows, and no
column-order convention can be trusted on backfill.

### 1.3 Direction is destroyed again at read time

Even where order survives, [`build_graph`](tools/graph_tools.py:111) writes every edge into both
`adj[a][b]` and `adj[b][a]`. The traversal layer is undirected by construction. Fixing storage
without fixing this changes nothing.

### 1.4 One row often carries several relationships — sometimes about neither endpoint

11.5% of rows (654) match two or more distinct semantic patterns. The pathological case is worse than
multi-label:

> **conn #2687** `Palmer Luckey --[financial]--> Peter Thiel`
> *"Thiel's Founders Fund is lead investor in Anduril (…Series G alone). Luckey operates within
> Thiel's tech-right network. Stephens (Thiel protege) co-founded Anduril with Luckey."*

The control fact in that row — Founders Fund is Anduril's lead investor — is about **Founders Fund
and Anduril**, neither of which is an endpoint. Similarly conn #2699 (`Founders Fund — Peter Thiel`)
asserts four separate relations, two of them involving Palantir and SpaceX.

*Inference, not measurement:* the frequency of the non-endpoint case is unquantified — detecting it
needs an LLM read, not a regex. But its existence is decisive for the design. **A sub-vocabulary
column on `connections` cannot represent a relationship whose endpoints are not the row's
endpoints.** That single observation rules out Option A as a complete fix.

### 1.5 Temporal columns exist and are empty; the `as_of` filter is a no-op

`valid_from`: **4 of 5,710**. `valid_until`: **0**. `build_graph(as_of=…)` admits undated edges
unconditionally ("Connections without temporal data are always included"), so `--as-of` currently
filters 0.07% of the graph and silently passes the rest. A caller believes they got a dated snapshot.

`date_range` (TEXT, free-form) is populated on **954** rows and **734 (77%) are mechanically
parseable**: `YYYY-YYYY` 350, ISO 183, bare year 137, `YYYY-present` 64. That is the dating backfill
asset.

### 1.6 Alias resolution is silently dead

[`_load_aliases`](tools/graph_tools.py:91) issues `SELECT alias_name, canonical_name FROM
name_aliases`. The column is `alias`, not `alias_name`. The query raises `OperationalError`, which the
surrounding `except … pass` swallows. **The alias map has been empty for every graph traversal**, and
168 alias rows are unused.

Consequence: `Palantir`, `Palantir Technologies`, `Palantir Technologies Inc`, `Palantir Technologies
Inc.` are four nodes; `Anduril`, `Anduril Industries`, `Anduril Industries LLC` are three. Across the
graph, 115 normalized keys cover 246 distinct surface strings. Only **51.3%** of node strings match
an `entities` row exactly.

This is a one-line bug, but it must be fixed *before* backfill, or the backfill mints control edges
against fragmented nodes.

### 1.7 There is no hard identifier and no node typing

`entities` has `ein` (139 populated of 6,178) and no UEI, LEI, CIK, or registry-number column. The
DHS census carries `recipient_uei`. There is no join. `entity_type` has no `program`, `statute`, or
`agency` value, so `ICE Skip Tracing Program`, `Proclamation 10886`, and `Laken Riley Act` are
untypeable graph nodes — the tautological-traversal hazard card 30 hit.

### 1.8 The evidence floor is unusable as a binary, but a tier is already derivable

126 of 5,679 edges are `verified` (2.2%). Gating on that reproduces card 38's outcome: one admitted
edge, $636,500 of a $75.86B ledger.

Two uplift paths exist in held data:
- **211** edges are `unverified` but their backing finding is `verified` — status is simply not
  propagated.
- **3,452** edges carry a `finding_id` whose `claim_type` is already recorded:
  `direct_quote` 1,377 / `paraphrase` 1,211 / `synthesis` 782 / `inference` 81. This maps directly
  onto the claim-type → max-confidence ladder in `CLAUDE.md`.
- 2,227 edges have no `finding_id` at all — these are the genuinely unsourced floor.

### 1.9 `entity_relations` is the control vocabulary's natural experiment — run twice, failed both ways

Revision 1 of this document called `entity_relations` "written by nothing." **That was wrong.** It is
actively written by `entity_tracker.py add-relation` ([entity_tracker.py:322](tools/entity_tracker.py:322),
recent commits `f9f91c0`, `f2b7c90`), holds 897 rows with entity-id-anchored endpoints, and 859 of
them carry a `source`. Its *content* is the best control material on the platform: `sole_member`,
`sole_shareholder`, `beneficial_owner`, `general_partner_of` (6), `trustee_of` (7),
`registered_agent_of` (42), and funds edges with dollar amounts and finding refs.

But `add-relation` passes `relation_type` through as a **raw string** — no CHECK, no vocabulary.
Result: **200+ distinct types across 897 rows.** One relation, six spellings (`subsidiary_of` /
`subsidiary` / `parent` / `parent_of` / `parent_company` / `parent_organization`); descriptions
leaked into the type field (`'purchased all units Aug 2017'`, `'SOP agent / formation counsel'`);
and a long tail of 150+ single-use inventions.

The platform has therefore demonstrated **both** failure modes of edge-vocabulary design:

| store | vocabulary | outcome |
|---|---|---|
| `connections` | closed, too coarse (17 domains) | semantics buried in prose — the V1 defect |
| `entity_relations` | open, unvalidated | 200-type splinter zoo, type-field pollution |

Each table rotted in the direction of its missing constraint. The design lesson is exact: **closed
CHECK vocabulary + a free-text `notes` escape hatch + a single validated writer.** All three, or the
table decays. This is the strongest argument for the schema in §3 — and it reframes `control_edges`
as the *disciplined successor of `entity_relations`* rather than a third parallel store (§6).

One more inflation datum that constrains §3: `strength='strong'` sits on **73%** of non-retracted
edges (4,138/5,679). Free-choice enums drift high under agent writing. `control_tier` therefore
cannot be an agent's free pick — see `tier_basis` in §3.2.

---

## 2. Options weighed

### Option A — typed sub-vocabulary on `connections`

Add `relationship_semantic` with a CHECK constraint over ~25 semantic verbs.

Rejected as the primary fix, for four reasons in descending weight:

1. **It cannot express §1.4.** A scalar column on a row whose endpoints are `Luckey`/`Thiel` cannot
   record `Founders Fund → lead_investor_in → Anduril`.
2. **1:N.** 11.5% of rows need multiple labels. Splitting into multiple rows collides with
   `idx_connections_unique(person_a, person_b, relationship_type, profile_id)`, forcing an index
   change on a live 5,710-row table.
3. **Direction still needs repair on 5,710 rows** — the hook-blocked `UPDATE connections SET` path,
   and per §1.2 there is nothing correct to repair *to* without re-reading descriptions anyway.
4. **Scope mismatch.** Only ~20% of edges are control-relevant (§4). Loading `social`,
   `intelligence`, and `legal` edges with ownership-threshold and effective-date machinery is dead
   weight on 80% of the table.

### Option C — generic edge-attributes (EAV) table

Rejected. Untyped keys cannot carry per-attribute CHECK constraints, every query becomes a pivot,
direction is still unaddressed, and an open key space re-creates exactly the drift that produced the
domain/semantics muddle. It offers flexibility where the problem is *insufficient constraint*.

### Option B — separate dated control table — **recommended, in a layered form**

Additive; expresses arbitrary endpoints; direction enforced by column naming rather than convention;
dates, thresholds, evidence tier, and identifiers all live where they belong; and it leaves the loose
`connections` graph untouched for discovery work, which the project's methodology explicitly values
("Document aggressively … it may surface connections later").

The one real risk is a fourth graph store drifting alongside the other three. §1.9 shows how that
happens (a writer without a vocabulary), and the mitigation is structural, not aspirational:
`control_edges` *replaces* `entity_relations` (migrate + retire, §6), a single validated writer owns
the vocabulary (§7), and every traversal reports coverage (§5). End state is **two** graph stores —
`connections` as the loose discovery graph, `control_edges` as the assertion layer — not four.

**Recommendation: two additive tables, not one.**

| layer | table | scope | fill cost | answers |
|---|---|---|---|---|
| **label** | `connection_semantics` | all 5,679 edges, multi-label | cheap, bulk | "what does this edge mean?" / "exclude competitor + alumni" |
| **assertion** | `control_edges` | ~1,150 control-relevant | expensive, reviewed | "who controlled what, when, on what evidence?" |

They are separate because they are different epistemic objects. A semantic label *classifies an
existing assertion* — cheap, high-volume, LLM-backfillable, low stakes, reversible. A control edge is
*a new evidentiary claim* with direction, dates, and a threshold — it needs provenance and review.
Merging them would force the review gate onto 5,679 rows, or waive it on the 1,150 that need it.

A third table, `entity_identifiers` (§3.3), addresses the join-key gap both memos flagged. It is
independent and can ship separately.

---

## 3. Schema

### 3.1 `connection_semantics` — the label layer

```sql
CREATE TABLE connection_semantics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id   INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    semantic        TEXT NOT NULL CHECK (semantic IN (
        -- control family (candidates for control_edges promotion)
        'majority_owner_of','minority_owner_of','parent_of','beneficial_owner_of',
        'controls','board_chair_of','board_member_of','officer_of','founder_of',
        'general_partner_of','trustee_of','successor_to',
        -- capital family
        'lead_investor_in','investor_in','lender_to','grantor_to','donor_to',
        -- commercial family
        'client_of','counsel_to','vendor_to','co_contractor_of','subcontractor_to',
        -- personnel / affiliation
        'employed_by','advisor_to','alumnus_of','co_founder_with',
        -- explicitly NOT control — must be nameable to be excludable
        'competitor_of','co_defendant_with','co_investor_with','kin_of',
        'co_member_of','social_tie','mentioned_with'
    )),
    -- The semantic's own endpoints. NULL means "same as the parent connection row,
    -- in the direction given by subject_is". Non-NULL handles the §1.4 case where the
    -- relationship is about entities that are not the row's endpoints.
    subject_name    TEXT,
    object_name     TEXT,
    subject_is      TEXT CHECK (subject_is IN ('person_a','person_b','other')),
    resolution_method TEXT NOT NULL CHECK (resolution_method IN
        ('lexicon','llm','manual','source_document','inherited')),
    resolution_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (resolution_status IN ('candidate','reviewed','rejected')),
    resolution_score  REAL,
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Uniqueness must live in a standalone expression index: SQLite rejects COALESCE()
-- inside a table-level UNIQUE. idx_connections_unique already sets the precedent.
CREATE UNIQUE INDEX idx_cs_unique ON connection_semantics(
    connection_id, semantic, COALESCE(subject_name,''), COALESCE(object_name,''));
CREATE INDEX idx_cs_connection ON connection_semantics(connection_id);
CREATE INDEX idx_cs_semantic   ON connection_semantics(semantic, resolution_status);
```

`resolution_status`/`resolution_method` deliberately mirror `finding_entities`, which already uses
`asserted|candidate|reviewed` and `exact|alias|fuzzy|manual`.

Naming the anti-control semantics (`competitor_of`, `alumnus_of`, `co_investor_with`) is the point,
not an afterthought. Card 30's failure was that the alumni and competitor edges in conn #3463 were
*unnameable*, so they could not be excluded.

### 3.2 `control_edges` — the assertion layer

```sql
CREATE TABLE control_edges (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ENDPOINTS: anchored on entity ids. The writer runs the same _ensure_entity
    -- machinery findings_tracker.add_connection already uses, so NOT NULL is cheap.
    -- Names are denormalized display copies refreshed from entities; they carry no
    -- identity. This is what keeps the fuzzy-name-join hazard out of the control layer.
    controller_entity_id INTEGER NOT NULL REFERENCES entities(id),
    controlled_entity_id INTEGER NOT NULL REFERENCES entities(id),
    controller_name     TEXT NOT NULL,
    controlled_name     TEXT NOT NULL,
    -- DIRECTION: enforced by column name. There is no a/b ordering to get backwards.

    control_type        TEXT NOT NULL CHECK (control_type IN (
        'equity','voting','board','officer','contractual','beneficial',
        'trust','general_partner','successor','de_facto'
    )),
    semantic            TEXT NOT NULL,   -- canonical vocabulary owned by the writer module (§7)
    control_tier        TEXT NOT NULL CHECK (control_tier IN (
        'terminal',      -- majority equity, sole member, disclosed UBO, consolidation parent
        'presumptive',   -- e.g. GP of the fund; chair + founder + largest holder
        'influence'      -- lead investor, minority stake, board seat — NOT control
    )),
    -- §1.9: free-choice enums inflate (73% of connections claim strength='strong').
    -- Non-influence tiers must cite a checkable predicate; the writer validates it:
    --   terminal    <= ownership_pct > 50, OR semantic in {parent_of, sole_member,
    --                  beneficial_owner_of}, OR a registry/consolidation filing ref
    --   presumptive <= a predicate from a fixed list, named here (e.g. 'gp_of_fund')
    tier_basis          TEXT,

    ownership_pct       REAL CHECK (ownership_pct IS NULL
                                    OR (ownership_pct >= 0 AND ownership_pct <= 100)),
    pct_is_approximate  INTEGER NOT NULL DEFAULT 0,

    -- EFFECTIVE DATING (tools/date_normalize.py vocabulary, precision per endpoint:
    -- "2003 – 2019-05-12" is year-precision at one end and day-precision at the other)
    valid_from            TEXT,
    valid_from_precision  TEXT CHECK (valid_from_precision IN ('day','month','year','unknown')),
    valid_until           TEXT,
    valid_until_precision TEXT CHECK (valid_until_precision IN ('day','month','year','unknown')),
    open_ended          INTEGER NOT NULL DEFAULT 0,   -- 1 = "to present" as asserted, not as verified

    -- EVIDENCE FLOOR
    evidence_tier       TEXT NOT NULL CHECK (evidence_tier IN (
        'documented',    -- primary source, direct_quote, verified
        'corroborated',  -- paraphrase of a primary source, or 2+ independent secondaries
        'asserted',      -- synthesis/inference from held findings
        'unsourced'      -- no finding_id, no evidence ref
    )),
    finding_id          INTEGER REFERENCES findings(id),
    source_connection_id      INTEGER REFERENCES connections(id),   -- provenance back-pointers
    source_entity_relation_id INTEGER,                              -- retired entity_relations row
    evidence_ref        TEXT,
    source_quote        TEXT,

    direction_basis     TEXT NOT NULL CHECK (direction_basis IN (
        'source_document','description_parse','llm_read','manual','registry_filing'
    )),
    derivation_method   TEXT NOT NULL CHECK (derivation_method IN
        ('lexicon','llm','manual','registry_ingest','inherited')),
    review_status       TEXT NOT NULL DEFAULT 'candidate'
        CHECK (review_status IN ('candidate','reviewed','disputed','retracted')),
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMP,

    -- GLOBAL SCOPE (rev 2): control facts are world-facts — entity-like, not
    -- finding-like. profile_id records which investigation first surfaced the edge;
    -- it is provenance only and deliberately excluded from the uniqueness key, so the
    -- same real-world edge cannot fork per profile (the Barak re-derivation lesson).
    profile_id          TEXT,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_run_id        TEXT,

    CHECK (controller_entity_id <> controlled_entity_id),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CHECK (control_tier = 'influence' OR tier_basis IS NOT NULL)
);
-- Standalone expression index (table-level UNIQUE cannot hold COALESCE):
CREATE UNIQUE INDEX idx_ce_unique ON control_edges(
    controller_entity_id, controlled_entity_id, semantic, COALESCE(valid_from,''));
CREATE INDEX idx_ce_controller ON control_edges(controller_entity_id, review_status);
CREATE INDEX idx_ce_controlled ON control_edges(controlled_entity_id, review_status);
CREATE INDEX idx_ce_dates      ON control_edges(valid_from, valid_until);
CREATE INDEX idx_ce_tier       ON control_edges(control_tier, evidence_tier);
```

Five design choices worth defending:

- **Entity-id endpoints, NOT NULL.** `entity_relations` got this right and `connections` got it
  wrong; the 51.3% name-resolution rate is the cost of the wrong choice. `_ensure_entity` already
  exists, so requiring ids costs one call at write time — and it makes the UEI crosswalk compose:
  ledger UEI → `entity_identifiers` → entity id → control edges, no name fuzz anywhere in the chain.
- **Global scope with discovery provenance.** One row per real-world edge; `profile_id` records
  first discovery but is outside the uniqueness key. Per-profile forks of the same ownership fact
  were the failure mode in the Barak duplicate-findings incident.
- **`control_tier` is separate from `control_type`, and gated by `tier_basis`.** A board seat is
  `board`-type but only `influence`-tier; a chair who is also founder and largest holder is
  `presumptive`. And because free-choice enums provably inflate here (73% `strong`), `terminal` and
  `presumptive` are writer-enforced predicates, not vibes — the predicate is recorded.
- **`open_ended` is a flag, not a NULL `valid_until`.** "2025 to present" (64 rows in `date_range`)
  asserts an open interval; a missing end date asserts nothing. Collapsing them makes stale edges
  look live forever.
- **`ownership_pct` will be sparse and partly corrupted.** Descriptions in this corpus have suffered
  the known zsh currency-stripping papercut — conn #2699 reads `controls B AUM`, conn #2700 reads
  `B+ Army contract`. Any percentage parsed from a description must be checked against that failure
  mode before it is stored. Prefer `NULL` over a guess.

### 3.3 `entity_identifiers` — the crosswalk (separable phase)

```sql
CREATE TABLE entity_identifiers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id    INTEGER NOT NULL REFERENCES entities(id),
    id_type      TEXT NOT NULL CHECK (id_type IN
        ('uei','lei','cik','ein','duns','registry_no','icij_node','opensanctions_id','cage')),
    id_value     TEXT NOT NULL,
    jurisdiction TEXT,
    source       TEXT NOT NULL,
    valid_from   TEXT,
    valid_until  TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_type, id_value, COALESCE(jurisdiction,''))
);
```

This is what makes a graph↔ledger join non-fuzzy. Both memos named its absence as blocking; card 30
measured the cost (`Tesla` → `TESLA LABORATORIES INC.`, `The Boring Company` → `MACK BORING & PARTS
CO`).

It also seeds itself mechanically: `census-awards.csv` already carries `recipient_name` /
`recipient_uei` / `recipient_parent_uei` / `recipient_parent_name` for 4,155 DHS vendors. Every
vendor we hold as an entity gets its UEI row with `source='dhs-census-2026-07-28'` and zero research;
the 53 conflicting-parent UEIs are stored as-is (the conflict is real; the crosswalk records
identifiers, not resolutions).

### 3.4 Node typing

Add `program`, `statute`, `agency`, `court_case`, `event` to the accepted `entities.entity_type`
values (the column has no CHECK constraint, so this is a documentation + validator change, not DDL),
and exclude them from control traversal by default. Card 30's tautological route
`Palantir → ICE Skip Tracing Program → GEO Group` (conns #2859, #2860) disappears.

---

## 4. Backfill

Measured feasibility over the 5,679 non-retracted rows:

| asset | volume |
|---|---|
| non-blank `description` | 5,200 (91.6%), median 152 chars |
| blank `description` | 479 (8.4%) — unbackfillable from text |
| single unambiguous lexicon hit | ~1,610 (28.4%) |
| ≥2 lexicon hits (multi-label) | 654 (11.5%) |
| no lexicon hit | 3,412 (60.1%) — needs LLM or stays unclassified |
| control-relevant candidates | **1,156 (20.4%)** — epstein 407, tech-right 227, hfia 144 |
| — with `direct_quote`/`paraphrase` backing (upgradeable on review) | 414 |
| — with `synthesis`/`inference` backing (caps at `asserted`) | 182 |
| — with **no `finding_id`** (needs new evidence, not review) | **560** |
| `entity_relations` rows (entity-anchored, semantically typed, 859 sourced) | **897** |
| parseable `date_range` | 734 of 954 |
| evidence tier derivable from backing finding | 3,452 |
| verified-finding → unverified-edge uplift | 211 |

**Pass 0 — deterministic, no model.**
Fix `_load_aliases` (§1.6) first. Then: parse `date_range` via `tools/date_normalize.py`; derive
`evidence_tier` from `findings.claim_type` × `findings.verification_status`
(`direct_quote`+`verified` → `documented`; `paraphrase` → `corroborated`; `synthesis`/`inference` →
`asserted`; no `finding_id` → `unsourced`); write `connection_semantics` rows with
`resolution_method='inherited'` for the six already-semantic types
(`owns`, `controls`, `subsidiary_of`, `successor_to`, `shares_officer`, `supplies`, n=284).
*No direction inferred from `connections` column order in this pass* — per §1.2 it is worthless.

Pass 0 also migrates `entity_relations`: a fixed mapping table takes its top ~25 types into the
canonical vocabulary (`sole_member` → `equity`/`terminal`; `general_partner_of` →
`general_partner`/`presumptive`; `registered_agent_of` → **candidate-generator only, not control**;
splinters like `subsidiary`/`parent`/`parent_company` collapse into `parent_of`). Unlike
`connections`, its a→b order is caller intent (no alphabetizing writer ever touched it) — but intent
is not proof, so migrated rows keep `review_status='candidate'`, get
`direction_basis='description_parse'` only where the description confirms direction, and carry
`source_entity_relation_id` back-pointers. The ~150 junk/one-off types fall through to Pass 2.

**Pass 1 — lexicon, high precision.**
Emit `connection_semantics` only where exactly one label fires and it is consistent with the domain
type. `resolution_method='lexicon'`, `resolution_status='candidate'`. Never promotes to
`control_edges` unaided.

**Pass 2 — LLM adjudication, batched by profile.**
Where a `finding_id` exists (3,452 edges), read the **finding's evidence quotes**
(`finding_evidence.source_quote`), not just the connection description — the description is a
paraphrase of a paraphrase, and quotes are one step closer to the source. Emit (subject, semantic,
object, direction_basis, dates, confidence) tuples. This is the pass that resolves §1.4 — the model
can name Founders Fund and Anduril as the real endpoints of conn #2687. Output is always `candidate`.
Caps: **description-only derivation may not exceed `evidence_tier='asserted'`**; quote-grounded
derivation may propose `corroborated` but only review confirms it. This matches the
`synthesis → max medium confidence` rule in `CLAUDE.md`.

**Pass 3 — review, control edges only.**
The review pool is **~596 rows, not 1,150**: only candidates with a backing finding can be lifted by
review (414 `direct_quote`/`paraphrase` → `documented`/`corroborated`; 182 `synthesis`/`inference`
stay capped at `asserted` but get direction/date/tier checked). The other **560 candidates have no
`finding_id` — review cannot help them; they need new evidence.** Those become leads via the
existing `auto_leads` pattern ("source the control claim in conn #NNNN"), which converts a schema
defect into ordinary queue work. Only `reviewed` rows are admissible at `documented`/`corroborated`.

**Direction normalization**, explicitly: direction is derived **from description text, never from
column order**, and the basis is recorded in `direction_basis`. Rows where the description does not
determine direction are written with `review_status='candidate'` and
`direction_basis='description_parse'`, and are excluded from `terminal`-tier traversal until
reviewed. Errors are then auditable in one query (`WHERE direction_basis='llm_read' AND
review_status='candidate'`) instead of invisible.

---

## 5. Should `verification_status` gate traversal?

**No — not as a binary.** Gating on `verification_status='verified'` admits 126 edges platform-wide
and reproduces card 38's null (one edge, $636,500 of $75.86B). That is not discipline, it is a dead
tool.

Instead: `--min-evidence {documented,corroborated,asserted,unsourced}` defaulting to `asserted`, with
**mandatory coverage output on every traversal**:

```
admitted 84 edges | excluded: 12 below evidence floor, 7 outside date window,
                    31 non-control semantic, 3 excluded node type
coverage: 84/137 candidate edges (61.3%) | dated: 22/84 (26.2%)
```

Card 38's amendment #3 asked for exactly this four-row coverage statement. Making it a property of
the tool rather than of analyst discipline is the whole point — card 30 and card 38 both failed
because the coverage number had to be hand-computed and could be omitted.

Corollary: `--as-of` gains an explicit policy. `--as-of-policy strict` excludes undated edges (today
that would drop 99.93% of the graph and *should say so*); `lenient` keeps current behavior but
reports the undated fraction. The current silent-lenient default is the trap.

---

## 6. Migration strategy (hook-compatible)

`.claude/hooks/protect-investigation-db.sh` blocks, for Bash commands mentioning `investigation.db`:
`DROP TABLE`; `DELETE FROM` without `tools/` in the command; `rm` of the db; and
`UPDATE (findings|connections) SET` without `tools/` in the command.

**The migration needs none of those.** It is `CREATE TABLE` + `INSERT` only. This is not a workaround
— it is a design consequence. Dates, direction, and semantics live on the new tables precisely
*because* the existing rows must not be rewritten: their `relationship_type` and endpoint order are
accurate records of what an agent asserted, and the audit trail is worth more than the tidiness.

Concretely:

1. `tools/migrate_control_edges.py --create` — DDL only, idempotent (`CREATE TABLE IF NOT EXISTS`),
   `--dry-run` prints the DDL.
2. `tools/migrate_control_edges.py --backfill-pass0` — deterministic inserts, `--dry-run`,
   `--profile <name>` to run one profile at a time, `--limit`.
3. Passes 1–3 likewise, each `--dry-run`-able and profile-scoped.
4. `cp investigation.db investigation.db.bak-pre-control-edges` before pass 0 (matches the existing
   `.bak-pre-coremodel` / `.bak-pre-reanchor` convention).
5. Rollback is `DROP TABLE control_edges` — which the hook blocks from Bash, so the migration tool
   gets an explicit `--rollback` subcommand that performs it in-process. Because the migration is
   additive, rollback loses only derived data.
6. **`entity_relations` retirement needs no DDL at all.** The table stays in place as a historical
   record (dropping it is both hook-blocked and pointless); `entity_tracker.py add-relation` gains a
   deprecation warning pointing at the new writer; and `build_graph` stops reading `entity_relations`
   once its rows are migrated with back-pointers. Retirement = stop writing + stop reading, not
   destruction.

**Tests ship with each phase** (per the clean-PR policy): migration idempotency on a fixture db
(`--create` twice = no-op); Pass-0 determinism (same fixture in, byte-identical rows out); a
vocabulary single-source assertion (the DDL CHECK lists are generated from — or asserted equal to —
the writer module's canonical lists, so they cannot drift); an alias-resolution regression test that
would have caught §1.6 (build a graph over a fixture with `name_aliases` rows and assert the variants
collapse); and a hook non-interference test that runs each migration command string through
`protect-investigation-db.sh` and asserts exit 0. No test touches the live `investigation.db`.

**The one place an `UPDATE connections` is warranted** is the alias-driven node collapse (§1.6) if we
ever choose to rewrite endpoint strings. Recommendation: **don't**. Resolve at read time through the
(now working) alias map, and record collapses in `name_aliases`. If a `connections` field must ever
change, expose `findings_tracker.py correct-connection <id> --field … --reason …`. Most of that
machinery already exists internally: `_record_connection_correction`
([findings_tracker.py:1740](tools/findings_tracker.py:1740)) and `_invalidate_verified_connection`
(:1759) have already logged **383** connection corrections (`verification_status` 151, `profile_id`
101, `description` 31, `strength` 12, `date_range` 9). What is missing is the CLI surface —
`ALLOWED_CORRECT_FIELDS` and the `correct` subcommand are findings-only. The hook permits the new
subcommand because the command string contains `tools/`.

---

## 7. `graph_tools.py` changes

Ordered by dependency.

1. **Fix `_load_aliases`**: `alias_name` → `alias` ([graph_tools.py:95](tools/graph_tools.py:95)).
   Replace the bare `except OperationalError: pass` with a warning — a silently empty alias map is
   how this survived. *Prerequisite for everything else.*
2. **`build_graph(..., directed=False)`** — when `True`, populate `adj[a][b]` only
   ([graph_tools.py:183](tools/graph_tools.py:183), and :210 for the `entity_relations` pass).
3. **`build_control_graph(profile_id, as_of, min_evidence, tiers, semantics)`** — reads
   `control_edges`, always directed, always dated, returns `(adj, nodes, coverage)`.
4. **`--semantic` / `--exclude-semantic` on `neighbors`, `paths`, `communities`, `triangles`.** Card
   30 had to hand-roll BFS because `neighbors` has no type filter at all; only `triangles` accepts
   `--rel-type`.
5. **`--output` on `paths`** — the only subcommand lacking it, in violation of the project's
   bulk-results convention.
6. **`--exclude-node-types program,statute,agency`**, default on for control traversal.
7. **New `control-path <source> <target>`** and **`controllers-of <entity> [--as-of]`** subcommands.
8. **Coverage block emitted by every traversal** (§5).
9. **`--as-of-policy {lenient,strict}`**, default `lenient` + undated-fraction warning.
10. **`control-coverage` subcommand** — reports how much of `connections` has been semantically
    classified, per profile. This is the anti-orphan check: if `entity_relations` had had one, its
    897 unmaintained rows would have been visible years ago.

**The write path (the actual fix).** Both existing stores rotted at write time — `connections` under
a too-coarse closed vocabulary, `entity_relations` under an open one (§1.9). So phase 1 includes a
single writer module, `tools/control_edges.py`, which **owns the canonical semantic vocabulary and
the tier predicates** (the DDL CHECK lists are asserted against it in tests), runs `_ensure_entity`
on both endpoints, validates `tier_basis`, and normalizes dates through `date_normalize`. The legacy
write paths stay functional but warn: `entity_tracker.py add-relation` prints a deprecation notice
naming the new writer, and `findings_tracker.py connect` nudges toward `--semantic` when it sees a
control-flavored description. New edges must not rot on arrival; that property lives in the writer,
not in agent discipline.

---

## 8. Worked example — Thiel / Palantir / Anduril

### 8.1 Today

Under card 30's pre-registered edge set (`owns`, `controls`, `subsidiary_of`, `shares_officer`,
`familial`), **Peter Thiel is an isolated node** with 25 documented edges: depth 1 = 1 node, vendors
matched = 0, share = 0.00%.

Widen to `+corporate, employment, advisory` and the traversal reaches Anduril via:

```
Peter Thiel --[corporate]--> Palantir --[corporate]--> Forterra --[corporate]--> Anduril
```

where the final hop is **conn #3463**: *"Scott Sanders (Forterra CGO) is former early Anduril
employee. Both compete for DoD ground autonomy programs."* — an alumni edge and an explicit
**competitor** edge. The real relationship (Thiel → Founders Fund → Anduril) is excluded because
investment is typed `financial`/`funds`.

### 8.2 The same five rows, decomposed

| conn | stored | description (ground truth) |
|---|---|---|
| #2700 | `Palantir Technologies Inc --[corporate]--> Peter Thiel` | "Thiel is Palantir chairman; FF founding investor" |
| #2717 | `Palantir Technologies --[corporate]--> Peter Thiel` | "Co-founder of Palantir" |
| #2699 | `Founders Fund --[financial]--> Peter Thiel` | "Thiel founded Founders Fund; controls …AUM; FF invested in Palantir, Anduril, SpaceX" |
| #2687 | `Palmer Luckey --[financial]--> Peter Thiel` | "Thiel's Founders Fund is **lead investor in Anduril**" |
| #3463 | `Anduril Industries --[corporate]--> Forterra` | "…former early Anduril employee. **Both compete** for DoD ground autonomy" |
| #3744 | `Palantir Technologies Inc. --[subsidiary_of]--> Palantir USG Inc` | "Palantir USG Inc **is the** … subsidiary **of** Palantir Technologies Inc." |

Every fact needed is present. None of it is in `relationship_type`, and none of it is in the endpoint
order.

### 8.3 After Pass 0 (alias fix)

`Palantir` / `Palantir Technologies` / `Palantir Technologies Inc` / `Palantir Technologies Inc.`
collapse to one node; `Anduril` / `Anduril Industries` / `Anduril Industries LLC` to one. #2700 and
#2717 stop being edges to different companies.

### 8.4 After Pass 2 — `connection_semantics`

```
#2700 → board_chair_of   (subject=Peter Thiel,   object=Palantir Technologies Inc)
#2700 → investor_in      (subject=Founders Fund, object=Palantir Technologies Inc)   [subject_is='other']
#2717 → founder_of       (subject=Peter Thiel,   object=Palantir Technologies Inc)
#2699 → founder_of       (subject=Peter Thiel,   object=Founders Fund)
#2699 → controls         (subject=Peter Thiel,   object=Founders Fund)
#2699 → investor_in      (subject=Founders Fund, object=Anduril Industries)          [subject_is='other']
#2687 → lead_investor_in (subject=Founders Fund, object=Anduril Industries)          [subject_is='other']
#3463 → alumnus_of       (subject=Scott Sanders, object=Anduril Industries)          [subject_is='other']
#3463 → competitor_of    (subject=Forterra,      object=Anduril Industries)
#3744 → parent_of        (subject=Palantir Technologies Inc, object=Palantir USG Inc)
```

Note #2687 and #3463: both carry `subject_is='other'` — the semantics are about entities that are not
the row's endpoints. This is the representation Option A cannot produce.

### 8.5 After Pass 3 — `control_edges`

| controller | → | controlled | type | tier | dates | evidence | basis |
|---|---|---|---|---|---|---|---|
| Peter Thiel | → | Palantir Technologies Inc | board | **presumptive** | 2003– open | corroborated (#4589 paraphrase) | description_parse |
| Peter Thiel | → | Founders Fund | equity/voting | **terminal** | 2005– open | corroborated (#4587 paraphrase) | description_parse |
| Founders Fund | → | Anduril Industries | equity | **influence** | 2017– open | corroborated (#4572) | llm_read |
| Palantir Technologies Inc | → | Palantir USG Inc | equity | **terminal** | — | documented (`subsidiary_of`, verified) | description_parse |

*Date provenance, stated because this document argues for dating discipline:* `2003` is carried by
conn #2757 ("co-founded Palantir with Thiel in 2003"); `2017` by conn #2688 ("Trae Stephens worked at
Palantir 2008-2014 before co-founding Anduril") and #2684 ("since 2017"). **`2005` for Thiel →
Founders Fund appears in no held description** — it is illustrative of what Pass 3 must supply, and
under the schema that edge would carry `valid_from = NULL` until sourced, which excludes it from any
`--as-of-policy strict` traversal. That exclusion is the mechanism working, not a gap in the example.
The Palantir USG row has no dates at all for the same reason.

Excluded and *auditably so*: `competitor_of`(Forterra→Anduril), `alumnus_of`(Sanders→Anduril),
`co_contractor_of`(Anduril↔Palantir, conn #2688 — the TITAN teaming edge), and the program node
`ICE Skip Tracing Program`.

### 8.6 The resolved traversal

```
$ graph_tools.py --profile tech-right controllers-of "Anduril Industries" \
      --as-of 2026-01-01 --min-evidence corroborated --max-tier influence

Anduril Industries
  ← [equity/influence]    Founders Fund            (2017–, corroborated, conn #2687/#2699)
      ← [equity/terminal] Peter Thiel              (2005–, corroborated, conn #2699)

admitted 2 edges | excluded: 1 competitor_of, 1 alumnus_of, 1 co_contractor_of,
                             1 program node, 0 below evidence floor
coverage: 2/6 candidate edges (33.3%) | dated: 2/2 (100%)
```

```
$ graph_tools.py --profile tech-right control-path "Peter Thiel" "Anduril Industries" --as-of 2026-01-01

Peter Thiel --[controls/terminal]--> Founders Fund --[equity/influence]--> Anduril Industries
  path tier: influence  (weakest link governs — this is NOT a control path)
```

Three things resolve at once:

1. **Thiel is no longer isolated.** He reaches Palantir at depth 1 and Anduril at depth 2, on the
   real relationships, from rows that already exist.
2. **The competitor route is gone** — not by luck of edge-set choice but because `competitor_of` is a
   nameable, excluded semantic.
3. **The path is honestly labelled `influence`, not control.** Lead-investor status in a
   later-stage round is not control of Anduril, and the tier says so. Card 30's 1.08% "Thiel network"
   share would, under this schema, have to be reported as an influence-tier network with a stated
   33.3% edge coverage — which is the finding the memo actually supports.

For card 38's rollup: `Palantir Technologies Inc → Palantir USG Inc` is a `terminal`-tier dated edge
in the correct direction, so DHS obligations to Palantir USG roll to Palantir — a real consolidation
the current schema stores backwards and would therefore invert.

---

## 9. Phasing, and what this does not fix

| phase | content | blocking? |
|---|---|---|
| **0** | Alias fix + `--output` on `paths` + `directed=` reader + `--as-of-policy` | No — bugfix-grade, ship independently |
| **1** | DDL (all three tables) + `tools/control_edges.py` writer + legacy-writer deprecations + Pass 0 (incl. `entity_relations` migration) + tests | Unblocks nothing alone |
| **2** | Passes 1–2 (lexicon + LLM over quotes), populating **both** tables; control traversal tooling (`build_control_graph`, `controllers-of`, `control-path`, coverage lines) | **Milestone: cards 30/38 rerun honestly at `asserted` floor** |
| **3** | Pass 3 review (~596 rows) + auto-leads for the 560 unsourced candidates; `entity_relations` reads switched off | Lifts results to `corroborated`/`documented` |
| **4** | `entity_identifiers` + mechanical UEI seed from the census; label-layer query tooling (`--semantic` filters on the discovery graph) | Separable; unblocks graph↔ledger joins and full card-30 pre-registration |

**Not fixed by this proposal:**

- **Historical registry coverage.** Card 38's core blocker is that most registries expose only
  current state. This schema gives dates a *place to live*; it does not source them. GLEIF returned
  zero parents in a 42-name frame, and OpenCorporates is 401-blocked.
- **The 53 UEIs / $2.687B conflicting-parent set.** `control_edges` can *represent* the conflict
  (two dated edges with overlapping validity), and traversal can refuse to resolve it, but choosing
  the right parent needs dated filings we do not hold. Representing it honestly is the improvement.
- **479 blank descriptions.** Nothing to parse.
- **Coverage bias.** A curated numerator over a complete denominator is still a documentation
  statistic; §5's mandatory coverage line makes that visible rather than solving it.

The honest summary: this converts a graph that *silently returns wrong control answers* into one that
returns narrower, tier-labelled, coverage-stated answers — and refuses where it does not know.
