#!/usr/bin/env python3
"""Query Palm Beach County's official parcel-detail GIS layer.

The Property Appraiser publishes a county parcel/assessment representation
through an anonymous ArcGIS FeatureServer. ``OBJECTID`` identifies a feature
occurrence. ``PARCEL_NUMBER`` is retained as a candidate exact tax-account
join, while ``PARID`` remains a separate published geometry/group identifier.
Neither identifier is assumed unique in the layer.

Bounded scans use ordered ArcGIS pagination within a maximum-OBJECTID snapshot
boundary. Omitting ``--limit`` exhausts that bounded population; a caller limit
returns a query/schema/snapshot-bound continuation cursor.

Examples:
    uv run python tools/query_palm_beach_property_appraiser.py parcel 00424400000000000
    uv run python tools/query_palm_beach_property_appraiser.py owner SMITH
    uv run python tools/query_palm_beach_property_appraiser.py address "100 MAIN"
    uv run python tools/query_palm_beach_property_appraiser.py sale 1234/567
    uv run python tools/query_palm_beach_property_appraiser.py point -80.10 26.70
    uv run python tools/query_palm_beach_property_appraiser.py probe
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
        ArcGISRESTClient,
        PaginationError,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
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
        ArcGISRESTClient,
        PaginationError,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-fl-palm-beach-property-appraiser"
COUNTY_GEOID = "12099"
STATE_FIPS = "12"
STATE_CODE = "FL"
COUNTY_NAME = "Palm Beach"

LAYER_URL = (
    "https://gis.pbcgov.org/arcgis/rest/services/"
    "Parcels/PARCEL_INFO/FeatureServer/4"
)
QUERY_URL = f"{LAYER_URL}/query"
QSALES_LAYER_URL = (
    "https://gis.pbcgov.org/arcgis/rest/services/"
    "Parcels/QSALES/FeatureServer/0"
)
QSALES_QUERY_URL = f"{QSALES_LAYER_URL}/query"
PROPERTY_APPRAISER_DATA_URL = "https://pbcpao.gov/departments/gis.htm"
CLERK_SOURCE_ID = "us-fl-palm-beach-official-records"
CLERK_SEARCH_URL = "https://erec.mypalmbeachclerk.com/"
FL_DOR_SOURCE_ID = "us-fl-dor-property-roll"

OBJECT_ID_FIELD = "OBJECTID"
LAYER_NAME = "PARCEL_DETAILS"
QSALES_LAYER_NAME = "PAO.PARCEL_QSALES"
GEOMETRY_TYPE = "esriGeometryPolygon"
OUTPUT_CRS = "EPSG:4326"
CURSOR_PREFIX = "pbc-parcel-details:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRY_ATTEMPTS = 3

REQUIRED_FIELDS = (
    "OBJECTID",
    "PARID",
    "PARCEL_NUMBER",
    "OWNER_NAME1",
    "OWNER_NAME2",
    "SITE_ADDR_STR",
    "PADDR1",
    "PADDR2",
    "PADDR3",
    "SALEKEY",
    "SALE_DATE",
    "BOOK",
    "PAGE",
    "PRICE",
    "INSTRUMENT",
    "TOTAL_MARKET",
    "MKT_NOT_CAPPED",
    "MKT_CAPPED",
    "CAP_ADJ_VAL",
    "AG_USE_VAL",
    "ASSESSED_VAL",
    "EXEMPTION",
    "TOTAL_VALUE",
    "TOTAL_TAXABLE",
    "HMSTD_FLG",
    "LAND_MARKET",
    "IMPRV_MRKT",
    "PROPERTY_USE",
    "CONFID_FLG",
    "QUAL_CODE",
    "Q_SALE_DATE",
    "LEGAL1",
    "LEGAL2",
    "LEGAL3",
)

SEARCH_FIELDS = {
    "parcel": ("PARCEL_NUMBER",),
    "parid": ("PARID",),
    "owner": ("OWNER_NAME1", "OWNER_NAME2"),
    "address": (
        "SITE_ADDR_STR",
        "PADDR1",
        "PADDR2",
        "PADDR3",
        "STREET_NAME",
    ),
    "sale": ("BOOK", "PAGE"),
    "legal": ("LEGAL1", "LEGAL2", "LEGAL3"),
    "property-use": ("PROPERTY_USE",),
    "subdivision": ("SUBDIV_NAME",),
}
SEARCH_FIELDS["any"] = tuple(
    dict.fromkeys(
        field_name
        for group in SEARCH_FIELDS.values()
        for field_name in group
    )
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Palm Beach County Property Appraiser Parcel Details",
    source_role="county_parcel_assessment_geometry",
    base_url=LAYER_URL,
    dataset_id="Parcels/PARCEL_INFO/FeatureServer/4",
    metadata={
        "authority": "Palm Beach County Property Appraiser",
        "operator": "Palm Beach County GIS",
        "county_geoid": COUNTY_GEOID,
        "record_grain": "published_parcel_detail_feature_occurrence",
        "primary_identity": OBJECT_ID_FIELD,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Palm Beach County, Florida",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    metadata={"state_fips": STATE_FIPS, "county_fips_3": "099"},
)
SOURCE_WARNINGS = (
    "OBJECTID identifies a published feature occurrence. PARCEL_NUMBER is a "
    "candidate county tax-account join and PARID is a separate published "
    "geometry/group identifier; neither is assumed unique.",
    "Owner fields describe the assessment roll. They are not assertions of "
    "current recorded title or beneficial ownership.",
    "The published sale fields are assessment-layer last-sale labels. Book "
    "and page can pivot to the Clerk source, but this layer is not an "
    "instrument copy.",
    "CONFID_FLG and blank owner/address fields are preserved as publisher "
    "redaction state without guessing the flag's unpublished semantics.",
)


@dataclass(frozen=True)
class LayerContract:
    schema_fingerprint: str
    field_names: tuple[str, ...]
    max_record_count: int
    object_id_field: str
    geometry_type: str
    spatial_reference: Mapping[str, Any]
    layer_name: str
    layer_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_fingerprint": self.schema_fingerprint,
            "field_names": list(self.field_names),
            "max_record_count": self.max_record_count,
            "object_id_field": self.object_id_field,
            "geometry_type": self.geometry_type,
            "spatial_reference": dict(self.spatial_reference),
            "layer_name": self.layer_name,
            "layer_url": self.layer_url,
            "supports_pagination": True,
            "supports_order_by": True,
            "supports_statistics": True,
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
    boundary_object_id: int
    total_count: int
    offset: int
    last_object_id: int


@dataclass(frozen=True)
class FeatureBatch:
    features: tuple[Mapping[str, Any], ...]
    contract: LayerContract
    boundary_object_id: int | None
    total_count: int
    next_cursor: str | None
    requests_made: int


class PalmBeachPropertyError(ValueError):
    """Query/continuation error with result-envelope semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query_selection",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


class PalmBeachPropertyClient(ArcGISRESTClient):
    """ArcGIS client with explicit metadata, count, and bounded page methods."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = 0.0,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            LAYER_URL,
            page_size=1,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
            **kwargs,
        )

    def fetch_metadata(self, layer_url: str = LAYER_URL) -> Mapping[str, Any]:
        payload = self._request_json(layer_url, params={"f": "json"})
        return _arcgis_object(payload, "layer metadata", layer_url)

    def fetch_count(
        self,
        where: str,
        *,
        parameters: Mapping[str, Any] | None = None,
        query_url: str = QUERY_URL,
    ) -> int:
        payload = self._request_json(
            query_url,
            params={
                **dict(parameters or {}),
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        value = _arcgis_object(payload, "count query", query_url)
        count = value.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Palm Beach ArcGIS count is not a non-negative integer",
                url=query_url,
                details={"count": count},
            )
        return count

    def fetch_boundary(
        self,
        where: str,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> int | None:
        payload = self._request_json(
            QUERY_URL,
            params={
                **dict(parameters or {}),
                "where": where,
                "outFields": OBJECT_ID_FIELD,
                "returnGeometry": "false",
                "orderByFields": f"{OBJECT_ID_FIELD} DESC",
                "resultRecordCount": 1,
                "f": "json",
            },
        )
        features = _feature_tuple(payload, QUERY_URL, "boundary query")
        if not features:
            return None
        return _feature_object_id(features[0])

    def fetch_page(
        self,
        *,
        where: str,
        offset: int,
        record_count: int,
        return_geometry: bool,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            QUERY_URL,
            params={
                **dict(parameters or {}),
                "where": where,
                "outFields": "*",
                "returnGeometry": str(return_geometry).lower(),
                "orderByFields": f"{OBJECT_ID_FIELD} ASC",
                "resultOffset": offset,
                "resultRecordCount": record_count,
                **({"outSR": 4326} if return_geometry else {}),
                "f": "json",
            },
        )
        value = _arcgis_object(payload, "feature query", QUERY_URL)
        features = _feature_tuple(value, QUERY_URL, "feature query")
        if value.get("exceededTransferLimit") is True and not features:
            raise PaginationError(
                "Palm Beach ArcGIS reported more rows without returning features",
                url=QUERY_URL,
                details={"offset": offset},
            )
        return features

    def fetch_distinct_count(
        self,
        field_name: str,
        *,
        query_url: str = QUERY_URL,
    ) -> int | None:
        payload = self._request_json(
            query_url,
            params={
                "where": "1=1",
                "outStatistics": canonical_json(
                    [
                        {
                            "statisticType": "countDistinct",
                            "onStatisticField": field_name,
                            "outStatisticFieldName": "distinct_count",
                        }
                    ]
                ),
                "returnGeometry": "false",
                "f": "json",
            },
        )
        features = _feature_tuple(payload, query_url, "distinct-count query")
        if len(features) != 1:
            raise SourceSchemaError(
                "Palm Beach distinct-count query did not return one row",
                url=query_url,
                details={"row_count": len(features)},
            )
        attributes = features[0].get("attributes")
        if not isinstance(attributes, Mapping):
            raise SourceSchemaError(
                "Palm Beach distinct-count row lacks attributes",
                url=query_url,
            )
        count = attributes.get("distinct_count")
        if count is None:
            return None
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Palm Beach distinct count is not a non-negative integer",
                url=query_url,
                details={"field": field_name, "count": count},
            )
        return count


def _arcgis_object(
    payload: Any,
    description: str,
    url: str,
) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            f"Palm Beach {description} response must be an object",
            url=url,
            details={"response_type": type(payload).__name__},
        )
    if "error" in payload:
        raise SourceResponseError(
            f"Palm Beach {description} returned an ArcGIS error",
            url=url,
            details={"response": payload.get("error")},
        )
    return payload


def _feature_tuple(
    payload: Any,
    url: str,
    description: str,
) -> tuple[Mapping[str, Any], ...]:
    value = _arcgis_object(payload, description, url)
    features = value.get("features")
    if not isinstance(features, list) or any(
        not isinstance(feature, Mapping) for feature in features
    ):
        raise SourceSchemaError(
            f"Palm Beach {description} lacks a valid features array",
            url=url,
        )
    return tuple(features)


def metadata_contract(
    metadata: Mapping[str, Any],
    *,
    layer_url: str = LAYER_URL,
    expected_name: str = LAYER_NAME,
) -> LayerContract:
    """Validate the layer identity and its ordered traversal capabilities."""

    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Palm Beach layer metadata lacks valid field declarations",
            url=layer_url,
        )
    field_names = tuple(str(field.get("name") or "") for field in fields)
    missing = sorted(set(REQUIRED_FIELDS) - set(field_names))
    if missing:
        raise SourceSchemaError(
            "Palm Beach parcel layer is missing required fields",
            url=layer_url,
            details={"missing_fields": missing},
        )
    oid_fields = [
        field for field in fields if field.get("type") == "esriFieldTypeOID"
    ]
    if (
        len(oid_fields) != 1
        or oid_fields[0].get("name") != OBJECT_ID_FIELD
        or metadata.get("objectIdField") not in (None, OBJECT_ID_FIELD)
    ):
        raise SourceSchemaError(
            "Palm Beach feature identity contract changed",
            url=layer_url,
            details={
                "oid_fields": [field.get("name") for field in oid_fields],
                "objectIdField": metadata.get("objectIdField"),
            },
        )
    identity = {
        "name": metadata.get("name"),
        "type": metadata.get("type"),
        "geometryType": metadata.get("geometryType"),
    }
    expected_identity = {
        "name": expected_name,
        "type": "Feature Layer",
        "geometryType": GEOMETRY_TYPE,
    }
    if identity != expected_identity:
        raise SourceSchemaError(
            "Palm Beach parcel-layer identity changed",
            url=layer_url,
            details={"expected": expected_identity, "observed": identity},
        )
    capabilities = {
        value.strip()
        for value in str(metadata.get("capabilities") or "").split(",")
        if value.strip()
    }
    if "Query" not in capabilities:
        raise SourceSchemaError(
            "Palm Beach parcel layer no longer declares query capability",
            url=layer_url,
        )
    advanced = metadata.get("advancedQueryCapabilities")
    required_capabilities = {
        "supportsPagination": True,
        "supportsOrderBy": True,
        "supportsStatistics": True,
    }
    if not isinstance(advanced, Mapping) or any(
        advanced.get(key) is not expected
        for key, expected in required_capabilities.items()
    ):
        raise SourceSchemaError(
            "Palm Beach ordered traversal capabilities changed",
            url=layer_url,
            details={
                key: advanced.get(key) if isinstance(advanced, Mapping) else None
                for key in required_capabilities
            },
        )
    max_record_count = metadata.get("maxRecordCount")
    if (
        isinstance(max_record_count, bool)
        or not isinstance(max_record_count, int)
        or max_record_count <= 0
    ):
        raise SourceSchemaError(
            "Palm Beach layer lacks a usable maxRecordCount",
            url=layer_url,
            details={"maxRecordCount": max_record_count},
        )
    spatial_reference = metadata.get("spatialReference")
    if not isinstance(spatial_reference, Mapping):
        extent = metadata.get("extent")
        spatial_reference = (
            extent.get("spatialReference") if isinstance(extent, Mapping) else None
        )
    if not isinstance(spatial_reference, Mapping):
        raise SourceSchemaError(
            "Palm Beach layer lacks a spatial reference",
            url=layer_url,
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "layer_url": layer_url,
            "identity": identity,
            "fields": arcgis_declared_schema(fields),
            "object_id_field": OBJECT_ID_FIELD,
            "spatial_reference": dict(spatial_reference),
            "traversal": required_capabilities,
        }
    )
    return LayerContract(
        schema_fingerprint=schema_fingerprint,
        field_names=field_names,
        max_record_count=max_record_count,
        object_id_field=OBJECT_ID_FIELD,
        geometry_type=GEOMETRY_TYPE,
        spatial_reference=dict(spatial_reference),
        layer_name=expected_name,
        layer_url=layer_url,
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _object_id(value: Any) -> int:
    if isinstance(value, bool) or (
        isinstance(value, float) and not value.is_integer()
    ):
        raise SourceSchemaError(
            "Palm Beach OBJECTID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "Palm Beach OBJECTID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        ) from error
    if parsed < 0:
        raise SourceSchemaError(
            "Palm Beach OBJECTID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        )
    return parsed


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "Palm Beach feature lacks attributes",
            url=QUERY_URL,
        )
    return attributes


def _feature_object_id(feature: Mapping[str, Any]) -> int:
    return _object_id(_attributes(feature).get(OBJECT_ID_FIELD))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_literal(value: Any, description: str) -> str:
    text = _clean_text(value)
    if not text:
        raise PalmBeachPropertyError(
            "blank_selector",
            f"{description} must not be blank",
        )
    return text.replace("'", "''")


def _match_expression(field_name: str, value: str, match: str) -> str:
    literal = _sql_literal(value, "search selector")
    if match == "exact":
        return f"{field_name}='{literal}'"
    if match == "prefix":
        return f"{field_name} LIKE '{literal}%'"
    if match == "contains":
        return f"{field_name} LIKE '%{literal}%'"
    raise PalmBeachPropertyError(
        "invalid_match_mode",
        f"unsupported match mode: {match}",
    )


def _normalize_parcel_selector(value: str) -> str:
    """Normalize a recognized 17-digit PCN without changing other selectors."""

    cleaned = _clean_text(value)
    if not cleaned or not re.fullmatch(r"[0-9][0-9\s./-]*[0-9]", cleaned):
        return value
    digits = re.sub(r"\D", "", cleaned)
    return digits if len(digits) == 17 else value


def _search_where(value: str, *, field: str, match: str) -> str:
    try:
        fields = SEARCH_FIELDS[field]
    except KeyError as error:
        raise PalmBeachPropertyError(
            "invalid_search_field",
            f"unsupported Palm Beach search field: {field}",
        ) from error
    selector = (
        _normalize_parcel_selector(value)
        if field == "parcel" and match == "exact"
        else value
    )
    expressions = [
        _match_expression(field_name, selector, match)
        for field_name in fields
    ]
    if len(expressions) == 1:
        return expressions[0]
    return " OR ".join(f"({expression})" for expression in expressions)


def _sale_where(value: str, field: str) -> str:
    cleaned = _sql_literal(value, "sale selector")
    if field == "any" and re.fullmatch(r"\d+\s*/\s*\d+", cleaned):
        field = "book-page"
    if field == "sale-key":
        if not cleaned.isdigit():
            raise PalmBeachPropertyError(
                "invalid_sale_key",
                "sale key must contain digits only",
            )
        return f"SALEKEY={int(cleaned)}"
    if field == "book-page":
        parts = [
            item.strip()
            for item in re.split(r"[/,:-]", cleaned)
            if item.strip()
        ]
        if len(parts) != 2:
            raise PalmBeachPropertyError(
                "invalid_book_page",
                "book-page search requires BOOK/PAGE",
            )
        book = _sql_literal(parts[0], "book")
        page = _sql_literal(parts[1], "page")
        return f"BOOK='{book}' AND PAGE='{page}'"
    return _search_where(cleaned, field="sale", match="exact")


def _query_spec(args: argparse.Namespace) -> QuerySpec:
    command = args.command
    where = "1=1"
    geometry_parameters: dict[str, Any] = {}
    return_geometry = bool(getattr(args, "geometry", False))
    if command == "search":
        where = _search_where(args.query, field=args.field, match=args.match)
    elif command == "parcel":
        where = _search_where(args.query, field="parcel", match="exact")
    elif command == "parid":
        where = _search_where(args.query, field="parid", match="exact")
    elif command == "owner":
        where = _search_where(args.query, field="owner", match=args.match)
    elif command == "address":
        where = _search_where(args.query, field="address", match=args.match)
    elif command == "sale":
        where = _sale_where(args.query, args.field)
    elif command == "objectid":
        where = f"{OBJECT_ID_FIELD}={_object_id(args.objectid)}"
    elif command == "count" and getattr(args, "query", None):
        where = _search_where(args.query, field=args.field, match=args.match)
    elif command == "point":
        if not (-180 <= args.longitude <= 180):
            raise PalmBeachPropertyError(
                "invalid_longitude",
                "longitude must be between -180 and 180",
            )
        if not (-90 <= args.latitude <= 90):
            raise PalmBeachPropertyError(
                "invalid_latitude",
                "latitude must be between -90 and 90",
            )
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
            raise PalmBeachPropertyError(
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


def _bounded_where(where: str, boundary_object_id: int) -> str:
    return f"({where}) AND {OBJECT_ID_FIELD}<={boundary_object_id}"


def _criteria_fingerprint(operation: str, spec: QuerySpec) -> str:
    return sha256_fingerprint(
        {
            "cursor_version": CURSOR_VERSION,
            "source_id": SOURCE_ID,
            "operation": operation,
            "where": spec.where,
            "geometry_parameters": dict(spec.geometry_parameters),
            "return_geometry": spec.return_geometry,
            "traversal": "OBJECTID_ASC_offset_with_max_OBJECTID_boundary",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "schema": state.schema_fingerprint,
        "boundary": state.boundary_object_id,
        "total": state.total_count,
        "offset": state.offset,
        "last": state.last_object_id,
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
        raise PalmBeachPropertyError(
            "invalid_cursor",
            "cursor does not belong to the Palm Beach parcel adapter",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PalmBeachPropertyError(
            "invalid_cursor",
            "cursor is not valid encoded JSON",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != CURSOR_VERSION:
        raise PalmBeachPropertyError(
            "invalid_cursor",
            "cursor version is not supported",
        )
    try:
        numbers = (
            payload["boundary"],
            payload["total"],
            payload["offset"],
            payload["last"],
        )
        if any(
            isinstance(item, bool)
            or (isinstance(item, float) and not item.is_integer())
            for item in numbers
        ):
            raise TypeError("non-integral cursor number")
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            schema_fingerprint=str(payload["schema"]),
            boundary_object_id=int(numbers[0]),
            total_count=int(numbers[1]),
            offset=int(numbers[2]),
            last_object_id=int(numbers[3]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PalmBeachPropertyError(
            "invalid_cursor",
            "cursor lacks required continuation fields",
        ) from error
    if (
        state.boundary_object_id < 0
        or state.total_count <= 0
        or state.offset <= 0
        or state.offset >= state.total_count
        or state.last_object_id < 0
        or state.last_object_id > state.boundary_object_id
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise PalmBeachPropertyError(
            "invalid_cursor",
            "cursor continuation values are inconsistent",
        )
    return state


def _validate_cursor(
    client: PalmBeachPropertyClient,
    state: CursorState,
    *,
    criteria_fingerprint: str,
    contract: LayerContract,
    spec: QuerySpec,
) -> None:
    if state.criteria_fingerprint != criteria_fingerprint:
        raise PalmBeachPropertyError(
            "cursor_query_mismatch",
            "cursor belongs to different Palm Beach parcel criteria",
        )
    if state.schema_fingerprint != contract.schema_fingerprint:
        raise PalmBeachPropertyError(
            "cursor_schema_changed",
            "Palm Beach parcel schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
        )
    bounded = _bounded_where(spec.where, state.boundary_object_id)
    count = client.fetch_count(
        bounded,
        parameters=spec.geometry_parameters,
    )
    if count != state.total_count:
        raise PalmBeachPropertyError(
            "cursor_snapshot_changed",
            "bounded Palm Beach feature population changed after cursor issue",
            status=ResultStatus.SOURCE_CHANGED,
            details={"cursor_total": state.total_count, "current_total": count},
        )
    prefix_count = client.fetch_count(
        f"({bounded}) AND {OBJECT_ID_FIELD}<={state.last_object_id}",
        parameters=spec.geometry_parameters,
    )
    if prefix_count != state.offset:
        raise PalmBeachPropertyError(
            "cursor_boundary_changed",
            "Palm Beach feature ordering changed at the cursor boundary",
            status=ResultStatus.SOURCE_CHANGED,
            details={"cursor_offset": state.offset, "prefix_count": prefix_count},
        )


def fetch_feature_batch(
    client: PalmBeachPropertyClient,
    *,
    operation: str,
    spec: QuerySpec,
    limit: int | None,
    cursor: str | None,
) -> FeatureBatch:
    if limit is not None and limit <= 0:
        raise PalmBeachPropertyError(
            "invalid_limit",
            "limit must be a positive integer",
        )
    start_requests = client.request_count
    metadata = client.fetch_metadata()
    contract = metadata_contract(metadata)
    criteria_fingerprint = _criteria_fingerprint(operation, spec)
    state = _decode_cursor(cursor)
    if state is None:
        boundary = client.fetch_boundary(
            spec.where,
            parameters=spec.geometry_parameters,
        )
        if boundary is None:
            return FeatureBatch(
                features=(),
                contract=contract,
                boundary_object_id=None,
                total_count=0,
                next_cursor=None,
                requests_made=client.request_count - start_requests,
            )
        bounded_where = _bounded_where(spec.where, boundary)
        total_count = client.fetch_count(
            bounded_where,
            parameters=spec.geometry_parameters,
        )
        offset = 0
    else:
        _validate_cursor(
            client,
            state,
            criteria_fingerprint=criteria_fingerprint,
            contract=contract,
            spec=spec,
        )
        boundary = state.boundary_object_id
        bounded_where = _bounded_where(spec.where, boundary)
        total_count = state.total_count
        offset = state.offset

    remaining = total_count - offset
    requested = remaining if limit is None else min(limit, remaining)
    features: list[Mapping[str, Any]] = []
    while len(features) < requested:
        page_count = min(
            contract.max_record_count,
            requested - len(features),
        )
        page = client.fetch_page(
            where=bounded_where,
            offset=offset + len(features),
            record_count=page_count,
            return_geometry=spec.return_geometry,
            parameters=spec.geometry_parameters,
        )
        if len(page) != page_count:
            raise PaginationError(
                "Palm Beach bounded pagination returned an incomplete page",
                url=QUERY_URL,
                details={
                    "expected": page_count,
                    "observed": len(page),
                    "offset": offset + len(features),
                },
            )
        features.extend(page)

    observed_ids = tuple(_feature_object_id(feature) for feature in features)
    if len(observed_ids) != len(set(observed_ids)):
        raise PaginationError(
            "Palm Beach pagination repeated a feature occurrence",
            url=QUERY_URL,
        )
    if observed_ids != tuple(sorted(observed_ids)):
        raise PaginationError(
            "Palm Beach feature response is not ordered by OBJECTID",
            url=QUERY_URL,
        )
    if state is not None and observed_ids and observed_ids[0] <= state.last_object_id:
        raise PaginationError(
            "Palm Beach continuation repeated or moved behind its boundary",
            url=QUERY_URL,
        )
    if observed_ids and observed_ids[-1] > boundary:
        raise PaginationError(
            "Palm Beach page crossed its snapshot OBJECTID boundary",
            url=QUERY_URL,
        )
    next_offset = offset + len(features)
    next_cursor = None
    if next_offset < total_count:
        if not observed_ids:
            raise PaginationError(
                "Palm Beach cursor cannot advance without a feature",
                url=QUERY_URL,
            )
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria_fingerprint,
                schema_fingerprint=contract.schema_fingerprint,
                boundary_object_id=boundary,
                total_count=total_count,
                offset=next_offset,
                last_object_id=observed_ids[-1],
            )
        )
    return FeatureBatch(
        features=tuple(features),
        contract=contract,
        boundary_object_id=boundary,
        total_count=total_count,
        next_cursor=next_cursor,
        requests_made=client.request_count - start_requests,
    )


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _money(value: Any) -> int | float | None:
    numeric = _number(value)
    if numeric is not None:
        return numeric
    text = _clean_text(value)
    if text is None:
        return None
    cleaned = text.replace("$", "").replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    return float(cleaned) if "." in cleaned else int(cleaned)


def _epoch_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(
                value / 1000,
                tz=timezone.utc,
            ).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    return _clean_text(value)


def _owner_observations(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    for field_name in ("OWNER_NAME1", "OWNER_NAME2"):
        raw_name = _clean_text(attributes.get(field_name))
        if raw_name:
            owners.append(
                {
                    "raw_name": raw_name,
                    "role": "assessment_roll_owner",
                    "source_field": field_name,
                    "confidence": "high",
                    "recorded_title_evidence": False,
                }
            )
    return owners


def _situs_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = _clean_text(attributes.get("SITE_ADDR_STR"))
    if not raw:
        return None
    return {
        "raw_address": raw,
        "street_number": _clean_text(attributes.get("STREET_NUMBER")),
        "street_fraction": _clean_text(attributes.get("STREET_FRACTION")),
        "pre_direction": _clean_text(attributes.get("PRE_DIR")),
        "street_name": _clean_text(attributes.get("STREET_NAME")),
        "street_suffix": _clean_text(attributes.get("STREET_SUFFIX_ABBR")),
        "post_direction": _clean_text(attributes.get("POST_DIR")),
        "city": _clean_text(attributes.get("MUNICIPALITY")),
        "country": "US",
    }


def _mailing_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    lines = [
        _clean_text(attributes.get(field_name))
        for field_name in ("PADDR1", "PADDR2", "PADDR3")
    ]
    raw = ", ".join(line for line in lines if line)
    if not raw:
        return None
    zip1 = _clean_text(attributes.get("ZIP1"))
    zip2 = _clean_text(attributes.get("ZIP2"))
    postal_code = f"{zip1}-{zip2}" if zip1 and zip2 else zip1
    return {
        "raw_address": raw,
        "address_lines": [line for line in lines if line],
        "city": _clean_text(attributes.get("CITYNAME")),
        "state": _clean_text(attributes.get("STATE")),
        "postal_code": postal_code,
        "country": "US",
    }


def _last_sale(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    values = {
        "sale_key": attributes.get("SALEKEY"),
        "sale_date": _epoch_date(attributes.get("SALE_DATE")),
        "book": _clean_text(attributes.get("BOOK")),
        "page": _clean_text(attributes.get("PAGE")),
        "published_price": _clean_text(attributes.get("PRICE")),
        "sale_price": _money(attributes.get("PRICE")),
        "instrument_code": _clean_text(attributes.get("INSTRUMENT")),
        "qualification_code": _clean_text(attributes.get("QUAL_CODE")),
        "qualified_sale_date": _epoch_date(attributes.get("Q_SALE_DATE")),
        "months_since_sale": _number(attributes.get("MONTHS_SINCE_SALE")),
    }
    if not any(value not in (None, "") for value in values.values()):
        return None
    book = values["book"]
    page = values["page"]
    source_document_ref = (
        f"BOOK:{book}:PAGE:{page}"
        if book and page
        else (
            f"SALEKEY:{values['sale_key']}"
            if values["sale_key"] is not None
            else None
        )
    )
    return {
        **values,
        "source_document_ref": source_document_ref,
        "derivation": "assessment_roll_last_sale",
        "recorded_title_evidence": False,
        "instrument_copy_in_source": False,
        "book_page_pivot": (
            {
                "source_id": CLERK_SOURCE_ID,
                "url": CLERK_SEARCH_URL,
                "book": book,
                "page": page,
                "relationship": "exact_book_page_search_candidate",
            }
            if book and page
            else None
        ),
    }


def normalize_feature(
    feature: Mapping[str, Any],
    *,
    contract: LayerContract,
    geometry_requested: bool,
) -> dict[str, Any]:
    """Normalize one feature occurrence without collapsing parcel-number repeats."""

    attributes = dict(_attributes(feature))
    object_id = _feature_object_id(feature)
    parcel_number = _clean_text(attributes.get("PARCEL_NUMBER"))
    parid = _clean_text(attributes.get("PARID"))
    occurrence_id = f"OBJECTID:{object_id}"
    feature_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "parcel_feature",
        occurrence_id,
    )
    blank_publisher_fields = [
        field_name
        for field_name in (
            "OWNER_NAME1",
            "OWNER_NAME2",
            "SITE_ADDR_STR",
            "PADDR1",
            "PADDR2",
            "PADDR3",
        )
        if _clean_text(attributes.get(field_name)) is None
    ]
    legal_lines = [
        _clean_text(attributes.get(field_name))
        for field_name in ("LEGAL1", "LEGAL2", "LEGAL3")
    ]
    record: dict[str, Any] = {
        "record_kind": "parcel_assessment_geometry_snapshot",
        "source_id": SOURCE_ID,
        "source_url": LAYER_URL,
        "canonical_ref": feature_ref,
        "feature_ref": feature_ref,
        "source_occurrence_id": occurrence_id,
        "feature_occurrence": {
            "object_id_field": OBJECT_ID_FIELD,
            "object_id": object_id,
            "feature_ref": feature_ref,
        },
        "native_parcel_id": parcel_number,
        "parcel_join_key": (
            {
                "county_geoid": COUNTY_GEOID,
                "field": "parcel_number",
                "value": parcel_number,
                "role": "candidate_exact_tax_account_join",
                "uniqueness_in_layer": "not_assumed",
            }
            if parcel_number
            else None
        ),
        "published_identifiers": {
            "parcel_number": parcel_number,
            "parid": parid,
            "parid_role": "published_geometry_or_group_identifier",
            "parid_uniqueness_assumed": False,
        },
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
            "market_value": _number(attributes.get("TOTAL_MARKET")),
            "market_value_not_capped": _number(attributes.get("MKT_NOT_CAPPED")),
            "market_value_capped": _number(attributes.get("MKT_CAPPED")),
            "cap_adjusted_value": _number(attributes.get("CAP_ADJ_VAL")),
            "agricultural_use_value": _number(attributes.get("AG_USE_VAL")),
            "assessed_value": _number(attributes.get("ASSESSED_VAL")),
            "exemption_value": _number(attributes.get("EXEMPTION")),
            "parcel_value": _number(attributes.get("TOTAL_VALUE")),
            "taxable_value": _number(attributes.get("TOTAL_TAXABLE")),
            "land_value": _number(attributes.get("LAND_MARKET")),
            "improvement_value": _number(attributes.get("IMPRV_MRKT")),
            "assessment_class": _clean_text(attributes.get("PROPERTY_USE")),
            "homestead_flag": _clean_text(attributes.get("HMSTD_FLG")),
        },
        "last_sale": _last_sale(attributes),
        "land": {
            "acres": _number(attributes.get("ACRES")),
            "published_area": _number(
                attributes.get("PAO.PARCEL_DETAILS.AREA")
            ),
            "condominium": _clean_text(attributes.get("CONDO")),
            "subdivision_name": _clean_text(attributes.get("SUBDIV_NAME")),
            "neighborhood": _clean_text(attributes.get("NBHD")),
            "municipality": _clean_text(attributes.get("MUNICIPALITY")),
            "community_redevelopment_area": _clean_text(attributes.get("CRA")),
            "legal_lines": [line for line in legal_lines if line],
            "legal_description": " ".join(line for line in legal_lines if line)
            or None,
        },
        "publisher_redaction_state": {
            "confidential_flag": _clean_text(attributes.get("CONFID_FLG")),
            "blank_owner_or_address_fields": blank_publisher_fields,
            "interpretation": "publisher_state_preserved_without_code_inference",
        },
        "source_schema": {
            "schema_fingerprint": contract.schema_fingerprint,
            "object_id_field": contract.object_id_field,
            "geometry_type": contract.geometry_type,
        },
        "source_semantics": {
            "record_grain": "published_parcel_detail_feature_occurrence",
            "assessment_owner_role": True,
            "recorded_title_or_beneficial_ownership": False,
            "recorder_instrument_copy": False,
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
            "County GIS feature transformed to EPSG:4326; not a surveyed "
            "legal boundary."
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
) -> PalmBeachPropertyClient:
    limits = access_contract.get("limits") or {}
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return PalmBeachPropertyClient(
        timeout=args.timeout,
        minimum_interval=minimum_interval,
        retry_attempts=args.retry_attempts,
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
    qsales_metadata: Mapping[str, Any],
    qsales_contract: LayerContract,
) -> dict[str, Any]:
    return {
        "record_kind": "source_metadata",
        "source_id": SOURCE_ID,
        "primary_representation": {
            "name": metadata.get("name"),
            "url": LAYER_URL,
            **contract.to_dict(),
        },
        "related_representations": [
            {
                "name": qsales_metadata.get("name"),
                "url": QSALES_LAYER_URL,
                **qsales_contract.to_dict(),
                "relationship": (
                    "same_publisher_thematic_representation_candidate_same_population"
                ),
                "independent_corroboration": False,
                "exact_objectid_or_row_parity_established": False,
            }
        ],
        "traversal": {
            "identity": OBJECT_ID_FIELD,
            "stable_order": f"{OBJECT_ID_FIELD}_ascending",
            "snapshot_boundary": f"maximum_matching_{OBJECT_ID_FIELD}",
            "pagination": "resultOffset_with_live_maxRecordCount",
            "caller_limit_required": False,
        },
        "complements": [
            {
                "source_id": CLERK_SOURCE_ID,
                "role": "recorded_instrument_index_and_document_pivot",
                "url": CLERK_SEARCH_URL,
            },
            {
                "source_id": FL_DOR_SOURCE_ID,
                "role": "statewide_roll_bulk_complement",
            },
            {
                "url": PROPERTY_APPRAISER_DATA_URL,
                "role": "advertised_appraiser_flat_file_directory",
                "access_note": (
                    "The current cloud-drive invitation presents consent "
                    "language inconsistent with general anonymous reuse; the "
                    "invitation is not accepted or automated."
                ),
            },
        ],
    }


def _probe_record(
    client: PalmBeachPropertyClient,
    metadata: Mapping[str, Any],
    contract: LayerContract,
    qsales_metadata: Mapping[str, Any],
    qsales_contract: LayerContract,
) -> dict[str, Any]:
    total_count = client.fetch_count("1=1")
    qsales_count = client.fetch_count("1=1", query_url=QSALES_QUERY_URL)
    sample_batch = fetch_feature_batch(
        client,
        operation="probe",
        spec=QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=1,
        cursor=None,
    )
    sample = None
    if sample_batch.features:
        attributes = dict(_attributes(sample_batch.features[0]))
        sample = {
            "object_id": _feature_object_id(sample_batch.features[0]),
            "parcel_number": attributes.get("PARCEL_NUMBER"),
            "parid": attributes.get("PARID"),
            "confidential_flag": attributes.get("CONFID_FLG"),
        }
    return {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "schema_fingerprint": contract.schema_fingerprint,
        "stable_contract": {
            "primary": contract.to_dict(),
            "qsales": qsales_contract.to_dict(),
            "primary_layer_name": metadata.get("name"),
            "qsales_layer_name": qsales_metadata.get("name"),
        },
        "rolling_observations": {
            "feature_count": total_count,
            "distinct_parcel_number_count": client.fetch_distinct_count(
                "PARCEL_NUMBER"
            ),
            "distinct_parid_count": client.fetch_distinct_count("PARID"),
            "null_parid_count": client.fetch_count("PARID IS NULL"),
            "qsales_feature_count": qsales_count,
            "primary_and_qsales_counts_equal": total_count == qsales_count,
            "sample": sample,
        },
        "identity_notes": {
            "feature_occurrence": OBJECT_ID_FIELD,
            "candidate_parcel_join": "PARCEL_NUMBER",
            "published_geometry_or_group_identifier": "PARID",
            "parcel_number_uniqueness_assumed": False,
            "parid_uniqueness_assumed": False,
        },
    }


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    client: PalmBeachPropertyClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one catalog-aware Palm Beach parcel query."""

    query = build_query(args)
    try:
        decision = (
            access_contract if access_contract is not None else _access_contract(args)
        )
        active_client = client or _client(args, decision)
        if args.command in {"metadata", "discovery", "probe"}:
            metadata = active_client.fetch_metadata()
            contract = metadata_contract(metadata)
            qsales_metadata = active_client.fetch_metadata(QSALES_LAYER_URL)
            qsales_contract = metadata_contract(
                qsales_metadata,
                layer_url=QSALES_LAYER_URL,
                expected_name=QSALES_LAYER_NAME,
            )
            record = (
                _probe_record(
                    active_client,
                    metadata,
                    contract,
                    qsales_metadata,
                    qsales_contract,
                )
                if args.command == "probe"
                else _metadata_record(
                    metadata,
                    contract,
                    qsales_metadata,
                    qsales_contract,
                )
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=SOURCE_WARNINGS,
            )
        else:
            spec = _query_spec(args)
            if args.command == "count":
                metadata = active_client.fetch_metadata()
                contract = metadata_contract(metadata)
                count = active_client.fetch_count(
                    spec.where,
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
                            "count": count,
                            "schema_fingerprint": contract.schema_fingerprint,
                        }
                    ],
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
                        decision.get("reason_code")
                        or "machine_acquisition_denied"
                    ),
                    message=str(error),
                    category="access_policy",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    except PalmBeachPropertyError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="palm_beach_property_normalization_failed",
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
        except Exception as error:  # pragma: no cover - external logging
            print(f"WARNING: search logging failed: {error}", file=sys.stderr)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Palm Beach parcel details {args.command} ({result.status.value})",
    ):
        return
    print(
        f"Palm Beach parcel details {args.command}: {result.status.value} "
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
                "Optional caller-selected result bound; omitted traverses the "
                "complete bounded matching population"
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
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB_PATH))
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
            "Query Palm Beach County's official anonymous parcel-detail GIS"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("metadata", "discovery", "probe"):
        command_parser = subparsers.add_parser(command)
        _add_runtime_arguments(command_parser)

    count_parser = subparsers.add_parser("count")
    count_parser.add_argument("query", nargs="?")
    count_parser.add_argument(
        "--field",
        choices=tuple(SEARCH_FIELDS),
        default="any",
    )
    _add_match_argument(count_parser)
    _add_runtime_arguments(count_parser)

    list_parser = subparsers.add_parser("list")
    _add_runtime_arguments(list_parser, records=True)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--field",
        choices=tuple(SEARCH_FIELDS),
        default="any",
    )
    _add_match_argument(search_parser)
    _add_runtime_arguments(search_parser, records=True)

    for command, help_text in (
        ("parcel", "Match the published PARCEL_NUMBER exactly"),
        ("parid", "Match the separate published PARID exactly"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_runtime_arguments(command_parser, records=True)

    owner_parser = subparsers.add_parser("owner")
    owner_parser.add_argument("query")
    _add_match_argument(owner_parser)
    _add_runtime_arguments(owner_parser, records=True)

    address_parser = subparsers.add_parser("address")
    address_parser.add_argument("query")
    _add_match_argument(address_parser)
    _add_runtime_arguments(address_parser, records=True)

    sale_parser = subparsers.add_parser("sale")
    sale_parser.add_argument("query")
    sale_parser.add_argument(
        "--field",
        choices=("any", "sale-key", "book-page"),
        default="any",
    )
    _add_runtime_arguments(sale_parser, records=True)

    objectid_parser = subparsers.add_parser("objectid")
    objectid_parser.add_argument("objectid", type=_nonnegative_int)
    _add_runtime_arguments(objectid_parser, records=True)

    point_parser = subparsers.add_parser("point")
    point_parser.add_argument("longitude", type=float)
    point_parser.add_argument("latitude", type=float)
    _add_runtime_arguments(point_parser, records=True)

    bbox_parser = subparsers.add_parser("bbox")
    bbox_parser.add_argument("west", type=float)
    bbox_parser.add_argument("south", type=float)
    bbox_parser.add_argument("east", type=float)
    bbox_parser.add_argument("north", type=float)
    _add_runtime_arguments(bbox_parser, records=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
