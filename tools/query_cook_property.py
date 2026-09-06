#!/usr/bin/env python3
"""Cook County Assessor Parcel Universe via the official Socrata API.

The Parcel Universe is a historical parcel/geography dataset covering
1999-present. Its current schema has PIN, tax-year, classification, centroid,
and district fields; it does not contain owner-name or street-address fields.

Usage:
    uv run python tools/query_cook_property.py parcel 01-01-106-009-1001
    uv run python tools/query_cook_property.py parcel 0101106009 --tax-year 2025
    uv run python tools/query_cook_property.py probe --output /tmp/cook-probe.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
        PublicRecordsHTTPError,
        SocrataSODAClient,
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
        PublicRecordsHTTPError,
        SocrataSODAClient,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-il-cook-parcel-universe"
BASE_URL = "https://datacatalog.cookcountyil.gov/resource"
DATASET_ID = "nj4t-kc8j"
DATASET_URL = (
    "https://datacatalog.cookcountyil.gov/Property-Taxation/"
    "Assessor-Parcel-Universe/nj4t-kc8j"
)
COOK_COUNTY_GEOID = "17031"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Cook County Assessor Parcel Universe",
    source_role="historic_parcel_geography",
    base_url=BASE_URL,
    dataset_id=DATASET_ID,
    metadata={
        "authority": "Cook County Assessor's Office",
        "coverage": "Cook County, Illinois; tax years 1999-present",
        "dataset_url": DATASET_URL,
        "owner_field_state": "not_present_in_dataset_schema",
        "street_address_field_state": "not_present_in_dataset_schema",
        "verified_metadata_sha256": (
            "7123576c8b0e91c4690b9c43b36f7e347d80d85fc999f51c8dbfb5990318a3fb"
        ),
    },
)

SOURCE_WARNINGS = (
    "The official Parcel Universe schema contains no owner-name or street-address field.",
    "The official metadata instructs users to zero-pad Parcel Index Numbers to 14 digits.",
    "The current tax year may remain incomplete until the assessment roll is certified.",
)

ADAPTER_FIELDS = (
    "pin",
    "pin10",
    "year",
    "class",
    "triad_name",
    "triad_code",
    "township_name",
    "township_code",
    "nbhd_code",
    "tax_code",
    "zip_code",
    "lon",
    "lat",
    "x_3435",
    "y_3435",
    "row_id",
)
ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "dataset_id": DATASET_ID,
        "normalization_version": 1,
        "fields": ADAPTER_FIELDS,
    }
)


def _sql_literal(value: str) -> str:
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized.replace("'", "''")


def _normalize_pin(value: str) -> tuple[str, str]:
    raw = _require_selector(value)
    digits = "".join(character for character in raw if character.isdigit())
    if not digits:
        raise ValueError("Cook County PIN must contain digits")
    if len(digits) <= 10:
        return "pin10", digits.zfill(10)
    if len(digits) <= 14:
        return "pin", digits.zfill(14)
    raise ValueError("Cook County PIN must contain at most 14 digits")


def _require_selector(value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized


def _normalize_year(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _where(operation: str, selector: str | None, tax_year: int | None) -> str:
    if operation == "probe":
        expression = "1=1"
    elif operation == "parcel":
        field, normalized = _normalize_pin(selector or "")
        expression = f"{field}='{_sql_literal(normalized)}'"
    else:
        raise ValueError(f"unsupported Cook County operation: {operation}")
    if tax_year is not None:
        expression = f"({expression}) AND year={int(tax_year)}"
    return expression


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
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
    args: argparse.Namespace, access_contract: Mapping[str, Any]
) -> SocrataSODAClient:
    limits = access_contract.get("limits") or {}
    reviewed_page_size = int(limits.get("maximum_page_size") or args.page_size)
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    effective_limit = args.limit
    return SocrataSODAClient(
        BASE_URL,
        DATASET_ID,
        app_token=os.environ.get("COOK_COUNTY_SODA_APP_TOKEN"),
        page_size=min(args.page_size, reviewed_page_size, effective_limit),
        max_records=effective_limit,
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
    )


def build_query(
    operation: str,
    selector: str | None,
    *,
    tax_year: int | None,
    limit: int,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COOK_COUNTY_GEOID,
            name="Cook County, Illinois",
            state_code="IL",
            county_fips=COOK_COUNTY_GEOID,
            locality="Cook County",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "tax_year": tax_year,
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _normalize_record(
    row: Mapping[str, Any], *, response_schema_fingerprint: str
) -> dict[str, Any]:
    raw = dict(row)
    pin = str(raw.get("pin") or "").strip()
    year = _normalize_year(raw.get("year"))
    source_row_id = str(raw.get("row_id") or "").strip()
    if not pin or not year:
        raise ValueError("Parcel Universe row lacks pin or tax year")
    native_id = source_row_id or f"{pin}:{year}"
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COOK_COUNTY_GEOID,
            "parcel_snapshot",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": DATASET_ID,
        "source_row_id": source_row_id or None,
        "jurisdiction": {
            "state_code": "IL",
            "county_name": "Cook County",
            "county_geoid": COOK_COUNTY_GEOID,
        },
        "native_parcel_id": pin,
        "pin10": raw.get("pin10"),
        "tax_year": year,
        "property_class": raw.get("class"),
        "owner_observation": {
            "state": "not_present_in_dataset_schema",
            "names": [],
        },
        "situs_location": {
            "street_address_state": "not_present_in_dataset_schema",
            "postal_code": raw.get("zip_code"),
            "centroid": {
                "longitude": _number(raw.get("lon")),
                "latitude": _number(raw.get("lat")),
                "x_crs_3435": _number(raw.get("x_3435")),
                "y_crs_3435": _number(raw.get("y_3435")),
            },
        },
        "assessor_geography": {
            "triad_name": raw.get("triad_name"),
            "triad_code": raw.get("triad_code"),
            "township_name": raw.get("township_name"),
            "township_code": raw.get("township_code"),
            "neighborhood_code": raw.get("nbhd_code"),
            "tax_district_code": raw.get("tax_code"),
        },
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_record": raw,
    }


def _access_failure(
    query: PublicRecordsQuery, error: Exception
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code") or "acquisition_route_unavailable"
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
        query, status, [public_error], warnings=SOURCE_WARNINGS
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    operation = args.command
    selector = getattr(args, "query", None)
    tax_year = getattr(args, "tax_year", None)
    limit = 1 if operation == "probe" else args.limit
    query = build_query(
        operation,
        selector,
        tax_year=tax_year,
        limit=limit,
        cursor=args.cursor,
    )
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        fetched = _client(args, access_contract).query(
            {
                "$where": _where(operation, selector, tax_year),
                "$order": "year DESC,row_id",
            },
            requested_limit=limit,
            cursor=args.cursor,
        )
        records = [
            _normalize_record(
                row,
                response_schema_fingerprint=fetched.schema_fingerprint,
            )
            for row in fetched.records
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

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"Cook Parcel Universe {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Cook Parcel Universe {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record['native_parcel_id']} | {record['tax_year']} | "
            f"{record['situs_location'].get('postal_code') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor from a prior result")
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.0)
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and access reviews",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Cook County Assessor Parcel Universe"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parcel = subparsers.add_parser(
        "parcel", help="Look up a 10- or 14-digit Cook County PIN"
    )
    parcel.add_argument("query")
    parcel.add_argument("--tax-year", type=int)
    _add_shared_arguments(parcel)

    probe = subparsers.add_parser("probe", help="Run one bounded health query")
    probe.add_argument("--tax-year", type=int)
    _add_shared_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit <= 0 or args.page_size <= 0:
        parser.error("limit and page-size must be positive")
    if args.tax_year is not None and args.tax_year <= 0:
        parser.error("tax-year must be positive")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
