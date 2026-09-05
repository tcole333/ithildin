# Wyoming DOR statewide parcels

Verified 2026-07-31. The Wyoming Department of Revenue (DOR), Property Tax
Division publishes a current annual parcel layer assembled from county tax-roll
and cadastral data. The standalone adapter queries the official 2026 hosted
Feature Service while preserving its annual parcel/account joins separately
from every raw polygon occurrence.

## Current official release

- Source ID: `us-wy-dor-statewide-parcels`
- Official application: [`4bb9a66f7287402b8f650aa9f21d3fa5`](https://wyo-prop-div.maps.arcgis.com/apps/webappviewer/index.html?id=4bb9a66f7287402b8f650aa9f21d3fa5)
- Application title: `Wyoming Statewide Parcel and Tax District Viewer`
- Observed application subtitle: `Current as of January 1, 2026`
- Official item: [`9ab04f655f5b4e398d9f2f070d2d29bb`](https://www.arcgis.com/home/item.html?id=9ab04f655f5b4e398d9f2f070d2d29bb)
- Item title: `Wyoming Parcels for 2026`
- Publisher account: `dave.chapman@wyo.gov`
- Layer: `Wyoming_Parcels_for_2026`, ID `0`
- Service:
  `https://services3.arcgis.com/r0iJ85SKZ4zAzz3P/arcgis/rest/services/Wyoming_Parcels_for_2026/FeatureServer/0`
- Coverage: 373,666 feature occurrences across all 23 Wyoming counties
- Tax year: every observed row publishes `2026`

The DOR [Maps & GIS Data page](https://wyo-prop-div.wyo.gov/tax-districts/maps-gis-data)
links the statewide parcel viewer. Wyoming Enterprise Technology Services also
lists the viewer under DOR on its official
[GeoResources page](https://ets.wyo.gov/gis-office/georesources).
The application item and application data provide a stable publisher root. Its
query widget currently names the implemented parcel layer and exposes the
published `accountno` and `parcelnb` selectors. Discovery and monitoring check
that app-to-layer agreement rather than relying only on a release-specific
service URL.

The layer is a public polygon FeatureServer with `Query`, ordered pagination,
and a native `maxRecordCount` of 2,000. That value is one transfer-page size,
not a result ceiling. With no `--limit` or `--max-records`, the adapter follows
ordered `FID ASC` pages until the matching source result is exhausted. A
caller-selected window returns an ArcGIS continuation cursor.

## Standalone adapter

```bash
# Annual owner observations; surname matches remain unresolved candidates
uv run python tools/query_wy_dor_parcels.py owner "STATE OF WYOMING" \
  --output /tmp/wy-owner.json

# Published parcel and property-account identifiers
uv run python tools/query_wy_dor_parcels.py parcel 49720332401200 \
  --jurisdiction Campbell --output /tmp/wy-parcel.json
uv run python tools/query_wy_dor_parcels.py account R0059774 \
  --output /tmp/wy-account.json

# County, address, mailing, and legal-description searches
uv run python tools/query_wy_dor_parcels.py county Campbell \
  --output /tmp/wy-campbell.json
uv run python tools/query_wy_dor_parcels.py situs "KETTLESON XING" --json
uv run python tools/query_wy_dor_parcels.py mailing "BISHOP BLVD" --json
uv run python tools/query_wy_dor_parcels.py legal "LEGACY RIDGE" --json

# One release occurrence, with or without its WGS84 polygon
uv run python tools/query_wy_dor_parcels.py fid 30558 --json
uv run python tools/query_wy_dor_parcels.py geometry 30558 --json

# WGS84 spatial intersection
uv run python tools/query_wy_dor_parcels.py point -105.5013 44.2526 --json
uv run python tools/query_wy_dor_parcels.py bbox \
  -105.51 44.24 -105.49 44.27 --geometry --json

# Source, county coverage, identity audit, lineage, live schema, and sentinel
uv run python tools/query_wy_dor_parcels.py discovery source --json
uv run python tools/query_wy_dor_parcels.py discovery counties --json
uv run python tools/query_wy_dor_parcels.py discovery identity --json
uv run python tools/query_wy_dor_parcels.py discovery routes --json
uv run python tools/query_wy_dor_parcels.py discovery agreement --json
uv run python tools/query_wy_dor_parcels.py discovery metadata --json
uv run python tools/query_wy_dor_parcels.py probe --json
```

Owner, parcel, account, situs, mailing, and legal searches accept `contains`,
`starts`, or `exact`. Parcel and account default to exact matching; text fields
default to contains. `--jurisdiction` and `--tax-year` add exact source-field
filters. `--geometry` includes each returned WGS84 feature instead of changing
the record grain.

## Annual identity and raw occurrence audit

The source has two legitimate grains:

1. an annual tax-roll parcel/account join; and
2. each published polygon feature occurrence, identified by `FID`.

The distinction is material. Grouping the complete layer by:

```text
(taxyear, jurisdicti, parcelnb, accountno)
```

found 84 FIDs for the largest usable tuple:

```text
2026 / LINCOLN / 37181840001700 / R0015471
```

A row sample showed the same owner, mailing, situs, legal, value, acreage, tax
district, parcel, and account payload on each FID, with different shape area
and length. The tuple is therefore one annual business join represented by 84
geometry occurrences. The adapter emits all 84 raw features, gives each a
different occurrence canonical reference based on `FID`, and gives them one
shared `same_annual_record_key` and annual parcel canonical reference. It
neither manufactures 84 parcels nor collapses the raw geometry features. This
is the Wyoming source-specific instance of methodology observation #2169.

`FID` is a release occurrence, not an identity carried across annual releases.
The numeric `ID` field is retained separately as source payload.

### Blank values and fallback keys

ArcGIS `COUNT(field)` reported all 373,666 rows as non-null for `taxyear`,
`jurisdicti`, `parcelnb`, and `accountno`, but explicit string checks found
source blanks encoded as a single space:

| Observation | Feature occurrences |
|---|---:|
| Blank parcel and blank account | 1,214 |
| Blank account, including the rows above | 40,487 |
| Non-specific parcel label with blank account | 1,799 |

The observed high-frequency non-specific labels were `BLM`, `STATE`, `ROW`,
`NO PIN`, and `99999999999999`. They remain in `parcel_number` and raw source
attributes, but without a specific account they do not define one annual
parcel join.

The normalized 2026 identity bases reconcile to the complete layer:

| Accepted basis | Occurrences | Annual join fields |
|---|---:|---|
| Full parcel/account | 333,179 | tax year + jurisdiction + parcel + account |
| Specific parcel only | 37,474 | tax year + jurisdiction + parcel |
| Specific account only | 0 observed | tax year + jurisdiction + account |
| Release occurrence only | 3,013 | FID; 1,214 blank-both plus 1,799 non-specific parcel labels without account |

The account-only fallback is represented in the normalization contract for a
later annual release, but it was not present in the audited 2026 layer. A row
becomes occurrence-only when neither published parcel nor account supplies a
sufficiently specific annual join. Numeric zero assessment and land values are
preserved as zero; whitespace-only fields normalize to null.

The audit data and representative multipart, parcel-only, and occurrence-only
rows are captured under `tests/fixtures/public_records/wy_dor_parcels/`.

## Normalized annual context

Every feature occurrence retains:

- tax year, source jurisdiction, normalized county name/FIPS/GEOID;
- parcel number, account number, `FID`, and source `ID`;
- primary and secondary annual tax-roll owner labels;
- situs and structured mailing observations;
- legal description;
- actual and assessed values plus the default tax district;
- reported gross acres and square feet;
- source shape area and length; and
- complete raw attributes and response/layer schema fingerprints.

Owner fields are annual assessment-roll context, not a recorded title
conclusion. An owner or surname result has
`resolution_status: unresolved_candidate`; jurisdiction, parcel/account,
address, legal, and recorded-instrument evidence can resolve the candidate.

## Exact bounded sentinel

The probe uses a government-owned Campbell County annual parcel:

```text
taxyear      2026
jurisdicti   CAMPBELL
parcelnb     49720332401200
accountno    R0059774
locationad   16 KETTLESON XING
```

The exact four-field lookup currently returns one WGS84 polygon occurrence.
The probe checks the item/layer schema, annual identifiers, situs, and polygon
presence. Owner labels, values, `FID`, source `ID`, and shape measurements are
rolling release content and are not part of the stable sentinel assertion.

## Publisher lineage and county complements

The ArcGIS item advertises CSV, Shapefile, SQLite, GeoPackage, File
Geodatabase, Feature Collection, GeoJSON, Excel, JSONL, KML, and Parquet
exports. Those exports and the query layer are representations of the same
hosted annual release, not independent corroboration.

The DOR [Assessment Data Download](https://wyo-prop-div.wyo.gov/assessment-data-download)
page states that its data is current as of January 1, 2026. It is a
same-authority annual assessment route. It can complement a spatial query or
support bulk work, but repeating the same county/DOR owner or assessment
observation does not create another title source.

Wyoming ETS publishes an official
[directory of GIS and mapping sites for all 23 counties](https://ets.wyo.gov/gis-office/georesources).
Those local destinations lead to three useful field-matched evidence domains:

- county assessor systems for current local property accounts, assessment,
  situs, legal, improvements, and county parcel identifiers;
- county treasurer systems for tax bills, balances, delinquencies, and
  payments; and
- county clerk systems for grantor/grantee indexes, recording dates,
  instrument types, book/page or instrument numbers, and recorded documents.

The county clerk is the title-event route. Assessor and treasurer records add
current and payment context. Jurisdiction, parcel/account, address, legal
description, and owner candidate are the practical join fields among these
sources.

## Reusable ArcGIS-family lessons

This source added several concrete improvements to the statewide-source
workflow:

1. Resolve the current official item and validate its `serviceItemId`, layer
   name, OID field, geometry type, field set, and ordered pagination together.
2. Audit both database nulls and whitespace/sentinel blanks. `COUNT(field)`
   alone would have hidden all 40,487 blank account strings.
3. Group proposed business keys over the complete layer, then inspect rows in
   the largest groups. A duplicate key may represent multipart geometry rather
   than duplicate parcels or bad records.
4. Preserve the annual business join and every raw geometry occurrence as
   separate identity domains. Geometry flags change payload, not grain.
5. Use the agency's official county-directory page to map local assessor,
   treasurer, and clerk complements while keeping their evidence roles
   distinct.
6. Classify hosted exports by publisher and dataset lineage so a convenient
   bulk copy is not mistaken for independent corroboration.
7. Anchor the fixed sentinel in stable annual identifiers and location while
   allowing owners, values, feature IDs, and shape measurements to roll.

## Shared lifecycle

`query_property.py` exposes owner, parcel, account, county/jurisdiction, situs,
mailing, legal, FID, point, bounding-box, map/geometry, discovery, and probe
operations under the same source ID. An omitted shared limit remains
exhaustive; caller-selected limits, cursors, technical page sizes, and overall
ceilings pass through to the standalone adapter.

`ingest_property_records.py` stores every `FID` as a source occurrence. Rows
with a supported annual identity project to one annual parcel shell, one
assessment-roll owner/address/value set, and one deterministic geometry
representative. The representative is the lowest geometry-bearing numeric
`FID`, and all other FIDs remain separately attributable observations and
aliases. The 3,013 audited occurrence-only rows remain raw evidence without a
parcel projection. Ingestion does not create a sale or recorded instrument
from the annual tax roll.

The source catalog and census register both `assessment_roll` and
`parcel_geometry` coverage for all 23 county GEOIDs. County assessor,
treasurer, and clerk destinations remain field-matched complements. The
monitor keeps app, layer, schema, identity, and paging fingerprints separate
from release year, source count, owner, value, FID, and source-version
observations. The canonical citation resolves through the official
application root.

## Focused validation

```bash
.venv/bin/pytest -q \
  tests/test_query_wy_dor_parcels.py \
  tests/test_wy_dor_parcels_shared_integration.py
.venv/bin/ruff check \
  tools/query_wy_dor_parcels.py \
  tests/test_query_wy_dor_parcels.py \
  tests/test_wy_dor_parcels_shared_integration.py
.venv/bin/python -m py_compile \
  tools/query_wy_dor_parcels.py \
  tests/test_query_wy_dor_parcels.py \
  tests/test_wy_dor_parcels_shared_integration.py
```
