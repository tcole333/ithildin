#!/usr/bin/env python3
"""Maryland statewide real-property assessments via official Socrata data.

The source dataset is published as "Maryland Real Property
Assessments_Hidden Property Owner Names." The API contains parcel, situs,
assessment, deed, and historical grantor fields but omits current-owner names.
Normalized records preserve that source-withheld state explicitly.

Usage:
    uv run python tools/query_md_property.py address "7 TRAYMORE RD"
    uv run python tools/query_md_property.py parcel 04030311078580
    uv run python tools/query_md_property.py probe --output /tmp/md-probe.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import requests

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


SOURCE_ID = "us-md-sdat-property-hidden"
BASE_URL = "https://opendata.maryland.gov/resource"
DATASET_ID = "ed4q-f8tm"
DATASET_NAME = "Maryland Real Property Assessments_Hidden Property Owner Names"
DATASET_URL = (
    "https://opendata.maryland.gov/Business-and-Economy/"
    "Maryland-Real-Property-Assessments_Hidden-Property/ed4q-f8tm"
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

FIELDS = {
    "jurisdiction_code": "jurisdiction_code_mdp_field_jurscode",
    "county_name": "county_name_mdp_field_cntyname",
    "account_id": "account_id_mdp_field_acctid",
    "property_link": "real_property_search_link",
    "finder_link": "finder_online_link",
    "longitude": "mdp_longitude_mdp_field_digxcord_converted_to_wgs84",
    "latitude": "mdp_latitude_mdp_field_digycord_converted_to_wgs84",
    "county_code": "record_key_county_code_sdat_field_1",
    "district": "record_key_district_ward_sdat_field_2",
    "account_number": "record_key_account_number_sdat_field_3",
    "geographic_code": (
        "record_key_geographic_code_mdp_field_geogcode_sdat_field_5"
    ),
    "owner_occupancy": (
        "record_key_owner_occupancy_code_mdp_field_ooi_sdat_field_6"
    ),
    "address": "mdp_street_address_mdp_field_address",
    "city": "mdp_street_address_city_mdp_field_city",
    "postal_code": "mdp_street_address_zip_code_mdp_field_zipcode",
    "unit": "mdp_street_address_units_mdp_field_strtunt",
    "legal_1": "legal_description_line_1_mdp_field_legal1_sdat_field_17",
    "legal_2": "legal_description_line_2_mdp_field_legal2_sdat_field_18",
    "legal_3": "legal_description_line_3_mdp_field_legal3_sdat_field_19",
    "deed_liber": "deed_reference_1_liber_mdp_field_dr1liber_sdat_field_30",
    "deed_folio": "deed_reference_1_folio_mdp_field_dr1folio_sdat_field_31",
    "base_land": "base_cycle_data_land_value_sdat_field_154",
    "base_improvements": "base_cycle_data_improvements_value_sdat_field_155",
    "current_land": (
        "current_cycle_data_land_value_mdp_field_names_nfmlndvl_curlndvl_"
        "and_sallndvl_sdat_field_164"
    ),
    "current_improvements": (
        "current_cycle_data_improvements_value_mdp_field_names_nfmimpvl_"
        "curimpvl_and_salimpvl_sdat_field_165"
    ),
    "current_total": "current_assessment_year_total_assessment_sdat_field_172",
    "assessment_cycle_year": "assessment_cycle_year_sdat_field_399",
    "source_updated": "date_of_most_recent_open_data_portal_record_update",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=DATASET_NAME,
    source_role="statewide_assessment_parcel_sales",
    base_url=BASE_URL,
    dataset_id=DATASET_ID,
    metadata={
        "authority": (
            "Maryland State Department of Assessments and Taxation and "
            "Maryland Department of Planning"
        ),
        "coverage": "State of Maryland",
        "dataset_url": DATASET_URL,
        "owner_field_state": "withheld_by_source",
        "license": "Public Domain",
        "verified_metadata_sha256": (
            "1b808d59db040ff38349bc5e1c1a1cd397b415f519629de01b534f29f434984f"
        ),
    },
)

SOURCE_WARNINGS = (
    "The official dataset is labeled 'Hidden Property Owner Names' and its API schema omits current-owner name fields.",
    "The source metadata states that portal records update at different frequencies from MDP and SDAT products.",
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "dataset_id": DATASET_ID,
        "normalization_version": 1,
        "fields": FIELDS,
        "owner_visibility": "withheld_by_source",
    }
)


def _sql_literal(value: str) -> str:
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized.replace("'", "''")


def _county_code(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits:
        raise ValueError("Maryland SDAT county code must be 01 through 24")
    normalized = digits.zfill(2)
    if normalized not in COUNTY_GEOIDS:
        raise ValueError("Maryland SDAT county code must be 01 through 24")
    return normalized


def _account_id(value: str) -> str:
    normalized = "".join(
        character for character in str(value).upper() if character.isalnum()
    )
    if not normalized:
        raise ValueError("account or parcel identifier must not be blank")
    return normalized


def _where(
    operation: str,
    selector: str | None,
    county_code: str | None,
) -> str:
    if operation == "probe":
        expression = "1=1"
    elif operation == "address":
        value = _sql_literal(selector or "").upper()
        expression = (
            f"UPPER({FIELDS['address']}) LIKE '%{value}%' "
            f"OR UPPER({FIELDS['legal_2']}) LIKE '%{value}%'"
        )
    elif operation == "parcel":
        value = _sql_literal(_account_id(selector or ""))
        expression = (
            f"{FIELDS['account_id']}='{value}' "
            f"OR {FIELDS['account_number']}='{value}'"
        )
    else:
        raise ValueError(f"unsupported Maryland operation: {operation}")
    if county_code:
        expression = (
            f"({expression}) AND {FIELDS['county_code']}='{county_code}'"
        )
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
        app_token=os.environ.get("MARYLAND_SODA_APP_TOKEN"),
        page_size=min(args.page_size, reviewed_page_size, effective_limit),
        max_records=effective_limit,
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
        session=requests.Session(),
    )


def _number(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _source_url(value: Any) -> str | None:
    if isinstance(value, Mapping):
        url = value.get("url")
        return str(url) if url else None
    return str(value) if value else None


def _date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text in {"0000.00.00", "00000000"}:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    parts = text.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return "-".join(parts)
    return text


def _sale_segment(row: Mapping[str, Any], number: int) -> dict[str, Any] | None:
    if number == 1:
        prefix = "sales_segment_1"
        suffixes = {
            "transfer_number": "_transfer_number_mdp_field_transno1_sdat_field_79",
            "grantor": "_grantor_name_mdp_field_grntnam1_sdat_field_80",
            "liber": (
                "_grantor_deed_reference_1_liber_mdp_field_gr1libr1_sdat_field_82"
            ),
            "folio": (
                "_grantor_deed_reference_1_folio_mdp_field_gr1folo1_sdat_field_83"
            ),
            "conveyance": "_how_conveyed_ind_mdp_field_convey1_sdat_field_87",
            "date": "_transfer_date_yyyy_mm_dd_mdp_field_tradate_sdat_field_89",
            "consideration": "_consideration_mdp_field_considr1_sdat_field_90",
        }
    else:
        start = {2: 99, 3: 119}[number]
        prefix = f"sales_segment_{number}"
        suffixes = {
            "transfer_number": f"_transfer_number_sdat_field_{start}",
            "grantor": f"_grantor_name_sdat_field_{start + 1}",
            "liber": (
                f"_grantor_deed_reference_1_liber_sdat_field_{start + 3}"
            ),
            "folio": (
                f"_grantor_deed_reference_1_folio_sdat_field_{start + 4}"
            ),
            "conveyance": f"_how_conveyed_ind_sdat_field_{start + 8}",
            "date": f"_transfer_date_yyyy_mm_dd_sdat_field_{start + 10}",
            "consideration": f"_consideration_sdat_field_{start + 11}",
        }
    values = {key: row.get(prefix + suffix) for key, suffix in suffixes.items()}
    if not any(value not in (None, "", "000000") for value in values.values()):
        return None
    return {
        "segment": number,
        "transfer_number": values["transfer_number"],
        "party": {
            "raw_name": values["grantor"],
            "role": "historical_grantor",
        },
        "deed_reference": {
            "liber": values["liber"],
            "folio": values["folio"],
        },
        "conveyance": values["conveyance"],
        "transfer_date": _date(values["date"]),
        "consideration": _number(values["consideration"]),
        "currency": "USD",
    }


def _jurisdiction(
    county_code: str | None,
) -> JurisdictionMetadata:
    if county_code:
        geoid, name = COUNTY_GEOIDS[county_code]
        return JurisdictionMetadata(
            jurisdiction_id=geoid,
            name=name,
            state_code="MD",
            county_fips=geoid,
        )
    return JurisdictionMetadata(
        jurisdiction_id="24",
        name="Maryland",
        state_code="MD",
    )


def build_query(
    operation: str,
    selector: str | None,
    *,
    county_code: str | None,
    limit: int,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=_jurisdiction(county_code),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "sdat_county_code": county_code,
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _normalize_record(
    row: Mapping[str, Any], *, response_schema_fingerprint: str
) -> dict[str, Any]:
    raw = dict(row)
    account_id = str(raw.get(FIELDS["account_id"]) or "").strip()
    source_county_code = _county_code(
        str(raw.get(FIELDS["county_code"]) or "").strip() or None
    )
    if not account_id:
        raise ValueError("Maryland assessment row lacks account_id")
    county_geoid, canonical_county_name = (
        COUNTY_GEOIDS[source_county_code]
        if source_county_code
        else ("24", "Maryland")
    )
    sales = [
        segment
        for number in (1, 2, 3)
        if (segment := _sale_segment(raw, number)) is not None
    ]
    legal_lines = [
        str(raw.get(FIELDS[key])).strip()
        for key in ("legal_1", "legal_2", "legal_3")
        if str(raw.get(FIELDS[key]) or "").strip()
    ]
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID, county_geoid, "parcel", account_id
        ),
        "source_id": SOURCE_ID,
        "dataset_id": DATASET_ID,
        "jurisdiction": {
            "state_code": "MD",
            "county_name": (
                raw.get(FIELDS["county_name"]) or canonical_county_name
            ),
            "county_geoid": county_geoid,
            "sdat_county_code": source_county_code,
            "jurisdiction_code": raw.get(FIELDS["jurisdiction_code"]),
        },
        "native_parcel_id": account_id,
        "record_key": {
            "district_or_ward": raw.get(FIELDS["district"]),
            "account_number": raw.get(FIELDS["account_number"]),
            "geographic_code": raw.get(FIELDS["geographic_code"]),
        },
        "owners": [],
        "owner_visibility": {
            "state": "withheld_by_source",
            "dataset_name": DATASET_NAME,
            "current_owner_name_field_present": False,
        },
        "owner_occupancy_code": raw.get(FIELDS["owner_occupancy"]),
        "situs_address": {
            "raw": (
                str(raw.get(FIELDS["address"])).strip()
                if raw.get(FIELDS["address"])
                else None
            ),
            "unit": raw.get(FIELDS["unit"]),
            "city": raw.get(FIELDS["city"]),
            "state": "MD",
            "postal_code": raw.get(FIELDS["postal_code"]),
        },
        "location": {
            "longitude": _number(raw.get(FIELDS["longitude"])),
            "latitude": _number(raw.get(FIELDS["latitude"])),
        },
        "legal_description": {
            "lines": legal_lines,
        },
        "current_deed_reference": {
            "liber": raw.get(FIELDS["deed_liber"]),
            "folio": raw.get(FIELDS["deed_folio"]),
        },
        "assessment": {
            "cycle_year": raw.get(FIELDS["assessment_cycle_year"]),
            "base_land_value": _number(raw.get(FIELDS["base_land"])),
            "base_improvement_value": _number(
                raw.get(FIELDS["base_improvements"])
            ),
            "current_land_value": _number(raw.get(FIELDS["current_land"])),
            "current_improvement_value": _number(
                raw.get(FIELDS["current_improvements"])
            ),
            "current_total_assessment": _number(
                raw.get(FIELDS["current_total"])
            ),
            "currency": "USD",
        },
        "sales_history": sales,
        "source_links": {
            "real_property_search": _source_url(
                raw.get(FIELDS["property_link"])
            ),
            "finder": _source_url(raw.get(FIELDS["finder_link"])),
        },
        "source_record_updated": _date(raw.get(FIELDS["source_updated"])),
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
    county_code = _county_code(getattr(args, "county_code", None))
    limit = 1 if operation == "probe" else args.limit
    query = build_query(
        operation,
        selector,
        county_code=county_code,
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
                "$where": _where(operation, selector, county_code),
                "$order": f"{FIELDS['account_id']}",
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
        summary=f"Maryland property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Maryland property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record['native_parcel_id']} | "
            f"{record['situs_address'].get('raw') or '?'} | "
            f"owner={record['owner_visibility']['state']}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--county-code", help="Optional two-digit Maryland SDAT county code"
    )
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
        description=(
            "Query Maryland statewide real-property assessments with "
            "source-withheld owner semantics"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    address = subparsers.add_parser(
        "address", help="Search source street-address and legal-address fields"
    )
    address.add_argument("query")
    _add_shared_arguments(address)

    parcel = subparsers.add_parser(
        "parcel", help="Look up a statewide account ID or account number"
    )
    parcel.add_argument("query")
    _add_shared_arguments(parcel)

    probe = subparsers.add_parser("probe", help="Run one bounded health query")
    _add_shared_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit <= 0 or args.page_size <= 0:
        parser.error("limit and page-size must be positive")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
