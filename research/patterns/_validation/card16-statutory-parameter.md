# Card 16 validation — statutory-parameter-screen (impossible values, cap clustering)

**Card under test:** `research/patterns/detection-signatures.md` § 16 (lines 293–310).
**Data exercised:** `data/ppp_loans.parquet` (666 MB, 11,365,188 loans, 2020-04-03 → 2021-07-19) via
`tools/query_ppp.py`; `registry.db` (7.1 GB, project root) via `tools/query_registry.py` and direct read-only
SQLite.
**Slice:** national for the mass-point leg (cheap); **Florida** (964,980 loans) for the paired
ghost-recipient / address-colocation legs.
**Runtime:** national mass-point queries < 1 s each; the full three-leg FL screen ran in **8.3 s**.
**No writes:** investigation.db untouched (not opened); registry.db opened `mode=ro`; all artifacts in
`/tmp/osint-6LeVcWG2/`.

---

## 1. EXECUTABILITY, field by field

### Mechanics — partially sufficient. Screen (b) is runnable; screen (a) is structurally empty here; the two paired tests are under-specified to the point of being misleading.

**(b) benefit-cap-clustering — runnable, but the card's one named parameter is wrong in three ways.**

1. *The value is rounded.* The card says the mass point is at "$20,833". The statutory parameter is
   `$100,000 / 12 x 2.5 = $20,833.33`. The card's figure is the *colloquial* rounding, and the card never
   shows the derivation, so an analyst cannot re-derive it for a different draw or sector.
2. *The mass point is not "exactly at the statutory maximum."* It sits at lender-specific roundings **below**
   the maximum. Nationally: `$20,833.00` n=519,891, `$20,832.00` n=380,405, and the *true* statutory
   `$20,833.33` only n=58,432. An analyst who follows the card's "mass points exactly at statutory maxima"
   literally captures **3.6 %** of the first-draw cluster.
3. *There is more than one cap.* PPP has at least four screenable parameters and the card names one:
   first-draw program ceiling `$10,000,000`; second-draw program ceiling `$2,000,000`; sole-proprietor
   2.5x cap `$20,833.33` (both draws); second-draw NAICS-72 3.5x cap `$29,166.67`. I supplied all four
   from knowledge — none are recorded anywhere in the repo. The NAICS-72 cap validated empirically:
   1,381 of the 1,459 FL second-draw loans in `[29,100, 29,166.67]` are NAICS 72 (94.6 %).

**(a) impossible-value-vs-legal-limit — structurally null on this dataset.** Zero loans exceed either
program ceiling (max first-draw = exactly `$10,000,000`, max second-draw = exactly `$2,000,000`), because
SBA's E-Tran enforces the ceiling at origination. The card presents (a) and (b) as two co-equal screens
without saying that (a) can only fire where the cap is *self-reported* (Thiel's Roth) and never where it is
*machine-enforced at entry* (PPP). A *derived*-cap variant does fire — 5,223 FL loans with
`businesstype IN ('Sole Proprietorship','Self-Employed Individuals','Independent Contractors')`,
`jobsreported = 1`, and amount > `$20,833.33` — but the card gives no recipe for constructing a derived cap
from a composite of fields.

**No thresholds anywhere.** "Mass point" has no operational definition (spike ratio? excess over local
density? multiple of the adjacent bin?). I invented one: bin-vs-neighbour ratio on 250-wide bins.

**Ghost-recipient — the load-bearing step is missing.** "Recipients absent from the registries that should
contain them" gives no rule for deciding *which* recipients should be there. On the FL at-cap population,
**86.2 %** are Sole Proprietorship / Self-Employed Individuals / Independent Contractors — entity forms no
state corporate registry is required to contain. Run naively, the screen reports a 95.6 % "ghost rate" on
that subpopulation, which is 100 % artifact. The missing step is a registerable-business-type filter built
from the 21 observed `businesstype` values.

**Address colocation — no threshold, no control, no exclusion list.** "Many recipients, one mail drop"
does not say how many, measured against what, or how to exclude commercial registered-agent addresses.
See Failure modes below: both omissions bit.

### Minimum data — accurate but materially understated.

Card says: *"instrument-level values + the statutory parameter history; registries for existence checks."*
The first and third clauses held. The middle clause is a phantom: **the platform holds no statutory
parameter history.** There is no cap table, no rate schedule, no dated-parameter dataset anywhere in the
repo; I supplied every cap value and every effective date from model knowledge, unverifiable against a
primary source without leaving the platform.

Five fields were load-bearing and none are listed:

| Field needed | Why | PPP column |
|---|---|---|
| entity/business type | decides whether registry absence is meaningful at all | `businesstype` |
| origination date | the *eligibility rule behind* the cap changed mid-program | `dateapproved` |
| originator | the cap's numeric *representation* is lender-specific | `originatinglender` |
| sector code | the second-draw cap is sector-conditional (3.5x for NAICS 72) | `naicscode` |
| address | the paired colocation test cannot run without it | `borroweraddress`, `borrowerzip` |
| draw discriminator | first vs second draw have different ceilings | `processingmethod` (PPP / PPS) |

### Ithildin mapping — two of three legs work; one factual error; one broken path.

| Card says | Reality |
|---|---|
| "PPP/EIDL DuckDB (cap clustering ran on this platform already)" | **PPP half correct, EIDL wrong.** `data/ppp_loans.parquet`, queried by `uv run python tools/query_ppp.py sql "..." --output "$WORKDIR/x.json"` — worked first try, sub-second on full scans. **No EIDL data is held**: `processingmethod` takes only `PPP` (8,523,060) and `PPS` (2,842,128); no EIDL file exists under `data/` or `datasets/`; `tools/query_ppp.py` never references EIDL. The card inherited the mislabel from `docs/modules/government.md`, whose section heading reads "query_ppp.py — PPP/EIDL Loans (DuckDB)". |
| "query_registry (nonexistence)" | Tool exists (`tools/query_registry.py` over `/Users/travcole/projects/osint-research/registry.db`, 7.1 GB) but has **no bulk or anti-join mode** — subcommands are `search / entity / officers / address / agent / filings / stats / jurisdictions / ucc-*`, all single-selector. A 15,481-name nonexistence check is not expressible; I had to write a DuckDB `ATTACH '<registry.db>' AS reg (TYPE sqlite, READ_ONLY)` join by hand. **Coverage constraint the card never states:** `query_registry.py jurisdictions` returns FL 5,993,885 entities, then NY 286, UK 41, VI 34, CO 29, DC 19, OH 16, and single digits for everything else. **Outside Florida this leg does not exist.** That, not runtime, is why the slice is FL. |
| "registry_address_index (colocation)" | **Misdescribed and currently broken.** `tools/registry_address_index.py` is a *builder/validator* (`build / status / validate / rollback`), not a query CLI. The query path is `query_registry.py address`, and it fails closed: `ERROR: Registry address index is stale relative to registry.db. Rebuild it with: uv run python tools/registry_address_index.py build --force`. Even `registry_address_index.py status` returns that same error. Rebuilding a 1.9 GB trigram FTS sidecar over 5.99 M entities was out of scope for a read-only validation run, so I fell back to direct read-only `sqlite3 "file:...registry.db?mode=ro"` LIKE scans (11–15 s each; there is no index on `principal_address`). Separately: the index is *registry-side*; PPP-to-PPP colocation needs no index at all, just a `GROUP BY` on the parquet. The card conflates the two uses. |

Also: three files are named `registry.db` — the real one at project root (7.1 GB), `data/registry.db`
(4,096 B), `datasets/registry.db` (0 B). The card's bare "query_registry" gives no way to know which.

### Failure modes — both listed warnings fired; the three that dominated the run are absent.

**Listed, and hit:**
- *"legitimate cap-seeking behavior (caps attract honest maximizers too)"* — this is the whole ballgame.
  The at-cap band is 11.7 % of the entire FL book (112,542 of 964,980). The card is right that "cluster
  shape and registry-absence distinguish," but see below: on this data neither actually did.
- *"parameter histories change (date the cap)"* — hit, and it is the sharpest single result. National
  first-draw at-cap share by approval month: 2.4 % (2020-04) → 4.2 % → 8.1 % → 10.6 % → 10.0 % (2020-08),
  then 30.6 % (2021-01), 20.5 %, 22.6 %, 31.3 %, **32.8 % (2021-05)**. A screen that pools the whole program
  compares two different eligibility regimes.

**Missing, and each one would have produced a false finding:**

1. **Registry-absence is dominated by name-linkage error, not by ghost status.** I built the control the
   card doesn't ask for: FL borrowers of *registerable* business types that are **not** at the cap — a
   population where absence should be near zero. **58.7 % of them are absent** from the FL registry
   (288,106 of 491,123) on exact normalized-name match. The at-cap registerable rate is 64.7 %
   (10,018 of 15,481). The screen's raw output is **59 points of matcher noise carrying 6 points of
   signal**. Card 2's failure mode — *"measure and disclose linkage error"* — is the mandatory companion
   here, and card 16 does not cross-reference it.
2. **Colocation is *anti*-correlated with cap clustering on this slice.** At-cap FL loans sitting at an
   address with >= 10 other at-cap loans: 185 of 112,274 = **0.16 %**. All FL loans at an address with
   >= 10 loans: 8,678 of 963,506 = **0.90 %**. The at-cap population is *less* colocated than the general
   population — because sole proprietors file from scattered home addresses while the general book contains
   real office towers. The card pairs the two tests as if mutually reinforcing; without the base rate an
   analyst reads "10 clusters found" as corroboration when the population-level signal points the other way.
3. **Registered-agent and virtual-office addresses.** The top at-cap cluster — 1317 EDGEWATER DR, Orlando
   32804, 67 at-cap loans, 42 distinct borrowers, 9 originating lenders — is an address hosting **3,787
   registered Florida entities**. It is a commercial agent address, not a scheme mail drop. Colocation
   without an agent-address exclusion nominates the agent industry first, every time.
4. **The cap's numeric representation is lender-specific.** FL at-cap loans by originator:
   Prestamos CDFI writes `20832.00` 10,715 times and `20833.00` 9 times; Harvest Small Business Finance
   writes `20833.00` 15,150 times and `20832.00` 137; Itria Ventures writes `20833.33` 1,775 times,
   `20833.00` 1,296, `20832.00` 543; Cross River splits 6,895 / 6,638. **Screening on a single literal
   makes the output a portrait of one lender's rounding rule** — searching only `$20,833` erases
   Prestamos CDFI's entire book.

---

## 2. FRICTION LOG

Every point where the card left me guessing, in the order I hit them.

1. **Cap value not derivable from the card.** "$20,833" is a rounding of `$100,000/12 x 2.5`. Neither the
   formula nor the `$100,000` per-employee compensation ceiling appears on the card; both came from
   knowledge, not from the platform.
2. **Which caps?** Card names one; I needed four (see Mechanics). The second-draw NAICS-72 3.5x cap
   `$29,166.67` was supplied from knowledge and then validated empirically against the data.
3. **Which amount column?** `initialapprovalamount` vs `currentapprovalamount` — card silent, and they
   differ (post-hoc reductions land in `current`). Chose `initial`, since that is the value the cap
   constrains at application. A different analyst would defensibly choose the other and get different counts.
4. **Draw discriminator undocumented.** The card says "first/second draw"; the field is `processingmethod`
   with codes `PPP` / `PPS`, documented nowhere in the card or in `docs/modules/government.md`.
5. **Point or band?** Had to invent the screening band `[20,800, 20,833.33]`. Choosing the point instead
   changes the FL count from 112,542 to 61,611.
6. **No mass-point threshold.** Invented an adjacent-bin ratio on 250-wide bins.
7. **"Registries that should contain them" has no rule.** Had to enumerate the 21 distinct `businesstype`
   values and hand-classify them into registerable / not.
8. **No join key, and the card never mentions this is the hard part.** PPP carries no EIN, no UEI, no
   state corp number. The only bridges to a registry are borrower name and address. The entire difficulty
   of the ghost check is the fuzzy join, and the card treats it as a lookup.
9. **The platform's name normalizer is not vectorizable.** `tools/entity_resolution.normalize_entity_name`
   is a row-wise Python function; to normalize 5,993,885 registry names against 112,542 borrower names I
   hand-ported its suffix list and regexes into DuckDB SQL. Divergence between the port and the original
   is unmeasured and is a hidden contributor to the 58.7 % baseline absence.
10. **Registry coverage is FL-only** — discovered only by running `query_registry.py jurisdictions`.
11. **`query_registry.py` has no bulk mode** (see mapping table).
12. **`query_registry.py address` fails closed on a stale index**; `registry_address_index.py status`
    returns the same error rather than a status.
13. **Three `registry.db` files**, two of them empty stubs.
14. **Result-envelope shape.** `query_ppp.py ... --output` writes
    `{"columns": [...], "total": N, "records": [...]}`, not a bare list. Two parse attempts failed before
    I inspected the envelope. Not a card defect, but it costs every first-time user the same two round trips.
15. **zsh currency-stripping papercut — hit by construction, and card 16 is the library's worst offender.**
    Verified live in this session:
    `/bin/zsh -c 'v="cap is $20,833.33 exactly"; echo "$v"'` prints `cap is ,833.33 exactly`.
    `$20` expands to the empty positional parameter and the digits vanish **silently** — no error, just a
    query against the wrong number. Card 16 is the only card in the library whose single named operational
    parameter is a bare dollar literal, so it is the card most likely to trigger this. Avoided here by
    using unformatted numeric literals in SQL and a quoted heredoc (`<<'MEMO_EOF'`) for this memo.
16. **EIDL claimed, not held** (see mapping table).
17. **Column-name casing.** `tools/query_ppp.py` `cmd_stats` reads `forgivenessAmount`; the parquet column
    is `forgivenessamount`. Harmless under DuckDB's case-insensitive resolution, a silent `None` if ported
    to a case-sensitive engine.

---

## 3. RESULT (secondary)

### National mass point — 11,365,188 loans

Top exact values, all draws:

| Draw | Amount | n |
|---|---:|---:|
| PPP | 20,833.00 | 519,891 |
| PPP | 20,832.00 | 380,405 |
| PPS | 20,833.00 | 188,382 |
| PPP | 20,800.00 | 96,894 |
| PPP | 20,000.00 | 68,744 |
| PPS | 20,832.00 | 64,792 |
| PPP | 20,833.33 | 58,432 |
| PPP | 20,833.32 | 49,335 |
| PPS | 20,833.33 | 18,714 |
| PPS | 29,166.00 | 10,078 |

Cap band `[20,800, 20,833.33]`: first draw 1,161,890 of 8,523,060 (13.6 %); second draw 333,828 of
2,842,128 (11.7 %). Loans above the applicable program ceiling: 0 in both draws.

First-draw shape, 250-wide bins (national):

| bin | n |
|---:|---:|
| 19,750 | 55,450 |
| 20,000 | 153,567 |
| 20,250 | 105,500 |
| 20,500 | 118,293 |
| **20,750** | **1,206,127** |
| 21,000 | 18,419 |
| 21,250 | 15,128 |

Spike ratio: 10.2x the bin below, **65.5x the bin above**.

At-cap share by approval month, first draw: 2020-04 2.4 %, 2020-05 4.2 %, 2020-06 8.1 %, 2020-07 10.6 %,
2020-08 10.0 %, 2021-01 30.6 %, 2021-02 20.5 %, 2021-03 22.6 %, 2021-04 31.3 %, 2021-05 32.8 %,
2021-06 27.9 %.

### Florida slice — 964,980 loans (716,053 first draw + 248,927 second)

- At-cap band: **112,542** (11.7 %). Exact `20,833.00` 61,611; `20,832.00` 34,109; `20,833.33` 3,268.
- Second-draw NAICS-72 band `[29,100, 29,166.67]`: 1,459, of which 1,381 (94.6 %) are NAICS 72.
- FL shape: 20,750 bin 119,278 vs 20,500 bin 20,216 (5.9x) and 21,000 bin 1,813 (**65.8x**).
- Impossible-value screen (a): **0** loans above the `$10 M` / `$2 M` ceilings. Derived-cap variant:
  **5,223** sole-prop/self-employed/IC loans with `jobsreported = 1` above `$20,833.33`, out of 438,615
  such single-job loans.
- At-cap composition: 97,056 non-registerable business types (86.2 %), 15,481 registerable (13.8 %), 5 null.
  Leading types: Sole Proprietorship 54,517; Self-Employed Individuals 21,635; Independent Contractors
  20,801; LLC 8,925; Corporation 3,277; S-Corp 1,599; Single Member LLC 1,308.

**Ghost check** vs 5,724,602 distinct normalized FL registry names:

| population | n | absent | % |
|---|---:|---:|---:|
| at-cap, registerable type | 15,481 | 10,018 | **64.7 %** |
| at-cap, non-registerable type | 97,056 | 92,829 | 95.6 % |
| **control: registerable, not at cap** | 491,123 | 288,106 | **58.7 %** |

Lift of the screen over its own control: **+6.0 pp**.

**Colocation** — 112,274 at-cap FL loans with usable addresses across 91,258 distinct addresses:

| loans per address | addresses | loans |
|---|---:|---:|
| 1 | 74,466 | 74,466 |
| 2 | 14,139 | 28,278 |
| 3–4 | 2,360 | 7,755 |
| 5–9 | 283 | 1,590 |
| 10–19 | 8 | 93 |
| 20–49 | 1 | 25 |
| 50+ | 1 | 67 |

At-cap loans at addresses with >= 10 at-cap loans: 185 (**0.16 %**). Base rate, all FL loans
(963,506 loans / 763,347 addresses): 8,678 (**0.90 %**).

Top clusters, with FL registry entity count at the same address:

| address | at-cap loans | names | lenders | window | total | registry entities at address |
|---|---:|---:|---:|---|---:|---:|
| 1317 EDGEWATER DR, Orlando 32804 | 67 | 42 | 9 | 2021-02-12 → 2021-05-26 | 1,395,804.66 | **3,787** |
| 540 NW 4TH AVE, Ft Lauderdale 33311 | 25 | 22 | 7 | 2020-06-08 → 2021-05-25 | 520,766.00 | 96 |
| 11211 S MILITARY TRL, Boynton Beach 33436 | 15 | 13 | 7 | 2021-02-12 → 2021-05-29 | 312,490.50 | 25 |
| 1100 BRICKELL BAY DR, Miami 33131 | 12 | 10 | 7 | 2021-02-19 → 2021-05-22 | 249,992.00 | — |
| 4444 S RIO GRANDE AVE, Orlando 32839 | 12 | 10 | 8 | 2021-02-10 → 2021-05-29 | 249,994.66 | 36 |

**Originator concentration** of the FL at-cap population (top 8, with mean `jobsreported`):
Harvest Small Business Finance 15,698 (1.00); Cross River Bank 15,240 (1.05); Prestamos CDFI 11,264 (1.00);
Capital Plus Financial 10,314 (1.00); Benworth Capital 8,183 (1.00); BSD Capital dba Lendistry 7,209 (1.00);
Fountainhead SBF 6,478 (1.00); Itria Ventures 5,226 (1.03).

**Rounding convention by originator** (FL at-cap): Prestamos CDFI 20,832.00 = 10,715 / 20,833.00 = 9;
Harvest 20,833.00 = 15,150 / 20,832.00 = 137; Itria 20,833.33 = 1,775 / 20,833.00 = 1,296 /
20,832.00 = 543; Cross River 20,833.00 = 6,895 / 20,832.00 = 6,638.

---

## 4. AMENDMENTS

### 4a. Card 16 — proposed replacement text

**Mechanics** (replace the existing paragraph):

> **Mechanics:** Legal instruments have hard parameters — contribution caps, benefit maxima, eligibility
> ceilings. Two screens, and which one is available depends on *where the cap is enforced*.
> (a) **impossible-value-vs-legal-limit** — only fires where the cap is *self-reported* rather than
> machine-enforced at entry: a wrapper whose observed contents could not have arisen from compliant inputs
> (`$5B` in a `$2K/yr` Roth) proves a non-market entry event without observing it. Where the cap is enforced
> at origination (PPP's E-Tran ceilings; most benefit-disbursement systems) this screen returns exactly
> zero and is not evidence of compliance. In those systems, substitute a **derived cap** — a ceiling that
> follows from a composite of held fields rather than from the program maximum (a one-employee Schedule C
> filer above `2.5 x $100,000/12`) — and treat exceedances as data-quality or eligibility-misstatement
> nominations, not as proof.
> (b) **benefit-cap-clustering** — mass points *near* statutory maxima betray inputs reverse-engineered from
> the cap. Screen a **band**, not a point: the observed mass sits at the filer's or the originator's
> rounding of the parameter, not at the parameter. Enumerate **every** parameter in the program, including
> the sector- and tranche-conditional ones, and screen each. Score the spike by its ratio to the adjacent
> bins on both sides, then decompose the at-cap population by originator, by entity type, and by month
> before interpreting it. Pair with **ghost-recipient checks** (recipients absent from the registries that
> *are legally required to contain their entity type* — filter to registerable forms first, and measure the
> matcher's own miss rate on a control population where absence is a priori unexpected) and
> **address-colocation** (many recipients, one drop — always against the colocation base rate of the full
> population, and always with commercial registered-agent addresses excluded).

**Minimum data** (replace):

> **Minimum data:** instrument-level values **plus, for each value, the fields that determine which
> parameter applies to it** — entity/beneficiary type, sector code, tranche/draw discriminator, origination
> date, and originator. The statutory parameter itself, **with its derivation and its effective-date
> range**, must be written down before the screen runs; the platform holds no cap table, so this is authored
> input. For the paired tests: a registry with bulk coverage of the relevant jurisdiction, an address field,
> and a control population for measuring match error.
>
> *PPP instantiation (verified):* `initialapprovalamount`, `processingmethod` (`PPP` = first draw,
> `PPS` = second), `businesstype`, `naicscode`, `dateapproved`, `originatinglender`, `borroweraddress`.
> Caps: first-draw ceiling `$10,000,000`; second-draw ceiling `$2,000,000`; sole-proprietor
> `$100,000/12 x 2.5 = $20,833.33` (both draws); second-draw NAICS-72 `$100,000/12 x 3.5 = $29,166.67`.
> Screen the band `[cap - 40, cap]`, not the point.

**Ithildin mapping** (replace):

> **Ithildin mapping:** `data/ppp_loans.parquet` via `tools/query_ppp.py sql "..." --output` — 11,365,188
> PPP/PPS loans, 2020-04 → 2021-07; full-scan aggregates run in under a second. **No EIDL data is held**
> (`processingmethod` is `PPP`/`PPS` only) — do not plan an EIDL leg without ingesting it first.
> `tools/query_registry.py` over the 7.1 GB `registry.db` **at the project root** (not the empty
> `data/registry.db` or `datasets/registry.db` stubs) for nonexistence — but it is single-selector only, so
> a bulk anti-join needs DuckDB `ATTACH '<root>/registry.db' AS reg (TYPE sqlite, READ_ONLY)`, and its bulk
> coverage is **Florida only** (5,993,885 entities; every other jurisdiction holds fewer than 300 rows).
> Recipient-to-recipient colocation needs no index — `GROUP BY` the normalized address on the parquet.
> Registry-side colocation goes through `query_registry.py address`, which fails closed when the
> `datasets/registry_address_search.db` sidecar is stale (`registry_address_index.py` is the *builder*, not
> a query CLI); the fallback is a read-only `sqlite3` LIKE scan, ~15 s and unindexed.
> Generalizes to ERTC, FEMA IA, crop insurance, state relief. GAP: a dated statutory-parameter table.

**Failure modes** (replace):

> **Failure modes:** legitimate cap-seeking behaviour — caps attract honest maximizers, and on PPP the
> at-cap band is ~12 % of the entire book, so the cluster's *existence* is not the finding. Parameter
> histories change: date the cap and cut the screen by period (PPP's first-draw at-cap share ran 2.4 % in
> 2020-04 and 32.8 % in 2021-05 — two eligibility regimes in one file). **Rounding is per-originator**:
> `$20,833.00`, `$20,832.00` and `$20,833.33` are the same cap seen through three lenders' arithmetic, and
> screening one literal silently selects one lender's book. **Registry absence is mostly matcher error, not
> ghost status** — on a control population that must legally be registered, exact normalized-name matching
> still reports 58.7 % absent, so the screen's raw absence rate is uninterpretable without that control
> (see card 2's linkage-error discipline). **Colocation needs its own base rate and a registered-agent
> exclusion**: at-cap PPP loans are *less* colocated than the general population (0.16 % vs 0.90 % at
> addresses with >= 10 loans), and the single largest cluster resolves to a commercial agent address
> hosting 3,787 registered entities.

### 4b. Library-schema amendment

**Add a `**Control:**` field to every card**, between *Minimum data* and *Ithildin mapping*: the
null-hypothesis population the screen's output must be measured against, and how to construct it from the
same held data.

This card produced three numbers that read as findings and were not, and in each case the fix was the same
missing field:

- "95.6 % of at-cap recipients are absent from the corporate registry" → control says the expected absence
  for that entity type is ~100 %.
- "64.7 % of registerable at-cap recipients are ghosts" → control says 58.7 % of definitely-real ones are
  too; true lift is 6 pp.
- "10 colocation clusters found" → control says the population is *less* colocated than baseline.

The field generalizes beyond card 16: cards 3, 5, 14, 21 and 29 all emit rates or outlier counts whose
meaning is entirely determined by a comparison the card currently leaves to the analyst's discretion.
Proposed wording for card 16's instance:

> **Control:** the same screen run on a matched population where the signal should be absent — for cap
> clustering, the same entity types outside the cap band; for the registry check, entities whose type is
> legally required to be registered but which are *not* at the cap (this measures the matcher, not the
> subject); for colocation, the colocation distribution of the full jurisdiction. Report the screen's lift
> over its control, never its raw rate.

*Secondary (card-format convention, not a field):* any card that names a numeric parameter should carry its
**derivation** alongside the value, and dollar literals in card text should be written so they are not
pasted into a shell — under zsh, `"$20,833.33"` silently becomes `,833.33`. Card 16 is the library's most
exposed card on this point.

---

## 5. VERDICT

**needs-amendment.**

The card is genuinely executable: all three legs ran end-to-end against held data in 8.3 seconds, and the
central claim is emphatically confirmed — the PPP first-draw distribution carries a mass point 65x the
density of the adjacent bin above it, exactly where the card says to look. That is a real, reproducible
signature, and the card earned its place. But as written, two of its three legs produce output that a
competent analyst would misread. The ghost-recipient check without a registerable-entity-type filter reports
a 95.6 % ghost rate that is pure artifact, and even correctly filtered its raw 64.7 % absence is 58.7 %
matcher error; the colocation check without a base rate and an agent-address exclusion nominates a
registered-agent office with 3,787 tenants as its top hit, on a population that is in fact *less* colocated
than baseline. The card also carries one factual mapping error (EIDL is not held), one broken tool path
(the address index is stale and `query_registry.py address` fails closed), one unstated hard constraint (the
registry has bulk coverage for Florida only, which is what actually bounds the slice — not runtime), and a
single named parameter that is both rounded and incomplete, and that the platform's own documented zsh
papercut will silently corrupt if pasted into a shell. None of these is fatal to the pattern; all are fatal
to a first-time analyst running the card literally. Amend the Mechanics, Minimum data, Ithildin mapping and
Failure modes as drafted above, add the `Control` field library-wide, and the card becomes
operational-as-is.
