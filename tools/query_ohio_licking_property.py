#!/usr/bin/env python3
"""Query the official Licking County Auditor parcel-search GIS layer.

The layer publishes assessor/tax-roll observations, recent transfer fields,
and parcel polygons.  A feature occurrence is identified by ``GlobalID``
(falling back to ``OBJECTID``); the published parcel number is a separate
business key.  This distinction keeps every source feature attributable even
when a row has no parcel number or a future release repeats one.

Every record operation exhausts the ordered native ArcGIS result set before
applying an optional caller ``--limit`` window.  Continuations are bound to the
query, declared schema, and complete ordered membership.

Examples:
    uv run python tools/query_ohio_licking_property.py metadata --json
    uv run python tools/query_ohio_licking_property.py parcel \
        001-000006-01.000 --geometry --json
    uv run python tools/query_ohio_licking_property.py owner SMITH --limit 25 \
        --output /tmp/licking-owner.json
    uv run python tools/query_ohio_licking_property.py value \
        --field market-total --minimum 1000000 --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
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


SOURCE_ID = "us-oh-licking-county-auditor-gis"
STATE_CODE = "OH"
STATE_FIPS = "39"
COUNTY_GEOID = "39089"
COUNTY_NAME = "Licking County"
VIEWER_URL = (
    "https://apps.lickingcounty.gov/maps/taxparcelviewer/default.html"
)
LAYER_URL = (
    "https://gis.lickingcounty.gov/server/rest/services/"
    "Auditor/ParcelsSearch/MapServer/0"
)
ITEM_ID = "2203dea8729044d4990050b111c0ecff"
DEFAULT_PAGE_SIZE = 1_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "ohio-licking-auditor-gis:v1:"
SENTINEL_PARCEL = "001-000006-01.000"
PROBE_EXPECTED_REQUESTS = 4

FIELDS = (
    "OBJECTID",
    "PID",
    "Parcel",
    "OwnerName",
    "SiteAddress",
    "SiteAddressNumber",
    "SiteStreet",
    "SitePostalCity",
    "SitePostalZip",
    "Jurisdiction",
    "Municipality",
    "Township",
    "TaxAcres",
    "CAUVAcres",
    "GISAcres",
    "LegalDescription",
    "PlatBookPage",
    "PlatInstrument",
    "PlatName1",
    "PlatName2",
    "Instrument",
    "EpinCount",
    "TaxDistrictID",
    "TaxDistrict",
    "SchoolDistrict",
    "LUC",
    "Landuse",
    "Class",
    "RoutingNumber",
    "RoutingMap",
    "RoutingID",
    "NeighborhoodID",
    "Neighborhood",
    "Dwelling",
    "YearBuilt",
    "LivingAreaSqFt",
    "MarketLandValue",
    "CAUVLandValue",
    "ExemptLandValue",
    "MarketImpValue",
    "AbatedImpValue",
    "ExemptImpValue",
    "MarketTotalValue",
    "NetTotalValue",
    "TIF",
    "OwnerOccupied",
    "Homestead",
    "OwnerAddress",
    "OwnerCareOf",
    "OwnerAttention",
    "OwnerCity",
    "OwnerState",
    "OwnerZip",
    "OwnerZip4",
    "T1From",
    "T1To",
    "T1Date",
    "T1TransferType",
    "T1InstrumentType",
    "T1Instrument",
    "T1SaleAmount",
    "T1Valid",
    "T1Parcels",
    "T2From",
    "T2To",
    "T2Date",
    "T2TransferType",
    "T2InstrumentType",
    "T2Instrument",
    "T2SaleAmount",
    "T2Valid",
    "T2Parcels",
    "T3From",
    "T3To",
    "T3Date",
    "T3TransferType",
    "T3InstrumentType",
    "T3Instrument",
    "T3SaleAmount",
    "T3Valid",
    "T3Parcels",
    "GlobalID",
    "Shape.STArea()",
    "Shape.STLength()",
)

VALUE_FIELDS: Mapping[str, str] = {
    "tax-acres": "TaxAcres",
    "cauv-acres": "CAUVAcres",
    "gis-acres": "GISAcres",
    "year-built": "YearBuilt",
    "living-area": "LivingAreaSqFt",
    "market-land": "MarketLandValue",
    "cauv-land": "CAUVLandValue",
    "exempt-land": "ExemptLandValue",
    "market-improvement": "MarketImpValue",
    "abated-improvement": "AbatedImpValue",
    "exempt-improvement": "ExemptImpValue",
    "market-total": "MarketTotalValue",
    "net-total": "NetTotalValue",
    "sale-amount-1": "T1SaleAmount",
    "sale-amount-2": "T2SaleAmount",
    "sale-amount-3": "T3SaleAmount",
}

ATTRIBUTE_FIELDS: Mapping[str, str] = {
    "jurisdiction": "Jurisdiction",
    "municipality": "Municipality",
    "township": "Township",
    "legal-description": "LegalDescription",
    "plat-book-page": "PlatBookPage",
    "plat-instrument": "PlatInstrument",
    "plat-name": "PlatName1",
    "instrument": "Instrument",
    "tax-district-id": "TaxDistrictID",
    "tax-district": "TaxDistrict",
    "school-district": "SchoolDistrict",
    "land-use": "Landuse",
    "class": "Class",
    "routing-number": "RoutingNumber",
    "routing-map": "RoutingMap",
    "routing-id": "RoutingID",
    "neighborhood-id": "NeighborhoodID",
    "neighborhood": "Neighborhood",
    "dwelling": "Dwelling",
    "tif": "TIF",
    "owner-occupied": "OwnerOccupied",
    "homestead": "Homestead",
}

MANIFEST = arcgis_shared.ArcGISLayerManifest(
    source_id=SOURCE_ID,
    name="Licking County Auditor Parcel Search GIS",
    layer_url=LAYER_URL,
    layer_id=0,
    service_item_id=ITEM_ID,
    expected_layer_name="Parcels",
    object_id_field="OBJECTID",
    required_fields=FIELDS,
    source_crs_wkids=(102723, 3735),
    record_kind="county_assessor_parcel_feature_occurrence",
    publisher="Licking County Auditor",
    observed_count=83_796,
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Licking County Auditor Parcel Search GIS",
    source_role=(
        "official_county_assessor_parcel_owner_address_value_transfer_"
        "attribute_and_geometry_observations"
    ),
    base_url=LAYER_URL,
    dataset_id=ITEM_ID,
    metadata={
        "authority": "Licking County Auditor",
        "platform_family": "arcgis_mapserver_feature_layer",
        "county_geoid": COUNTY_GEOID,
        "viewer_url": VIEWER_URL,
        "record_grain": "published_feature_occurrence",
        "parcel_join_field": "Parcel",
        "occurrence_identity_fields": ["GlobalID", "OBJECTID"],
        "assessment_owner_is_recorded_title": False,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS, "county_geoid": COUNTY_GEOID},
)

SOURCE_WARNINGS = (
    "OwnerName and mailing fields are county assessment-roll observations, "
    "not recorded-title findings.",
    "T1/T2/T3 fields are source-published transfer observations; recorder "
    "instruments remain the controlling recorded-document representation.",
    "Parcel polygons are administrative mapping geometry rather than surveyed "
    "legal boundaries.",
)


class LickingPropertySelectionError(ValueError):
    """A caller selection or continuation cannot be applied."""

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


class LickingPropertyClient(arcgis_shared.BoundedArcGISClient):
    """Source-named binding for the shared bounded ArcGIS transport."""


@dataclass(frozen=True)
class LickingFeatureCollection:
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


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _finite_number(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("value must be finite")
    return parsed


def _sql_number(value: float) -> str:
    """Render a finite CLI float as a non-exponent ArcGIS SQL literal."""

    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sql_text(value: Any, label: str = "query") -> str:
    text = str(value).strip()
    if not text:
        raise LickingPropertySelectionError(
            "empty_query",
            f"{label} must not be empty",
        )
    if "\x00" in text:
        raise LickingPropertySelectionError(
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
            "Licking parcel feature lacks an integer OBJECTID",
            url=LAYER_URL,
            details={"OBJECTID": value},
        )
    return value


def _where(args: argparse.Namespace) -> str:
    command = args.command
    if command == "list":
        return "1=1"
    if command == "occurrence":
        return f"OBJECTID={int(args.object_id)}"
    if command == "parcel":
        return f"Parcel='{_sql_text(args.query, 'parcel number')}'"
    if command == "value":
        field = VALUE_FIELDS[args.field]
        clauses = [f"{field} IS NOT NULL"]
        if args.minimum is not None:
            clauses.append(f"{field}>={_sql_number(args.minimum)}")
        if args.maximum is not None:
            clauses.append(f"{field}<={_sql_number(args.maximum)}")
        if len(clauses) == 1:
            raise LickingPropertySelectionError(
                "value_range_required",
                "value search requires --minimum, --maximum, or both",
            )
        return " AND ".join(clauses)
    term = _sql_text(getattr(args, "query", "")).upper()
    if command == "owner":
        return f"UPPER(OwnerName) LIKE '%{term}%'"
    if command == "situs":
        fields = (
            "SiteAddress",
            "SiteAddressNumber",
            "SiteStreet",
            "SitePostalCity",
            "SitePostalZip",
        )
        return "(" + " OR ".join(
            f"UPPER({field}) LIKE '%{term}%'" for field in fields
        ) + ")"
    if command == "mailing":
        fields = (
            "OwnerAddress",
            "OwnerCareOf",
            "OwnerAttention",
            "OwnerCity",
            "OwnerState",
            "OwnerZip",
            "OwnerZip4",
        )
        return "(" + " OR ".join(
            f"UPPER({field}) LIKE '%{term}%'" for field in fields
        ) + ")"
    if command == "attribute":
        field = ATTRIBUTE_FIELDS[args.field]
        if args.match == "exact":
            return f"UPPER({field})='{term}'"
        return f"UPPER({field}) LIKE '%{term}%'"
    raise LickingPropertySelectionError(
        "unsupported_operation",
        f"unsupported Licking property operation: {command}",
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
    client: LickingPropertyClient | Any,
    *,
    where: str,
    return_geometry: bool,
) -> LickingFeatureCollection:
    """Exhaust one source snapshot with monotonic OBJECTID keyset paging."""

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
                "Licking parcel count was nonzero but no boundary row was returned",
                url=LAYER_URL,
                details={"reported_count": total_count},
            )
        return LickingFeatureCollection(
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
                    "Licking parcel paging repeated or crossed its snapshot boundary",
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
                "Licking parcel traversal exceeded its snapshot count",
                url=LAYER_URL,
                details={
                    "snapshot_count": bounded_count,
                    "collected": len(features),
                },
            )

    if len(features) != bounded_count:
        raise SourceSchemaError(
            "Licking parcel traversal did not yield its snapshot count",
            url=LAYER_URL,
            details={
                "snapshot_count": bounded_count,
                "collected": len(features),
                "boundary_object_id": boundary,
            },
        )
    return LickingFeatureCollection(
        features=tuple(features),
        total_count=total_count,
        bounded_count=bounded_count,
        boundary_object_id=boundary,
        schema_fingerprint=schema_fingerprint,
        maximum_page_size=maximum_page_size,
        pages_fetched=pages_fetched,
    )


def _selection_fingerprint(selection: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(selection).encode("utf-8")
    ).hexdigest()


def _membership_fingerprint(
    features: Sequence[Mapping[str, Any]],
) -> str:
    membership = []
    for feature in features:
        attributes = arcgis_shared.feature_attributes(feature)
        membership.append(
            [
                attributes.get("OBJECTID"),
                _clean_text(attributes.get("GlobalID")),
                _clean_text(attributes.get("Parcel")),
            ]
        )
    return hashlib.sha256(
        canonical_json(membership).encode("utf-8")
    ).hexdigest()


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise LickingPropertySelectionError(
            "invalid_cursor",
            "cursor is not a Licking County Auditor GIS continuation",
        )
    token = value.removeprefix(CURSOR_PREFIX)
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            ).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise LickingPropertySelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping):
        raise LickingPropertySelectionError(
            "invalid_cursor",
            "cursor payload changed type",
        )
    return payload


def _window_features(
    collection: LickingFeatureCollection,
    *,
    selection: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    if cursor and limit is None:
        raise LickingPropertySelectionError(
            "cursor_requires_limit",
            "continuing a caller window requires --limit",
        )
    selection_hash = _selection_fingerprint(selection)
    membership_hash = _membership_fingerprint(collection.features)
    offset = 0
    if cursor:
        payload = _decode_cursor(cursor)
        if payload.get("source_id") != SOURCE_ID:
            raise LickingPropertySelectionError(
                "cursor_source_mismatch",
                "cursor belongs to another source",
            )
        if payload.get("selection_fingerprint") != selection_hash:
            raise LickingPropertySelectionError(
                "cursor_query_mismatch",
                "cursor belongs to another selector set",
            )
        if (
            payload.get("schema_fingerprint")
            != collection.schema_fingerprint
            or payload.get("membership_fingerprint") != membership_hash
            or payload.get("total") != len(collection.features)
        ):
            raise LickingPropertySelectionError(
                "cursor_membership_changed",
                "ordered source-response membership changed",
            )
        try:
            offset = int(payload["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise LickingPropertySelectionError(
                "invalid_cursor",
                "cursor offset is invalid",
            ) from error
        if offset < 0 or offset > len(collection.features):
            raise LickingPropertySelectionError(
                "invalid_cursor",
                "cursor offset is outside the source response",
            )

    end = (
        len(collection.features)
        if limit is None
        else min(offset + limit, len(collection.features))
    )
    window = list(collection.features[offset:end])
    next_cursor = None
    if end < len(collection.features):
        next_cursor = _encode_cursor(
            {
                "source_id": SOURCE_ID,
                "selection_fingerprint": selection_hash,
                "schema_fingerprint": collection.schema_fingerprint,
                "membership_fingerprint": membership_hash,
                "offset": end,
                "total": len(collection.features),
            }
        )
    return window, next_cursor


def _transfer(attributes: Mapping[str, Any], position: int) -> dict[str, Any] | None:
    prefix = f"T{position}"
    values = {
        "sequence": position,
        "from": _clean_text(attributes.get(f"{prefix}From")),
        "to": _clean_text(attributes.get(f"{prefix}To")),
        "date_raw": attributes.get(f"{prefix}Date"),
        "date_iso": _epoch_millis_iso(attributes.get(f"{prefix}Date")),
        "transfer_type": _clean_text(attributes.get(f"{prefix}TransferType")),
        "instrument_type": _clean_text(
            attributes.get(f"{prefix}InstrumentType")
        ),
        "instrument": _clean_text(attributes.get(f"{prefix}Instrument")),
        "sale_amount": attributes.get(f"{prefix}SaleAmount"),
        "valid_sale": _clean_text(attributes.get(f"{prefix}Valid")),
        "parcel_count": attributes.get(f"{prefix}Parcels"),
    }
    if all(value is None for key, value in values.items() if key != "sequence"):
        return None
    return values


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = dict(arcgis_shared.feature_attributes(feature))
    object_id = _object_id(feature)
    global_id = _clean_text(attributes.get("GlobalID"))
    parcel_number = _clean_text(attributes.get("Parcel"))
    occurrence_native_id = global_id or f"OBJECTID:{object_id}"
    occurrence_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "feature_occurrence",
        occurrence_native_id,
    )
    parcel_ref = (
        canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            parcel_number,
        )
        if parcel_number is not None
        else None
    )
    transfers = [
        transfer
        for position in (1, 2, 3)
        if (transfer := _transfer(attributes, position)) is not None
    ]
    geometry = feature.get("geometry") if geometry_requested else None

    record: dict[str, Any] = {
        "record_kind": "county_assessor_parcel_feature_occurrence",
        "source_id": SOURCE_ID,
        "dataset_id": ITEM_ID,
        "source_record_id": str(object_id),
        "native_id": occurrence_native_id,
        "canonical_ref": occurrence_ref,
        "occurrence_identity": {
            "native_id": occurrence_native_id,
            "identity_basis": "GlobalID" if global_id else "OBJECTID",
            "global_id": global_id,
            "object_id": object_id,
            "canonical_ref": occurrence_ref,
        },
        "parcel_identity": (
            {
                "parcel_number": parcel_number,
                "canonical_ref": parcel_ref,
                "identity_role": "published_business_join_candidate",
            }
            if parcel_number is not None
            else None
        ),
        "identity_state": (
            "occurrence_and_parcel_key"
            if parcel_number is not None
            else "occurrence_only"
        ),
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "pid": attributes.get("PID"),
        "parcel_number": parcel_number,
        "owner_name_observation": _clean_text(attributes.get("OwnerName")),
        "assessment_owner_semantics": "assessment_roll_observation_not_title",
        "situs_address_observation": {
            "raw": _clean_text(attributes.get("SiteAddress")),
            "number": _clean_text(attributes.get("SiteAddressNumber")),
            "street": _clean_text(attributes.get("SiteStreet")),
            "city": _clean_text(attributes.get("SitePostalCity")),
            "postal_code": _clean_text(attributes.get("SitePostalZip")),
        },
        "mailing_address_observation": {
            "address": _clean_text(attributes.get("OwnerAddress")),
            "care_of": _clean_text(attributes.get("OwnerCareOf")),
            "attention": _clean_text(attributes.get("OwnerAttention")),
            "city": _clean_text(attributes.get("OwnerCity")),
            "state": _clean_text(attributes.get("OwnerState")),
            "postal_code": _clean_text(attributes.get("OwnerZip")),
            "postal_code_extension": _clean_text(attributes.get("OwnerZip4")),
        },
        "administrative_geography": {
            "jurisdiction": _clean_text(attributes.get("Jurisdiction")),
            "municipality": _clean_text(attributes.get("Municipality")),
            "township": _clean_text(attributes.get("Township")),
            "tax_district_id": _clean_text(attributes.get("TaxDistrictID")),
            "tax_district": _clean_text(attributes.get("TaxDistrict")),
            "school_district": _clean_text(attributes.get("SchoolDistrict")),
            "neighborhood_id": _clean_text(attributes.get("NeighborhoodID")),
            "neighborhood": _clean_text(attributes.get("Neighborhood")),
        },
        "land_and_classification": {
            "tax_acres": attributes.get("TaxAcres"),
            "cauv_acres": attributes.get("CAUVAcres"),
            "gis_acres": attributes.get("GISAcres"),
            "land_use_code": attributes.get("LUC"),
            "land_use": _clean_text(attributes.get("Landuse")),
            "class": _clean_text(attributes.get("Class")),
            "legal_description": _clean_text(
                attributes.get("LegalDescription")
            ),
        },
        "plat_and_routing": {
            "plat_book_page": _clean_text(attributes.get("PlatBookPage")),
            "plat_instrument": _clean_text(attributes.get("PlatInstrument")),
            "plat_name_1": _clean_text(attributes.get("PlatName1")),
            "plat_name_2": _clean_text(attributes.get("PlatName2")),
            "instrument": _clean_text(attributes.get("Instrument")),
            "epin_count": attributes.get("EpinCount"),
            "routing_number": _clean_text(attributes.get("RoutingNumber")),
            "routing_map": _clean_text(attributes.get("RoutingMap")),
            "routing_id": _clean_text(attributes.get("RoutingID")),
        },
        "improvements": {
            "dwelling": _clean_text(attributes.get("Dwelling")),
            "year_built": attributes.get("YearBuilt"),
            "living_area_sq_ft": attributes.get("LivingAreaSqFt"),
        },
        "assessment_value_observations": {
            "market_land": attributes.get("MarketLandValue"),
            "cauv_land": attributes.get("CAUVLandValue"),
            "exempt_land": attributes.get("ExemptLandValue"),
            "market_improvement": attributes.get("MarketImpValue"),
            "abated_improvement": attributes.get("AbatedImpValue"),
            "exempt_improvement": attributes.get("ExemptImpValue"),
            "market_total": attributes.get("MarketTotalValue"),
            "net_total": attributes.get("NetTotalValue"),
            "currency": "USD",
        },
        "program_flags": {
            "tif": _clean_text(attributes.get("TIF")),
            "owner_occupied": _clean_text(attributes.get("OwnerOccupied")),
            "homestead": _clean_text(attributes.get("Homestead")),
        },
        "recent_transfer_observations": transfers,
        "recorded_title_evidence": False,
        "shape_metrics_native": {
            "area": attributes.get("Shape.STArea()"),
            "length": attributes.get("Shape.STLength()"),
        },
        "source_layer_url": LAYER_URL,
        "source_viewer_url": VIEWER_URL,
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
                "geometry_role": "county_assessor_parcel_mapping_polygon",
            }
        )
    return record


def _source_record() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "native_manifest": MANIFEST.contract_record(),
        "official_routes": {
            "viewer": VIEWER_URL,
            "layer": LAYER_URL,
            "query": MANIFEST.query_url,
        },
        "verified_operations": [
            "metadata",
            "probe",
            "list",
            "parcel",
            "occurrence",
            "owner",
            "situs",
            "mailing",
            "value",
            "attribute",
            "geometry_via_record_operations",
        ],
        "identity_contract": {
            "occurrence": "GlobalID, with OBJECTID as the row locator/fallback",
            "parcel_business_key": "Parcel when nonblank",
            "join_policy": (
                "retain every feature occurrence; expose Parcel separately as "
                "a candidate business join"
            ),
            "live_audit_2026_07_31": {
                "total_occurrences": 83_796,
                "nonnull_parcel_values": 82_604,
                "unique_nonnull_parcel_values": 82_604,
                "null_parcel_occurrences": 1_192,
                "empty_string_parcel_occurrences": 0,
                "null_global_id_occurrences": 0,
            },
        },
        "source_relationships": [
            {
                "source_id": "us-oh-licking-county-auditor-ontrac",
                "relationship": "same_authority_assessment_route",
                "role": "interactive_property_detail_complement",
                "independent_corroboration_for_overlapping_fields": False,
            },
            {
                "source_id": "us-oh-ogrip-statewide-parcels",
                "relationship": "county_origin_statewide_representation",
                "role": "statewide_parcel_and_geometry_index",
                "independent_corroboration_for_overlapping_fields": False,
            },
            {
                "source_id": "us-oh-licking-county-recorder-pax",
                "relationship": "different_official_record_domain",
                "role": "recorded_instrument_and_party_evidence",
            },
        ],
        "warnings": list(SOURCE_WARNINGS),
    }


def _metadata_record(
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
    for key in (
        "query",
        "object_id",
        "field",
        "match",
        "minimum",
        "maximum",
        "geometry",
    ):
        if hasattr(args, key):
            parameters[key] = getattr(args, key)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "adapter": "tools/query_ohio_licking_property.py",
                "pagination": (
                    "complete_objectid_keyset_snapshot_then_caller_window"
                ),
            },
        ),
    )


def _new_client(args: argparse.Namespace) -> LickingPropertyClient:
    return LickingPropertyClient(
        MANIFEST,
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: LickingPropertySelectionError,
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
    owned_client = client is None and args.command != "source"
    try:
        if args.command == "source":
            result = PublicRecordsResult.success(query, [_source_record()])
        else:
            active_client = active_client or _new_client(args)
            if args.command == "metadata":
                metadata = active_client.fetch_metadata()
                schema_fingerprint, maximum = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                result = PublicRecordsResult.success(
                    query,
                    [_metadata_record(metadata, schema_fingerprint, maximum)],
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
                null_parcel_count = active_client.fetch_count("Parcel IS NULL")
                sample = active_client.fetch_page(
                    where=f"Parcel='{SENTINEL_PARCEL}'",
                    record_count=2,
                    return_geometry=False,
                )
                if len(sample) != 1 or _clean_text(
                    arcgis_shared.feature_attributes(sample[0]).get("Parcel")
                ) != SENTINEL_PARCEL:
                    raise SourceSchemaError(
                        "Licking parcel sentinel identity changed",
                        url=LAYER_URL,
                        details={"sentinel_parcel": SENTINEL_PARCEL},
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
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "schema_fingerprint": schema_fingerprint,
                            "maximum_page_size": maximum,
                            "record_count": total_count,
                            "null_parcel_occurrence_count": null_parcel_count,
                            "sentinel_parcel": SENTINEL_PARCEL,
                            "sentinel_occurrence_identity": sentinel[
                                "occurrence_identity"
                            ],
                            "probe_request_count": probe_request_count,
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                where = _where(args)
                collection = fetch_all_features(
                    active_client,
                    where=where,
                    return_geometry=args.geometry,
                )
                selection = {
                    "source_id": SOURCE_ID,
                    "operation": args.command,
                    "where": where,
                    "return_geometry": args.geometry,
                    "ordering": "OBJECTID ASC",
                }
                selected, next_cursor = _window_features(
                    collection,
                    selection=selection,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                records = [
                    _normalize_feature(
                        feature,
                        schema_fingerprint=collection.schema_fingerprint,
                        geometry_requested=args.geometry,
                    )
                    for feature in selected
                ]
                snapshot = {
                    "total_matching_records_at_retrieval": (
                        collection.total_count
                    ),
                    "records_inside_objectid_boundary": (
                        collection.bounded_count
                    ),
                    "boundary_object_id": collection.boundary_object_id,
                    "native_pages_fetched": collection.pages_fetched,
                    "native_pagination_complete": True,
                    "caller_window_applied_after_native_exhaustion": (
                        args.limit is not None
                    ),
                    "window_returned_records": len(records),
                    "continuation_available": next_cursor is not None,
                    "schema_fingerprint": collection.schema_fingerprint,
                }
                for record in records:
                    record["retrieval_snapshot"] = snapshot
                warnings = list(SOURCE_WARNINGS)
                if args.limit is not None and len(records) < len(
                    collection.features
                ):
                    warnings.append(
                        f"Caller window returned {len(records)} of "
                        f"{len(collection.features)} collected occurrences."
                    )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    warnings=warnings,
                )
    except LickingPropertySelectionError as error:
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
            f"Licking County Auditor GIS {args.command} "
            f"({result.status.value})"
        ),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Licking County Auditor GIS {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command in {"source", "metadata", "probe"}:
            print(f"  {record.get('source_id', SOURCE_ID)}")
        else:
            print(
                f"  {record.get('parcel_number') or record['source_record_id']} | "
                f"{record.get('owner_name_observation') or '?'}"
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
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=3,
    )
    add_output_args(parser)


def _add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Caller window applied after complete native traversal",
    )
    parser.add_argument(
        "--cursor",
        help="Resume a query/schema/membership-bound caller window",
    )
    parser.add_argument(
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include parcel geometry transformed to EPSG:4326",
    )
    _add_transport_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Licking County Auditor parcel GIS"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show verified source, field, identity, and lineage semantics",
    )
    add_output_args(source)

    metadata = subparsers.add_parser(
        "metadata",
        help="Validate and report the live ArcGIS layer contract",
    )
    _add_transport_args(metadata)

    probe = subparsers.add_parser(
        "probe",
        help="Validate schema, counts, null identity state, and a sentinel",
    )
    _add_transport_args(probe)

    listing = subparsers.add_parser(
        "list",
        help="Traverse all published feature occurrences",
    )
    _add_record_args(listing)

    parcel = subparsers.add_parser(
        "parcel",
        help="Look up an exact published Auditor parcel number",
    )
    parcel.add_argument("query")
    _add_record_args(parcel)

    occurrence = subparsers.add_parser(
        "occurrence",
        help="Look up an exact layer OBJECTID occurrence",
    )
    occurrence.add_argument("object_id", type=_positive_int)
    _add_record_args(occurrence)

    owner = subparsers.add_parser(
        "owner",
        help="Search assessment-roll owner-name observations",
    )
    owner.add_argument("query")
    _add_record_args(owner)

    situs = subparsers.add_parser(
        "situs",
        help="Search published situs-address components",
    )
    situs.add_argument("query")
    _add_record_args(situs)

    mailing = subparsers.add_parser(
        "mailing",
        help="Search published owner-mailing-address components",
    )
    mailing.add_argument("query")
    _add_record_args(mailing)

    value = subparsers.add_parser(
        "value",
        help="Search a published numeric acreage, building, value, or sale field",
    )
    value.add_argument("--field", choices=tuple(VALUE_FIELDS), required=True)
    value.add_argument("--minimum", type=_finite_number)
    value.add_argument("--maximum", type=_finite_number)
    _add_record_args(value)

    attribute = subparsers.add_parser(
        "attribute",
        help="Search a published classification, district, routing, or plat field",
    )
    attribute.add_argument("field", choices=tuple(ATTRIBUTE_FIELDS))
    attribute.add_argument("query")
    attribute.add_argument(
        "--match",
        choices=("contains", "exact"),
        default="contains",
    )
    _add_record_args(attribute)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if (
        getattr(args, "command", None) == "value"
        and args.minimum is not None
        and args.maximum is not None
        and args.minimum > args.maximum
    ):
        parser.error("--minimum must not exceed --maximum")
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
