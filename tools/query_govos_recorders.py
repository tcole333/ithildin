#!/usr/bin/env python3
"""Query verified county GovOS/Kofile recorder tenants.

The county portals share one anonymous bootstrap, WebSocket search/detail, and
session-signed page-image protocol. Tenant configuration keeps source identity,
department taxonomy, jurisdiction, coverage, and health sentinels distinct.

Usage:
    uv run python tools/query_govos_recorders.py search \
      --source us-pa-berks-recorder-publicsearch 2024000062
    uv run python tools/query_govos_recorders.py search \
      --source us-oh-franklin-county-recorder-publicsearch 202607290091301
    uv run python tools/query_govos_recorders.py document \
      --source us-pa-delaware-recorder-publicsearch 187146913
    uv run python tools/query_govos_recorders.py probe \
      --source us-co-denver-recorder-publicsearch
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

try:
    from tools import query_reeves_records as recorder
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        PublicRecordsError,
        PublicRecordsResult,
        ResultStatus,
    )
except ImportError:
    import query_reeves_records as recorder
    from output_util import add_output_args, write_output
    from public_records_contract import (
        PublicRecordsError,
        PublicRecordsResult,
        ResultStatus,
    )


TENANTS = (
    recorder.RecorderTenant(
        key="pa-berks",
        source_id="us-pa-berks-recorder-publicsearch",
        name="Berks County Recorder PublicSearch",
        authority="Berks County Recorder of Deeds",
        jurisdiction_name="Berks County, Pennsylvania",
        county_geoid="42011",
        state_code="PA",
        department="RP",
        departments=("RP", "MISC"),
        base_url="https://berks.pa.publicsearch.us",
        official_linking_page=(
            "https://www.berkspa.gov/departments/recorder-of-deeds/"
            "search-records-on-line-%28register-login%29"
        ),
        coverage=(
            "Berks County recorded instruments; RP and MISC are distinct "
            "source departments"
        ),
        probe_instrument_number="2024000062",
        probe_document_id=203097905,
        probe_page_count=3,
        probe_page_sha256=(
            "6daf0d155fd3fc96dc9f49008b6a4d40"
            "a7c30719f163d66496642234ea0ca9bb"
        ),
    ),
    recorder.RecorderTenant(
        key="pa-delaware",
        source_id="us-pa-delaware-recorder-publicsearch",
        name="Delaware County Recorder PublicSearch",
        authority="Delaware County Recorder of Deeds",
        jurisdiction_name="Delaware County, Pennsylvania",
        county_geoid="42045",
        state_code="PA",
        department="RP",
        base_url="https://delaware.pa.publicsearch.us",
        official_linking_page=(
            "https://delcopa.gov/recorder-deeds/public-access-sites"
        ),
        coverage="Delaware County, Pennsylvania recorded instruments",
        probe_instrument_number="2024000062",
        probe_document_id=187146913,
        probe_page_count=5,
        probe_page_sha256=(
            "1b2c64543ab3bf4626dcef503e5bd80f"
            "2a8920bbf40a2e234e2cbb1107c19302"
        ),
    ),
    recorder.RecorderTenant(
        key="pa-indiana",
        source_id="us-pa-indiana-recorder-publicsearch",
        name="Indiana County Register and Recorder PublicSearch",
        authority="Indiana County Register and Recorder",
        jurisdiction_name="Indiana County, Pennsylvania",
        county_geoid="42063",
        state_code="PA",
        department="RP",
        base_url="https://indiana.pa.publicsearch.us",
        official_linking_page=(
            "https://www.indianacountypa.gov/departments/"
            "register-and-recorder/"
        ),
        coverage="Indiana County, Pennsylvania recorded instruments",
        probe_instrument_number="1982-002331",
        probe_document_id=133236252,
        probe_page_count=4,
        probe_page_sha256=(
            "5623f1e338b5b4dc72f1bc7eda66711b"
            "6c9f78204108a6d5acf0cdc49962662b"
        ),
    ),
    recorder.RecorderTenant(
        key="pa-lawrence",
        source_id="us-pa-lawrence-recorder-publicsearch",
        name="Lawrence County Register and Recorder PublicSearch",
        authority="Lawrence County Register and Recorder",
        jurisdiction_name="Lawrence County, Pennsylvania",
        county_geoid="42073",
        state_code="PA",
        department="RP",
        base_url="https://lawrence.pa.publicsearch.us",
        official_linking_page=(
            "https://www.lawrencecountypa.gov/departments/"
            "register-recorder"
        ),
        coverage="Lawrence County, Pennsylvania recorded instruments",
        probe_instrument_number="2001-017168",
        probe_document_id=104759101,
        probe_page_count=7,
        probe_page_sha256=(
            "8aa3b02f76b4a43b1f2f0ea8c4032d5"
            "8c383035ceacb6d7f01a1cd5efe3b9917"
        ),
    ),
    recorder.RecorderTenant(
        key="de-kent",
        source_id="us-de-kent-recorder-publicsearch",
        name="Kent County Delaware GovOS Recorder Slice",
        authority="Kent County Recorder of Deeds",
        jurisdiction_name="Kent County, Delaware",
        county_geoid="10001",
        state_code="DE",
        department="RP",
        departments=("RP", "UCC"),
        base_url="https://kent.de.ds.search.govos.com",
        official_linking_page=(
            "https://www.kentcountyde.gov/My-Government/"
            "Departments/Deeds-Office"
        ),
        coverage=(
            "Working GovOS RP and UCC 2025 slice; the county-linked I2 "
            "service is the full-history complement"
        ),
        probe_instrument_number="506378",
        probe_document_id=36619563,
        probe_page_count=13,
        probe_page_sha256=(
            "67b8d1cf62cc3ff54e067aeea8e15b47"
            "f9b57d89175e05e4ae61297c2ae21e54"
        ),
    ),
    recorder.RecorderTenant(
        key="co-denver",
        source_id="us-co-denver-recorder-publicsearch",
        name="Denver Clerk and Recorder PublicSearch",
        authority="City and County of Denver Clerk and Recorder",
        jurisdiction_name="City and County of Denver, Colorado",
        county_geoid="08031",
        state_code="CO",
        department="RP",
        departments=("RP", "MAR", "MISC"),
        base_url="https://denver.co.publicsearch.us",
        official_linking_page=(
            "https://www.denvergov.org/Government/"
            "Agencies-Departments-Offices/Agencies-Departments-Offices-"
            "Directory/Denver-Clerk-and-Recorder/"
            "Learn-more-about-the-Denver-Clerk-and-Recorder"
        ),
        coverage=(
            "Denver recorded documents with separate real-property, "
            "marriage, and historic-index departments"
        ),
        probe_instrument_number="2026010037",
        probe_document_id=293353911,
        probe_page_count=1,
        probe_page_sha256=(
            "6d74f825d6b9196008d8fc13f3476581"
            "5b82aa7538b618cd1dfca64ca3829d4e"
        ),
    ),
    recorder.RecorderTenant(
        key="oh-franklin",
        source_id="us-oh-franklin-county-recorder-publicsearch",
        name="Franklin County Recorder PublicSearch",
        authority="Franklin County Recorder",
        jurisdiction_name="Franklin County, Ohio",
        county_geoid="39049",
        state_code="OH",
        department="RP",
        base_url="https://franklin.oh.publicsearch.us",
        official_linking_page=(
            "https://www.franklincountyohio.gov/Agency-Directory/"
            "Recorder/Real-Estate/Public-Records-Search"
        ),
        coverage="Franklin County, Ohio recorded instruments",
        probe_instrument_number="202607290091301",
        probe_document_id=323279115,
        probe_page_count=6,
        probe_page_sha256=(
            "2e7e562081d4fd72b0728d7996c2a098"
            "c45a8f9fdbdc8ae1cc05872727c7c228"
        ),
    ),
)

TENANTS_BY_SOURCE = {tenant.source_id: tenant for tenant in TENANTS}
SOURCE_IDS = tuple(TENANTS_BY_SOURCE)
DEPARTMENTS = tuple(
    sorted(
        {
            department
            for tenant in TENANTS
            for department in tenant.supported_departments
        }
    )
)


class TenantSelectionError(ValueError):
    """The selected department is not advertised for this tenant."""


def tenant_for_args(args: argparse.Namespace) -> recorder.RecorderTenant:
    tenant = TENANTS_BY_SOURCE[args.source]
    department = getattr(args, "department", None)
    if department is None or department == tenant.department:
        return tenant
    if department not in tenant.supported_departments:
        raise TenantSelectionError(
            f"{tenant.source_id} exposes departments "
            f"{', '.join(tenant.supported_departments)}, not {department}"
        )
    return replace(tenant, department=department)


def execute(
    args: argparse.Namespace,
    *,
    client: recorder.ReevesRecordsClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    base_tenant = TENANTS_BY_SOURCE[args.source]
    try:
        tenant = tenant_for_args(args)
    except TenantSelectionError as error:
        attempted_department = getattr(args, "department", None)
        attempted_tenant = (
            replace(base_tenant, department=attempted_department)
            if attempted_department
            else base_tenant
        )
        query = recorder.build_query(args, tenant=attempted_tenant)
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="department_not_supported",
                    message=str(error),
                    category="query_selection",
                    retryable=False,
                    details={
                        "selected_department": getattr(
                            args,
                            "department",
                            None,
                        ),
                        "supported_departments": list(
                            base_tenant.supported_departments
                        ),
                    },
                )
            ],
            warnings=recorder.SOURCE_WARNINGS,
        )
        recorder.log_search(
            recorder.canonical_json(query.to_dict()),
            base_tenant.source_id,
            None,
        )
        return result
    return recorder.execute(
        args,
        client=client,
        access_decision=access_decision,
        tenant=tenant,
    )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    tenant = TENANTS_BY_SOURCE[args.source]
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"{tenant.name} {args.command} ({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"{tenant.name} {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('instrument_number') or '?'} | "
            f"doc {record.get('doc_id') or '?'} | "
            f"{record.get('instrument_type_label') or record.get('instrument_type') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, choices=SOURCE_IDS)


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query verified GovOS/Kofile county-recorder tenants"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search indexed fields, OCR, or a recorded-date range",
    )
    _add_source(search)
    search.add_argument("query", nargs="?")
    search.add_argument("--department", choices=DEPARTMENTS)
    search.add_argument("--ocr", action="store_true")
    search.add_argument("--date-from")
    search.add_argument("--date-to")
    search.add_argument(
        "--limit",
        type=int,
        help=(
            "Return at most this many records and expose continuation; "
            "omit to follow all source pages"
        ),
    )
    search.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start at a caller-selected native offset",
    )
    search.add_argument(
        "--cursor",
        help="Resume a query-bound continuation returned by a prior search",
    )
    search.add_argument("--workspace-id")
    _add_runtime_and_output(search)

    document = sub.add_parser(
        "document",
        help="Fetch exact instrument detail by native document ID",
    )
    _add_source(document)
    document.add_argument("doc_id", type=int)
    document.add_argument("--department", choices=DEPARTMENTS)
    _add_runtime_and_output(document)

    page = sub.add_parser(
        "page",
        help="Fetch one caller-selected instrument page image",
    )
    _add_source(page)
    page.add_argument("doc_id", type=int)
    page.add_argument("page_number", type=int)
    page.add_argument("destination", nargs="?", type=Path)
    page.add_argument("--department", choices=DEPARTMENTS)
    page.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(page)

    probe = sub.add_parser(
        "probe",
        help="Verify tenant, exact record, detail, and page-image sentinel",
    )
    _add_source(probe)
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")
    if args.retry_backoff < 0:
        parser.error("--retry-backoff must not be negative")
    if (
        getattr(args, "limit", None) is not None
        and args.limit <= 0
    ):
        parser.error("--limit must be positive")
    if getattr(args, "offset", 0) < 0:
        parser.error("--offset must not be negative")
    if getattr(args, "cursor", None) and getattr(args, "offset", 0):
        parser.error("--cursor and a nonzero --offset cannot be combined")
    if getattr(args, "doc_id", 1) <= 0:
        parser.error("doc_id must be positive")
    if getattr(args, "page_number", 1) <= 0:
        parser.error("page_number must be positive")
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
