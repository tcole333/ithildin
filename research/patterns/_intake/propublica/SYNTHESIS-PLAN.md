# ProPublica Ontology — Synthesis Plan (survives context compaction)

## User request (2026-07-28)
1. Review ProPublica's reporting → ontology of (a) what they found, (b) what sources/evidence they used.
2. Synthesize into models/patterns recognizable during our own investigations.
3. **ADDED mid-session**: identify sources we're MISSING adapters for — concrete build candidates
   (diff ProPublica's evidence-source inventory vs our existing 90+ tools).

## DE-BIASING DISCIPLINE (user directive 2026-07-28: "don't lead with priors — let this be analytical based on what we find")
Binding rules for synthesis:
1. My seeded story lists + starting taxonomies are HYPOTHESES, not structure. The final ontology
   is re-derived bottom-up from the coded story entries.
2. Every finding-type / detection-signature / evidence-source category in the final ontology needs
   >=2 independently cited story instances (>=3 for "core" status). Frequencies reported per category.
3. The ontology doc MUST carry: (a) "Retired priors" — my starting tags with no empirical support;
   (b) "Emergent categories" — tags that arose from the data that I did not seed.
4. report-10-census.md (empirical corpus census from ProPublica's own series/topic/sitemap structure)
   is the sampling frame. Flagship-cluster selection bias must be quantified/stated in the README.
5. SECOND WAVE: spawn extraction agents for census-revealed uncovered areas with NO seeded stories
   and FREE-FORM tagging (no starting taxonomy given). Synthesis reconciles both tag streams.
6. Adapter-gap ranking = observed source-usage frequency across coded corpus + number of patterns
   unlocked, NOT my hypothesis-list ordering. coverage-inventory.md gap list is hypotheses only.

## Wave state
10 background agents writing to this directory:
- report-10-census.md — EMPIRICAL corpus census (series index, topics, sitemap volumes, LRN,
  coverage-diff vs the 8 clusters, second-wave recommendations). Second wave spawns from this.
- report-01-tax-wealth.md
- report-02-judicial-ethics.md
- report-03-dark-money.md
- report-04-healthcare.md
- report-05-criminal-justice.md
- report-06-corporate-consumer.md
- report-07-gov-spending.md
- report-08-environment-labor-tech.md
- report-09-meta-methods.md (Nerd Blog / Data Store / How-We-Did-This / crowdsourcing / standards)

## Deliverables (write into repo, do NOT commit)
- research/patterns/README.md — what the library is, schema, extension path (other outlets next: ICIJ/OCCRP/Reuters), promotion path to craft-research Tier-2 lenses via /discover-frameworks
- research/patterns/propublica-ontology.md — finding-type taxonomy + evidence-source taxonomy + acquisition playbooks + provenance checklist
- research/patterns/detection-signatures.md — the operational pattern cards (name, mechanics, min data requirements, Ithildin tool mapping, failure modes, exemplars w/ URLs)
- research/patterns/propublica-story-index.md — per-story structured entries (evidence base, distilled from agent reports)
- research/patterns/adapter-gaps.md — missing-source adapter candidates: source, what it provides, which patterns need it, access characteristics, build difficulty, priority. Candidates for infra_tracker (do NOT enqueue without user).
- Also: coverage-inventory.md (scratchpad only) = our current source→tool map used for the diff.
- End: update MEMORY.md pointer + one-line CLAUDE.md reference if appropriate. No DB writes. No commits.

## Known coverage (from CLAUDE.md module table, to verify against docs/modules/*)
financial: EDGAR, ratios, market data, SEC enforcement, 990s, FDIC, FINRA
registries: unified + 20+ state/intl corporate registries
government: USASpending, HigherGov, SAM, Medicare/Medicaid, CMS Open Payments, PPP, FPDS (query_fpds.py)
legal: CourtListener, NYSCEF, HUDOC, BCMR/BCNR, MilJustice
political: FEC, lobbying, FARA, Congress, GovInfo, Senate Finance archives
osint-infra: crt.sh, Wayback, Shodan, URLScan, Maigret, FAA
corpora: DOJ, LMSBAND, Unified, DugganUSA, DocumentCloud, MuckRock
blockchain: Etherscan, Solscan, Dune
network-sanctions: LittleSis, ICIJ, OpenCorporates, OpenSanctions, GLEIF, FinCEN
patents: USPTO
peru: El Peruano, SUNARP, SUNAT, Infogob, OEFA, SEACE, Contraloría
property/local-courts: ingest_property_records.py, query_property.py, query_state_courts.py, public_records_* (in flight on this branch)
