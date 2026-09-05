# Licking County Auditor Parcel Search GIS

Verified 2026-07-31 against the official Licking County GIS ArcGIS layer at
[`Auditor/ParcelsSearch/MapServer/0`](https://gis.lickingcounty.gov/server/rest/services/Auditor/ParcelsSearch/MapServer/0).
The standalone adapter is `tools/query_ohio_licking_property.py`; its source
identity is `us-oh-licking-county-auditor-gis`.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_licking_property.py source \
  --output "$WORKDIR/licking-source.json"

uv run python tools/query_ohio_licking_property.py probe \
  --output "$WORKDIR/licking-probe.json"

uv run python tools/query_ohio_licking_property.py parcel \
  001-000006-01.000 --geometry \
  --output "$WORKDIR/licking-parcel.json"

uv run python tools/query_ohio_licking_property.py owner SMITH \
  --output "$WORKDIR/licking-owner.json"

uv run python tools/query_ohio_licking_property.py value \
  --field market-total --minimum 1000000 \
  --output "$WORKDIR/licking-market-value.json"

uv run python tools/query_ohio_licking_property.py attribute \
  land-use "VACANT LAND" \
  --output "$WORKDIR/licking-land-use.json"
```

## Verified source and coverage

The layer identifies itself as `Parcels`, has ArcGIS item ID
`2203dea8729044d4990050b111c0ecff`, and declares ordered queries,
pagination, statistics, and distinct values. Its native spatial reference is
Ohio State Plane South (`WKID 102723`, latest `3735`); requested geometry is
returned by the adapter as Esri JSON in EPSG:4326.

The live audit found 83,796 feature occurrences. Of those, 82,604 had a
non-null `Parcel` value and every non-null value was unique at the time of the
audit. Another 1,192 occurrences had no parcel number. All occurrences had a
`GlobalID`. The adapter retains the null-parcel rows rather than treating the
parcel number as the source row identity.

The official [Licking County Tax Parcel
Viewer](https://apps.lickingcounty.gov/maps/taxparcelviewer/default.html)
provides the county's interactive owner, address, and Auditor PIN search
route. The REST layer is the structured official GIS route used by this
adapter.

## Operations

- `source` reports verified routes, supported operations, identity semantics,
  and relationships to nearby Ohio sources without opening a network client.
- `metadata` validates the live layer identity, field declarations, CRS, and
  ordered-pagination capabilities.
- `probe` performs four requests: metadata, total count, null-parcel count,
  and exact retrieval of sentinel parcel `001-000006-01.000`.
- `list` returns all matching feature occurrences.
- `parcel` searches the exact published `Parcel` value.
- `occurrence` retrieves an exact `OBJECTID` row locator.
- `owner`, `situs`, and `mailing` search the respective published assessment
  fields.
- `value` filters a selected acreage, improvement, assessed-value, or recent
  sale-amount field by minimum, maximum, or both.
- `attribute` searches published jurisdiction, district, land-use, class,
  plat, routing, neighborhood, dwelling, or assessment-program fields.

Record operations accept `--geometry`. They traverse the complete ordered
native match set before applying an optional caller `--limit`; a returned
cursor is tied to the selector, declared schema, and full ordered membership.
The native `--page-size` controls transport only and is bounded by the layer's
declared `maxRecordCount`.

## Identity and normalized fields

The normalized record kind is
`county_assessor_parcel_feature_occurrence`. `GlobalID` is the canonical
occurrence identity, with `OBJECTID` retained as its source row locator and as
the fallback when a future row lacks `GlobalID`. `Parcel`, when present, is
exposed separately as a business-key join candidate. Repeated parcel values
therefore remain separately attributable feature occurrences.

Normalized records retain:

- assessment owner-name and situs/mailing-address observations;
- municipality, township, tax district, school district, and neighborhood;
- acreage, legal description, land-use code, class, plat, and routing fields;
- dwelling, year-built, and living-area observations;
- market, CAUV, exempt, abated, improvement, and net value observations;
- TIF, owner-occupied, and homestead flags;
- up to three source-published recent transfers, including parties, date,
  type, instrument text, sale amount, validity flag, and parcel count;
- native shape metrics and optional parcel geometry; and
- raw attributes plus the exact source row selector and schema fingerprint.

Owner and mailing fields describe the Auditor's assessment roll. The recent
transfer columns are also Auditor observations; the corresponding recorded
instrument remains separately addressable through the Recorder source.

## Related sources

- `us-oh-licking-county-auditor-ontrac` is the same Auditor's interactive
  property-detail route and can add presentation/detail fields. Overlapping
  values share an authority and data lineage.
- `us-oh-ogrip-statewide-parcels` is the statewide OGRIP representation of
  county-origin parcel and geometry data. It is useful for cross-county search
  and standardized parcel identifiers; overlapping county fields are not a
  separate originating observation.
- `us-oh-licking-county-recorder-pax` represents recorded instruments and
  indexed parties, a complementary official record domain for title and
  conveyance work.
- `us-oh-licking-county-recorder-instrument-detail` is the anonymous exact-
  instrument detail/PDF representation available when broad PAX discovery is
  account-gated.
- `us-oh-licking-sheriff-realauction` and the Licking foreclosure
  archive add auction, case, parcel, and disposition observations for
  foreclosure research.

These routes can be joined on exact parcel or instrument identifiers and then
compared at their distinct record grains: GIS feature occurrence, assessment
detail, recorded instrument, and foreclosure event.
