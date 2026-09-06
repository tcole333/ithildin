#!/usr/bin/env python3
"""NYC ACRIS property-record adapter with shared source and result contracts.

The adapter queries the official NYC Open Data Socrata resources for ACRIS
    master, party, and legal records. Party and BBL searches return document-level
    records enriched from all three datasets. Source capabilities and endpoint
    paging metadata come from the central catalog, and each outcome has an explicit
    status.

Usage:
    uv run python tools/query_acris.py party "Jeffrey Epstein"
    uv run python tools/query_acris.py party "LSJE LLC" --exact
    uv run python tools/query_acris.py address --borough 1 --block 1390 --lot 29
    uv run python tools/query_acris.py document "2019012345678"
    uv run python tools/query_acris.py history --borough 1 --block 1390 --lot 29
    uv run python tools/query_acris.py batch-entities
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
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


SOURCE_ID = "us-nyc-acris"
BASE_URL = "https://data.cityofnewyork.us/resource"
MASTER_ID = "bnx9-e6tj"
PARTIES_ID = "636b-3b5g"
LEGALS_ID = "8h5j-fqxa"
MASTER_BATCH_SIZE = 20

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="NYC ACRIS",
    source_role="recorder_instrument_index",
    base_url=BASE_URL,
    dataset_id=",".join((MASTER_ID, PARTIES_ID, LEGALS_ID)),
    metadata={
        "authority": "New York City Department of Finance",
        "coverage_note": (
            "ACRIS covers Manhattan, Bronx, Brooklyn, and Queens; Richmond "
            "County records are maintained separately."
        ),
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
    },
)

SOURCE_WARNINGS = (
    "ACRIS party roles and indexed legal descriptions are recorder observations, not proof of beneficial ownership.",
    "ACRIS does not provide Richmond County (Staten Island) land records.",
)

BOROUGH_METADATA = {
    "1": ("36061", "New York County (Manhattan)"),
    "2": ("36005", "Bronx County"),
    "3": ("36047", "Kings County (Brooklyn)"),
    "4": ("36081", "Queens County"),
    "5": ("36085", "Richmond County (outside ACRIS coverage)"),
}

KNOWN_PROPERTIES = {
    "9 E 71st St": {"borough": "1", "block": "1386", "lot": "10"},
    "11 E 71st St": {"borough": "1", "block": "1386", "lot": "12"},
    "457 Madison Ave": {"borough": "1", "block": "1312", "lot": "52"},
    "301 E 66th St": {"borough": "1", "block": "1419", "lot": "31"},
}

DOC_TYPE_MAP = {
    "DEED": "Deed",
    "DEEDO": "Deed, Other",
    "MTGE": "Mortgage",
    "M&CON": "Mortgage & Consolidation",
    "AGMT": "Agreement",
    "ASST": "Assignment",
    "SAT": "Satisfaction",
    "RPTT": "Real Property Transfer Tax",
    "UCC1": "UCC1 Financing Statement",
    "UCC3": "UCC3 Amendment",
    "AL&R": "Assignment of Leases & Rents",
    "ALIS": "Lis Pendens",
    "MCON": "Mortgage Consolidation",
    "CORRM": "Corrective Mortgage",
    "SUBM": "Subordination of Mortgage",
}


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


def _jurisdiction(borough: str | None) -> JurisdictionMetadata:
    geoid, name = BOROUGH_METADATA.get(
        str(borough or ""),
        ("nyc-acris", "New York City ACRIS coverage"),
    )
    return JurisdictionMetadata(
        jurisdiction_id=geoid,
        name=name,
        state_code="NY",
        county_fips=geoid if geoid.isdigit() else None,
        locality="New York City",
    )


def build_query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    borough: str | None,
    requested_limit: int | None,
    cursor: str | None,
) -> PublicRecordsQuery:
    """Build the deterministic public-record query used for logging and output."""
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=_jurisdiction(borough),
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters),
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _require_access(args: argparse.Namespace) -> dict[str, Any]:
    """Bootstrap a missing source entry, then read its latest access review."""
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


class _ACRISSource:
    """Shared Socrata acquisition context for all ACRIS datasets."""

    def __init__(self, args: argparse.Namespace, decision: Mapping[str, Any]) -> None:
        limits = decision.get("limits", {})
        requested_interval = float(getattr(args, "minimum_interval", 0.25))
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
        self.token = (
            os.environ.get("NYC_SODA_APP_TOKEN")
            or os.environ.get("NY_SODA_APP_TOKEN")
        )
        self._clients: dict[str, SocrataSODAClient] = {}
        self._last_query_finished: float | None = None

    def _client(self, dataset_id: str) -> SocrataSODAClient:
        if dataset_id not in self._clients:
            self._clients[dataset_id] = SocrataSODAClient(
                BASE_URL,
                dataset_id,
                app_token=self.token,
                page_size=self.page_size,
                max_records=self.max_records,
                timeout=self.timeout,
                minimum_interval=self.minimum_interval,
            )
        return self._clients[dataset_id]

    def query(
        self,
        dataset_id: str,
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
            return self._client(dataset_id).query(
                parameters,
                requested_limit=requested_limit,
                max_records=self.max_records,
                cursor=cursor,
            )
        finally:
            self._last_query_finished = time.monotonic()


def _cursor_parts(cursor: str | None, expected_kind: str) -> tuple[str, str | None]:
    if not cursor:
        return expected_kind, None
    prefix = "acris:"
    if not cursor.startswith(prefix):
        return expected_kind, cursor
    remainder = cursor[len(prefix) :]
    kind, separator, source_cursor = remainder.partition(":")
    if not separator or kind != expected_kind or not source_cursor:
        raise ValueError(f"invalid ACRIS {expected_kind} continuation cursor")
    return kind, source_cursor


def _wrap_cursor(kind: str, cursor: str | None) -> str | None:
    return f"acris:{kind}:{cursor}" if cursor else None


def _batch_values(values: Sequence[str], size: int = MASTER_BATCH_SIZE):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _fetch_document_rows(
    source: _ACRISSource,
    dataset_id: str,
    document_ids: Sequence[str],
    *,
    order: str,
) -> tuple[list[Mapping[str, Any]], list[str]]:
    rows: list[Mapping[str, Any]] = []
    warnings: list[str] = []
    for batch in _batch_values(list(document_ids)):
        id_list = ",".join(f"'{_sql_literal(document_id)}'" for document_id in batch)
        fetched = source.query(
            dataset_id,
            {
                "$where": f"document_id IN ({id_list})",
                "$order": order,
            },
            requested_limit=source.max_records,
        )
        rows.extend(fetched.records)
        warnings.extend(fetched.warnings)
        if fetched.truncated_by_cap:
            warnings.append(
                f"Enrichment from dataset {dataset_id} reached the configured record ceiling."
            )
    return rows, warnings


def _group_by_document(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        document_id = str(row.get("document_id") or "").strip()
        if document_id:
            grouped.setdefault(document_id, []).append(dict(row))
    return grouped


def _minimal_document_records(
    matched_rows: Sequence[Mapping[str, Any]],
    match_key: str,
) -> list[dict[str, Any]]:
    grouped = _group_by_document(matched_rows)
    return [
        {
            "source_id": SOURCE_ID,
            "document_id": document_id,
            match_key: rows,
            "master": None,
            "parties": [],
            "legals": [],
            "enrichment_complete": False,
        }
        for document_id, rows in grouped.items()
    ]


def _enrich_documents(
    source: _ACRISSource,
    matched_rows: Sequence[Mapping[str, Any]],
    *,
    match_key: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    matched_by_document = _group_by_document(matched_rows)
    document_ids = list(matched_by_document)
    if matched_rows and not document_ids:
        raise ValueError(
            "ACRIS match rows no longer contain the required document_id field"
        )
    if not document_ids:
        return [], []

    masters, master_warnings = _fetch_document_rows(
        source,
        MASTER_ID,
        document_ids,
        order="document_id",
    )
    parties, party_warnings = _fetch_document_rows(
        source,
        PARTIES_ID,
        document_ids,
        order="document_id, party_type, name",
    )
    legals, legal_warnings = _fetch_document_rows(
        source,
        LEGALS_ID,
        document_ids,
        order="document_id, borough, block, lot",
    )
    master_by_document = {
        str(row.get("document_id")): dict(row)
        for row in masters
        if row.get("document_id")
    }
    parties_by_document = _group_by_document(parties)
    legals_by_document = _group_by_document(legals)

    records = []
    missing_master = 0
    for document_id in document_ids:
        master = master_by_document.get(document_id)
        if master is None:
            missing_master += 1
        records.append(
            {
                "source_id": SOURCE_ID,
                "document_id": document_id,
                "crfn": master.get("crfn") if master else None,
                "document_type": master.get("doc_type") if master else None,
                "document_type_description": (
                    DOC_TYPE_MAP.get(master.get("doc_type"), master.get("doc_type"))
                    if master
                    else None
                ),
                match_key: matched_by_document[document_id],
                "master": master,
                "parties": parties_by_document.get(document_id, []),
                "legals": legals_by_document.get(document_id, []),
                "enrichment_complete": master is not None,
            }
        )
    warnings = [*master_warnings, *party_warnings, *legal_warnings]
    if missing_master:
        warnings.append(
            f"{missing_master} indexed document(s) lacked a matching ACRIS master row."
        )
    return records, warnings


def _finalize(
    query: PublicRecordsQuery,
    records: Sequence[Mapping[str, Any]],
    *,
    next_cursor: str | None = None,
    warnings: Sequence[str] = (),
    errors: Sequence[PublicRecordsError] = (),
    primary_truncated: bool = False,
) -> PublicRecordsResult:
    all_warnings = tuple(dict.fromkeys((*SOURCE_WARNINGS, *warnings)))
    if errors:
        status = ResultStatus.PARTIAL if records else ResultStatus.UNAVAILABLE
        return PublicRecordsResult.failure(
            query,
            status,
            errors,
            records=records,
            next_cursor=next_cursor,
            warnings=all_warnings,
        )
    if primary_truncated:
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


def _execute_party(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    source: _ACRISSource,
) -> PublicRecordsResult:
    name = _sql_literal(args.query).upper()
    cursor_kind = "exact"
    source_cursor = None
    if args.cursor:
        if args.cursor.startswith("acris:like:"):
            cursor_kind, source_cursor = _cursor_parts(args.cursor, "like")
        else:
            cursor_kind, source_cursor = _cursor_parts(args.cursor, "exact")

    where = (
        f"upper(name) = '{name}'"
        if cursor_kind == "exact"
        else f"upper(name) LIKE '%{name}%'"
    )
    fetched = source.query(
        PARTIES_ID,
        {"$where": where, "$order": "document_id, party_type, name"},
        requested_limit=args.limit,
        cursor=source_cursor,
    )
    if (
        not fetched.records
        and not args.cursor
        and not args.exact
        and cursor_kind == "exact"
    ):
        cursor_kind = "like"
        fetched = source.query(
            PARTIES_ID,
            {
                "$where": f"upper(name) LIKE '%{name}%'",
                "$order": "document_id, party_type, name",
            },
            requested_limit=args.limit,
        )

    next_cursor = _wrap_cursor(cursor_kind, fetched.next_cursor)
    minimal_records = _minimal_document_records(fetched.records, "matched_parties")
    try:
        records, enrichment_warnings = _enrich_documents(
            source,
            fetched.records,
            match_key="matched_parties",
        )
    except PublicRecordsHTTPError as error:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL if minimal_records else error.result_status,
            [error.to_contract_error()],
            records=minimal_records,
            next_cursor=next_cursor,
            warnings=(*SOURCE_WARNINGS, *fetched.warnings),
        )
    return _finalize(
        query,
        records,
        next_cursor=next_cursor,
        warnings=(*fetched.warnings, *enrichment_warnings),
        primary_truncated=fetched.truncated_by_cap,
    )


def _bbl_from_args(args: argparse.Namespace) -> tuple[str, str, str]:
    borough = getattr(args, "borough", None)
    block = getattr(args, "block", None)
    lot = getattr(args, "lot", None)
    property_name = getattr(args, "property_name", None)
    if property_name:
        for name, bbl in KNOWN_PROPERTIES.items():
            if property_name.lower() in name.lower():
                return bbl["borough"], bbl["block"], bbl["lot"]
        raise ValueError(
            f"unknown property name; known values: {', '.join(KNOWN_PROPERTIES)}"
        )
    if not (borough and block and lot):
        raise ValueError(
            "must specify --borough, --block, --lot or --property-name"
        )
    return str(borough), str(block), str(lot)


def _execute_bbl(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    source: _ACRISSource,
) -> PublicRecordsResult:
    borough, block, lot = _bbl_from_args(args)
    _, source_cursor = _cursor_parts(args.cursor, "legal")
    fetched = source.query(
        LEGALS_ID,
        {
            "$where": (
                f"borough='{_sql_literal(borough)}' AND "
                f"block='{_sql_literal(block)}' AND lot='{_sql_literal(lot)}'"
            ),
            "$order": "document_id, borough, block, lot",
        },
        requested_limit=args.limit,
        cursor=source_cursor,
    )
    next_cursor = _wrap_cursor("legal", fetched.next_cursor)
    minimal_records = _minimal_document_records(fetched.records, "matched_legals")
    try:
        records, enrichment_warnings = _enrich_documents(
            source,
            fetched.records,
            match_key="matched_legals",
        )
    except PublicRecordsHTTPError as error:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL if minimal_records else error.result_status,
            [error.to_contract_error()],
            records=minimal_records,
            next_cursor=next_cursor,
            warnings=(*SOURCE_WARNINGS, *fetched.warnings),
        )
    if args.command == "history":
        records.sort(
            key=lambda record: (
                (record.get("master") or {}).get("document_date") or "",
                record["document_id"],
            )
        )
    return _finalize(
        query,
        records,
        next_cursor=next_cursor,
        warnings=(*fetched.warnings, *enrichment_warnings),
        primary_truncated=fetched.truncated_by_cap,
    )


def _execute_document(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    source: _ACRISSource,
) -> PublicRecordsResult:
    document_id = _sql_literal(args.document_id)
    matched = [{"document_id": document_id}]
    records, warnings = _enrich_documents(
        source,
        matched,
        match_key="matched_documents",
    )
    if records and not (
        records[0]["master"] or records[0]["parties"] or records[0]["legals"]
    ):
        records = []
    return _finalize(query, records, warnings=warnings)


def _execute_batch_entities(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    source: _ACRISSource,
) -> PublicRecordsResult:
    db_path = Path(getattr(args, "investigation_db", Path(__file__).parent.parent / "investigation.db"))
    if not db_path.exists():
        raise ValueError(f"investigation database not found: {db_path}")
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        entities = db.execute(
            "SELECT id, name FROM entities WHERE length(name) >= 4 ORDER BY name"
        ).fetchall()

    records: list[dict[str, Any]] = []
    errors: list[PublicRecordsError] = []
    warnings: list[str] = []
    for entity in entities:
        safe_name = _sql_literal(entity["name"]).upper()
        try:
            fetched = source.query(
                PARTIES_ID,
                {
                    "$where": f"upper(name) = '{safe_name}'",
                    "$order": "document_id, party_type, name",
                },
                requested_limit=args.per_entity_limit,
            )
            matched = list(fetched.records)
            if not matched and not args.exact:
                fetched = source.query(
                    PARTIES_ID,
                    {
                        "$where": f"upper(name) LIKE '%{safe_name}%'",
                        "$order": "document_id, party_type, name",
                    },
                    requested_limit=args.per_entity_limit,
                )
                matched = list(fetched.records)
            if not matched:
                continue
            enriched, enrichment_warnings = _enrich_documents(
                source,
                matched,
                match_key="matched_parties",
            )
            records.append(
                {
                    "entity_id": entity["id"],
                    "entity_name": entity["name"],
                    "documents": enriched,
                }
            )
            warnings.extend((*fetched.warnings, *enrichment_warnings))
        except PublicRecordsHTTPError as error:
            errors.append(error.to_contract_error())

    return _finalize(
        query,
        records,
        warnings=warnings,
        errors=errors,
    )


def execute(
    args: argparse.Namespace,
    *,
    source: _ACRISSource | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    """Execute one remote ACRIS command and return a canonical result envelope."""
    operation = args.command
    try:
        if operation in {"address", "history"}:
            borough, block, lot = _bbl_from_args(args)
            parameters = {
                "borough": borough,
                "block": block,
                "lot": lot,
                "property_name": getattr(args, "property_name", None),
            }
            requested_limit = args.limit
        elif operation == "party":
            borough = None
            parameters = {"name": args.query, "exact_only": args.exact}
            requested_limit = args.limit
        elif operation == "document":
            borough = None
            parameters = {"document_id": args.document_id}
            requested_limit = 1
        elif operation == "batch-entities":
            borough = None
            parameters = {
                "investigation_db": str(args.investigation_db),
                "per_entity_limit": args.per_entity_limit,
                "exact_only": args.exact,
            }
            requested_limit = args.per_entity_limit
        else:
            raise ValueError(f"unsupported remote command: {operation}")
        query = build_query(
            operation,
            parameters,
            borough=borough,
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
        )
    except ValueError as error:
        query = build_query(
            operation,
            {"invalid_request": True},
            borough=getattr(args, "borough", None),
            requested_limit=getattr(args, "limit", 1),
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
        if operation in {"address", "history"} and borough == "5":
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.UNAVAILABLE,
                [
                    PublicRecordsError(
                        code="outside_source_coverage",
                        message=(
                            "Richmond County land records are outside ACRIS "
                            "coverage."
                        ),
                        category="coverage",
                        retryable=False,
                    )
                ],
                warnings=SOURCE_WARNINGS,
            )
            count = None
            log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
            return result
        acquisition = source or _ACRISSource(args, decision)
        try:
            if operation == "party":
                result = _execute_party(args, query, acquisition)
            elif operation in {"address", "history"}:
                result = _execute_bbl(args, query, acquisition)
            elif operation == "document":
                result = _execute_document(args, query, acquisition)
            else:
                result = _execute_batch_entities(args, query, acquisition)
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


def _format_amount(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return ""
    return "" if amount == 0 else f"${amount:,.0f}"


def _format_date(value: Any) -> str:
    return str(value or "")[:10]


def _print_transaction(record: Mapping[str, Any]) -> None:
    master = record.get("master") or {}
    document_id = record.get("document_id", "?")
    doc_type = master.get("doc_type") or record.get("document_type") or "?"
    amount = _format_amount(master.get("document_amt"))
    print(f"  [{doc_type}] {DOC_TYPE_MAP.get(doc_type, doc_type)}")
    print(f"    Document: {document_id} | CRFN: {master.get('crfn', 'N/A')}")
    if amount:
        print(f"    Amount: {amount}")
    if master.get("document_date"):
        print(
            f"    Date: {_format_date(master.get('document_date'))} "
            f"(recorded: {_format_date(master.get('recorded_datetime'))})"
        )
    grantors = [
        party.get("name", "?")
        for party in record.get("parties", ())
        if party.get("party_type") == "1"
    ]
    grantees = [
        party.get("name", "?")
        for party in record.get("parties", ())
        if party.get("party_type") == "2"
    ]
    if grantors:
        print(f"    From (grantor): {', '.join(grantors)}")
    if grantees:
        print(f"    To (grantee): {', '.join(grantees)}")
    for legal in record.get("legals", ())[:3]:
        if legal.get("borough") and legal.get("block") and legal.get("lot"):
            print(
                "    Property: Borough "
                f"{legal['borough']}, Block {legal['block']}, Lot {legal['lot']}"
            )
    print()


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"ACRIS {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(f"ACRIS {args.command}: {result.status.value} ({len(result.records)} records)")
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    if args.command == "batch-entities":
        for match in result.records:
            print(f"  {match['entity_name']}: {len(match['documents'])} documents")
    else:
        for record in result.records[: getattr(args, "max_docs", len(result.records))]:
            _print_transaction(record)
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def cmd_party(args: argparse.Namespace) -> None:
    _emit(execute(args), args)


def cmd_address(args: argparse.Namespace) -> None:
    _emit(execute(args), args)


def cmd_document(args: argparse.Namespace) -> None:
    _emit(execute(args), args)


def cmd_history(args: argparse.Namespace) -> None:
    _emit(execute(args), args)


def cmd_batch_entities(args: argparse.Namespace) -> None:
    _emit(execute(args), args)


def cmd_known(args: argparse.Namespace) -> None:
    data = [{"name": name, **bbl} for name, bbl in KNOWN_PROPERTIES.items()]
    if write_output(data, args, summary="ACRIS known properties"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print("Known ACRIS property shortcuts:")
    for row in data:
        print(
            f"  {row['name']}: Borough {row['borough']}, "
            f"Block {row['block']}, Lot {row['lot']}"
        )


def _add_remote_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_cursor: bool = True,
) -> None:
    if include_cursor:
        parser.add_argument("--cursor", help="Continuation cursor from a prior result")
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling for one dataset query",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.25,
        help="Client pacing in seconds (a documented catalog minimum, if any, also applies)",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--catalog-db", default=str(DEFAULT_DB_PATH))
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official NYC ACRIS records via Socrata"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    party = sub.add_parser("party", help="Search by grantor/grantee party name")
    party.add_argument("query")
    party.add_argument("--limit", type=int, default=100)
    party.add_argument("--max-docs", type=int, default=20)
    party.add_argument("--exact", action="store_true")
    _add_remote_arguments(party)

    address = sub.add_parser("address", help="Search by borough/block/lot")
    address.add_argument("--borough")
    address.add_argument("--block")
    address.add_argument("--lot")
    address.add_argument("--property-name")
    address.add_argument("--limit", type=int, default=50)
    address.add_argument("--max-docs", type=int, default=20)
    _add_remote_arguments(address)

    document = sub.add_parser("document", help="Fetch one ACRIS document")
    document.add_argument("document_id")
    document.add_argument("--max-docs", type=int, default=1)
    _add_remote_arguments(document, include_cursor=False)

    history = sub.add_parser("history", help="Get enriched BBL transaction history")
    history.add_argument("--borough")
    history.add_argument("--block")
    history.add_argument("--lot")
    history.add_argument("--property-name")
    history.add_argument("--limit", type=int, default=50)
    history.add_argument("--max-docs", type=int, default=50)
    _add_remote_arguments(history)

    batch = sub.add_parser(
        "batch-entities",
        help="Cross-reference investigation entities against ACRIS",
    )
    batch.add_argument(
        "--investigation-db",
        default=str(Path(__file__).resolve().parent.parent / "investigation.db"),
    )
    batch.add_argument("--per-entity-limit", type=int, default=5)
    batch.add_argument("--exact", action="store_true")
    batch.add_argument("--max-docs", type=int, default=20)
    _add_remote_arguments(batch, include_cursor=False)

    known = sub.add_parser("known", help="List local ACRIS property shortcuts")
    add_output_args(known)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for name in ("limit", "page_size", "max_records", "per_entity_limit"):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"{name.replace('_', '-')} must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("minimum-interval must not be negative")
    commands = {
        "party": cmd_party,
        "address": cmd_address,
        "document": cmd_document,
        "history": cmd_history,
        "batch-entities": cmd_batch_entities,
        "known": cmd_known,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
