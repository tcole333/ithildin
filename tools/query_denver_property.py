#!/usr/bin/env python3
"""Denver assessor parcel, value, and sale observations via official ArcGIS.

The City and County of Denver publishes its parcel layer through an ArcGIS
FeatureServer owned by the city. The layer combines parcel identifiers,
assessor-owner and address observations, valuation fields, physical
characteristics, and the latest sale/reception attributes.

Assessor-owner fields are dated source observations rather than proof of title.
Use ``RECEPTION_NUM`` as a join key to the separately sourced Denver Clerk and
Recorder records when a recorded instrument is needed.

Usage:
    uv run python tools/query_denver_property.py owner "RODRIGUEZ"
    uv run python tools/query_denver_property.py address "16159 E RANDOLPH PL"
    uv run python tools/query_denver_property.py parcel "0017103008000"
    uv run python tools/query_denver_property.py objectid 991475
    uv run python tools/query_denver_property.py probe --output /tmp/denver.json
"""

from __future__ import annotations

import argparse
import json
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


SOURCE_ID = "us-co-denver-parcels"
DENVER_GEOID = "08031"
ARCGIS_ITEM_ID = "7c53bd0894134e80ae1e478c0789bf49"
LAYER_ID = 245
LAYER_URL = (
    "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
    f"ODC_PROP_PARCELS_A/FeatureServer/{LAYER_ID}"
)
RECORDER_SOURCE_ID = "us-co-denver-recorder-publicsearch"
RECORDER_SEARCH_URL = "https://denver.co.publicsearch.us"
PROBE_SCHEDULE_NUMBER = "0017103008000"
SOURCE_MAX_PAGE_SIZE = 2_000
SOURCE_GEOMETRY_CRS = "EPSG:2877"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="City and County of Denver Property Parcels",
    source_role="parcel_gis_assessment_sales",
    base_url=LAYER_URL,
    dataset_id=f"{ARCGIS_ITEM_ID}/{LAYER_ID}",
    metadata={
        "authority": (
            "City and County of Denver Department of Finance, "
            "Assessment Division, GIS Section"
        ),
        "coverage": "City and County of Denver, Colorado",
        "arcgis_item_id": ARCGIS_ITEM_ID,
        "layer_id": LAYER_ID,
        "native_max_record_count": SOURCE_MAX_PAGE_SIZE,
        "recorder_join_field": "RECEPTION_NUM",
        "recorder_source_id": RECORDER_SOURCE_ID,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=DENVER_GEOID,
    name="City and County of Denver, Colorado",
    state_code="CO",
    county_fips=DENVER_GEOID,
    locality="Denver",
)

OUT_FIELDS = (
    "OBJECTID",
    "SCHEDNUM",
    "MAPNUM",
    "BLKNUM",
    "PARCELNUM",
    "APPENDAGE",
    "PARCEL_SOURCE",
    "SYSTEM_START_DATE",
    "OWNER_NAME",
    "OWNER_ADDRESS_LINE1",
    "OWNER_ADDRESS_LINE2",
    "OWNER_CITY",
    "OWNER_STATE",
    "OWNER_ZIP",
    "SITUS_ADDRESS_ID",
    "SITUS_ADDRESS_LINE1",
    "SITUS_ADDRESS_LINE2",
    "SITUS_CITY",
    "SITUS_STATE",
    "SITUS_ZIP",
    "SITUS_ADDR_NBR",
    "SITUS_ADDR_NBR_SUFFIX",
    "SITUS_STR_NAME_PRE_MOD",
    "SITUS_STR_NAME_PRE_DIR",
    "SITUS_STR_NAME_PRE_TYPE",
    "SITUS_STR_NAME",
    "SITUS_STR_NAME_POST_TYPE",
    "SITUS_STR_NAME_POST_DIR",
    "SITUS_STR_NAME_POST_MOD",
    "SITUS_UNIT_TYPE",
    "SITUS_UNIT_IDENT",
    "TAX_DIST",
    "SITUS_X_COORD",
    "SITUS_Y_COORD",
    "PROP_CLASS",
    "D_CLASS",
    "D_CLASS_CN",
    "DCL12",
    "ZONE_ID",
    "ZONE_10",
    "APPRAISED_LAND_VALUE",
    "APPRAISED_IMP_VALUE",
    "APPRAISED_TOTAL_VALUE",
    "ASSESSED_LAND_VALUE_LOCAL",
    "ASSESSED_BLDG_VALUE_LOCAL",
    "ASSESSED_TOTAL_VALUE_LOCAL",
    "EXEMPT_AMT_LOCAL",
    "TAXABLE_AMT_LOCAL",
    "ASSESSED_LAND_VALUE_SCH",
    "ASSESSED_BLDG_VALUE_SCH",
    "ASSESSED_TOTAL_VALUE_SCH",
    "EXEMPT_AMT_SCH",
    "TAXABLE_AMT_SCH",
    "LAND_AREA",
    "RES_ORIG_YEAR_BUILT",
    "RES_ABOVE_GRADE_AREA",
    "COM_ORIG_YEAR_BUILT",
    "COM_GROSS_AREA",
    "COM_NET_AREA",
    "COM_STRUCTURE_TYPE",
    "LEGAL_DESC",
    "TOT_UNITS",
    "RECEPTION_NUM",
    "ASAL_INSTR",
    "SALE_DATE",
    "SALE_MONTHDAY",
    "SALE_YEAR",
    "SALE_PRICE",
    "GlobalID",
    "Shape__Area",
    "Shape__Length",
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "arcgis_item_id": ARCGIS_ITEM_ID,
        "layer_id": LAYER_ID,
        "normalization_version": 2,
        "fields": OUT_FIELDS,
    }
)

SOURCE_WARNINGS = (
    "The owner field is an assessor observation, not proof of legal or beneficial ownership.",
    "Sale and reception fields are assessor attributes; use the reception number to inspect the recorder's instrument.",
    "Parcel geometry is GIS mapping data and is not a surveyed legal boundary.",
)


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    """Load the tracked review and require its machine-acquisition contract."""
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


def _sql_literal(value: str) -> str:
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized.replace("'", "''")


def _where(operation: str, selector: str | None) -> str:
    if operation == "probe":
        return f"SCHEDNUM='{PROBE_SCHEDULE_NUMBER}'"

    value = _sql_literal(selector or "")
    if operation == "owner":
        return f"UPPER(OWNER_NAME) LIKE '%{value.upper()}%'"
    if operation == "address":
        upper = value.upper()
        return (
            f"UPPER(SITUS_ADDRESS_LINE1) LIKE '%{upper}%' "
            f"OR UPPER(SITUS_ADDRESS_LINE2) LIKE '%{upper}%'"
        )
    if operation == "parcel":
        return f"SCHEDNUM='{value}' OR PARCELNUM='{value}'"
    if operation == "objectid":
        if not value.isdigit():
            raise ValueError("objectid must be numeric")
        return f"OBJECTID={int(value)}"
    raise ValueError(f"unsupported Denver property operation: {operation}")


def _arcgis_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .date()
                .isoformat()
            )
        except (OverflowError, OSError, ValueError):
            pass
    text = str(value or "").strip()
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _sale_date(attributes: Mapping[str, Any]) -> str | None:
    source_date = _arcgis_date(attributes.get("SALE_DATE"))
    if source_date:
        return source_date
    year_value = attributes.get("SALE_YEAR")
    month_day = str(attributes.get("SALE_MONTHDAY") or "").strip().zfill(4)
    try:
        year = int(float(year_value))
        month = int(month_day[:2])
        day = int(month_day[2:])
        return datetime(year, month, day).date().isoformat()
    except (TypeError, ValueError):
        return None


def _raw_address(*parts: Any) -> str | None:
    values = [str(part).strip() for part in parts if str(part or "").strip()]
    return ", ".join(values) if values else None


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError("Denver ArcGIS feature attributes must be an object")
    attributes = dict(attributes_value)

    schedule_number = str(attributes.get("SCHEDNUM") or "").strip() or None
    global_id = str(attributes.get("GlobalID") or "").strip() or None
    object_id = attributes.get("OBJECTID")
    native_id = schedule_number or global_id or str(object_id or "").strip()
    if not native_id:
        raise ValueError("Denver parcel feature lacks a stable source identifier")

    owner_name = str(attributes.get("OWNER_NAME") or "").strip()
    owners = (
        [
            {
                "raw_name": owner_name,
                "role": "primary_assessor_owner",
                "assertion_type": "assessment_roll",
                "confidence": "high",
                "title_caveat": (
                    "not_proof_of_legal_or_beneficial_ownership"
                ),
            }
        ]
        if owner_name
        else []
    )
    reception_number = (
        str(attributes.get("RECEPTION_NUM") or "").strip() or None
    )
    parcel_number = str(attributes.get("PARCELNUM") or "").strip() or None
    source_last_updated = _arcgis_date(
        attributes.get("SYSTEM_START_DATE")
    )

    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            DENVER_GEOID,
            "parcel",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "jurisdiction": {
            "state_code": "CO",
            "county_name": "City and County of Denver",
            "county_geoid": DENVER_GEOID,
        },
        "native_parcel_id": schedule_number or native_id,
        "alternate_parcel_ids": (
            [parcel_number]
            if parcel_number
            and parcel_number != (schedule_number or native_id)
            else []
        ),
        "object_id": object_id,
        "global_id": global_id,
        "parcel_components": {
            "schedule_number": schedule_number,
            "map_number": attributes.get("MAPNUM"),
            "block_number": attributes.get("BLKNUM"),
            "parcel_number": parcel_number,
            "appendage": attributes.get("APPENDAGE"),
            "parcel_source": attributes.get("PARCEL_SOURCE"),
        },
        "owners": owners,
        "situs_address": {
            "raw": _raw_address(
                attributes.get("SITUS_ADDRESS_LINE1"),
                attributes.get("SITUS_ADDRESS_LINE2"),
            ),
            "line1": attributes.get("SITUS_ADDRESS_LINE1"),
            "line2": attributes.get("SITUS_ADDRESS_LINE2"),
            "city": attributes.get("SITUS_CITY"),
            "state": attributes.get("SITUS_STATE") or "CO",
            "postal_code": attributes.get("SITUS_ZIP"),
            "source_address_id": attributes.get("SITUS_ADDRESS_ID"),
            "parsed": {
                "number": attributes.get("SITUS_ADDR_NBR"),
                "number_suffix": attributes.get("SITUS_ADDR_NBR_SUFFIX"),
                "street_pre_modifier": attributes.get(
                    "SITUS_STR_NAME_PRE_MOD"
                ),
                "street_pre_direction": attributes.get(
                    "SITUS_STR_NAME_PRE_DIR"
                ),
                "street_pre_type": attributes.get(
                    "SITUS_STR_NAME_PRE_TYPE"
                ),
                "street_name": attributes.get("SITUS_STR_NAME"),
                "street_post_type": attributes.get(
                    "SITUS_STR_NAME_POST_TYPE"
                ),
                "street_post_direction": attributes.get(
                    "SITUS_STR_NAME_POST_DIR"
                ),
                "street_post_modifier": attributes.get(
                    "SITUS_STR_NAME_POST_MOD"
                ),
                "unit_type": attributes.get("SITUS_UNIT_TYPE"),
                "unit": attributes.get("SITUS_UNIT_IDENT"),
            },
            "source_coordinate": {
                "x": attributes.get("SITUS_X_COORD"),
                "y": attributes.get("SITUS_Y_COORD"),
                "crs": SOURCE_GEOMETRY_CRS,
            },
        },
        "mailing_address": {
            "raw": _raw_address(
                attributes.get("OWNER_ADDRESS_LINE1"),
                attributes.get("OWNER_ADDRESS_LINE2"),
            ),
            "line1": attributes.get("OWNER_ADDRESS_LINE1"),
            "line2": attributes.get("OWNER_ADDRESS_LINE2"),
            "city": attributes.get("OWNER_CITY"),
            "state": attributes.get("OWNER_STATE"),
            "postal_code": attributes.get("OWNER_ZIP"),
        },
        "classification": {
            "property_class": attributes.get("PROP_CLASS"),
            "detail_class": attributes.get("D_CLASS"),
            "detail_class_description": attributes.get("D_CLASS_CN"),
            "dcl12": attributes.get("DCL12"),
            "tax_district": attributes.get("TAX_DIST"),
            "zone_id": attributes.get("ZONE_ID"),
            "zone_2010": attributes.get("ZONE_10"),
        },
        "assessment": {
            "land_value": attributes.get("APPRAISED_LAND_VALUE"),
            "improvement_value": attributes.get(
                "APPRAISED_IMP_VALUE"
            ),
            "parcel_value": attributes.get("APPRAISED_TOTAL_VALUE"),
            "assessed_value": attributes.get(
                "ASSESSED_TOTAL_VALUE_LOCAL"
            ),
            "assessment_class": attributes.get("PROP_CLASS"),
            "appraised_land_value": attributes.get(
                "APPRAISED_LAND_VALUE"
            ),
            "appraised_improvement_value": attributes.get(
                "APPRAISED_IMP_VALUE"
            ),
            "appraised_total_value": attributes.get(
                "APPRAISED_TOTAL_VALUE"
            ),
            "local": {
                "assessed_land_value": attributes.get(
                    "ASSESSED_LAND_VALUE_LOCAL"
                ),
                "assessed_building_value": attributes.get(
                    "ASSESSED_BLDG_VALUE_LOCAL"
                ),
                "assessed_total_value": attributes.get(
                    "ASSESSED_TOTAL_VALUE_LOCAL"
                ),
                "exempt_amount": attributes.get("EXEMPT_AMT_LOCAL"),
                "taxable_amount": attributes.get("TAXABLE_AMT_LOCAL"),
            },
            "school": {
                "assessed_land_value": attributes.get(
                    "ASSESSED_LAND_VALUE_SCH"
                ),
                "assessed_building_value": attributes.get(
                    "ASSESSED_BLDG_VALUE_SCH"
                ),
                "assessed_total_value": attributes.get(
                    "ASSESSED_TOTAL_VALUE_SCH"
                ),
                "exempt_amount": attributes.get("EXEMPT_AMT_SCH"),
                "taxable_amount": attributes.get("TAXABLE_AMT_SCH"),
            },
            "currency": "USD",
        },
        "physical_characteristics": {
            "land_area": attributes.get("LAND_AREA"),
            "residential_original_year_built": attributes.get(
                "RES_ORIG_YEAR_BUILT"
            ),
            "residential_above_grade_area": attributes.get(
                "RES_ABOVE_GRADE_AREA"
            ),
            "commercial_original_year_built": attributes.get(
                "COM_ORIG_YEAR_BUILT"
            ),
            "commercial_gross_area": attributes.get("COM_GROSS_AREA"),
            "commercial_net_area": attributes.get("COM_NET_AREA"),
            "commercial_structure_type": attributes.get(
                "COM_STRUCTURE_TYPE"
            ),
            "total_units": attributes.get("TOT_UNITS"),
        },
        "legal_description_raw": attributes.get("LEGAL_DESC"),
        "last_sale": {
            "source_document_ref": reception_number,
            "instrument_type": attributes.get("ASAL_INSTR"),
            "sale_date": _sale_date(attributes),
            "sale_month_day_raw": attributes.get("SALE_MONTHDAY"),
            "sale_year": attributes.get("SALE_YEAR"),
            "consideration": attributes.get("SALE_PRICE"),
            "currency": "USD",
        },
        "recorder_join": (
            {
                "source_id": RECORDER_SOURCE_ID,
                "department": "RP",
                "instrument_number": reception_number,
                "search_url": RECORDER_SEARCH_URL,
            }
            if reception_number
            else None
        ),
        "source_last_updated": source_last_updated,
        "source_system_start_date": source_last_updated,
        "source_shape_area": attributes.get("Shape__Area"),
        "source_shape_length": attributes.get("Shape__Length"),
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
) -> PublicRecordsResult:
    operation = args.command
    selector = getattr(args, "query", None)
    limit = 1 if operation == "probe" else args.limit
    if operation != "probe" and args.max_records is not None:
        limit = (
            min(limit, args.max_records)
            if limit is not None
            else args.max_records
        )
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
        fetched = source_client.query(
            where=_where(operation, selector),
            out_fields=OUT_FIELDS,
            parameters={"orderByFields": "OBJECTID"},
            requested_limit=limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
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
    log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"Denver property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Denver property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        owner_names = ", ".join(
            owner["raw_name"] for owner in record["owners"]
        )
        print(
            f"  {record['native_parcel_id']} | "
            f"{record['situs_address'].get('raw') or '?'} | "
            f"{owner_names or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int)
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
        description=(
            "Query the official City and County of Denver property parcel layer"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("owner", "Search assessor owner-name observations"),
        ("address", "Search situs address observations"),
        ("parcel", "Look up a Denver schedule or parcel number"),
        ("objectid", "Look up one ArcGIS object ID"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_shared_arguments(command_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Query one stable parcel sentinel",
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
            "limit is optional; page-size and timeout must be positive; "
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
