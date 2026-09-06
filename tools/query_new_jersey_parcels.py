#!/usr/bin/env python3
"""Query New Jersey's official statewide parcels and MOD-IV composite.

NJGIN publishes an ArcGIS Online feature service containing statewide parcel
polygons joined, where possible, to annual MOD-IV assessment records.  The
official NJGIN landing page points to the current ArcGIS item; this adapter
resolves that item before every query so a service migration is visible and
does not leave a stale endpoint hidden in code.

Owner names are blank in the hosted source under NJGIN's published Daniel's
Law redaction.  Other useful fields remain available, including parcel and tax
identifiers, situs and mailing addresses, assessed values, last-year tax,
property classification, sale price, deed references, dates, and geometry.

Omitting ``--limit`` exhausts every native match for the selected query.
``--page-size`` only controls transport batches and is bounded by live source
metadata.

Examples:
    uv run python tools/query_new_jersey_parcels.py pin \
        1225_299_1.02_C0304 --geometry
    uv run python tools/query_new_jersey_parcels.py address \
        "304 MAPLE HILL DR" --county Middlesex
    uv run python tools/query_new_jersey_parcels.py block-lot \
        --municipality-code 1225 --block 299 --lot 1.02 --qualifier C0304
    uv run python tools/query_new_jersey_parcels.py search \
        --county Essex --has-modiv no --limit 20
    uv run python tools/query_new_jersey_parcels.py point \
        -74.30143 40.55346
    uv run python tools/query_new_jersey_parcels.py alternatives --json
    uv run python tools/query_new_jersey_parcels.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

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


SOURCE_ID = "us-nj-njgin-parcels-modiv"
STATE_CODE = "NJ"
STATE_FIPS = "34"
JURISDICTION_GEOID = "34"

LANDING_URL = "https://www.nj.gov/njgin/edata/parcels/"
ITEM_ID = "533599bbfbaa4748bf39faf1375a8a9c"
ITEM_PAGE_URL = (
    "https://newjersey.maps.arcgis.com/home/item.html"
    f"?id={ITEM_ID}"
)
ITEM_API_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ITEM_ID}"
)
DEFAULT_SERVICE_URL = (
    "https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/arcgis/rest/services/"
    "Parcels_Composite_NJ_WM/FeatureServer"
)
DEFAULT_LAYER_URL = f"{DEFAULT_SERVICE_URL}/0"

PROPERTY_EXPLORER_URL = (
    "https://newjersey.maps.arcgis.com/apps/webappviewer/index.html"
    "?id=3a4290e1b3d64094a8b8a127965ab43a"
)
NJGIN_STATEWIDE_DOWNLOAD_URL = (
    "https://njogis-newjersey.opendata.arcgis.com/documents/"
    "newjersey::parcels-and-mod-iv-composite-of-nj-download/about"
)
NJGIN_PARCELS_ONLY_URL = (
    "https://njogis-newjersey.opendata.arcgis.com/documents/"
    "d543ddcc1e6844319ffa826fee52fccf/about"
)
NJGIN_MODIV_DOWNLOAD_URL = (
    "https://njogis-newjersey.opendata.arcgis.com/documents/"
    "property-tax-list-mod-iv-of-nj-fgdb-download/about"
)
TREASURY_STATISTICS_URL = (
    "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml"
)
TREASURY_MODIV_OBSERVED_2026_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/modiv-2026.zip"
)
TREASURY_SR1A_OBSERVED_YTD_2026_URL = (
    "https://www.nj.gov/treasury/taxation/lpt/statdata/"
    "YTDSR1A2026.zip"
)
TREASURY_SR1A_LAYOUT_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/"
    "SR1Afilelayout.pdf"
)
ASSESSOR_DIRECTORY_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/"
    "assessor/statewidebycounty.pdf"
)
COUNTY_TAX_BOARD_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/"
    "CountyBoardsofTaxation.pdf"
)
COUNTY_RECORDER_RETENTION_URL = (
    "https://nj.gov/treasury/revenue/rms/pdf/C100000-010.pdf"
)
STATE_ARCHIVES_COUNTY_URL = (
    "https://www.nj.gov/state/archives/catcounty.html"
)
OPRA_URL = "https://www.nj.gov/opra/home/request-records.shtml"

PROBE_PIN = "1225_299_1.02_C0304"
PROBE_ADDRESS = "304 MAPLE HILL DR"
SOURCE_LAYER_NAME = "Cad_parcel_mod4"
SOURCE_GEOMETRY_TYPE = "esriGeometryPolygon"
DEFAULT_PAGE_SIZE = 2_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "njgin-parcels:v1:"
CURSOR_VERSION = 1

REQUIRED_FIELDS = (
    "OBJECTID",
    "PAMS_PIN",
    "PCL_MUN",
    "PCLBLOCK",
    "PCLLOT",
    "PCLQCODE",
    "PCLLASTUPD",
    "PIN_NODUP",
    "GIS_PIN",
    "CD_CODE",
    "PROP_CLASS",
    "COUNTY",
    "MUN_NAME",
    "PROP_LOC",
    "OWNER_NAME",
    "ST_ADDRESS",
    "CITY_STATE",
    "ZIP_CODE",
    "LAND_VAL",
    "IMPRVT_VAL",
    "NET_VALUE",
    "LAST_YR_TX",
    "BLDG_DESC",
    "LAND_DESC",
    "CALC_ACRE",
    "ADD_LOTS1",
    "ADD_LOTS2",
    "FAC_NAME",
    "PROP_USE",
    "BLDG_CLASS",
    "DEED_BOOK",
    "DEED_PAGE",
    "DEED_DATE",
    "YR_CONSTR",
    "SALES_CODE",
    "SALE_PRICE",
    "DWELL",
    "COMM_DWELL",
    "OLD_PROPID",
    "ZIP5",
    "ZIP_PLUS4",
    "PCL_PBDATE",
    "PCL_GUID",
)

COUNTIES = {
    "01": ("Atlantic", "34001"),
    "02": ("Bergen", "34003"),
    "03": ("Burlington", "34005"),
    "04": ("Camden", "34007"),
    "05": ("Cape May", "34009"),
    "06": ("Cumberland", "34011"),
    "07": ("Essex", "34013"),
    "08": ("Gloucester", "34015"),
    "09": ("Hudson", "34017"),
    "10": ("Hunterdon", "34019"),
    "11": ("Mercer", "34021"),
    "12": ("Middlesex", "34023"),
    "13": ("Monmouth", "34025"),
    "14": ("Morris", "34027"),
    "15": ("Ocean", "34029"),
    "16": ("Passaic", "34031"),
    "17": ("Salem", "34033"),
    "18": ("Somerset", "34035"),
    "19": ("Sussex", "34037"),
    "20": ("Union", "34039"),
    "21": ("Warren", "34041"),
}
COUNTY_ALIASES = {
    re.sub(r"[^a-z0-9]", "", name.lower()): code
    for code, (name, _geoid) in COUNTIES.items()
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="NJGIN Parcels and MOD-IV Composite of New Jersey",
    source_role="statewide_parcel_geometry_assessment_tax_sale_index",
    base_url=LANDING_URL,
    dataset_id=f"{ITEM_ID}/0",
    metadata={
        "authority": (
            "New Jersey Office of Information Technology, Office of GIS"
        ),
        "operator": "NJ Geographic Information Network",
        "arcgis_item_id": ITEM_ID,
        "arcgis_item_api": ITEM_API_URL,
        "current_service_resolved_at_runtime": True,
        "coverage": "New Jersey statewide parcel composite",
        "geometry_role": "approximate planning parcel polygon",
        "owner_name_visibility": "redacted_by_source",
        "parcel_modiv_join": "partial",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-nj",
    name="New Jersey",
    state_code=STATE_CODE,
    metadata={
        "state_fips": STATE_FIPS,
        "county_count": 21,
        "parcel_municipality_code": "PCL_MUN",
    },
)

SOURCE_WARNINGS = (
    "NJGIN publishes OWNER_NAME as blank under its Daniel's Law redaction; "
    "a blank field is a source-visibility state, not a finding that the "
    "parcel lacks an owner.",
    "Some parcel polygons do not have a matched MOD-IV row. PCL_MUN and the "
    "parcel identifiers remain useful when denormalized assessment fields "
    "are null.",
    "County and municipal contributors have different update dates; retain "
    "PCLLASTUPD and PCL_PBDATE for each record.",
    "The source describes its polygons as planning representations rather "
    "than legal survey boundaries.",
    "Sale and deed fields are index attributes. County-recorded instruments "
    "remain the document-level title evidence.",
)


class NewJerseyParcelError(RuntimeError):
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


@dataclass(frozen=True)
class Selection:
    where: str
    spatial_parameters: Mapping[str, Any]
    coverage_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceSnapshot:
    schema_fingerprint: str
    dataset_version: int | None
    item_modified: int | None
    layer_url: str
    native_page_size: int
    metadata: Mapping[str, Any]
    item_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    schema_fingerprint: str
    dataset_version: int | None
    layer_url: str


@dataclass(frozen=True)
class TraversalBatch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    remaining_count: int
    pages_fetched: int
    snapshot: SourceSnapshot
    error: PublicRecordsError | None = None


class NewJerseyParcelClient(ArcGISRESTClient):
    """Resolve the current NJGIN item and query its parcel layer."""

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            DEFAULT_LAYER_URL,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )

    def fetch_snapshot(self) -> SourceSnapshot:
        item = self._request_json(ITEM_API_URL, params={"f": "json"})
        if not isinstance(item, Mapping) or "error" in item:
            raise SourceResponseError(
                "NJGIN returned invalid ArcGIS item metadata",
                url=ITEM_API_URL,
                details={"response": item},
            )
        service_url = item.get("url")
        if not isinstance(service_url, str) or not service_url.strip():
            raise SourceSchemaError(
                "NJGIN ArcGIS item lacks a service URL",
                url=ITEM_API_URL,
            )
        self.layer_url = f"{service_url.rstrip('/')}/0"
        layer = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(layer, Mapping) or "error" in layer:
            raise SourceResponseError(
                "NJGIN returned invalid parcel-layer metadata",
                url=self.layer_url,
                details={"response": layer},
            )
        return _compatible_snapshot(item, layer, self.layer_url)

    def fetch_count(
        self,
        where: str,
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
                "NJGIN returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "NJGIN count is not a non-negative integer",
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
        params: dict[str, Any] = {
            **dict(spatial_parameters or {}),
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "orderByFields": "OBJECTID ASC",
            "resultRecordCount": record_count,
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._request_json(self.query_url, params=params)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "NJGIN returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "NJGIN response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any, field_name: str = "selector") -> str:
    text = _clean_text(value)
    if not text:
        raise NewJerseyParcelError(
            "blank_selector",
            f"{field_name} must not be blank",
            details={"field": field_name},
        )
    return text.replace("'", "''")


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


def _county_code(value: str) -> str:
    text = _clean_text(value)
    if not text:
        raise NewJerseyParcelError(
            "blank_county",
            "county must not be blank",
        )
    numeric = text.zfill(2) if text.isdigit() else None
    if numeric in COUNTIES:
        return numeric
    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        re.sub(r"\s+county$", "", text, flags=re.IGNORECASE).lower(),
    )
    code = COUNTY_ALIASES.get(normalized)
    if code is None:
        raise NewJerseyParcelError(
            "unknown_county",
            f"unknown New Jersey county: {text}",
            details={"accepted_names": [value[0] for value in COUNTIES.values()]},
        )
    return code


def _municipality_code(value: str) -> str:
    text = _clean_text(value)
    if text is None or not re.fullmatch(r"\d{4}", text):
        raise NewJerseyParcelError(
            "invalid_municipality_code",
            "municipality code must contain exactly four digits",
        )
    if text[:2] not in COUNTIES:
        raise NewJerseyParcelError(
            "invalid_municipality_code",
            "municipality code has an unknown county prefix",
            details={"county_prefix": text[:2]},
        )
    return text


def _numeric_text(value: Any, field_name: str) -> int:
    text = _clean_text(value)
    if text is None or not text.isdigit():
        raise NewJerseyParcelError(
            "invalid_numeric_selector",
            f"{field_name} must be numeric",
            details={"field": field_name},
        )
    return int(text)


def _county_clause(value: str) -> str:
    code = _county_code(value)
    return f"PCL_MUN LIKE '{code}%'"


def _address_clause(value: str) -> str:
    text = _sql_text(value, "address").upper()
    return (
        f"(UPPER(PROP_LOC) LIKE '%{text}%' "
        f"OR UPPER(ST_ADDRESS) LIKE '%{text}%')"
    )


def _pin_clause(value: str) -> str:
    text = _sql_text(value, "pin").upper()
    return (
        f"(PAMS_PIN='{text}' OR PIN_NODUP='{text}' "
        f"OR GIS_PIN='{text}')"
    )


def _optional_location_clauses(args: argparse.Namespace) -> list[str]:
    clauses: list[str] = []
    if getattr(args, "county", None):
        clauses.append(_county_clause(args.county))
    if getattr(args, "municipality_code", None):
        code = _municipality_code(args.municipality_code)
        clauses.append(f"PCL_MUN='{code}'")
    if getattr(args, "municipality", None):
        value = _sql_text(args.municipality, "municipality").upper()
        clauses.append(f"UPPER(MUN_NAME) LIKE '%{value}%'")
    return clauses


def _search_clauses(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    clauses = _optional_location_clauses(args)
    notes: list[str] = []
    if getattr(args, "address", None):
        clauses.append(_address_clause(args.address))
    if getattr(args, "pin", None):
        clauses.append(_pin_clause(args.pin))
    if getattr(args, "block", None):
        value = _sql_text(args.block, "block").upper()
        clauses.append(f"PCLBLOCK='{value}'")
    if getattr(args, "lot", None):
        value = _sql_text(args.lot, "lot").upper()
        clauses.append(f"PCLLOT='{value}'")
    if getattr(args, "qualifier", None):
        value = _sql_text(args.qualifier, "qualifier").upper()
        clauses.append(f"PCLQCODE='{value}'")
    if getattr(args, "property_class", None):
        value = _sql_text(args.property_class, "property_class").upper()
        clauses.append(f"PROP_CLASS='{value}'")
    if getattr(args, "property_use", None):
        value = _sql_text(args.property_use, "property_use").upper()
        clauses.append(f"PROP_USE='{value}'")
    if getattr(args, "deed_book", None):
        value = _sql_text(args.deed_book, "deed_book").upper()
        clauses.append(f"DEED_BOOK='{value}'")
    if getattr(args, "deed_page", None):
        value = _sql_text(args.deed_page, "deed_page").upper()
        clauses.append(f"DEED_PAGE='{value}'")
    if getattr(args, "sale_min", None) is not None:
        clauses.append(f"SALE_PRICE >= {int(args.sale_min)}")
    if getattr(args, "sale_max", None) is not None:
        clauses.append(f"SALE_PRICE <= {int(args.sale_max)}")
    has_modiv = getattr(args, "has_modiv", "any")
    if has_modiv == "yes":
        clauses.append("GIS_PIN IS NOT NULL")
    elif has_modiv == "no":
        clauses.append("GIS_PIN IS NULL")
    if getattr(args, "municipality", None) and not getattr(
        args, "municipality_code", None
    ):
        notes.append(
            "Municipality-name filtering uses joined MUN_NAME and therefore "
            "does not include parcel-only rows whose MOD-IV join is absent. "
            "Use --municipality-code when complete parcel coverage matters."
        )
    return clauses, notes


def _selection_from_args(args: argparse.Namespace) -> Selection:
    operation = args.command
    if operation == "probe":
        return Selection(where=_pin_clause(PROBE_PIN), spatial_parameters={})
    if operation == "pin":
        return Selection(where=_pin_clause(args.query), spatial_parameters={})
    if operation == "address":
        clauses = [_address_clause(args.query), *_optional_location_clauses(args)]
        notes = ()
        if getattr(args, "municipality", None) and not getattr(
            args, "municipality_code", None
        ):
            notes = (
                "Municipality-name filtering uses the joined MOD-IV field; "
                "municipality-code filtering retains parcel-only rows.",
            )
        return Selection(
            where=" AND ".join(f"({clause})" for clause in clauses),
            spatial_parameters={},
            coverage_notes=notes,
        )
    if operation == "objectid":
        object_id = _numeric_text(args.query, "objectid")
        return Selection(
            where=f"OBJECTID={object_id}",
            spatial_parameters={},
        )
    if operation == "block-lot":
        municipality = _municipality_code(args.municipality_code)
        block = _sql_text(args.block, "block").upper()
        lot = _sql_text(args.lot, "lot").upper()
        clauses = [
            f"PCL_MUN='{municipality}'",
            f"PCLBLOCK='{block}'",
            f"PCLLOT='{lot}'",
        ]
        if args.qualifier:
            qualifier = _sql_text(args.qualifier, "qualifier").upper()
            clauses.append(f"PCLQCODE='{qualifier}'")
        return Selection(
            where=" AND ".join(clauses),
            spatial_parameters={},
        )
    if operation in {"search", "count"}:
        clauses, notes = _search_clauses(args)
        if (
            operation == "search"
            and not clauses
            and not getattr(args, "all", False)
        ):
            raise NewJerseyParcelError(
                "missing_search_selector",
                "search needs at least one selector or --all",
            )
        return Selection(
            where=" AND ".join(f"({clause})" for clause in clauses) or "1=1",
            spatial_parameters={},
            coverage_notes=tuple(notes),
        )
    if operation in {"point", "bbox"}:
        clauses = _optional_location_clauses(args)
        if operation == "point":
            geometry = f"{args.longitude},{args.latitude}"
            geometry_type = "esriGeometryPoint"
        else:
            geometry = ",".join(
                str(value)
                for value in (args.xmin, args.ymin, args.xmax, args.ymax)
            )
            geometry_type = "esriGeometryEnvelope"
        return Selection(
            where=" AND ".join(f"({clause})" for clause in clauses) or "1=1",
            spatial_parameters={
                "geometry": geometry,
                "geometryType": geometry_type,
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
            },
        )
    raise NewJerseyParcelError(
        "unsupported_operation",
        f"unsupported New Jersey parcel operation: {operation}",
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.command
    parameters: dict[str, Any] = {
        "return_geometry": bool(getattr(args, "geometry", False))
    }
    if operation in {"pin", "address", "objectid"}:
        parameters["query"] = getattr(args, "query", None)
    elif operation == "block-lot":
        parameters.update(
            {
                "municipality_code": args.municipality_code,
                "block": args.block,
                "lot": args.lot,
                "qualifier": args.qualifier,
            }
        )
    elif operation in {"search", "count"}:
        for name in (
            "county",
            "municipality",
            "municipality_code",
            "address",
            "pin",
            "block",
            "lot",
            "qualifier",
            "property_class",
            "property_use",
            "deed_book",
            "deed_page",
            "sale_min",
            "sale_max",
            "has_modiv",
            "all",
        ):
            parameters[name] = getattr(args, name, None)
    elif operation == "point":
        parameters.update(
            {
                "longitude": args.longitude,
                "latitude": args.latitude,
                "county": args.county,
            }
        )
    elif operation == "bbox":
        parameters.update(
            {
                "bbox": [args.xmin, args.ymin, args.xmax, args.ymax],
                "county": args.county,
            }
        )
    elif operation == "probe":
        parameters.update({"pin": PROBE_PIN, "address": PROBE_ADDRESS})
    return parameters


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    requested_limit = (
        1
        if args.command == "probe"
        else getattr(args, "limit", None)
    )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _compatible_snapshot(
    item: Mapping[str, Any],
    layer: Mapping[str, Any],
    layer_url: str,
) -> SourceSnapshot:
    item_identity = {
        "id": item.get("id"),
        "type": item.get("type"),
        "owner": item.get("owner"),
        "access": item.get("access"),
    }
    expected_item = {
        "id": ITEM_ID,
        "type": "Feature Service",
        "owner": "NJOGIS",
        "access": "public",
    }
    if item_identity != expected_item:
        raise SourceSchemaError(
            "NJGIN ArcGIS item identity changed",
            url=ITEM_API_URL,
            details={"expected": expected_item, "observed": item_identity},
        )
    identity = {
        "name": layer.get("name"),
        "id": layer.get("id"),
        "service_item_id": layer.get("serviceItemId"),
        "object_id_field": layer.get("objectIdField"),
        "geometry_type": layer.get("geometryType"),
    }
    expected_identity = {
        "name": SOURCE_LAYER_NAME,
        "id": 0,
        "service_item_id": ITEM_ID,
        "object_id_field": "OBJECTID",
        "geometry_type": SOURCE_GEOMETRY_TYPE,
    }
    if identity != expected_identity:
        raise SourceSchemaError(
            "NJGIN parcel-layer identity changed",
            url=layer_url,
            details={"expected": expected_identity, "observed": identity},
        )
    capabilities = layer.get("advancedQueryCapabilities")
    if not isinstance(capabilities, Mapping) or not (
        capabilities.get("supportsOrderBy") is True
        and capabilities.get("supportsPagination") is True
    ):
        raise SourceSchemaError(
            "NJGIN parcel layer no longer declares ordered pagination",
            url=layer_url,
        )
    fields = layer.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "NJGIN parcel metadata lacks field declarations",
            url=layer_url,
        )
    definitions = {
        str(field.get("name")): {
            "name": field.get("name"),
            "type": field.get("type"),
            "length": field.get("length"),
        }
        for field in fields
        if isinstance(field.get("name"), str)
    }
    missing = sorted(set(REQUIRED_FIELDS) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "NJGIN parcel layer is missing required fields",
            url=layer_url,
            details={"missing_fields": missing},
        )
    native_page_size = layer.get("maxRecordCount")
    if (
        isinstance(native_page_size, bool)
        or not isinstance(native_page_size, int)
        or native_page_size <= 0
    ):
        raise SourceSchemaError(
            "NJGIN parcel layer lacks a usable maxRecordCount",
            url=layer_url,
            details={"maxRecordCount": native_page_size},
        )
    editing_info = layer.get("editingInfo")
    dataset_version = (
        editing_info.get("dataLastEditDate")
        if isinstance(editing_info, Mapping)
        else None
    )
    if isinstance(dataset_version, bool) or not isinstance(
        dataset_version, (int, type(None))
    ):
        dataset_version = None
    item_modified = item.get("modified")
    if isinstance(item_modified, bool) or not isinstance(
        item_modified, (int, type(None))
    ):
        item_modified = None
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "identity": identity,
            "required_fields": {
                name: definitions[name] for name in REQUIRED_FIELDS
            },
        }
    )
    return SourceSnapshot(
        schema_fingerprint=schema_fingerprint,
        dataset_version=dataset_version,
        item_modified=item_modified,
        layer_url=layer_url,
        native_page_size=native_page_size,
        metadata=dict(layer),
        item_metadata=dict(item),
    )


def _criteria_fingerprint(
    selection: Selection,
    *,
    operation: str,
    return_geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": operation,
            "where": selection.where,
            "spatial_parameters": dict(selection.spatial_parameters),
            "return_geometry": return_geometry,
            "ordering": "OBJECTID ASC",
            "fields": "*",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
        "dataset_version": state.dataset_version,
        "layer_url": state.layer_url,
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
        raise NewJerseyParcelError(
            "invalid_cursor",
            "cursor does not belong to the NJGIN parcel adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
            dataset_version=(
                None
                if payload.get("dataset_version") is None
                else int(payload["dataset_version"])
            ),
            layer_url=str(payload["layer_url"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise NewJerseyParcelError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or state.last_object_id < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
        or not state.layer_url.startswith("https://")
    ):
        raise NewJerseyParcelError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _validate_cursor(
    state: CursorState | None,
    *,
    criteria: str,
    snapshot: SourceSnapshot,
) -> None:
    if state is None:
        return
    if state.criteria_fingerprint != criteria:
        raise NewJerseyParcelError(
            "cursor_query_mismatch",
            "cursor belongs to different query criteria",
        )
    if state.schema_fingerprint != snapshot.schema_fingerprint:
        raise NewJerseyParcelError(
            "cursor_schema_changed",
            "source schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    if state.layer_url != snapshot.layer_url:
        raise NewJerseyParcelError(
            "cursor_service_changed",
            "the official ArcGIS item now resolves to a different service; "
            "restart the query for one source snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_layer_url": state.layer_url,
                "current_layer_url": snapshot.layer_url,
            },
        )
    if (
        state.dataset_version is not None
        and snapshot.dataset_version is not None
        and state.dataset_version != snapshot.dataset_version
    ):
        raise NewJerseyParcelError(
            "cursor_snapshot_changed",
            "NJGIN refreshed the parcel data after this cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_dataset_version": state.dataset_version,
                "current_dataset_version": snapshot.dataset_version,
            },
        )


def _object_id(feature: Mapping[str, Any]) -> int:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "NJGIN feature lacks an attributes object",
            url="arcgis://feature",
        )
    value = attributes.get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSchemaError(
            "NJGIN feature lacks a valid OBJECTID",
            url="arcgis://feature",
            details={"OBJECTID": value},
        )
    return value


def _keyset_where(where: str, last_object_id: int | None) -> str:
    if last_object_id is None:
        return where
    return f"({where}) AND OBJECTID > {last_object_id}"


def _partial_error(
    code: str,
    message: str,
    *,
    details: Mapping[str, Any],
) -> PublicRecordsError:
    return PublicRecordsError(
        code=code,
        message=message,
        category="source_schema",
        retryable=False,
        details=details,
    )


def _traverse(
    client: Any,
    *,
    operation: str,
    selection: Selection,
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> TraversalBatch:
    start_snapshot = client.fetch_snapshot()
    criteria = _criteria_fingerprint(
        selection,
        operation=operation,
        return_geometry=return_geometry,
    )
    state = _decode_cursor(cursor)
    _validate_cursor(state, criteria=criteria, snapshot=start_snapshot)
    total_count = client.fetch_count(
        selection.where, selection.spatial_parameters
    )
    if state is not None and state.total_count != total_count:
        raise NewJerseyParcelError(
            "cursor_count_changed",
            "the matching source count changed after this cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_total_count": state.total_count,
                "current_total_count": total_count,
            },
        )
    last_object_id = state.last_object_id if state is not None else None
    remaining_where = _keyset_where(selection.where, last_object_id)
    remaining_count = (
        total_count
        if last_object_id is None
        else client.fetch_count(
            remaining_where, selection.spatial_parameters
        )
    )
    target = remaining_count if limit is None else min(limit, remaining_count)
    page_size = min(int(client.page_size), start_snapshot.native_page_size)
    collected: list[Mapping[str, Any]] = []
    pages_fetched = 0
    traversal_error: PublicRecordsError | None = None

    while len(collected) < target:
        requested = min(page_size, target - len(collected))
        page = client.fetch_page(
            where=_keyset_where(selection.where, last_object_id),
            record_count=requested,
            return_geometry=return_geometry,
            spatial_parameters=selection.spatial_parameters,
        )
        pages_fetched += 1
        if not page:
            traversal_error = _partial_error(
                "arcgis_traversal_ended_early",
                "NJGIN traversal ended before its reported count",
                details={
                    "target": target,
                    "retrieved": len(collected),
                    "remaining_count": remaining_count,
                },
            )
            break
        if len(page) > requested:
            traversal_error = _partial_error(
                "arcgis_page_exceeded_request",
                "NJGIN returned more features than requested",
                details={"requested": requested, "returned": len(page)},
            )
            page = page[:requested]
        for feature in page:
            current_object_id = _object_id(feature)
            if (
                last_object_id is not None
                and current_object_id <= last_object_id
            ):
                traversal_error = _partial_error(
                    "arcgis_keyset_not_monotonic",
                    "NJGIN repeated or reordered a keyset feature",
                    details={
                        "previous_object_id": last_object_id,
                        "object_id": current_object_id,
                    },
                )
                break
            collected.append(feature)
            last_object_id = current_object_id
        if traversal_error is not None:
            break
        if len(page) < requested and len(collected) < target:
            traversal_error = _partial_error(
                "arcgis_short_page_before_count",
                "NJGIN returned a short page before its reported count",
                details={
                    "target": target,
                    "retrieved": len(collected),
                    "page_size": len(page),
                },
            )
            break

    if traversal_error is None and len(collected) != target:
        traversal_error = _partial_error(
            "arcgis_count_mismatch",
            "NJGIN traversal did not return its reported target count",
            details={"target": target, "retrieved": len(collected)},
        )

    try:
        end_snapshot = client.fetch_snapshot()
        end_count = client.fetch_count(
            selection.where, selection.spatial_parameters
        )
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        end_snapshot = start_snapshot
        end_count = total_count
        traversal_error = error.to_contract_error()

    if traversal_error is None and (
        end_snapshot.schema_fingerprint
        != start_snapshot.schema_fingerprint
        or end_snapshot.dataset_version != start_snapshot.dataset_version
        or end_snapshot.layer_url != start_snapshot.layer_url
        or end_count != total_count
    ):
        traversal_error = _partial_error(
            "source_changed_during_traversal",
            "NJGIN parcel data changed during traversal",
            details={
                "start_count": total_count,
                "end_count": end_count,
                "start_dataset_version": start_snapshot.dataset_version,
                "end_dataset_version": end_snapshot.dataset_version,
                "start_layer_url": start_snapshot.layer_url,
                "end_layer_url": end_snapshot.layer_url,
            },
        )

    next_cursor = None
    if (
        traversal_error is None
        and remaining_count > len(collected)
        and collected
    ):
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria,
                last_object_id=_object_id(collected[-1]),
                total_count=total_count,
                schema_fingerprint=start_snapshot.schema_fingerprint,
                dataset_version=start_snapshot.dataset_version,
                layer_url=start_snapshot.layer_url,
            )
        )
    return TraversalBatch(
        records=tuple(collected),
        next_cursor=next_cursor,
        total_count=total_count,
        remaining_count=remaining_count,
        pages_fetched=pages_fetched,
        snapshot=start_snapshot,
        error=traversal_error,
    )


def _epoch_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(
                value / 1000, tz=timezone.utc
            ).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    return None


def _deed_date(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None or not re.fullmatch(r"\d{6}", text):
        return None
    try:
        return datetime.strptime(text, "%y%m%d").date().isoformat()
    except ValueError:
        return None


def _county_from_attributes(
    attributes: Mapping[str, Any],
) -> tuple[str | None, str | None, str | None]:
    municipality_code = _clean_text(attributes.get("PCL_MUN"))
    county_code = (
        municipality_code[:2]
        if municipality_code and len(municipality_code) >= 2
        else None
    )
    county = COUNTIES.get(county_code or "")
    if county is not None:
        return county_code, county[0], county[1]
    county_name = _clean_text(attributes.get("COUNTY"))
    return county_code, county_name, None


def _source_snapshot_record(batch: TraversalBatch) -> dict[str, Any]:
    snapshot = batch.snapshot
    return {
        "reported_total_matches": batch.total_count,
        "reported_remaining_matches_at_start": batch.remaining_count,
        "pages_fetched": batch.pages_fetched,
        "compatible_schema_fingerprint": snapshot.schema_fingerprint,
        "data_last_edit_epoch_ms": snapshot.dataset_version,
        "arcgis_item_modified_epoch_ms": snapshot.item_modified,
        "resolved_layer_url": snapshot.layer_url,
        "native_page_size": snapshot.native_page_size,
    }


def _normalize_feature(
    feature: Mapping[str, Any],
    batch: TraversalBatch,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise SourceSchemaError(
            "NJGIN feature lacks attributes",
            url=batch.snapshot.layer_url,
        )
    attributes = dict(attributes_value)
    object_id = _object_id(feature)
    pams_pin = _clean_text(attributes.get("PAMS_PIN"))
    pin_nodup = _clean_text(attributes.get("PIN_NODUP"))
    gis_pin = _clean_text(attributes.get("GIS_PIN"))
    parcel_guid = _clean_text(attributes.get("PCL_GUID"))
    native_id = pin_nodup or pams_pin or parcel_guid or str(object_id)
    county_code, county_name, county_geoid = _county_from_attributes(
        attributes
    )
    municipality_code = _clean_text(attributes.get("PCL_MUN"))
    owner_name = _clean_text(attributes.get("OWNER_NAME"))
    modiv_matched = gis_pin is not None
    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county_geoid or JURISDICTION_GEOID,
            "parcel",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_type": "statewide_parcel_modiv_observation",
        "object_id": object_id,
        "native_parcel_id": native_id,
        "parcel_identifiers": {
            "pams_pin": pams_pin,
            "pin_nodup": pin_nodup,
            "gis_pin": gis_pin,
            "parcel_guid": parcel_guid,
            "old_property_id": _clean_text(
                attributes.get("OLD_PROPID")
            ),
            "municipality_code": municipality_code,
            "block": _clean_text(attributes.get("PCLBLOCK")),
            "lot": _clean_text(attributes.get("PCLLOT")),
            "qualifier": _clean_text(attributes.get("PCLQCODE")),
            "tax_district_code": _clean_text(attributes.get("CD_CODE")),
        },
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_code": county_code,
            "county_name": county_name,
            "county_geoid": county_geoid,
            "municipality_code": municipality_code,
            "municipality_name": _clean_text(attributes.get("MUN_NAME")),
        },
        "modiv_join": {
            "state": (
                "matched_to_modiv"
                if modiv_matched
                else "parcel_without_joined_modiv"
            ),
            "join_key": gis_pin,
            "parcel_key": pams_pin,
            "denormalized_county_raw": _clean_text(
                attributes.get("COUNTY")
            ),
        },
        "owner_observation": {
            "raw_name": owner_name,
            "visibility_state": (
                "present_in_source_response"
                if owner_name
                else "redacted_by_source"
            ),
            "source_field": "OWNER_NAME",
            "policy_url": LANDING_URL,
        },
        "situs_address": {
            "raw": _clean_text(attributes.get("PROP_LOC")),
            "postal_code": _clean_text(attributes.get("ZIP5"))
            or _clean_text(attributes.get("ZIP_CODE")),
            "state": STATE_CODE,
        },
        "mailing_address": {
            "street": _clean_text(attributes.get("ST_ADDRESS")),
            "city_state_raw": _clean_text(attributes.get("CITY_STATE")),
            "postal_code_raw": _clean_text(attributes.get("ZIP_CODE")),
            "postal_code": _clean_text(attributes.get("ZIP5")),
            "postal_plus4": _clean_text(attributes.get("ZIP_PLUS4")),
        },
        "assessment": {
            "land_value": attributes.get("LAND_VAL"),
            "improvement_value": attributes.get("IMPRVT_VAL"),
            "net_assessed_value": attributes.get("NET_VALUE"),
            "last_year_tax": attributes.get("LAST_YR_TX"),
            "currency": "USD",
        },
        "classification": {
            "property_class": _clean_text(
                attributes.get("PROP_CLASS")
            ),
            "property_use": _clean_text(attributes.get("PROP_USE")),
            "building_class": _clean_text(
                attributes.get("BLDG_CLASS")
            ),
            "facility_name": _clean_text(attributes.get("FAC_NAME")),
        },
        "physical_characteristics": {
            "building_description": _clean_text(
                attributes.get("BLDG_DESC")
            ),
            "land_description": _clean_text(
                attributes.get("LAND_DESC")
            ),
            "calculated_acres": attributes.get("CALC_ACRE"),
            "year_constructed": attributes.get("YR_CONSTR"),
            "dwelling_units": attributes.get("DWELL"),
            "commercial_dwelling_units": attributes.get("COMM_DWELL"),
            "additional_lots": [
                value
                for value in (
                    _clean_text(attributes.get("ADD_LOTS1")),
                    _clean_text(attributes.get("ADD_LOTS2")),
                )
                if value is not None
            ],
        },
        "last_sale_and_deed_reference": {
            "sale_price": attributes.get("SALE_PRICE"),
            "sale_code": _clean_text(attributes.get("SALES_CODE")),
            "deed_book": _clean_text(attributes.get("DEED_BOOK")),
            "deed_page": _clean_text(attributes.get("DEED_PAGE")),
            "deed_date_raw": _clean_text(attributes.get("DEED_DATE")),
            "deed_date": _deed_date(attributes.get("DEED_DATE")),
            "currency": "USD",
        },
        "source_dates": {
            "parcel_last_update": _epoch_date(
                attributes.get("PCLLASTUPD")
            ),
            "parcel_publication_date": _epoch_date(
                attributes.get("PCL_PBDATE")
            ),
            "parcel_last_update_epoch_ms": attributes.get("PCLLASTUPD"),
            "parcel_publication_epoch_ms": attributes.get("PCL_PBDATE"),
        },
        "related_routes": {
            "statewide_modiv_tax_list": {
                "url": NJGIN_MODIV_DOWNLOAD_URL,
                "join_fields": ["PAMS_PIN", "GIS_PIN", "PCL_MUN"],
                "adds": "MOD-IV rows that do not match a parcel polygon",
            },
            "treasury_sr1a_sales": {
                "url": TREASURY_STATISTICS_URL,
                "join_fields": [
                    "county and district code",
                    "block",
                    "lot",
                    "deed book and page",
                    "property location",
                ],
                "adds": (
                    "grantor, grantee, recording date, transfer fee, "
                    "reported and verified sale prices"
                ),
            },
            "county_recorded_instrument": {
                "url": STATE_ARCHIVES_COUNTY_URL,
                "join_fields": ["deed book", "deed page", "parcel", "party"],
                "adds": "deed, mortgage, release, and other instrument text",
            },
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
                "geometry_role": "approximate_parcel_polygon",
            }
        )
    return result


def _alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "us-nj-njgin-property-explorer",
            "route_id": "property-explorer",
            "name": "NJGIN Property Explorer",
            "url": PROPERTY_EXPLORER_URL,
            "authority": "New Jersey Office of GIS",
            "access": "anonymous interactive map",
            "coverage": "statewide address, county, municipality, block and lot",
            "adds": "human-readable parcel discovery and map context",
            "relationship_to_primary": (
                "presentation of the NJGIN parcel family; not independent "
                "corroboration"
            ),
        },
        {
            "source_id": "us-nj-njgin-parcels-modiv-bulk",
            "route_id": "statewide-and-county-downloads",
            "name": "NJGIN statewide and county parcel/MOD-IV downloads",
            "url": NJGIN_STATEWIDE_DOWNLOAD_URL,
            "authority": "New Jersey Office of GIS",
            "access": "anonymous File Geodatabase and county shapefile downloads",
            "coverage": (
                "statewide composite plus 21 county packages; county vintages "
                "vary"
            ),
            "adds": "reproducible bulk snapshots and county-specific packages",
            "gaps": "hosted owner names remain redacted",
            "relationship_to_primary": (
                "bulk representation of the same lineage, with county "
                "packages useful for freshness review"
            ),
        },
        {
            "source_id": "us-nj-njgin-parcels-only-bulk",
            "route_id": "statewide-parcels-without-modiv",
            "name": "NJGIN statewide parcels-only download",
            "url": NJGIN_PARCELS_ONLY_URL,
            "authority": "New Jersey Office of GIS",
            "access": "anonymous File Geodatabase download",
            "adds": "parcel geometry and native parcel identity without a tax join",
            "relationship_to_primary": "parcel component of the joined composite",
        },
        {
            "source_id": "us-nj-njgin-modiv-tax-list",
            "route_id": "statewide-modiv-tax-list",
            "name": "NJGIN statewide MOD-IV tax-list download",
            "url": NJGIN_MODIV_DOWNLOAD_URL,
            "authority": (
                "New Jersey Division of Taxation and New Jersey Office of GIS"
            ),
            "access": "anonymous File Geodatabase download",
            "coverage": "all published MOD-IV rows, including unmatched parcels",
            "adds": (
                "tax records absent from the parcel join and a separate "
                "assessment-table completeness check"
            ),
            "gaps": "NJGIN states hosted owner names are redacted",
            "relationship_to_primary": "complementary tax table joined only where matched",
        },
        {
            "source_id": "us-nj-treasury-modiv-files",
            "route_id": "annual-property-assessment-files",
            "name": "Division of Taxation annual Property Assessment (MOD-IV) files",
            "url": TREASURY_STATISTICS_URL,
            "observed_2026_download": TREASURY_MODIV_OBSERVED_2026_URL,
            "authority": "New Jersey Division of Taxation",
            "access": "anonymous annual ZIP downloads with a fixed-width layout",
            "coverage": "published annual files for 2021 through 2026",
            "adds": "year-specific assessment snapshots outside the ArcGIS transport",
            "gaps": (
                "release-specific redaction and record layout should be "
                "verified before treating a field as present"
            ),
            "relationship_to_primary": "separate official annual bulk representation",
        },
        {
            "source_id": "us-nj-treasury-sr1a-sales",
            "route_id": "sr1a-property-sales",
            "name": "Division of Taxation SR1A property-sales files",
            "url": TREASURY_STATISTICS_URL,
            "observed_ytd_2026_download": (
                TREASURY_SR1A_OBSERVED_YTD_2026_URL
            ),
            "layout_url": TREASURY_SR1A_LAYOUT_URL,
            "authority": "New Jersey Division of Taxation",
            "access": "anonymous year-to-date and annual ZIP downloads",
            "coverage": "current year-to-date and published annual sales files",
            "adds": (
                "grantor and grantee, reported and verified price, assessment, "
                "recording date, deed book/page, transfer fee, block/lot, "
                "property class, year built, and living space"
            ),
            "relationship_to_primary": (
                "complementary transaction layer; one parcel row does not "
                "represent the full sales history"
            ),
        },
        {
            "source_id": "us-nj-local-assessors-tax-boards",
            "route_id": "municipal-assessor-and-county-tax-board",
            "name": "Municipal assessors and County Boards of Taxation",
            "url": ASSESSOR_DIRECTORY_URL,
            "county_board_url": COUNTY_TAX_BOARD_URL,
            "authority": (
                "New Jersey Division of Taxation, county boards, and "
                "municipal assessors"
            ),
            "access": "local online, inspection, copy, or custodian route",
            "adds": (
                "property record cards, certified tax lists, added or omitted "
                "assessments, local corrections, and assessment appeals"
            ),
            "relationship_to_primary": (
                "local record-of-administration complement and freshness check"
            ),
        },
        {
            "source_id": "us-nj-county-clerks-registers",
            "route_id": "county-clerk-register-and-state-archives",
            "name": "County Clerk/Register of Deeds and State Archives holdings",
            "url": STATE_ARCHIVES_COUNTY_URL,
            "custodian_schedule_url": COUNTY_RECORDER_RETENTION_URL,
            "authority": (
                "New Jersey county clerks/registers and New Jersey State Archives"
            ),
            "access": "county-specific online, copy, in-person, or archives route",
            "adds": (
                "deeds, mortgages, releases, party names, controlling "
                "instrument text, and historical county holdings"
            ),
            "relationship_to_primary": "document-level title and lien evidence",
        },
        {
            "source_id": "us-nj-opra-property-records",
            "route_id": "record-custodian-request",
            "name": "New Jersey OPRA custodian routing",
            "url": OPRA_URL,
            "authority": "State, county, or municipal record custodian",
            "access": "records request to the office maintaining the record",
            "adds": (
                "defined copies or extracts not already published by the "
                "statewide, county, assessor, or recorder route"
            ),
            "relationship_to_primary": "request channel for a specified record set",
        },
    ]


def _metadata_record(snapshot: SourceSnapshot) -> dict[str, Any]:
    layer = snapshot.metadata
    fields = layer.get("fields")
    return {
        "source_id": SOURCE_ID,
        "record_type": "source_contract",
        "official_landing_url": LANDING_URL,
        "arcgis_item_id": ITEM_ID,
        "arcgis_item_url": ITEM_PAGE_URL,
        "resolved_layer_url": snapshot.layer_url,
        "layer_name": layer.get("name"),
        "geometry_type": layer.get("geometryType"),
        "object_id_field": layer.get("objectIdField"),
        "native_page_size": snapshot.native_page_size,
        "supported_query_formats": layer.get("supportedQueryFormats"),
        "field_count": len(fields) if isinstance(fields, list) else None,
        "required_fields": list(REQUIRED_FIELDS),
        "schema_fingerprint": snapshot.schema_fingerprint,
        "data_last_edit_epoch_ms": snapshot.dataset_version,
        "arcgis_item_modified_epoch_ms": snapshot.item_modified,
        "owner_name_visibility": "redacted_by_source",
        "parcel_modiv_join": "partial",
    }


def _result_from_batch(
    query: PublicRecordsQuery,
    batch: TraversalBatch,
    records: Sequence[Mapping[str, Any]],
    warnings: Sequence[str],
) -> PublicRecordsResult:
    if batch.error is not None:
        status = ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED
        return PublicRecordsResult.failure(
            query,
            status,
            [batch.error],
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )


def _client_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "page_size": getattr(args, "page_size", DEFAULT_PAGE_SIZE),
        "timeout": getattr(args, "timeout", DEFAULT_TIMEOUT),
        "minimum_interval": getattr(
            args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL
        ),
        "retry_attempts": getattr(args, "retry_attempts", 3),
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    source_client = client
    try:
        if args.command == "alternatives":
            result = PublicRecordsResult.success(query, _alternative_routes())
        else:
            source_client = source_client or NewJerseyParcelClient(
                **_client_args(args)
            )
            if args.command == "metadata":
                snapshot = source_client.fetch_snapshot()
                result = PublicRecordsResult.success(
                    query, [_metadata_record(snapshot)]
                )
            elif args.command == "count":
                selection = _selection_from_args(args)
                snapshot = source_client.fetch_snapshot()
                count = source_client.fetch_count(
                    selection.where, selection.spatial_parameters
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "record_type": "source_count",
                            "count": count,
                            "where": selection.where,
                            "spatial_parameters": dict(
                                selection.spatial_parameters
                            ),
                            "resolved_layer_url": snapshot.layer_url,
                            "schema_fingerprint": (
                                snapshot.schema_fingerprint
                            ),
                            "data_last_edit_epoch_ms": (
                                snapshot.dataset_version
                            ),
                        }
                    ],
                    warnings=(
                        *SOURCE_WARNINGS,
                        *selection.coverage_notes,
                    ),
                )
            else:
                selection = _selection_from_args(args)
                limit = 1 if args.command == "probe" else args.limit
                batch = _traverse(
                    source_client,
                    operation=args.command,
                    selection=selection,
                    limit=limit,
                    cursor=getattr(args, "cursor", None),
                    return_geometry=bool(args.geometry),
                )
                records = [
                    _normalize_feature(
                        feature,
                        batch,
                        geometry_requested=bool(args.geometry),
                    )
                    for feature in batch.records
                ]
                result = _result_from_batch(
                    query,
                    batch,
                    records,
                    (*SOURCE_WARNINGS, *selection.coverage_notes),
                )
    except NewJerseyParcelError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
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
        )

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
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
        summary=(
            f"New Jersey parcels {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"New Jersey parcels {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "metadata":
            print(
                f"  {record['layer_name']} | "
                f"{record['resolved_layer_url']}"
            )
        elif args.command == "count":
            print(f"  {record['count']} | {record['where']}")
        else:
            print(
                f"  {record['native_parcel_id']} | "
                f"{record['situs_address']['raw'] or '?'} | "
                f"{record['jurisdiction']['county_name'] or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_network_args(
    parser: argparse.ArgumentParser,
    *,
    geometry_default: bool = False,
) -> None:
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
        default=geometry_default,
        help="Return source parcel geometry in EPSG:4326",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Transport batch size, bounded by live source metadata",
    )
    parser.add_argument(
        "--timeout",
        type=_nonnegative_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def _add_location_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county", help="New Jersey county name or code 01-21")
    parser.add_argument(
        "--municipality-code",
        help="Four-digit MOD-IV county/municipality code",
    )
    parser.add_argument(
        "--municipality",
        help="Municipality-name substring from joined MOD-IV data",
    )


def _add_search_args(
    parser: argparse.ArgumentParser,
    *,
    allow_all: bool,
) -> None:
    _add_location_args(parser)
    parser.add_argument("--address", help="Situs or mailing-address substring")
    parser.add_argument("--pin", help="PAMS_PIN, PIN_NODUP, or GIS_PIN")
    parser.add_argument("--block")
    parser.add_argument("--lot")
    parser.add_argument("--qualifier")
    parser.add_argument("--property-class")
    parser.add_argument("--property-use")
    parser.add_argument("--deed-book")
    parser.add_argument("--deed-page")
    parser.add_argument("--sale-min", type=int)
    parser.add_argument("--sale-max", type=int)
    parser.add_argument(
        "--has-modiv",
        choices=("any", "yes", "no"),
        default="any",
        help="Filter by whether the parcel has a joined MOD-IV row",
    )
    if allow_all:
        parser.add_argument(
            "--all",
            action="store_true",
            help="Select the statewide layer when no narrower selector is set",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query NJGIN statewide parcel geometry and joined MOD-IV "
            "assessment records"
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    pin = subparsers.add_parser("pin", help="Search an exact parcel PIN")
    pin.add_argument("query")
    _add_network_args(pin)

    address = subparsers.add_parser(
        "address", help="Search situs or mailing-address text"
    )
    address.add_argument("query")
    _add_location_args(address)
    _add_network_args(address)

    objectid = subparsers.add_parser(
        "objectid", help="Fetch one ArcGIS OBJECTID"
    )
    objectid.add_argument("query")
    _add_network_args(objectid)

    block_lot = subparsers.add_parser(
        "block-lot", help="Search a municipality's block and lot"
    )
    block_lot.add_argument("--municipality-code", required=True)
    block_lot.add_argument("--block", required=True)
    block_lot.add_argument("--lot", required=True)
    block_lot.add_argument("--qualifier")
    _add_network_args(block_lot)

    search = subparsers.add_parser(
        "search", help="Combine parcel and assessment selectors"
    )
    _add_search_args(search, allow_all=True)
    _add_network_args(search)

    count = subparsers.add_parser(
        "count", help="Count a selected source population"
    )
    _add_search_args(count, allow_all=False)
    count.add_argument(
        "--page-size", type=_positive_int, default=DEFAULT_PAGE_SIZE
    )
    count.add_argument(
        "--timeout", type=_nonnegative_float, default=DEFAULT_TIMEOUT
    )
    count.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    count.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(count)

    point = subparsers.add_parser(
        "point", help="Find parcels intersecting a WGS84 point"
    )
    point.add_argument("longitude", type=float)
    point.add_argument("latitude", type=float)
    point.add_argument("--county")
    point.set_defaults(municipality=None, municipality_code=None)
    _add_network_args(point, geometry_default=True)

    bbox = subparsers.add_parser(
        "bbox", help="Find parcels intersecting a WGS84 bounding box"
    )
    bbox.add_argument("xmin", type=float)
    bbox.add_argument("ymin", type=float)
    bbox.add_argument("xmax", type=float)
    bbox.add_argument("ymax", type=float)
    bbox.add_argument("--county")
    bbox.set_defaults(municipality=None, municipality_code=None)
    _add_network_args(bbox, geometry_default=True)

    metadata = subparsers.add_parser(
        "metadata", help="Resolve and validate the current source contract"
    )
    metadata.add_argument(
        "--page-size", type=_positive_int, default=DEFAULT_PAGE_SIZE
    )
    metadata.add_argument(
        "--timeout", type=_nonnegative_float, default=DEFAULT_TIMEOUT
    )
    metadata.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    metadata.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(metadata)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="List complementary official property-record routes",
    )
    add_output_args(alternatives)

    probe = subparsers.add_parser(
        "probe", help="Run one exact live source sentinel"
    )
    _add_network_args(probe)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
