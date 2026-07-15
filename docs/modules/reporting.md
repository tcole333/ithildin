# Epstein Reporting Knowledge Layer

The reporting corpus answers a different question from the primary-document
corpora: what has been reported, by whom, based on what, who repeated it, and
whether later primary evidence supports or contradicts it.

Database: `datasets/epstein_reporting.db`  
Schema contract: `tools/epstein_reporting.py`  
CLI: `tools/reporting_corpus.py`  
Source inventory: `investigations/epstein/reporting_sources.yaml`

## Non-negotiable evidence boundary

A `reporting_item` is a publication. A `reporting_claim` is an attributed claim
made by that publication. Neither is automatically a finding.

A claim may be promoted to `investigation.db` only when all of these are true:

1. Its status is `primary_supported` or `independently_corroborated`.
2. A reviewer is recorded.
3. At least one `claim_source` is explicitly marked primary.
4. Every primary link contains a canonical evidence reference and source quote.
5. The claim has a subject suitable for canonical entity resolution.

The promotion is recorded in `claim_promotion`. Re-OCRs, syndications, rewrites,
and articles summarizing the same filing are not independent corroboration.

## Phase 1: initialize and seed existing institutional memory

```bash
uv run python tools/reporting_corpus.py init
uv run python tools/reporting_corpus.py discover-repository
uv run python tools/reporting_corpus.py stats
```

`discover-repository` scans the Epstein-specific paths in
`reporting_sources.yaml`, keeps only configured reporting domains, normalizes
URLs, and creates deduplicated candidates. It also loads publisher-level source
notes, including the investigation's author/source conflicts.

Fetch a bounded candidate batch. Text is not stored unless rights permit and
`--store-text` is explicitly supplied:

```bash
uv run python tools/reporting_corpus.py ingest-candidates --limit 50
uv run python tools/reporting_corpus.py ingest-candidates --limit 50 \
  --store-text --rights-status local_research
uv run python tools/reporting_corpus.py ingest-candidates --limit 1000 \
  --workers 4 --store-text --rights-status local_research
```

## Phase 2: historical backfill

Use multiple discovery channels; none is complete by itself.

| Channel | Best use | Limitation |
|---|---|---|
| Existing repository references | Recover already-used institutional knowledge | Biased toward prior investigation choices |
| Outlet archives and author pages | Core series and corrections | Search quality varies |
| Media Cloud CSV/API exports | Broad online-news discovery | Coverage begins when a feed was monitored; text is not downloadable |
| Common Crawl / Wayback | Recover known older or vanished URLs | Not a universal article full-text search |
| ProQuest, Nexis, Factiva | Print, paywalled, and historical backfill | Licensed access and export limits |
| Court filings and bibliographies | Find reporting cited by litigants and researchers | Discovery lead only |

Imports accept `.ris`, `.csv`, `.jsonl`, and `.ndjson`:

```bash
uv run python tools/reporting_corpus.py import-file licensed-export.ris --source approved_source
uv run python tools/reporting_corpus.py import-file mediacloud.csv --source mediacloud \
  --access-status open
```

Use `discover-file` when a bibliography should enter the ordinary fetch queue
rather than become metadata-only items immediately. This is useful for
publisher series indexes with opaque article IDs:

```bash
uv run python tools/reporting_corpus.py discover-file \
  investigations/epstein/reporting_historical_seed.jsonl \
  --source curated_series
uv run python tools/reporting_corpus.py ingest-candidates --limit 500 \
  --store-text --rights-status local_research
```

Configured `candidate_seed_files` are loaded idempotently by the update runner.
Maintained seeds include early profiles, Palm Beach archive captures, a
released-document-backed 2009–2018 bibliography, multilingual gap coverage, and
curated date backfills. Publisher redirects are resolved to the fetched
canonical item without recreating aliases; released-document IDs and richer
archived versions are preserved during canonical merges.

Verified publisher topic/series pages can seed their same-outlet story links:

```bash
uv run python tools/reporting_corpus.py discover-page \
  'https://www.lemonde.fr/affaire-epstein/' \
  --query epstein --query maxwell --publisher 'Le Monde' --language fr
```

Publisher-native search APIs must be discovered from the live search client
before use. Two currently verified examples are NRC's
`/nrseek/search/keyword` JSON endpoint and NBC News's public Queryly client at
`https://api.queryly.com/json.aspx`; exact audited results are persisted in the
multilingual seed rather than making these APIs permanent evidence URLs. The
Queryly certificate chain validates with system `curl` but may fail in the
bundled Python certificate store. Use the verified `curl` path and never bypass
TLS verification.

Configured `discovery_pages` are revisited by the update runner. A candidate
whose URL or visible title directly names Epstein/Maxwell can also be
materialized as a metadata-only bibliographic item without leaving the fetch
queue:

```bash
uv run python tools/reporting_corpus.py materialize-candidates \
  --method publisher_page --limit 5000
```

This keeps “article existence is verified” separate from “full text has been
retrieved.” `--workers` parallelizes network fetches only; SQLite writes remain
serialized in the parent process.

Discovery landing pages are link sources, not article records. Repository and
publisher-page discovery skip configured topic/index pages, and
`cleanup-navigation` removes any legacy landing-page items. When a canonical
article URL carries an exact calendar date (including Guardian month-name,
Le Monde numeric, and compact podcast paths), ingestion records that date and
the schema migration backfills it for older undated items.

Field aliases cover common title, URL, author, date, publication, language,
abstract, and full-text headers. Unknown exports should first be tested on a
small batch. Preserve the raw imported record in `item_version.metadata_json`.

### Georgia Tech licensed databases

Use the authenticated browser to search; do not automate login, bypass access
controls, or scrape beyond the database's permitted workflow. Georgia Tech's
eResource policy permits limited saving for personal academic use but prohibits
systematic/substantial reproduction and creation of a searchable archive from
licensed database content. Keep the query and aggregate coverage log in
`investigations/epstein/licensed_database_searches.yaml`.

1. Run each query family in `reporting_sources.yaml`, including multilingual and
   network terms rather than only `Jeffrey Epstein`.
2. Record database name, query, result count, date/source facets, and search date
   or adjacent research log.
3. Use the licensed index to identify gaps and high-value citations, then resolve
   those citations to publisher pages, archives, court filings, government
   records, or another source whose terms permit ingestion.
4. Import a licensed RIS/CSV export only when the applicable license or explicit
   text-and-data-mining permission allows the intended storage and use; record the
   permission context in the discovery-run metadata.
5. Search overlapping databases deliberately, then deduplicate by canonical URL,
   source-native ID, title/date, and later content hash. Database overlap is not
   corroboration.

For systematic backfill, divide the date range around major epochs: pre-2005;
Palm Beach investigation and NPA; 2008 conviction; 2009–2018 civil and financial
reporting; 2019 arrest; Maxwell prosecution; bank/USVI litigation; and current
document releases. Record zero-result searches as coverage evidence.

### Public archive recovery

Recover known publisher URLs through official public indexes. Wayback CDX is
tried first; if its replay is missing or only a placeholder, Common Crawl's
current indexes and WARC byte ranges are used as a fallback:

```bash
uv run python tools/reporting_corpus.py recover-archives \
  --access-status paywalled --limit 50 --store-text
uv run python tools/reporting_corpus.py recover-archives \
  --failed-candidates --provider auto --limit 50 --store-text
uv run python tools/reporting_corpus.py recover-archives \
  --item-id 42 --provider commoncrawl --store-text
```

For archive.is/archive.today, supply a known snapshot explicitly; the service
does not expose a dependable public search API and may rate-limit automated
lookups:

```bash
uv run python tools/reporting_corpus.py ingest-archive-url \
  'https://publisher.example/original-story' 'https://archive.is/ABCDE' \
  --store-text
```

Archive captures are versions of the original publisher item. They retain the
original canonical URL, publisher, and independence group; an archive provider
is a retrieval path, not an additional corroborating source. Capture timestamp,
digest, WARC collection/range, and replay URL are stored in version metadata.
Empty or non-HTML replays are rejected rather than indexed.

Publisher-domain Wayback discovery is independently resumable and stops after
five consecutive archive errors by default. This prevents a CDX outage from
turning every configured publisher into a long timeout; rerun the same command
when the archive is healthy, or set `--max-consecutive-errors 0` deliberately.
Keep a long archive pass in a supervised terminal or worker session. Codex task
shells may reap detached `nohup ... &` children when the launching exec cell
closes, even when the command printed a PID; verify both the live process and a
new incomplete `archive_recovery` row before treating the pass as active.

## Phase 3: continuous monitoring

GDELT's verified DOC 2.0 endpoint is used only for its rolling recent window:

```bash
uv run python tools/reporting_corpus.py discover-gdelt '"Jeffrey Epstein"' \
  --timespan 3m --limit 250
uv run python tools/reporting_corpus.py discover-feed FEED_URL --query Epstein
uv run python tools/reporting_corpus.py ingest-candidates --limit 100
```

Do not invent RSS or API endpoints. Add a feed only after opening it and
confirming that it returns RSS or Atom. A scheduled job can run the configured
queries later, but scheduling is separate from corpus semantics.

Repeated ingestion is safe. URLs are normalized, unchanged versions reuse their
content hash, changed pages create a new `item_version`, and the prior current
version becomes `superseded`.

A bounded update runner combines configured repository discovery, all configured
GDELT queries, candidate ingestion, and exact-content duplicate detection:

```bash
uv run python scripts/update_reporting_corpus.py --ingest-limit 50
uv run python scripts/update_reporting_corpus.py --ingest-limit 50 \
  --archive-limit 25 --store-text --rights-status local_research
uv run python scripts/update_reporting_corpus.py --discover-wayback \
  --ingest-limit 500 --archive-limit 100 --store-text \
  --rights-status local_research
# Fast discovery-only smoke run:
uv run python scripts/update_reporting_corpus.py --max-queries 1 --ingest-limit 0
# Stop an unhealthy GDELT pass after three consecutive provider errors (default):
uv run python scripts/update_reporting_corpus.py --gdelt-delay 12 \
  --gdelt-max-consecutive-errors 3 --ingest-limit 500
# Fully offline runner smoke test:
uv run python scripts/update_reporting_corpus.py --skip-repository --skip-seeds \
  --skip-pages --skip-gdelt --ingest-limit 0
```

The runner is not itself a scheduler. Scheduling it requires a separately
approved automation; the database retains every discovery run and zero-result
query for coverage auditing.

GDELT query failures are also durable coverage records. The runner stops its
GDELT phase after three consecutive provider errors by default, then continues
with candidate ingestion and deduplication. Set
`--gdelt-max-consecutive-errors 0` only for an intentionally unbounded provider
pass; later runs safely retry the uncompleted query family.

## Phase 4: claims, lineage, and primary verification

Create the smallest independently testable claim, retaining attribution and a
short locator/excerpt:

```bash
uv run python tools/reporting_corpus.py add-claim 42 \
  --claim 'The article reported that X paid Y in 2015.' \
  --subject X --predicate paid --object Y --date 2015 \
  --attribution 'named court filing' --locator 'paragraph 14' --by analyst
```

Link its reported basis and then primary evidence:

```bash
uv run python tools/reporting_corpus.py link-evidence 7 \
  --ref EFTA01234567 --source-type primary_document --primary \
  --quote 'Verbatim primary-source support' --page p.3 \
  --independence-group DOJ-DS10 --assessment 'Directly supports amount and parties'

uv run python tools/reporting_corpus.py verify-claim 7 \
  --status primary_supported --confidence high --by reviewer
```

When support is a DOJ or SEC press release, use the government sidecar link so
the corpus retains both its stable internal ID and citable official URL:

```bash
uv run python tools/reporting_corpus.py link-release 7 SEC-PR:2024-83 \
  --quote 'Short verbatim support from the official release' \
  --assessment 'Supports only that the agency announced the action'
```

Record genealogy rather than counting repetitions:

```bash
uv run python tools/reporting_corpus.py relate item 51 42 rewrites \
  --assessment 'Repeats the same unnamed-source claim'
uv run python tools/reporting_corpus.py relate claim 12 7 contradicts
uv run python tools/reporting_corpus.py lineage claim 7
uv run python tools/reporting_corpus.py conflicts
```

Promote only after review:

```bash
uv run python tools/reporting_corpus.py promote 7 --by reviewer --confidence high
```

## Analysis and quality-control commands

```bash
uv run python tools/reporting_corpus.py search 'Southern Trust' --output "$WORKDIR/items.json"
uv run python tools/reporting_corpus.py claims JPMorgan --output "$WORKDIR/claims.json"
uv run python tools/reporting_corpus.py primary-gaps --output "$WORKDIR/gaps.json"
uv run python tools/reporting_corpus.py latest --output "$WORKDIR/latest.json"
uv run python tools/reporting_corpus.py review-queue --output "$WORKDIR/review.json"
uv run python tools/reporting_corpus.py import-claims claims.jsonl --by analyst
uv run python tools/reporting_corpus.py coverage --output "$WORKDIR/coverage.json"
uv run python tools/reporting_corpus.py resolve-entities --limit 1000
uv run python tools/reporting_corpus.py stats --output "$WORKDIR/stats.json"
```

Entity resolution creates candidate links to canonical `investigation.db`
entities; it never creates new canonical entities. Review ambiguous names before
accepting them.

## Rights and preservation

- Do not bypass paywalls or authentication controls.
- Store full text only when the access terms permit local research storage.
- Metadata-only records retain title, author, publication, dates, URL, abstract,
  source-native ID, retrieval history, and hashes where available.
- Do not republish licensed full text. Public-facing products should cite the
  publisher URL and use only appropriately short supporting excerpts.
- Preserve corrections, retractions, changed headlines, and inaccessible pages
  as versions; do not overwrite history.
