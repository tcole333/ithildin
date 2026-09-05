# Santa Fe County ClerkTrack recorded documents

Verified 2026-07-31. The standalone adapter uses the Santa Fe County Clerk's
published index guest route and source ID
`us-nm-santa-fe-clerktrack-index`.

## Access and commands

The County Clerk's
[Public Records Access page](https://www.santafecountynm.gov/clerk/divisions/public-records-access)
links
[ClerkTrack](https://clerktrackweb.santafecountynm.gov/CTWeb/login.aspx).
ClerkTrack publishes `INDEX` / `INDEX` for free index-only access and
`PUBLIC` / `PUBLIC` for its document-purchase workflow.

```bash
uv run python tools/query_santa_fe_clerktrack.py search \
  --name "MAYNARD*" --output /tmp/santa-fe-recordings.json
uv run python tools/query_santa_fe_clerktrack.py search \
  --instrument 1019405 --output /tmp/santa-fe-instrument-index.json
uv run python tools/query_santa_fe_clerktrack.py search \
  --from-date 1998-04-01 --to-date 1998-04-30 \
  --document-type "QUITCLAIM DEED" \
  --output /tmp/santa-fe-quitclaims.json
uv run python tools/query_santa_fe_clerktrack.py detail 1019405 \
  --output /tmp/santa-fe-instrument-detail.json
uv run python tools/query_santa_fe_clerktrack.py probe \
  --output /tmp/santa-fe-clerktrack-probe.json
uv run python tools/query_santa_fe_clerktrack.py routes --json
```

Search exposes the source's party-name and role, recording-date, instrument,
book/page, document-type, legal-description, subdivision, lot, block, tract,
section, township, range, unit, and additional-information selectors. Party
names accept ClerkTrack's published `*` wildcard. Document-type labels are
resolved against the live multi-select inventory rather than copied into the
adapter.

## Acquisition and result grain

One search record is one County Clerk recorded-instrument index row. It
preserves:

- instrument number, book, page, recording date, and document type;
- the source-formatted grantor and grantee displays;
- legal-description and legal-information displays;
- the source's current last-index date;
- stable form, document-type inventory, and result-schema fingerprints;
- instrument and book/page keys for joining to independently produced
  Assessor observations.

ClerkTrack currently publishes 25 rows per native result page. That is a
transfer page, not a dataset limit. With no `--limit`, the adapter validates
and traverses every source page. A caller-selected `--limit` returns a
query-bound continuation cursor.

Each cursor binds its position to the source total, page count, last-index
date, result schema, and a fingerprint of the stable first-page instrument
identities. A resumed search opens a new session and rejects a changed
snapshot instead of silently skipping or duplicating rows. Cursor state does
not contain ClerkTrack session values or detail selectors.

The traversal checks the source-reported total against its native page count
and row counts, requires stable instrument ordering, and rejects repeated
instrument identities across fetched pages. These checks describe
completeness; they do not impose a local result ceiling.

## Detail retrieval

The result grid's `viewdetails.aspx?param=...` value is opaque
session/query-generated retrieval state. It is not a durable document
identifier. The `detail` and `probe` commands therefore:

1. start with a new public index session;
2. search the exact published instrument number;
3. require one exact index row;
4. use the selector issued for that row in the active session;
5. verify the visible instrument number, book, page, recording date, and
   document type before returning detail metadata.

Normalized output stores the stable instrument identity and the verification
result, not the opaque selector. Detail adds separated grantor and grantee
names, structured legal-information rows, submitter/address/location fields
when published, and additional descriptions. It remains another view of the
same Clerk instrument, not independent corroboration of the index row.

The probe uses instrument `1019405` as a visible sentinel. A missing or changed
sentinel is reported as source change rather than an authoritative empty
search.

## Shared lifecycle

The shared property router exposes the verified search fields, exact detail,
route discovery, and probe:

```bash
uv run python tools/query_property.py owner "MAYNARD*" \
  --source us-nm-santa-fe-clerktrack-index --jurisdiction 35049 \
  --output "$WORKDIR/santa-fe-clerk-parties.json"
uv run python tools/query_property.py search "1477/604" \
  --source us-nm-santa-fe-clerktrack-index --search-field book-page \
  --output "$WORKDIR/santa-fe-clerk-book-page.json"
uv run python tools/query_property.py instrument 1019405 \
  --source us-nm-santa-fe-clerktrack-index --ingest \
  --output "$WORKDIR/santa-fe-clerk-detail.json"
uv run python tools/query_property.py discovery routes \
  --source us-nm-santa-fe-clerktrack-index \
  --output "$WORKDIR/santa-fe-clerk-routes.json"
uv run python tools/public_records_monitor.py run \
  us-nm-santa-fe-clerktrack-index \
  --output "$WORKDIR/santa-fe-clerk-monitor.json"
```

An omitted caller limit traverses every source-reported native page. Shared
`search` accepts party/name, grantor, grantee, instrument, book, page,
book-page, recording-date, document-type, legal, subdivision, lot, block,
tract, section, township, range, unit, and additional-information selectors.
`instrument` and `detail` both perform the fresh-session exact lookup.

Ingestion creates one recorded-instrument identity per instrument number.
Index grantor and grantee displays remain aggregate snapshot observations;
detail rows add the individually published grantor and grantee roles. Book,
page, recording date, type, legal text, descriptions, and Assessor join keys
remain instrument metadata. Neither index nor detail metadata creates a
current-owner or title assertion, and no document artifact is created because
these operations do not retrieve image bytes.

The monitor uses the exact instrument in a five-request budget: login page,
guest login, search form, exact result list, and detail. It dynamically checks
list/detail agreement and fetches no image. Route, form, identity, paging,
fresh-session reacquisition, and lineage contracts are hashed separately from
the rolling index-through date, party/legal counts, and other detail content.

## Complementary routes

| Route | Record or artifact | Relationship |
|---|---|---|
| ClerkTrack index search | Recorded-instrument index row | Primary implemented source; independent Clerk evidence |
| ClerkTrack detail | Expanded metadata for the selected instrument | Same Clerk instrument |
| ClerkTrack `PUBLIC` workflow | Purchased recorded-document image | Underlying artifact from the same Clerk |
| ClerkTrack Index Books | Historic grantor/grantee index-book page | Same Clerk authority; useful historic complement |
| Clerk instrument-number copy request or in-person research | Official document copy | Same Clerk artifact through a human acquisition route |
| Santa Fe County Assessor Accounts layer | Parcel/account observation with deed, instrument, and book/page hints | Independently produced field-matched source |
| Santa Fe County Treasurer property-tax search | Tax account, balance, and payment observation | Distinct official tax-record complement |

If the interactive index route is unavailable, the document-purchase or Clerk
copy-request routes can recover the same underlying Clerk artifact. Index
Books can extend historic name research. The Assessor Accounts layer can
surface candidate parcel, deed, instrument, or book/page values for a later
Clerk lookup, but an Assessor representation is not a second copy of the
Clerk's recorded event. Treasurer results add a separately produced tax
observation rather than another Clerk representation.

## Reusable process lesson

ASP.NET WebForms links often mix durable record identity with temporary page
state. A reliable integration separates them:

1. inventory the published form controls and source page-size contract;
2. retain the complete WebForms state only while making the next request;
3. persist the source's stable document identity;
4. reacquire an opaque detail selector through an exact lookup in the current
   session;
5. verify visible identity fields before accepting the detail;
6. bind continuation positions to a token-free result snapshot;
7. classify index, detail, purchased image, and staff copy by lineage so
   multiple delivery routes for one Clerk artifact are not counted as
   independent corroboration.

This pattern applies to other recorder and court systems that issue opaque
row selectors while publishing stable instrument, docket, or filing numbers.

## Focused validation

```bash
.venv/bin/pytest -q tests/test_query_santa_fe_clerktrack.py \
  tests/test_santa_fe_clerktrack_shared_integration.py
.venv/bin/ruff check tools/query_santa_fe_clerktrack.py \
  tools/query_property.py tools/ingest_property_records.py \
  tools/public_records_monitor.py tests/test_query_santa_fe_clerktrack.py \
  tests/test_santa_fe_clerktrack_shared_integration.py
.venv/bin/python -m py_compile tools/query_santa_fe_clerktrack.py \
  tests/test_query_santa_fe_clerktrack.py \
  tests/test_santa_fe_clerktrack_shared_integration.py
```
