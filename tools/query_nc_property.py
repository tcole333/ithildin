#!/usr/bin/env python3
"""North Carolina OneMap statewide parcel query adapter.

The official NC OneMap ArcGIS layer standardizes county-provided parcel
geometry and core assessor attributes across all 100 counties and the Eastern
Band of Cherokee Indians. Assessor-owner fields are dated source observations,
not proof of title, and source geometry is not a surveyed legal boundary.

The endpoint was probed before implementation:
https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1

Usage:
    uv run python tools/query_nc_property.py owner "SMITH" --county-fips 037
    uv run python tools/query_nc_property.py address "100 MAIN ST"
    uv run python tools/query_nc_property.py parcel "3013467134" --county-fips 005
    uv run python tools/query_nc_property.py probe --output /tmp/nc-probe.json
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

SOURCE_ID = "us-nc-onemap-parcels"
LAYER_URL = (
    "https://services.nconemap.gov/secure/rest/services/"
    "NC1Map_Parcels/MapServer/1"
)
SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="North Carolina OneMap Parcels",
    source_role="parcel_gis_assessment",
    base_url=LAYER_URL,
    dataset_id="NC1Map_Parcels/1",
    metadata={
        "authority": "North Carolina Center for Geographic Information and Analysis",
        "coverage": "All 100 counties plus Eastern Band of Cherokee Indians",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
    },
)

OUT_FIELDS = (
    "objectid",
    "parno",
    "altparno",
    "nparno",
    "ownname",
    "ownname2",
    "owntype",
    "subsurfown",
    "subowntype",
    "mailadd",
    "munit",
    "mcity",
    "mstate",
    "mzip",
    "siteadd",
    "sunit",
    "scity",
    "sstate",
    "szip",
    "landval",
    "improvval",
    "parval",
    "parvaltype",
    "saledate",
    "saledatetx",
    "legdecfull",
    "sourceref",
    "sourcedate",
    "sourcedatx",
    "subdivisio",
    "cntyname",
    "cntyfips",
    "stfips",
    "stcntyfips",
    "sourceagnt",
    "revisedate",
    "revdatetx",
    "reviseyear",
)

SOURCE_WARNINGS = (
    "The owner field is an assessor/county-source observation, not proof of legal title or beneficial ownership.",
    "Parcel geometry is source-provided mapping data and is not a surveyed legal boundary.",
    "Coverage, field population, and freshness vary by contributing county.",
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
    reviewed_page_size = int(limits.get("maximum_page_size") or args.page_size)
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return ArcGISRESTClient(
        LAYER_URL,
        page_size=min(args.page_size, reviewed_page_size),
        max_records=args.max_records,
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
    )


def _sql_literal(value: str) -> str:
    cleaned = " ".join(str(value).replace("\x00", "").split()).strip()
    if not cleaned:
        raise ValueError("query value must not be blank")
    return cleaned.replace("'", "''")


def _county_geoid(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 3:
        digits = f"37{digits}"
    if len(digits) != 5 or not digits.startswith("37"):
        raise ValueError("North Carolina county FIPS must be 3 digits or a 5-digit 37xxx GEOID")
    return digits


def _where(operation: str, selector: str | None, county_geoid: str | None) -> str:
    if operation == "probe":
        expression = "1=1"
    else:
        value = _sql_literal(selector or "")
        if operation == "owner":
            upper = value.upper()
            expression = (
                f"UPPER(ownname) LIKE '%{upper}%' "
                f"OR UPPER(ownname2) LIKE '%{upper}%'"
            )
        elif operation == "address":
            expression = f"UPPER(siteadd) LIKE '%{value.upper()}%'"
        elif operation == "parcel":
            expression = f"parno='{value}' OR altparno='{value}' OR nparno='{value}'"
        elif operation == "objectid":
            if not value.isdigit():
                raise ValueError("objectid must be numeric")
            expression = f"objectid={int(value)}"
        else:
            raise ValueError(f"unsupported operation: {operation}")
    if county_geoid:
        expression = f"({expression}) AND stcntyfips='{county_geoid}'"
    return expression


def _arcgis_date(value: Any, fallback: Any = None) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .date()
                .isoformat()
            )
        except (OverflowError, OSError, ValueError):
            pass
    text = str(fallback or value or "").strip()
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _nonblank(*values: Any) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes", {})
    if not isinstance(attributes_value, Mapping):
        raise ValueError("ArcGIS feature attributes must be an object")
    attributes = dict(attributes_value)
    county_geoid = str(attributes.get("stcntyfips") or "").strip() or "37"
    parcel_number = str(
        attributes.get("parno")
        or attributes.get("nparno")
        or attributes.get("objectid")
        or ""
    ).strip()
    if not parcel_number:
        raise ValueError("NC OneMap feature lacks a parcel and object identifier")

    aliases = _nonblank(attributes.get("altparno"), attributes.get("nparno"))
    owners = []
    for raw_name, owner_role in (
        (attributes.get("ownname"), "primary_assessor_owner"),
        (attributes.get("ownname2"), "secondary_assessor_owner"),
        (attributes.get("subsurfown"), "subsurface_assessor_owner"),
    ):
        if str(raw_name or "").strip():
            owners.append(
                {
                    "raw_name": str(raw_name).strip(),
                    "role": owner_role,
                    "assertion_type": "assessment_roll",
                    "confidence": "high",
                    "title_caveat": "not_proof_of_legal_or_beneficial_ownership",
                }
            )

    result = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID, county_geoid, "parcel", parcel_number
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "NC",
            "state_fips": str(attributes.get("stfips") or "37"),
            "county_name": attributes.get("cntyname"),
            "county_geoid": county_geoid,
        },
        "native_parcel_id": parcel_number,
        "alternate_parcel_ids": aliases,
        "object_id": attributes.get("objectid"),
        "owners": owners,
        "situs_address": {
            "raw": attributes.get("siteadd"),
            "unit": attributes.get("sunit"),
            "city": attributes.get("scity"),
            "state": attributes.get("sstate") or "NC",
            "postal_code": attributes.get("szip"),
        },
        "mailing_address": {
            "raw": attributes.get("mailadd"),
            "unit": attributes.get("munit"),
            "city": attributes.get("mcity"),
            "state": attributes.get("mstate"),
            "postal_code": attributes.get("mzip"),
        },
        "assessment": {
            "land_value": attributes.get("landval"),
            "improvement_value": attributes.get("improvval"),
            "parcel_value": attributes.get("parval"),
            "value_type": attributes.get("parvaltype"),
            "currency": "USD",
        },
        "last_sale": {
            "sale_date": _arcgis_date(
                attributes.get("saledate"), attributes.get("saledatetx")
            ),
            "source_document_ref": attributes.get("sourceref"),
            "source_document_date": _arcgis_date(
                attributes.get("sourcedate"), attributes.get("sourcedatx")
            ),
        },
        "legal_description_raw": attributes.get("legdecfull"),
        "subdivision": attributes.get("subdivisio"),
        "source_agent": attributes.get("sourceagnt"),
        "source_revised_date": _arcgis_date(
            attributes.get("revisedate"),
            attributes.get("revdatetx") or attributes.get("reviseyear"),
        ),
        "schema_fingerprint": schema_fingerprint,
        "raw_attributes": attributes,
    }
    if "geometry" in feature:
        result["geometry"] = feature.get("geometry")
        result["geometry_disclaimer"] = SOURCE_WARNINGS[1]
    return result


def build_query(
    operation: str,
    selector: str | None,
    *,
    county_geoid: str | None,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> PublicRecordsQuery:
    jurisdiction_name = (
        f"North Carolina county GEOID {county_geoid}"
        if county_geoid
        else "North Carolina"
    )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=county_geoid or "37",
            name=jurisdiction_name,
            state_code="NC",
            county_fips=county_geoid,
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "county_geoid": county_geoid,
                "return_geometry": return_geometry,
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    operation = args.command
    selector = getattr(args, "query", None)
    county_geoid = _county_geoid(getattr(args, "county_fips", None))
    limit = 1 if operation == "probe" else args.limit
    query = build_query(
        operation,
        selector,
        county_geoid=county_geoid,
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
        fetched = _client(args, access_contract).query(
            where=_where(operation, selector, county_geoid),
            out_fields=OUT_FIELDS,
            requested_limit=limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        records = [
            _normalize_feature(
                feature,
                schema_fingerprint=fetched.schema_fingerprint,
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
    except AcquisitionUnavailableError as error:
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        result = PublicRecordsResult.failure(
            query,
            status,
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

    count = (
        len(result.records)
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"NC OneMap {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"NC OneMap {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record['native_parcel_id']} | "
            f"{record['situs_address'].get('raw') or '?'} | "
            f"{', '.join(owner['raw_name'] for owner in record['owners']) or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county-fips", help="3-digit county code or 5-digit NC GEOID")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor from a previous result")
    parser.add_argument("--geometry", action="store_true", help="Return source geometry")
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
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
        description="Query official North Carolina OneMap statewide parcel records"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("owner", "Search assessor owner-name observations"),
        ("address", "Search full site addresses"),
        ("parcel", "Look up a native, alternate, or national parcel number"),
        ("objectid", "Look up one ArcGIS object ID"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_shared_arguments(command_parser)

    probe_parser = sub.add_parser("probe", help="Run one bounded source-health query")
    _add_shared_arguments(probe_parser)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if (
        args.limit <= 0
        or args.page_size <= 0
        or (args.max_records is not None and args.max_records <= 0)
    ):
        parser.error("limit and page-size must be positive; max-records is optional")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
