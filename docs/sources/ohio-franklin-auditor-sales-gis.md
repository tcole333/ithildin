# Franklin County Auditor Sales Information GIS

Source ID: `us-oh-franklin-county-auditor-sales-gis`

Adapter: `tools/query_ohio_franklin_sales_gis.py`

Official source: [Franklin County Auditor `Sales Information` FeatureServer,
layer 0](https://gis.franklincountyohio.gov/hosting/rest/services/RealEstate/Sales_Information/FeatureServer/0)

The Auditor publishes a structured point layer of recent sale observations.
It complements the longer bulk appraisal and conveyance history with direct
parcel, conveyance, transaction-party, qualification, address, building, and
map-point fields. It is an Auditor representation, not a recorded-instrument
index or a parcel-boundary layer.

## Operations

```bash
WORKDIR=$(mktemp -d /tmp/osint-franklin-sales-XXXXXXXX)

uv run python tools/query_ohio_franklin_sales_gis.py source \
  --output "$WORKDIR/franklin-sales-source.json"
uv run python tools/query_ohio_franklin_sales_gis.py layers \
  --output "$WORKDIR/franklin-sales-layers.json"
uv run python tools/query_ohio_franklin_sales_gis.py schema \
  --output "$WORKDIR/franklin-sales-schema.json"
uv run python tools/query_ohio_franklin_sales_gis.py count \
  --output "$WORKDIR/franklin-sales-count.json"

uv run python tools/query_ohio_franklin_sales_gis.py parcel 010-000006 \
  --geometry --output "$WORKDIR/franklin-sales-parcel.json"
uv run python tools/query_ohio_franklin_sales_gis.py conveyance 00004012 \
  --output "$WORKDIR/franklin-sales-conveyance.json"
uv run python tools/query_ohio_franklin_sales_gis.py party \
  "LAMAR EQUITY INVESTMENTS LLC" \
  --output "$WORKDIR/franklin-sales-party.json"
uv run python tools/query_ohio_franklin_sales_gis.py date-range \
  --start 2024-01-01 --end 2024-12-31 \
  --output "$WORKDIR/franklin-sales-2024.json"
uv run python tools/query_ohio_franklin_sales_gis.py validity N \
  --output "$WORKDIR/franklin-sales-validity-n.json"
uv run python tools/query_ohio_franklin_sales_gis.py probe \
  --output "$WORKDIR/franklin-sales-probe.json"
```

`search` accepts `--field all`, `parcel`, `conveyance`, `party`, `address`,
or `object-id`. The dedicated parcel and conveyance operations are exact;
party search covers all four published grantor and grantee fields. Date bounds
are inclusive calendar dates. `ValidSale` is searched as a raw publisher
value rather than being converted into a binary statement about whether a
transaction occurred.

Record operations traverse matching rows in deterministic `OBJECTID` order.
With no `--limit`, the adapter exhausts the source match set. An explicit
limit returns a cursor bound to the operation, selector, schema, geometry
choice, and the source snapshot's matching count and `OBJECTID` boundary. The
cursor resumes after its recorded `OBJECTID` anchor and cannot silently
continue a different query. `--page-size` changes transport batching within
the service's published 2,000-row maximum; it does not change the requested
result set.

The shared router exposes the same source through `query_property.py`:

```bash
uv run python tools/query_property.py parcel 010-000006 \
  --source us-oh-franklin-county-auditor-sales-gis --jurisdiction 39049 \
  --geometry --ingest --output "$WORKDIR/franklin-shared-sale.json"

uv run python tools/query_property.py instrument 00004012 \
  --source us-oh-franklin-county-auditor-sales-gis --jurisdiction 39049 \
  --output "$WORKDIR/franklin-shared-conveyance.json"

uv run python tools/query_property.py search N --search-field validity \
  --source us-oh-franklin-county-auditor-sales-gis --jurisdiction 39049 \
  --output "$WORKDIR/franklin-shared-validity.json"
```

On this source, shared `owner` means a grantor/grantee transaction-party
search; it does not reinterpret a party as the current owner. Shared
`instrument` selects the Auditor's `ConveyanceNum` field, which is a useful
Recorder pivot but is not itself represented as a Recorder-issued identity.

## Verified source and layer contract

Live verification on 2026-07-31 found:

- service item `1ce134b7dabe45bdad4121193934a38d`;
- canonical layer 0, `Sales Details`, with 98,291 point-feature occurrences;
- `OBJECTID` as the ordered row locator and non-nullable `GlobalID` as the
  declared occurrence key;
- a 2,000-row native maximum, ordered queries, pagination, statistics, and
  distinct-value support;
- source CRS `WKID 102723` / latest `3735`, with requested geometry returned
  in EPSG:4326;
- no null service geometry among the 98,291 observed features, while zero rows
  had both raw `X_COORD` and `Y_COORD` attributes populated—request service
  geometry for coordinates and retain those empty attributes only as raw source
  fields;
- no observed null or blank `PARCELID` or `ConveyanceNum`; no observed null
  `GlobalID`; and 98,291 distinct GlobalIDs for 98,291 occurrences, with no
  duplicate group observed; and
- a source-managed sale-date span from 2023-01-03 through 2025-07-16.

Layers 1 through 4 are named current-year and prior-year sales, but each had
the same 98,291 rows, schema, and first `OBJECTID`/`GlobalID` as layer 0, with
no definition expression. Their difference is an Arcade renderer expression
and symbol. The adapter therefore queries layer 0 once and reports layers
1–4 as display aliases rather than separate datasets.

## Identity and field semantics

Every result preserves the feature occurrence. `GlobalID` is preferred; the
stable fallback combines service item ID, layer ID, and `OBJECTID` so a source
row remains attributable even if a future representation omits its GlobalID.
`OBJECTID` remains the source row locator, not a cross-release business key.
The probe checks that distinct non-null GlobalIDs equal total rows minus null
GlobalIDs, so fallback rows remain supported without allowing duplicate
non-null occurrence keys.

`PARCELID` is the parcel join. A normalized sale business event uses
`ConveyanceNum` plus `PARCELID`, separately from the feature occurrence.
`ParcelCount` is retained as the source's conveyance-cardinality observation;
it does not collapse the individual parcel occurrences attached to a
multi-parcel transaction.

The layer also preserves:

- sale date, price, year, instrument code, sale type, and raw `ValidSale`;
- two grantee and two grantor fields;
- parcel-active state, site address, ZIP code, subdivision/condominium name,
  tax and school districts, neighborhood, class, acreage, and map routing;
- dwelling and other structure fields such as area, year built, type, rooms,
  baths, condition, grade, and construction attributes;
- raw `X_COORD`/`Y_COORD` attributes, requested Esri point geometry, and
  update/edit dates (the raw coordinate attributes were empty in the live
  audit and are not a substitute for requested geometry);
  and
- raw attributes, source selectors, schema fingerprint, and exact source URL.

The live layer reported 56,936 `ValidSale=Y` rows and 41,355 `ValidSale=N`
rows. Of 61,933 rows with both a date and positive price, 5,001 were marked
`N`. Ingestion therefore preserves `ValidSale` as a qualification while
projecting a dated positive-price assessor sale observation regardless of
that value. The raw transaction remains distinguishable from any conclusion
that it was qualified, arm's-length, or valid for appraisal analysis.

## Lineage and complementary sources

- `us-oh-franklin-county-auditor-bulk` provides longer appraisal Sales and
  daily-conveyance release history, artifact hashes, and physical row
  provenance. Agreement with this GIS layer is same-authority redundancy.
- `us-oh-franklin-county-auditor-property` is the same Auditor's interactive
  property-detail representation.
- `us-oh-ogrip-statewide-parcels` adds the statewide standardized county-
  origin parcel representation and parcel polygons. Its overlapping Franklin
  fields are not a separate originating observation.
- `us-oh-franklin-county-recorder-publicsearch` is the distinct official
  recorded-instrument domain. Exact conveyance, parcel, party, and date joins
  can be used to verify the corresponding Recorder record and image.

## Health monitoring

The ten-request probe checks layer metadata, total and distinct-GlobalID
counts, null and blank join states, sale/update date statistics, and one exact
occurrence. Monitoring hashes the stable service, layer, schema, identity,
paging, alias-layer,
shared-operation, and lineage contract separately from the rolling feature
count, join-field state counts, sale-date span, `LASTUPDATE` span, and sentinel
values. A normal source refresh can therefore change rolling coverage without
being reported as structural drift.
