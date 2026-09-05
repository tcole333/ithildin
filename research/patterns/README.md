# Investigative Pattern Library

A transferable library of investigative patterns extracted from published bodies of investigative journalism:
what a top outlet *finds*, what *evidence and sources* it runs on, and the precise *detection move* that
surfaced each finding — so this platform's investigation agents can recognize the same patterns in other data.

**Four outlets profiled** (as of 2026-07-29): **ProPublica** (2008–2026, the founding corpus), **ICIJ**,
**OCCRP**, and **The Markup**. ~490 coded entries total. Each outlet has its own story index and `_intake/`
extraction layer; the card layer and the adapter-gap ranking are shared, so a pattern confirmed in four
independent corpora reads as one card with four exemplar sets.

| File | Contents |
|---|---|
| [detection-signatures.md](detection-signatures.md) | **The card layer** (shared): 41 operational pattern cards — mechanics, minimum data, Ithildin tool mapping, failure modes, discipline fields, exemplar URLs, and per-card cross-outlet exemplars + input-dependency |
| [cross-outlet-ontology.md](cross-outlet-ontology.md) | **The merged layer**: finding-type/evidence-source families with per-outlet frequencies; the local-name → shared-family signature map; the four-outlet input-dependency comparison and the instrument-decay result |
| [propublica-ontology.md](propublica-ontology.md) | ProPublica's own taxonomies with frequencies; acquisition playbooks; provenance checklist; retired priors; emergent categories (the template the merged layer builds on) |
| [propublica-story-index.md](propublica-story-index.md) · [icij-story-index.md](icij-story-index.md) · [occrp-story-index.md](occrp-story-index.md) · [markup-story-index.md](markup-story-index.md) | Per-story evidence indexes — the coded corpora behind every frequency claim. Non-ProPublica indexes carry a `Dependency:` field per entry |
| [adapter-gaps.md](adapter-gaps.md) | Missing data-source adapters ranked by observed usage — ProPublica ranking (rows 1–5 enqueued as infra #218–222) plus a separate cross-outlet ranking (nothing enqueued) |
| [promotion-candidates.md](promotion-candidates.md) | What was promoted to `research/craft-research/` frameworks, what was held in the card layer instead, and why — plus outstanding follow-ups |
| `_intake/<outlet>/` | Raw extraction layer per outlet: cluster/methodology/census reports, `tally/` mechanical extracts, `raw/` census pulls. Every claim in the synthesis layer traces to a cited entry here |
| [_intake/access-substitution-analysis.md](_intake/access-substitution-analysis.md) | The input-dependency methodology: what a leak-based method loses to public substitutes, per signature, with live-checked substitute inventory |
| `_validation/` | Live validation memos — cards executed against held platform data (PPP parquet, DHS census + FPDS, tech-right graph), with field-by-field executability verdicts and the amendments that were applied. The discipline fields in detection-signatures.md (Pre-registration, Coverage, Control, Preconditions) came from this pass |

## Method

Two-wave extraction with a de-biasing discipline:

1. **Wave 1** coded ~107 stories across 8 flagship clusters (tax/wealth, judicial ethics, dark money,
   healthcare, criminal justice, corporate/consumer, government spending, environment/labor/tech) plus a
   methodology-infrastructure report (Nerd Blog, Data Store, standards) — agents were *seeded* with candidate
   stories and starting taxonomies, instructed to verify attribution, extend freely, and cite a URL for every claim.
2. **Corpus census** (report-10) counted ProPublica's actual output from its own WordPress API — 287 series,
   12,391 articles — to measure what the flagship frame missed, and identified the uncovered clusters.
3. **Wave 2** coded the census-identified uncovered areas (immigration, education/children, military/veterans,
   housing, democracy/elections, tribal affairs) with **no seeded stories and no seeded taxonomy** (free-form
   tagging), so its tag stream tests wave-1 categories rather than inheriting them. ~73 further coded entries;
   total coded corpus ≈ 180 story entries (the index carries 217 entries including methodology-infrastructure
   items and cross-references).
4. **Synthesis** re-derived the taxonomies bottom-up from the coded entries: a category exists only with ≥2
   independently cited story instances (≥3 + ≥2 clusters for "core"); seeded categories that failed the bar are
   listed as **retired priors**; unseeded categories that recur are **emergent** — both in
   [propublica-ontology.md](propublica-ontology.md) §6–7.

### The method as applied to outlets 2–4

The same discipline (own-site census → free-form second wave → bottom-up re-derivation) was applied to ICIJ,
OCCRP, and The Markup, with one addition and one scope inversion:

- **Input-dependency coding (added).** Every entry outside the ProPublica corpus classifies its decisive
  evidence as **(a)** open-record-runnable end-to-end, **(b)** re-anchoring (leak/insider discovery, public
  verification half), **(c)** leak-dependent, or **(d)** closed-platform-dependent — the methodology and the
  live-checked substitute inventory are in
  [_intake/access-substitution-analysis.md](_intake/access-substitution-analysis.md). This is what makes the
  library actionable rather than admiring: a card whose exemplars are all (c) cannot be run here.
- **Volume-ranking inversion (ICIJ).** The ICIJ census found the famous 7-project leak canon is 14% of projects
  but 50.7% of project-path output, and that its largest *residual* cluster (noncanonical offshore/tax leaks)
  was methodologically nearest the canon. The wave therefore deliberately **skipped the biggest residual
  cluster** and took the open-records clusters instead (extractives/environment, aid/development finance,
  lobbying/regulatory capture, conflict/repression). It paid off: those clusters are 63% end-to-end public
  versus the canon's 45%.
- **Full-portfolio extraction (The Markup).** Its census §8 ranks clusters by *famous-frame-missed* volume,
  which scores its most method-distinctive work (Blacklight/Pixel Hunt privacy instrumentation, platform labor)
  at zero — an artifact of that formula assuming a prior canon extraction exists, which for this outlet it did
  not. All 9 clusters were extracted, with the low-ranked ones instructed to go to full depth.
- **Markup-specific fields.** Because the outlet open-sources heavily (84 GitHub repos, "Show Your Work"
  methodology pages), its entries cite repo + methodology page as the methodology field, and class-(a) entries
  additionally record whether the instrument path **still works today** — see the decay result in
  [cross-outlet-ontology.md](cross-outlet-ontology.md) §4.

## Entry schema (the coded unit)

Each story entry in `_intake` reports and the story index carries: title/year/URL; partner + awards; what they
found (concrete, with amounts); finding-type tags; typed evidence sources with acquisition mode; **detection
signature** (the join/diff/gap/reconstruction that surfaced the finding — the load-bearing field); corroboration
structure; methodology link (cited "How We Did This" vs `[inferred]`); generalization notes. Wave-1 entries also
carry access-tier/acquisition-path fields; the index adds a `Systems:` line naming specific record systems for
the adapter-gap tally. Entries in the ICIJ/OCCRP/Markup layers add **INPUT DEPENDENCY** (a/b/c/d with the
public/private split stated exactly), and Markup entries add runnable-today status.

## Sampling frame and known biases

The census (report-10 §9, `_intake/propublica/report-10-census.md`) quantifies what this library's selection
sees and misses. Read these before trusting any frequency:

- **Coverage:** the flagship frame (eight subject clusters plus the methodology bucket) covers 64.5% of
  ProPublica's named series and ~71% of series-tagged output; wave 2 raises honest coverage to ~95% of
  named-series output. Series-tagged work is itself only ~45% of all articles — untagged daily output is not
  sampled.
- **Award-canon bias:** flagship clusters cover 18/22 Pulitzer entries (82%) but only ~71% of output; 3 of the
  5 most recent Pulitzer *wins* fall in wave-2 territory (the frame over-represents award-anointed work).
- **National-vs-local bias:** the Local Reporting Network concentrates precisely in wave-2 areas (37% of LRN
  series), and the 50-State Initiative means the uncovered share of *new* series grows over time.
- **Evidence-type bias:** a flagship-only extraction over-learns "big dataset + outlier analysis" and
  under-learns "state agency records + human sourcing" — the reason wave 2 exists.
- **Era bias:** measured NOT material (~35% uncovered share is stable across eras).
- **Story double-counting:** a handful of stories legitimately live in two clusters (RealPage, workers' comp,
  TurboTax, Trump inaugural); family frequency counts note the dups.
- **Extraction-layer caveat:** entries were coded by LLM agents from published stories and methodology pages —
  quoted-methodology vs `[inferred]` is marked per entry, and misattributed candidates were dropped in wave 1,
  but the coding itself has not been independently double-keyed.

### Cross-outlet frame caveats (added 2026-07-29)

- **Sampling depth differs by outlet**, so cross-outlet frequency *sums* are meaningless and are never
  reported: ProPublica ~1.5% of its 12,391-article corpus, ICIJ 43 wave-2 stories against 1,664 project-path
  items, OCCRP 73 stories, The Markup 83 of 835 dated URLs (~10%, the deepest). Comparisons in
  [cross-outlet-ontology.md](cross-outlet-ontology.md) are therefore *within-outlet* frequencies plus a count
  of how many outlets independently converged on a family.
- **The site frame lies differently at every outlet, and each census had to catch it:** ICIJ's investigations
  index repeats page 1 through page 10 (the project sitemap is the only defensible backbone); The Markup
  exposes no sitemap at all and its visible archive omits 17.5% of dated pages (146 newsletter URLs, recovered
  only by unioning every series index). Any recount must re-derive the frame, not trust the UI.
- **Attribution rules are outlet-specific.** ICIJ/OCCRP are consortia: a project banner may coordinate hundreds
  of reporters while partner outlets publish on their own domains, so entries name lead outlets and count only
  ICIJ/OCCRP-hosted URLs. The Markup merged with CalMatters in 2024; its census uses a domain-structural rule
  (count Markup-domain URLs once; exclude separately-canonical CalMatters copies, CalMatters-only work, and
  translations) audited against all 3,733 post-merger CalMatters posts.
- **Era/access drift:** several ICIJ clusters are 2000–2012 work whose pages were migrated in 2012 or later, so
  sitemap `lastmod` is not publication date, and some claims are cited to Wayback copies (marked per entry).
- **Dependency coding is not double-keyed either**, and canon entries inherit their class from the
  access-substitution tables rather than from a fresh read; entries with no plausible match are marked
  `unassessed` (29 ICIJ + 22 OCCRP methodology units) rather than guessed.

## How agents should use this

- **Screening:** Tier-1 signature cards (two-books-diff, silo-join, denominator-construction,
  enforcement-gap-ratio…) are standing questions to ask of any new investigation's data. The cards' "Ithildin
  mapping" lines name the concrete tools; "GAP:" flags where the move needs an adapter we don't have.
- **Lead generation:** when a finding matches a card's finding-type composite (e.g., captive population +
  per-diem payer + weak inspection), the card's co-occurring components are the next leads.
- **Provenance:** the 10-point checklist (ontology §4) is the promotion gate discipline; it maps onto
  findings_tracker claim-type/confidence rules.

## Extension path

- **Outlets already profiled:** ProPublica, ICIJ, OCCRP, The Markup. The method (seeded flagship pass →
  own-taxonomy census → free-form second wave → bottom-up re-derivation, plus input-dependency coding) is
  stable and reusable as-is. Each outlet gets its own story index and `_intake/` layer; cards stay unified in
  detection-signatures.md with per-outlet exemplars.
- **Candidate outlets next**, ranked by expected end-to-end-runnable yield (the access-substitution logic):
  Reuters investigations and BIJ (records-heavy, non-leak-centric); Bellingcat (open-source verification
  methods — likely the highest class-(a) share of any outlet, and the closest to this platform's own
  constraints); Le Monde/SZ as consortium *partners* rather than coordinators, which would test the
  consortium-attribution rule from the other side. Reaching for another leak-centered outlet is the lowest-value
  option — that ground is now covered twice.
- **Recount triggers:** re-run an outlet's census before trusting its frequencies if the site is restructured
  (The Markup/CalMatters integration is mid-flight), and re-check Markup class-(a) runnable-today statuses
  periodically — 20 of 65 are already degraded, and that number only grows.
- **Promotion to analytical models:** detection signatures are *detection moves*; `research/craft-research/`
  Tier-2 lenses are *explanatory models*. When a pattern card proves out in a live investigation (accumulates
  grounding findings with evidence chains), propose it through `/discover-frameworks` for promotion into
  `research/craft-research/analytical-models.md` as a Tier-2 lens (and eventually Tier 1 with full specs), the
  way the tech-right lens set was promoted. Current state of that queue, including two candidate lenses written
  in the 2026-07-29 pass and what was deliberately *not* promoted:
  [promotion-candidates.md](promotion-candidates.md).
- **Adapter builds:** adapter-gaps.md candidates go through the normal infra_tracker triage when the user
  green-lights them — the library ranks by observed usage, the queue decides by investigation fit. The two
  cross-outlet additions with no ProPublica-derived equivalent are customs/bill-of-lading data and a
  first-party web-instrumentation harness; the latter is the cheapest high-value build on either ranking
  (Blacklight is open source; Playwright is already a project dependency).

## Provenance of this library

Built 2026-07-28/29. Extraction agents' reports (with per-claim URLs) in `_intake/<outlet>/`; tally layers
(mechanically extracted coded lines) in `_intake/<outlet>/tally/`; census raw pulls in
`_intake/<outlet>/raw/` (ProPublica's WordPress API; ICIJ's project/editorial sitemaps; The Markup's archive +
series union, GitHub API, and CalMatters attribution audit). Extraction and tally work was performed by Codex
(gpt-5.6-sol) agents under a read-only-database constraint; the merge, card unification, and promotion
decisions in this pass were done in-session. **Nothing in this library was written to investigation.db and no
infra requests were enqueued from it** — including the `/discover-frameworks` hypothesis registration for the
two candidate lenses, which is recorded as an outstanding follow-up in
[promotion-candidates.md](promotion-candidates.md) §4.
