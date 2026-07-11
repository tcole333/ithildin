# Epstein-Aetna Investigation — Agent Context Addendum

Case-specific context for agents working on the `epstein-aetna` profile.
This supplements the generic platform instructions in the project `AGENTS.md`.

## Scope

This is **not** a general Epstein investigation — the broader network lives in
`/investigations/epstein`. This profile's lens is **financial and
corporate-governance**, centered on the July 2011 Freedom Air International →
ASI Wings LLC helicopter sale (N722JE, $11.9M, $11.8M wired to Panama), the
June 2019 no-consideration return transfer to Hyperion Air LLC (23 days
before Epstein's arrest), and the Aetna-Epstein-Apollo corporate network
surfaced by that transaction.

The criminal sex-trafficking dimension is the existing Epstein profile's
domain. This profile's interest in the USVI/Little St. James context is
strictly as the destination of Leon Black's $158-170M Epstein payments (per
Wyden Senate Finance Committee findings and USVI settlement) and the
operational pattern of the helicopter during and after the nominal Aetna
ownership period.

## Pre-Verification Memo

`investigations/epstein-aetna/memo-source.md` is a **pre-verification
exploratory draft** copied from the research session that preceded this
profile. It was written without platform sourcing rigor — web search claims
cited without archived URLs, confidence levels conflated, claim types not
classified.

**Do NOT cite the memo as primary evidence.** Treat it as a claim inventory
to be re-sourced into `investigation.db` with proper `claim_type`,
`confidence`, `source_quote`, and `evidence_ids` metadata via
`tools/findings_tracker.py add`.

`investigations/epstein-aetna/unresolved-questions.md` contains the memo's
open questions; these are the feeder for the lead pipeline.

## Source Reliability — Investigation-Specific

**Tier 1 primary sources** (confidence=confirmed possible for direct quotes):
- **EFTA01339374** — 921-page IATS escrow file, DOJ Epstein Files Dataset 8,
  SDNY Maxwell case bates. Primary evidence for the 2011 transaction.
- **Exhibit 56, USVI v. JPMorgan (1:22-cv-10904)** — Axia Advisors
  (Jorge A. Amador) expert report, Doc 238-31, 161 pages. Forensic
  classification of Epstein aviation entities as shell companies.
- **Exhibit 86, USVI v. JPMorgan** — JPMorgan USCG Due Diligence Report for
  Hyperion Air, Inc., Doc 285-20, JPM-SDNYLIT-00036884-36890.
- **Aetna Inc. 10-K and DEF 14A filings 2011-2018** — SEC EDGAR.
- **CVS Health 10-K filings 2018-2025** — SEC EDGAR.
- **Chiquita Brands SEC filings and the March 2007 plea agreement** (SEC
  Ex 10.1 filed 2007-03-19).
- **FAA Aircraft Registry bulk data** — authoritative for N-number ownership.
- **Hong Kong Companies Registry** — for the HK Freedom Air International
  Limited check (likely unrelated, but archive results before citing).
- **Senate Finance Committee Wyden letters and findings** on Leon Black /
  Epstein payments (2022, 2023, 2025).

**Tier 2 secondary** (max confidence=high for verified paraphrase):
- helis.com, jetphotos.com, AvBuyer, Flightaware, JetASG sale brochure —
  aviation databases. Cross-reference against FAA primary data.
- National Security Archive Chiquita Papers — de-anonymized Individual A-J
  letters from the 2007 plea proffer.

**Tier 3 tertiary** (never cite as evidence — lead starter only):
- NY Post, MEAWW, Simple Flying, Business Insider aggregation, Grokipedia.

**Debunked** (do NOT cite under any circumstances):
- "BEHR Group Holdings" (issuu.com/behrgroup) — SEO/scam shell with
  fabricated Aguirre/Sarna executive claims; issuu account was deleted; one
  of its blog posts promoted an Iraqi dinar investment scam. See
  `config.yaml source_overrides`.

## Confidence Discipline Reminder

The platform enforces `CONFIDENCE_CAPS` at write-time:

| claim_type | max confidence | notes |
|---|---|---|
| direct_quote | confirmed | verbatim from primary source |
| paraphrase | high | agent summary of source |
| inference | medium | agent conclusion from evidence |
| synthesis | medium | combined multiple sources |
| user_provided | confirmed | human-supplied fact |

Agents MUST NOT set `confidence=confirmed` for inferences or syntheses. The
system will auto-clamp and print a warning. Always include:
- `--claim-type` matching the claim's actual nature
- `--sources` (datasets like `court_exhibit`, `edgar`, `faa_registry`)
- `--evidence` (EFTA IDs, SDNY bates numbers, SEC accession numbers)
- `--source-quote` (with document ref → quote + page + assessment)

## Bridge Thread to /investigations/epstein

The `bridge_threads` field in config.yaml currently empty. After first seed,
look up the DB `investigation_threads.id` for the Epstein profile's thread
named "Apollo / Leon Black Financial" (local id 5 in epstein config.yaml).
Update `bridge_threads` so that leads mentioning Leon Black, Apollo, or
Leon-Black-adjacent associates are routed into this helicopter investigation
as well.

Entities already tracked in the shared DB (do NOT duplicate, enrich/link
instead):
- Hyperion Air, LLC (entity #46)
- Freedom Air Petroleum, LLC (entity #13) — likely alias for Freedom Air
  International; verify by jurisdiction/account before merging
- Shmitka Air (entity #357)
- FSF LLC (entity #395)
- Probable existing: Jeffrey Epstein, Darren K. Indyke, Lawrence Visoski,
  Richard D. Kahn, Harry Beller, Leon Black, Ghislaine Maxwell (verify in
  entity_tracker before creating)

## Corpus Tools Notes

- **DOJ Vol 11**: EFTA01339374 lives here with full OCR; search for "N722JE",
  "Freedom Air", "ASI Wings", "11800000", "1603473416" to surface the
  escrow-file pages.
- **LMSBAND / Unified**: verify overlap with DOJ Vol 11 (3 sources returning
  the same doc is redundancy, not corroboration).
- **FAA registry** (`ingest_faa.py`): use for N-number chain confirmation on
  N722JE (current owner Industrial Integrity Solutions LLC, CA), N162AE (now
  with TVPX as trustee), and N152AE (Aetna's other S-76C).
- **query_investigations.py**: use to search across the court exhibits
  ingested into this profile (EFTA01339374 OCR'd, Ex 56 Axia, Ex 86 JPM DDR).

## Mandatory SEC EDGAR Bundle for Aetna-side work

```bash
# Aetna subsidiaries and board composition over time
uv run python tools/query_edgar.py filings 0001122304 --form "10-K,DEF 14A,8-K" --start 2010-01-01 --end 2018-12-31 --output $WORKDIR/aetna-filings.json

# CVS Health post-merger filings covering ASI Wings through 2019 transfer window
uv run python tools/query_edgar.py filings 0000064803 --form "10-K,10-Q,8-K" --start 2018-11-01 --end 2020-06-30 --output $WORKDIR/cvs-filings.json

# Chiquita Brands plea-era filings (the 2007 March plea)
uv run python tools/query_edgar.py search "Chiquita Brands" --forms "10-K,DEF 14A,8-K,10-Q" --start 2005-01-01 --end 2012-12-31 --output $WORKDIR/chiquita-filings.json
```

## What Makes a Good Story Here

- Evidence that the 2011 sale was structured (leaseback, financing) rather
  than arm's-length: internal Aetna memos, a lease agreement in ASI Wings
  records, flight logs showing Epstein/Visoski as PIC during Aetna ownership.
- The 2019 transfer price (or documentation of zero consideration): FAA Form
  337, USVI corporate filings, CVS internal aircraft disposition records.
- The destination of the $11.8M after arriving at JPMorgan Panama: onward
  wires, foreign currency conversions, account closures.
- Any Aetna executive's personal connection to Epstein, Leon Black, Apollo,
  Chiquita, or the Davos/WEF network that ties back to this transaction.
- "Denise Cote" identity — the name referenced on every Aetna wire transfer
  as the payment authorizer; not the SDNY federal judge; finance/treasury
  employee not publicly indexed.

