#!/usr/bin/env python3
"""Query Washington's official normalized statewide parcel representations.

The Washington State Parcels Project is published through several official
ArcGIS representations with one shared state/county lineage:

* Ecology hosted FeatureServer: default query surface plus county freshness
  and county-specific land-use lookup tables.
* DNR public MapServer: current public mirror of the normalized parcel layer.
* DAHP/WISAARD MapServer: optional parity surface that may reflect an older
  snapshot.

The live normalized schemas publish parcel identifiers, situs fields, land-use
codes, assessed land/building values, county assessor ``DATA_LINK`` routes, and
geometry. They currently publish no owner or taxpayer fields.

Usage:
    uv run python tools/query_washington_parcels.py metadata
    uv run python tools/query_washington_parcels.py count --county King
    uv run python tools/query_washington_parcels.py search 2038010000001 \
        --field parcel
    uv run python tools/query_washington_parcels.py point -117.97 47.255
    uv run python tools/query_washington_parcels.py bbox \
        -117.983 47.250 -117.960 47.261
    uv run python tools/query_washington_parcels.py county-freshness
    uv run python tools/query_washington_parcels.py land-use-codes \
        --county Clark --code 11-10
    uv run python tools/query_washington_parcels.py parity --include-wisaard
    uv run python tools/query_washington_parcels.py probe --operation all
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

try:
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
        schema_fingerprint,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
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
        schema_fingerprint,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "WA"
STATE_FIPS = "53"
LINEAGE_ID = "us-wa-state-parcels-normalized"
CURSOR_PREFIX = "washington-parcels:v1:"
CURSOR_VERSION = 1
SENTINEL_PARCEL_ID = "001-2038010000001"
SENTINEL_ORIGINAL_ID = "2038010000001"

ECOLOGY_SOURCE_ID = "us-wa-current-parcels-ecology"
DNR_SOURCE_ID = "us-wa-current-parcels-dnr"
WISAARD_SOURCE_ID = "us-wa-current-parcels-wisaard"
FRESHNESS_SOURCE_ID = "us-wa-current-parcels-county-freshness"
LAND_USE_SOURCE_ID = "us-wa-current-parcels-county-land-use"

ECOLOGY_SERVICE_URL = (
    "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/"
    "Current_Parcels/FeatureServer"
)
ECOLOGY_LAYER_URL = f"{ECOLOGY_SERVICE_URL}/0"
FRESHNESS_TABLE_URL = f"{ECOLOGY_SERVICE_URL}/1"
LAND_USE_TABLE_URL = f"{ECOLOGY_SERVICE_URL}/2"
DNR_LAYER_URL = (
    "https://gis.dnr.wa.gov/site2/rest/services/Public_Forest_Practices/"
    "WADNR_PUBLIC_OCIO_Parcels/MapServer/0"
)
WISAARD_LAYER_URL = (
    "https://wisaard.dahp.wa.gov/server/rest/services/"
    "County_Parcels/MapServer/0"
)

COMMON_REQUIRED_FIELDS = (
    "OBJECTID",
    "FIPS_NR",
    "COUNTY_NM",
    "PARCEL_ID_NR",
    "ORIG_PARCEL_ID",
    "SITUS_ADDRESS",
    "SUB_ADDRESS",
    "SITUS_CITY_NM",
    "SITUS_ZIP_NR",
    "LANDUSE_CD",
    "VALUE_LAND",
    "VALUE_BLDG",
    "DATA_LINK",
)
OWNER_FIELD_MARKERS = (
    "OWNER",
    "OWNR",
    "TAXPAYER",
    "TAX_PAYER",
    "MAIL_ADD",
    "MAILING",
)

WASHINGTON_COUNTY_FIPS = {
    "Adams": "001",
    "Asotin": "003",
    "Benton": "005",
    "Chelan": "007",
    "Clallam": "009",
    "Clark": "011",
    "Columbia": "013",
    "Cowlitz": "015",
    "Douglas": "017",
    "Ferry": "019",
    "Franklin": "021",
    "Garfield": "023",
    "Grant": "025",
    "Grays Harbor": "027",
    "Island": "029",
    "Jefferson": "031",
    "King": "033",
    "Kitsap": "035",
    "Kittitas": "037",
    "Klickitat": "039",
    "Lewis": "041",
    "Lincoln": "043",
    "Mason": "045",
    "Okanogan": "047",
    "Pacific": "049",
    "Pend Oreille": "051",
    "Pierce": "053",
    "San Juan": "055",
    "Skagit": "057",
    "Skamania": "059",
    "Snohomish": "061",
    "Spokane": "063",
    "Stevens": "065",
    "Thurston": "067",
    "Wahkiakum": "069",
    "Walla Walla": "071",
    "Whatcom": "073",
    "Whitman": "075",
    "Yakima": "077",
}


@dataclass(frozen=True)
class CountyInfo:
    """Canonical county identity and statewide parcel selectors."""

    name: str
    fips: str

    @property
    def geoid(self) -> str:
        return f"{STATE_FIPS}{self.fips}"

    @property
    def coded_value(self) -> str:
        return str(int(self.fips))


COUNTIES_BY_FIPS = {
    fips: CountyInfo(name=name, fips=fips)
    for name, fips in WASHINGTON_COUNTY_FIPS.items()
}


def _county_key(value: Any) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


COUNTIES_BY_KEY = {
    _county_key(info.name): info for info in COUNTIES_BY_FIPS.values()
}


@dataclass(frozen=True)
class Representation:
    """One official representation of the shared normalized parcel lineage."""

    key: str
    source_id: str
    name: str
    layer_url: str
    dataset_id: str
    publisher: str
    role: str
    max_page_size: int
    county_value_style: str
    has_feature_file_date: bool
    has_original_land_use: bool

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role="statewide_assessment_parcel_geometry_routing",
            base_url=self.layer_url,
            dataset_id=self.dataset_id,
            metadata={
                "authority": "State of Washington",
                "publisher": self.publisher,
                "coverage": "39 Washington counties",
                "representation": self.key,
                "representation_role": self.role,
                "lineage_id": LINEAGE_ID,
                "lineage_relationship": "same_normalized_state_county_dataset",
                "owner_name_state": "observed_from_live_schema",
                "county_detail_link_field": "DATA_LINK",
                "county_detail_route_role": (
                    "assessor_tax_and_owner_enrichment"
                ),
            },
        )


ECOLOGY = Representation(
    key="ecology",
    source_id=ECOLOGY_SOURCE_ID,
    name="Washington Current Parcels — Ecology hosted",
    layer_url=ECOLOGY_LAYER_URL,
    dataset_id="2b603a599a0842a3b2284c04c8927f35/layer-0",
    publisher="Washington Technology Solutions / Department of Ecology",
    role="default",
    max_page_size=2_000,
    county_value_style="code",
    has_feature_file_date=False,
    has_original_land_use=True,
)
DNR = Representation(
    key="dnr",
    source_id=DNR_SOURCE_ID,
    name="Washington Current Parcels — DNR public mirror",
    layer_url=DNR_LAYER_URL,
    dataset_id="d935d2ece44c4bc4a5e3360537574a21/layer-0",
    publisher="Washington Department of Natural Resources / WaTech",
    role="public_mirror",
    max_page_size=1_000,
    county_value_style="code",
    has_feature_file_date=True,
    has_original_land_use=True,
)
WISAARD = Representation(
    key="wisaard",
    source_id=WISAARD_SOURCE_ID,
    name="Washington Current Parcels — DAHP/WISAARD parity",
    layer_url=WISAARD_LAYER_URL,
    dataset_id="cd9652e4621142e09ee8df67ec803c05/layer-0",
    publisher="Washington Department of Archaeology and Historic Preservation",
    role="optional_parity",
    max_page_size=2_000,
    county_value_style="name",
    has_feature_file_date=True,
    has_original_land_use=False,
)
REPRESENTATIONS = {
    representation.key: representation
    for representation in (ECOLOGY, DNR, WISAARD)
}

FRESHNESS_METADATA = SourceMetadata(
    source_id=FRESHNESS_SOURCE_ID,
    name="Washington Current Parcels county file dates",
    source_role="parcel_county_freshness",
    base_url=FRESHNESS_TABLE_URL,
    dataset_id="Current_Parcels/FeatureServer/1",
    metadata={
        "authority": "State of Washington",
        "lineage_id": LINEAGE_ID,
        "join_key": "COUNTY_NM",
        "expected_counties": 39,
    },
)
LAND_USE_METADATA = SourceMetadata(
    source_id=LAND_USE_SOURCE_ID,
    name="Washington county-specific parcel land-use codes",
    source_role="parcel_land_use_lookup",
    base_url=LAND_USE_TABLE_URL,
    dataset_id="Current_Parcels/FeatureServer/2",
    metadata={
        "authority": "State of Washington",
        "lineage_id": LINEAGE_ID,
        "join_key": ["COUNTY_NM", "CODE"],
    },
)
LINEAGE_METADATA = SourceMetadata(
    source_id=LINEAGE_ID,
    name="Washington State normalized parcel lineage",
    source_role="parcel_mirror_health",
    base_url=ECOLOGY_LAYER_URL,
    dataset_id="Washington State Parcels Project",
    metadata={
        "authority": "State of Washington and Washington counties",
        "representations": sorted(REPRESENTATIONS),
        "parity_interpretation": "mirror_health_not_corroboration",
    },
)
STATE_JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-wa",
    name="Washington",
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS},
)


class WashingtonParcelSelectionError(ValueError):
    """Invalid source selection or query input."""

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
            category="query",
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class CursorState:
    """Query-bound deterministic ArcGIS continuation state."""

    query_fingerprint: str
    representation: str
    offset: int
    anchor_object_id: int
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class QuerySpec:
    """ArcGIS attribute and spatial query."""

    where: str
    geometry_parameters: Mapping[str, Any]
    return_geometry: bool
    county: CountyInfo | None = None


@dataclass(frozen=True)
class ArcGISBatch:
    """A deterministic page traversal plus snapshot diagnostics."""

    features: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any]
    schema_fingerprint: str
    total_count: int
    pages_fetched: int
    next_cursor: str | None
    warnings: tuple[str, ...] = ()


class WashingtonArcGISClient(ArcGISRESTClient):
    """ArcGIS client with explicit metadata, count, and ordered-page methods."""

    def __init__(
        self,
        layer_url: str,
        *,
        page_size: int,
        max_page_size: int,
        timeout: float,
        minimum_interval: float,
        retry_attempts: int,
        transport: Any = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "page_size": min(page_size, max_page_size),
            "timeout": timeout,
            "minimum_interval": minimum_interval,
            "retry_policy": RetryPolicy(max_attempts=retry_attempts),
        }
        if transport is not None:
            kwargs["transport"] = transport
        super().__init__(layer_url, **kwargs)
        self.maximum_page_size = max_page_size

    @staticmethod
    def _mapping_payload(
        payload: Any,
        *,
        url: str,
        operation: str,
    ) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                f"ArcGIS {operation} response must be a JSON object",
                url=url,
                details={"response_type": type(payload).__name__},
            )
        if "error" in payload:
            raise SourceResponseError(
                f"ArcGIS returned an error during {operation}",
                url=url,
                details={"response": payload.get("error")},
            )
        return payload

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        return self._mapping_payload(
            payload,
            url=self.layer_url,
            operation="metadata",
        )

    def fetch_count(
        self,
        where: str,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                **dict(parameters or {}),
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        data = self._mapping_payload(
            payload,
            url=self.query_url,
            operation="count",
        )
        count = data.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "ArcGIS count response lacks a non-negative integer count",
                url=self.query_url,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        offset: int,
        record_count: int,
        out_fields: str = "*",
        return_geometry: bool,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            **dict(parameters or {}),
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "resultOffset": offset,
            "resultRecordCount": record_count,
            "orderByFields": "OBJECTID ASC",
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._request_json(self.query_url, params=params)
        data = self._mapping_payload(
            payload,
            url=self.query_url,
            operation="record query",
        )
        features = data.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "ArcGIS record response is missing a features array",
                url=self.query_url,
            )
        if any(not isinstance(feature, Mapping) for feature in features):
            raise SourceSchemaError(
                "ArcGIS features array contains a non-object feature",
                url=self.query_url,
            )
        return tuple(features)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _longitude(value: str) -> float:
    parsed = float(value)
    if not -180 <= parsed <= 180:
        raise argparse.ArgumentTypeError("longitude must be between -180 and 180")
    return parsed


def _latitude(value: str) -> float:
    parsed = float(value)
    if not -90 <= parsed <= 90:
        raise argparse.ArgumentTypeError("latitude must be between -90 and 90")
    return parsed


def _representation(value: str) -> Representation:
    try:
        return REPRESENTATIONS[value]
    except KeyError as error:
        raise WashingtonParcelSelectionError(
            "unknown_representation",
            f"unknown Washington parcel representation: {value}",
            details={"known_representations": sorted(REPRESENTATIONS)},
        ) from error


def _resolve_county(value: Any) -> CountyInfo:
    text = str(value or "").strip()
    if not text:
        raise WashingtonParcelSelectionError(
            "blank_county",
            "county must not be blank",
        )
    digits = text
    if digits.startswith(STATE_FIPS) and len(digits) == 5:
        digits = digits[2:]
    if digits.isdigit():
        digits = digits.zfill(3)
        county = COUNTIES_BY_FIPS.get(digits)
    else:
        county = COUNTIES_BY_KEY.get(_county_key(text))
    if county is None:
        raise WashingtonParcelSelectionError(
            "unknown_county",
            f"unknown Washington county: {value}",
            details={"known_counties": sorted(WASHINGTON_COUNTY_FIPS)},
        )
    return county


def _clean_text(value: Any, field_name: str) -> str:
    cleaned = " ".join(str(value or "").replace("\x00", "").split()).strip()
    if not cleaned:
        raise WashingtonParcelSelectionError(
            "blank_query",
            f"{field_name} must not be blank",
        )
    return cleaned


def _sql_literal(value: Any, field_name: str) -> str:
    return _clean_text(value, field_name).replace("'", "''")


def _county_native_value(
    representation: Representation,
    county: CountyInfo,
) -> str:
    if representation.county_value_style == "code":
        return county.coded_value
    return county.name


def _county_expression(
    representation: Representation,
    county: CountyInfo,
) -> str:
    native = _sql_literal(
        _county_native_value(representation, county),
        "county",
    )
    return f"COUNTY_NM='{native}'"


def _fips_expression(value: Any) -> str:
    county = _resolve_county(value)
    return f"FIPS_NR='{county.fips}'"


def _situs_expression(value: Any) -> str:
    term = _sql_literal(value, "situs")
    return "(" + " OR ".join(
        f"{field_name} LIKE '%{term}%'"
        for field_name in (
            "SITUS_ADDRESS",
            "SUB_ADDRESS",
            "SITUS_CITY_NM",
            "SITUS_ZIP_NR",
        )
    ) + ")"


def _parcel_expression(value: Any) -> str:
    term = _sql_literal(value, "parcel identifier")
    return (
        f"(PARCEL_ID_NR='{term}' OR ORIG_PARCEL_ID='{term}')"
    )


def _search_expression(
    representation: Representation,
    field: str,
    value: Any,
) -> tuple[str, CountyInfo | None]:
    if field == "parcel":
        return _parcel_expression(value), None
    if field == "parcel-id":
        term = _sql_literal(value, "parcel identifier")
        return f"PARCEL_ID_NR='{term}'", None
    if field == "original-parcel-id":
        term = _sql_literal(value, "original parcel identifier")
        return f"ORIG_PARCEL_ID='{term}'", None
    if field == "county":
        county = _resolve_county(value)
        return _county_expression(representation, county), county
    if field == "fips":
        county = _resolve_county(value)
        return f"FIPS_NR='{county.fips}'", county
    if field == "situs":
        return _situs_expression(value), None
    if field == "land-use":
        try:
            code = int(value)
        except (TypeError, ValueError) as error:
            raise WashingtonParcelSelectionError(
                "invalid_land_use",
                "DOR land-use code must be an integer",
            ) from error
        return f"LANDUSE_CD={code}", None
    if field == "original-land-use":
        if not representation.has_original_land_use:
            raise WashingtonParcelSelectionError(
                "field_not_published",
                (
                    f"{representation.key} does not publish "
                    "ORIG_LANDUSE_CD in its normalized layer"
                ),
                details={"representation": representation.key},
            )
        code = _sql_literal(value, "original land-use code")
        return f"ORIG_LANDUSE_CD='{code}'", None
    if field == "auto":
        term = _sql_literal(value, "search term")
        return (
            "("
            f"PARCEL_ID_NR='{term}' OR "
            f"ORIG_PARCEL_ID='{term}' OR "
            f"SITUS_ADDRESS LIKE '%{term}%' OR "
            f"SUB_ADDRESS LIKE '%{term}%' OR "
            f"SITUS_CITY_NM LIKE '%{term}%' OR "
            f"SITUS_ZIP_NR LIKE '%{term}%'"
            ")",
            None,
        )
    raise WashingtonParcelSelectionError(
        "unknown_search_field",
        f"unknown Washington parcel search field: {field}",
    )


def _common_filter_expressions(
    args: argparse.Namespace,
    representation: Representation,
) -> tuple[list[str], CountyInfo | None]:
    expressions: list[str] = []
    selected_county: CountyInfo | None = None
    if getattr(args, "county", None):
        selected_county = _resolve_county(args.county)
        expressions.append(_county_expression(representation, selected_county))
    if getattr(args, "fips", None):
        fips_county = _resolve_county(args.fips)
        if selected_county is not None and selected_county != fips_county:
            raise WashingtonParcelSelectionError(
                "conflicting_county_filters",
                "--county and --fips select different counties",
            )
        selected_county = fips_county
        expressions.append(f"FIPS_NR='{fips_county.fips}'")
    if getattr(args, "parcel_id", None):
        term = _sql_literal(args.parcel_id, "parcel identifier")
        expressions.append(f"PARCEL_ID_NR='{term}'")
    if getattr(args, "original_parcel_id", None):
        term = _sql_literal(
            args.original_parcel_id,
            "original parcel identifier",
        )
        expressions.append(f"ORIG_PARCEL_ID='{term}'")
    if getattr(args, "situs", None):
        expressions.append(_situs_expression(args.situs))
    if getattr(args, "land_use", None) is not None:
        expressions.append(f"LANDUSE_CD={int(args.land_use)}")
    if getattr(args, "original_land_use", None):
        if not representation.has_original_land_use:
            raise WashingtonParcelSelectionError(
                "field_not_published",
                (
                    f"{representation.key} does not publish "
                    "ORIG_LANDUSE_CD in its normalized layer"
                ),
                details={"representation": representation.key},
            )
        code = _sql_literal(args.original_land_use, "original land-use code")
        expressions.append(f"ORIG_LANDUSE_CD='{code}'")
    return expressions, selected_county


def _query_spec(
    args: argparse.Namespace,
    representation: Representation,
) -> QuerySpec:
    expressions, selected_county = _common_filter_expressions(
        args,
        representation,
    )
    if args.command == "search":
        expression, field_county = _search_expression(
            representation,
            args.field,
            args.query,
        )
        expressions.insert(0, expression)
        if field_county is not None:
            if selected_county is not None and selected_county != field_county:
                raise WashingtonParcelSelectionError(
                    "conflicting_county_filters",
                    "search term and --county select different counties",
                )
            selected_county = field_county

    geometry_parameters: dict[str, Any] = {}
    return_geometry = bool(getattr(args, "geometry", False))
    if args.command == "point":
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
            raise WashingtonParcelSelectionError(
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
        where=" AND ".join(f"({item})" for item in expressions) or "1=1",
        geometry_parameters=geometry_parameters,
        return_geometry=return_geometry,
        county=selected_county,
    )


def _field_definitions(metadata: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "ArcGIS metadata lacks a valid fields array",
            url="layer-metadata",
        )
    return tuple(fields)


def _owner_fields(field_names: Iterable[str]) -> list[str]:
    return sorted(
        field_name
        for field_name in field_names
        if any(marker in field_name.upper() for marker in OWNER_FIELD_MARKERS)
    )


def _metadata_contract(
    representation: Representation,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    fields = _field_definitions(metadata)
    field_names = [str(field.get("name") or "") for field in fields]
    field_set = set(field_names)
    required = list(COMMON_REQUIRED_FIELDS)
    if representation.has_original_land_use:
        required.append("ORIG_LANDUSE_CD")
    missing = sorted(set(required) - field_set)
    if missing:
        raise SourceSchemaError(
            "Washington parcel layer is missing required fields",
            url=representation.layer_url,
            details={
                "representation": representation.key,
                "missing_fields": missing,
            },
        )
    geometry_type = metadata.get("geometryType")
    if geometry_type != "esriGeometryPolygon":
        raise SourceSchemaError(
            "Washington parcel layer is not a polygon layer",
            url=representation.layer_url,
            details={"geometry_type": geometry_type},
        )
    server_max = metadata.get("maxRecordCount")
    if isinstance(server_max, bool) or not isinstance(server_max, int) or server_max <= 0:
        raise SourceSchemaError(
            "Washington parcel metadata lacks maxRecordCount",
            url=representation.layer_url,
        )
    capabilities = metadata.get("advancedQueryCapabilities")
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    declared = arcgis_declared_schema(fields)
    detected = _owner_fields(field_names)
    return {
        "schema_fingerprint": schema_fingerprint(declared),
        "field_names": field_names,
        "missing_required_fields": missing,
        "owner_fields_detected": detected,
        "owner_name_state": (
            "published_in_live_schema"
            if detected
            else "not_published_by_normalized_statewide_layer"
        ),
        "geometry_type": geometry_type,
        "spatial_reference": metadata.get("spatialReference"),
        "max_record_count": min(server_max, representation.max_page_size),
        "service_max_record_count": server_max,
        "supports_pagination": bool(capabilities.get("supportsPagination")),
        "supports_order_by": bool(capabilities.get("supportsOrderBy")),
        "supports_statistics": bool(
            metadata.get("supportsStatistics")
            or capabilities.get("supportsStatistics")
        ),
        "layer_name": metadata.get("name"),
        "service_item_id": metadata.get("serviceItemId"),
    }


def _dor_land_use_domain(metadata: Mapping[str, Any]) -> dict[int, str]:
    for field in _field_definitions(metadata):
        if field.get("name") != "LANDUSE_CD":
            continue
        domain = field.get("domain")
        if not isinstance(domain, Mapping):
            return {}
        values = domain.get("codedValues")
        if not isinstance(values, list):
            return {}
        result: dict[int, str] = {}
        for value in values:
            if not isinstance(value, Mapping):
                continue
            code = value.get("code")
            name = value.get("name")
            if isinstance(code, int) and isinstance(name, str):
                result[code] = name
        return result
    return {}


def _feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "Washington parcel feature lacks attributes",
            url="source-feature",
        )
    return attributes


def _object_id(feature: Mapping[str, Any]) -> int:
    value = _feature_attributes(feature).get("OBJECTID")
    if isinstance(value, bool):
        raise SourceSchemaError(
            "Washington parcel OBJECTID must be an integer",
            url="source-feature",
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "Washington parcel feature lacks a usable OBJECTID",
            url="source-feature",
            details={"value": value},
        ) from error
    if parsed <= 0:
        raise SourceSchemaError(
            "Washington parcel OBJECTID must be positive",
            url="source-feature",
            details={"value": parsed},
        )
    return parsed


def _cursor_criteria_fingerprint(
    representation: Representation,
    *,
    operation: str,
    spec: QuerySpec,
) -> str:
    return sha256_fingerprint(
        {
            "version": CURSOR_VERSION,
            "representation": representation.key,
            "operation": operation,
            "where": spec.where,
            "geometry_parameters": dict(spec.geometry_parameters),
            "return_geometry": spec.return_geometry,
            "order_by": "OBJECTID ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "query_fingerprint": state.query_fingerprint,
        "representation": state.representation,
        "offset": state.offset,
        "anchor_object_id": state.anchor_object_id,
        "total_count": state.total_count,
        "schema_fingerprint": state.schema_fingerprint,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(
    value: str | None,
    *,
    expected_query_fingerprint: str,
    expected_representation: str,
) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise WashingtonParcelSelectionError(
            "invalid_cursor",
            "cursor has an unknown Washington parcel format",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WashingtonParcelSelectionError(
            "invalid_cursor",
            "cursor is not valid encoded JSON",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != CURSOR_VERSION:
        raise WashingtonParcelSelectionError(
            "invalid_cursor",
            "cursor version is not supported",
        )
    if payload.get("query_fingerprint") != expected_query_fingerprint:
        raise WashingtonParcelSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to a different Washington parcel query",
        )
    if payload.get("representation") != expected_representation:
        raise WashingtonParcelSelectionError(
            "cursor_representation_mismatch",
            "cursor belongs to a different parcel representation",
        )
    try:
        state = CursorState(
            query_fingerprint=str(payload["query_fingerprint"]),
            representation=str(payload["representation"]),
            offset=int(payload["offset"]),
            anchor_object_id=int(payload["anchor_object_id"]),
            total_count=int(payload["total_count"]),
            schema_fingerprint=str(payload["schema_fingerprint"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WashingtonParcelSelectionError(
            "invalid_cursor",
            "cursor lacks required continuation fields",
        ) from error
    if (
        state.offset <= 0
        or state.anchor_object_id <= 0
        or state.total_count < state.offset
        or not state.schema_fingerprint
    ):
        raise WashingtonParcelSelectionError(
            "invalid_cursor",
            "cursor continuation values are invalid",
        )
    return state


def _fetch_batch(
    client: Any,
    representation: Representation,
    *,
    operation: str,
    spec: QuerySpec,
    limit: int,
    cursor: str | None,
) -> ArcGISBatch:
    metadata = client.fetch_metadata()
    contract = _metadata_contract(representation, metadata)
    query_fingerprint = _cursor_criteria_fingerprint(
        representation,
        operation=operation,
        spec=spec,
    )
    cursor_state = _decode_cursor(
        cursor,
        expected_query_fingerprint=query_fingerprint,
        expected_representation=representation.key,
    )
    if (
        cursor_state is not None
        and cursor_state.schema_fingerprint != contract["schema_fingerprint"]
    ):
        raise WashingtonParcelSelectionError(
            "cursor_schema_mismatch",
            "parcel schema changed since the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
        )

    total_count = client.fetch_count(
        spec.where,
        parameters=spec.geometry_parameters,
    )
    offset = cursor_state.offset if cursor_state is not None else 0
    if offset > total_count:
        raise WashingtonParcelSelectionError(
            "cursor_out_of_range",
            "cursor offset exceeds the current source count",
            details={"offset": offset, "count": total_count},
        )

    warnings: list[str] = []
    previous_object_id: int | None = None
    if cursor_state is not None:
        boundary = client.fetch_page(
            where=spec.where,
            offset=offset - 1,
            record_count=1,
            out_fields="OBJECTID",
            return_geometry=False,
            parameters=spec.geometry_parameters,
        )
        if len(boundary) != 1:
            raise PaginationError(
                "Washington parcel continuation boundary is missing",
                url=representation.layer_url,
                details={"offset": offset},
            )
        observed_anchor = _object_id(boundary[0])
        if observed_anchor != cursor_state.anchor_object_id:
            raise PaginationError(
                "Washington parcel ordering changed at the cursor boundary",
                url=representation.layer_url,
                details={
                    "expected_anchor": cursor_state.anchor_object_id,
                    "observed_anchor": observed_anchor,
                },
            )
        previous_object_id = observed_anchor
        if cursor_state.total_count != total_count:
            warnings.append(
                "Source count changed since the cursor was issued; the "
                "OBJECTID boundary still matched."
            )

    page_size = min(
        int(getattr(client, "page_size", representation.max_page_size)),
        int(contract["max_record_count"]),
    )
    features: list[Mapping[str, Any]] = []
    pages_fetched = 0
    while len(features) < limit and offset < total_count:
        record_count = min(page_size, limit - len(features), total_count - offset)
        page = client.fetch_page(
            where=spec.where,
            offset=offset,
            record_count=record_count,
            return_geometry=spec.return_geometry,
            parameters=spec.geometry_parameters,
        )
        pages_fetched += 1
        if not page:
            raise PaginationError(
                "Washington parcel query ended before its reported count",
                url=representation.layer_url,
                details={"offset": offset, "count": total_count},
            )
        page_object_ids = [_object_id(feature) for feature in page]
        if page_object_ids != sorted(page_object_ids) or len(page_object_ids) != len(
            set(page_object_ids)
        ):
            raise PaginationError(
                "Washington parcel page is not strictly ordered by OBJECTID",
                url=representation.layer_url,
                details={"offset": offset},
            )
        if (
            previous_object_id is not None
            and page_object_ids[0] <= previous_object_id
        ):
            raise PaginationError(
                "Washington parcel pages overlap or regress",
                url=representation.layer_url,
                details={
                    "previous_object_id": previous_object_id,
                    "next_object_id": page_object_ids[0],
                },
            )
        features.extend(page)
        offset += len(page)
        previous_object_id = page_object_ids[-1]
        if len(page) < record_count and offset < total_count:
            raise PaginationError(
                "Washington parcel page was short before the reported count",
                url=representation.layer_url,
                details={
                    "offset": offset,
                    "returned": len(page),
                    "requested": record_count,
                    "count": total_count,
                },
            )

    next_cursor = None
    if offset < total_count and previous_object_id is not None:
        next_cursor = _encode_cursor(
            CursorState(
                query_fingerprint=query_fingerprint,
                representation=representation.key,
                offset=offset,
                anchor_object_id=previous_object_id,
                total_count=total_count,
                schema_fingerprint=str(contract["schema_fingerprint"]),
            )
        )
    return ArcGISBatch(
        features=tuple(features),
        metadata=metadata,
        schema_fingerprint=str(contract["schema_fingerprint"]),
        total_count=total_count,
        pages_fetched=pages_fetched,
        next_cursor=next_cursor,
        warnings=tuple(warnings),
    )


def _arcgis_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1_000, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (OSError, OverflowError, ValueError):
            pass
    return str(value).strip() or None


def _case_insensitive_value(
    attributes: Mapping[str, Any],
    *field_names: str,
) -> Any:
    by_key = {str(key).casefold(): value for key, value in attributes.items()}
    for field_name in field_names:
        key = field_name.casefold()
        if key in by_key:
            return by_key[key]
    return None


def _county_from_attributes(attributes: Mapping[str, Any]) -> CountyInfo:
    fips_value = str(attributes.get("FIPS_NR") or "").strip()
    if fips_value.isdigit():
        county = COUNTIES_BY_FIPS.get(fips_value.zfill(3))
        if county is not None:
            return county
    native = str(attributes.get("COUNTY_NM") or "").strip()
    if native:
        try:
            return _resolve_county(native)
        except WashingtonParcelSelectionError:
            pass
    raise SourceSchemaError(
        "Washington parcel feature lacks a recognized county",
        url="source-feature",
        details={
            "FIPS_NR": attributes.get("FIPS_NR"),
            "COUNTY_NM": attributes.get("COUNTY_NM"),
        },
    )


def _route_family(host: str) -> str:
    normalized = host.casefold()
    if "publicaccessnow.com" in normalized:
        return "taxsifter_publicaccessnow"
    if "taxsifter" in normalized or "mapsifter" in normalized:
        return "taxsifter_mapsifter"
    if "geocortex" in normalized or "vertigis" in normalized:
        return "geocortex_vertigis"
    return "county_specific"


def _county_assessor_route(value: Any) -> dict[str, Any] | None:
    url = str(value or "").strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {
            "kind": "county_assessor_detail",
            "url": url,
            "host": None,
            "vendor_family": "unclassified",
            "discovered_from": "DATA_LINK",
        }
    return {
        "kind": "county_assessor_detail",
        "url": url,
        "host": parsed.netloc.casefold(),
        "vendor_family": _route_family(parsed.netloc),
        "discovered_from": "DATA_LINK",
        "adds": [
            "owner_or_taxpayer",
            "mailing_address",
            "tax_and_exemption_detail",
            "sales_or_permit_detail_when_published",
        ],
    }


def _table_rows(
    client: Any,
    *,
    where: str = "1=1",
    limit: int | None = None,
) -> tuple[Mapping[str, Any], ...]:
    metadata = client.fetch_metadata()
    fields = _field_definitions(metadata)
    field_names = {str(field.get("name") or "") for field in fields}
    if "OBJECTID" not in field_names:
        raise SourceSchemaError(
            "Washington parcel companion table lacks OBJECTID",
            url=str(getattr(client, "layer_url", "companion-table")),
        )
    count = client.fetch_count(where)
    target = count if limit is None else min(count, limit)
    page_size = min(
        int(getattr(client, "page_size", 2_000)),
        int(metadata.get("maxRecordCount") or 2_000),
    )
    offset = 0
    rows: list[Mapping[str, Any]] = []
    previous_object_id: int | None = None
    while offset < target:
        page = client.fetch_page(
            where=where,
            offset=offset,
            record_count=min(page_size, target - offset),
            return_geometry=False,
        )
        if not page:
            raise PaginationError(
                "Washington parcel companion table ended before its count",
                url=str(getattr(client, "layer_url", "companion-table")),
                details={"offset": offset, "count": count},
            )
        object_ids = [_object_id(feature) for feature in page]
        if object_ids != sorted(object_ids) or (
            previous_object_id is not None and object_ids[0] <= previous_object_id
        ):
            raise PaginationError(
                "Washington parcel companion table is not ordered by OBJECTID",
                url=str(getattr(client, "layer_url", "companion-table")),
            )
        rows.extend(page)
        offset += len(page)
        previous_object_id = object_ids[-1]
    return tuple(rows)


def _freshness_map(client: Any) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for feature in _table_rows(client):
        attributes = _feature_attributes(feature)
        code = str(attributes.get("COUNTY_NM") or "").strip()
        if code:
            result[code] = _arcgis_timestamp(attributes.get("FILE_DATE"))
    return result


def _county_land_use_map(client: Any) -> dict[tuple[str, str], str | None]:
    result: dict[tuple[str, str], str | None] = {}
    for feature in _table_rows(client):
        attributes = _feature_attributes(feature)
        county = str(attributes.get("COUNTY_NM") or "").strip()
        code = str(attributes.get("CODE") or "").strip()
        if county and code:
            description = str(attributes.get("CODE_DESC") or "").strip() or None
            result[(county, code)] = description
    return result


def _normalize_feature(
    representation: Representation,
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
    owner_fields_detected: Iterable[str],
    dor_land_use: Mapping[int, str],
    freshness: Mapping[str, str | None],
    county_land_use: Mapping[tuple[str, str], str | None],
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = _feature_attributes(feature)
    county = _county_from_attributes(attributes)
    normalized_parcel_id = str(attributes.get("PARCEL_ID_NR") or "").strip() or None
    original_parcel_id = (
        str(attributes.get("ORIG_PARCEL_ID") or "").strip() or None
    )
    identity = original_parcel_id or normalized_parcel_id
    if identity is None:
        identity = f"OBJECTID-{_object_id(feature)}"
    county_code = county.coded_value
    original_land_use = (
        str(attributes.get("ORIG_LANDUSE_CD") or "").strip() or None
    )
    source_file_date = _arcgis_timestamp(attributes.get("FILE_DATE"))
    current_county_file_date = freshness.get(county_code)
    if not representation.has_feature_file_date:
        source_file_date = current_county_file_date
    dor_code = attributes.get("LANDUSE_CD")
    dor_description = (
        dor_land_use.get(dor_code) if isinstance(dor_code, int) else None
    )
    route = _county_assessor_route(attributes.get("DATA_LINK"))
    owner_field_names = tuple(sorted(set(owner_fields_detected)))
    owner_related_attributes = {
        field_name: attributes.get(field_name)
        for field_name in owner_field_names
        if field_name in attributes
    }
    owner_name_fields = tuple(
        field_name
        for field_name in owner_field_names
        if any(
            marker in field_name.upper()
            for marker in ("OWNER", "OWNR", "TAXPAYER", "TAX_PAYER")
        )
    )
    owners = [
        {
            "raw_name": str(attributes[field_name]).strip(),
            "source_field": field_name,
        }
        for field_name in owner_name_fields
        if attributes.get(field_name) not in (None, "")
        and str(attributes[field_name]).strip()
    ]
    record: dict[str, Any] = {
        "record_kind": "property_parcel",
        "source_id": representation.source_id,
        "representation": representation.key,
        "representation_role": representation.role,
        "lineage_id": LINEAGE_ID,
        "canonical_ref": canonical_property_ref(
            LINEAGE_ID,
            county.geoid,
            "parcel",
            identity,
        ),
        "source_feature_id": f"OBJECTID:{_object_id(feature)}",
        "object_id": _object_id(feature),
        "global_id": _case_insensitive_value(
            attributes,
            "GlobalID",
            "GLOBALID",
        ),
        "native_parcel_id": original_parcel_id,
        "normalized_parcel_id": normalized_parcel_id,
        "original_parcel_id": original_parcel_id,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": county.name,
            "county_fips": county.fips,
            "county_geoid": county.geoid,
            "source_native_county": attributes.get("COUNTY_NM"),
        },
        "situs": {
            "address": attributes.get("SITUS_ADDRESS"),
            "sub_address": attributes.get("SUB_ADDRESS"),
            "city": attributes.get("SITUS_CITY_NM"),
            "zip": attributes.get("SITUS_ZIP_NR"),
        },
        "assessment": {
            "land_value": attributes.get("VALUE_LAND"),
            "building_value": attributes.get("VALUE_BLDG"),
            "total_value": (
                (attributes.get("VALUE_LAND") or 0)
                + (attributes.get("VALUE_BLDG") or 0)
                if isinstance(attributes.get("VALUE_LAND"), (int, float))
                and isinstance(attributes.get("VALUE_BLDG"), (int, float))
                else None
            ),
        },
        "land_use": {
            "dor_code": dor_code,
            "dor_description": dor_description,
            "county_original_code": original_land_use,
            "county_original_description": (
                county_land_use.get((county_code, original_land_use))
                if original_land_use
                else None
            ),
            "county_code_join": (
                {
                    "county_native_code": county_code,
                    "code": original_land_use,
                    "source_id": LAND_USE_SOURCE_ID,
                }
                if original_land_use
                else None
            ),
        },
        "source_file_date": source_file_date,
        "current_county_file_date": current_county_file_date,
        "county_freshness_source_id": FRESHNESS_SOURCE_ID,
        "owners": owners,
        "owner_visibility": {
            "state": (
                "published_in_live_schema"
                if owner_field_names
                else "not_published_by_normalized_statewide_layer"
            ),
            "published_owner_fields": list(owner_field_names),
            "county_detail_field": "DATA_LINK",
        },
        "owner_related_attributes": owner_related_attributes,
        "county_assessor_route": route,
        "data_link": attributes.get("DATA_LINK"),
        "source_lineage": {
            "lineage_id": LINEAGE_ID,
            "representation_source_id": representation.source_id,
            "relationship": "same_normalized_state_county_dataset",
            "publisher": representation.publisher,
            "upstream_custodians": "Washington counties",
            "mirror_comparison_is_corroboration": False,
        },
        "response_schema_fingerprint": schema_fingerprint_value,
        "raw_attributes": dict(attributes),
    }
    if geometry_requested:
        record["geometry"] = feature.get("geometry")
        record["geometry_crs"] = "EPSG:4326"
    return record


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "retry_attempts",
    }
    parameters: dict[str, Any] = {}
    for key, value in vars(args).items():
        if key in ignored or value is None:
            continue
        if isinstance(value, Path):
            parameters[key] = str(value)
        else:
            parameters[key] = value
    return parameters


def _jurisdiction_for_args(args: argparse.Namespace) -> JurisdictionMetadata:
    county_value = getattr(args, "county", None) or getattr(args, "fips", None)
    if not county_value:
        return STATE_JURISDICTION
    try:
        county = _resolve_county(county_value)
    except WashingtonParcelSelectionError:
        return STATE_JURISDICTION
    return JurisdictionMetadata(
        jurisdiction_id=county.geoid,
        name=f"{county.name} County, Washington",
        state_code=STATE_CODE,
        county_fips=county.geoid,
        metadata={"state_fips": STATE_FIPS, "county_fips_3": county.fips},
    )


def _build_query(
    args: argparse.Namespace,
    source: SourceMetadata,
    *,
    requested_limit: int | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction_for_args(args),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: WashingtonParcelSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
    )


def _source_changed_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.SOURCE_CHANGED,
        [
            PublicRecordsError(
                code="washington_parcel_normalization_failed",
                message=str(error),
                category="source_schema",
                retryable=False,
            )
        ],
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    source_id: str,
    result: PublicRecordsResult,
    *,
    enabled: bool,
) -> None:
    if not enabled:
        return
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception as error:  # pragma: no cover - logging backend is external
        print(f"WARNING: search logging failed: {error}", file=sys.stderr)


def _client_map(args: argparse.Namespace) -> dict[str, WashingtonArcGISClient]:
    common = {
        "page_size": args.page_size,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "retry_attempts": args.retry_attempts,
    }
    clients = {
        representation.key: WashingtonArcGISClient(
            representation.layer_url,
            max_page_size=representation.max_page_size,
            **common,
        )
        for representation in REPRESENTATIONS.values()
    }
    clients["freshness"] = WashingtonArcGISClient(
        FRESHNESS_TABLE_URL,
        max_page_size=2_000,
        **common,
    )
    clients["landuse"] = WashingtonArcGISClient(
        LAND_USE_TABLE_URL,
        max_page_size=2_000,
        **common,
    )
    return clients


def _client(clients: Mapping[str, Any], key: str) -> Any:
    try:
        return clients[key]
    except KeyError as error:
        raise WashingtonParcelSelectionError(
            "missing_client",
            f"no ArcGIS client configured for {key}",
        ) from error


def _metadata_record(
    representation: Representation,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _metadata_contract(representation, metadata)
    return {
        "record_kind": "source_metadata",
        "source": representation.source_metadata().to_dict(),
        "representation": representation.key,
        "lineage_id": LINEAGE_ID,
        "layer_url": representation.layer_url,
        **contract,
        "county_detail_route": {
            "field": "DATA_LINK",
            "role": "county_assessor_tax_owner_and_history_enrichment",
        },
    }


def _execute_metadata(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    selections = (
        list(REPRESENTATIONS.values())
        if args.representation == "all"
        else [_representation(args.representation)]
    )
    source = (
        LINEAGE_METADATA
        if len(selections) > 1
        else selections[0].source_metadata()
    )
    query = _build_query(args, source)
    records = [
        _metadata_record(
            representation,
            _client(clients, representation.key).fetch_metadata(),
        )
        for representation in selections
    ]
    return query, PublicRecordsResult.success(query, records)


def _execute_count(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    representation = _representation(args.representation)
    query = _build_query(args, representation.source_metadata())
    spec = _query_spec(args, representation)
    count = _client(clients, representation.key).fetch_count(
        spec.where,
        parameters=spec.geometry_parameters,
    )
    record = {
        "record_kind": "source_count",
        "source_id": representation.source_id,
        "representation": representation.key,
        "lineage_id": LINEAGE_ID,
        "where": spec.where,
        "count": count,
        "geometry_filter": dict(spec.geometry_parameters),
    }
    return query, PublicRecordsResult.success(query, [record])


def _execute_records(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    representation = _representation(args.representation)
    query = _build_query(
        args,
        representation.source_metadata(),
        requested_limit=args.limit,
    )
    spec = _query_spec(args, representation)
    batch = _fetch_batch(
        _client(clients, representation.key),
        representation,
        operation=args.command,
        spec=spec,
        limit=args.limit,
        cursor=args.cursor,
    )
    freshness: dict[str, str | None] = {}
    county_land_use: dict[tuple[str, str], str | None] = {}
    if args.enrich:
        freshness = _freshness_map(_client(clients, "freshness"))
        county_land_use = _county_land_use_map(_client(clients, "landuse"))
    dor_land_use = _dor_land_use_domain(batch.metadata)
    live_contract = _metadata_contract(representation, batch.metadata)
    records = [
        _normalize_feature(
            representation,
            feature,
            schema_fingerprint_value=batch.schema_fingerprint,
            owner_fields_detected=live_contract["owner_fields_detected"],
            dor_land_use=dor_land_use,
            freshness=freshness,
            county_land_use=county_land_use,
            geometry_requested=spec.return_geometry,
        )
        for feature in batch.features
    ]
    if live_contract["owner_fields_detected"]:
        owner_observation = (
            "The live normalized schema publishes owner-related fields; their "
            "raw values are surfaced with the parcel record."
        )
    else:
        owner_observation = (
            "The live normalized schema currently publishes no owner or "
            "taxpayer fields; DATA_LINK identifies the county detail route."
        )
    warnings = [owner_observation, *batch.warnings]
    if representation is WISAARD:
        warnings.append(
            "WISAARD is an optional parity surface; compare its count and "
            "FILE_DATE with the Ecology default before using snapshot values."
        )
    result = PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )
    return query, result


def _execute_freshness(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    query = _build_query(args, FRESHNESS_METADATA)
    county = _resolve_county(args.county) if args.county else None
    where = (
        f"COUNTY_NM='{county.coded_value}'"
        if county is not None
        else "1=1"
    )
    rows = _table_rows(
        _client(clients, "freshness"),
        where=where,
        limit=args.limit,
    )
    records: list[dict[str, Any]] = []
    for feature in rows:
        attributes = _feature_attributes(feature)
        row_county = _resolve_county(attributes.get("COUNTY_NM"))
        records.append(
            {
                "record_kind": "county_parcel_freshness",
                "source_id": FRESHNESS_SOURCE_ID,
                "lineage_id": LINEAGE_ID,
                "county_name": row_county.name,
                "county_fips": row_county.fips,
                "county_geoid": row_county.geoid,
                "source_native_county": attributes.get("COUNTY_NM"),
                "file_date": _arcgis_timestamp(attributes.get("FILE_DATE")),
                "global_id": attributes.get("GlobalID"),
                "object_id": attributes.get("OBJECTID"),
            }
        )
    return query, PublicRecordsResult.success(query, records)


def _execute_land_use_codes(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    query = _build_query(args, LAND_USE_METADATA)
    expressions: list[str] = []
    selected_county = _resolve_county(args.county) if args.county else None
    if selected_county is not None:
        expressions.append(f"COUNTY_NM='{selected_county.coded_value}'")
    if args.code:
        expressions.append(f"CODE='{_sql_literal(args.code, 'land-use code')}'")
    where = " AND ".join(f"({item})" for item in expressions) or "1=1"
    rows = _table_rows(
        _client(clients, "landuse"),
        where=where,
        limit=args.limit,
    )
    records: list[dict[str, Any]] = []
    for feature in rows:
        attributes = _feature_attributes(feature)
        county = _resolve_county(attributes.get("COUNTY_NM"))
        records.append(
            {
                "record_kind": "county_land_use_code",
                "source_id": LAND_USE_SOURCE_ID,
                "lineage_id": LINEAGE_ID,
                "county_name": county.name,
                "county_fips": county.fips,
                "county_geoid": county.geoid,
                "source_native_county": attributes.get("COUNTY_NM"),
                "code": attributes.get("CODE"),
                "description": attributes.get("CODE_DESC"),
                "join_key": {
                    "county_native_code": str(
                        attributes.get("COUNTY_NM") or ""
                    ),
                    "code": str(attributes.get("CODE") or ""),
                },
                "global_id": attributes.get("GlobalID"),
                "object_id": attributes.get("OBJECTID"),
            }
        )
    return query, PublicRecordsResult.success(query, records)


def _sentinel_snapshot(
    representation: Representation,
    client: Any,
    *,
    freshness: Mapping[str, str | None],
) -> dict[str, Any]:
    metadata = client.fetch_metadata()
    contract = _metadata_contract(representation, metadata)
    total_count = client.fetch_count("1=1")
    where = f"PARCEL_ID_NR='{SENTINEL_PARCEL_ID}'"
    sentinel_count = client.fetch_count(where)
    page = client.fetch_page(
        where=where,
        offset=0,
        record_count=1,
        return_geometry=False,
    )
    if sentinel_count != 1 or len(page) != 1:
        raise SourceSchemaError(
            "Washington parcel sentinel is missing or non-unique",
            url=representation.layer_url,
            details={
                "representation": representation.key,
                "sentinel_count": sentinel_count,
                "returned": len(page),
            },
        )
    attributes = _feature_attributes(page[0])
    county = _county_from_attributes(attributes)
    file_date = _arcgis_timestamp(attributes.get("FILE_DATE"))
    if not representation.has_feature_file_date:
        file_date = freshness.get(county.coded_value)
    return {
        "representation": representation.key,
        "source_id": representation.source_id,
        "representation_role": representation.role,
        "lineage_id": LINEAGE_ID,
        "total_count": total_count,
        "schema_fingerprint": contract["schema_fingerprint"],
        "owner_fields_detected": contract["owner_fields_detected"],
        "parcel_id": attributes.get("PARCEL_ID_NR"),
        "original_parcel_id": attributes.get("ORIG_PARCEL_ID"),
        "county_fips": attributes.get("FIPS_NR"),
        "county_name": county.name,
        "land_value": attributes.get("VALUE_LAND"),
        "building_value": attributes.get("VALUE_BLDG"),
        "file_date": file_date,
        "data_link": attributes.get("DATA_LINK"),
        "data_link_host": (
            _county_assessor_route(attributes.get("DATA_LINK")) or {}
        ).get("host"),
        "object_id": attributes.get("OBJECTID"),
        "global_id": _case_insensitive_value(
            attributes,
            "GlobalID",
            "GLOBALID",
        ),
    }


def _parity_record(
    clients: Mapping[str, Any],
    *,
    include_wisaard: bool,
) -> dict[str, Any]:
    freshness = _freshness_map(_client(clients, "freshness"))
    selections = [ECOLOGY, DNR]
    if include_wisaard:
        selections.append(WISAARD)
    snapshots = {
        representation.key: _sentinel_snapshot(
            representation,
            _client(clients, representation.key),
            freshness=freshness,
        )
        for representation in selections
    }
    baseline = snapshots[ECOLOGY.key]
    comparisons: list[dict[str, Any]] = []
    for representation in selections[1:]:
        candidate = snapshots[representation.key]
        identity_equal = all(
            candidate.get(field_name) == baseline.get(field_name)
            for field_name in (
                "parcel_id",
                "original_parcel_id",
                "county_fips",
            )
        )
        snapshot_equal = all(
            candidate.get(field_name) == baseline.get(field_name)
            for field_name in (
                "total_count",
                "land_value",
                "building_value",
                "file_date",
            )
        )
        if not identity_equal:
            health = "identity_mismatch"
        elif snapshot_equal:
            health = "aligned"
        elif (
            candidate.get("file_date")
            and baseline.get("file_date")
            and str(candidate["file_date"]) < str(baseline["file_date"])
        ):
            health = "lagging"
        else:
            health = "different_snapshot"
        comparisons.append(
            {
                "baseline": ECOLOGY.key,
                "candidate": representation.key,
                "identity_equal": identity_equal,
                "snapshot_equal": snapshot_equal,
                "health": health,
                "differences": {
                    field_name: {
                        "baseline": baseline.get(field_name),
                        "candidate": candidate.get(field_name),
                    }
                    for field_name in (
                        "total_count",
                        "land_value",
                        "building_value",
                        "file_date",
                        "data_link",
                    )
                    if baseline.get(field_name) != candidate.get(field_name)
                },
            }
        )
    return {
        "record_kind": "parcel_representation_parity",
        "lineage_id": LINEAGE_ID,
        "sentinel_parcel_id": SENTINEL_PARCEL_ID,
        "interpretation": "mirror_health_not_corroboration",
        "representations": snapshots,
        "comparisons": comparisons,
    }


def _execute_parity(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    query = _build_query(args, LINEAGE_METADATA)
    record = _parity_record(
        clients,
        include_wisaard=args.include_wisaard,
    )
    return query, PublicRecordsResult.success(query, [record])


def _pagination_boundary_probe(
    representation: Representation,
    client: Any,
) -> dict[str, Any]:
    metadata = client.fetch_metadata()
    contract = _metadata_contract(representation, metadata)
    boundary_offset = int(contract["max_record_count"])
    before = client.fetch_page(
        where="1=1",
        offset=boundary_offset - 1,
        record_count=1,
        out_fields="OBJECTID",
        return_geometry=False,
    )
    after = client.fetch_page(
        where="1=1",
        offset=boundary_offset,
        record_count=1,
        out_fields="OBJECTID",
        return_geometry=False,
    )
    if len(before) != 1 or len(after) != 1:
        raise PaginationError(
            "Washington parcel page-boundary probe returned incomplete rows",
            url=representation.layer_url,
        )
    before_id = _object_id(before[0])
    after_id = _object_id(after[0])
    if after_id <= before_id:
        raise PaginationError(
            "Washington parcel page-boundary OBJECTID did not advance",
            url=representation.layer_url,
            details={"before": before_id, "after": after_id},
        )
    return {
        "status": "ok",
        "boundary_offset": boundary_offset,
        "before_object_id": before_id,
        "after_object_id": after_id,
        "order_by": "OBJECTID ASC",
    }


def _representation_probe(
    representation: Representation,
    client: Any,
    *,
    operation: str,
    freshness: Mapping[str, str | None],
) -> dict[str, Any]:
    operations = (
        ("metadata", "count", "sentinel", "pagination")
        if operation == "all"
        else (operation,)
    )
    record: dict[str, Any] = {
        "record_kind": "source_probe",
        "source_id": representation.source_id,
        "representation": representation.key,
        "lineage_id": LINEAGE_ID,
        "operations": {},
    }
    metadata: Mapping[str, Any] | None = None
    for selected in operations:
        if selected == "metadata":
            metadata = metadata or client.fetch_metadata()
            record["operations"]["metadata"] = {
                "status": "ok",
                **_metadata_contract(representation, metadata),
            }
        elif selected == "count":
            record["operations"]["count"] = {
                "status": "ok",
                "count": client.fetch_count("1=1"),
            }
        elif selected == "sentinel":
            record["operations"]["sentinel"] = {
                "status": "ok",
                **_sentinel_snapshot(
                    representation,
                    client,
                    freshness=freshness,
                ),
            }
        elif selected == "pagination":
            record["operations"]["pagination"] = _pagination_boundary_probe(
                representation,
                client,
            )
        else:
            raise WashingtonParcelSelectionError(
                "unknown_probe_operation",
                f"unknown parcel probe operation: {selected}",
            )
    return record


def _companion_probe(clients: Mapping[str, Any]) -> dict[str, Any]:
    freshness_client = _client(clients, "freshness")
    land_use_client = _client(clients, "landuse")
    freshness_count = freshness_client.fetch_count("1=1")
    land_use_count = land_use_client.fetch_count("1=1")
    freshness_rows = _table_rows(freshness_client, limit=1)
    land_use_rows = _table_rows(land_use_client, limit=1)
    if freshness_count != 39:
        raise SourceSchemaError(
            "Washington county freshness table does not contain 39 rows",
            url=FRESHNESS_TABLE_URL,
            details={"count": freshness_count},
        )
    return {
        "record_kind": "companion_table_probe",
        "lineage_id": LINEAGE_ID,
        "freshness": {
            "status": "ok",
            "source_id": FRESHNESS_SOURCE_ID,
            "count": freshness_count,
            "sample": dict(_feature_attributes(freshness_rows[0])),
        },
        "county_land_use": {
            "status": "ok",
            "source_id": LAND_USE_SOURCE_ID,
            "count": land_use_count,
            "join_key": ["COUNTY_NM", "CODE"],
            "sample": dict(_feature_attributes(land_use_rows[0])),
        },
    }


def _execute_probe(
    args: argparse.Namespace,
    clients: Mapping[str, Any],
) -> tuple[PublicRecordsQuery, PublicRecordsResult]:
    query = _build_query(args, LINEAGE_METADATA)
    records: list[dict[str, Any]] = []
    freshness = _freshness_map(_client(clients, "freshness"))
    if args.operation in {"all", "companions"}:
        records.append(_companion_probe(clients))
    if args.operation in {"all", "parity"}:
        records.append(
            _parity_record(
                clients,
                include_wisaard=args.include_wisaard,
            )
        )
    if args.operation not in {"companions", "parity"}:
        selections = (
            list(REPRESENTATIONS.values())
            if args.representation == "all"
            else [_representation(args.representation)]
        )
        for representation in selections:
            if (
                args.representation == "all"
                and representation is WISAARD
                and not args.include_wisaard
            ):
                continue
            records.append(
                _representation_probe(
                    representation,
                    _client(clients, representation.key),
                    operation=args.operation,
                    freshness=freshness,
                )
            )
    return query, PublicRecordsResult.success(query, records)


def execute(
    args: argparse.Namespace,
    *,
    clients: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Washington parcel operation."""

    active_clients = clients or _client_map(args)
    if args.command in {"parity", "probe"}:
        source = LINEAGE_METADATA
    elif args.command == "county-freshness":
        source = FRESHNESS_METADATA
    elif args.command == "land-use-codes":
        source = LAND_USE_METADATA
    else:
        representation_value = getattr(args, "representation", "ecology")
        source = (
            LINEAGE_METADATA
            if representation_value == "all"
            else _representation(representation_value).source_metadata()
        )
    fallback_query = _build_query(
        args,
        source,
        requested_limit=getattr(args, "limit", None),
    )
    try:
        if args.command == "metadata":
            query, result = _execute_metadata(args, active_clients)
        elif args.command == "count":
            query, result = _execute_count(args, active_clients)
        elif args.command in {"search", "export", "point", "bbox"}:
            query, result = _execute_records(args, active_clients)
        elif args.command == "county-freshness":
            query, result = _execute_freshness(args, active_clients)
        elif args.command == "land-use-codes":
            query, result = _execute_land_use_codes(args, active_clients)
        elif args.command == "parity":
            query, result = _execute_parity(args, active_clients)
        elif args.command == "probe":
            query, result = _execute_probe(args, active_clients)
        else:
            raise WashingtonParcelSelectionError(
                "unknown_operation",
                f"unknown Washington parcel operation: {args.command}",
            )
    except WashingtonParcelSelectionError as error:
        query = fallback_query
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        query = fallback_query
        result = failure_result(query, error)
    except (TypeError, ValueError) as error:
        query = fallback_query
        result = _source_changed_failure(query, error)
    _best_effort_log(
        query,
        query.source.source_id,
        result,
        enabled=log_results,
    )
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Washington parcels {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Washington parcels {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("normalized_parcel_id")
            or record.get("county_name")
            or record.get("representation")
            or record.get("record_kind")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=2_000,
        help="Requested page size, clamped to the selected service maximum",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=0.2,
        help="Minimum seconds between requests to one component",
    )
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def _add_representation_argument(
    parser: argparse.ArgumentParser,
    *,
    allow_all: bool = False,
) -> None:
    choices = sorted(REPRESENTATIONS)
    if allow_all:
        choices.append("all")
    parser.add_argument(
        "--representation",
        choices=choices,
        default="ecology",
        help="Official ArcGIS representation; Ecology is the default",
    )


def _add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county", help="County name, 3-digit FIPS, or 5-digit GEOID")
    parser.add_argument("--fips", help="County name, 3-digit FIPS, or 5-digit GEOID")
    parser.add_argument("--parcel-id")
    parser.add_argument("--original-parcel-id")
    parser.add_argument("--situs")
    parser.add_argument("--land-use", type=int)
    parser.add_argument("--original-land-use")


def _add_record_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_limit: int,
) -> None:
    _add_representation_argument(parser)
    _add_filter_arguments(parser)
    parser.add_argument("--limit", type=_positive_int, default=default_limit)
    parser.add_argument("--cursor")
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Return source geometry transformed to WGS84",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_false",
        dest="enrich",
        help="Skip county freshness and original land-use lookup joins",
    )
    parser.set_defaults(enrich=True)
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Washington's official normalized statewide parcel "
            "representations"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata = subparsers.add_parser(
        "metadata",
        help="Inspect representation lineage, fields, and query capabilities",
    )
    _add_representation_argument(metadata, allow_all=True)
    _add_transport_arguments(metadata)

    count = subparsers.add_parser(
        "count",
        help="Count parcels matching structured filters",
    )
    _add_representation_argument(count)
    _add_filter_arguments(count)
    _add_transport_arguments(count)

    search = subparsers.add_parser(
        "search",
        help="Search parcel IDs, county, situs, or land-use fields",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=(
            "auto",
            "parcel",
            "parcel-id",
            "original-parcel-id",
            "county",
            "fips",
            "situs",
            "land-use",
            "original-land-use",
        ),
        default="auto",
    )
    _add_record_arguments(search, default_limit=100)

    export = subparsers.add_parser(
        "export",
        help="Export a deterministic OBJECTID-ordered parcel slice",
    )
    _add_record_arguments(export, default_limit=5_000)

    point = subparsers.add_parser(
        "point",
        help="Find parcels intersecting a WGS84 point",
    )
    point.add_argument("longitude", type=_longitude)
    point.add_argument("latitude", type=_latitude)
    _add_record_arguments(point, default_limit=100)

    bbox = subparsers.add_parser(
        "bbox",
        help="Find parcels intersecting a WGS84 bounding box",
    )
    bbox.add_argument("west", type=_longitude)
    bbox.add_argument("south", type=_latitude)
    bbox.add_argument("east", type=_longitude)
    bbox.add_argument("north", type=_latitude)
    _add_record_arguments(bbox, default_limit=100)

    freshness = subparsers.add_parser(
        "county-freshness",
        help="List Ecology's per-county parcel file dates",
    )
    freshness.add_argument("--county")
    freshness.add_argument("--limit", type=_positive_int, default=39)
    _add_transport_arguments(freshness)

    land_use = subparsers.add_parser(
        "land-use-codes",
        help="Query county-specific original land-use code descriptions",
    )
    land_use.add_argument("--county")
    land_use.add_argument("--code")
    land_use.add_argument("--limit", type=_positive_int, default=2_000)
    _add_transport_arguments(land_use)

    parity = subparsers.add_parser(
        "parity",
        help="Compare the stable sentinel as mirror health, not corroboration",
    )
    parity.add_argument(
        "--include-wisaard",
        action="store_true",
        help="Include the optional WISAARD parity representation",
    )
    _add_transport_arguments(parity)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded metadata/count/sentinel/pagination/component probes",
    )
    probe.add_argument(
        "--operation",
        choices=(
            "metadata",
            "count",
            "sentinel",
            "pagination",
            "companions",
            "parity",
            "all",
        ),
        default="all",
    )
    _add_representation_argument(probe, allow_all=True)
    probe.add_argument(
        "--include-wisaard",
        action="store_true",
        help="Include WISAARD in all/parity probes",
    )
    _add_transport_arguments(probe)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
