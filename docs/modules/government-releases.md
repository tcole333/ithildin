# DOJ and SEC Government Press Releases

Database: `datasets/government_releases.db`  
Schema contract: `tools/government_releases.py`  
CLI: `tools/government_release_corpus.py`

This primary-source sidecar contains official agency statements. It is separate
from `epstein_reporting.db`: a government press release is authoritative evidence
of what the agency announced, charged, alleged, settled, or concluded, but it is
not automatically proof that every allegation in the release is true.

## Confirmed source coverage

| Agency | Official source | Coverage and access |
|---|---|---|
| DOJ | `https://www.justice.gov/api/v1/press_releases.json` | Official News API; max 50 records/request; documented four requests/second ceiling |
| DOJ OPA archive | `/archive/opa/pr/{year}/{month}/` | Official historical archive, July 1994–January 2009 |
| SEC | `https://www.sec.gov/newsroom/press-releases` | Paginated official index, 2012–present |
| SEC archive | `/news/press/pressarchive/{year}press.shtml` | Official yearly indexes, 1997–2011 |

The DOJ interactive listing is sometimes protected by an interstitial; the
official JSON API is the supported ingestion route. The SEC source is distinct
from the existing enforcement corpus of litigation releases, administrative
proceedings, and AAERs.

## Initialize and ingest

```bash
uv run python tools/government_release_corpus.py init

# Resumable DOJ batches. Omit --max-pages (or use 0) for all remaining pages.
uv run python tools/government_release_corpus.py ingest-doj --max-pages 100
uv run python tools/government_release_corpus.py ingest-doj --title Epstein
uv run python tools/government_release_corpus.py discover-doj-archive
uv run python tools/government_release_corpus.py fetch-doj-archive --limit 500

# Discover every official SEC press-release URL and then fetch full text.
uv run python tools/government_release_corpus.py discover-sec \
  --start-year 1997 --end-year 2026
uv run python tools/government_release_corpus.py fetch-sec --limit 500
```

`ingest-doj` requests the explicit stable order `created ASC` and stores its next
page in a versioned `ingest_state` key after every committed API page. It is safe
to stop and resume, and an older cursor from a different ordering contract cannot
be reused accidentally. SEC discovery is idempotent; repeated fetch runs create
a new version only when the extracted content changes.

DOJ's `robots.txt` specifies a ten-second crawl delay for the historical site.
The archive commands default to that delay and a single worker. Monthly index
pages still make every legacy title and agency summary searchable immediately;
full-body retrieval is deliberately slower and resumable.

## Query

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/government_release_corpus.py search 'Jeffrey Epstein' \
  --agency DOJ --output "$WORKDIR/doj-epstein.json"
uv run python tools/government_release_corpus.py search 'JPMorgan' \
  --agency SEC --output "$WORKDIR/sec-jpmorgan.json"
uv run python tools/government_release_corpus.py show SEC-PR:2024-83 \
  --output "$WORKDIR/release.json"
uv run python tools/government_release_corpus.py stats \
  --output "$WORKDIR/government-release-stats.json"
```

Canonical internal references are `DOJ-PR:<uuid>` and
`SEC-PR:<release-number>`. Search/show output always includes the citable official
URL. When attaching a release to a reporting claim, prefer `reporting_corpus.py
link-release`; it stores the official URL as finding evidence and the internal ID
as the independence group.

## Evidence discipline

- Preserve words such as *alleged*, *charged*, *settled*, *admitted*, *convicted*,
  and *acquitted*.
- A charging announcement proves that the government filed or announced a
  charge, not that the defendant committed the charged conduct.
- A press release and the complaint/order it summarizes are related
  representations, not independent corroboration.
- Version history is retained because agencies can update headlines, body text,
  links, and disposition language.
