#!/usr/bin/env python3
"""Query Mason County's official Tax Parcels ArcGIS layer.

The county layer is a current GIS/assessment representation.  Its ArcGIS
metadata explicitly reports that offset pagination and server-side ordering
are unsupported.  Record traversal therefore snapshots the matching ``FID``
values with ``returnIdsOnly=true``, sorts them client-side, and retrieves
features by bounded ``objectIds`` batches.

``FID`` identifies a source feature occurrence.  ``PIN``, ``TERRA_PIN``, and
``Taxlot`` are retained separately as candidate parcel join identifiers; the
adapter does not assume that any one of them is unique in the layer.

Examples:
    uv run python tools/query_mason_county_tax_parcels.py metadata
    uv run python tools/query_mason_county_tax_parcels.py parcel 1234567890123
    uv run python tools/query_mason_county_tax_parcels.py owner SMITH
    uv run python tools/query_mason_county_tax_parcels.py address "100 MAIN"
    uv run python tools/query_mason_county_tax_parcels.py point -123.10 47.20
    uv run python tools/query_mason_county_tax_parcels.py probe
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        acquisition_result_status,
    )
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        PaginationError,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        _BaseJSONClient,
        arcgis_declared_schema,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        acquisition_result_status,
    )
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_http import (
        PaginationError,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        _BaseJSONClient,
        arcgis_declared_schema,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-wa-mason-county-tax-parcels-gis"
COUNTY_GEOID = "53045"
STATE_FIPS = "53"
STATE_CODE = "WA"
COUNTY_NAME = "Mason"
LAYER_URL = (
    "https://gis.masoncountywa.gov/arcgis/rest/services/"
    "MasonCoSite/TaxParcels/MapServer/0"
)
QUERY_URL = f"{LAYER_URL}/query"
OBJECT_ID_FIELD = "FID"
LAYER_NAME = "Tax Parcels (Zoom in to 1:30,000)"
GEOMETRY_TYPE = "esriGeometryPolygon"
OUTPUT_CRS = "EPSG:4326"
CURSOR_PREFIX = "mason-tax-parcels:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRY_ATTEMPTS = 3

REQUIRED_FIELDS = (
    "FID",
    "PIN",
    "Taxlot",
    "Map_number",
    "TERRA_PIN",
    "Assessment",
    "IsExempt",
    "TotalMarke",
    "TotalAsses",
    "MarketLand",
    "MarketBuil",
    "AssessedLa",
    "AssessedBu",
    "ResultingT",
    "TotalAcres",
    "LastName",
    "FirstName",
    "Address1",
    "Address2",
    "City",
    "State",
    "Zip",
    "Situs",
    "AssembledL",
    "SubName",
)

PARCEL_FIELDS = ("PIN", "TERRA_PIN", "Taxlot")
OWNER_FIELDS = ("LastName", "FirstName")
ADDRESS_FIELDS = ("Situs", "Address1", "Address2", "City", "Zip")
SEARCH_FIELDS = {
    "parcel": PARCEL_FIELDS,
    "owner": OWNER_FIELDS,
    "address": ADDRESS_FIELDS,
    "assessment": ("Assessment",),
    "afn": ("AFN",),
    "subdivision": ("SubName", "AssembledL"),
}
SEARCH_FIELDS["any"] = tuple(
    dict.fromkeys(
        (
            *PARCEL_FIELDS,
            *OWNER_FIELDS,
            *ADDRESS_FIELDS,
            "Assessment",
            "AFN",
            "SubName",
            "AssembledL",
        )
    )
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Mason County Tax Parcels GIS",
    source_role="county_parcel_assessment_geometry",
    base_url=LAYER_URL,
    dataset_id="MasonCoSite/TaxParcels/MapServer/0",
    metadata={
        "authority": "Mason County, Washington",
        "operator": "Mason County GIS",
        "county_geoid": COUNTY_GEOID,
        "record_grain": "current_parcel_assessment_geometry_feature",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Mason County, Washington",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    metadata={"state_fips": STATE_FIPS, "county_fips_3": "045"},
)
SOURCE_WARNINGS = (
    "The layer publishes current assessor/GIS names, addresses, values, and "
    "parcel geometry; it is not a recorder-instrument index or a treasury "
    "balance/payment-history source.",
    "A source feature FID and a parcel join identifier are different "
    "identities; PIN, TERRA_PIN, and Taxlot uniqueness is not assumed.",
)


@dataclass(frozen=True)
class LayerContract:
    schema_fingerprint: str
    field_names: tuple[str, ...]
    max_record_count: int
    object_id_field: str
    geometry_type: str
    spatial_reference: Mapping[str, Any]
    supports_pagination: bool
    supports_order_by: bool
    supports_statistics: bool
    supports_advanced_queries: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_fingerprint": self.schema_fingerprint,
            "field_names": list(self.field_names),
            "max_record_count": self.max_record_count,
            "object_id_field": self.object_id_field,
            "geometry_type": self.geometry_type,
            "spatial_reference": dict(self.spatial_reference),
            "supports_pagination": self.supports_pagination,
            "supports_order_by": self.supports_order_by,
            "supports_statistics": self.supports_statistics,
            "supports_advanced_queries": self.supports_advanced_queries,
        }


@dataclass(frozen=True)
class QuerySpec:
    where: str
    geometry_parameters: Mapping[str, Any]
    return_geometry: bool


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    schema_fingerprint: str
    ids_fingerprint: str
    offset: int
    last_object_id: int
    total_count: int


@dataclass(frozen=True)
class FeatureBatch:
    features: tuple[Mapping[str, Any], ...]
    contract: LayerContract
    matching_object_ids: tuple[int, ...]
    ids_fingerprint: str
    next_cursor: str | None
    requests_made: int


class MasonParcelSelectionError(ValueError):
    """A caller selection or continuation error with an explicit result state."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query_selection",
            retryable=False,
            details=self.details,
        )


class MasonCountyTaxParcelsClient(_BaseJSONClient):
    """Minimal ArcGIS client for a layer without offset/order support."""

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(LAYER_URL, params={"f": "json"})
        return _arcgis_object(payload, "layer metadata", LAYER_URL)

    def fetch_object_ids(
        self,
        *,
        where: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[int, ...]:
        payload = self._request_json(
            QUERY_URL,
            params={
                **dict(parameters or {}),
                "where": where,
                "returnIdsOnly": "true",
                "f": "json",
            },
        )
        value = _arcgis_object(payload, "object-ID query", QUERY_URL)
        declared_oid = value.get("objectIdFieldName")
        if declared_oid not in (None, OBJECT_ID_FIELD):
            raise SourceSchemaError(
                "Mason object-ID query changed its identity field",
                url=QUERY_URL,
                details={"objectIdFieldName": declared_oid},
            )
        raw_ids = value.get("objectIds")
        if not isinstance(raw_ids, list):
            raise SourceSchemaError(
                "Mason object-ID query lacks objectIds",
                url=QUERY_URL,
            )
        parsed = tuple(_object_id(item) for item in raw_ids)
        if len(parsed) != len(set(parsed)):
            raise PaginationError(
                "Mason object-ID snapshot contains duplicates",
                url=QUERY_URL,
            )
        return tuple(sorted(parsed))

    def fetch_features(
        self,
        object_ids: Sequence[int],
        *,
        return_geometry: bool,
    ) -> tuple[Mapping[str, Any], ...]:
        if not object_ids:
            return ()
        requested = tuple(_object_id(value) for value in object_ids)
        payload = self._request_json(
            QUERY_URL,
            params={
                "objectIds": ",".join(str(value) for value in requested),
                "outFields": "*",
                "returnGeometry": str(return_geometry).lower(),
                **({"outSR": 4326} if return_geometry else {}),
                "f": "json",
            },
        )
        value = _arcgis_object(payload, "feature query", QUERY_URL)
        if value.get("exceededTransferLimit") is True:
            raise PaginationError(
                "Mason feature query exceeded the published record ceiling",
                url=QUERY_URL,
                details={"requested_count": len(requested)},
            )
        raw_features = value.get("features")
        if not isinstance(raw_features, list) or any(
            not isinstance(feature, Mapping) for feature in raw_features
        ):
            raise SourceSchemaError(
                "Mason feature query lacks a valid features array",
                url=QUERY_URL,
            )
        features = tuple(raw_features)
        observed_ids = tuple(_feature_object_id(feature) for feature in features)
        if len(observed_ids) != len(set(observed_ids)):
            raise PaginationError(
                "Mason feature response repeats a source occurrence",
                url=QUERY_URL,
            )
        if set(observed_ids) != set(requested):
            raise PaginationError(
                "Mason feature response does not match requested object IDs",
                url=QUERY_URL,
                details={
                    "requested": list(requested),
                    "observed": list(observed_ids),
                },
            )
        return tuple(
            feature
            for _, feature in sorted(
                zip(observed_ids, features, strict=True),
                key=lambda item: item[0],
            )
        )


def _arcgis_object(
    payload: Any,
    description: str,
    url: str,
) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            f"Mason {description} response must be an object",
            url=url,
            details={"response_type": type(payload).__name__},
        )
    if "error" in payload:
        raise SourceResponseError(
            f"Mason {description} returned an ArcGIS error",
            url=url,
            details={"response": payload.get("error")},
        )
    return payload


def _field_definitions(
    metadata: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Mason layer metadata lacks a valid fields array",
            url=LAYER_URL,
        )
    return tuple(fields)


def metadata_contract(metadata: Mapping[str, Any]) -> LayerContract:
    """Validate the verified non-pageable layer contract."""

    fields = _field_definitions(metadata)
    field_names = tuple(str(field.get("name") or "") for field in fields)
    missing = sorted(set(REQUIRED_FIELDS) - set(field_names))
    if missing:
        raise SourceSchemaError(
            "Mason Tax Parcels layer is missing required fields",
            url=LAYER_URL,
            details={"missing_fields": missing},
        )

    oid_fields = [field for field in fields if field.get("type") == "esriFieldTypeOID"]
    if (
        len(oid_fields) != 1
        or oid_fields[0].get("name") != OBJECT_ID_FIELD
        or metadata.get("objectIdField") not in (None, OBJECT_ID_FIELD)
    ):
        raise SourceSchemaError(
            "Mason Tax Parcels feature identity contract changed",
            url=LAYER_URL,
            details={
                "oid_fields": [field.get("name") for field in oid_fields],
                "objectIdField": metadata.get("objectIdField"),
            },
        )
    if metadata.get("name") != LAYER_NAME:
        raise SourceSchemaError(
            "Mason Tax Parcels layer identity changed",
            url=LAYER_URL,
            details={"name": metadata.get("name")},
        )
    if metadata.get("type") != "Feature Layer":
        raise SourceSchemaError(
            "Mason Tax Parcels endpoint is no longer a feature layer",
            url=LAYER_URL,
            details={"type": metadata.get("type")},
        )
    if metadata.get("geometryType") != GEOMETRY_TYPE:
        raise SourceSchemaError(
            "Mason Tax Parcels geometry type changed",
            url=LAYER_URL,
            details={"geometryType": metadata.get("geometryType")},
        )
    capabilities = {
        item.strip()
        for item in str(metadata.get("capabilities") or "").split(",")
        if item.strip()
    }
    if "Query" not in capabilities:
        raise SourceSchemaError(
            "Mason Tax Parcels layer no longer declares query capability",
            url=LAYER_URL,
            details={"capabilities": sorted(capabilities)},
        )

    server_max = metadata.get("maxRecordCount")
    if (
        isinstance(server_max, bool)
        or not isinstance(server_max, int)
        or server_max <= 0
    ):
        raise SourceSchemaError(
            "Mason Tax Parcels metadata lacks maxRecordCount",
            url=LAYER_URL,
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping):
        raise SourceSchemaError(
            "Mason Tax Parcels metadata lacks advanced query capabilities",
            url=LAYER_URL,
        )
    expected_false = {
        "supportsPagination": advanced.get("supportsPagination"),
        "supportsOrderBy": advanced.get("supportsOrderBy"),
        "supportsStatistics": advanced.get("supportsStatistics"),
    }
    if any(value is not False for value in expected_false.values()):
        raise SourceSchemaError(
            "Mason Tax Parcels traversal support flags changed",
            url=LAYER_URL,
            details=expected_false,
        )
    if metadata.get("supportsAdvancedQueries") is not False:
        raise SourceSchemaError(
            "Mason Tax Parcels advanced-query support flag changed",
            url=LAYER_URL,
            details={
                "supportsAdvancedQueries": metadata.get("supportsAdvancedQueries")
            },
        )
    if metadata.get("supportsStatistics") is not False:
        raise SourceSchemaError(
            "Mason Tax Parcels statistics support flag changed",
            url=LAYER_URL,
            details={"supportsStatistics": metadata.get("supportsStatistics")},
        )

    spatial_reference = metadata.get("spatialReference")
    if not isinstance(spatial_reference, Mapping):
        extent = metadata.get("extent")
        spatial_reference = (
            extent.get("spatialReference") if isinstance(extent, Mapping) else None
        )
    if not isinstance(spatial_reference, Mapping):
        raise SourceSchemaError(
            "Mason Tax Parcels metadata lacks a spatial reference",
            url=LAYER_URL,
        )

    contract_value = {
        "fields": arcgis_declared_schema(fields),
        "object_id_field": OBJECT_ID_FIELD,
        "geometry_type": metadata.get("geometryType"),
        "spatial_reference": dict(spatial_reference),
        "max_record_count": server_max,
        "supports_pagination": advanced.get("supportsPagination"),
        "supports_order_by": advanced.get("supportsOrderBy"),
        "supports_statistics": advanced.get("supportsStatistics"),
        "supports_advanced_queries": metadata.get("supportsAdvancedQueries"),
    }
    return LayerContract(
        schema_fingerprint=sha256_fingerprint(contract_value),
        field_names=field_names,
        max_record_count=server_max,
        object_id_field=OBJECT_ID_FIELD,
        geometry_type=GEOMETRY_TYPE,
        spatial_reference=dict(spatial_reference),
        supports_pagination=False,
        supports_order_by=False,
        supports_statistics=False,
        supports_advanced_queries=False,
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _object_id(value: Any) -> int:
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise SourceSchemaError(
            "Mason FID must be a non-negative integer",
            url=QUERY_URL,
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "Mason FID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        ) from error
    if parsed < 0:
        raise SourceSchemaError(
            "Mason FID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": parsed},
        )
    return parsed


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "Mason feature lacks an attributes object",
            url=QUERY_URL,
        )
    return attributes


def _feature_object_id(feature: Mapping[str, Any]) -> int:
    return _object_id(_attributes(feature).get(OBJECT_ID_FIELD))


def _clean_text(value: Any) -> str | None:
    text = " ".join(str(value or "").replace("\x00", "").split()).strip()
    return text or None


def _sql_literal(value: str, description: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        raise MasonParcelSelectionError(
            "blank_selector",
            f"{description} must not be blank",
        )
    return cleaned.replace("'", "''")


def _match_expression(field: str, value: str, match: str) -> str:
    literal = _sql_literal(value, "search selector")
    if match == "exact":
        return f"{field}='{literal}'"
    if match == "prefix":
        return f"{field} LIKE '{literal}%'"
    if match == "contains":
        return f"{field} LIKE '%{literal}%'"
    raise MasonParcelSelectionError(
        "invalid_match_mode",
        f"unsupported match mode: {match}",
    )


def _search_where(
    value: str,
    *,
    field: str,
    match: str,
) -> str:
    try:
        fields = SEARCH_FIELDS[field]
    except KeyError as error:
        raise MasonParcelSelectionError(
            "invalid_search_field",
            f"unsupported Mason search field: {field}",
        ) from error
    return " OR ".join(
        f"({_match_expression(field_name, value, match)})" for field_name in fields
    )


def _query_spec(args: argparse.Namespace) -> QuerySpec:
    command = args.command
    where = "1=1"
    geometry_parameters: dict[str, Any] = {}
    return_geometry = bool(getattr(args, "geometry", False))

    if command == "search":
        where = _search_where(
            args.query,
            field=args.field,
            match=args.match,
        )
    elif command == "parcel":
        where = _search_where(args.query, field="parcel", match="exact")
    elif command == "owner":
        where = _search_where(
            args.query,
            field="owner",
            match=args.match,
        )
    elif command == "address":
        where = _search_where(
            args.query,
            field="address",
            match=args.match,
        )
    elif command == "objectid":
        where = f"{OBJECT_ID_FIELD}={_object_id(args.objectid)}"
    elif command == "count" and getattr(args, "query", None):
        where = _search_where(
            args.query,
            field=args.field,
            match=args.match,
        )
    elif command == "point":
        geometry_parameters = {
            "geometry": canonical_json(
                {
                    "x": args.longitude,
                    "y": args.latitude,
                    "spatialReference": {"wkid": 4326},
                }
            ),
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
        return_geometry = True
    elif command == "bbox":
        if args.west >= args.east or args.south >= args.north:
            raise MasonParcelSelectionError(
                "invalid_bbox",
                "bbox requires west < east and south < north",
            )
        geometry_parameters = {
            "geometry": canonical_json(
                {
                    "xmin": args.west,
                    "ymin": args.south,
                    "xmax": args.east,
                    "ymax": args.north,
                    "spatialReference": {"wkid": 4326},
                }
            ),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
        return_geometry = True
    return QuerySpec(
        where=where,
        geometry_parameters=geometry_parameters,
        return_geometry=return_geometry,
    )


def _criteria_fingerprint(
    *,
    operation: str,
    spec: QuerySpec,
) -> str:
    return sha256_fingerprint(
        {
            "cursor_version": CURSOR_VERSION,
            "source_id": SOURCE_ID,
            "operation": operation,
            "where": spec.where,
            "geometry_parameters": dict(spec.geometry_parameters),
            "return_geometry": spec.return_geometry,
            "traversal": "sorted_returnIdsOnly_FID_snapshot",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "schema": state.schema_fingerprint,
        "ids": state.ids_fingerprint,
        "offset": state.offset,
        "last": state.last_object_id,
        "total": state.total_count,
    }
    encoded = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(value: str | None) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise MasonParcelSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Mason Tax Parcels adapter",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MasonParcelSelectionError(
            "invalid_cursor",
            "cursor is not valid encoded JSON",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != CURSOR_VERSION:
        raise MasonParcelSelectionError(
            "invalid_cursor",
            "cursor version is not supported",
        )
    try:
        numeric_values = (
            payload["offset"],
            payload["last"],
            payload["total"],
        )
        if any(
            isinstance(item, bool)
            or (isinstance(item, float) and not item.is_integer())
            for item in numeric_values
        ):
            raise TypeError("non-integral cursor number")
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            schema_fingerprint=str(payload["schema"]),
            ids_fingerprint=str(payload["ids"]),
            offset=int(numeric_values[0]),
            last_object_id=int(numeric_values[1]),
            total_count=int(numeric_values[2]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise MasonParcelSelectionError(
            "invalid_cursor",
            "cursor lacks required continuation fields",
        ) from error
    digests = (
        state.criteria_fingerprint,
        state.schema_fingerprint,
        state.ids_fingerprint,
    )
    if (
        state.offset <= 0
        or state.last_object_id < 0
        or state.total_count < state.offset
        or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in digests)
    ):
        raise MasonParcelSelectionError(
            "invalid_cursor",
            "cursor continuation values are inconsistent",
        )
    return state


def _validate_cursor(
    state: CursorState | None,
    *,
    criteria_fingerprint: str,
    contract: LayerContract,
    object_ids: Sequence[int],
    ids_fingerprint: str,
) -> int:
    if state is None:
        return 0
    if state.criteria_fingerprint != criteria_fingerprint:
        raise MasonParcelSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Mason parcel criteria",
        )
    if state.schema_fingerprint != contract.schema_fingerprint:
        raise MasonParcelSelectionError(
            "cursor_schema_changed",
            "Mason parcel schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if state.ids_fingerprint != ids_fingerprint or state.total_count != len(object_ids):
        raise MasonParcelSelectionError(
            "cursor_snapshot_changed",
            "matching Mason feature occurrences changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            details={
                "cursor_total": state.total_count,
                "current_total": len(object_ids),
            },
        )
    if state.offset > len(object_ids):
        raise MasonParcelSelectionError(
            "cursor_out_of_range",
            "cursor offset exceeds the current matching feature count",
        )
    if object_ids[state.offset - 1] != state.last_object_id:
        raise MasonParcelSelectionError(
            "cursor_boundary_changed",
            "Mason feature ordering changed at the cursor boundary",
            status=ResultStatus.SOURCE_CHANGED,
        )
    return state.offset


def fetch_feature_batch(
    client: MasonCountyTaxParcelsClient,
    *,
    operation: str,
    spec: QuerySpec,
    limit: int | None,
    cursor: str | None,
) -> FeatureBatch:
    if limit is not None and limit <= 0:
        raise MasonParcelSelectionError(
            "invalid_limit",
            "limit must be a positive integer",
        )
    start_requests = client.request_count
    metadata = client.fetch_metadata()
    contract = metadata_contract(metadata)
    object_ids = client.fetch_object_ids(
        where=spec.where,
        parameters=spec.geometry_parameters,
    )
    ids_fingerprint = sha256_fingerprint(list(object_ids))
    criteria_fingerprint = _criteria_fingerprint(
        operation=operation,
        spec=spec,
    )
    state = _decode_cursor(cursor)
    offset = _validate_cursor(
        state,
        criteria_fingerprint=criteria_fingerprint,
        contract=contract,
        object_ids=object_ids,
        ids_fingerprint=ids_fingerprint,
    )
    stop = len(object_ids) if limit is None else min(len(object_ids), offset + limit)
    selected_ids = object_ids[offset:stop]

    features: list[Mapping[str, Any]] = []
    for chunk_start in range(0, len(selected_ids), contract.max_record_count):
        chunk = selected_ids[chunk_start : chunk_start + contract.max_record_count]
        features.extend(
            client.fetch_features(
                chunk,
                return_geometry=spec.return_geometry,
            )
        )
    observed_ids = tuple(_feature_object_id(feature) for feature in features)
    if observed_ids != selected_ids:
        raise PaginationError(
            "Mason client-side feature ordering diverged from its ID snapshot",
            url=QUERY_URL,
            details={
                "selected": list(selected_ids),
                "observed": list(observed_ids),
            },
        )

    next_cursor = None
    if stop < len(object_ids) and selected_ids:
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria_fingerprint,
                schema_fingerprint=contract.schema_fingerprint,
                ids_fingerprint=ids_fingerprint,
                offset=stop,
                last_object_id=selected_ids[-1],
                total_count=len(object_ids),
            )
        )
    return FeatureBatch(
        features=tuple(features),
        contract=contract,
        matching_object_ids=object_ids,
        ids_fingerprint=ids_fingerprint,
        next_cursor=next_cursor,
        requests_made=client.request_count - start_requests,
    )


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _parcel_identifiers(attributes: Mapping[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, field in (
        ("pin", "PIN"),
        ("terra_pin", "TERRA_PIN"),
        ("taxlot", "Taxlot"),
        ("map_number", "Map_number"),
        ("segment_number", "SEG_NUMBER"),
    ):
        value = _clean_text(attributes.get(field))
        if value:
            values[key] = value
    return values


def _parcel_join(
    identifiers: Mapping[str, str],
) -> tuple[str | None, dict[str, Any] | None]:
    for field in ("pin", "terra_pin", "taxlot"):
        value = identifiers.get(field)
        if value:
            return (
                value,
                {
                    "county_geoid": COUNTY_GEOID,
                    "field": field,
                    "value": value,
                    "identity_role": "candidate_parcel_join",
                    "uniqueness_in_layer": "not_assumed",
                },
            )
    return None, None


def _owner_observations(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    last_name = _clean_text(attributes.get("LastName"))
    first_name = _clean_text(attributes.get("FirstName"))
    if not last_name and not first_name:
        return []
    raw_name = (
        f"{last_name}, {first_name}"
        if last_name and first_name
        else last_name or first_name
    )
    return [
        {
            "raw_name": raw_name,
            "first_name": first_name,
            "last_name": last_name,
            "role": "assessment_snapshot_name",
            "confidence": "high",
            "assertion_scope": "county_assessor_gis_name_not_recorded_title",
        }
    ]


def _situs_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = _clean_text(attributes.get("Situs"))
    if not raw:
        return None
    return {
        "raw": raw,
        "source_fields": ["Situs"],
    }


def _mailing_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    lines = [
        value
        for field in ("Address1", "Address2")
        if (value := _clean_text(attributes.get(field)))
    ]
    if not lines:
        return None
    return {
        "raw": ", ".join(lines),
        "address_lines": lines,
        "city": _clean_text(attributes.get("City")),
        "state": _clean_text(attributes.get("State")),
        "postal_code": _clean_text(attributes.get("Zip")),
        "source_fields": ["Address1", "Address2", "City", "State", "Zip"],
    }


def normalize_feature(
    feature: Mapping[str, Any],
    *,
    contract: LayerContract,
    geometry_requested: bool,
) -> dict[str, Any]:
    """Normalize one source occurrence while keeping join identity separate."""

    attributes = dict(_attributes(feature))
    object_id = _feature_object_id(feature)
    identifiers = _parcel_identifiers(attributes)
    native_parcel_id, parcel_join_key = _parcel_join(identifiers)
    feature_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "parcel_feature",
        f"FID:{object_id}",
    )
    canonical_ref = (
        canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            native_parcel_id,
        )
        if native_parcel_id
        else feature_ref
    )

    record: dict[str, Any] = {
        "record_kind": "parcel_assessment_geometry_snapshot",
        "source_id": SOURCE_ID,
        "source_url": LAYER_URL,
        "canonical_ref": canonical_ref,
        "feature_ref": feature_ref,
        "source_occurrence_id": f"FID:{object_id}",
        "feature_occurrence": {
            "object_id_field": OBJECT_ID_FIELD,
            "object_id": object_id,
            "feature_ref": feature_ref,
        },
        "native_parcel_id": native_parcel_id,
        "parcel_join_key": parcel_join_key,
        "parcel_identifiers": identifiers,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "owners": _owner_observations(attributes),
        "situs_address": _situs_address(attributes),
        "mailing_address": _mailing_address(attributes),
        "assessment": {
            "assessment_label": _clean_text(attributes.get("Assessment")),
            "assessment_class": _clean_text(attributes.get("Assessment")),
            "exemption_flag": _clean_text(attributes.get("IsExempt")),
            "parcel_value": _number(attributes.get("TotalMarke")),
            "market_value": _number(attributes.get("TotalMarke")),
            "assessed_value": _number(attributes.get("TotalAsses")),
            "land_value": _number(attributes.get("MarketLand")),
            "improvement_value": _number(attributes.get("MarketBuil")),
            "market_land_value": _number(attributes.get("MarketLand")),
            "market_building_value": _number(attributes.get("MarketBuil")),
            "assessed_land_value": _number(attributes.get("AssessedLa")),
            "assessed_building_value": _number(attributes.get("AssessedBu")),
            "published_resulting_tax": _number(attributes.get("ResultingT")),
            "published_resulting_tax_scope": (
                "assessment_layer_field_not_treasury_balance_or_payment_history"
            ),
            "assessed_1": _number(attributes.get("Assessed_1")),
        },
        "land": {
            "total_acres": _number(attributes.get("TotalAcres")),
            "subdivision_name": _clean_text(attributes.get("SubName")),
            "assembled_legal": _clean_text(attributes.get("AssembledL")),
            "district": _clean_text(attributes.get("District")),
            "department": _clean_text(attributes.get("Department")),
            "secondary_label": _clean_text(attributes.get("SecondaryL")),
        },
        "map_reference": {
            "map_number": _clean_text(attributes.get("Map_number")),
            "township": attributes.get("Township"),
            "township_direction": _clean_text(attributes.get("Towndir")),
            "range": attributes.get("Range"),
            "range_direction": _clean_text(attributes.get("Rangedir")),
            "section": attributes.get("Section"),
            "quarter": _clean_text(attributes.get("QTR")),
            "quarter_quarter": _clean_text(attributes.get("QTRQTR")),
            "map_accuracy": _clean_text(attributes.get("MapAccurac")),
        },
        "source_schema": {
            "schema_fingerprint": contract.schema_fingerprint,
            "object_id_field": contract.object_id_field,
            "geometry_type": contract.geometry_type,
        },
        "source_semantics": {
            "record_grain": "current_assessor_gis_feature",
            "recorder_instruments": False,
            "treasury_balances_or_payment_history": False,
            "recorded_title_or_beneficial_ownership": False,
            "surveyed_legal_boundary": False,
        },
        "raw_attributes": attributes,
    }
    geometry = feature.get("geometry")
    if geometry_requested and isinstance(geometry, Mapping):
        record["geometry"] = dict(geometry)
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = OUTPUT_CRS
        record["geometry_disclaimer"] = (
            "County GIS parcel feature transformed to EPSG:4326; not a "
            "surveyed legal boundary."
        )
    return record


def _access_contract(args: argparse.Namespace) -> Mapping[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> MasonCountyTaxParcelsClient:
    limits = access_contract.get("limits") or {}
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return MasonCountyTaxParcelsClient(
        timeout=args.timeout,
        minimum_interval=minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "catalog_db",
        "catalog_config",
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "retry_attempts",
    }
    return {
        key: value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _metadata_record(
    metadata: Mapping[str, Any],
    contract: LayerContract,
) -> dict[str, Any]:
    return {
        "record_kind": "source_metadata",
        "source_id": SOURCE_ID,
        "source_url": LAYER_URL,
        "layer_name": metadata.get("name"),
        "layer_type": metadata.get("type"),
        "capabilities": metadata.get("capabilities"),
        "display_field": metadata.get("displayField"),
        **contract.to_dict(),
        "traversal": {
            "identity": OBJECT_ID_FIELD,
            "id_snapshot": "returnIdsOnly",
            "stable_order": "client_sorted_FID_ascending",
            "feature_fetch": "objectIds_batches",
            "offset_pagination_used": False,
            "server_order_by_used": False,
        },
    }


def _probe_record(
    batch: FeatureBatch,
) -> dict[str, Any]:
    sample = None
    if batch.features:
        attributes = dict(_attributes(batch.features[0]))
        sample = {
            "object_id": _feature_object_id(batch.features[0]),
            "parcel_identifiers": _parcel_identifiers(attributes),
            "assessment": attributes.get("Assessment"),
            "total_market": attributes.get("TotalMarke"),
            "total_assessed": attributes.get("TotalAsses"),
            "situs": attributes.get("Situs"),
        }
    return {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "source_url": LAYER_URL,
        "schema_fingerprint": batch.contract.schema_fingerprint,
        "id_snapshot_fingerprint": batch.ids_fingerprint,
        "feature_count": len(batch.matching_object_ids),
        "smallest_object_id": (
            batch.matching_object_ids[0] if batch.matching_object_ids else None
        ),
        "sample": sample,
        "requests_made": batch.requests_made,
        "contract": batch.contract.to_dict(),
        "traversal": {
            "identity": OBJECT_ID_FIELD,
            "id_snapshot": "returnIdsOnly",
            "stable_order": "client_sorted_FID_ascending",
            "offset_pagination_used": False,
            "server_order_by_used": False,
        },
    }


def _selection_failure(
    query: PublicRecordsQuery,
    error: MasonParcelSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    client: MasonCountyTaxParcelsClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one catalog-aware Mason County query."""

    query = build_query(args)
    try:
        decision = (
            access_contract if access_contract is not None else _access_contract(args)
        )
        active_client = client or _client(args, decision)
        if args.command == "metadata":
            metadata = active_client.fetch_metadata()
            contract = metadata_contract(metadata)
            result = PublicRecordsResult.success(
                query,
                [_metadata_record(metadata, contract)],
                warnings=SOURCE_WARNINGS,
            )
        else:
            spec = _query_spec(args)
            if args.command == "count":
                metadata = active_client.fetch_metadata()
                contract = metadata_contract(metadata)
                object_ids = active_client.fetch_object_ids(
                    where=spec.where,
                    parameters=spec.geometry_parameters,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "record_kind": "source_count",
                            "source_id": SOURCE_ID,
                            "source_url": QUERY_URL,
                            "where": spec.where,
                            "geometry_filter": dict(spec.geometry_parameters),
                            "count": len(object_ids),
                            "id_snapshot_fingerprint": sha256_fingerprint(
                                list(object_ids)
                            ),
                            "schema_fingerprint": (contract.schema_fingerprint),
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                batch = fetch_feature_batch(
                    active_client,
                    operation="probe",
                    spec=QuerySpec(
                        where="1=1",
                        geometry_parameters={},
                        return_geometry=False,
                    ),
                    limit=1,
                    cursor=None,
                )
                result = PublicRecordsResult.success(
                    query,
                    [_probe_record(batch)],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                batch = fetch_feature_batch(
                    active_client,
                    operation=args.command,
                    spec=spec,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                records = [
                    normalize_feature(
                        feature,
                        contract=batch.contract,
                        geometry_requested=spec.return_geometry,
                    )
                    for feature in batch.features
                ]
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=batch.next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
    except AcquisitionUnavailableError as error:
        decision = error.decision
        result = PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code") or "machine_acquisition_denied"
                    ),
                    message=str(error),
                    category="access_policy",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    except MasonParcelSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="mason_parcel_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        try:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
        except Exception as error:  # pragma: no cover - logging is external
            print(f"WARNING: search logging failed: {error}", file=sys.stderr)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Mason County Tax Parcels {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Mason County Tax Parcels {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("native_parcel_id")
            or record.get("feature_ref")
            or record.get("record_kind")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    records: bool = False,
) -> None:
    if records:
        parser.add_argument(
            "--limit",
            type=_positive_int,
            help=(
                "Optional caller-selected result bound; omitted queries "
                "exhaust the matching object-ID snapshot"
            ),
        )
        parser.add_argument(
            "--cursor",
            help="Continuation cursor from a previous bounded query",
        )
        parser.add_argument(
            "--geometry",
            action="store_true",
            help="Return parcel geometry transformed to EPSG:4326",
        )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=0.0,
        help="Optional caller-selected minimum seconds between requests",
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    add_output_args(parser)


def _add_match_argument(
    parser: argparse.ArgumentParser,
    *,
    default: str = "contains",
) -> None:
    parser.add_argument(
        "--match",
        choices=("contains", "prefix", "exact"),
        default=default,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Mason County's official current Tax Parcels GIS and "
            "assessment fields"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Inspect layer schema and traversal support flags",
    )
    _add_runtime_arguments(metadata_parser)

    count_parser = subparsers.add_parser(
        "count",
        help="Count all features or records matching one field selector",
    )
    count_parser.add_argument("query", nargs="?")
    count_parser.add_argument(
        "--field",
        choices=tuple(SEARCH_FIELDS),
        default="any",
    )
    _add_match_argument(count_parser)
    _add_runtime_arguments(count_parser)

    list_parser = subparsers.add_parser(
        "list",
        help="Traverse all feature occurrences in stable FID order",
    )
    _add_runtime_arguments(list_parser, records=True)

    search_parser = subparsers.add_parser(
        "search",
        help="Search published parcel, owner, address, or assessment fields",
    )
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--field",
        choices=tuple(SEARCH_FIELDS),
        default="any",
    )
    _add_match_argument(search_parser)
    _add_runtime_arguments(search_parser, records=True)

    parcel_parser = subparsers.add_parser(
        "parcel",
        help="Match PIN, TERRA_PIN, or Taxlot exactly",
    )
    parcel_parser.add_argument("query")
    _add_runtime_arguments(parcel_parser, records=True)

    owner_parser = subparsers.add_parser(
        "owner",
        help="Search LastName and FirstName fields",
    )
    owner_parser.add_argument("query")
    _add_match_argument(owner_parser)
    _add_runtime_arguments(owner_parser, records=True)

    address_parser = subparsers.add_parser(
        "address",
        help="Search situs and published mailing-address fields",
    )
    address_parser.add_argument("query")
    _add_match_argument(address_parser)
    _add_runtime_arguments(address_parser, records=True)

    objectid_parser = subparsers.add_parser(
        "objectid",
        help="Fetch one exact source feature occurrence by FID",
    )
    objectid_parser.add_argument("objectid", type=_nonnegative_int)
    _add_runtime_arguments(objectid_parser, records=True)

    point_parser = subparsers.add_parser(
        "point",
        help="Find polygon features intersecting a WGS84 point",
    )
    point_parser.add_argument("longitude", type=float)
    point_parser.add_argument("latitude", type=float)
    _add_runtime_arguments(point_parser, records=True)

    bbox_parser = subparsers.add_parser(
        "bbox",
        help="Find polygon features intersecting a WGS84 bounding box",
    )
    bbox_parser.add_argument("west", type=float)
    bbox_parser.add_argument("south", type=float)
    bbox_parser.add_argument("east", type=float)
    bbox_parser.add_argument("north", type=float)
    _add_runtime_arguments(bbox_parser, records=True)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Verify schema, ID traversal, and one current feature occurrence",
    )
    _add_runtime_arguments(probe_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
