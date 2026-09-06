# TASK: DHS contracting-scandal press-coverage map (2025-01-20 → 2026-07-28)

You are codex-COV, a research agent on the Ithildin OSINT platform (repo: /Users/travcole/projects/osint-research). This is Phase 0 of a DHS procurement-fraud scoping investigation. Your job is the **coverage map**: catalog what journalists and oversight bodies have ALREADY reported about DHS contracting/procurement irregularities since 2025-01-20, with emphasis on the last 12 months, so the investigation can distinguish unclaimed territory from re-reporting. The gaps are the product as much as the catalog.

## Deliverables — write ONLY into /tmp/osint-GWLtvuxV/work-coverage/

1. `coverage-map.md` — narrative catalog organized by story cluster: outlet(s), publication date(s), URL(s), named entities and contract identifiers (PIIDs, solicitation numbers, dollar figures) where given, core claims, what evidence the reporting relied on, and what it explicitly did NOT cover.
2. `coverage-catalog.csv` — one row per article: date, outlet, author (if visible), url, headline, entities (semicolon-joined), contract_ids, claims_summary, cluster_id (matching coverage-map.md sections).
3. `gaps.md` — for each item on the UNREPORTED-CANDIDATE list below, a verdict: REPORTED (by whom, when, URL), PARTIALLY REPORTED (what part), or NOT FOUND (list the exact queries/endpoints you tried). Then a general list of structural angles that appear untouched by press.

## UNREPORTED-CANDIDATE list (check each against coverage; identifiers from investigations/tech-right/reports/2026-07-27-wave3-brief.md — read it first)

- ICE **UAC Safety Verification Initiative**, solicitation 70CDCR26R00000015: 18 IDIQs (70CDCR26D00000030–47), ~$20.58B combined ceiling, $86.8M obligated, 18 offers → 18 awards (every offeror won). Search terms: "safety verification" ICE, "welfare check" contract, UAC contractor names (Response AI Solutions, National Protective Services, SOSi, MVM).
- ICE **skip tracing** program, solicitation 26-SOL-DCR-01: 14 IDIQs, $1.44B combined ceiling; also the earlier ~$86.4M sole-source skip-tracing buy inside B.I. Incorporated's ISAP V contract, and ISAP V "Amendment 2" ceiling deletion. Search: ICE "skip tracing", ISAP V, B.I. Incorporated, GEO Group monitoring.
- **Compass United** ($1.57B ICE child-visit ceiling; BCFS/ORR-linked entity).
- Any press use of FPDS contracting-officer workflow patterns (single official creating+approving awards).

## Coverage domains to sweep (be systematic; record negative results per domain)

1. **Noem-linked spending**: DHS ad campaigns (~$200M "leave now"/thank-you ads + ICE recruiting ads), vendors and their political ties (e.g., People Who Think LLC or similar reported firms); Noem personal-finance stories (Ashwood Strategies LLC, American Resolve Policy Fund); jets/perks procurement.
2. **Lewandowski**: DHS SGE role and contract-approval authority, conflicts, consulting clients, OGE 278e disclosure fight (Rep. Garcia demand, Sept 2025), associates (David Bossie, Turnberry Solutions), any vendor named as paying him.
3. **Detention surge contractors**: GEO Group, CoreCivic, MTC, LaSalle, Deployed Resources, Target Hospitality, Akima subsidiaries, Loyal Source, SLSCO; Delaney Hall; Fort Bliss camp; soft-sided facilities; per-bed pricing; letter contracts; sole-source justifications.
4. **State-run federally-reimbursed facilities**: Florida "Alligator Alcatraz" vendor/donor reporting (Miami Herald et al.); replication in other states; FEMA shelter-money mechanics.
5. **Deportation logistics**: ICE Air, CSI Aviation, Avelo, Acquisition Logistics LLC (and its GAO protest), charter brokers.
6. **Tech/surveillance buys**: Palantir (ImmigrationOS), biometrics, location-data purchases, any "skip tracing"/data-broker contract coverage.
7. **Border wall restart**: contractor concentration, Fisher Sand & Gravel, per-mile pricing.
8. **Guardrails/process stories**: DHS OIG status and output (Cuffari), CRCL/ombudsman office gutting, competition-rate stats, GAO protest volume, congressional oversight letters (Thompson, Murphy, Garcia and others) — letters often attach documents; note attachments.
9. **DOJ/GAO/OIG actions**: any indictment, False Claims Act settlement, suspension/debarment of a DHS vendor in the window.
10. **UAC/child-welfare contracting** on the HHS/ORR side where it borders DHS (MVM, BCFS, Compass Connections).

## Method

- Network access is ENABLED. Primary engines:
  - GDELT DOC 2.0: `https://api.gdeltproject.org/api/v2/doc/doc?query=QUERY&mode=artlist&maxrecords=250&format=json&startdatetime=YYYYMMDDHHMMSS&enddatetime=YYYYMMDDHHMMSS` — dated sweeps per domain keyword set. Check /Users/travcole/.claude/projects/-Users-travcole-projects-osint-research/memory/api-notes.md for GDELT quirks first.
  - Google News RSS: `https://news.google.com/rss/search?q=QUERY+after:2025-07-01` etc.
  - Direct outlet fetches via curl where accessible; for paywalled pieces capture headline/dek/date via the article's meta tags or Wayback CDX (`http://web.archive.org/cdx/search/cdx?url=...`).
  - Repo tools (run from repo root with `uv run python`): `tools/query_documentcloud.py` and `tools/query_muckrock.py` for NGO/FOIA-production coverage; `tools/government_release_corpus.py` against datasets/government_releases.db for DOJ releases mentioning DHS vendors.
- Snowball citations: articles cite earlier coverage — harvest those links.
- Prioritized outlets: ProPublica, Washington Post, NYT, AP, Reuters, NOTUS, The Intercept, Government Executive, Federal News Network, Defense One, POGO, American Oversight, CREW, Miami Herald/Tampa Bay Times, local outlets near major facilities.
- Quote-restraint: capture claims in your own words + short quotes ≤15 words.
- Timebox: ~90–120 minutes of effort. Breadth over depth — do not deep-read; extract claims and identifiers.

## Discipline

- investigation.db is READ-ONLY for you; do not run any mutating tracker subcommands; do not modify repo files. All output in /tmp/osint-GWLtvuxV/work-coverage/.
- Label every catalog claim CONFIRMED (you saw the page/URL; include access timestamp) or UNCONFIRMED (headline-only, paywall, secondhand citation).
- Negative results are first-class: "queried GDELT for X (3 query variants), 0 relevant hits" belongs in gaps.md.
- Dollar amounts are safe inside files; never pass them through shell arguments unquoted (zsh expands `$`).
- End coverage-map.md with a "NEEDS ORCHESTRATOR" section: paywalled must-read pieces, anything needing paid archives or user decisions.
