# Card 15 validation — `entity-genealogy-screen (age, formation, first-filing)`

**Card under test:** `research/patterns/detection-signatures.md` lines 278-291
**Test data:** `investigations/tech-right/reports/2026-07-28-dhs-census/` (2026-07-28 DHS procurement census)
**Slice:** 18 DHS awardees — 14 census-S4-flagged zero-history vendors (group A) + 4 established wall/aviation
incumbents as controls (group B: Fisher, Barnard, CSI Aviation, Sundt).
**Live calls:** 21 FPDS ATOM queries, 6 unified-registry, 2 Delaware, 2 Texas, 1 Wyoming, 2 GLEIF.
**DB writes:** none. No tracker commands run. `investigation.db` never opened.

---

## 1. EXECUTABILITY, field by field

### Observed — *not assessed* (out of scope; the corpus support is 4 story-uses / 2 clusters)

### Mechanics — **partially sufficient. Three of four named screens are under-specified, and the
one that dominated the held data is not in the card at all.**

The card names four screens. Against this slice:

| screen | executable? | notes |
|---|---|---|
| **first-time-vendor flag** | YES — cleanly | The workhorse. 14/14 group A confirmed, 0/4 group B. See §3. |
| **formation-date-vs-award-date under 90 days** | YES but near-empty | Fires on **1 of 12** vendors that had a formation date. |
| **new-entity-first-filing-watch** | N/A here | 990/trust-shaped; no nonprofit leg in a procurement slice. Not a defect — but the card gives no signal that three of its four screens are domain-specific. |
| **officer-succession-registry-diff** | NOT REACHED | Requires time-series registry snapshots. Neither `query_registry` nor the per-state adapters expose a filing-history diff for the states in this slice. |

**The missing screen.** The card's only age test is a *short* gap (<90 days). In the held data the productive
shape is the **opposite**: 6 of 12 vendors with a known formation date were formed **more than three years**
before their first federal contract action (median gap across the cohort = **1,183 days / 3.2 years**). Compass
United was formed 2000-10-02 and took its first federal prime action 2026-06-16 — a 9,388-day gap, against a
$2.34B ceiling sum. Security Insights: 2,561 days. Maverick Strategies: 1,372. Septimo: 1,183. Rauma: 4,298.
SLS Federal: 1,887. A dormant, aged, clean-registry shell is *better* tradecraft than a fresh one and it is
invisible to every screen the card lists. The <90-day flag caught **8%** of the flagged cohort; a
dormancy-then-activation flag would have caught **50%**.

**"Cross-tab with sole-source/urgency codes" — executable, and it is the step that does the actual work,
but NOT via the tool the card names.** `tools/query_fpds.py` does not parse competition data at all: `_parse_entry`
(lines 119-198) extracts dates, dollars, vendor, PSC, NAICS and the workflow/approval fields, and **no**
`extentCompeted`, `solicitationProcedures`, `numberOfOffersReceived`, or `otherThanFullAndOpenCompetition`.
The cross-tab had to be run off `census-awards.csv` (USASpending-derived). It was worth running — it is the
single most discriminating move in the whole card:

- 4 of 14 carry **URGENCY (FAR 6.302-2)** awards — SLS Federal, Salus, Daedalus, Safe America Media
- 2 of 14 carry **PUBLIC INTEREST (FAR 6.302-7)** — Rauma, Davie Defense (the ICE-Pact icebreaker yards; the
  census already reads these as explainable market entries, and the OTFO code corroborates that read)
- **8 of 14 carry no OTFO code and zero urgency actions** — the UAC-family IDIQ holders and the JV shells

So the cross-tab splits a flat 14-vendor "new entrant" list into 4 anomalous / 2 explained / 8 competed-vehicle.
Without it, the first-time-vendor flag alone is close to useless at this base rate. The card states this
correctly in principle ("the flag nominates, the principal's history convicts") but files the cross-tab as a
trailing clause rather than as a required second stage.

### Minimum data — **accurate but incomplete on one axis.**

"the award/filing stream + incorporation registry with dates; principal-resolvable metadata" is right as far as
it goes. Two omissions the run exposed:

1. **A denominator/base-rate leg is missing.** A first-time-vendor flag is meaningless without knowing how many
   first-time vendors a normal DHS quarter produces. The census supplies this; the card does not ask for it.
2. **"principal-resolvable metadata" is the load-bearing input and the card treats it as an afterthought.** The
   single highest-value result in this run came from officer data (see §3, SLS Federal / John Sullivan) — and no
   tool the card names returns officers.

### Ithildin mapping — **the FPDS half is right; the registry half is wrong for this slice.**

Commands that **worked**:

```
uv run python tools/query_fpds.py search 'VENDOR_UEI:"KE7ZAT98UBM7"' --max-pages 15 --output "$WORKDIR/f.json"
uv run python tools/query_fpds.py search 'VENDOR_UEI:"X" SIGNED_DATE:[2004/01/01,2024/11/04]' --output ...
uv run python tools/query_fpds.py search 'VENDOR_NAME:"FISHER SAND"' --max-pages 6 --output ...
uv run python tools/query_texas.py search "SLS FEDERAL" --output ...
uv run python tools/query_texas.py entity 32075978828 --output ...        # returns formation date + officers
uv run python tools/query_wyoming.py search "Salus Worldwide" --output ... # Node helper cleared the F5 WAF
```

Commands that **failed**:

```
uv run python tools/query_registry.py search "DAEDALUS AVIATION" --output ...   # 0 results (x6 entities)
uv run python tools/query_delaware.py search "Daedalus Aviation" --output ...
  -> ERROR: OpenCorporates rejected OPENCORPORATES_API_KEY (HTTP 401). [stale token]
uv run python tools/query_gleif.py search "Daedalus Aviation" --output ...
  -> 1 result: "Daedalus Aviation Group B.V.", Tilburg NL — wrong-country name collision, not the DE corp
uv run python tools/query_gleif.py search "Salus Worldwide" --output ...       # 0 results
```

Three concrete mapping defects:

**(a) `query_registry` is the wrong tool and the card names only it.** `query_registry.py jurisdictions` on this
machine: FL 5,993,885 · NY 286 · UK 41 · VI 34 · CO 29 · DC 19 · OH 16 · **TX 6** · PA 5 · NM 3 · **WY 2** · CA/MA/MI/NJ 1 each.
**Delaware, Virginia, Maryland, Tennessee and Washington are absent entirely.** Those five states cover 9 of the
14 flagged vendors. `query_registry` returned 0 results on all 6 lookups. The formation-date leg only ran because
I routed around the card to `query_texas.py` and `query_wyoming.py`, which the card does not mention. The card
should name the **routing rule**, not a single tool.

**(b) GLEIF is not a formation-date source and the card implies it is.** "GLEIF/OpenCorporates for lifecycle
data" reads as one fallback pair. GLEIF LEI records carry LEI-registration dates and `registeredAs`, not
incorporation dates, and coverage of small US LLCs is near zero — 1 of 2 lookups returned a same-name Dutch B.V.
that an unwary run would have adopted. OpenCorporates is the real fallback and it is **currently 401**.

**(c) `query_fpds.py` silently drops every IDV entry.** The FPDS ATOM feed carries two payload roots,
`<ns1:award>` and `<ns1:IDV>` (verified against raw XML: 27 `award` / 2 `IDV` on one Fisher page). `_parse_entry`
only descends into `award`, so every IDV action returns **all-null except `title`** — no PIID, no signed date,
no obligation, no NAICS. In this slice: **59 of 586 rows (10.1%)** parsed to null; **23 in group A**; **11 of 14
group-A vendors affected**. For six of them the null row *is* the flagship instrument:

```
New IDC 70CDCR26D00000045 awarded to SAVVY PROFESSOR LLC for the amount of $0     <- the $1.596B UAC IDIQ
New IDC 70CDCR26D00000033 awarded to COMPASS UNITED for the amount of $0
New IDC 70CDCR26D00000043 awarded to SEPTIMO SOLUTIONS, LLC for the amount of $0
```

This is directly adverse to card 15: a vendor whose only pre-window federal presence is an IDV base award parses
as *no dated history at all*, i.e. a **manufactured first-time-vendor true-positive**. It did not flip any flag
here (the census's independent USASpending leg agreed), but the mechanism is live and would bite a
FPDS-only run.

**(d) Silent paging truncation.** 3 of 4 controls returned exactly **150 = 15 pages x 10**, the `--max-pages`
cap, with no truncation signal in the output. A run that treats "earliest signed_date in the returned set" as
the vendor's true first action will get a wrong answer for any vendor above the cap. (Group A was safe — all
under 35 actions — and Fisher's 46 was verified stable at `--max-pages` 5 and 25, so the feed does terminate
honestly when it is short.)

### Failure modes — **both named modes are real and I hit both; but the card misses the one that
actually breaks the screen.**

**"Subsidiaries of experienced parents look new" — HIT, and confirmed to primary source.** SLS Federal Services
LLC ($2.38B obligated, flagged zero-history) resolves via `query_texas.py entity 32075978828` to: TX SOS
registration **09/21/2020**, file 0803767906, mailing address **6702 Broadway St, Galveston TX**, registered
agent InCorp Services, **manager JOHN SULLIVAN**. That is the Sullivan Land Services / SLSCO family — the
Galveston border-wall incumbent. The census hypothesised this; the officer record confirms it. The card's
warning is correct and the disconfirming evidence was one CLI call away.

**"Emergency contexts legitimately produce new vendors" — HIT.** Rauma Marine (Finland) and Davie Defense
(Canada) are ICE-Pact icebreaker yards registering US entities; both carry FAR 6.302-7 PUBLIC INTEREST rather
than urgency. Correctly nominated, correctly acquitted.

**"Shelf companies defeat naive formation dates" — HALF-RIGHT.** The card frames shelf companies as a
*false-negative* problem (an aged shell hides newness). The held data shows the aged-shell shape is the
**dominant true signal**, not the evasion: 6 of 12: old formation + zero federal history + large ceilings. The
card tells you to distrust the aged entity; it does not tell you to *screen for* it.

**MISSING failure mode — identifier multiplicity. This is the one that breaks the screen.** One legal entity can
hold multiple UEIs with non-overlapping eras. Demonstrated on a control:

```
FISHER SAND & GRAVEL CO.
  DGT8NKKG9NR3   n=21   1982-06-15 -> 2024-03-01    21 pre-window actions
  XAVBDA4D13N7   n=33   2023-07-17 -> 2026-07-27     3 pre-window actions
```

Same name, two UEIs, a clean 2023-24 handover. A UEI-keyed zero-history flag run on `XAVBDA4D13N7` sees a vendor
with 3 pre-window actions and a 2023 origin; the 42 years of history sit under the other UEI and are invisible.
Fisher survived only because the handover happened to straddle the window. Six months later and a
44-year-old incumbent is a clean **false positive**. `VENDOR_NAME:"FISHER SAND"` recovers both. The card says
nothing about this and neither does its "Minimum data" line.

(Note: the related worry that FPDS `VENDOR_UEI` cannot reach DUNS-era records is **refuted** — FPDS backfilled
UEIs onto legacy rows; Barnard resolves to 1985-04-15, Sundt to 1984-04-15, CSI Aviation to 1993-04-15. Those
pre-2004 legacy rows do carry a **day-of-month = 15 placeholder**, so their date precision is month, not day.)

---

## 2. FRICTION LOG — where the card left me guessing

1. **Which formation date?** The card says "formation-date" without saying whether that means state-of-incorporation
   date, SAM `entityStartDate`, or SAM registration date. These differ: Rauma's SAM registration is 2025-09-10
   but its entity start is 2014-03-21 — an 11-year spread that decides whether it is "new". I used SAM entity
   start and cross-checked three against state registries; all three matched exactly (Salus WY filed 02/07/2023 =
   SAM 20230207; Compass United TX 10/02/2000 = SAM 20001002; SLS TX 09/21/2020 = SAM 20200921). That the two
   agree is a *finding of this run*, not something the card told me I could rely on.
2. **<90 days from what event?** Award date, first *action* date, solicitation date, or SAM registration? Safe
   America Media is 13 days on formation→first-FPDS-action, but 4 days on formation→SAM registration, and its
   task orders land months later. Different choices move it across the threshold.
3. **Where does 90 come from?** No provenance. It fires on 1 of 12 here. Nothing in the card says whether 90 is
   a ProPublica-inherited constant, a platform default, or illustrative.
4. **How far back is "zero prior history"?** The card says "zero prior history" with no lookback bound. FPDS-NG
   reaches ~1978 with degraded precision; the census chose 2007-10-01. Unstated, so unreproducible.
5. **UEI vs DUNS vs CAGE vs name.** Not addressed at all — and per §1 this is the failure mode most likely to
   produce a wrong answer.
6. **Registry routing.** The card names `query_registry`, which is a local index with no coverage for 5 of the 6
   states in this cohort. Nothing tells you the real path is per-state adapters with per-state gating.
7. **What counts as "zero" when the parser returns nulls.** No instruction on how to treat unparsed rows. The
   naive read (null = no history) is exactly backwards.
8. **Credential/CAPTCHA expectations.** DE needs a live OpenCorporates key (currently 401). WY needs a Node
   browser helper through an F5 WAF (worked unattended). MD needs manual reCAPTCHA. VA has no adapter at all.
   The card gives no cost model, so you cannot scope a run before starting it.
9. **`census.db` is referenced but not persisted.** `census-report.md` lists `census.db`, `raw/`, `enrich_state.json`
   and the job-provenance files under Deliverables; only the CSVs and `scripts/` are on disk. Not a card defect —
   flagging it because a future card-15 run following that report will look for a database that is not there.

---

## 3. RESULT (secondary — counts only, no leads/findings created)

**Slice:** 18 DHS awardees. Window boundary 2024-11-05 (census convention).

| measure | count |
|---|---|
| FPDS actions retrieved | 586 across 18 vendors |
| Group A (census-flagged) confirmed **zero pre-window FPDS actions** | **14 / 14** |
| Group B (controls) with pre-window FPDS history | **4 / 4** (0 false positives) |
| Concordance with the census's independent USASpending-derived flag | **18 / 18** |
| Rows lost to the IDV parse defect | 59 / 586 (10.1%); 23 in group A; 11 of 14 vendors |
| Controls silently truncated at the paging cap | 3 / 4 (exactly 150 rows each) |
| Group A with a usable formation date | 12 / 14 (2 absent from the local SAM extract) |
| Formation→first-award gap **< 90 days** | **1 / 12** (Safe America Media, 13 days) |
| Formation→first-award gap < 1 year | 2 / 12 |
| Formation→first-award gap **> 3 years** (dormancy) | **6 / 12**; median cohort gap 1,183 days |
| Vendors with ≥1 **URGENCY (FAR 6.302-2)** award | 4 / 14 |
| Vendors with **PUBLIC INTEREST (FAR 6.302-7)** | 2 / 14 |
| Vendors with no OTFO code and zero urgency | 8 / 14 |
| Entities with a **second UEI** carrying the older history | 1 confirmed (Fisher: 2 UEIs, 1982-2024 / 2023-2026) |

**Registry lookups: 3 succeeded, 8 blocked or empty, of 11 attempted.**

| route | outcome |
|---|---|
| `query_registry` (the tool the card names) | **0 / 6** — no DE/VA/MD/TN/WA coverage; TX has 6 entities, WY has 2 |
| `query_texas` | **2 / 2 success** — formation date, file number, agent **and officers** |
| `query_wyoming` | **1 / 1 success** — Node helper cleared the F5 WAF/CAPTCHA unattended |
| `query_delaware` | **0 / 2 — HARD BLOCK**, HTTP 401, stale `OPENCORPORATES_API_KEY` |
| `query_gleif` | 0 / 2 usable — one empty, one wrong-country name collision |
| Virginia (Septimo, Savvy Professor) | **no adapter exists** |

Blocked-state exposure: **DE, VA, MD** — 9 of the 14 flagged vendors sit in states this platform cannot
currently reach for formation data.

Three formation dates independently corroborated against state primaries (SLS/TX, Compass United/TX,
Salus/WY); all three matched SAM entity-start to the day.

---

## 4. AMENDMENTS

### 4a. Card 15 — proposed replacement text

**Mechanics** (replace lines 280-284):

> **Mechanics:** An entity's registry lifecycle is a fraud clock, and it runs in both directions. Screens:
> award recipients whose identifier has zero prior history (**first-time-vendor flag**); **formation-date-vs-
> award-date** — flag both tails, a short gap (a fresh entity, illustratively <90 days, date the threshold to
> the program) and, more productively at procurement base rates, a **dormancy gap** (an entity aged >3 years
> with zero prior federal history, then a large ceiling — the aged shell is better tradecraft than the fresh
> one); **new-entity-first-filing-watch** (a new trust/nonprofit whose *first* filing shows 8-10-figure revenue
> matching a contemporaneous M&A deal); **officer-succession-registry-diff** (control handoffs timed against
> corporate events). State the lookback bound and which date you are using (state incorporation vs SAM
> entity-start vs SAM registration — they diverge by years). The flag alone is near-useless at DHS base rates:
> **the required second stage is the cross-tab** against sole-source/urgency authority, offers-received and
> category mismatch, which sorts nominees into anomalous, explained-by-authority, and ordinary competed-vehicle
> winners.

**Minimum data** (replace line 285):

> **Minimum data:** the award/filing stream with a stated lookback + incorporation registry with dates + a
> base-rate denominator (how many first-time vendors a normal period produces) + **officer-of-record data**,
> which is what actually resolves a nominee. All identifiers the entity has used, not one.

**Ithildin mapping** (replace lines 286-287):

> **Ithildin mapping:** `query_fpds search 'VENDOR_UEI:"..."' --output` for the history leg (note: it returns no
> competition fields — take extent-competed/offers/OTFO from `query_usaspending` or a census extract, and it
> drops `<IDV>` entries to nulls, so re-read titles before scoring a zero). Registry leg **routes by state**:
> `query_texas` (keyless, returns formation date + officers), `query_wyoming` (Node browser helper, F5 WAF),
> `query_delaware`/`query_opencorporates` (needs a live OPENCORPORATES_API_KEY), `ingest_maryland` (manual
> reCAPTCHA), `ingest_florida`/`ingest_newyork`/`ingest_colorado`/`ingest_dc` (bulk, already local). `query_registry`
> only searches jurisdictions already ingested — check `query_registry jurisdictions` before assuming coverage;
> **VA has no adapter**. GLEIF gives LEI-registration dates, not incorporation dates, and name-collides across
> countries — do not use it as a formation-date source. `query_990` first-filings for the nonprofit variant.

**Failure modes** (replace lines 288-289):

> **Failure modes:** **identifier multiplicity is the primary false-positive engine** — one entity can hold
> several UEIs with non-overlapping eras (verified: Fisher Sand & Gravel, DGT8NKKG9NR3 1982-2024 alongside
> XAVBDA4D13N7 2023-2026), so re-run every zero-history hit on `VENDOR_NAME` and on the parent UEI before it
> counts; JV shells and new subsidiaries of experienced parents look new (officer-of-record disproves it in one
> call — SLS Federal's TX manager is John Sullivan of the Galveston SLSCO wall family); shelf companies defeat
> naive formation dates *and* are themselves a signal; emergency and treaty contexts legitimately produce new
> vendors (FAR 6.302-7 PUBLIC INTEREST distinguishes these from 6.302-2 URGENCY); parser nulls and silent paging
> truncation both manufacture false "zero history". The flag nominates, the principal's history convicts.

### 4b. Library-schema amendment

The card format has no field for **what the move costs to run**. Card 15 is the case that proves the need: its
mechanics are sound, but 9 of 14 nominees sat in states that are credential-gated, CAPTCHA-gated, or have no
adapter — and nothing in the card format could have told me that before I started. Add one line to the card
schema, documented in "How to read a card":

> *Preconditions* = credentials, CAPTCHA/browser-helper dependencies, jurisdictional coverage limits, and
> known-stale adapters that gate this move. "BLOCKED:" marks a currently-unavailable leg.

For card 15 that line would read:

> **Preconditions:** FPDS and `query_texas` keyless. `query_wyoming`/`query_tennessee_corps`/`query_nevada` need
> the Node browser helper. **BLOCKED:** `query_delaware`/`query_opencorporates`/`query_hongkong`/`query_cyprus`
> — OPENCORPORATES_API_KEY returns HTTP 401 as of 2026-07-29. `ingest_maryland` needs manual reCAPTCHA. No
> Virginia adapter exists.

Second, smaller: three of card 15's four screens are domain-specific (procurement vs nonprofit/trust). The
"How to read a card" header explains *Observed / Mechanics / Minimum data / Ithildin mapping / Failure modes*
but gives no convention for marking a screen as domain-scoped. A `[procurement]` / `[nonprofit]` tag on
individual screens inside a multi-screen card would have saved a wasted look for the first-filing leg.

### 4c. Two platform defects worth spinning off (not card edits)

1. `tools/query_fpds.py::_parse_entry` must handle the `<ns1:IDV>` payload root as well as `<ns1:award>`.
   10.1% of rows in this slice were lost, including six flagship IDIQs.
2. `tools/query_fpds.py` should signal when `--max-pages` truncated the feed. Three of four controls hit the
   cap silently at exactly 150 rows.

---

## 5. VERDICT

**needs-amendment.** The card's core move is real and it works: the first-time-vendor flag ran cleanly on live
FPDS, agreed with the census's independently-derived USASpending flag on 18 of 18 vendors, produced zero false
positives against four established-incumbent controls, and the cross-tab against urgency authority did genuine
analytic work — sorting a flat 14-vendor list into 4 anomalous, 2 treaty-explained and 8 ordinary competed-vehicle
winners. That is a usable pattern. But three things must change before the card can be handed to an agent as
written. First, its named threshold is aimed at the wrong tail: the <90-day screen fired on 1 of 12, while the
dormancy shape the card never mentions fired on 6 of 12 at a median 3.2-year gap. Second, the Ithildin mapping
sends you to `query_registry` for the formation leg, which returned 0 results on all 6 lookups because Delaware,
Virginia, Maryland, Tennessee and Washington are simply not ingested — the leg only ran because I routed around
the card to per-state adapters it does not name, and Delaware is hard-blocked on a stale OpenCorporates token
regardless. Third, and most seriously, the card omits the failure mode most likely to produce a wrong answer:
identifier multiplicity, demonstrated here on a control where a 44-year incumbent's history splits across two
UEIs with a clean handover, so that a UEI-keyed zero-history flag would have called Fisher Sand & Gravel a new
entrant on a slightly different window boundary. With the amendments in §4 — both-tails age screen, state-routed
registry mapping with a Preconditions field, and an identifier-multiplicity warning — this is operational.
Without them an agent will produce confident false positives and will not know which of its blank registry
lookups were real negatives.
