# Santa Fe County property sources

Verified 2026-07-31. The first integration is the official Santa Fe County
Assessor Accounts layer. The other routes below are retained as field-matched
enrichment and provenance paths.

## Standalone adapter

`tools/query_santa_fe_property.py` queries the parcel/account layer used by the
county Tax Parcel Viewer:

```bash
uv run python tools/query_santa_fe_property.py owner "SANTA FE COUNTY" \
  --output /tmp/santa-fe-county.json
uv run python tools/query_santa_fe_property.py address "18 DINKLE RD" \
  --output /tmp/santa-fe-address.json
uv run python tools/query_santa_fe_property.py parcel 910002704 \
  --output /tmp/santa-fe-parcel.json
uv run python tools/query_santa_fe_property.py probe \
  --output /tmp/santa-fe-probe.json
uv run python tools/query_santa_fe_property.py routes --json
```

Search modes cover owner name, situs address, owner mailing address, UPC,
parcel number, alternate ID, and ArcGIS `OBJECTID`. `--active-only` is
available when the investigation needs the source's `active_status = A`
subset. Geometry is optional and is transformed to EPSG:4326.

The adapter exposes the identity basis and tier on every record. A UPC is the
preferred durable parcel-account identity, with parcel number as the fallback.
Rows that have only an ArcGIS `OBJECTID` are labeled
`parcel_geometry_feature_occurrence`, carry `native_parcel_id: null`, and are
not eligible for parcel projection. Their `OBJECTID` remains available as
`native_feature_id` for retrieving the same layer occurrence.

The layer publishes a native `maxRecordCount` of 2,000 and declares ordered
pagination. That is the size of one ArcGIS transfer page, not the size of the
county dataset. When the caller does not pass `--limit` or `--max-records`, the
adapter walks technical pages until the matching source result is exhausted.
A caller-selected result window returns an ArcGIS continuation cursor.

Normalized records preserve:

- UPC, parcel number, alternate ID, status, and effective dates;
- Assessor owner, situs, and mailing observations;
- legal description, PLSS and subdivision components, map number, and acreage;
- current and prior assessment components using the source field names;
- exemption indicators;
- Assessor-supplied recording number, book/page, `ADEED`, and `ADHST` join
  hints;
- the complete raw ArcGIS attributes and response/layer schema fingerprints.

Owner fields describe the Assessor account. Clerk instruments are the
independent source for recorded title events. Parcel polygons are cadastral GIS
geometry.

## Verified route and lineage map

| Route | Verified access | Record class | Relationship |
|---|---|---|---|
| [Tax Parcel Viewer](https://sfcomaps.santafecountynm.gov/mapsvc/apps/webappviewer/index.html?id=7ba6293895454413a140b25200f40fda) → `LAND/Accounts/MapServer/0` | Anonymous ArcGIS query; 90,695 feature occurrences observed | Live parcel/account and assessment layer | Primary adapter |
| Portal item `98a3e4e30d7c4495a6d74499e6996a44` → `Hosted/ParcelDownload/FeatureServer/0` | Anonymous query plus advertised sync/extract; 81,841 rows observed | Published parcel snapshot | Same Assessor records, narrower snapshot |
| Portal item `d7a8094e799a416d8863ebe6be4e35e1` → `LAND/Parcels/MapServer/0` | Anonymous ArcGIS query | Parcel geometry and summarized account fields | Same Assessor records, alternate layer |
| [Assessor Document Manager](https://www.santafecountynm.gov/assessor/tools/document-manager) | Public session; exact property ID, valuation year, and notice type; PDF artifact verified | Annual Notice of Value | Same authority, field-matched document |
| [Clerk real-estate records access](https://www.santafecountynm.gov/clerk/divisions/research-public-records-access) → [ClerkTrack](https://clerktrackweb.santafecountynm.gov/CTWeb/login.aspx) | County-published index guest login verified | Recorded instrument index | Independent recorded-document evidence |
| [Treasurer property-tax search](https://paydici.com/santa-fe-treasurer-nm/search/property-tax-search-group) | Interactive search configuration verified for account number, name, and address; reCAPTCHA-backed asynchronous request | Tax bill, balance, and payment observation | Distinct tax record |

The Assessor's [GIS description](https://archives.santafecountynm.gov/assessor/staff_directory/gis)
states that the cadastral parcel layer is its land record and that UPC links
spatial and tabular account data.

### Live layer

The Assessor page links ArcGIS application item
`7ba6293895454413a140b25200f40fda`. Its application data names web map
`f845a6fead3b464ca52880a0d618dc9f`; that web map names:

```text
https://sfcomaps.santafecountynm.gov/restsvc/rest/services/
LAND/Accounts/MapServer/0
```

The layer advertises `Map,Query,Data`, ordered pagination, and a 2,000-record
native page. At verification it contained 90,695 feature occurrences, 87,416
with a UPC, and 87,332 with both UPC and active status `A`. Some low
`OBJECTID` geometry occurrences have no populated account attributes, so the
adapter preserves those rows as feature occurrences rather than treating the
layer-local `OBJECTID` as a durable parcel identifier.

### ParcelDownload snapshot

The official portal catalogs `ParcelDownload` as a public Feature Service and
returns service item ID `98a3e4e30d7c4495a6d74499e6996a44`. The item still
publishes this legacy hostname:

```text
https://sfcserver.co.santa-fe.nm.us/restsvc/rest/services/
Hosted/ParcelDownload/FeatureServer
```

That hostname did not resolve during verification. Preserving the exact
service path on the current county ArcGIS host returned the same
`serviceItemId`:

```text
https://sfcomaps.santafecountynm.gov/restsvc/rest/services/
Hosted/ParcelDownload/FeatureServer/0
```

The snapshot has 81,841 rows and shortened export-style field names. UPC,
parcel number, owner, address, legal, valuation, GlobalID, and geometry fields
match the live Assessor family. It is useful for bulk acquisition and
cross-checking extraction completeness, but it is not independent
corroboration.

### Notice of Value documents

The Document Manager has an explicit public-login flow. Its only application
is `NOTICE_OF_VALUES`, searchable by:

- `PROPERTY ID` (the live layer's `parcel_number`);
- `VALUATION YEAR`;
- `NOTICE TYPE`.

An exact lookup for property ID `99312914` returned its 2026 real-property
notice and a one-page PDF. The PDF repeated the property ID, formatted UPC,
owner/mailing address, situs, legal description, full value, taxable value,
exemptions, and estimated tax. This makes the notice a strong same-authority
artifact for a selected account and valuation year.

### ClerkTrack recorded-document index

The Clerk's official access page links ClerkTrack and states that index
searches are free. The ClerkTrack login page publishes an index-only guest
login. A verified read-only search exposed:

- instrument number;
- book and page;
- recording date;
- document type;
- grantors and grantees;
- legal description and structured legal information.

The result grid publishes 25 rows per native page. A test search for
`MAYNARD*` returned 314 records across 13 source pages. The detail selector is
session scoped. `query_santa_fe_clerktrack.py` and its shared
`query_property.py` routes reacquire the exact instrument in a fresh guest
session, use the selector issued for that result, and verify instrument number,
book, page, recording date, and document type before accepting the detail.
The selector is never persisted.

The Clerk index is independent evidence of recorded events. Multiple Assessor
layers that repeat the same deed or owner hint remain one Assessor
observation. See
[`santa-fe-county-clerktrack.md`](santa-fe-county-clerktrack.md) for the shared
search, detail, ingestion, and fixed-budget monitor contracts.

### Treasurer tax search

The county Treasurer links Point & Pay/Paydici. Its public page declares
account-number, name, and address selectors and exposes tax-year, tax paid,
interest, penalty, collection-fee, and amount-due fields in the client
configuration. Search submission uses reCAPTCHA and asynchronous polling, so
the route is currently best treated as an interactive enrichment path rather
than a headless API adapter.

## Reusable discovery lesson

An ArcGIS application's item-data response or a service URL in portal metadata
is not the final availability test. For a county-hosted Portal:

1. read the application item and application data;
2. follow its web-map item;
3. extract the operational layer URL;
4. search the same official portal for related services and download items;
5. when portal metadata contains a retired hostname, preserve the exact
   service path on the portal's current service host;
6. require matching item/service identity and compatible schema before
   classifying the route as the same source;
7. label snapshots, map layers, and source documents from the same office as
   alternate representations rather than added corroboration.

This sequence recovered both the live Accounts layer and the ParcelDownload
snapshot without inventing an endpoint.

## Focused validation

```bash
.venv/bin/pytest -q tests/test_query_santa_fe_property.py \
  tests/test_santa_fe_property_shared_integration.py
.venv/bin/ruff check tools/query_santa_fe_property.py \
  tools/query_property.py tools/ingest_property_records.py \
  tools/public_records_monitor.py tests/test_query_santa_fe_property.py \
  tests/test_santa_fe_property_shared_integration.py
```

## Shared lifecycle

The same source is available through `tools/query_property.py`:

```bash
uv run python tools/query_property.py owner "SANTA FE COUNTY" \
  --source us-nm-santa-fe-assessor-accounts --jurisdiction 35049 \
  --output "$WORKDIR/santa-fe-owner.json"
uv run python tools/query_property.py search "PO BOX 276" \
  --source us-nm-santa-fe-assessor-accounts --search-field mailing \
  --output "$WORKDIR/santa-fe-mailing.json"
uv run python tools/query_property.py parcel 910002704 \
  --source us-nm-santa-fe-assessor-accounts --geometry --ingest \
  --output "$WORKDIR/santa-fe-parcel.json"
uv run python tools/query_property.py map 249 \
  --source us-nm-santa-fe-assessor-accounts \
  --output "$WORKDIR/santa-fe-feature.json"
uv run python tools/query_property.py discovery routes \
  --source us-nm-santa-fe-assessor-accounts \
  --output "$WORKDIR/santa-fe-routes.json"
uv run python tools/query_property.py discovery metadata \
  --source us-nm-santa-fe-assessor-accounts \
  --output "$WORKDIR/santa-fe-metadata.json"
uv run python tools/public_records_monitor.py run \
  us-nm-santa-fe-assessor-accounts \
  --output "$WORKDIR/santa-fe-monitor.json"
```

Omitting a result limit leaves the ArcGIS traversal unbounded by the adapter;
the native transfer size remains technical pagination. Shared `search` selects
owner by default and accepts `address`, `mailing`, `parcel`, or `objectid`
through `--search-field`. `map` treats its selector as an `OBJECTID` and asks
for geometry. `discovery` returns either the lineage-aware route map or the
validated layer metadata.

Ingestion creates parcel snapshots only when the row publishes a UPC or parcel
number. An `OBJECTID`-only geometry row is retained as a
`parcel_geometry_feature_occurrence` observation and never projected as a
durable parcel. Assessor owner names become `assessment_roll` assertions.
Situs and mailing addresses and parcel geometry use their dedicated sidecar
tables; legal, classification, exemption, and join-hint fields remain in the
full parcel snapshot.

The layer labels its valuation groups only `current` and `prior`. The
normalized assessment rows therefore use `source-period:current` and
`source-period:prior`, retain `year_published: false`, and do not manufacture a
tax year. Recording number, book/page, `ADEED`, and `ADHST` remain join hints;
they do not create instruments, sales, or title assertions.

The fixed monitor makes two requests: one layer-metadata request and one exact
county-owned UPC lookup. Its route-contract hash covers route identities,
paging, durable/feature identity, and lineage. Owner names, assessment values,
and published counts are rolling observations; layer schema has its own hash.
