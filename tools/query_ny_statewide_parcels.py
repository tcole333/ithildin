#!/usr/bin/env python3
"""Query New York's official Statewide Parcel Map Program.

NYS ITS Geospatial Services publishes three complementary ArcGIS datasets:

* parcel centroids with assessment attributes for all 62 counties;
* parcel polygons for counties that authorize statewide redistribution; and
* a statewide subset of parcels identified as New York State owned.

The three datasets share the standardized ``SWIS_SBL_ID``,
``SWIS_PRINT_KEY_ID``, and ``MUNI_PARCEL_ID`` fields.  Those identifiers make
it possible to begin with the all-county centroid index, attach public geometry
where available, and pivot to state-agency ownership without fuzzy matching.

Searches use ordered ``OBJECTID`` keyset traversal.  Omitting ``--limit``
retrieves every native match; ``--page-size`` controls transport batches.

Examples:
    uv run python tools/query_ny_statewide_parcels.py owner "STATE OF NEW YORK"
    uv run python tools/query_ny_statewide_parcels.py address "190 KARNER RD"
    uv run python tools/query_ny_statewide_parcels.py parcel \
        01010004100000021270000000 --collection public-parcels --geometry
    uv run python tools/query_ny_statewide_parcels.py agency DEC \
        --collection state-owned
    uv run python tools/query_ny_statewide_parcels.py point \
        -73.8682488 42.7208301 --geometry
    uv run python tools/query_ny_statewide_parcels.py coverage --json
    uv run python tools/query_ny_statewide_parcels.py alternatives --json
    uv run python tools/query_ny_statewide_parcels.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-ny-statewide-parcels"
STATE_CODE = "NY"
STATE_FIPS = "36"
LANDING_URL = "https://gis.ny.gov/parcels"
MIGRATION_URL = "https://gis.ny.gov/migration-web-services"
DATA_DICTIONARY_URL = "https://gis.ny.gov/standardized-tax-parcel-data-dictionary"
POLYGON_METADATA_URL = "https://gis.ny.gov/current-parcel-polygon-metadata"
CENTROID_METADATA_URL = "https://gis.ny.gov/current-parcel-centroid-metadata"
STATE_OWNED_METADATA_URL = "https://gis.ny.gov/current-state-owned-parcels-metadata"

CENTROID_SERVICE_URL = (
    "https://gisservices.its.ny.gov/arcgis/rest/services/"
    "NYS_Tax_Parcel_Centroid_Points/FeatureServer"
)
PUBLIC_SERVICE_URL = (
    "https://gisservices.its.ny.gov/arcgis/rest/services/"
    "NYS_Tax_Parcels_Public/FeatureServer"
)
STATE_OWNED_SERVICE_URL = (
    "https://gisservices.its.ny.gov/arcgis/rest/services/"
    "NYS_Tax_Parcels_State_Owned/FeatureServer"
)
ASSESSMENT_LOOKUP_URL = (
    "https://gisservices.its.ny.gov/arcgis/rest/services/"
    "NYSTaxAssessmentLookup/GPServer/TaxAssessment"
)

PUBLIC_DOWNLOAD_URL = "https://gisdata.ny.gov/GISData/State/Parcels/NYS-Tax-Parcels.zip"
CENTROID_DOWNLOAD_URL = (
    "https://gisdata.ny.gov/GISData/State/Parcels/"
    "NYS-Tax-Parcel-Centroid-Points.gdb.zip"
)
STATE_OWNED_DOWNLOAD_URL = (
    "https://gisdata.ny.gov/GISData/State/Parcels/NYS-Tax-Parcels-State-Owned.gdb.zip"
)

MUNICIPAL_DATA_PORTAL_URL = "https://www.tax.ny.gov/pit/property/munidataportal.htm"
SALES_WEB_APP_URL = "https://pad.tax.ny.gov"
TRANSFER_INFO_URL = (
    "https://www.tax.ny.gov/pit/property/new-homebuyers/transfer-reporting.htm"
)
ACRIS_URL = "https://www.nyc.gov/acris"
OGS_LAND_RECORDS_URL = "https://ogs.ny.gov/real-estate/land-records-and-maps"

DEFAULT_PAGE_SIZE = 1_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "ny-parcels:v1:"
CURSOR_VERSION = 1

COMMON_REQUIRED_FIELDS = (
    "OBJECTID",
    "COUNTY_NAME",
    "MUNI_NAME",
    "SWIS",
    "PARCEL_ADDR",
    "PRINT_KEY",
    "SBL",
    "CITYTOWN_NAME",
    "CITYTOWN_SWIS",
    "LOC_ST_NBR",
    "LOC_STREET",
    "LOC_UNIT",
    "LOC_ZIP",
    "PROP_CLASS",
    "ROLL_SECTION",
    "LAND_AV",
    "TOTAL_AV",
    "FULL_MARKET_VAL",
    "PRIMARY_OWNER",
    "ADD_OWNER",
    "MAIL_ADDR",
    "MAIL_CITY",
    "MAIL_STATE",
    "MAIL_ZIP",
    "BOOK",
    "PAGE",
    "MUNI_PARCEL_ID",
    "SWIS_SBL_ID",
    "SWIS_PRINT_KEY_ID",
    "ROLL_YR",
    "SPATIAL_YR",
    "OWNER_TYPE",
    "NYS_NAME",
    "NYS_NAME_SOURCE",
    "DUP_GEO",
    "CALC_ACRES",
)
FOOTPRINT_REQUIRED_FIELDS = (
    "OBJECTID",
    "NAME",
    "COUNTY_FIPS",
    "SWIS",
)

COUNTIES = {
    "001": "Albany",
    "003": "Allegany",
    "005": "Bronx",
    "007": "Broome",
    "009": "Cattaraugus",
    "011": "Cayuga",
    "013": "Chautauqua",
    "015": "Chemung",
    "017": "Chenango",
    "019": "Clinton",
    "021": "Columbia",
    "023": "Cortland",
    "025": "Delaware",
    "027": "Dutchess",
    "029": "Erie",
    "031": "Essex",
    "033": "Franklin",
    "035": "Fulton",
    "037": "Genesee",
    "039": "Greene",
    "041": "Hamilton",
    "043": "Herkimer",
    "045": "Jefferson",
    "047": "Kings",
    "049": "Lewis",
    "051": "Livingston",
    "053": "Madison",
    "055": "Monroe",
    "057": "Montgomery",
    "059": "Nassau",
    "061": "New York",
    "063": "Niagara",
    "065": "Oneida",
    "067": "Onondaga",
    "069": "Ontario",
    "071": "Orange",
    "073": "Orleans",
    "075": "Oswego",
    "077": "Otsego",
    "079": "Putnam",
    "081": "Queens",
    "083": "Rensselaer",
    "085": "Richmond",
    "087": "Rockland",
    "089": "St Lawrence",
    "091": "Saratoga",
    "093": "Schenectady",
    "095": "Schoharie",
    "097": "Schuyler",
    "099": "Seneca",
    "101": "Steuben",
    "103": "Suffolk",
    "105": "Sullivan",
    "107": "Tioga",
    "109": "Tompkins",
    "111": "Ulster",
    "113": "Warren",
    "115": "Washington",
    "117": "Wayne",
    "119": "Westchester",
    "121": "Wyoming",
    "123": "Yates",
}


def _name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


COUNTY_ALIASES = {
    _name_key(name): (f"{STATE_FIPS}{fips}", name) for fips, name in COUNTIES.items()
}
COUNTY_ALIASES.update(
    {
        "brooklyn": ("36047", "Kings"),
        "manhattan": ("36061", "New York"),
        "statenisland": ("36085", "Richmond"),
    }
)

OWNER_TYPE_DESCRIPTIONS = {
    "1": "federal",
    "2": "state",
    "3": "county",
    "4": "city",
    "5": "town",
    "6": "village",
    "7": "mixed_government",
    "8": "private",
    "9": "public_school_district_or_boces",
    "10": "road_right_of_way",
    "11": "water",
    "-999": "unknown",
}

SOURCE_WARNINGS = (
    "These are annual parcel and assessment observations. County property "
    "systems may contain newer local changes.",
    "Public parcel polygons currently cover participating counties; parcel "
    "centroids provide the statewide assessment index.",
    "BOOK and PAGE are populated only for a recent-sale window in the source. "
    "Use Sales Web or the recording office for transfer and instrument history.",
    "Parcel geometry is contributed by counties and may include coincident "
    "duplicates identified by DUP_GEO.",
)


@dataclass(frozen=True)
class Component:
    key: str
    service_url: str
    layer_id: int
    layer_name: str
    geometry_type: str
    source_role: str
    record_type: str
    coverage: str
    download_url: str | None
    metadata_url: str
    required_fields: tuple[str, ...] = COMMON_REQUIRED_FIELDS

    @property
    def layer_url(self) -> str:
        return f"{self.service_url}/{self.layer_id}"


COMPONENTS = {
    "centroids": Component(
        key="centroids",
        service_url=CENTROID_SERVICE_URL,
        layer_id=0,
        layer_name="NYS_Tax_Parcel_Centroid_Points",
        geometry_type="esriGeometryPoint",
        source_role="statewide_annual_parcel_assessment_centroid_index",
        record_type="statewide_annual_parcel_assessment_centroid",
        coverage="assessment attributes and centroid points for all 62 counties",
        download_url=CENTROID_DOWNLOAD_URL,
        metadata_url=CENTROID_METADATA_URL,
    ),
    "public-parcels": Component(
        key="public-parcels",
        service_url=PUBLIC_SERVICE_URL,
        layer_id=1,
        layer_name="NYS_Tax_Parcels_Public",
        geometry_type="esriGeometryPolygon",
        source_role="annual_public_parcel_geometry_and_assessment",
        record_type="statewide_annual_public_parcel_polygon",
        coverage="parcel polygons for counties authorizing public redistribution",
        download_url=PUBLIC_DOWNLOAD_URL,
        metadata_url=POLYGON_METADATA_URL,
    ),
    "state-owned": Component(
        key="state-owned",
        service_url=STATE_OWNED_SERVICE_URL,
        layer_id=0,
        layer_name="NYS_Tax_Parcels_State_Owned",
        geometry_type="esriGeometryPolygon",
        source_role="state_owned_parcel_geometry_and_agency_attribution",
        record_type="state_owned_parcel_polygon",
        coverage="parcels identified as New York State owned across all counties",
        download_url=STATE_OWNED_DOWNLOAD_URL,
        metadata_url=STATE_OWNED_METADATA_URL,
    ),
}

FOOTPRINT_COMPONENT = Component(
    key="public-footprint",
    service_url=PUBLIC_SERVICE_URL,
    layer_id=0,
    layer_name="NYS_Tax_Parcels_Public_Footprint",
    geometry_type="esriGeometryPolygon",
    source_role="public_parcel_polygon_county_coverage_footprint",
    record_type="public_parcel_polygon_county_coverage",
    coverage="county footprints for the public parcel polygon component",
    download_url=None,
    metadata_url=POLYGON_METADATA_URL,
    required_fields=FOOTPRINT_REQUIRED_FIELDS,
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="New York",
    state_code=STATE_CODE,
)


class NYParcelError(RuntimeError):
    """Query-selection or cursor error with result-envelope semantics."""

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


@dataclass(frozen=True)
class SourceSnapshot:
    component: str
    schema_fingerprint: str
    dataset_title: str
    assessment_year: int
    publication_date: str | None
    page_size: int
    geometry_type: str


@dataclass(frozen=True)
class CursorState:
    component: str
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    consumed_count: int
    schema_fingerprint: str
    dataset_title: str


@dataclass(frozen=True)
class TraversalBatch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    consumed_count: int
    remaining_count: int
    pages_fetched: int
    snapshot: SourceSnapshot
    error: PublicRecordsError | None = None


class NYParcelClient(ArcGISRESTClient):
    """Metadata, count, and ordered feature access for one NYS component."""

    def __init__(
        self,
        component: Component,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        self.component = component
        super().__init__(
            component.layer_url,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )

    def fetch_source_metadata(self) -> Mapping[str, Any]:
        layer = self._request_json(self.layer_url, params={"f": "json"})
        item_url = f"{self.component.service_url}/info/iteminfo"
        item = self._request_json(item_url, params={"f": "json"})
        if not isinstance(layer, Mapping) or "error" in layer:
            raise SourceResponseError(
                "NYS ArcGIS returned invalid layer metadata",
                url=self.layer_url,
                details={"response": layer},
            )
        if not isinstance(item, Mapping) or "error" in item:
            raise SourceResponseError(
                "NYS ArcGIS returned invalid item metadata",
                url=item_url,
                details={"response": item},
            )
        return {"layer": layer, "item": item}

    def fetch_count(
        self,
        where: str,
        *,
        spatial_parameters: Mapping[str, Any] | None = None,
    ) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                **dict(spatial_parameters or {}),
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "NYS ArcGIS returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "NYS ArcGIS count is not a non-negative integer",
                url=self.query_url,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        spatial_parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        parameters: dict[str, Any] = {
            **dict(spatial_parameters or {}),
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "orderByFields": "OBJECTID ASC",
            "resultRecordCount": record_count,
            "f": "json",
        }
        if return_geometry:
            parameters["outSR"] = 4326
        payload = self._request_json(self.query_url, params=parameters)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "NYS ArcGIS returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "NYS ArcGIS response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)


def _source_metadata(component: Component | None) -> SourceMetadata:
    if component is None:
        return SourceMetadata(
            source_id=SOURCE_ID,
            name="New York Statewide Parcel Map Program",
            source_role="multi_component_statewide_parcel_program",
            base_url=LANDING_URL,
            dataset_id="NYS-Statewide-Parcel-Map-Program",
            metadata={
                "authority": "NYS ITS Geospatial Services",
                "coverage": "New York State",
                "update_frequency": "annual",
                "component_count": 3,
            },
        )
    return SourceMetadata(
        source_id=SOURCE_ID,
        name=f"New York Statewide Parcel Map Program: {component.key}",
        source_role=component.source_role,
        base_url=component.layer_url,
        dataset_id=(f"{component.layer_name}/FeatureServer/{component.layer_id}"),
        metadata={
            "authority": "NYS ITS Geospatial Services",
            "coverage": component.coverage,
            "update_frequency": "annual",
            "program_page": LANDING_URL,
            "component": component.key,
            "download_url": component.download_url,
        },
    )


def source_metadata(component: Component | None = None) -> SourceMetadata:
    """Return program-level or component-level source metadata."""

    return _source_metadata(component)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any, field_name: str = "query") -> str:
    text = _clean_text(value)
    if text is None:
        raise NYParcelError(
            "blank_query",
            f"{field_name} must not be blank",
        )
    return text.replace("'", "''")


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _longitude(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("longitude must be numeric") from error
    if not -180 <= number <= 180:
        raise argparse.ArgumentTypeError("longitude must be between -180 and 180")
    return number


def _latitude(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("latitude must be numeric") from error
    if not -90 <= number <= 90:
        raise argparse.ArgumentTypeError("latitude must be between -90 and 90")
    return number


def _county_identity(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    text = _sql_text(value, "county")
    digits = re.sub(r"\D", "", text)
    if text.replace("-", "").isdigit():
        if len(digits) == 5 and digits.startswith(STATE_FIPS):
            digits = digits[2:]
        if len(digits) != 3 or digits not in COUNTIES:
            raise NYParcelError(
                "invalid_county_fips",
                "county must be a New York county name, 3-digit FIPS, or 5-digit GEOID",
            )
        return f"{STATE_FIPS}{digits}", COUNTIES[digits]
    key = _name_key(re.sub(r"\bcounty\b", "", text, flags=re.I))
    identity = COUNTY_ALIASES.get(key)
    if identity is None:
        raise NYParcelError(
            "unknown_county",
            f"unknown New York county: {text}",
        )
    return identity


def _location_clauses(args: argparse.Namespace) -> list[str]:
    clauses: list[str] = []
    _county_geoid, county_name = _county_identity(getattr(args, "county", None))
    if county_name:
        clauses.append(f"UPPER(COUNTY_NAME)='{_sql_text(county_name).upper()}'")
    municipality = getattr(args, "municipality", None)
    if municipality:
        value = _sql_text(municipality, "municipality").upper()
        clauses.append(
            f"(UPPER(MUNI_NAME)='{value}' OR UPPER(CITYTOWN_NAME)='{value}')"
        )
    swis = getattr(args, "swis", None)
    if swis:
        value = _sql_text(swis, "SWIS")
        if not re.fullmatch(r"[0-9]{6}", value):
            raise NYParcelError(
                "invalid_swis",
                "SWIS must be a six-digit code",
            )
        clauses.append(f"SWIS='{value}'")
    roll_year = getattr(args, "roll_year", None)
    if roll_year is not None:
        clauses.append(f"ROLL_YR={int(roll_year)}")
    return clauses


def _selector_clause(
    operation: str,
    args: argparse.Namespace,
) -> str:
    if operation == "probe":
        return "OBJECTID > 0"
    if operation == "point":
        return "1=1"
    if operation == "native":
        return _sql_text(args.query, "native where expression")
    if operation == "deed":
        return f"BOOK={int(args.book)} AND PAGE={int(args.page)}"

    value = _sql_text(args.query).upper()
    if operation == "owner":
        return (
            f"(UPPER(PRIMARY_OWNER) LIKE '%{value}%' OR "
            f"UPPER(ADD_OWNER) LIKE '%{value}%')"
        )
    if operation == "address":
        return (
            f"(UPPER(PARCEL_ADDR) LIKE '%{value}%' OR "
            f"UPPER(LOC_STREET) LIKE '%{value}%')"
        )
    if operation == "mailing":
        return (
            f"(UPPER(MAIL_ADDR) LIKE '%{value}%' OR "
            f"UPPER(MAIL_CITY) LIKE '%{value}%' OR "
            f"UPPER(ADD_MAIL_ADDR) LIKE '%{value}%' OR "
            f"UPPER(ADD_MAIL_CITY) LIKE '%{value}%')"
        )
    if operation == "parcel":
        id_type = getattr(args, "id_type", "auto")
        if id_type == "auto":
            if re.fullmatch(r"[0-9]{26}", value):
                id_type = "swis-sbl"
            elif re.match(r"^[0-9]{6}", value) and re.search(r"[^0-9]", value[6:]):
                id_type = "swis-print-key"
            else:
                id_type = "all"
        field_by_type = {
            "swis-sbl": "SWIS_SBL_ID",
            "swis-print-key": "SWIS_PRINT_KEY_ID",
            "municipal": "MUNI_PARCEL_ID",
            "sbl": "SBL",
            "print-key": "PRINT_KEY",
        }
        field_name = field_by_type.get(id_type)
        if field_name is not None:
            return f"{field_name}='{value}'"
        return (
            f"(SWIS_SBL_ID='{value}' OR "
            f"SWIS_PRINT_KEY_ID='{value}' OR "
            f"MUNI_PARCEL_ID='{value}' OR "
            f"SBL='{value}' OR PRINT_KEY='{value}')"
        )
    if operation == "agency":
        return f"UPPER(NYS_NAME) LIKE '%{value}%'"
    if operation == "search":
        return (
            f"(UPPER(PRIMARY_OWNER) LIKE '%{value}%' OR "
            f"UPPER(ADD_OWNER) LIKE '%{value}%' OR "
            f"UPPER(PARCEL_ADDR) LIKE '%{value}%' OR "
            f"UPPER(MAIL_ADDR) LIKE '%{value}%' OR "
            f"UPPER(NYS_NAME) LIKE '%{value}%' OR "
            f"UPPER(SWIS_SBL_ID)='{value}' OR "
            f"UPPER(SWIS_PRINT_KEY_ID)='{value}' OR "
            f"UPPER(MUNI_PARCEL_ID)='{value}')"
        )
    if operation == "objectid":
        if not value.isdigit():
            raise NYParcelError(
                "invalid_object_id",
                "objectid must be numeric",
            )
        return f"OBJECTID={int(value)}"
    raise NYParcelError(
        "unsupported_operation",
        f"unsupported New York parcel operation: {operation}",
    )


def _where(operation: str, args: argparse.Namespace) -> str:
    clauses = [_selector_clause(operation, args), *_location_clauses(args)]
    return " AND ".join(f"({clause})" for clause in clauses)


def _spatial_parameters(
    operation: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if operation != "point":
        return {}
    return {
        "geometry": f"{args.longitude},{args.latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }


def _component_from_args(args: argparse.Namespace) -> Component | None:
    key = getattr(args, "collection", None)
    return COMPONENTS.get(key) if key else None


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    component = _component_from_args(args)
    operation = args.command
    parameters: dict[str, Any] = {
        "component": component.key if component else None,
    }
    for field_name in (
        "query",
        "id_type",
        "county",
        "municipality",
        "swis",
        "roll_year",
        "book",
        "page",
        "longitude",
        "latitude",
    ):
        if hasattr(args, field_name):
            parameters[field_name] = getattr(args, field_name)
    if operation not in {"alternatives", "routes", "coverage"}:
        parameters["return_geometry"] = bool(getattr(args, "geometry", False))
    return PublicRecordsQuery(
        source=_source_metadata(component),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=(
                1 if operation == "probe" else getattr(args, "limit", None)
            ),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _item_text(value: Any) -> str:
    text = _clean_text(value) or ""
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def _compatible_snapshot(
    metadata: Mapping[str, Any],
    component: Component,
) -> SourceSnapshot:
    layer = metadata.get("layer")
    item = metadata.get("item")
    if not isinstance(layer, Mapping) or not isinstance(item, Mapping):
        raise SourceSchemaError(
            "NYS parcel metadata bundle is malformed",
            url=component.layer_url,
        )

    identity = {
        "id": layer.get("id"),
        "name": layer.get("name"),
        "type": layer.get("type"),
        "object_id_field": layer.get("objectIdField"),
        "geometry_type": layer.get("geometryType"),
    }
    expected_identity = {
        "id": component.layer_id,
        "name": component.layer_name,
        "type": "Feature Layer",
        "object_id_field": "OBJECTID",
        "geometry_type": component.geometry_type,
    }
    if identity != expected_identity:
        raise SourceSchemaError(
            "NYS parcel layer identity changed",
            url=component.layer_url,
            details={"expected": expected_identity, "observed": identity},
        )

    capabilities = layer.get("advancedQueryCapabilities")
    if not isinstance(capabilities, Mapping) or any(
        capabilities.get(key) is not True
        for key in ("supportsPagination", "supportsOrderBy")
    ):
        raise SourceSchemaError(
            "NYS parcel layer no longer declares ordered pagination",
            url=component.layer_url,
        )

    fields = layer.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "NYS parcel layer metadata lacks field declarations",
            url=component.layer_url,
        )
    definitions = {
        str(field.get("name")): {
            key: field.get(key)
            for key in ("name", "type", "length", "nullable")
            if key in field
        }
        for field in fields
        if isinstance(field.get("name"), str)
    }
    missing = sorted(set(component.required_fields) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "NYS parcel layer is missing required fields",
            url=component.layer_url,
            details={"missing_fields": missing},
        )

    native_maximum = layer.get("maxRecordCount")
    if (
        isinstance(native_maximum, bool)
        or not isinstance(native_maximum, int)
        or native_maximum <= 0
    ):
        raise SourceSchemaError(
            "NYS parcel layer lacks a usable maxRecordCount",
            url=component.layer_url,
            details={"maxRecordCount": native_maximum},
        )

    title = _clean_text(item.get("title"))
    if title is None:
        raise SourceSchemaError(
            "NYS parcel item metadata lacks a dataset title",
            url=component.service_url,
        )
    year_match = re.search(r"\b(20[0-9]{2})\b", title)
    if year_match is None:
        raise SourceSchemaError(
            "NYS parcel dataset title no longer identifies an assessment year",
            url=component.service_url,
            details={"title": title},
        )
    item_type = _clean_text(item.get("type"))
    if item_type != "Map Service":
        raise SourceSchemaError(
            "NYS parcel item type changed",
            url=component.service_url,
            details={"type": item_type},
        )

    description = _item_text(item.get("description"))
    publication_match = re.search(
        r"Publication Date:\s*([A-Za-z]+\s+20[0-9]{2})",
        description,
        flags=re.I,
    )
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "component": component.key,
            "identity": identity,
            "required_fields": {
                name: definitions[name] for name in component.required_fields
            },
        }
    )
    return SourceSnapshot(
        component=component.key,
        schema_fingerprint=schema_fingerprint,
        dataset_title=title,
        assessment_year=int(year_match.group(1)),
        publication_date=(publication_match.group(1) if publication_match else None),
        page_size=native_maximum,
        geometry_type=component.geometry_type,
    )


def _criteria_fingerprint(
    *,
    component: Component,
    operation: str,
    where: str,
    spatial_parameters: Mapping[str, Any],
    return_geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "component": component.key,
            "operation": operation,
            "where": where,
            "spatial_parameters": dict(spatial_parameters),
            "return_geometry": return_geometry,
            "ordering": "OBJECTID ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "component": state.component,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "consumed": state.consumed_count,
        "schema": state.schema_fingerprint,
        "title": state.dataset_title,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(cursor: str | None) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise NYParcelError(
            "invalid_cursor",
            "cursor does not belong to the New York parcel adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
        state = CursorState(
            component=str(payload["component"]),
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            consumed_count=int(payload["consumed"]),
            schema_fingerprint=str(payload["schema"]),
            dataset_title=str(payload["title"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise NYParcelError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or state.component not in COMPONENTS
        or state.last_object_id < 0
        or state.total_count < 0
        or state.consumed_count < 0
        or state.consumed_count > state.total_count
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise NYParcelError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _object_id(feature: Mapping[str, Any], component: Component) -> int:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "NYS parcel feature lacks an attributes object",
            url=component.layer_url,
        )
    value = attributes.get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSchemaError(
            "NYS parcel feature has an invalid OBJECTID",
            url=component.layer_url,
            details={"OBJECTID": value},
        )
    return value


def _keyset_where(where: str, last_object_id: int | None) -> str:
    if last_object_id is None:
        return where
    return f"({where}) AND OBJECTID > {last_object_id}"


def _cursor_for_position(
    *,
    component: Component,
    criteria_fingerprint: str,
    last_object_id: int | None,
    total_count: int,
    consumed_count: int,
    snapshot: SourceSnapshot,
) -> str | None:
    if last_object_id is None or consumed_count >= total_count:
        return None
    return _encode_cursor(
        CursorState(
            component=component.key,
            criteria_fingerprint=criteria_fingerprint,
            last_object_id=last_object_id,
            total_count=total_count,
            consumed_count=consumed_count,
            schema_fingerprint=snapshot.schema_fingerprint,
            dataset_title=snapshot.dataset_title,
        )
    )


def _validate_cursor(
    state: CursorState | None,
    *,
    component: Component,
    criteria_fingerprint: str,
    snapshot: SourceSnapshot,
    total_count: int,
    remaining_count: int,
) -> None:
    if state is None:
        return
    mismatches: dict[str, Any] = {}
    if state.component != component.key:
        mismatches["component"] = {
            "cursor": state.component,
            "current": component.key,
        }
    if state.criteria_fingerprint != criteria_fingerprint:
        mismatches["criteria"] = "query criteria changed"
    if state.schema_fingerprint != snapshot.schema_fingerprint:
        mismatches["schema_fingerprint"] = {
            "cursor": state.schema_fingerprint,
            "current": snapshot.schema_fingerprint,
        }
    if state.dataset_title != snapshot.dataset_title:
        mismatches["dataset_title"] = {
            "cursor": state.dataset_title,
            "current": snapshot.dataset_title,
        }
    if state.total_count != total_count:
        mismatches["total_count"] = {
            "cursor": state.total_count,
            "current": total_count,
        }
    expected_remaining = state.total_count - state.consumed_count
    if remaining_count != expected_remaining:
        mismatches["remaining_count"] = {
            "cursor_expected": expected_remaining,
            "current": remaining_count,
        }
    if mismatches:
        raise NYParcelError(
            "stale_cursor",
            "source data or query criteria changed since the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=mismatches,
        )


def _traverse(
    client: Any,
    *,
    component: Component,
    operation: str,
    where: str,
    spatial_parameters: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> TraversalBatch:
    cursor_state = _decode_cursor(cursor)
    metadata = client.fetch_source_metadata()
    snapshot = _compatible_snapshot(metadata, component)
    criteria_fingerprint = _criteria_fingerprint(
        component=component,
        operation=operation,
        where=where,
        spatial_parameters=spatial_parameters,
        return_geometry=return_geometry,
    )
    total_count = client.fetch_count(
        where,
        spatial_parameters=spatial_parameters,
    )
    last_object_id = cursor_state.last_object_id if cursor_state is not None else None
    consumed_before = cursor_state.consumed_count if cursor_state is not None else 0
    remaining_before = client.fetch_count(
        _keyset_where(where, last_object_id),
        spatial_parameters=spatial_parameters,
    )
    _validate_cursor(
        cursor_state,
        component=component,
        criteria_fingerprint=criteria_fingerprint,
        snapshot=snapshot,
        total_count=total_count,
        remaining_count=remaining_before,
    )
    if cursor_state is None and remaining_before != total_count:
        raise SourceSchemaError(
            "NYS parcel count changed during query initialization",
            url=component.layer_url,
            details={
                "full_count": total_count,
                "remaining_count": remaining_before,
            },
        )

    desired_count = remaining_before
    if limit is not None:
        desired_count = min(desired_count, limit)
    page_size = min(client.page_size, snapshot.page_size)
    records: list[Mapping[str, Any]] = []
    pages_fetched = 0

    try:
        while len(records) < desired_count:
            request_count = min(
                page_size,
                desired_count - len(records),
            )
            page = client.fetch_page(
                where=_keyset_where(where, last_object_id),
                record_count=request_count,
                return_geometry=return_geometry,
                spatial_parameters=spatial_parameters,
            )
            pages_fetched += 1
            if not page:
                raise SourceSchemaError(
                    "NYS parcel traversal ended before the reported count",
                    url=component.layer_url,
                    details={
                        "reported_remaining": remaining_before,
                        "records_received": len(records),
                    },
                )
            page_ids = [_object_id(feature, component) for feature in page]
            if page_ids != sorted(page_ids) or len(page_ids) != len(set(page_ids)):
                raise SourceSchemaError(
                    "NYS parcel page is not uniquely ordered by OBJECTID",
                    url=component.layer_url,
                    details={"object_ids": page_ids},
                )
            if last_object_id is not None and page_ids[0] <= last_object_id:
                raise SourceSchemaError(
                    "NYS parcel keyset traversal did not advance",
                    url=component.layer_url,
                    details={
                        "previous_object_id": last_object_id,
                        "next_object_id": page_ids[0],
                    },
                )
            records.extend(page)
            last_object_id = page_ids[-1]

        consumed_count = consumed_before + len(records)
        remaining_count = client.fetch_count(
            _keyset_where(where, last_object_id),
            spatial_parameters=spatial_parameters,
        )
        final_total = client.fetch_count(
            where,
            spatial_parameters=spatial_parameters,
        )
        final_snapshot = _compatible_snapshot(
            client.fetch_source_metadata(),
            component,
        )
        expected_remaining = total_count - consumed_count
        changes: dict[str, Any] = {}
        if final_snapshot != snapshot:
            changes["snapshot"] = {
                "before": {
                    "schema_fingerprint": snapshot.schema_fingerprint,
                    "dataset_title": snapshot.dataset_title,
                    "publication_date": snapshot.publication_date,
                },
                "after": {
                    "schema_fingerprint": final_snapshot.schema_fingerprint,
                    "dataset_title": final_snapshot.dataset_title,
                    "publication_date": final_snapshot.publication_date,
                },
            }
        if final_total != total_count:
            changes["total_count"] = {
                "before": total_count,
                "after": final_total,
            }
        if remaining_count != expected_remaining:
            changes["remaining_count"] = {
                "expected": expected_remaining,
                "observed": remaining_count,
            }
        if changes:
            raise SourceSchemaError(
                "NYS parcel dataset changed during traversal",
                url=component.layer_url,
                details=changes,
            )
    except PublicRecordsHTTPError as error:
        if not records:
            raise
        consumed_count = consumed_before + len(records)
        remaining_count = max(total_count - consumed_count, 0)
        return TraversalBatch(
            records=tuple(records),
            next_cursor=_cursor_for_position(
                component=component,
                criteria_fingerprint=criteria_fingerprint,
                last_object_id=last_object_id,
                total_count=total_count,
                consumed_count=consumed_count,
                snapshot=snapshot,
            ),
            total_count=total_count,
            consumed_count=consumed_count,
            remaining_count=remaining_count,
            pages_fetched=pages_fetched,
            snapshot=snapshot,
            error=error.to_contract_error(),
        )

    return TraversalBatch(
        records=tuple(records),
        next_cursor=_cursor_for_position(
            component=component,
            criteria_fingerprint=criteria_fingerprint,
            last_object_id=last_object_id,
            total_count=total_count,
            consumed_count=consumed_count,
            snapshot=snapshot,
        ),
        total_count=total_count,
        consumed_count=consumed_count,
        remaining_count=remaining_count,
        pages_fetched=pages_fetched,
        snapshot=snapshot,
    )


def _source_snapshot_record(batch: TraversalBatch) -> dict[str, Any]:
    return {
        "component": batch.snapshot.component,
        "dataset_title": batch.snapshot.dataset_title,
        "assessment_year": batch.snapshot.assessment_year,
        "publication_date": batch.snapshot.publication_date,
        "schema_fingerprint": batch.snapshot.schema_fingerprint,
        "reported_total_matches": batch.total_count,
        "consumed_through_this_result": batch.consumed_count,
        "remaining_after_this_result": batch.remaining_count,
        "pages_fetched": batch.pages_fetched,
    }


def _county_from_attributes(
    attributes: Mapping[str, Any],
) -> tuple[str, str | None]:
    county_name = _clean_text(attributes.get("COUNTY_NAME"))
    if county_name is None:
        return STATE_FIPS, None
    identity = COUNTY_ALIASES.get(_name_key(county_name))
    if identity is None:
        return STATE_FIPS, county_name
    return identity


def _owner_observations(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for role, field_name in (
        ("primary_owner", "PRIMARY_OWNER"),
        ("additional_owner", "ADD_OWNER"),
    ):
        name = _clean_text(attributes.get(field_name))
        if name is not None:
            observations.append(
                {
                    "role": role,
                    "raw_name": name,
                    "source_field": field_name,
                }
            )
    return observations


def _mailing_address(
    attributes: Mapping[str, Any],
    *,
    additional: bool,
) -> dict[str, Any]:
    if additional:
        fields = {
            "street": "ADD_MAIL_ADDR",
            "po_box": "ADD_MAIL_PO_BOX",
            "city": "ADD_MAIL_CITY",
            "state": "ADD_MAIL_STATE",
            "postal_code": "ADD_MAIL_ZIP",
        }
    else:
        fields = {
            "street": "MAIL_ADDR",
            "po_box": "PO_BOX",
            "city": "MAIL_CITY",
            "state": "MAIL_STATE",
            "postal_code": "MAIL_ZIP",
        }
    return {
        key: _clean_text(attributes.get(field_name))
        for key, field_name in fields.items()
    }


def _native_id(
    attributes: Mapping[str, Any],
    object_id: int,
) -> tuple[str, str]:
    for identifier_type, field_name in (
        ("swis_sbl_id", "SWIS_SBL_ID"),
        ("swis_print_key_id", "SWIS_PRINT_KEY_ID"),
        ("municipal_parcel_id", "MUNI_PARCEL_ID"),
    ):
        value = _clean_text(attributes.get(field_name))
        if value is not None:
            return value, identifier_type
    swis = _clean_text(attributes.get("SWIS"))
    sbl = _clean_text(attributes.get("SBL"))
    if swis and sbl:
        return f"{swis}{sbl}", "constructed_swis_sbl"
    return str(object_id), "object_id"


def _geometry_role(component: Component) -> str:
    if component.key == "centroids":
        return "mathematically_derived_point_within_parcel"
    if component.key == "state-owned":
        return "county_contributed_state_owned_parcel_polygon"
    return "county_contributed_public_parcel_polygon"


def _normalize_feature(
    feature: Mapping[str, Any],
    batch: TraversalBatch,
    component: Component,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise SourceSchemaError(
            "NYS parcel feature lacks attributes",
            url=component.layer_url,
        )
    attributes = dict(attributes_value)
    object_id = _object_id(feature, component)
    county_geoid, county_name = _county_from_attributes(attributes)
    native_id, native_id_type = _native_id(attributes, object_id)
    owner_type = _clean_text(attributes.get("OWNER_TYPE"))
    swis_sbl_id = _clean_text(attributes.get("SWIS_SBL_ID"))
    swis_print_key_id = _clean_text(attributes.get("SWIS_PRINT_KEY_ID"))
    municipal_parcel_id = _clean_text(attributes.get("MUNI_PARCEL_ID"))

    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county_geoid,
            "parcel",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": (f"{component.layer_name}/FeatureServer/{component.layer_id}"),
        "component": component.key,
        "component_role": component.source_role,
        "component_coverage": component.coverage,
        "record_type": component.record_type,
        "native_id": native_id,
        "native_id_type": native_id_type,
        "object_id": object_id,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": county_name,
            "county_geoid": county_geoid,
            "municipality": _clean_text(attributes.get("MUNI_NAME")),
            "city_or_town": _clean_text(attributes.get("CITYTOWN_NAME")),
        },
        "parcel_identifiers": {
            "swis": _clean_text(attributes.get("SWIS")),
            "sbl": _clean_text(attributes.get("SBL")),
            "print_key": _clean_text(attributes.get("PRINT_KEY")),
            "citytown_swis": _clean_text(attributes.get("CITYTOWN_SWIS")),
            "municipal_parcel_id": municipal_parcel_id,
            "swis_sbl_id": swis_sbl_id,
            "swis_print_key_id": swis_print_key_id,
        },
        "cross_component_join_keys": [
            {
                "field": field_name,
                "value": value,
            }
            for field_name, value in (
                ("SWIS_SBL_ID", swis_sbl_id),
                ("SWIS_PRINT_KEY_ID", swis_print_key_id),
                ("MUNI_PARCEL_ID", municipal_parcel_id),
            )
            if value is not None
        ],
        "owners": _owner_observations(attributes),
        "owner_type": {
            "code": owner_type,
            "description": OWNER_TYPE_DESCRIPTIONS.get(owner_type or ""),
        },
        "state_ownership": {
            "agency_name": _clean_text(attributes.get("NYS_NAME")),
            "agency_name_source_code": _clean_text(attributes.get("NYS_NAME_SOURCE")),
            "source_classifies_as_state_owned": owner_type == "2",
        },
        "situs_address": {
            "raw": _clean_text(attributes.get("PARCEL_ADDR")),
            "street_number": _clean_text(attributes.get("LOC_ST_NBR")),
            "street": _clean_text(attributes.get("LOC_STREET")),
            "unit": _clean_text(attributes.get("LOC_UNIT")),
            "postal_code": _clean_text(attributes.get("LOC_ZIP")),
            "state": STATE_CODE,
        },
        "mailing_addresses": {
            "primary_owner": _mailing_address(
                attributes,
                additional=False,
            ),
            "additional_owner": _mailing_address(
                attributes,
                additional=True,
            ),
        },
        "assessment": {
            "roll_year": attributes.get("ROLL_YR"),
            "roll_section": _clean_text(attributes.get("ROLL_SECTION")),
            "property_class": _clean_text(attributes.get("PROP_CLASS")),
            "land_assessed_value": attributes.get("LAND_AV"),
            "total_assessed_value": attributes.get("TOTAL_AV"),
            "full_market_value": attributes.get("FULL_MARKET_VAL"),
            "currency": "USD",
        },
        "property_characteristics": {
            "year_built": attributes.get("YR_BLT"),
            "assessed_square_feet": attributes.get("SQ_FT"),
            "living_square_feet": attributes.get("SQFT_LIVING"),
            "gross_floor_area": attributes.get("GFA"),
            "assessed_acres": attributes.get("ACRES"),
            "calculated_gis_acres": attributes.get("CALC_ACRES"),
            "bedrooms": attributes.get("NBR_BEDROOMS"),
            "full_bathrooms": attributes.get("NBR_FULL_BATHS"),
            "building_style": _clean_text(attributes.get("BLDG_STYLE_DESC")),
            "primary_commercial_use": _clean_text(attributes.get("USED_AS_DESC")),
        },
        "deed_reference": {
            "book": attributes.get("BOOK"),
            "page": attributes.get("PAGE"),
            "source_scope": "recent-sale window in annual parcel product",
        },
        "source_dates": {
            "assessment_roll_year": attributes.get("ROLL_YR"),
            "spatial_year": attributes.get("SPATIAL_YR"),
        },
        "geometry_flags": {
            "duplicate_geometry": (
                (_clean_text(attributes.get("DUP_GEO")) or "").upper() == "Y"
            ),
            "duplicate_geometry_raw": _clean_text(attributes.get("DUP_GEO")),
        },
        "source_record_url": f"{component.layer_url}/{object_id}",
        "related_official_routes": {
            "program_and_county_resources": LANDING_URL,
            "standardized_data_dictionary": DATA_DICTIONARY_URL,
            "property_transfer_search": MUNICIPAL_DATA_PORTAL_URL,
            "web_service_migration_status": MIGRATION_URL,
        },
        "source_snapshot": _source_snapshot_record(batch),
        "raw_attributes": attributes,
    }
    if geometry_requested and "geometry" in feature:
        result.update(
            {
                "geometry": feature.get("geometry"),
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_role": _geometry_role(component),
            }
        )
    return result


def _alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "centroid-feature-service",
            "name": "NYS Tax Parcel Centroid Points",
            "url": COMPONENTS["centroids"].layer_url,
            "authority": "NYS ITS Geospatial Services",
            "access": "anonymous ArcGIS FeatureServer",
            "record_role": (
                "all-county owner, address, assessment, parcel identifier, "
                "and centroid index"
            ),
            "coverage": "all 62 counties",
            "join_keys": [
                "SWIS_SBL_ID",
                "SWIS_PRINT_KEY_ID",
                "MUNI_PARCEL_ID",
            ],
            "relationship_to_primary": "primary statewide search component",
        },
        {
            "route_id": "public-polygon-feature-service",
            "name": "NYS Tax Parcels - Public",
            "url": COMPONENTS["public-parcels"].layer_url,
            "authority": "NYS ITS Geospatial Services",
            "access": "anonymous ArcGIS FeatureServer",
            "record_role": "parcel boundary geometry plus assessment attributes",
            "coverage": "counties authorizing statewide redistribution",
            "join_keys": [
                "SWIS_SBL_ID",
                "SWIS_PRINT_KEY_ID",
                "MUNI_PARCEL_ID",
            ],
            "relationship_to_primary": (
                "geometry complement to the statewide centroid index"
            ),
        },
        {
            "route_id": "state-owned-feature-service",
            "name": "NYS Tax Parcels - State Owned",
            "url": COMPONENTS["state-owned"].layer_url,
            "authority": "NYS ITS Geospatial Services",
            "access": "anonymous ArcGIS FeatureServer",
            "record_role": (
                "state-owned parcel subset and owning or operating agency attribution"
            ),
            "coverage": "all 62 counties",
            "join_keys": [
                "SWIS_SBL_ID",
                "SWIS_PRINT_KEY_ID",
                "MUNI_PARCEL_ID",
            ],
            "relationship_to_primary": (
                "government-ownership classification complement"
            ),
        },
        {
            "route_id": "official-bulk-downloads",
            "name": "Current statewide parcel bulk downloads",
            "url": LANDING_URL,
            "direct_downloads": {
                "public_parcels": PUBLIC_DOWNLOAD_URL,
                "centroid_points": CENTROID_DOWNLOAD_URL,
                "state_owned_parcels": STATE_OWNED_DOWNLOAD_URL,
            },
            "authority": "NYS ITS Geospatial Services",
            "access": "anonymous ZIP downloads",
            "record_role": "full annual snapshots and bulk ingestion",
            "join_keys": [
                "SWIS_SBL_ID",
                "SWIS_PRINT_KEY_ID",
                "MUNI_PARCEL_ID",
            ],
            "relationship_to_primary": (
                "same-source transport and snapshot alternative"
            ),
        },
        {
            "route_id": "county-parcel-resource-directory",
            "name": "County Parcel Data Resources",
            "url": LANDING_URL,
            "authority": "NYS ITS Geospatial Services",
            "access": "official directory of county data, viewers, and resources",
            "record_role": (
                "local parcel geometry, assessment, tax, and current county detail"
            ),
            "coverage": "all New York counties",
            "join_keys": ["county", "SWIS", "SBL", "PRINT_KEY", "address"],
            "relationship_to_primary": (
                "upstream local route when central polygon coverage or "
                "freshness is insufficient"
            ),
        },
        {
            "route_id": "orpts-sales-web",
            "name": "ORPTS Sales Web",
            "url": MUNICIPAL_DATA_PORTAL_URL,
            "application_url": SALES_WEB_APP_URL,
            "authority": "NYS Department of Taxation and Finance, ORPTS",
            "access": "public web application with search-result download",
            "record_role": (
                "ten years of weekly-updated real-property transfers outside "
                "New York City"
            ),
            "coverage": "New York State excluding New York City",
            "join_keys": [
                "tax map ID",
                "county",
                "book",
                "page",
                "address",
                "buyer",
                "seller",
            ],
            "relationship_to_primary": (
                "transfer-history complement to annual ownership observations"
            ),
        },
        {
            "route_id": "nyc-acris",
            "name": "NYC Automated City Register Information System",
            "url": ACRIS_URL,
            "authority": "New York City Department of Finance",
            "access": "public search, document images, and electronic data services",
            "record_role": "deeds and other recorded real-property documents",
            "coverage": (
                "recorded documents for Manhattan, Queens, Bronx, and "
                "Brooklyn; NYC transfer-tax workflows also include Staten Island"
            ),
            "join_keys": [
                "borough-block-lot",
                "address",
                "document ID",
                "party name",
            ],
            "relationship_to_primary": (
                "NYC instrument-level and transfer-history complement"
            ),
        },
        {
            "route_id": "nys-ogs-land-records",
            "name": "NYS OGS Land Records and Maps",
            "url": OGS_LAND_RECORDS_URL,
            "authority": "New York State Office of General Services",
            "access": "public holdings description and record request route",
            "record_role": (
                "historic and current state-land maps, patents, deeds, and title papers"
            ),
            "coverage": "New York State-owned land records",
            "join_keys": [
                "state agency",
                "county",
                "location",
                "map",
                "deed or patent",
            ],
            "relationship_to_primary": (
                "document and historical complement for state-owned parcels"
            ),
        },
        {
            "route_id": "assessment-coordinate-lookup",
            "name": "NYS Assessment Look-Up Tool",
            "url": ASSESSMENT_LOOKUP_URL,
            "authority": "NYS ITS Geospatial Services",
            "access": "anonymous synchronous ArcGIS geoprocessing task",
            "record_role": "coordinate-to-assessment lookup",
            "coverage": "described by the state as statewide",
            "observed_status": (
                "2026-07-30 probes reported a coordinate match but returned "
                "blank assessment output fields"
            ),
            "relationship_to_primary": (
                "spatial lookup route to re-probe; not used by this adapter's "
                "data path while outputs are blank"
            ),
        },
        {
            "route_id": "service-migration-status",
            "name": "NYS GIS web-service migration status",
            "url": MIGRATION_URL,
            "authority": "NYS ITS Geospatial Services",
            "access": "public status page",
            "record_role": "current and successor service discovery",
            "relationship_to_primary": (
                "official endpoint-change control for the parcel services"
            ),
        },
        {
            "route_id": "standardized-data-dictionary",
            "name": "NYS Tax Parcels Data Dictionary",
            "url": DATA_DICTIONARY_URL,
            "authority": "NYS ITS Geospatial Services",
            "access": "public PDF",
            "record_role": "field meanings, identifiers, and owner-type codes",
            "relationship_to_primary": "official schema documentation",
        },
    ]


def alternative_routes() -> list[dict[str, Any]]:
    """Return the official parcel-program and complementary source routes."""

    return _alternative_routes()


def _component_coverage_record(
    client: Any,
    component: Component,
) -> dict[str, Any]:
    before = _compatible_snapshot(
        client.fetch_source_metadata(),
        component,
    )
    count = client.fetch_count("1=1", spatial_parameters={})
    after = _compatible_snapshot(
        client.fetch_source_metadata(),
        component,
    )
    if before != after:
        raise SourceSchemaError(
            "NYS parcel component changed during coverage count",
            url=component.layer_url,
            details={
                "component": component.key,
                "before": before.dataset_title,
                "after": after.dataset_title,
            },
        )
    return {
        "component": component.key,
        "layer_url": component.layer_url,
        "source_role": component.source_role,
        "coverage": component.coverage,
        "record_count": count,
        "geometry_type": component.geometry_type,
        "dataset_title": before.dataset_title,
        "assessment_year": before.assessment_year,
        "publication_date": before.publication_date,
        "schema_fingerprint": before.schema_fingerprint,
        "native_max_record_count": before.page_size,
        "bulk_download_url": component.download_url,
    }


def _coverage_summary(
    client_factory: Callable[[Component], Any],
) -> dict[str, Any]:
    components = [
        _component_coverage_record(client_factory(component), component)
        for component in COMPONENTS.values()
    ]
    footprint_client = client_factory(FOOTPRINT_COMPONENT)
    footprint_batch = _traverse(
        footprint_client,
        component=FOOTPRINT_COMPONENT,
        operation="coverage",
        where="1=1",
        spatial_parameters={},
        limit=None,
        cursor=None,
        return_geometry=False,
    )
    counties: list[dict[str, Any]] = []
    for feature in footprint_batch.records:
        attributes = feature.get("attributes")
        if not isinstance(attributes, Mapping):
            raise SourceSchemaError(
                "NYS public parcel footprint feature lacks attributes",
                url=FOOTPRINT_COMPONENT.layer_url,
            )
        name = _clean_text(attributes.get("NAME"))
        county_fips = _clean_text(attributes.get("COUNTY_FIPS"))
        if name is None or county_fips is None:
            raise SourceSchemaError(
                "NYS public parcel footprint lacks county identity",
                url=FOOTPRINT_COMPONENT.layer_url,
                details={"attributes": dict(attributes)},
            )
        counties.append(
            {
                "county_name": name,
                "county_fips": county_fips,
                "county_geoid": f"{STATE_FIPS}{county_fips}",
                "countywide_swis": _clean_text(attributes.get("SWIS")),
            }
        )
    counties.sort(key=lambda record: record["county_name"])
    return {
        "source_id": SOURCE_ID,
        "program": "New York Statewide Parcel Map Program",
        "program_url": LANDING_URL,
        "update_frequency": "annual",
        "component_counts": components,
        "centroid_county_coverage": {
            "county_count": 62,
            "coverage_basis": ("official program and current service metadata"),
        },
        "public_polygon_county_coverage": {
            "county_count": len(counties),
            "counties": counties,
            "footprint_layer_url": FOOTPRINT_COMPONENT.layer_url,
        },
        "state_owned_county_coverage": {
            "county_count": 62,
            "coverage_basis": ("official program and current service metadata"),
        },
        "cross_component_join_keys": [
            "SWIS_SBL_ID",
            "SWIS_PRINT_KEY_ID",
            "MUNI_PARCEL_ID",
        ],
        "coverage_routing": {
            "attributes_all_counties": COMPONENTS["centroids"].layer_url,
            "public_geometry": COMPONENTS["public-parcels"].layer_url,
            "state_owned_geometry": COMPONENTS["state-owned"].layer_url,
            "county_sources": LANDING_URL,
            "transfer_history": MUNICIPAL_DATA_PORTAL_URL,
            "recorded_documents_nyc": ACRIS_URL,
        },
    }


def _client_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "page_size": args.page_size,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "retry_attempts": args.retry_attempts,
    }


def _result_from_batch(
    query: PublicRecordsQuery,
    batch: TraversalBatch,
    records: Sequence[Mapping[str, Any]],
) -> PublicRecordsResult:
    if batch.error is not None:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [batch.error],
            records=records,
            next_cursor=batch.next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    client_factory: Callable[[Component], Any] | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    operation = args.command
    component = _component_from_args(args)
    try:
        if operation in {"alternatives", "routes"}:
            result = PublicRecordsResult.success(
                query,
                _alternative_routes(),
            )
        elif operation == "coverage":
            factory = client_factory or (
                lambda selected: NYParcelClient(
                    selected,
                    **_client_args(args),
                )
            )
            result = PublicRecordsResult.success(
                query,
                [_coverage_summary(factory)],
                warnings=SOURCE_WARNINGS,
            )
        else:
            if component is None:
                raise NYParcelError(
                    "missing_component",
                    "a parcel component is required",
                )
            where = _where(operation, args)
            spatial_parameters = _spatial_parameters(operation, args)
            source_client = client or NYParcelClient(
                component,
                **_client_args(args),
            )
            batch = _traverse(
                source_client,
                component=component,
                operation=operation,
                where=where,
                spatial_parameters=spatial_parameters,
                limit=(1 if operation == "probe" else getattr(args, "limit", None)),
                cursor=getattr(args, "cursor", None),
                return_geometry=bool(getattr(args, "geometry", False)),
            )
            records = [
                _normalize_feature(
                    feature,
                    batch,
                    component,
                    geometry_requested=bool(getattr(args, "geometry", False)),
                )
                for feature in batch.records
            ]
            result = _result_from_batch(query, batch, records)
    except NYParcelError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=SOURCE_WARNINGS,
        )
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )

    result_count = (
        len(result.records)
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else None
    )
    log_search(
        canonical_json(query.to_dict()),
        query.source.source_id,
        result_count,
    )
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(f"New York statewide parcels {args.command} ({result.status.value})"),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"New York statewide parcels {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command in {"alternatives", "routes"}:
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "coverage":
            public = record["public_polygon_county_coverage"]
            print(
                "  statewide centroids | "
                f"public polygons in {public['county_count']} counties | "
                "state-owned subset"
            )
        else:
            owners = ", ".join(owner["raw_name"] for owner in record["owners"])
            print(
                f"  {record['native_id']} | "
                f"{record['situs_address']['raw'] or '?'} | "
                f"{owners or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_network_args(
    parser: argparse.ArgumentParser,
    *,
    default_collection: str = "centroids",
) -> None:
    parser.add_argument(
        "--collection",
        choices=tuple(COMPONENTS),
        default=default_collection,
        help="NYS parcel component to query",
    )
    parser.add_argument(
        "--county",
        help="County name, 3-digit FIPS, or 5-digit GEOID",
    )
    parser.add_argument(
        "--municipality",
        help="Optional municipality, city, or town name",
    )
    parser.add_argument("--swis", help="Optional six-digit SWIS code")
    parser.add_argument(
        "--roll-year",
        type=_positive_int,
        help="Optional assessment roll year",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional result bound; omitted traverses every native match",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor returned by a prior bounded query",
    )
    parser.add_argument(
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Return source geometry transformed to EPSG:4326",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Transport batch size, bounded by live source metadata",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
    )
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


def _add_coverage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
    )
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query New York's official Statewide Parcel Map Program")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("owner", "Search primary and additional owner observations"),
        ("address", "Search parcel situs-address observations"),
        ("mailing", "Search owner mailing-address observations"),
        ("parcel", "Look up standardized or municipal parcel identifiers"),
        ("agency", "Search NYS owning or operating agency attribution"),
        ("search", "Search owner, address, agency, and parcel identifiers"),
        ("objectid", "Look up a component-native ArcGIS OBJECTID"),
        ("native", "Run a source-native ArcGIS where expression"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        if command == "parcel":
            command_parser.add_argument(
                "--id-type",
                choices=(
                    "auto",
                    "swis-sbl",
                    "swis-print-key",
                    "municipal",
                    "sbl",
                    "print-key",
                    "all",
                ),
                default="auto",
                help=("Identifier field; auto recognizes standardized SWIS join keys"),
            )
        _add_network_args(
            command_parser,
            default_collection=("state-owned" if command == "agency" else "centroids"),
        )

    deed = subparsers.add_parser(
        "deed",
        help="Search the parcel product's recent-sale book and page fields",
    )
    deed.add_argument("book", type=_positive_int)
    deed.add_argument("page", type=_positive_int)
    _add_network_args(deed)

    point = subparsers.add_parser(
        "point",
        help="Find a public or state-owned parcel polygon intersecting a point",
    )
    point.add_argument("longitude", type=_longitude)
    point.add_argument("latitude", type=_latitude)
    _add_network_args(point, default_collection="public-parcels")

    probe = subparsers.add_parser(
        "probe",
        help="Verify a component with its first ordered record",
    )
    _add_network_args(probe)

    coverage = subparsers.add_parser(
        "coverage",
        help="Report live component counts and public-polygon county coverage",
    )
    _add_coverage_args(coverage)

    for command in ("alternatives", "routes"):
        alternatives = subparsers.add_parser(
            command,
            help=(
                "List official parcel, local, transfer, deed, bulk, and "
                "migration routes"
            ),
        )
        add_output_args(alternatives)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    timeout = getattr(args, "timeout", None)
    if timeout is not None and timeout <= 0:
        parser.error("timeout must be positive")
    minimum_interval = getattr(args, "minimum_interval", None)
    if minimum_interval is not None and minimum_interval < 0:
        parser.error("minimum-interval must not be negative")
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
