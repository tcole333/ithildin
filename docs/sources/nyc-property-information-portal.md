# NYC Property Information Portal

Verified 2026-07-31. The New York City Department of Finance (DOF)
[Property Information Portal](https://propertyinformationportal.nyc.gov/) is
backed by five related public ArcGIS layers. The standalone adapter queries
those layers directly and joins their different record grains through the
ten-digit borough-block-lot identifier (BBL).

## Shared lifecycle

The existing `us-nyc-property-information-portal` catalog identity now points
at the verified ArcGIS family below. `query_property.py` exposes owner,
address, BBL or borough/block/lot, detail, geometry, current assessment,
history, exemptions, discovery, and probe operations. `ingest_property_records.py`
preserves every component occurrence and projects the durable parcel fields,
and `public_records_monitor.py` checks one metadata response and one exact BBL
page for each layer.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_property.py parcel 1013860010 \
  --source us-nyc-property-information-portal --ingest \
  --output "$WORKDIR/nyc-pip-parcel.json"
uv run python tools/query_property.py history 1013860010 \
  --source us-nyc-property-information-portal \
  --output "$WORKDIR/nyc-pip-history.json"
uv run python tools/public_records_monitor.py run \
  us-nyc-property-information-portal \
  --output "$WORKDIR/nyc-pip-monitor.json"
```

## Verified layer family

The official DOF
[Digital Tax Map page](https://home4.nyc.gov/site/finance/property/property-digital-tax-map.page)
links the PIP application. The application uses the public ArcGIS Online
organization rooted at:

```text
https://services6.arcgis.com/yG5s3afENB5iO9fj/ArcGIS/rest/services
```

| Component | Service layer | Source grain | Native page |
|---|---|---|---:|
| Parcel detail | `DTM_ETL_DAILY_view/FeatureServer/18` (`PTS_DESC_DAILY`) | Current DOF parcel/building observation | 1,000 |
| Tax lot | `DTM_ETL_DAILY_view/FeatureServer/0` (`TAX_LOT_POLYGON`) | Cadastral tax-lot polygon occurrence | 1,000 |
| Current assessment | `PROPMAST__VIEW/FeatureServer/0` (`PROPMAST`) | Current published assessment occurrence | 2,000 |
| Assessment history | `PROPMAST_HIST_VIEW/FeatureServer/0` (`PROPMAST_HIST`) | Historical assessment occurrence | 2,000 |
| Exemptions | `EXDET_PIP_VIEW/FeatureServer/0` (`EXDET_PIP`) | Published exemption occurrence | 2,000 |

All five layers advertise query, ordered results, and offset pagination. The
native record count is a technical transfer-page size. When neither
`--limit` nor `--max-records` is supplied, owner, address, and component
lookups continue through native pages until the source result is exhausted.
Exact BBL bundles and the sentinel fetch every matching row in every
component.

## Standalone adapter

```bash
# All five components for a durable BBL
uv run python tools/query_nyc_pip.py bbl 1013860010 \
  --output /tmp/nyc-pip-bbl.json

# The same lookup from borough, block, and lot
uv run python tools/query_nyc_pip.py lot Manhattan 1386 10 \
  --output /tmp/nyc-pip-lot.json

# Parcel-detail searches
uv run python tools/query_nyc_pip.py owner "BOLT 1 L.P." \
  --output /tmp/nyc-pip-owner.json
uv run python tools/query_nyc_pip.py address "9 E 71st St" \
  --output /tmp/nyc-pip-address.json

# Individual source components
uv run python tools/query_nyc_pip.py detail 1013860010 --json
uv run python tools/query_nyc_pip.py geometry 1013860010 --json
uv run python tools/query_nyc_pip.py current-assessment 1013860010 --json
uv run python tools/query_nyc_pip.py assessment-history 1013860010 --json
uv run python tools/query_nyc_pip.py exemptions 1013860010 --json

# Static route manifests, live metadata validation, and fixed sentinel
uv run python tools/query_nyc_pip.py discovery layers --json
uv run python tools/query_nyc_pip.py discovery metadata --json
uv run python tools/query_nyc_pip.py discovery routes --json
uv run python tools/query_nyc_pip.py probe --json
```

Owner matching supports `contains`, `starts`, and `exact`. Address matching
normalizes common direction and street-type abbreviations into the separate
`HOUSENUM` and `STREET_NAME` fields. A caller-selected result window returns
an ArcGIS continuation cursor.

## Identity and record grain

The layer family publishes three different identity domains:

| Identity | Role |
|---|---|
| Ten-digit BBL | Durable parcel/tax-lot join across the five components |
| Layer `OBJECTID` | One occurrence in one published ArcGIS layer; retained separately from the parcel |
| Assessment or exemption child tuple | Cross-representation or within-series join at the child-record grain |

Every normalized component row has a parcel canonical reference based on BBL
and a separate canonical occurrence reference based on layer plus
`OBJECTID`. An `OBJECTID` is never substituted for the BBL.

### Assessment identity audit

Aggregate queries over the complete current and history layers found a
maximum observed count of one for:

```text
(PARID, TAXYR, PERIOD)
```

in each component. The normalized `same_assessment_key` exposes that tuple as
a cross-representation join. A current `PROPMAST` row and its
`PROPMAST_HIST` representation remain distinct occurrences with different
layer names, `OBJECTID` values, canonical references, and schema
fingerprints.

### Exemption identity audit

Grouping exemptions only by:

```text
(PARID, TAXYR, F_EXCODE, F_EXEMPT_TYPE, SORT_ORDER)
```

produced an apparent 324-row group for BBL `3801190032`, tax year 2025, and
MTA exemption code `12366`. A row sample showed that `PARID_ORG` carried
different unit/original-parcel values such as `3801190032 E219` and
`3801190032 E147`. Repeating the complete-layer aggregate with the fuller
child tuple:

```text
(PARID_ORG, PARID, TAXYR, F_EXCODE, F_EXEMPT_TYPE, SORT_ORDER)
```

produced a maximum observed count of one.

The adapter therefore includes `PARID_ORG` in the published exemption child
tuple while retaining `OBJECTID` as the release occurrence. If fully
identical published tuples appear in a complete exact-BBL result, each
occurrence remains present and receives a deterministic duplicate ordinal.
For a caller-selected window, the ordinal is labeled as window-scoped.
Assessment and exemption values stay in the payload rather than becoming
identity fields.

The captured aggregate and sample-row evidence lives in
`tests/fixtures/public_records/nyc_pip/`.

## Sentinel contract

The bounded probe uses BBL `1013860010`:

- Manhattan, block 1386, lot 10;
- parcel address `9 EAST 71 STREET`;
- one parcel-detail row and one tax-lot polygon;
- current and historical assessment rows; and
- zero exemption rows at verification, which is a valid component result.

The sentinel checks stable parcel identity, address, geometry presence, and
component availability. Owner name, assessment values, assessment
`OBJECTID`s, and tax years are rolling observations and can change without
making the route invalid.

## Evidence lineage and complements

The parcel-detail `OWNER` field is a DOF tax-roll observation. It is valuable
for finding a parcel and tracking assessment context, but it does not by
itself report a recorded title event.

PIP's recent-recording display represents ACRIS data. A PIP display and the
corresponding ACRIS result are two views of the same recording lineage, not
two independent records. Complete recorded-instrument routes are:

- [ACRIS](https://www.nyc.gov/site/finance/property/acris.page) for
  Manhattan, Bronx, Brooklyn, and Queens; and
- the [Richmond County Clerk land-document search](https://richmondcountyclerk.com/Search/SearchIndex)
  for Staten Island.

Other official sources add useful, different record domains when a PIP field
is absent or the investigation needs more context:

- NYC PLUTO/MapPLUTO for planning, zoning, land-use, building, and geographic
  attributes;
- NYC Department of Buildings records for jobs, permits, complaints, and
  violations tied to an address or BBL;
- NYC Housing Preservation and Development records for building
  registrations, owners/managers reported to HPD, complaints, and housing
  violations;
- DOF rolling-sales and tax-lien datasets for transaction and delinquency
  screening; and
- NYSCEF/eCourts and county court records for litigation tied to parties,
  addresses, foreclosures, liens, and recorded instruments.

These are field-matched complements. They can corroborate or add a different
event domain without being collapsed into the PIP assessment observation.

## Shared projection

Every returned layer row becomes a raw source observation keyed as
`component:BBL:OBJECTID`. The parcel table contains only the order-independent
BBL identity, so repeated detail/building rows cannot overwrite it with a
different building representation. Identical tax-roll owner and situs labels
are deduplicated.

The assessment table is an explicit current-view projection. For multiple
current rows in one tax year it chooses the highest numeric `PERIOD`, then the
lowest `OBJECTID`; all current alternatives and every history row remain raw
occurrences. Exemption rows remain raw with `PARID_ORG`, the full published
tuple, duplicate ordinal when needed, and their own `OBJECTID`. PIP does not
create sale, recorded-instrument, document-artifact, or title rows.

## Process improvements from this source

This integration sharpened a reusable sequence for portal-backed property
sources:

1. Start from the authority page and follow the official application link.
2. Inspect the application's public service configuration before treating an
   interactive portal session as the only access route.
3. Model the backing layers as a family and identify the join grain of each
   layer rather than assuming the portal exposes one record type.
4. Run aggregate uniqueness queries over proposed child keys before making
   them canonical. Include identity-bearing fields such as original parcel or
   unit references before interpreting duplicates.
5. Treat service `maxRecordCount` as pagination metadata and verify native
   page exhaustion offline with an injected multi-page transport.
6. Build fixed probes around stable identity and routing facts while leaving
   rolling owners, values, years, and ETL occurrence IDs outside the sentinel
   contract.
7. Map alternate official datasets at the same time, distinguishing another
   representation of the same record from a genuinely different evidence
   domain.

The same discovery ladder is useful when the visible application is blocked
or awkward: authority link, application configuration, portal item or web
map, backing service metadata, bounded sample, identity audit, then
field-matched complements.

## Focused validation

```bash
.venv/bin/pytest -q \
  tests/test_query_nyc_pip.py tests/test_nyc_pip_shared_integration.py
.venv/bin/ruff check tools/query_nyc_pip.py \
  tests/test_query_nyc_pip.py tests/test_nyc_pip_shared_integration.py
.venv/bin/python -m py_compile \
  tools/query_nyc_pip.py tools/query_property.py \
  tools/ingest_property_records.py tools/public_records_monitor.py
```
