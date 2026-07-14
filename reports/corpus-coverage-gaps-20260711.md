# Corpus Coverage Gaps — Most-Mentioned Entities vs Findings (2026-07-11)

**Question:** which entities dominate the Epstein corpus (kabasshouse, 1.42M pages) but have little or no findings coverage in the `epstein` profile (5,147 findings)?

**Headline:** the biggest uncovered layer is the **money-movement machinery** — Epstein's private bankers, in-house accountants, and the bank-operations staff who executed wires and valuations. They are among the most-mentioned humans in the corpus (5K–15K substantive pages each) with zero targeted findings. Second tier: household/office staff (witness value), the Krauss/ASU Origins cluster, and several uncovered corporate vehicles (Mitchell Mitchell Holdings, Glendower Capital funds). On the org side, **no finding in the profile targets JPMorgan itself** — ≥140K pages of JPM-family mentions resolve to 3 findings targeted at Jes Staley.

## Method

- **Mentions:** kabasshouse `entities` (person/organization) joined to `documents`, counted as distinct pages (EFTA page = unit; no reliable multi-page doc grouping exists). Person aliases merged via `epstein_derived.db` person resolution; **bare single-token raw variants excluded** (the resolver folds bare "Larry"/"Richard" into clusters and inflates counts — this cut Visoski's raw 27K to a clean 15K).
- **Noise filter:** 25,851 pages (1.8% of corpus) flagged and excluded: typed news/article/press-release/research-report/newsletter pages + FTS boilerplate markers (`unsubscribe`, "you are receiving this", "view this email in your browser", "for immediate release", "national press office", "market update/commentary", briefing markers). Notably, **noise share among top-mentioned people is only 0.1–2%** — the top ranks are driven by transactional documents (DS10 financial estate + DS10/11 email corpus), not newsletters. Mass-mail noise matters lower in the distribution (world figures name-dropped in market commentary), not at the top.
- **Findings coverage:** epstein-profile findings matched by target_name (exact + subset token match, person and org tokenizations), `finding_entities` links, `name_aliases`, plus a substring scan of finding text (`text=` column = findings that *mention* the entity anywhere — narrative presence without targeted coverage).
- Rerunnable: `uv run python scripts/coverage_gap_scan.py`. Full ranked tables: `reports/corpus-coverage-gaps-20260711-persons.csv` (600) / `-orgs.csv` (400).

**Validation:** well-covered people rank exactly as expected — Indyke 95 targeted findings, Leon Black 62, Ruemmler 33, Groff 24, Epstein 224. The zeros below were spot-checked against `target_name LIKE` queries directly.

## A. Person gaps

`clean` = non-noise pages mentioning the person; `targeted` = findings targeting them; `text` = findings mentioning them anywhere.

### A1. Money-movement layer (matches profile's financial-mapping priority)

| Person | Clean pages | Targeted | Text | Who they are (annotation) |
|---|---|---|---|---|
| **Paul Morris** | 9,778 | 0 | 11 | Epstein's private banker — JPMorgan PB, then recruited to Deutsche Bank 2013 and brought the relationship with him (the DB NYDFS consent-order relationship-manager role). Emails + valuation statements. *Highest-priority gap.* |
| **Bella Klein** | 10,769 | 1 | 32 | NY-office bookkeeper — wire instructions, account reconciliation |
| **Amanda Kirby** | 6,068 | 0 | 6 | Financial ops — emails + bank/valuation statements (DS10) |
| **Harry Beller** | 5,796 | 1 | 29 | Accountant — 2,460 pages of memoranda + KYC prints; longtime Epstein-org accounting figure |
| **Vahe Stepanian** | 5,325 | 0 | 4 | Private-wealth banker (emails + valuation statements) |
| **Daniel Sabba** | 2,741 | 0 | 3 | Private-wealth banker (emails + valuation statements) |
| **Tazia Smith** | 3,820 | 0 | 6 | Private-wealth banker (emails + valuation statements) |
| **Janet E. Young** | 4,715 | 0 | 8 | Name appears almost exclusively on bank statements (2,600+ pages) — likely bank client-service officer; mechanical, but identifies the servicing desk |
| **Bradley Gillin** | 2,648 | 0 | 1 | Emails + **"Revocation of Designation of Successor Trustees"** docs — trust/estate structure figure |
| **Melanie Spinella** | 5,403 | 1 | 19 | Financial/office ops (DS10) |
| **Paul Barrett** | 4,475 | 0 | 16 | Financial (DS10) |

### A2. Operations & household staff (witness layer)

| Person | Clean pages | Targeted | Text | Annotation |
|---|---|---|---|---|
| **Larry Visoski** | 15,057 | 0 | 7 | Chief pilot ~1991–2019; testified at Maxwell trial. Most-mentioned uncovered human in the corpus. |
| **Ann Rodriguez** | 14,760 | 0 | 1 | NY office staff — 10K+ email pages (DS10/11). Second-most-mentioned uncovered person. |
| **Natalia Molotkova** | 8,277 | 0 | 1 | Staff (DS10 emails) |
| **Brice Gordon** | 8,257 | 0 | 1 | Staff (DS10 emails) |
| **Daphne Wallace** | 7,040 | 0 | 13 | Office staff — appears as correspondent in JPM-exhibit email metadata too |
| **Merwin de la Cruz** | 6,763 | 0 | 3 | Household staff |
| Fontanilla family (Jo-Jo/Luciano/Lyn) | ~9,500 combined | 0–1 | 6 | NY townhouse household staff |
| **Janusz Banasiak** | 2,617 | 0 | 0 | Palm Beach house manager (2000s-era deposition figure) |
| Cynthia Rodriguez, Cashkim Bussue, Jermaine Ruan, Scott Denett, Eileen Alexanderson, Jeanne Brennan, Richard Joslin, Emad Hanna, Steve Hanson | 1.7K–2.6K each | 0 | 0–12 | Staff/vendor email correspondents (DS10/11) — unidentified; triage-worthy |

### A3. Science / philanthropy network

| Person | Clean pages | Targeted | Text | Annotation |
|---|---|---|---|---|
| **Joi Ito** | 5,159 | 1 | 2 | MIT Media Lab — 1 finding despite the public MIT-donations scandal |
| **Martin Nowak** | 5,010 | 1 | 17 | Harvard Program for Evolutionary Dynamics ($6.5M Epstein-funded) |
| **Lawrence Krauss** | 4,146 | 0 | 6 | ASU Origins Project — pairs with **Arizona State University: 1,917 org pages, 0 findings**. Coherent uncovered cluster. |
| **Joscha Bach** | 2,225 | 1 | 4 | AI researcher, Epstein-funded |

### A4. Social / public figures (mentioned heavily, thin local coverage)

| Person | Clean pages | Targeted | Text | Annotation |
|---|---|---|---|---|
| **Cecile de Jongh** | 4,368 | 0 | 15 | USVI first lady, central to USVI v JPMorgan — zero targeted findings despite salience |
| **Peggy Siegal** | 4,359 | 0 | 15 | Publicist, social gatekeeper post-2008 |
| **Woody Allen** | 3,281 | 0 | 29 | Frequent correspondent/dinner circuit |
| **Peter Mandelson** | 3,196 | 0 | 12 | UK politician |
| **David Mitchell** | 4,911 | 1 | 17 | Business — pairs with **Mitchell Mitchell Holdings LLC (2,718 org pages, 0 findings)** |
| **Faith Kates** | 2,859 | 1 | 2 | NEXT Management (modeling agency) co-founder |
| **Nicole Junkermann** | 2,057 | 1 | 16 | Investor, longtime associate |
| **Brad Wechsler** | 2,345 | 0 | 12 | IMAX chairman |
| **Deepak Chopra** | 1,915 | 0 | 4 | Flight-log figure |
| Gary Kerney | 4,269 | 0 | 1 | Unidentified — 3.9K email pages across DS10/11; possibly insurance/claims |
| Eric Roth | 4,093 | 0 | 1 | Unidentified business contact |

Court apparatus (Judge Alison Nathan, SDNY reporters) excluded as mechanical.

### Ratio observations (covered but underweighted vs volume)

- **Richard Kahn**: 43,379 pages / 11 targeted findings — co-executor, highest volume-to-coverage imbalance among named associates
- **Lesley Groff**: 98,367 / 24
- **Karyna Shuliak**: 20,060 / 7
- **Jes Staley**: 5,045 / 3
- **Stewart Oldfield**: 9,891 / 10 (and only 0.4% of his pages were caught by the newsletter filter — his volume is direct correspondence, not bulk mail)

## B. Organization gaps

| Org | Clean pages | Targeted | Annotation |
|---|---|---|---|
| **JPMorgan family** (all OCR variants) | ≥140,000 | 0 | No JPM-targeted finding exists in the profile; coverage lives only inside Staley/other findings' text. USVI v JPMorgan exhibits remain un-ingested (known priority source). |
| **Deutsche Bank family** | ~35,000 | 0 | Same pattern; pairs with Paul Morris gap |
| **American Express** (+ Centurion Travel) | ~29,600 | 0 | Card/travel rails — movement-reconstruction source, unmined |
| **AT&T of the V.I. / T-Mobile / Verizon / BlackBerry** | ~34,000 | 0 | Telecom records layer (DS11 device/network logs) — mechanical but confirms phone-records presence in corpus |
| **LSJ Company / LSJE LLC** | 5,160 | 1–2 | Little St. James operating entities — thin relative to volume |
| **Zorro Development / Hyperion Air** | 5,400 | 1–2 | Ranch + aviation entities — same |
| **Mitchell Mitchell Holdings LLC** | 2,718 | 0 | Uncovered vehicle; pairs with David Mitchell |
| **Glendower Capital (U.S.) LLC + Secondary Opportunities Fund IV** | 3,686 | 0 | PE secondaries fund position in estate docs — uncovered |
| **Arizona State University** | 1,917 | 0 | Krauss/Origins cluster |
| JEE corp. / "GMAIL COM" / SDNY reporters / FINRA / SIPC / NYSE / FDIC / FBI / DOJ / Apple | (large) | — | Statement boilerplate, email-parsing artifacts, court/regulatory apparatus — mechanically high, no action |

## Caveats

- Page-level counting: a 100-page statement mentioning a banker on every page counts 100 — volume partly reflects document format, not importance. Treat ranks as tiers, not precise ordering.
- `targeted=0` ≠ zero knowledge: the `text` column shows narrative presence inside other findings. The gap is in *targeted, evidence-linked* coverage — which is what dossiers, entity pages, and graph queries key off.
- Org mention layer is OCR-soup; brand-collapse was applied to major institutions but long-tail org counts are fragmentary.
- Noise filter is high-precision, not exhaustive — multi-page newsletters are only flagged on boilerplate-bearing pages. Since top-rank noise shares came out at 0.1–2%, residual leakage does not move these rankings.

## Suggested next steps (not executed)

1. `/deep-investigate` the private-banking cluster as one unit (Morris + Kirby + Stepanian + Smith + Sabba + Young) — reconstructs the JPM→DB servicing pipeline from DS10 valuation/wire docs.
2. Targeted findings pass on Visoski and Ann Rodriguez email volumes (top-2 uncovered humans).
3. Ingest USVI v JPMorgan exhibits (already on the priority-source list) before writing JPM-targeted findings.
4. Small dedicated pass on Krauss/ASU, Mitchell/MMH LLC, Glendower funds.
5. Triage the unidentified staff names (Kerney, Roth, Hanson, Denett, Bussue, Ruan, Alexanderson, Brennan, Joslin, Hanna) — a `/triage-leads`-style batch to classify who's who before any deep dives.
