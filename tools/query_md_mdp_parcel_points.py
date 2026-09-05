#!/usr/bin/env python3
"""Query Maryland's official MD iMAP Parcel Points representation.

Maryland Department of Planning publishes this statewide point layer from
State Department of Assessments and Taxation data, with additional planning
attributes.  It is a distinct representation of the same parcel-account
population exposed by the existing hidden-owner Socrata dataset:

* ``ACCTID`` is the exact cross-representation parcel-account join.
* ``OBJECTID`` identifies and orders one ArcGIS feature occurrence.
* Current-owner names are not fields in this representation.
* The fields labelled as owner mailing address are contact-address data, not
  assertions of recorded title or beneficial ownership.

Ordered scans use a maximum-``OBJECTID`` boundary.  Omitting ``--limit``
exhausts the bounded matching population; a caller-selected limit returns a
query-, schema-, and population-bound continuation cursor.

Examples:
    uv run python tools/query_md_mdp_parcel_points.py account 1901000047
    uv run python tools/query_md_mdp_parcel_points.py address "100 MAIN" --match exact
    uv run python tools/query_md_mdp_parcel_points.py query --county-code 19 --map 0042
    uv run python tools/query_md_mdp_parcel_points.py point -76.63 38.30
    uv run python tools/query_md_mdp_parcel_points.py probe
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
        CatalogError,
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
        CatalogError,
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


SOURCE_ID = "us-md-mdp-parcel-points"
RECORD_IDENTITY_SOURCE_ID = "us-md-sdat-property-hidden"
STATE_CODE = "MD"
STATE_FIPS = "24"

LAYER_URL = (
    "https://mdgeodata.md.gov/imap/rest/services/"
    "PlanningCadastre/MD_PropertyData/MapServer/0"
)
QUERY_URL = f"{LAYER_URL}/query"
LAYER_NAME = "Parcel Points"
DATASET_ID = "PlanningCadastre/MD_PropertyData/MapServer/0"
GEOMETRY_TYPE = "esriGeometryPoint"
OBJECT_ID_FIELD = "OBJECTID"
ACCOUNT_ID_FIELD = "ACCTID"
OUTPUT_CRS = "EPSG:4326"
CURSOR_PREFIX = "md-mdp-parcel-points:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRY_ATTEMPTS = 3

SDAT_SOCRATA_URL = (
    "https://opendata.maryland.gov/Business-and-Economy/"
    "Maryland-Real-Property-Assessments_Hidden-Property/ed4q-f8tm"
)
MDP_PRODUCT_URL = (
    "https://planning.maryland.gov/MSDC/Pages/9_gam/"
    "district-download-gis-files.aspx"
)

COUNTY_GEOIDS = {
    "01": ("24001", "Allegany County"),
    "02": ("24003", "Anne Arundel County"),
    "03": ("24510", "Baltimore City"),
    "04": ("24005", "Baltimore County"),
    "05": ("24009", "Calvert County"),
    "06": ("24011", "Caroline County"),
    "07": ("24013", "Carroll County"),
    "08": ("24015", "Cecil County"),
    "09": ("24017", "Charles County"),
    "10": ("24019", "Dorchester County"),
    "11": ("24021", "Frederick County"),
    "12": ("24023", "Garrett County"),
    "13": ("24025", "Harford County"),
    "14": ("24027", "Howard County"),
    "15": ("24029", "Kent County"),
    "16": ("24031", "Montgomery County"),
    "17": ("24033", "Prince George's County"),
    "18": ("24035", "Queen Anne's County"),
    "19": ("24037", "St. Mary's County"),
    "20": ("24039", "Somerset County"),
    "21": ("24041", "Talbot County"),
    "22": ("24043", "Washington County"),
    "23": ("24045", "Wicomico County"),
    "24": ("24047", "Worcester County"),
}

# These are the fields used by normalization or stable identity checks.  The
# live layer currently publishes additional planning attributes, which remain
# available in ``raw_attributes`` without making them part of this projection.
REQUIRED_FIELDS = (
    "OBJECTID",
    "JURSCODE",
    "ACCTID",
    "DIGXCORD",
    "DIGYCORD",
    "CT2020",
    "BG2020",
    "GEOGCODE",
    "OOI",
    "RESITYP",
    "ADDRESS",
    "STRTNUM",
    "STRTDIR",
    "STRTNAM",
    "STRTTYP",
    "STRTSFX",
    "STRTUNT",
    "ADDRTYP",
    "CITY",
    "ZIPCODE",
    "OWNADD1",
    "OWNADD2",
    "OWNCITY",
    "OWNSTATE",
    "OWNERZIP",
    "OWNZIP2",
    "PREMSNUM",
    "PREMSDIR",
    "PREMSNAM",
    "PREMSTYP",
    "PREMCITY",
    "PREMZIP",
    "PREMZIP2",
    "LEGAL1",
    "LEGAL2",
    "LEGAL3",
    "DR1LIBER",
    "DR1FOLIO",
    "TOWNCODE",
    "DESCTOWN",
    "SUBDIVSN",
    "DSUBCODE",
    "DESCSUBD",
    "PLAT",
    "PLTLIBER",
    "PLTFOLIO",
    "SECTION",
    "BLOCK",
    "LOT",
    "MAP",
    "GRID",
    "PARCEL",
    "ZONING",
    "ZNCHGDAT",
    "RZREALDAT",
    "CIUSE",
    "DESCCIUSE",
    "EXCLASS",
    "DESCEXCL",
    "LU",
    "DESCLU",
    "ACRES",
    "LANDAREA",
    "LUOM",
    "WIDTH",
    "DEPTH",
    "PFUW",
    "PFUS",
    "PFLW",
    "PFSP",
    "PFSU",
    "PERMITTYP",
    "YEARBLT",
    "SQFTSTRC",
    "STRUGRAD",
    "DESCGRAD",
    "STRUCNST",
    "DESCCNST",
    "STRUSTYL",
    "DESCSTYL",
    "STRUBLDG",
    "DESCBLDG",
    "BLDG_STORY",
    "BLDG_UNITS",
    "LASTINSP",
    "LASTASSD",
    "ASSESSOR",
    "GR1LIBR1",
    "GR1FOLO1",
    "CONVEY1",
    "TRADATE",
    "CONSIDR1",
    "NFMLNDVL",
    "NFMIMPVL",
    "NFMTTLVL",
    "PTYPE",
    "SDATWEBADR",
    "MDPVDATE",
    "SDATDATE",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Maryland MD iMAP Parcel Points",
    source_role="statewide_parcel_assessment_point_representation",
    base_url=LAYER_URL,
    dataset_id=DATASET_ID,
    metadata={
        "authority": (
            "Maryland Department of Planning and Maryland State Department "
            "of Assessments and Taxation"
        ),
        "coverage": "State of Maryland",
        "record_grain": "published_arcgis_parcel_point_occurrence",
        "primary_identity": OBJECT_ID_FIELD,
        "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
        "record_identity_field": ACCOUNT_ID_FIELD,
        "current_owner_name_state": "not_published_in_representation",
        "related_representation": {
            "source_id": RECORD_IDENTITY_SOURCE_ID,
            "relationship": "same_authority_dataset_alternative_representation",
            "join_field": ACCOUNT_ID_FIELD,
            "independent_corroboration": False,
        },
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "ACCTID is the exact parcel-account join to the Maryland hidden-owner "
    "Socrata representation; repeated ArcGIS feature occurrences remain "
    "separate by OBJECTID.",
    "Current-owner names are not published in this representation. Fields "
    "labelled as owner mailing address are preserved as contact-address "
    "fields and do not establish recorded title or beneficial ownership.",
    "Parcel Points are published point locations, not surveyed parcel "
    "boundaries.",
)


@dataclass(frozen=True)
class LayerContract:
    schema_fingerprint: str
    field_names: tuple[str, ...]
    max_record_count: int
    object_id_field: str
    geometry_type: str
    spatial_reference: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_fingerprint": self.schema_fingerprint,
            "field_names": list(self.field_names),
            "max_record_count": self.max_record_count,
            "object_id_field": self.object_id_field,
            "geometry_type": self.geometry_type,
            "spatial_reference": dict(self.spatial_reference),
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
class FeaturePage:
    features: tuple[Mapping[str, Any], ...]
    exceeded_transfer_limit: bool


@dataclass(frozen=True)
class FeatureBatch:
    features: tuple[Mapping[str, Any], ...]
    contract: LayerContract
    boundary_object_id: int | None
    total_count: int
    next_cursor: str | None
    requests_made: int
    transfer_limit_pages: int


class MarylandParcelPointsError(ValueError):
    """Selection or continuation error with result-envelope semantics."""

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


class MarylandParcelPointsClient(ArcGISRESTClient):
    """ArcGIS client exposing metadata and bounded ordered page operations."""

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

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(LAYER_URL, params={"f": "pjson"})
        return _arcgis_object(payload, "layer metadata", LAYER_URL)

    def fetch_count(
        self,
        where: str,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> int:
        payload = self._request_json(
            QUERY_URL,
            params={
                **dict(parameters or {}),
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        value = _arcgis_object(payload, "count query", QUERY_URL)
        count = value.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Maryland Parcel Points count is not a non-negative integer",
                url=QUERY_URL,
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
        features = _feature_tuple(payload, "boundary query")
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
    ) -> FeaturePage:
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
        features = _feature_tuple(value, "feature query")
        exceeded = value.get("exceededTransferLimit", False)
        if not isinstance(exceeded, bool):
            raise SourceSchemaError(
                "Maryland Parcel Points transfer-limit marker is not boolean",
                url=QUERY_URL,
                details={"exceededTransferLimit": exceeded},
            )
        if exceeded and not features:
            raise PaginationError(
                "Maryland Parcel Points reported more rows without a page",
                url=QUERY_URL,
                details={"offset": offset, "record_count": record_count},
            )
        return FeaturePage(
            features=features,
            exceeded_transfer_limit=exceeded,
        )


def _arcgis_object(
    payload: Any,
    description: str,
    url: str,
) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            f"Maryland Parcel Points {description} response must be an object",
            url=url,
            details={"response_type": type(payload).__name__},
        )
    if "error" in payload:
        raise SourceResponseError(
            f"Maryland Parcel Points {description} returned an ArcGIS error",
            url=url,
            details={"response": payload.get("error")},
        )
    return payload


def _feature_tuple(
    payload: Any,
    description: str,
) -> tuple[Mapping[str, Any], ...]:
    value = _arcgis_object(payload, description, QUERY_URL)
    features = value.get("features")
    if not isinstance(features, list) or any(
        not isinstance(feature, Mapping) for feature in features
    ):
        raise SourceSchemaError(
            f"Maryland Parcel Points {description} lacks a features array",
            url=QUERY_URL,
        )
    return tuple(features)


def metadata_contract(metadata: Mapping[str, Any]) -> LayerContract:
    """Validate feature identity, mapped fields, and traversal capabilities."""

    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Maryland Parcel Points metadata lacks field declarations",
            url=LAYER_URL,
        )
    field_names = tuple(str(field.get("name") or "") for field in fields)
    missing = sorted(set(REQUIRED_FIELDS) - set(field_names))
    if missing:
        raise SourceSchemaError(
            "Maryland Parcel Points is missing mapped fields",
            url=LAYER_URL,
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
            "Maryland Parcel Points occurrence identity changed",
            url=LAYER_URL,
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
        "name": LAYER_NAME,
        "type": "Feature Layer",
        "geometryType": GEOMETRY_TYPE,
    }
    if identity != expected_identity:
        raise SourceSchemaError(
            "Maryland Parcel Points layer identity changed",
            url=LAYER_URL,
            details={"expected": expected_identity, "observed": identity},
        )
    capabilities = {
        value.strip()
        for value in str(metadata.get("capabilities") or "").split(",")
        if value.strip()
    }
    if "Query" not in capabilities:
        raise SourceSchemaError(
            "Maryland Parcel Points no longer declares query capability",
            url=LAYER_URL,
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
            "Maryland Parcel Points traversal capabilities changed",
            url=LAYER_URL,
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
            "Maryland Parcel Points lacks a usable maxRecordCount",
            url=LAYER_URL,
            details={"maxRecordCount": max_record_count},
        )
    spatial_reference = metadata.get("sourceSpatialReference")
    if not isinstance(spatial_reference, Mapping):
        extent = metadata.get("extent")
        spatial_reference = (
            extent.get("spatialReference") if isinstance(extent, Mapping) else None
        )
    if not isinstance(spatial_reference, Mapping):
        raise SourceSchemaError(
            "Maryland Parcel Points lacks a spatial reference",
            url=LAYER_URL,
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "layer_url": LAYER_URL,
            "identity": identity,
            "fields": arcgis_declared_schema(fields),
            "object_id_field": OBJECT_ID_FIELD,
            "spatial_reference": dict(spatial_reference),
            "traversal": required_capabilities,
            "max_record_count": max_record_count,
        }
    )
    return LayerContract(
        schema_fingerprint=schema_fingerprint,
        field_names=field_names,
        max_record_count=max_record_count,
        object_id_field=OBJECT_ID_FIELD,
        geometry_type=GEOMETRY_TYPE,
        spatial_reference=dict(spatial_reference),
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


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_literal(value: Any, description: str) -> str:
    text = _clean_text(value)
    if not text:
        raise MarylandParcelPointsError(
            "blank_selector",
            f"{description} must not be blank",
        )
    return text.replace("'", "''")


def _account_id(value: Any) -> str:
    text = _sql_literal(value, "parcel account")
    normalized = "".join(
        character for character in text.upper() if character.isalnum()
    )
    if not normalized:
        raise MarylandParcelPointsError(
            "blank_selector",
            "parcel account must not be blank",
        )
    return normalized


def _county_code(value: Any) -> str:
    text = _sql_literal(value, "Maryland county code")
    digits = "".join(character for character in text if character.isdigit())
    normalized = digits.zfill(2)
    if normalized not in COUNTY_GEOIDS:
        raise MarylandParcelPointsError(
            "invalid_county_code",
            "Maryland SDAT county code must be 01 through 24",
        )
    return normalized


def _object_id(value: Any) -> int:
    if isinstance(value, bool) or (
        isinstance(value, float) and not value.is_integer()
    ):
        raise SourceSchemaError(
            "Maryland Parcel Points OBJECTID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "Maryland Parcel Points OBJECTID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        ) from error
    if parsed < 0:
        raise SourceSchemaError(
            "Maryland Parcel Points OBJECTID must be a non-negative integer",
            url=QUERY_URL,
            details={"value": value},
        )
    return parsed


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "Maryland Parcel Points feature lacks attributes",
            url=QUERY_URL,
        )
    return attributes


def _feature_object_id(feature: Mapping[str, Any]) -> int:
    return _object_id(_attributes(feature).get(OBJECT_ID_FIELD))


def _match_expression(field_name: str, value: Any, match: str) -> str:
    literal = _sql_literal(value, "search selector").upper()
    if match == "exact":
        return f"UPPER({field_name})='{literal}'"
    if match == "prefix":
        return f"UPPER({field_name}) LIKE '{literal}%'"
    if match == "contains":
        return f"UPPER({field_name}) LIKE '%{literal}%'"
    raise MarylandParcelPointsError(
        "invalid_match_mode",
        f"unsupported match mode: {match}",
    )


def _exact_expression(field_name: str, value: Any) -> str:
    literal = _sql_literal(value, field_name).upper()
    return f"UPPER({field_name})='{literal}'"


def _selector_filters(args: argparse.Namespace) -> list[str]:
    filters: list[str] = []
    command = args.command

    account = getattr(args, "account", None)
    parcel = getattr(args, "parcel", None)
    address = getattr(args, "address", None)
    if command == "account":
        account = args.selector
    elif command == "parcel":
        parcel = args.selector
    elif command == "address":
        address = args.selector

    if account is not None:
        filters.append(f"{ACCOUNT_ID_FIELD}='{_account_id(account)}'")
    if parcel is not None:
        filters.append(_exact_expression("PARCEL", parcel))
    if address is not None:
        filters.append(
            _match_expression(
                "ADDRESS",
                address,
                getattr(args, "match", "contains"),
            )
        )
    county = getattr(args, "county_code", None)
    if county is not None:
        code = _county_code(county)
        filters.append(f"JURSCODE LIKE '{code}%'")
    for argument, field_name in (
        ("map_number", "MAP"),
        ("plat", "PLAT"),
        ("grid", "GRID"),
        ("land_use", "LU"),
        ("zoning", "ZONING"),
    ):
        value = getattr(args, argument, None)
        if value is not None:
            filters.append(_exact_expression(field_name, value))
    return filters


def _query_spec(args: argparse.Namespace) -> QuerySpec:
    filters = _selector_filters(args)
    geometry_parameters: dict[str, Any] = {}
    return_geometry = bool(getattr(args, "geometry", False))
    if args.command == "objectid":
        filters.append(f"{OBJECT_ID_FIELD}={_object_id(args.objectid)}")
    elif args.command == "point":
        if not (-180 <= args.longitude <= 180):
            raise MarylandParcelPointsError(
                "invalid_longitude",
                "longitude must be between -180 and 180",
            )
        if not (-90 <= args.latitude <= 90):
            raise MarylandParcelPointsError(
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
    elif args.command == "bbox":
        if args.west >= args.east or args.south >= args.north:
            raise MarylandParcelPointsError(
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
        where=" AND ".join(f"({item})" for item in filters) or "1=1",
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
        raise MarylandParcelPointsError(
            "invalid_cursor",
            "cursor does not belong to the Maryland Parcel Points adapter",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarylandParcelPointsError(
            "invalid_cursor",
            "cursor is not valid encoded JSON",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != CURSOR_VERSION:
        raise MarylandParcelPointsError(
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
        raise MarylandParcelPointsError(
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
        raise MarylandParcelPointsError(
            "invalid_cursor",
            "cursor continuation values are inconsistent",
        )
    return state


def _validate_cursor(
    client: MarylandParcelPointsClient,
    state: CursorState,
    *,
    criteria_fingerprint: str,
    contract: LayerContract,
    spec: QuerySpec,
) -> None:
    if state.criteria_fingerprint != criteria_fingerprint:
        raise MarylandParcelPointsError(
            "cursor_query_mismatch",
            "cursor belongs to different Maryland Parcel Points criteria",
        )
    if state.schema_fingerprint != contract.schema_fingerprint:
        raise MarylandParcelPointsError(
            "cursor_schema_changed",
            "Maryland Parcel Points schema changed after cursor issue",
            status=ResultStatus.SOURCE_CHANGED,
        )
    bounded = _bounded_where(spec.where, state.boundary_object_id)
    count = client.fetch_count(
        bounded,
        parameters=spec.geometry_parameters,
    )
    if count != state.total_count:
        raise MarylandParcelPointsError(
            "cursor_snapshot_changed",
            "bounded Parcel Points population changed after cursor issue",
            status=ResultStatus.SOURCE_CHANGED,
            details={"cursor_total": state.total_count, "current_total": count},
        )
    prefix_count = client.fetch_count(
        f"({bounded}) AND {OBJECT_ID_FIELD}<={state.last_object_id}",
        parameters=spec.geometry_parameters,
    )
    if prefix_count != state.offset:
        raise MarylandParcelPointsError(
            "cursor_boundary_changed",
            "Parcel Points ordering changed at the cursor boundary",
            status=ResultStatus.SOURCE_CHANGED,
            details={"cursor_offset": state.offset, "prefix_count": prefix_count},
        )


def fetch_feature_batch(
    client: MarylandParcelPointsClient,
    *,
    operation: str,
    spec: QuerySpec,
    limit: int | None,
    cursor: str | None,
) -> FeatureBatch:
    """Fetch a bounded page or exhaust the bounded population."""

    if limit is not None and limit <= 0:
        raise MarylandParcelPointsError(
            "invalid_limit",
            "limit must be a positive integer",
        )
    start_requests = client.request_count
    contract = metadata_contract(client.fetch_metadata())
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
                transfer_limit_pages=0,
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
    transfer_limit_pages = 0
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
        if page.exceeded_transfer_limit:
            transfer_limit_pages += 1
        if len(page.features) != page_count:
            raise PaginationError(
                "Maryland Parcel Points returned an incomplete bounded page",
                url=QUERY_URL,
                details={
                    "expected": page_count,
                    "observed": len(page.features),
                    "offset": offset + len(features),
                    "exceededTransferLimit": page.exceeded_transfer_limit,
                },
            )
        features.extend(page.features)

    observed_ids = tuple(_feature_object_id(feature) for feature in features)
    if len(observed_ids) != len(set(observed_ids)):
        raise PaginationError(
            "Maryland Parcel Points pagination repeated an occurrence",
            url=QUERY_URL,
        )
    if observed_ids != tuple(sorted(observed_ids)):
        raise PaginationError(
            "Maryland Parcel Points response is not ordered by OBJECTID",
            url=QUERY_URL,
        )
    if state is not None and observed_ids and observed_ids[0] <= state.last_object_id:
        raise PaginationError(
            "Maryland Parcel Points continuation repeated its boundary",
            url=QUERY_URL,
        )
    if observed_ids and observed_ids[-1] > boundary:
        raise PaginationError(
            "Maryland Parcel Points page crossed its OBJECTID boundary",
            url=QUERY_URL,
        )

    next_offset = offset + len(features)
    next_cursor = None
    if next_offset < total_count:
        if not observed_ids:
            raise PaginationError(
                "Maryland Parcel Points cursor cannot advance without a feature",
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
        transfer_limit_pages=transfer_limit_pages,
    )


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return value
    text = _clean_text(value)
    if not text:
        return None
    candidate = text.replace("$", "").replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", candidate):
        return None
    numeric = float(candidate)
    return int(numeric) if numeric.is_integer() else numeric


def _date(value: Any) -> str | None:
    text = _clean_text(value)
    if not text or text in {"000000", "00000000", "0000.00.00"}:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) == 8:
        first_year = int(digits[:4])
        last_year = int(digits[-4:])
        if 1800 <= first_year <= 2199:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
        if 1800 <= last_year <= 2199:
            return f"{digits[4:]}-{digits[:2]}-{digits[2:4]}"
    if len(digits) == 6 and 1800 <= int(digits[:4]) <= 2199:
        return f"{digits[:4]}-{digits[4:]}"
    if len(digits) == 6 and 1800 <= int(digits[-4:]) <= 2199:
        return f"{digits[2:]}-{digits[:2]}"
    return text


def _date_observation(value: Any) -> dict[str, Any] | None:
    raw = _clean_text(value)
    if not raw:
        return None
    normalized = _date(raw)
    precision = (
        "day"
        if normalized and re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized)
        else (
            "month"
            if normalized and re.fullmatch(r"\d{4}-\d{2}", normalized)
            else "source_text"
        )
    )
    return {
        "raw": raw,
        "normalized": normalized,
        "precision": precision,
    }


def _county_from_attributes(
    attributes: Mapping[str, Any],
) -> tuple[str | None, str, str]:
    candidates = (
        _clean_text(attributes.get("JURSCODE")),
        _clean_text(attributes.get("ACCTID")),
    )
    for candidate in candidates:
        digits = "".join(
            character for character in (candidate or "") if character.isdigit()
        )
        if len(digits) >= 2 and digits[:2] in COUNTY_GEOIDS:
            geoid, name = COUNTY_GEOIDS[digits[:2]]
            return digits[:2], geoid, name
    return None, STATE_FIPS, "Maryland"


def _situs_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = _clean_text(attributes.get("ADDRESS"))
    structured_values = {
        "street_number": _clean_text(attributes.get("STRTNUM")),
        "pre_direction": _clean_text(attributes.get("STRTDIR")),
        "street_name": _clean_text(attributes.get("STRTNAM")),
        "street_type": _clean_text(attributes.get("STRTTYP")),
        "post_direction": _clean_text(attributes.get("STRTSFX")),
        "unit": _clean_text(attributes.get("STRTUNT")),
        "city": _clean_text(attributes.get("CITY")),
        "postal_code": _clean_text(attributes.get("ZIPCODE")),
    }
    premise_values = {
        "street_number": _clean_text(attributes.get("PREMSNUM")),
        "pre_direction": _clean_text(attributes.get("PREMSDIR")),
        "street_name": _clean_text(attributes.get("PREMSNAM")),
        "street_type": _clean_text(attributes.get("PREMSTYP")),
        "city": _clean_text(attributes.get("PREMCITY")),
        "postal_code": _clean_text(attributes.get("PREMZIP")),
        "postal_extension": _clean_text(attributes.get("PREMZIP2")),
    }
    if not raw and not any(structured_values.values()) and not any(
        premise_values.values()
    ):
        return None
    return {
        "raw": raw,
        "raw_address": raw,
        **structured_values,
        "state": STATE_CODE,
        "country": "US",
        "address_source_indicator": _clean_text(attributes.get("ADDRTYP")),
        "residential_address_type": _clean_text(attributes.get("RESITYP")),
        "premise_components": premise_values,
    }


def _mailing_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    lines = [
        _clean_text(attributes.get(field_name))
        for field_name in ("OWNADD1", "OWNADD2")
    ]
    city = _clean_text(attributes.get("OWNCITY"))
    state = _clean_text(attributes.get("OWNSTATE"))
    postal = _clean_text(attributes.get("OWNERZIP"))
    extension = _clean_text(attributes.get("OWNZIP2"))
    if not any((*lines, city, state, postal, extension)):
        return None
    postal_code = f"{postal}-{extension}" if postal and extension else postal
    raw = ", ".join(line for line in lines if line) or None
    return {
        "raw": raw,
        "raw_address": raw,
        "address_lines": [line for line in lines if line],
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": None,
        "published_field_role": "owner_mailing_address",
        "current_owner_name_published": False,
        "ownership_assertion": False,
        "source_fields": [
            "OWNADD1",
            "OWNADD2",
            "OWNCITY",
            "OWNSTATE",
            "OWNERZIP",
            "OWNZIP2",
        ],
    }


def _legal_description(attributes: Mapping[str, Any]) -> dict[str, Any]:
    lines = [
        _clean_text(attributes.get(field_name))
        for field_name in ("LEGAL1", "LEGAL2", "LEGAL3")
    ]
    present = [line for line in lines if line]
    return {
        "lines": present,
        "text": " ".join(present) or None,
    }


def normalize_feature(
    feature: Mapping[str, Any],
    *,
    contract: LayerContract,
    geometry_requested: bool,
) -> dict[str, Any]:
    """Normalize one point occurrence while sharing parcel-account identity."""

    attributes = dict(_attributes(feature))
    object_id = _feature_object_id(feature)
    account_id = _clean_text(attributes.get(ACCOUNT_ID_FIELD))
    if not account_id:
        raise SourceSchemaError(
            "Maryland Parcel Points feature lacks ACCTID",
            url=QUERY_URL,
            details={"object_id": object_id},
        )
    county_code, county_geoid, county_name = _county_from_attributes(attributes)
    canonical_ref = canonical_property_ref(
        RECORD_IDENTITY_SOURCE_ID,
        county_geoid,
        "parcel",
        account_id,
    )
    occurrence_ref = canonical_property_ref(
        SOURCE_ID,
        county_geoid,
        "parcel_feature",
        f"OBJECTID:{object_id}",
    )
    legal = _legal_description(attributes)
    record: dict[str, Any] = {
        "record_kind": "parcel_assessment_point_snapshot",
        "source_id": SOURCE_ID,
        "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
        "source_url": LAYER_URL,
        "canonical_ref": canonical_ref,
        "representation_ref": occurrence_ref,
        "source_occurrence_id": f"OBJECTID:{object_id}",
        "record_identity": {
            "source_id": RECORD_IDENTITY_SOURCE_ID,
            "field": ACCOUNT_ID_FIELD,
            "value": account_id,
            "relationship": "exact_cross_representation_parcel_account_join",
            "canonical_ref": canonical_ref,
        },
        "complements": [
            {
                "source_id": RECORD_IDENTITY_SOURCE_ID,
                "relationship": (
                    "same_authority_dataset_alternative_representation"
                ),
                "join_field": ACCOUNT_ID_FIELD,
                "join_value": account_id,
                "independent_corroboration": False,
            }
        ],
        "feature_occurrence": {
            "object_id_field": OBJECT_ID_FIELD,
            "object_id": object_id,
            "representation_ref": occurrence_ref,
        },
        "native_parcel_id": account_id,
        "published_identifiers": {
            "account_id": account_id,
            "jurisdiction_code": _clean_text(attributes.get("JURSCODE")),
            "geographic_code": _clean_text(attributes.get("GEOGCODE")),
            "map": _clean_text(attributes.get("MAP")),
            "grid": _clean_text(attributes.get("GRID")),
            "parcel": _clean_text(attributes.get("PARCEL")),
            "plat": _clean_text(attributes.get("PLAT")),
            "plat_liber": _clean_text(attributes.get("PLTLIBER")),
            "plat_folio": _clean_text(attributes.get("PLTFOLIO")),
            "section": _clean_text(attributes.get("SECTION")),
            "block": _clean_text(attributes.get("BLOCK")),
            "lot": _clean_text(attributes.get("LOT")),
            "subdivision_code": _clean_text(attributes.get("SUBDIVSN")),
            "district_subdivision_code": _clean_text(
                attributes.get("DSUBCODE")
            ),
        },
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": county_name,
            "county_geoid": county_geoid,
            "sdat_county_code": county_code,
        },
        "owners": [],
        "owner_visibility": {
            "state": "not_published_in_representation",
            "current_owner_name_field_present": False,
            "owner_mailing_address_field_present": any(
                _clean_text(attributes.get(field_name))
                for field_name in (
                    "OWNADD1",
                    "OWNADD2",
                    "OWNCITY",
                    "OWNSTATE",
                    "OWNERZIP",
                    "OWNZIP2",
                )
            ),
            "mailing_address_establishes_ownership": False,
        },
        "owner_occupancy_code": _clean_text(attributes.get("OOI")),
        "mailing_address": _mailing_address(attributes),
        "situs_address": _situs_address(attributes),
        "location": {
            "published_x": _number(attributes.get("DIGXCORD")),
            "published_y": _number(attributes.get("DIGYCORD")),
            "census_tract_2020": _clean_text(attributes.get("CT2020")),
            "census_block_group_2020": _clean_text(attributes.get("BG2020")),
        },
        "legal_description": legal,
        "deed_reference": {
            "liber": _clean_text(attributes.get("DR1LIBER")),
            "folio": _clean_text(attributes.get("DR1FOLIO")),
            "instrument_copy_in_source": False,
        },
        "plat_reference": {
            "plat": _clean_text(attributes.get("PLAT")),
            "liber": _clean_text(attributes.get("PLTLIBER")),
            "folio": _clean_text(attributes.get("PLTFOLIO")),
        },
        "land_use": {
            "zoning_code": _clean_text(attributes.get("ZONING")),
            "zoning_change_date": _date(attributes.get("ZNCHGDAT")),
            "rezoning_reality_date": _date(attributes.get("RZREALDAT")),
            "land_use_code": _clean_text(attributes.get("LU")),
            "land_use_description": _clean_text(attributes.get("DESCLU")),
            "commercial_industrial_use_code": _clean_text(
                attributes.get("CIUSE")
            ),
            "commercial_industrial_use_description": _clean_text(
                attributes.get("DESCCIUSE")
            ),
            "exemption_class_code": _clean_text(attributes.get("EXCLASS")),
            "exemption_class_description": _clean_text(
                attributes.get("DESCEXCL")
            ),
            "town_code": _clean_text(attributes.get("TOWNCODE")),
            "town_description": _clean_text(attributes.get("DESCTOWN")),
            "subdivision_description": _clean_text(
                attributes.get("DESCSUBD")
            ),
        },
        "land": {
            "acres": _number(attributes.get("ACRES")),
            "area": _number(attributes.get("LANDAREA")),
            "area_unit_code": _clean_text(attributes.get("LUOM")),
            "width": _number(attributes.get("WIDTH")),
            "depth": _number(attributes.get("DEPTH")),
            "public_water_code": _clean_text(attributes.get("PFUW")),
            "public_sewer_code": _clean_text(attributes.get("PFUS")),
            "waterfront_code": _clean_text(attributes.get("PFLW")),
            "paved_street_code": _clean_text(attributes.get("PFSP")),
            "unpaved_street_code": _clean_text(attributes.get("PFSU")),
        },
        "structure": {
            "year_built": _number(attributes.get("YEARBLT")),
            "square_feet": _number(attributes.get("SQFTSTRC")),
            "stories": _number(attributes.get("BLDG_STORY")),
            "units": _number(attributes.get("BLDG_UNITS")),
            "building_type": {
                "code": _clean_text(attributes.get("STRUBLDG")),
                "description": _clean_text(attributes.get("DESCBLDG")),
            },
            "building_style": {
                "code": _clean_text(attributes.get("STRUSTYL")),
                "description": _clean_text(attributes.get("DESCSTYL")),
            },
            "construction": {
                "code": _clean_text(attributes.get("STRUCNST")),
                "description": _clean_text(attributes.get("DESCCNST")),
                "grade_code": _clean_text(attributes.get("STRUGRAD")),
                "grade_description": _clean_text(attributes.get("DESCGRAD")),
            },
            "permit_type_code": _clean_text(attributes.get("PERMITTYP")),
            "last_inspected": _date(attributes.get("LASTINSP")),
            "last_assessed": _date(attributes.get("LASTASSD")),
            "assessor_code": _clean_text(attributes.get("ASSESSOR")),
        },
        "transfer": {
            "transfer_date": _date(attributes.get("TRADATE")),
            "consideration": _number(attributes.get("CONSIDR1")),
            "currency": "USD",
            "conveyance_code": _clean_text(attributes.get("CONVEY1")),
            "grantor_deed_reference": {
                "liber": _clean_text(attributes.get("GR1LIBR1")),
                "folio": _clean_text(attributes.get("GR1FOLO1")),
            },
            "parties_published": False,
        },
        "appraisal": {
            "new_appraised_land_value": _number(
                attributes.get("NFMLNDVL")
            ),
            "new_appraised_improvement_value": _number(
                attributes.get("NFMIMPVL")
            ),
            "new_appraised_full_value": _number(
                attributes.get("NFMTTLVL")
            ),
            "currency": "USD",
        },
        "freshness": {
            "mdp_product_publication_date": _date_observation(
                attributes.get("MDPVDATE")
            ),
            "sdat_linkage_date": _date_observation(
                attributes.get("SDATDATE")
            ),
        },
        "source_links": {
            "sdat_record": _clean_text(attributes.get("SDATWEBADR")),
            "mdp_product": MDP_PRODUCT_URL,
            "related_socrata_representation": SDAT_SOCRATA_URL,
        },
        "source_schema": {
            "schema_fingerprint": contract.schema_fingerprint,
            "object_id_field": contract.object_id_field,
            "geometry_type": contract.geometry_type,
        },
        "source_semantics": {
            "record_grain": "published_arcgis_parcel_point_occurrence",
            "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
            "record_identity_field": ACCOUNT_ID_FIELD,
            "point_representation_not_boundary": True,
            "current_owner_name_published": False,
            "mailing_address_is_ownership_assertion": False,
            "recorded_instrument_copy": False,
            "independent_corroboration_of_related_representation": False,
        },
        "raw_attributes": attributes,
    }
    geometry = feature.get("geometry")
    if geometry_requested and isinstance(geometry, Mapping):
        record["geometry"] = dict(geometry)
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = OUTPUT_CRS
        record["geometry_role"] = "published_parcel_point"
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
) -> MarylandParcelPointsClient:
    limits = access_contract.get("limits") or {}
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return MarylandParcelPointsClient(
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
    county = getattr(args, "county_code", None)
    if county is not None:
        county_code = _county_code(county)
        county_geoid, county_name = COUNTY_GEOIDS[county_code]
        jurisdiction = JurisdictionMetadata(
            jurisdiction_id=county_geoid,
            name=county_name,
            state_code=STATE_CODE,
            county_fips=county_geoid,
            metadata={"sdat_county_code": county_code},
        )
    else:
        jurisdiction = JURISDICTION
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=jurisdiction,
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
        "name": metadata.get("name"),
        "description": metadata.get("description"),
        "copyright": metadata.get("copyrightText"),
        "layer_url": LAYER_URL,
        "contract": contract.to_dict(),
        "identity": {
            "feature_occurrence": OBJECT_ID_FIELD,
            "cross_representation_record": ACCOUNT_ID_FIELD,
            "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
        },
        "traversal": {
            "stable_order": f"{OBJECT_ID_FIELD}_ascending",
            "snapshot_boundary": f"maximum_matching_{OBJECT_ID_FIELD}",
            "pagination": "resultOffset_with_live_maxRecordCount",
            "caller_limit_required": False,
            "exceeded_transfer_limit_checked": True,
        },
        "complements": [
            {
                "source_id": RECORD_IDENTITY_SOURCE_ID,
                "url": SDAT_SOCRATA_URL,
                "relationship": "same_authority_dataset_alternative_representation",
                "exact_join": ACCOUNT_ID_FIELD,
                "independent_corroboration": False,
            }
        ],
        "published_record_link": {
            "field": "SDATWEBADR",
            "role": "interactive_source_record_link",
            "followed_by_adapter": False,
        },
        "owner_field_semantics": {
            "current_owner_name": "not_published_in_representation",
            "mailing_address_fields": [
                "OWNADD1",
                "OWNADD2",
                "OWNCITY",
                "OWNSTATE",
                "OWNERZIP",
                "OWNZIP2",
            ],
            "mailing_address_establishes_ownership": False,
        },
    }


def _probe_record(
    client: MarylandParcelPointsClient,
    metadata: Mapping[str, Any],
    contract: LayerContract,
) -> dict[str, Any]:
    total_count = client.fetch_count("1=1")
    boundary = client.fetch_boundary("1=1")
    sample_page = (
        client.fetch_page(
            where=_bounded_where("1=1", boundary),
            offset=0,
            record_count=1,
            return_geometry=True,
        )
        if boundary is not None
        else FeaturePage(features=(), exceeded_transfer_limit=False)
    )
    sample = None
    if sample_page.features:
        attributes = _attributes(sample_page.features[0])
        sample = {
            "object_id": _feature_object_id(sample_page.features[0]),
            "account_id": attributes.get(ACCOUNT_ID_FIELD),
            "jurisdiction_code": attributes.get("JURSCODE"),
            "mdp_product_date": attributes.get("MDPVDATE"),
            "sdat_linkage_date": attributes.get("SDATDATE"),
        }
    return {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "schema_fingerprint": contract.schema_fingerprint,
        "stable_contract": {
            "name": metadata.get("name"),
            "layer_url": LAYER_URL,
            **contract.to_dict(),
        },
        "rolling_observations": {
            "feature_count": total_count,
            "maximum_object_id": boundary,
            "sample": sample,
            "sample_exceeded_transfer_limit": (
                sample_page.exceeded_transfer_limit
            ),
        },
    }


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    client: MarylandParcelPointsClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one catalog-aware MD iMAP Parcel Points query."""

    query = build_query(args)
    try:
        decision = (
            access_contract if access_contract is not None else _access_contract(args)
        )
        active_client = client or _client(args, decision)
        if args.command in {"metadata", "discovery", "probe"}:
            metadata = active_client.fetch_metadata()
            contract = metadata_contract(metadata)
            record = (
                _probe_record(active_client, metadata, contract)
                if args.command == "probe"
                else _metadata_record(metadata, contract)
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
                warnings = list(SOURCE_WARNINGS)
                if batch.transfer_limit_pages:
                    warnings.append(
                        "ArcGIS marked one or more complete pages with "
                        "exceededTransferLimit; traversal continued within "
                        "the validated count and OBJECTID boundary."
                    )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=batch.next_cursor,
                    warnings=warnings,
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
    except CatalogError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_unavailable",
                    message=str(error),
                    category="catalog",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    except MarylandParcelPointsError as error:
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
                    code="maryland_parcel_points_normalization_failed",
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
        summary=(
            f"Maryland MD iMAP Parcel Points {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    print(
        f"Maryland Parcel Points {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("native_parcel_id")
            or record.get("representation_ref")
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
            help="Return the published point transformed to EPSG:4326",
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


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--county-code",
        help="Two-digit Maryland SDAT county code, 01 through 24",
    )
    parser.add_argument("--map", dest="map_number")
    parser.add_argument("--plat")
    parser.add_argument("--grid")
    parser.add_argument("--land-use")
    parser.add_argument("--zoning")


def _add_match(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--match",
        choices=("exact", "prefix", "contains"),
        default="contains",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Maryland's official MD iMAP Parcel Points representation"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("metadata", "discovery", "probe"):
        command_parser = subparsers.add_parser(command)
        _add_runtime_arguments(command_parser)

    list_parser = subparsers.add_parser("list")
    _add_filters(list_parser)
    _add_runtime_arguments(list_parser, records=True)

    count_parser = subparsers.add_parser(
        "count",
        help="Count a combined parcel-account, address, or classification query",
    )
    count_parser.add_argument("--account")
    count_parser.add_argument("--parcel")
    count_parser.add_argument("--address")
    _add_match(count_parser)
    _add_filters(count_parser)
    _add_runtime_arguments(count_parser)

    query_parser = subparsers.add_parser(
        "query",
        help="Combine parcel-account, address, and classification filters",
    )
    query_parser.add_argument("--account")
    query_parser.add_argument("--parcel")
    query_parser.add_argument("--address")
    _add_match(query_parser)
    _add_filters(query_parser)
    _add_runtime_arguments(query_parser, records=True)

    account_parser = subparsers.add_parser(
        "account",
        help="Match ACCTID exactly",
    )
    account_parser.add_argument("selector")
    _add_filters(account_parser)
    _add_runtime_arguments(account_parser, records=True)

    parcel_parser = subparsers.add_parser(
        "parcel",
        help="Match the published local PARCEL field exactly",
    )
    parcel_parser.add_argument("selector")
    _add_filters(parcel_parser)
    _add_runtime_arguments(parcel_parser, records=True)

    address_parser = subparsers.add_parser(
        "address",
        help="Search the published ADDRESS field",
    )
    address_parser.add_argument("selector")
    _add_match(address_parser)
    _add_filters(address_parser)
    _add_runtime_arguments(address_parser, records=True)

    objectid_parser = subparsers.add_parser(
        "objectid",
        help="Match one ArcGIS feature occurrence",
    )
    objectid_parser.add_argument("objectid", type=_nonnegative_int)
    _add_runtime_arguments(objectid_parser, records=True)

    point_parser = subparsers.add_parser("point")
    point_parser.add_argument("longitude", type=float)
    point_parser.add_argument("latitude", type=float)
    _add_filters(point_parser)
    _add_runtime_arguments(point_parser, records=True)

    bbox_parser = subparsers.add_parser("bbox")
    bbox_parser.add_argument("west", type=float)
    bbox_parser.add_argument("south", type=float)
    bbox_parser.add_argument("east", type=float)
    bbox_parser.add_argument("north", type=float)
    _add_filters(bbox_parser)
    _add_runtime_arguments(bbox_parser, records=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
