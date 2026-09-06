#!/usr/bin/env python3
"""East Baton Rouge Parish property records via official Socrata APIs.

The adapter combines assessor, parcel, planning, and adjudicated-property
    datasets while preserving each row's source dataset. Source capabilities and
    endpoint paging metadata come from the central catalog, and all remote outcomes
    use the canonical public-record result envelope.

Usage:
    uv run python tools/query_la_property.py owner "SMITH" --parish ebr
    uv run python tools/query_la_property.py address "MAIN ST" --parish ebr
    uv run python tools/query_la_property.py parcel "011-0499-3" --parish ebr
    uv run python tools/query_la_property.py details "1104993" --parish ebr
    uv run python tools/query_la_property.py adjudicated "SMITH" --parish ebr
    uv run python tools/query_la_property.py parishes
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
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
    )
    from tools.public_records_http import (
        PaginatedFetch,
        PublicRecordsHTTPError,
        SocrataSODAClient,
    )
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH,
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
    )
    from public_records_http import (
        PaginatedFetch,
        PublicRecordsHTTPError,
        SocrataSODAClient,
    )
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-la-ebr-property"
DEFAULT_PARISH = "ebr"
PARISHES = {
    "ebr": {
        "name": "East Baton Rouge",
        "jurisdiction_geoid": "22033",
        "base_url": "https://data.brla.gov/resource",
        "token_env": "BRLA_SODA_APP_TOKEN",
        "datasets": {
            "tax_roll": "myfc-nh6n",
            "tax_parcel": "ei2c-krsr",
            "property_info": "re5c-hrw9",
            "adjudicated": "a4h4-zi7e",
        },
    },
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="East Baton Rouge Parish Property Open Data",
    source_role="assessment_parcel_tax_status",
    base_url=PARISHES["ebr"]["base_url"],
    dataset_id=",".join(PARISHES["ebr"]["datasets"].values()),
    metadata={
        "authority": "City of Baton Rouge and Parish of East Baton Rouge",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
    },
)

SOURCE_WARNINGS = (
    "Taxpayer and parcel-owner names are assessor observations, not proof of legal title or beneficial ownership.",
    "Assessment, planning, and adjudication datasets have distinct update cycles and should not be treated as a single contemporaneous record.",
)


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_env()


def _sql_literal(value: str) -> str:
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized.replace("'", "''")


def _format_assessment_no(raw_digits: str) -> str:
    padded = raw_digits.zfill(8)
    return f"{padded[:3]}-{padded[3:7]}-{padded[7:]}"


def _format_money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value) if value else ""
    return f"${amount:,.0f}"


def build_query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    parish: str,
    requested_limit: int,
    cursor: str | None,
) -> PublicRecordsQuery:
    config = PARISHES[parish]
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=config["jurisdiction_geoid"],
            name=f"{config['name']} Parish",
            state_code="LA",
            county_fips=config["jurisdiction_geoid"],
            locality=config["name"],
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={"parish": parish, **dict(parameters)},
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={"limit_semantics": "per_dataset"},
        ),
    )


def _require_access(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(getattr(args, "catalog_db", DEFAULT_DB_PATH))
    config_path = Path(
        getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
    )
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=db_path,
        config_path=config_path,
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _access_failure(
    query: PublicRecordsQuery,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        contract_error = PublicRecordsError(
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
        contract_error = PublicRecordsError(
            code="acquisition_route_unavailable",
            message=str(error),
            category="access_control",
            retryable=False,
        )
    return PublicRecordsResult.failure(
        query,
        status,
        [contract_error],
        warnings=SOURCE_WARNINGS,
    )


class _EBRSource:
    """Shared Socrata acquisition context for the configured parish datasets."""

    def __init__(self, args: argparse.Namespace, decision: Mapping[str, Any]) -> None:
        limits = decision.get("limits", {})
        requested_interval = float(getattr(args, "minimum_interval", 0.5))
        requested_cap = getattr(args, "max_records", None)
        if requested_cap is not None:
            requested_cap = int(requested_cap)
        reviewed_interval = limits.get("minimum_interval_seconds")
        self.minimum_interval = max(
            requested_interval,
            float(reviewed_interval) if reviewed_interval is not None else 0.0,
        )
        self.max_records = requested_cap
        requested_page_size = int(getattr(args, "page_size", 1_000))
        reviewed_page_size = limits.get("maximum_page_size")
        page_size_values = [requested_page_size]
        if self.max_records is not None:
            page_size_values.append(self.max_records)
        if reviewed_page_size is not None:
            page_size_values.append(int(reviewed_page_size))
        self.page_size = min(page_size_values)
        self.timeout = float(getattr(args, "timeout", 60.0))
        self._clients: dict[str, SocrataSODAClient] = {}
        self._last_query_finished: float | None = None

    def _client(self, parish: str, dataset_key: str) -> SocrataSODAClient:
        cache_key = f"{parish}:{dataset_key}"
        if cache_key not in self._clients:
            config = PARISHES[parish]
            self._clients[cache_key] = SocrataSODAClient(
                config["base_url"],
                config["datasets"][dataset_key],
                app_token=os.environ.get(config["token_env"]),
                page_size=self.page_size,
                max_records=self.max_records,
                timeout=self.timeout,
                minimum_interval=self.minimum_interval,
            )
        return self._clients[cache_key]

    def query(
        self,
        parish: str,
        dataset_key: str,
        parameters: Mapping[str, Any],
        *,
        requested_limit: int,
        cursor: str | None = None,
    ) -> PaginatedFetch:
        if self._last_query_finished is not None:
            elapsed = time.monotonic() - self._last_query_finished
            if elapsed < self.minimum_interval:
                time.sleep(self.minimum_interval - elapsed)
        try:
            return self._client(parish, dataset_key).query(
                parameters,
                requested_limit=requested_limit,
                max_records=self.max_records,
                cursor=cursor,
            )
        finally:
            self._last_query_finished = time.monotonic()


def _encode_cursor(cursors: Mapping[str, str | None]) -> str | None:
    nonempty = {key: value for key, value in cursors.items() if value}
    if not nonempty:
        return None
    payload = canonical_json(nonempty).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"ebr:{encoded}"


def _decode_cursor(cursor: str | None) -> dict[str, str]:
    if not cursor:
        return {}
    if not cursor.startswith("ebr:"):
        raise ValueError("invalid East Baton Rouge continuation cursor")
    encoded = cursor[4:]
    padding = "=" * (-len(encoded) % 4)
    try:
        value = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid East Baton Rouge continuation cursor") from error
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError("invalid East Baton Rouge continuation cursor")
    return value


def _record(dataset_key: str, dataset_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "dataset": dataset_key,
        "dataset_id": dataset_id,
        "record": dict(row),
    }


def _finalize(
    query: PublicRecordsQuery,
    records: Sequence[Mapping[str, Any]],
    *,
    cursors: Mapping[str, str | None],
    warnings: Sequence[str],
    failures: Sequence[PublicRecordsHTTPError],
    truncated: bool,
) -> PublicRecordsResult:
    next_cursor = _encode_cursor(cursors)
    all_warnings = tuple(dict.fromkeys((*SOURCE_WARNINGS, *warnings)))
    if failures:
        status = ResultStatus.PARTIAL if records else failures[0].result_status
        return PublicRecordsResult.failure(
            query,
            status,
            [error.to_contract_error() for error in failures],
            records=records,
            next_cursor=next_cursor,
            warnings=all_warnings,
        )
    if truncated:
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            next_cursor=next_cursor,
            warnings=all_warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        warnings=all_warnings,
    )


def _fetch_specs(
    source: _EBRSource | Any,
    parish: str,
    specs: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    requested_limit: int,
    input_cursors: Mapping[str, str],
) -> tuple[
    list[dict[str, Any]],
    dict[str, str | None],
    list[str],
    list[PublicRecordsHTTPError],
    bool,
    dict[str, list[dict[str, Any]]],
]:
    records: list[dict[str, Any]] = []
    next_cursors: dict[str, str | None] = {}
    warnings: list[str] = []
    failures: list[PublicRecordsHTTPError] = []
    truncated = False
    raw_by_dataset: dict[str, list[dict[str, Any]]] = {}
    for dataset_key, parameters in specs:
        try:
            fetched = source.query(
                parish,
                dataset_key,
                parameters,
                requested_limit=requested_limit,
                cursor=input_cursors.get(dataset_key),
            )
        except PublicRecordsHTTPError as error:
            failures.append(error)
            continue
        dataset_id = PARISHES[parish]["datasets"][dataset_key]
        rows = [dict(row) for row in fetched.records]
        raw_by_dataset[dataset_key] = rows
        records.extend(_record(dataset_key, dataset_id, row) for row in rows)
        next_cursors[dataset_key] = fetched.next_cursor
        warnings.extend(fetched.warnings)
        truncated = truncated or fetched.truncated_by_cap
    return (
        records,
        next_cursors,
        warnings,
        failures,
        truncated,
        raw_by_dataset,
    )


def _operation_specs(
    args: argparse.Namespace,
) -> tuple[list[tuple[str, Mapping[str, Any]]], dict[str, Any]]:
    operation = args.command
    if operation == "owner":
        value = _sql_literal(args.query).upper()
        return (
            [
                (
                    "tax_roll",
                    {
                        "$where": f"upper(taxpayer_name) LIKE '%{value}%'",
                        "$order": "assessment_no_new, tax_year",
                    },
                ),
                (
                    "tax_parcel",
                    {
                        "$where": f"upper(owner) LIKE '%{value}%'",
                        "$order": "assessment_num",
                    },
                ),
            ],
            {"owner_name": args.query},
        )
    if operation == "address":
        value = _sql_literal(args.query).upper()
        return (
            [
                (
                    "tax_parcel",
                    {
                        "$where": f"upper(physical_address) LIKE '%{value}%'",
                        "$order": "assessment_num",
                    },
                ),
                (
                    "property_info",
                    {
                        "$where": f"upper(full_address) LIKE '%{value}%'",
                        "$order": "full_address, lot_id",
                    },
                ),
            ],
            {"address": args.query},
        )
    if operation in {"parcel", "details"}:
        raw = args.assessment_no.replace("-", "").strip()
        if not raw:
            raise ValueError("assessment number must not be blank")
        formatted = _format_assessment_no(raw) if raw.isdigit() else args.assessment_no
        return (
            [
                (
                    "tax_roll",
                    {
                        "$where": (
                            f"assessment_no_new='{_sql_literal(raw)}' OR "
                            f"assessment_no='{_sql_literal(formatted)}'"
                        ),
                        "$order": "tax_year DESC, assessment_no_new",
                    },
                ),
                (
                    "tax_parcel",
                    {
                        "$where": f"assessment_num='{_sql_literal(formatted)}'",
                        "$order": "assessment_num",
                    },
                ),
            ],
            {
                "assessment_number": args.assessment_no,
                "assessment_number_normalized": formatted,
            },
        )
    if operation == "adjudicated":
        value = _sql_literal(args.query).upper()
        return (
            [
                (
                    "adjudicated",
                    {
                        "$where": f"upper(owner) LIKE '%{value}%'",
                        "$order": "assessment_num, tax_roll_year DESC",
                    },
                )
            ],
            {"owner_name": args.query, "tax_status": "adjudicated"},
        )
    raise ValueError(f"unsupported remote command: {operation}")


def _execute_remote(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    source: _EBRSource | Any,
) -> PublicRecordsResult:
    input_cursors = _decode_cursor(args.cursor)
    specs, _ = _operation_specs(args)
    (
        records,
        next_cursors,
        warnings,
        failures,
        truncated,
        raw_by_dataset,
    ) = _fetch_specs(
        source,
        args.parish,
        specs,
        requested_limit=args.limit,
        input_cursors=input_cursors,
    )

    if args.command == "details":
        parcel_rows = raw_by_dataset.get("tax_parcel", [])
        if parcel_rows:
            physical_address = str(
                parcel_rows[0].get("physical_address") or ""
            ).strip()
            if physical_address:
                details_specs = [
                    (
                        "property_info",
                        {
                            "$where": (
                                "upper(full_address) = "
                                f"'{_sql_literal(physical_address).upper()}'"
                            ),
                            "$order": "full_address, lot_id",
                        },
                    )
                ]
                (
                    detail_records,
                    detail_cursors,
                    detail_warnings,
                    detail_failures,
                    detail_truncated,
                    _,
                ) = _fetch_specs(
                    source,
                    args.parish,
                    details_specs,
                    requested_limit=args.limit,
                    input_cursors=input_cursors,
                )
                records.extend(detail_records)
                next_cursors.update(detail_cursors)
                warnings.extend(detail_warnings)
                failures.extend(detail_failures)
                truncated = truncated or detail_truncated

    return _finalize(
        query,
        records,
        cursors=next_cursors,
        warnings=warnings,
        failures=failures,
        truncated=truncated,
    )


def execute(
    args: argparse.Namespace,
    *,
    source: _EBRSource | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    """Execute a remote EBR query and return a canonical result envelope."""
    try:
        _, parameters = _operation_specs(args)
        query = build_query(
            args.command,
            parameters,
            parish=args.parish,
            requested_limit=args.limit,
            cursor=args.cursor,
        )
    except ValueError as error:
        query = build_query(
            args.command,
            {"invalid_request": True},
            parish=getattr(args, "parish", DEFAULT_PARISH),
            requested_limit=max(1, getattr(args, "limit", 1)),
            cursor=getattr(args, "cursor", None),
        )
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="invalid_query",
                    message=str(error),
                    category="query",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )

    try:
        decision = dict(access_decision or _require_access(args))
    except (
        AcquisitionUnavailableError,
        CatalogError,
        OSError,
        ValueError,
    ) as error:
        result = _access_failure(query, error)
    else:
        acquisition = source or _EBRSource(args, decision)
        try:
            result = _execute_remote(args, query, acquisition)
        except PublicRecordsHTTPError as error:
            result = PublicRecordsResult.failure(
                query,
                error.result_status,
                [error.to_contract_error()],
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

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _print_record(wrapper: Mapping[str, Any]) -> None:
    dataset = wrapper["dataset"]
    record = wrapper["record"]
    if dataset == "tax_roll":
        print(f"  {record.get('taxpayer_name', '?')} [tax roll]")
        print(
            "    Assessment: "
            f"{record.get('assessment_no', record.get('assessment_no_new', ''))} "
            f"| Tax Year: {record.get('tax_year', '')}"
        )
        if record.get("fair_market_val"):
            print(
                f"    Fair Market Value: {_format_money(record['fair_market_val'])}"
            )
    elif dataset == "tax_parcel":
        print(f"  {record.get('owner', '?')} [parcel]")
        print(
            f"    Assessment: {record.get('assessment_num', '')} | "
            f"Property: {record.get('physical_address', '')}"
        )
    elif dataset == "property_info":
        print(f"  {record.get('full_address', '?')} [property info]")
        print(
            f"    Zoning: {record.get('zoning_type', '')} | "
            f"Land Use: {record.get('existing_land_use', '')}"
        )
    else:
        print(f"  {record.get('owner', '?')} [adjudicated]")
        print(
            f"    Assessment: {record.get('assessment_num', '')} | "
            f"Tax Year: {record.get('tax_roll_year', '')}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"East Baton Rouge property {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"East Baton Rouge property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for wrapper in result.records[: args.max_results]:
        _print_record(wrapper)
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def cmd_remote(args: argparse.Namespace) -> None:
    _emit(execute(args), args)


def cmd_owner(args: argparse.Namespace) -> None:
    cmd_remote(args)


def cmd_address(args: argparse.Namespace) -> None:
    cmd_remote(args)


def cmd_parcel(args: argparse.Namespace) -> None:
    cmd_remote(args)


def cmd_details(args: argparse.Namespace) -> None:
    cmd_remote(args)


def cmd_adjudicated(args: argparse.Namespace) -> None:
    cmd_remote(args)


def cmd_parishes(args: argparse.Namespace) -> None:
    data = [
        {
            "key": key,
            "name": config["name"],
            "jurisdiction_geoid": config["jurisdiction_geoid"],
            "base_url": config["base_url"],
            "datasets": config["datasets"],
            "source_id": SOURCE_ID,
        }
        for key, config in PARISHES.items()
    ]
    if write_output(data, args, summary="LA property supported parishes"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    for entry in data:
        print(f"{entry['key']}: {entry['name']} ({entry['jurisdiction_geoid']})")


def _add_remote_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--parish",
        default=DEFAULT_PARISH,
        choices=tuple(PARISHES),
    )
    parser.add_argument("--limit", type=int, default=50, help="Records per dataset")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--cursor", help="Composite continuation cursor")
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling per dataset",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.5,
        help="Client pacing in seconds (a documented catalog minimum, if any, also applies)",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--catalog-db", default=str(DEFAULT_DB_PATH))
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query East Baton Rouge official property open data"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    owner = sub.add_parser("owner", help="Search taxpayer and parcel-owner names")
    owner.add_argument("query")
    _add_remote_arguments(owner)

    address = sub.add_parser("address", help="Search parcel and planning addresses")
    address.add_argument("query")
    _add_remote_arguments(address)

    parcel = sub.add_parser("parcel", help="Look up an assessment number")
    parcel.add_argument("assessment_no")
    _add_remote_arguments(parcel)

    details = sub.add_parser("details", help="Join parcel details across datasets")
    details.add_argument("assessment_no")
    _add_remote_arguments(details)

    adjudicated = sub.add_parser(
        "adjudicated",
        help="Search tax-defaulted property records",
    )
    adjudicated.add_argument("query")
    _add_remote_arguments(adjudicated)

    parishes = sub.add_parser("parishes", help="List configured parish sources")
    add_output_args(parishes)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for name in ("limit", "max_results", "page_size", "max_records"):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"{name.replace('_', '-')} must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("minimum-interval must not be negative")
    commands = {
        "owner": cmd_owner,
        "address": cmd_address,
        "parcel": cmd_parcel,
        "details": cmd_details,
        "adjudicated": cmd_adjudicated,
        "parishes": cmd_parishes,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
