# Epstein Reporting Corpus — Exploration & Synthesis (2026-07-13)

Consolidated read of the newly built reporting knowledge layer
(`datasets/epstein_reporting.db`, 7,775 articles / 6,759 full-text, 386
publishers, 26 languages). Eight parallel agents swept it: six Claude Fable 5
content lenses + two Codex `gpt-5.6-sol` meta-layer agents (integrity audit +
claims-pipeline bootstrap). Per-lens worksheets were captured to a scratch
workdir; this file is the durable synthesis.

**Evidence discipline:** reporting is SECONDARY. Nothing here is a finding.
Every item is a recommendation for primary-source work. Multiple outlets
repeating one filing = one source, not corroboration.

---

## Trust caveats (read first)

1. **Reporting ≠ corroboration.** The corpus's job is to tell us *which vein of
   our 1.42M-page primary corpus to mine*, not to supply facts. Nearly all 2026
   coverage is release-driven off datasets we already hold in full (DS9-11).
2. **Profile-scoping trap.** The active profile was `richard-merkin` during the
   sweep, so `findings_tracker.py search` returned FALSE NEGATIVES on the 5,148
   epstein findings. Use `--profile epstein` / `--all-profiles`, or query
   `findings_fts` directly. Two agents self-corrected mid-run; verify any
   "absent from findings" claim before acting.
3. **Corpus is "discovery-grade, not measurement-grade"** (Codex integrity
   audit, complete). DB integrity is sound (all 7,775 current-version pointers
   valid, FKs pass). But: `independence_group` is unusable as an independence
   measure (6 syndication families = 41 items collapsing to ~6 original reports;
   double-counting risk is real). ≥18.7% of non-NULL current text is extraction
   junk / AV stubs; 97.3% of `broadcast_transcript` rows have no transcript.
   Direct-scope pollution floor 3.1% (234 items); 40/42 pre-2005 rows are
   wrong-person NRC surname collisions (the 1938 date is genuine but off-topic).
   Coverage skews NBC/CBS/Guardian and the 2024-2026 release era.
   **Query-hygiene bug:** SQLite `date(published_at)` silently drops 398 dated
   rows — filter on `published_at` string ranges, not `date()`.

   **Coverage holes (fill targets):** present = NY Mag 2002, Vanity Fair 2003,
   Palm Beach Post 2006-08, Guardian Andrew arc. Partial = Miami Herald series
   (35/36 records lack article text). MISSING = NYT/Landon Thomas 2008-19, WSJ
   2023 + 2025-26 bank series, FT, most Bloomberg, Vicky Ward 2015 Daily Beast,
   historic BBC, Farrow/New Yorker, Mother Jones, books/podcasts. 70 of the 439
   failed candidates are valuable pre-2024 recovery targets. Codex produced a
   PROPOSED-ONLY fill plan (seed adds, recover-archives, Wayback, licensed-DB
   queries) — see `report-codex-integrity.md`.

---

## The headline: four lenses independently converged

Financial, genealogy, entity-gaps, and 2026-threads agents — four methods —
all surfaced the **April–July 2019 banking sprint** as the top untold story:

- As Deutsche Bank pushed Epstein out, **Fidelity and Charles Schwab both opened
  accounts in April 2019**; money routed through Banco Popular / FirstBank
  Puerto Rico to **Interactive Brokers** days before arrest.
- His dormant USVI bank, **Southern Country International**, reactivated to move
  ~$45M around his death (~$20M Apr-Jul 2019, ~$25M post-death), including a
  **$15M Deutsche→Southern Country wire the day after death** that drew a
  wire-fraud probe (opened 2020, closed 2024, unexplained).
- **We hold the wire-level primary documents** the reporting only gestures at.

When four blind searches hit the same coordinates, that is the signal. This is
the flagship story candidate and fits the investigation's financial-mapping
priority.

---

## New mental models to carry forward

1. **Reporting is a treasure map, not the treasure.** Highest use = pointing to
   which released-document vein to dig. Reporters sampled; we hold the whole
   corpus and can dig deeper than they could.
2. **The delta runs both directions — including against ourselves.** Auditing
   reporting vs. primary evidence is also a QA pass on our own database (it
   found real defects in our findings — see below).
3. **Where we beat the press is itself a story.** We answer the "$13M mystery"
   prosecutors litigated in open court; our Valar/Thiel figure is 2.3× NYT's; we
   hold the signed $25M Rothschild contract Drop Site described secondhand.
4. **Pre-dating reveals sourcing channels.** Reporting that asserted a fact
   before the confirming document was released maps the leak/plant channels
   (WSJ/NYT estate-archive pipeline; UK-tabloid mailbox; proffer-counsel).
5. **Each country's press excavates its own nationals.** French, German-Austrian,
   Norwegian, Argentine desks run deeper *separate* investigations invisible in
   English. The non-English layer is original reporting, not translation.

---

## Things to update on

### A. Defects in our OWN findings (independently verified against investigation.db)

| Finding | Defect | Verified? | Action |
|---|---|---|---|
| **#2403** | Summary reads "paid Ehud Barak **.3 million**" — truncated "$2.3M" | CONFIRMED (self-evident truncation; ToI evidence URL says $2.3M) | CORRECT figure |
| **#2** | "**M paid** by Leon Black" (truncated "$158M") + "**Deveraux** report" | CONFIRMED — Apollo's reviewer was **Dechert LLP**; "Deveraux" is wrong | CORRECT name + restore amount |
| **#2940** | Claims Kaplan presided over *Giuffre v. Maxwell* + *USVI v. JPMorgan* | CONFIRMED misattribution — Kaplan handled *Giuffre v. Andrew*; JPM = **Rakoff**; whole synthesis rests on wrong assignments | DISPUTE (then rebuild if any structural point survives) |
| **#11** (Ruemmler) | "successor Executor / trustee" may be from superseded instruments | NOT SAFE on reporting alone — finding is `confirmed` direct-quote from EFTA docs; needs will-version reconciliation | HOLD → primary check |
| **#639** (1953 Trust) | Labels EFTA00016865 "the Last Will"; may be an earlier version | NOT SAFE on reporting alone — same will-version question | HOLD → primary check |
| **#1567** (Staley/Sal Oppenheim) | Agent flagged "date mismatch" | NO DEFECT FOUND — solid `confirmed` direct-quote | LEAVE AS-IS |

The #11/#639 pair both hinge on **which Epstein will/trust version is
operative** (the Aug 8 2019 signed will vs. earlier drafts). Resolve that once,
against kabass/DOJ primary docs, then correct both together.

### B. Enrichment clusters (reporting adds precise dates/amounts/names)

- **Black fee reconciliation:** $148M+ (our 21 Bates-numbered wires) / $158M
  (Dechert) / $170M (Senate Finance) / ~$202M Exhibit-A gross / $95M
  Black's claimed "net." Our ledger can arbitrate what each figure counts. Add
  the **$62.5M USVI settlement** (criminal-immunity scope flag) to #37.
- **Settlement ledger (no findings yet):** JPM-victims **$290M** (Rakoff, Jun
  2023); JPM-USVI **$75M** (Sep 2023); **BofA $72.5M** (Mar 2026); DB-victims
  **$75M** (May 2023); estate **$35M** (Feb 2026). Add as medium, upgrade via
  dockets.
- **JPMorgan 2019 SAR** (unsealed Oct 2025): ~4,700 transactions / >$1B, Russian
  bank wires, $65M Wexner-trust circuit — almost entirely absent from our data.
- **Deutsche Bank consent-order timeline** (#322/#596/#3251/#3183): annotate
  "per consent order" — DOJ-file emails show accounts open until Jul 9 2019, not
  Dec 2018 (potential false-filing exposure; our #1592 independently shows Apr
  2019 activity).
- **Butterfly Trust** (#312/#339): 120+ wires/$2.65M, 97×$7,500 structured cash
  withdrawals, Dec 2014 Maxwell→Shuliak beneficiary swap, Marrakech $23M palace
  bid + Oldfield "redact the financials" email (§1344 angle).
- **Paul Barrett** (#68/#324/#1293): reframe from "JPM MD" to Epstein's
  **in-house trader** running "Alpha Group" RIA — JPM→Epstein-org move.

---

## Connections & entities we didn't have

- **The private-banking "servicing desk," fully named** (Fortune #2060): DB's
  Oldfield, Gillin, Beller, Kellerhals + trader Barrett; JPM's Mary Erdoes
  fielding referrals 6 years post-"termination." Unifies both banks' failures;
  maps onto **Paul Morris** (our #1 coverage gap, 9.8K pages / 0 findings — NOT
  illuminated by reporting; primary-docs-only).
- **African surveillance-tech-for-access channel** (multilingual, 0 findings):
  Ouattara's niece **Nina Keita** (person #1122) brokering an Israeli
  surveillance system + Boeing 727 to Ivory Coast; Wade/Senegal, Kagame/Rwanda.
- **French operational cluster:** recruiter **Daniel Siad**, diplomat **Fabrice
  Aidan** (#25010; live PNF case + Rothschild-bank raid), ex-Élysée advisor
  **Colom** — 134-1,314 primary mentions each, ~0 findings.
- **Re-identifications that fix mislabeled gaps:** **Natalia Molotkova** = Amex
  Centurion manager who booked decoy flights (not "staff"); **Ann Rodriguez** =
  LSJ island property manager (not "NY office staff"); **Brice Gordon** = Zorro
  Ranch manager.
- **Untracked money edges:** STC↔Fidelity, Wexner-trust $65M multi-bank circuit,
  Epstein↔Russian banks (Raiffeisen/Sberbank/UniCredit), Mandelson↔Staley↔Nat
  Rothschild's Vallar plc, Ben Black↔ESWW↔DFC, Ambani↔Epstein (Modi back-channel).

---

## Story angles (ranked; genuinely new only)

1. **"The $13M prosecutors couldn't trace — the files answer it."** Our Dec 23
   2019 $13M wire → Interactive Brokers money-market (finding #1461) answers an
   on-the-record court question. Lowest effort, highest credibility.
2. **The Apr–Jul 2019 money map** (the convergent flagship). Fidelity's *double*
   exposure + the vanishing DOJ SAR (recover-archives target).
3. **"The 14 the DEA was watching"** — reconstruct the OCDETF probe's 14 redacted
   co-targets from wire counterparties. Document-anchored, uniquely ours.
4. **The Black $170M reconciliation** — no outlet has published a wire-level
   breakdown; we can.
5. **The servicing desk** — the named human private-banking pipeline.
6. **Epstein's DNA program** (Thakuria/Cryobank/23andMe; 774 local docs, 0
   findings) and the **French operation** (avenue Foch/BNP/EdR) — both
   document-rich locally, both unbuilt.
7. **Planes as statecraft** — Sikorsky-to-Kirchner (Argentina) + Buenos Aires
   "intelligence" plan, alongside the already-flagged Aetna/Panama helicopter.

---

## Actions executed (2026-07-13, epstein profile; profile restored after)

### Leads created (top document-anchored angles)
1. **#57676** (high) — Apr-Jul 2019 banking exit-ramp; related #1036/#1035/#1217.
2. **#57678** (high) — DEA/OCDETF 14 co-targets reconstruction.
3. **#57680** (high) — DB/JPM servicing desk as one structure; related #107/#51.
4. **#57682** (medium) — Black fee reconciliation; related #203/#202/#210.

### Corrections applied (verified-safe subset only)
- **#2403** — ".3 million" → "$2.3 million" (factual_error). DONE.
- **#2** — "Deveraux" → "Dechert" + "M" → "$158 million" (factual_error). DONE.
- **#2940** — DISPUTED (Kaplan/Rakoff case misattribution). DONE.
- **#11 + #639** — CORRECTED (2026-07-13) after primary-doc reconciliation
  against the kabasshouse corpus + Govt will chronology (EFTA00086220),
  independently spot-checked. The reporting lead held: **EFTA00016865 is a
  superseded Jan 27 2012 will** (directs to "Trust One", not the 1953 Trust) —
  #639 wrongly labeled it "the Last Will." **EFTA01266457 is the 2018 Trust**
  (not "2019"), and **EFTA01266434 (2017 Trust) does NOT name Ruemmler** — #11
  overstated her as an operative estate fiduciary; she was in superseded 2018
  instruments only, replaced by Boris Nikolic (successor executor) in the
  operative Aug 8 2019 will, and never served. A superseded version
  (EFTA00016884) named Lawrence Summers as backup executor.
- **#1567** — no defect; unchanged.

### Claims layer
- Codex produced a **complete scored 200-item extraction queue**
  (`claims-queue.csv`, + `build_claims_queue.py`, `claims_queue.sql`,
  `queue-audit.md`) — era-balanced (VF 2003 #2, NY Mag 2002 #5, PBP 2006/08
  floored above 2026 volume), topically spread, dedup-aware. The audit
  independently confirmed `independence_group` is outlet-level not story-level
  (251 groups: 238 outlet / 13 exact-content) — don't use it to pick "one story
  per cluster."
- The **pilot JSONL + methodology memo were NOT produced** — the Codex run hit
  an upstream `model is at capacity` error after 327K tokens. The queue survived;
  the pilot extraction can be retried (Codex) or run by a Claude agent off the
  completed queue. Interim: the financial lens already drafted 29 import-ready
  claims (in `report-financial.md`). Import vetted `reported_only` claims via
  `reporting_corpus.py import-claims` (NO promotion to findings).

---

## Per-lens worksheet pointers

Full agent worksheets were written to the session scratch workdir:
`report-financial.md`, `report-multilingual.md`, `report-updates.md`,
`report-entities.md`, `report-genealogy.md`, `report-2026threads.md`, plus
Codex `report-codex-integrity.md` and `report-codex-claims.md` (pending) with
`claims-queue.csv` / `claims-pilot.jsonl`. Regenerate via the eight agent
prompts if the scratch dir has cleared.
