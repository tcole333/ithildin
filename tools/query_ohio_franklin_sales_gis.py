#!/usr/bin/env python3
"""Query Franklin County Auditor's official Sales Information GIS layer.

Layer 0 publishes one attributable sale/parcel feature occurrence per row.
``GlobalID`` is the preferred occurrence identity and ``OBJECTID`` remains the
row locator and fallback.  ``ConveyanceNum`` plus ``PARCELID`` is exposed as a
separate business join only when both values are usable.

Every record operation uses a deterministic, OBJECTID-bounded ArcGIS snapshot.
Omitting ``--limit`` exhausts and verifies that snapshot; an explicit limit
uses a query/schema/snapshot-bound keyset continuation without materializing
the complete selection first.

Examples:
    uv run python tools/query_ohio_franklin_sales_gis.py source --json
    uv run python tools/query_ohio_franklin_sales_gis.py parcel 010-000006 --json
    uv run python tools/query_ohio_franklin_sales_gis.py party LAMAR --limit 25 \
        --output /tmp/franklin-sales.json
    uv run python tools/query_ohio_franklin_sales_gis.py date-range \
        --start 2024-01-01 --end 2024-12-31 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

try:
    from tools import oregon_arcgis_keyset as arcgis_shared
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
    )
    from tools.public_records_http import (
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    import oregon_arcgis_keyset as arcgis_shared
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
    )
    from public_records_http import (
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-oh-franklin-county-auditor-sales-gis"
STATE_CODE = "OH"
STATE_FIPS = "39"
COUNTY_GEOID = "39049"
COUNTY_NAME = "Franklin County"
SERVICE_URL = (
    "https://gis.franklincountyohio.gov/hosting/rest/services/"
    "RealEstate/Sales_Information/FeatureServer"
)
LAYER_ID = 0
LAYER_URL = f"{SERVICE_URL}/{LAYER_ID}"
ITEM_ID = "1ce134b7dabe45bdad4121193934a38d"
DEFAULT_PAGE_SIZE = 1_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = arcgis_shared.cursor_prefix(
    "auditor-sales-gis",
    namespace="ohio-franklin",
)
SENTINEL_OBJECT_ID = 1
PROBE_EXPECTED_REQUESTS = 10

FIELDS = (
    "OBJECTID",
    "PARCELID",
    "LOWPARCELID",
    "STATEDAREA",
    "ACRES",
    "CVTTXCD",
    "CVTTXDSCRP",
    "SCHLTXCD",
    "SCHLDSCRP",
    "NBHDCD",
    "CLASSCD",
    "CLASSDSCRP",
    "SITEADDRESS",
    "ZIPCD",
    "CNVYNAME",
    "SALEDATE",
    "SalePrice",
    "SALEYEAR",
    "Instrument",
    "ConveyanceNum",
    "SaleType",
    "ParcelCount",
    "GranteeName1",
    "GranteeName2",
    "GrantorName1",
    "GrantorName2",
    "RESFLRAREA_AG",
    "RESFLRAREA_BG",
    "RESFLRAREA",
    "RESYRBLT",
    "RESYRBLTEFF",
    "RESSTRTYP",
    "Attic",
    "Basement",
    "ROOMS",
    "BATHS",
    "HBATHS",
    "BEDRMS",
    "FIREPLC",
    "AIRCOND",
    "WALL",
    "COND",
    "Grade",
    "HEIGHT",
    "BLDTYP",
    "BLDGAREA",
    "STRCLASS",
    "X_COORD",
    "Y_COORD",
    "LASTUPDATE",
    "created_user",
    "created_date",
    "last_edited_user",
    "last_edited_date",
    "ValidSale",
    "ISPARCELACTIVE",
    "GlobalID",
)

SEARCH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "parcel": ("PARCELID", "LOWPARCELID"),
    "conveyance": ("ConveyanceNum", "Instrument"),
    "party": (
        "GranteeName1",
        "GranteeName2",
        "GrantorName1",
        "GrantorName2",
    ),
    "address": ("SITEADDRESS", "ZIPCD", "CNVYNAME"),
}

MANIFEST = arcgis_shared.ArcGISLayerManifest(
    source_id=SOURCE_ID,
    name="Franklin County Auditor Sales Information GIS",
    layer_url=LAYER_URL,
    layer_id=LAYER_ID,
    service_item_id=ITEM_ID,
    expected_layer_name="Sales Details",
    object_id_field="OBJECTID",
    required_fields=FIELDS,
    source_crs_wkids=(102723, 3735),
    record_kind="county_auditor_sale_feature_occurrence",
    publisher="Franklin County Auditor",
    observed_count=98_291,
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Franklin County Auditor Sales Information GIS",
    source_role=(
        "official_county_auditor_sale_party_price_parcel_address_structure_"
        "and_location_observations"
    ),
    base_url=LAYER_URL,
    dataset_id=ITEM_ID,
    metadata={
        "authority": "Franklin County Auditor",
        "platform_family": "arcgis_featureserver_feature_layer",
        "county_geoid": COUNTY_GEOID,
        "record_grain": "published_sale_feature_occurrence",
        "occurrence_identity_fields": ["GlobalID", "OBJECTID"],
        "sale_business_join_fields": ["ConveyanceNum", "PARCELID"],
        "valid_sale_is_source_qualification": True,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS, "county_geoid": COUNTY_GEOID},
)

SOURCE_WARNINGS = (
    "ValidSale is preserved as the Auditor's qualification; it is not used "
    "to discard otherwise published dated, positive-price transactions.",
    "Layer 0 is the canonical dataset. Layers 1-4 are renderer-only display aliases "
    "of the same records and are not independent corroboration.",
    "Auditor sale, parcel, address, structure, and point-location fields are "
    "same-authority observations; recorder instruments control recorded-title "
    "and filing evidence.",
)


class FranklinSalesSelectionError(ValueError):
    """A selector or continuation cannot be applied safely."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query_selection",
            retryable=False,
            details=self.details,
        )


class FranklinSalesClient(arcgis_shared.BoundedArcGISClient):
    """Source-named ArcGIS transport with a bounded statistics request."""

    def fetch_coverage_statistics(self) -> Mapping[str, Any]:
        statistics = [
            {"statisticType": statistic, "onStatisticField": field, "outStatisticFieldName": alias}
            for field, stem in (("SALEDATE", "sale_date"), ("LASTUPDATE", "last_update"))
            for statistic, alias in (("min", f"{stem}_min"), ("max", f"{stem}_max"))
        ]
        payload = self._request_json(
            MANIFEST.query_url,
            params={
                "where": "1=1",
                "outStatistics": canonical_json(statistics),
                "returnGeometry": "false",
                "f": "json",
            },
            maximum_bytes=256 * 1024,
        )
        features = payload.get("features")
        if (
            not isinstance(features, list)
            or len(features) != 1
            or not isinstance(features[0], Mapping)
        ):
            raise SourceSchemaError(
                "Franklin sales statistics response is malformed",
                url=MANIFEST.query_url,
            )
        return arcgis_shared.feature_attributes(features[0])

    def fetch_distinct_count(self, field: str) -> int:
        if field not in FIELDS:
            raise ValueError(f"unknown Franklin sales field: {field}")
        payload = self._request_json(
            MANIFEST.query_url,
            params={
                "where": f"{field} IS NOT NULL",
                "outFields": field,
                "returnDistinctValues": "true",
                "returnCountOnly": "true",
                "returnGeometry": "false",
                "f": "json",
            },
            maximum_bytes=128 * 1024,
        )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Franklin sales distinct count is not a non-negative integer",
                url=MANIFEST.query_url,
                details={"field": field, "count": count},
            )
        return count


@dataclass(frozen=True)
class FranklinSalesCollection:
    features: tuple[Mapping[str, Any], ...]
    total_count: int
    bounded_count: int
    boundary_object_id: int | None
    schema_fingerprint: str
    maximum_page_size: int
    pages_fetched: int


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date must use YYYY-MM-DD"
        ) from error


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sql_text(value: Any, label: str = "query") -> str:
    text = str(value).strip()
    if not text:
        raise FranklinSalesSelectionError(
            "empty_query",
            f"{label} must not be empty",
        )
    if "\x00" in text:
        raise FranklinSalesSelectionError(
            "invalid_query",
            f"{label} contains a NUL byte",
        )
    return text.replace("'", "''")


def _epoch_millis_iso(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return (
            datetime.fromtimestamp(value / 1_000, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return None


def _object_id(feature: Mapping[str, Any]) -> int:
    value = arcgis_shared.feature_attributes(feature).get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaError(
            "Franklin sales feature lacks an integer OBJECTID",
            url=LAYER_URL,
            details={"OBJECTID": value},
        )
    return value


def _text_contains(fields: Sequence[str], term: str) -> str:
    return "(" + " OR ".join(
        f"UPPER({field}) LIKE '%{term}%'" for field in fields
    ) + ")"


def _where(args: argparse.Namespace) -> str:
    if args.command == "parcel":
        return f"UPPER(PARCELID)='{_sql_text(args.query, 'parcel ID').upper()}'"
    if args.command == "conveyance":
        return (
            "UPPER(ConveyanceNum)="
            f"'{_sql_text(args.query, 'conveyance number').upper()}'"
        )
    if args.command == "party":
        return _text_contains(
            SEARCH_FIELDS["party"],
            _sql_text(args.query, "party query").upper(),
        )
    if args.command == "validity":
        return f"UPPER(ValidSale)='{_sql_text(args.query, 'validity').upper()}'"
    if args.command == "date-range":
        clauses: list[str] = []
        if args.start is not None:
            clauses.append(f"SALEDATE >= DATE '{args.start.isoformat()}'")
        if args.end is not None:
            try:
                exclusive_end = args.end + timedelta(days=1)
            except OverflowError as error:
                raise FranklinSalesSelectionError(
                    "invalid_date_range",
                    "--end must be earlier than 9999-12-31",
                ) from error
            clauses.append(f"SALEDATE < DATE '{exclusive_end.isoformat()}'")
        if not clauses:
            raise FranklinSalesSelectionError(
                "date_range_required",
                "date-range requires --start, --end, or both",
            )
        return " AND ".join(clauses)
    if args.command == "search":
        term = _sql_text(args.query).upper()
        if args.field == "object-id":
            try:
                object_id = int(term)
            except ValueError as error:
                raise FranklinSalesSelectionError(
                    "invalid_object_id",
                    "object-id search requires a positive integer",
                ) from error
            if object_id < 1:
                raise FranklinSalesSelectionError(
                    "invalid_object_id",
                    "object-id search requires a positive integer",
                )
            return f"OBJECTID={object_id}"
        fields = (
            tuple(field for group in SEARCH_FIELDS.values() for field in group)
            if args.field == "all"
            else SEARCH_FIELDS[args.field]
        )
        return _text_contains(fields, term)
    raise FranklinSalesSelectionError(
        "unsupported_operation",
        f"unsupported Franklin sales operation: {args.command}",
    )


def _bounded_where(
    base_where: str,
    *,
    boundary: int,
    anchor: int | None = None,
) -> str:
    clauses = [f"({base_where})", f"OBJECTID<={boundary}"]
    if anchor is not None:
        clauses.append(f"OBJECTID>{anchor}")
    return " AND ".join(clauses)


def fetch_all_features(
    client: FranklinSalesClient | Any,
    *,
    where: str,
    return_geometry: bool,
) -> FranklinSalesCollection:
    """Exhaust one live snapshot with monotonic OBJECTID keyset paging."""

    metadata = client.fetch_metadata()
    schema_fingerprint, maximum_page_size = arcgis_shared.metadata_contract(
        MANIFEST,
        metadata,
    )
    total_count = client.fetch_count(where)
    boundary_page = client.fetch_page(
        where=where,
        record_count=1,
        return_geometry=False,
        descending=True,
    )
    if not boundary_page:
        if total_count != 0:
            raise SourceSchemaError(
                "Franklin sales count was nonzero but no boundary row was returned",
                url=LAYER_URL,
                details={"reported_count": total_count},
            )
        return FranklinSalesCollection(
            features=(),
            total_count=0,
            bounded_count=0,
            boundary_object_id=None,
            schema_fingerprint=schema_fingerprint,
            maximum_page_size=maximum_page_size,
            pages_fetched=1,
        )

    boundary = _object_id(boundary_page[0])
    snapshot_where = _bounded_where(where, boundary=boundary)
    bounded_count = client.fetch_count(snapshot_where)
    page_size = min(int(client.page_size), maximum_page_size)
    features: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    last_object_id: int | None = None
    pages_fetched = 0

    while True:
        page = client.fetch_page(
            where=_bounded_where(
                where,
                boundary=boundary,
                anchor=last_object_id,
            ),
            record_count=page_size,
            return_geometry=return_geometry,
        )
        pages_fetched += 1
        if not page:
            break
        for feature in page:
            object_id = _object_id(feature)
            if (
                object_id in seen
                or (last_object_id is not None and object_id <= last_object_id)
                or object_id > boundary
            ):
                raise SourceSchemaError(
                    "Franklin sales paging repeated or crossed its snapshot boundary",
                    url=LAYER_URL,
                    details={
                        "object_id": object_id,
                        "previous_object_id": last_object_id,
                        "boundary_object_id": boundary,
                    },
                )
            seen.add(object_id)
            last_object_id = object_id
            features.append(feature)
        if len(features) > bounded_count:
            raise SourceSchemaError(
                "Franklin sales traversal exceeded its snapshot count",
                url=LAYER_URL,
                details={
                    "snapshot_count": bounded_count,
                    "collected": len(features),
                },
            )

    if len(features) != bounded_count:
        raise SourceSchemaError(
            "Franklin sales traversal did not yield its snapshot count",
            url=LAYER_URL,
            details={
                "snapshot_count": bounded_count,
                "collected": len(features),
                "boundary_object_id": boundary,
            },
        )
    return FranklinSalesCollection(
        features=tuple(features),
        total_count=total_count,
        bounded_count=bounded_count,
        boundary_object_id=boundary,
        schema_fingerprint=schema_fingerprint,
        maximum_page_size=maximum_page_size,
        pages_fetched=pages_fetched,
    )


def _names(attributes: Mapping[str, Any], *fields: str) -> list[str]:
    return [
        value
        for field in fields
        if (value := _clean_text(attributes.get(field))) is not None
    ]


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = dict(arcgis_shared.feature_attributes(feature))
    object_id = _object_id(feature)
    global_id = _clean_text(attributes.get("GlobalID"))
    parcel_id = _clean_text(attributes.get("PARCELID"))
    conveyance_number = _clean_text(attributes.get("ConveyanceNum"))
    occurrence_native_id = (
        global_id or f"{ITEM_ID}:{LAYER_ID}:OBJECTID:{object_id}"
    )
    occurrence_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "sale_feature_occurrence",
        occurrence_native_id,
    )
    parcel_ref = (
        canonical_property_ref(SOURCE_ID, COUNTY_GEOID, "parcel", parcel_id)
        if parcel_id is not None
        else None
    )
    sale_native_id = (
        f"{conveyance_number}|{parcel_id}"
        if conveyance_number is not None and parcel_id is not None
        else None
    )
    sale_ref = (
        canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "sale_transaction",
            sale_native_id,
        )
        if sale_native_id is not None
        else None
    )
    geometry = feature.get("geometry") if geometry_requested else None
    sale_date_raw = attributes.get("SALEDATE")
    last_update_raw = attributes.get("LASTUPDATE")

    record: dict[str, Any] = {
        "record_kind": "county_auditor_sale_feature_occurrence",
        "source_id": SOURCE_ID,
        "dataset_id": ITEM_ID,
        "source_record_id": str(object_id),
        "native_id": occurrence_native_id,
        "canonical_ref": occurrence_ref,
        "occurrence_identity": {
            "native_id": occurrence_native_id,
            "identity_basis": (
                "GlobalID" if global_id else "service_item_layer_object_id"
            ),
            "global_id": global_id,
            "object_id": object_id,
            "service_item_id": ITEM_ID,
            "layer_id": LAYER_ID,
            "canonical_ref": occurrence_ref,
        },
        "parcel_identity": (
            {
                "parcel_id": parcel_id,
                "canonical_ref": parcel_ref,
                "identity_role": "published_business_join_candidate",
            }
            if parcel_id is not None
            else None
        ),
        "sale_identity": (
            {
                "conveyance_number": conveyance_number,
                "parcel_id": parcel_id,
                "canonical_ref": sale_ref,
                "identity_role": "published_business_join_candidate",
            }
            if sale_ref is not None
            else None
        ),
        "identity_state": (
            "occurrence_sale_and_parcel_keys"
            if sale_ref is not None
            else (
                "occurrence_and_parcel_key"
                if parcel_id is not None
                else "occurrence_only"
            )
        ),
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "parcel_id": parcel_id,
        "low_parcel_id": _clean_text(attributes.get("LOWPARCELID")),
        "conveyance_number": conveyance_number,
        "parcel_count": attributes.get("ParcelCount"),
        "sale": {
            "date_raw": sale_date_raw,
            "date_iso": _epoch_millis_iso(sale_date_raw),
            "year": _clean_text(attributes.get("SALEYEAR")),
            "price": attributes.get("SalePrice"),
            "currency": "USD",
            "instrument": _clean_text(attributes.get("Instrument")),
            "sale_type": _clean_text(attributes.get("SaleType")),
            "valid_sale": _clean_text(attributes.get("ValidSale")),
            "qualification_preserved": True,
        },
        "parties": {
            "grantee_names": _names(
                attributes,
                "GranteeName1",
                "GranteeName2",
            ),
            "grantor_names": _names(
                attributes,
                "GrantorName1",
                "GrantorName2",
            ),
        },
        "situs_address_observation": {
            "raw": _clean_text(attributes.get("SITEADDRESS")),
            "postal_code": _clean_text(attributes.get("ZIPCD")),
            "subdivision_or_condominium": _clean_text(
                attributes.get("CNVYNAME")
            ),
        },
        "land_and_classification": {
            "stated_area": attributes.get("STATEDAREA"),
            "acres": attributes.get("ACRES"),
            "tax_district_code": _clean_text(attributes.get("CVTTXCD")),
            "tax_district_description": _clean_text(
                attributes.get("CVTTXDSCRP")
            ),
            "school_district_code": _clean_text(attributes.get("SCHLTXCD")),
            "school_district_description": _clean_text(
                attributes.get("SCHLDSCRP")
            ),
            "neighborhood_code": _clean_text(attributes.get("NBHDCD")),
            "property_class_code": _clean_text(attributes.get("CLASSCD")),
            "property_class_description": _clean_text(
                attributes.get("CLASSDSCRP")
            ),
        },
        "improvements": {
            "residential_floor_area_above_grade": attributes.get(
                "RESFLRAREA_AG"
            ),
            "residential_floor_area_below_grade": attributes.get(
                "RESFLRAREA_BG"
            ),
            "residential_floor_area_total": attributes.get("RESFLRAREA"),
            "year_built": attributes.get("RESYRBLT"),
            "effective_year_built": attributes.get("RESYRBLTEFF"),
            "residential_structure_type": _clean_text(
                attributes.get("RESSTRTYP")
            ),
            "attic": _clean_text(attributes.get("Attic")),
            "basement": _clean_text(attributes.get("Basement")),
            "rooms": attributes.get("ROOMS"),
            "bathrooms": attributes.get("BATHS"),
            "half_bathrooms": attributes.get("HBATHS"),
            "bedrooms": attributes.get("BEDRMS"),
            "fireplaces": attributes.get("FIREPLC"),
            "heating_air_conditioning": _clean_text(
                attributes.get("AIRCOND")
            ),
            "wall_type": _clean_text(attributes.get("WALL")),
            "condition": _clean_text(attributes.get("COND")),
            "grade": _clean_text(attributes.get("Grade")),
            "height": _clean_text(attributes.get("HEIGHT")),
            "building_type": _clean_text(attributes.get("BLDTYP")),
            "gross_floor_area": attributes.get("BLDGAREA"),
            "structure_class": _clean_text(attributes.get("STRCLASS")),
        },
        "activity": {
            "is_parcel_active": _clean_text(
                attributes.get("ISPARCELACTIVE")
            ),
            "last_update_raw": last_update_raw,
            "last_update_iso": _epoch_millis_iso(last_update_raw),
        },
        "coordinates_native": {
            "x": attributes.get("X_COORD"),
            "y": attributes.get("Y_COORD"),
            "layer_declared_crs": "EPSG:3735",
            "field_coordinate_crs_verified": False,
        },
        "audit_fields": {
            "created_user": _clean_text(attributes.get("created_user")),
            "created_date_raw": attributes.get("created_date"),
            "created_date_iso": _epoch_millis_iso(
                attributes.get("created_date")
            ),
            "last_edited_user": _clean_text(
                attributes.get("last_edited_user")
            ),
            "last_edited_date_raw": attributes.get("last_edited_date"),
            "last_edited_date_iso": _epoch_millis_iso(
                attributes.get("last_edited_date")
            ),
        },
        "source_layer_url": LAYER_URL,
        "source_record_selector": {"field": "OBJECTID", "value": object_id},
        "source_response_schema_fingerprint": schema_fingerprint,
        "raw_attributes": attributes,
    }
    if geometry_requested and geometry is not None:
        record.update(
            {
                "geometry": geometry,
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_role": "county_auditor_sale_location_point",
            }
        )
    return record


def _source_record() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "native_manifest": MANIFEST.contract_record(),
        "official_routes": {
            "feature_service": SERVICE_URL,
            "canonical_layer": LAYER_URL,
            "query": MANIFEST.query_url,
        },
        "verified_operations": [
            "source",
            "layers",
            "schema",
            "count",
            "probe",
            "search",
            "parcel",
            "conveyance",
            "party",
            "date-range",
            "validity",
            "geometry_via_record_operations",
        ],
        "identity_contract": {
            "occurrence": (
                "GlobalID first; serviceItemId/layer/OBJECTID fallback"
            ),
            "sale_business_join": (
                "ConveyanceNum plus PARCELID only when both are nonblank"
            ),
            "parcel_business_join": "PARCELID only when nonblank",
            "join_policy": (
                "retain every source feature occurrence independently of "
                "whether either business join is available"
            ),
            "live_audit_2026_07_31": {
                "total_occurrences": 98_291,
                "distinct_global_id_occurrences": 98_291,
                "null_global_id_occurrences": 0,
                "null_parcel_id_occurrences": 0,
                "blank_parcel_id_occurrences": 0,
                "null_conveyance_number_occurrences": 0,
                "blank_conveyance_number_occurrences": 0,
            },
        },
        "qualification_policy": {
            "field": "ValidSale",
            "semantics": "source_published_qualification_preserved_raw",
            "projection": (
                "dated positive-price transactions remain available regardless "
                "of the qualification value"
            ),
        },
        "source_relationships": [
            {
                "source_id": "us-oh-franklin-county-auditor-bulk",
                "relationship": "same_authority_representation",
                "role": "bulk parcel_and_sale_history_complement",
                "independent_corroboration_for_overlapping_fields": False,
            },
            {
                "source_id": "us-oh-ogrip-statewide-parcels",
                "relationship": "county_origin_statewide_representation",
                "role": "statewide_parcel_and_geometry_index",
                "independent_corroboration_for_overlapping_fields": False,
            },
            {
                "source_id": (
                    "us-oh-franklin-county-recorder-publicsearch"
                ),
                "relationship": "different_official_record_domain",
                "role": "recorded_instrument_and_party_evidence",
            },
        ],
        "warnings": list(SOURCE_WARNINGS),
    }


def _layers_record() -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "service_item_id": ITEM_ID,
        "service_url": SERVICE_URL,
        "canonical_layer": {
            "id": 0,
            "name": "Sales Details",
            "url": LAYER_URL,
            "role": "canonical_complete_dataset",
        },
        "renderer_aliases": [
            {
                "id": layer_id,
                "name": name,
                "role": "renderer_only_display_alias_not_independent_dataset",
                "independent_corroboration": False,
            }
            for layer_id, name in (
                (1, "Current Years Sales"),
                (2, "1 Year Previous Sales"),
                (3, "2 Years Previous Sales"),
                (4, "3 Years Previous Sales"),
            )
        ],
    }


def _schema_record(
    metadata: Mapping[str, Any],
    schema_fingerprint: str,
    maximum_page_size: int,
) -> dict[str, Any]:
    fields = metadata.get("fields")
    indexes = metadata.get("indexes")
    return {
        "source_id": SOURCE_ID,
        "layer_url": LAYER_URL,
        "layer_id": metadata.get("id"),
        "layer_name": metadata.get("name"),
        "service_item_id": metadata.get("serviceItemId"),
        "display_field": metadata.get("displayField"),
        "geometry_type": metadata.get("geometryType"),
        "native_extent": metadata.get("extent"),
        "maximum_page_size": maximum_page_size,
        "schema_fingerprint": schema_fingerprint,
        "field_count": len(fields) if isinstance(fields, list) else None,
        "required_fields": list(FIELDS),
        "declared_indexes": [
            {
                "name": index.get("name"),
                "fields": index.get("fields"),
                "is_unique": index.get("isUnique"),
            }
            for index in indexes or []
            if isinstance(index, Mapping)
        ],
        "advanced_query_capabilities": metadata.get(
            "advancedQueryCapabilities"
        ),
    }


def _build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for key in ("query", "field", "start", "end", "geometry"):
        if hasattr(args, key):
            value = getattr(args, key)
            parameters[key] = value.isoformat() if isinstance(value, date) else value
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "adapter": "tools/query_ohio_franklin_sales_gis.py",
                "pagination": (
                    "objectid_keyset_snapshot; omitted_limit_exhausts; "
                    "explicit_limit_returns_bound_continuation"
                ),
            },
        ),
    )


def _new_client(args: argparse.Namespace) -> FranklinSalesClient:
    return FranklinSalesClient(
        MANIFEST,
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: FranklinSalesSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _schema_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.SOURCE_CHANGED,
        [
            PublicRecordsError(
                code="normalization_or_cursor_failed",
                message=str(error),
                category="source_schema",
                retryable=False,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _build_query(args)
    active_client = client
    owned_client = client is None and args.command not in {"source", "layers"}
    try:
        if args.command == "source":
            result = PublicRecordsResult.success(query, [_source_record()])
        elif args.command == "layers":
            result = PublicRecordsResult.success(query, [_layers_record()])
        else:
            active_client = active_client or _new_client(args)
            if args.command == "schema":
                metadata = active_client.fetch_metadata()
                schema_fingerprint, maximum = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                result = PublicRecordsResult.success(
                    query,
                    [_schema_record(metadata, schema_fingerprint, maximum)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "count":
                metadata = active_client.fetch_metadata()
                schema_fingerprint, maximum = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "record_count": active_client.fetch_count("1=1"),
                            "schema_fingerprint": schema_fingerprint,
                            "maximum_page_size": maximum,
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                requests_before = getattr(active_client, "request_count", None)
                metadata = active_client.fetch_metadata()
                schema_fingerprint, maximum = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                total_count = active_client.fetch_count("1=1")
                distinct_global_ids = active_client.fetch_distinct_count(
                    "GlobalID"
                )
                identity_audit = {
                    "distinct_global_id_occurrences": distinct_global_ids,
                    "null_global_id_occurrences": active_client.fetch_count(
                        "GlobalID IS NULL"
                    ),
                    "null_parcel_id_occurrences": active_client.fetch_count(
                        "PARCELID IS NULL"
                    ),
                    "blank_parcel_id_occurrences": active_client.fetch_count(
                        "PARCELID=''"
                    ),
                    "null_conveyance_number_occurrences": (
                        active_client.fetch_count("ConveyanceNum IS NULL")
                    ),
                    "blank_conveyance_number_occurrences": (
                        active_client.fetch_count("ConveyanceNum=''")
                    ),
                }
                populated_global_id_occurrences = (
                    total_count
                    - identity_audit["null_global_id_occurrences"]
                )
                if distinct_global_ids != populated_global_id_occurrences:
                    raise SourceSchemaError(
                        "Franklin sales populated GlobalID values are no longer unique",
                        url=LAYER_URL,
                        details={
                            "record_count": total_count,
                            "null_global_id_count": identity_audit[
                                "null_global_id_occurrences"
                            ],
                            "populated_global_id_count": (
                                populated_global_id_occurrences
                            ),
                            "distinct_global_id_count": distinct_global_ids,
                        },
                    )
                statistics = active_client.fetch_coverage_statistics()
                sample = active_client.fetch_page(
                    where=f"OBJECTID={SENTINEL_OBJECT_ID}",
                    record_count=1,
                    return_geometry=False,
                )
                if len(sample) != 1 or _object_id(sample[0]) != SENTINEL_OBJECT_ID:
                    raise SourceSchemaError(
                        "Franklin sales sentinel occurrence changed",
                        url=LAYER_URL,
                        details={"sentinel_object_id": SENTINEL_OBJECT_ID},
                    )
                sentinel = _normalize_feature(
                    sample[0],
                    schema_fingerprint=schema_fingerprint,
                    geometry_requested=False,
                )
                requests_after = getattr(active_client, "request_count", None)
                probe_request_count = (
                    requests_after - requests_before
                    if isinstance(requests_before, int)
                    and isinstance(requests_after, int)
                    else None
                )
                rolling_coverage = {
                    key: statistics.get(key)
                    for key in (
                        "sale_date_min",
                        "sale_date_max",
                        "last_update_min",
                        "last_update_max",
                    )
                }
                rolling_coverage.update(
                    {
                        f"{key}_iso": _epoch_millis_iso(value)
                        for key, value in tuple(rolling_coverage.items())
                    }
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "service_item_id": ITEM_ID,
                            "layer_id": LAYER_ID,
                            "schema_fingerprint": schema_fingerprint,
                            "maximum_page_size": maximum,
                            "record_count": total_count,
                            "identity_audit": identity_audit,
                            "rolling_coverage": rolling_coverage,
                            "sentinel_occurrence_identity": sentinel[
                                "occurrence_identity"
                            ],
                            "probe_request_count": probe_request_count,
                            "expected_probe_request_count": (
                                PROBE_EXPECTED_REQUESTS
                            ),
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                where = _where(args)
                if args.cursor and args.limit is None:
                    raise FranklinSalesSelectionError(
                        "cursor_requires_limit",
                        "continuing a caller window requires --limit",
                    )
                if args.limit is None:
                    collection = fetch_all_features(
                        active_client,
                        where=where,
                        return_geometry=args.geometry,
                    )
                    selected = list(collection.features)
                    next_cursor = None
                    total_count = collection.total_count
                    bounded_count = collection.bounded_count
                    boundary_object_id = collection.boundary_object_id
                    schema_fingerprint = collection.schema_fingerprint
                    pages_fetched = collection.pages_fetched
                    native_pagination_complete = True
                    count_changed_since_cursor = False
                    limited_native_window = False
                else:
                    try:
                        batch = arcgis_shared.fetch_batch(
                            active_client,
                            MANIFEST,
                            adapter_slug="auditor-sales-gis",
                            operation=args.command,
                            where=where,
                            limit=args.limit,
                            cursor=args.cursor,
                            return_geometry=args.geometry,
                            cursor_namespace="ohio-franklin",
                        )
                    except ValueError as error:
                        raise FranklinSalesSelectionError(
                            "invalid_cursor",
                            str(error),
                        ) from error
                    selected = list(batch.features)
                    next_cursor = batch.next_cursor
                    total_count = batch.total_count
                    bounded_count = batch.bounded_count
                    boundary_object_id = batch.boundary_object_id
                    schema_fingerprint = batch.schema_fingerprint
                    pages_fetched = batch.pages_fetched
                    native_pagination_complete = next_cursor is None
                    count_changed_since_cursor = (
                        batch.count_changed_since_cursor
                    )
                    limited_native_window = True
                records = [
                    _normalize_feature(
                        feature,
                        schema_fingerprint=schema_fingerprint,
                        geometry_requested=args.geometry,
                    )
                    for feature in selected
                ]
                snapshot = {
                    "total_matching_records_at_retrieval": total_count,
                    "records_inside_objectid_boundary": bounded_count,
                    "boundary_object_id": boundary_object_id,
                    "native_pages_fetched": pages_fetched,
                    "native_pagination_complete": native_pagination_complete,
                    "caller_window_applied_during_native_keyset_traversal": (
                        limited_native_window
                    ),
                    "window_returned_records": len(records),
                    "continuation_available": next_cursor is not None,
                    "count_changed_since_cursor": count_changed_since_cursor,
                    "schema_fingerprint": schema_fingerprint,
                }
                for record in records:
                    record["retrieval_snapshot"] = snapshot
                warnings = list(SOURCE_WARNINGS)
                if next_cursor is not None:
                    warnings.append(
                        f"Caller window returned {len(records)} records; "
                        "continue with next_cursor for the same bounded snapshot."
                    )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    warnings=warnings,
                )
    except FranklinSalesSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = _schema_failure(query, error)
    finally:
        if owned_client and active_client is not None:
            active_client.close()
    if log_results:
        _best_effort_log(query, result)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Franklin County Auditor Sales GIS {args.command} "
            f"({result.status.value})"
        ),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Franklin County Auditor Sales GIS {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command in {"source", "layers", "schema", "count", "probe"}:
            print(f"  {record.get('source_id', SOURCE_ID)}")
        else:
            print(
                f"  {record.get('parcel_id') or record['source_record_id']} | "
                f"{record.get('conveyance_number') or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Native keyset page size, bounded by live layer metadata",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def _add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Bounded native keyset window; omit to exhaust the selection",
    )
    parser.add_argument(
        "--cursor",
        help="Resume a query/schema/snapshot-bound keyset window",
    )
    parser.add_argument(
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include the sale-location point transformed to EPSG:4326",
    )
    _add_transport_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Franklin County Auditor Sales Information GIS"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show source, identity, qualification, and lineage semantics",
    )
    add_output_args(source)

    layers = subparsers.add_parser(
        "layers",
        help="Distinguish canonical layer 0 from renderer aliases 1-4",
    )
    add_output_args(layers)

    schema = subparsers.add_parser(
        "schema",
        help="Validate and report the live layer schema",
    )
    _add_transport_args(schema)

    count = subparsers.add_parser(
        "count",
        help="Return the current complete layer count",
    )
    _add_transport_args(count)

    probe = subparsers.add_parser(
        "probe",
        help="Validate schema, identity state, rolling coverage, and sentinel",
    )
    _add_transport_args(probe)

    search = subparsers.add_parser(
        "search",
        help="Search sale parties, parcel IDs, conveyances, and addresses",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("all", *SEARCH_FIELDS, "object-id"),
        default="all",
    )
    _add_record_args(search)

    parcel = subparsers.add_parser(
        "parcel",
        help="Look up an exact published PARCELID",
    )
    parcel.add_argument("query")
    _add_record_args(parcel)

    conveyance = subparsers.add_parser(
        "conveyance",
        help="Look up an exact published ConveyanceNum",
    )
    conveyance.add_argument("query")
    _add_record_args(conveyance)

    party = subparsers.add_parser(
        "party",
        help="Search grantor and grantee observations",
    )
    party.add_argument("query")
    _add_record_args(party)

    date_range = subparsers.add_parser(
        "date-range",
        help="Search an inclusive sale-date range",
    )
    date_range.add_argument("--start", type=_iso_date)
    date_range.add_argument("--end", type=_iso_date)
    _add_record_args(date_range)

    validity = subparsers.add_parser(
        "validity",
        help="Search the raw Auditor ValidSale qualification",
    )
    validity.add_argument("query")
    _add_record_args(validity)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if (
        getattr(args, "command", None) == "date-range"
        and args.start is not None
        and args.end is not None
        and args.start > args.end
    ):
        parser.error("--start must not exceed --end")
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
