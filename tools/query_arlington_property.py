#!/usr/bin/env python3
"""Arlington County parcel and assessment observations via official ArcGIS.

The County publishes a detailed property-map layer with RPC/parcel identifiers,
owner mailing-address components, classification, zoning, legal description,
lot size, assessment values, and parcel geometry. The layer does not expose
owner names, situs addresses, or sale history; those absences are represented
explicitly in normalized records.

Usage:
    uv run python tools/query_arlington_property.py parcel 03-001-009
    uv run python tools/query_arlington_property.py rpc 03001009
    uv run python tools/query_arlington_property.py address "3905 44TH ST N"
    uv run python tools/query_arlington_property.py objectid 1
    uv run python tools/query_arlington_property.py probe --output /tmp/arlington.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

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
        PublicRecordsHTTPError,
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
        PublicRecordsHTTPError,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-va-arlington-property-map"
ARLINGTON_GEOID = "51013"
LAYER_ID = 3
LAYER_URL = (
    "https://arlgis.arlingtonva.us/arcgis/rest/services/"
    f"StaffMap/Property_Map_public/MapServer/{LAYER_ID}"
)
RELATED_SIMPLE_LAYER_URL = (
    "https://arlgis.arlingtonva.us/arcgis/rest/services/"
    "Public_Maps/Parcel_Map/FeatureServer/1"
)
PROBE_RPC_NUMBER = "03001009"
SOURCE_MAX_PAGE_SIZE = 2_000
SOURCE_GEOMETRY_CRS = "EPSG:3857"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Arlington County Property Map",
    source_role="parcel_gis_assessment",
    base_url=LAYER_URL,
    dataset_id="StaffMap/Property_Map_public/MapServer/3",
    metadata={
        "authority": "Arlington County, Virginia",
        "coverage": "Arlington County, Virginia",
        "layer_id": LAYER_ID,
        "native_max_record_count": SOURCE_MAX_PAGE_SIZE,
        "related_simple_parcel_layer": RELATED_SIMPLE_LAYER_URL,
        "published_owner_name_field": False,
        "published_situs_address_field": False,
        "published_sales_fields": False,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=ARLINGTON_GEOID,
    name="Arlington County, Virginia",
    state_code="VA",
    county_fips=ARLINGTON_GEOID,
    locality="Arlington County",
)

OUT_FIELDS = (
    "OBJECTID",
    "RPCMSTR",
    "PARCEL_ID",
    "LRSN",
    "ZONING",
    "OWN_STREET",
    "OWN_CITY",
    "OWN_STATE",
    "OWN_ZIP",
    "PROPERTY_CLASS_DESC",
    "NEIGHBORHOOD",
    "MAP_PAGE",
    "LOTSIZE",
    "LEGAL_DESC",
    "CHANGE_REASON_TYPE",
    "ASSESSMENT_DATE",
    "IMPROVEMENT",
    "LAND",
    "TOTAL",
    "GeoSyncDate",
    "SHAPE.STArea()",
    "SHAPE.STLength()",
    "tax_exemption_type_dsc",
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "normalization_version": 2,
        "fields": OUT_FIELDS,
        "coverage_gaps": ("owner_name", "situs_address", "sales"),
    }
)

SOURCE_WARNINGS = (
    (
        "This layer publishes an owner mailing address but no owner name; "
        "the address is not an owner-identity observation."
    ),
    (
        "The layer does not publish situs-address or sale-history fields; "
        "normalized records preserve those source gaps explicitly."
    ),
    "Parcel geometry is GIS mapping data and is not a surveyed legal boundary.",
)


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    """Load the reviewed machine-acquisition contract for this source."""
    catalog_db = Path(
        getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
    ).expanduser()
    catalog_config = Path(
        getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
    ).expanduser()
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=catalog_db,
        config_path=catalog_config,
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> ArcGISRESTClient:
    limits = access_contract.get("limits") or {}
    reviewed_page_size = limits.get("maximum_page_size")
    page_size = min(args.page_size, SOURCE_MAX_PAGE_SIZE)
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return ArcGISRESTClient(
        LAYER_URL,
        page_size=page_size,
        max_records=args.max_records,
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
    )


def _clean_text(value: Any) -> str | None:
    text = " ".join(str(value or "").replace("\x00", "").split()).strip()
    return text or None


def _sql_literal(value: str) -> str:
    normalized = _clean_text(value)
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized.replace("'", "''")


def _normalize_parcel_id(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise ValueError("parcel/RPC value must not be blank")
    normalized = re.sub(r"[^0-9]", "", text)
    if len(normalized) != 8:
        raise ValueError("Arlington parcel/RPC must normalize to eight digits")
    return normalized


def _address_where(selector: str | None) -> str:
    raw_value = str(selector or "").replace("\x00", "").strip()
    if not raw_value:
        raise ValueError("query value must not be blank")
    parts = [
        _sql_literal(part)
        for part in raw_value.split(",")
        if _clean_text(part)
    ]
    street = parts[0].upper()
    predicates = [f"UPPER(OWN_STREET) LIKE '%{street}%'"]
    if len(parts) >= 2:
        predicates.append(f"UPPER(OWN_CITY) LIKE '%{parts[1].upper()}%'")
    if len(parts) >= 3:
        state_zip_match = re.fullmatch(
            r"([A-Za-z]{2})(?:\s+(\d{5}(?:-\d{4})?))?",
            parts[2],
        )
        if state_zip_match:
            predicates.append(
                f"UPPER(OWN_STATE)='{state_zip_match.group(1).upper()}'"
            )
            if state_zip_match.group(2):
                postal_code = state_zip_match.group(2)
                predicates.append(f"OWN_ZIP LIKE '{postal_code}%'")
        else:
            predicates.append(
                f"UPPER(OWN_STATE) LIKE '%{parts[2].upper()}%'"
            )
    if len(parts) >= 4:
        predicates.append(f"OWN_ZIP LIKE '{parts[3]}%'")
    return " AND ".join(predicates)


def _where(operation: str, selector: str | None) -> str:
    if operation == "probe":
        return f"RPCMSTR='{PROBE_RPC_NUMBER}'"
    if operation == "address":
        return _address_where(selector)
    if operation in {"parcel", "rpc"}:
        parcel_id = _normalize_parcel_id(selector)
        if operation == "rpc":
            return f"RPCMSTR='{parcel_id}'"
        return (
            f"RPCMSTR='{parcel_id}' OR PARCEL_ID='{parcel_id}'"
        )
    if operation == "objectid":
        value = _sql_literal(selector or "")
        if not value.isdigit():
            raise ValueError("objectid must be numeric")
        return f"OBJECTID={int(value)}"
    raise ValueError(
        f"unsupported Arlington property operation: {operation}"
    )


def _arcgis_datetime(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (OverflowError, OSError, ValueError):
            pass
    text = _clean_text(value)
    if not text:
        return None
    for date_format in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            parsed = datetime.strptime(text, date_format)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return (
                parsed.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except ValueError:
            continue
    return text


def _arcgis_date(value: Any) -> str | None:
    normalized = _arcgis_datetime(value)
    return normalized[:10] if normalized else None


def _raw_address(*parts: Any) -> str | None:
    values = [_clean_text(part) for part in parts]
    return ", ".join(value for value in values if value) or None


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError("Arlington ArcGIS feature attributes must be an object")
    attributes = dict(attributes_value)

    rpc_raw = _clean_text(attributes.get("RPCMSTR"))
    parcel_raw = _clean_text(attributes.get("PARCEL_ID"))
    rpc_number = _normalize_parcel_id(rpc_raw) if rpc_raw else None
    parcel_id = _normalize_parcel_id(parcel_raw) if parcel_raw else None
    native_id = rpc_number or parcel_id
    if not native_id:
        raise ValueError(
            "Arlington property feature lacks an RPC or parcel identifier"
        )

    assessment_date = _arcgis_date(attributes.get("ASSESSMENT_DATE"))
    source_sync_datetime = _arcgis_datetime(
        attributes.get("GeoSyncDate")
    )
    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            ARLINGTON_GEOID,
            "parcel",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "jurisdiction": {
            "state_code": "VA",
            "county_name": "Arlington County",
            "county_geoid": ARLINGTON_GEOID,
        },
        "native_parcel_id": native_id,
        "tax_year": (
            assessment_date[:4] if assessment_date else None
        ),
        "alternate_parcel_ids": (
            [parcel_id] if parcel_id and parcel_id != native_id else []
        ),
        "rpc_number": rpc_number,
        "parcel_id": parcel_id,
        "lrsn": attributes.get("LRSN"),
        "object_id": attributes.get("OBJECTID"),
        "owners": [],
        "owner_visibility": {
            "state": "not_exposed_by_source_layer",
            "owner_name_field_present": False,
            "mailing_address_fields_present": True,
        },
        "situs_address": None,
        "situs_address_visibility": {
            "state": "not_exposed_by_source_layer",
            "situs_address_fields_present": False,
        },
        "mailing_address": {
            "raw": _raw_address(
                attributes.get("OWN_STREET"),
                attributes.get("OWN_CITY"),
                attributes.get("OWN_STATE"),
                attributes.get("OWN_ZIP"),
            ),
            "line1": _clean_text(attributes.get("OWN_STREET")),
            "city": _clean_text(attributes.get("OWN_CITY")),
            "state": _clean_text(attributes.get("OWN_STATE")),
            "postal_code": _clean_text(attributes.get("OWN_ZIP")),
            "source_role": "owner_mailing_address_without_owner_name",
        },
        "classification": {
            "property_class_description": _clean_text(
                attributes.get("PROPERTY_CLASS_DESC")
            ),
            "zoning": _clean_text(attributes.get("ZONING")),
            "neighborhood_code": attributes.get("NEIGHBORHOOD"),
            "map_page": _clean_text(attributes.get("MAP_PAGE")),
            "tax_exemption_type": _clean_text(
                attributes.get("tax_exemption_type_dsc")
            ),
        },
        "assessment": {
            "tax_year": (
                assessment_date[:4] if assessment_date else None
            ),
            "assessment_date": assessment_date,
            "change_reason": _clean_text(
                attributes.get("CHANGE_REASON_TYPE")
            ),
            "land_value": attributes.get("LAND"),
            "improvement_value": attributes.get("IMPROVEMENT"),
            "parcel_value": attributes.get("TOTAL"),
            "assessed_value": attributes.get("TOTAL"),
            "assessment_class": _clean_text(
                attributes.get("PROPERTY_CLASS_DESC")
            ),
            "total_value": attributes.get("TOTAL"),
            "currency": "USD",
        },
        "lot": {
            "lot_size_square_feet": attributes.get("LOTSIZE"),
            "source_shape_area": attributes.get("SHAPE.STArea()"),
            "source_shape_length": attributes.get("SHAPE.STLength()"),
        },
        "legal_description_raw": _clean_text(
            attributes.get("LEGAL_DESC")
        ),
        "sales_history": [],
        "sales_visibility": {
            "state": "not_exposed_by_source_layer",
            "sale_fields_present": False,
        },
        "source_last_updated": source_sync_datetime,
        "source_sync_datetime": source_sync_datetime,
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }
    if "geometry" in feature:
        result["geometry"] = feature.get("geometry")
        result["geometry_format"] = "esri_json"
        result["geometry_crs"] = SOURCE_GEOMETRY_CRS
        result["geometry_disclaimer"] = SOURCE_WARNINGS[2]
    return result


def build_query(
    operation: str,
    selector: str | None,
    *,
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "return_geometry": return_geometry,
                "address_field_role": (
                    "owner_mailing" if operation == "address" else None
                ),
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code")
                or "acquisition_route_unavailable"
            ),
            message=str(decision.get("reason") or error),
            category="access",
            retryable=False,
            details=decision,
        )
    else:
        status = ResultStatus.UNAVAILABLE
        public_error = PublicRecordsError(
            code="catalog_unavailable",
            message=str(error),
            category="catalog",
            retryable=False,
        )
    return PublicRecordsResult.failure(
        query,
        status,
        [public_error],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: ArcGISRESTClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    operation = args.command
    selector = getattr(args, "query", None)
    limit = 1 if operation == "probe" else args.limit
    query = build_query(
        operation,
        selector,
        limit=limit,
        cursor=args.cursor,
        return_geometry=args.geometry,
    )
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        source_client = client or _client(args, access_contract)
        fetch_limit = 2 if operation == "probe" else limit
        fetched = source_client.query(
            where=_where(operation, selector),
            out_fields=OUT_FIELDS,
            parameters={"orderByFields": "OBJECTID"},
            requested_limit=fetch_limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        if operation == "probe" and len(fetched.records) != 1:
            raise ValueError(
                "Arlington probe RPC expected exactly one record; "
                f"received {len(fetched.records)}"
            )
        records = [
            _normalize_feature(
                feature,
                response_schema_fingerprint=fetched.schema_fingerprint,
            )
            for feature in fetched.records
        ]
        warnings = (*SOURCE_WARNINGS, *fetched.warnings)
        if fetched.truncated_by_cap:
            result = PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=fetched.next_cursor,
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=fetched.next_cursor,
                warnings=warnings,
            )
    except (AcquisitionUnavailableError, CatalogError, OSError) as error:
        result = _access_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
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
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    if log_results:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"Arlington property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Arlington property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record['native_parcel_id']} | "
            f"{record['mailing_address'].get('raw') or '?'} | "
            f"{record['assessment'].get('total_value') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Optional caller-selected result count; omitted queries all "
            "matching source pages"
        ),
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor from a previous result",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Return source parcel geometry",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=SOURCE_MAX_PAGE_SIZE,
        help="ArcGIS page size, bounded by the source-native maximum",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional caller-selected record ceiling",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.0)
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Arlington County property-map layer"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("parcel", "Look up an Arlington parcel or RPC number"),
        ("rpc", "Look up an Arlington RPC number"),
        (
            "address",
            "Search published owner mailing-address observations",
        ),
        ("objectid", "Look up one ArcGIS object ID"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_shared_arguments(command_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Query one stable RPC sentinel",
    )
    _add_shared_arguments(probe_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if (
        (args.limit is not None and args.limit <= 0)
        or args.page_size <= 0
        or args.timeout <= 0
        or args.minimum_interval < 0
        or (args.max_records is not None and args.max_records <= 0)
    ):
        parser.error(
            "limit, page-size, and timeout must be positive when supplied; "
            "minimum-interval must not be negative; max-records is optional"
        )
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
