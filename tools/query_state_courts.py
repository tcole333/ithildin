#!/usr/bin/env python3
"""Unified state and local court-record query router.

Normalized sidecar data is queried locally by default. Selecting an external
source reports the latest catalogued access decision before any adapter is
considered. Public query results use each record's current access state;
restriction history remains in the sidecar audit tables.

Usage:
    uv run python tools/query_state_courts.py sources --json
    uv run python tools/query_state_courts.py search "ACME LLC"
    uv run python tools/query_state_courts.py case 156728/2019 \
      --source us-ny-nyscef --court-id ny-supreme
    uv run python tools/query_state_courts.py docket 2025CV000001 \
      --court-id wi-dane-circuit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        CatalogError,
        PublicRecordsCatalog,
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
    from tools.public_records_store import (
        DEFAULT_COURT_DB,
        canonical_court_ref,
        connect_courts,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        CatalogError,
        PublicRecordsCatalog,
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
    from public_records_store import (
        DEFAULT_COURT_DB,
        canonical_court_ref,
        connect_courts,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_SOURCE_ID = "local-state-court-records-sidecar"
CATALOG_SOURCE_ID = "local-public-records-catalog"
PUBLIC_STATE = "public"

LOCAL_SOURCE = SourceMetadata(
    source_id=LOCAL_SOURCE_ID,
    name="Normalized state and local court records sidecar",
    source_role="local_normalized_cache",
    metadata={
        "serves_current_access_state": PUBLIC_STATE,
        "coverage_semantics": "cache_with_explicit_query_evidence",
    },
)
CATALOG_SOURCE = SourceMetadata(
    source_id=CATALOG_SOURCE_ID,
    name="Public records source catalog",
    source_role="source_control_plane",
)


def _jurisdiction(value: str | None) -> JurisdictionMetadata:
    normalized = str(value or "").strip()
    return JurisdictionMetadata(
        jurisdiction_id=normalized or "local",
        name=(
            f"Court jurisdiction {normalized}"
            if normalized
            else "Local normalized state and local courts"
        ),
    )


def _query(
    source: SourceMetadata,
    operation: str,
    selector: str | None,
    args: argparse.Namespace,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction(getattr(args, "jurisdiction", None)),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "source": getattr(args, "source", None),
                "jurisdiction": getattr(args, "jurisdiction", None),
                "court_id": getattr(args, "court_id", None),
                "case_type": getattr(args, "case_type", None),
                "filed_after": getattr(args, "after", None),
                "filed_before": getattr(args, "before", None),
                "document_type": getattr(args, "document_type", None),
                "case_number": getattr(args, "case_number", None),
            },
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "sqlite:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("local cursor must have form sqlite:offset:N")
    return int(cursor[len(prefix) :])


def _next_cursor(
    offset: int, limit: int, rows: list[sqlite3.Row]
) -> tuple[list[sqlite3.Row], str | None]:
    if len(rows) <= limit:
        return rows, None
    return rows[:limit], f"sqlite:offset:{offset + limit}"


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _case_filters(
    args: argparse.Namespace,
    *,
    table_alias: str = "c",
) -> tuple[list[str], list[Any]]:
    conditions = [f"{table_alias}.access_state=?"]
    params: list[Any] = [PUBLIC_STATE]
    if args.court_id:
        conditions.append(f"{table_alias}.court_id=?")
        params.append(args.court_id)
    if args.jurisdiction:
        conditions.append(
            "EXISTS(SELECT 1 FROM court filter_court "
            f"WHERE filter_court.court_id={table_alias}.court_id "
            "AND (filter_court.state_code=? OR filter_court.county_geoid=?))"
        )
        params.extend([args.jurisdiction.upper(), args.jurisdiction])
    if getattr(args, "case_type", None):
        conditions.append(
            f"{table_alias}.case_type LIKE ? ESCAPE '\\' COLLATE NOCASE"
        )
        params.append(_like(args.case_type))
    if getattr(args, "after", None):
        conditions.append(f"{table_alias}.filing_date>=?")
        params.append(args.after)
    if getattr(args, "before", None):
        conditions.append(f"{table_alias}.filing_date<=?")
        params.append(args.before)
    return conditions, params


def _case_record(db, row: Mapping[str, Any], *, include_parties: bool = True) -> dict[str, Any]:
    row = dict(row)
    record = {
        "canonical_ref": canonical_court_ref(
            row["source_id"],
            row["court_id"],
            row["raw_case_number"],
        ),
        "case_id": row["case_id"],
        "source_id": row["source_id"],
        "court": {
            "court_id": row["court_id"],
            "native_court_id": row["native_court_id"],
            "name": row["court_name"],
            "state_code": row["state_code"],
            "county_geoid": row["county_geoid"],
            "level": row["court_level"],
            "division": row["division"],
            "official_url": row["court_official_url"],
        },
        "raw_case_number": row["raw_case_number"],
        "display_case_number": row["display_case_number"],
        "caption": row["caption"],
        "case_type": row["case_type"],
        "filing_date": row["filing_date"],
        "disposition_date": row["disposition_date"],
        "status": row["case_status"],
        "access_state": row["access_state"],
        "certified_record": bool(row["certified_record"]),
        "source_url": row["case_source_url"],
    }
    if include_parties:
        record["parties"] = [
            {
                "case_party_id": party["case_party_id"],
                "sequence": party["sequence_no"],
                "role": party["role"],
                "raw_name": party["raw_name"],
                "normalized_name": party["normalized_name"],
                "entity_kind": party["entity_kind"],
            }
            for party in db.execute(
                """
                SELECT * FROM case_party
                WHERE case_id=? AND access_state='public'
                ORDER BY sequence_no, case_party_id
                """,
                (row["case_id"],),
            )
        ]
    return record


CASE_SELECT = """
SELECT c.case_id, c.source_id, c.court_id, c.raw_case_number,
       c.display_case_number, c.caption, c.case_type, c.filing_date,
       c.disposition_date, c.status AS case_status, c.access_state,
       c.certified_record, c.source_url AS case_source_url,
       ct.native_court_id, ct.name AS court_name, ct.state_code,
       ct.county_geoid, ct.court_level, ct.division,
       ct.official_url AS court_official_url
FROM case_record c
JOIN court ct ON ct.court_id=c.court_id
"""


def _local_search(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _case_filters(args)
    pattern = _like(selector)
    conditions.append(
        "(c.raw_case_number LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR c.display_case_number LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR c.caption LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR EXISTS(SELECT 1 FROM case_party cp "
        "WHERE cp.case_id=c.case_id AND cp.access_state='public' "
        "AND (cp.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR cp.normalized_name LIKE ? ESCAPE '\\' COLLATE NOCASE)) "
        "OR EXISTS(SELECT 1 FROM case_representation cr "
        "JOIN case_party cp2 ON cp2.case_party_id=cr.case_party_id "
        "JOIN attorney a ON a.attorney_id=cr.attorney_id "
        "WHERE cr.case_id=c.case_id AND cp2.access_state='public' "
        "AND (a.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR a.normalized_name LIKE ? ESCAPE '\\' COLLATE NOCASE)))"
    )
    params.extend([pattern] * 7)
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        {CASE_SELECT}
        WHERE {' AND '.join(conditions)}
        ORDER BY c.filing_date DESC, c.case_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    return [_case_record(db, row) for row in rows], cursor


def _local_case(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _case_filters(args)
    conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
    params.extend([selector, selector, args.limit + 1, offset])
    rows = db.execute(
        f"""
        {CASE_SELECT}
        WHERE {' AND '.join(conditions)}
        ORDER BY c.filing_date DESC, c.case_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    return [_case_record(db, row) for row in rows], cursor


def _matching_public_cases(
    db, selector: str, args: argparse.Namespace, *, limit: int | None = None
) -> list[sqlite3.Row]:
    conditions, params = _case_filters(args)
    conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
    params.extend([selector, selector, limit or args.limit])
    return db.execute(
        f"""
        {CASE_SELECT}
        WHERE {' AND '.join(conditions)}
        ORDER BY c.filing_date DESC, c.case_id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def _local_docket(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    records: list[dict[str, Any]] = []
    cases = _matching_public_cases(db, selector, args)
    for case in cases:
        remaining = args.limit + 1 - len(records)
        if remaining <= 0:
            break
        rows = db.execute(
            """
            SELECT * FROM docket_entry
            WHERE case_id=? AND access_state='public'
            ORDER BY
                CASE WHEN sequence_no GLOB '[0-9]*'
                     THEN CAST(sequence_no AS INTEGER) END,
                sequence_no, subsequence_no, docket_entry_id
            LIMIT ? OFFSET ?
            """,
            (case["case_id"], remaining, offset if len(cases) == 1 else 0),
        ).fetchall()
        for row in rows:
            records.append(
                {
                    "canonical_ref": canonical_court_ref(
                        case["source_id"],
                        case["court_id"],
                        case["raw_case_number"],
                        "docket",
                        row["native_entry_id"],
                    ),
                    "case": _case_record(db, case, include_parties=False),
                    "docket_entry_id": row["docket_entry_id"],
                    "native_entry_id": row["native_entry_id"],
                    "sequence": row["sequence_no"],
                    "subsequence": row["subsequence_no"],
                    "event_code": row["event_code"],
                    "text": row["raw_text"],
                    "filed_date": row["filed_date"],
                    "entered_date": row["entered_date"],
                    "event_date": row["event_date"],
                    "filer_raw": row["filer_raw"],
                    "document_available": (
                        None
                        if row["document_available"] is None
                        else bool(row["document_available"])
                    ),
                    "access_state": row["access_state"],
                }
            )
    next_cursor = None
    if len(records) > args.limit:
        records = records[: args.limit]
        next_cursor = f"sqlite:offset:{offset + args.limit}"
    return records, next_cursor


def _local_documents(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    records: list[dict[str, Any]] = []
    cases = _matching_public_cases(db, selector, args)
    for case in cases:
        conditions = ["d.case_id=?", "d.access_state='public'"]
        params: list[Any] = [case["case_id"]]
        if args.document_type:
            conditions.append("d.document_type LIKE ? ESCAPE '\\' COLLATE NOCASE")
            params.append(_like(args.document_type))
        params.extend([args.limit + 1 - len(records), offset if len(cases) == 1 else 0])
        rows = db.execute(
            f"""
            SELECT d.*, de.native_entry_id, de.sequence_no, de.raw_text
            FROM document_artifact d
            LEFT JOIN docket_entry de
              ON de.docket_entry_id=d.docket_entry_id
             AND de.access_state='public'
            WHERE {' AND '.join(conditions)}
              AND (d.docket_entry_id IS NULL OR de.docket_entry_id IS NOT NULL)
            ORDER BY d.filed_date, d.document_id
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        for row in rows:
            records.append(
                {
                    "canonical_ref": canonical_court_ref(
                        case["source_id"],
                        case["court_id"],
                        case["raw_case_number"],
                        "document",
                        row["native_document_id"],
                    ),
                    "case": _case_record(db, case, include_parties=False),
                    "document_id": row["document_id"],
                    "native_document_id": row["native_document_id"],
                    "document_type": row["document_type"],
                    "filed_date": row["filed_date"],
                    "source_url": row["source_url"],
                    "sha256": row["sha256"],
                    "mime_type": row["mime_type"],
                    "page_count": row["page_count"],
                    "ocr_status": row["ocr_status"],
                    "certification_status": row["certification_status"],
                    "access_state": row["access_state"],
                    "docket_entry": (
                        {
                            "native_entry_id": row["native_entry_id"],
                            "sequence": row["sequence_no"],
                            "text": row["raw_text"],
                        }
                        if row["native_entry_id"]
                        else None
                    ),
                }
            )
    next_cursor = None
    if len(records) > args.limit:
        records = records[: args.limit]
        next_cursor = f"sqlite:offset:{offset + args.limit}"
    return records, next_cursor


LOCAL_HANDLERS: dict[
    str,
    Callable[[sqlite3.Connection, str, argparse.Namespace], tuple[list[dict[str, Any]], str | None]],
] = {
    "search": _local_search,
    "case": _local_case,
    "docket": _local_docket,
    "documents": _local_documents,
}

LOCAL_COVERAGE_TABLES = (
    "source_snapshot",
    "court",
    "case_record",
    "case_party",
    "attorney",
    "docket_entry",
    "document_artifact",
)

_COURT_OPERATION_ALIASES = {
    "search": {"search", "case_search", "party_search"},
    "case": {"case", "case_lookup"},
    "docket": {"docket", "docket_entries"},
    "documents": {"documents", "document", "document_search"},
    "download": {"download", "document"},
}
_COURT_SELECTOR_KEYS = (
    "selector",
    "query",
    "case_number",
    "document_id",
    "native_document_id",
    "party_name",
)


def _local_coverage_counts(db: sqlite3.Connection) -> dict[str, int]:
    """Return the rows that establish local data or query provenance."""
    return {
        table: int(
            db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        )
        for table in LOCAL_COVERAGE_TABLES
    }


def _json_mapping(raw: Any) -> Mapping[str, Any] | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


def _normalized_selector(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _filter_matches(
    parameters: Mapping[str, Any],
    *,
    requested: Any,
    keys: tuple[str, ...],
) -> bool:
    evidence = next(
        (
            parameters.get(key)
            for key in keys
            if parameters.get(key) not in (None, "")
        ),
        None,
    )
    if requested in (None, ""):
        return evidence in (None, "")
    return str(evidence or "").casefold() == str(requested).casefold()


def _court_query_evidence(
    snapshot: Mapping[str, Any],
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any] | None:
    snapshot = dict(snapshot)
    raw = _json_mapping(snapshot.get("raw_json"))
    coverage = _json_mapping(snapshot.get("coverage_json"))
    if raw is None or coverage is None:
        return None
    query = raw.get("query")
    if not isinstance(query, Mapping):
        return None
    source = query.get("source")
    jurisdiction = query.get("jurisdiction")
    metadata = query.get("query")
    if not all(isinstance(value, Mapping) for value in (source, jurisdiction, metadata)):
        return None
    if source.get("source_id") != snapshot.get("source_id"):
        return None
    if query.get("fingerprint") != snapshot.get("query_fingerprint"):
        return None

    operation = str(metadata.get("operation") or "").strip().casefold()
    if operation not in _COURT_OPERATION_ALIASES.get(args.command, {args.command}):
        return None
    parameters = metadata.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    selectors = {
        _normalized_selector(parameters.get(key))
        for key in _COURT_SELECTOR_KEYS
        if parameters.get(key) not in (None, "")
    }
    if _normalized_selector(selector) not in selectors:
        return None

    evidence_jurisdiction = str(
        jurisdiction.get("jurisdiction_id") or ""
    ).strip()
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    requested_court = str(args.court_id or "").strip()
    if requested_court:
        if str(parameters.get("court_id") or "").strip() != requested_court:
            return None
    elif requested_jurisdiction:
        jurisdiction_values = {
            evidence_jurisdiction,
            str(jurisdiction.get("state_code") or "").strip(),
            str(jurisdiction.get("county_fips") or "").strip(),
            str(parameters.get("jurisdiction") or "").strip(),
        }
        if requested_jurisdiction not in jurisdiction_values:
            return None
    else:
        return None

    if not _filter_matches(
        parameters,
        requested=args.case_type,
        keys=("case_type",),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=args.after,
        keys=("filed_after", "after", "start_date"),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=args.before,
        keys=("filed_before", "before", "end_date"),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=getattr(args, "document_type", None),
        keys=("document_type",),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=getattr(args, "case_number", None),
        keys=("case_number",),
    ):
        return None

    complete_zero = (
        snapshot.get("access_status") == ResultStatus.NO_RESULTS.value
        and raw.get("status") == ResultStatus.NO_RESULTS.value
        and raw.get("records") == []
        and raw.get("next_cursor") is None
        and coverage.get("record_count") == 0
        and coverage.get("next_cursor") is None
        and metadata.get("cursor") is None
        and bool(snapshot.get("retrieved_at"))
    )
    return {
        "source_id": snapshot["source_id"],
        "status": snapshot["access_status"],
        "retrieved_at": snapshot["retrieved_at"],
        "query_fingerprint": snapshot["query_fingerprint"],
        "jurisdiction": evidence_jurisdiction,
        "court_id": parameters.get("court_id"),
        "operation": operation,
        "filed_after": args.after,
        "filed_before": args.before,
        "complete_zero": complete_zero,
    }


def _court_route_guidance(args: argparse.Namespace) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "discover": (
            "uv run python tools/query_state_courts.py sources "
            "[--jurisdiction STATE_OR_GEOID] --output FILE"
        ),
        "select_source": "--source SOURCE_ID",
        "plan_action": (
            "uv run python tools/public_records_actions.py plan SOURCE_ID "
            "--operation OPERATION --selector SELECTOR --output FILE"
        ),
        "catalog_sources": [],
    }
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        for source in catalog.list_sources(
            domain="court",
            jurisdiction=args.jurisdiction,
        ):
            source_id = source["source_id"]
            decision = catalog.machine_acquisition_decision(source_id)
            guidance["catalog_sources"].append(
                {
                    "source_id": source_id,
                    "official_url": source.get("official_url"),
                    "acquisition_status": acquisition_result_status(decision),
                }
            )
    except (CatalogError, sqlite3.Error, ValueError) as error:
        guidance["catalog_error"] = str(error)
    return guidance


def _court_local_coverage(
    db: sqlite3.Connection,
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any]:
    row_counts = _local_coverage_counts(db)
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    requested_court = str(args.court_id or "").strip()
    if requested_court:
        scope_clause = "ct.court_id=?"
        scope_params: tuple[Any, ...] = (requested_court,)
    elif requested_jurisdiction:
        scope_clause = "(ct.state_code=? OR ct.county_geoid=?)"
        scope_params = (
            requested_jurisdiction.upper(),
            requested_jurisdiction,
        )
    else:
        scope_clause = "1=1"
        scope_params = ()

    requested_counts = {
        "courts": int(
            db.execute(
                f"SELECT COUNT(*) FROM court ct WHERE {scope_clause}",
                scope_params,
            ).fetchone()[0]
        ),
        "cases": int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM case_record c
                JOIN court ct ON ct.court_id=c.court_id
                WHERE {scope_clause}
                """,
                scope_params,
            ).fetchone()[0]
        ),
        "public_cases": int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM case_record c
                JOIN court ct ON ct.court_id=c.court_id
                WHERE {scope_clause} AND c.access_state='public'
                """,
                scope_params,
            ).fetchone()[0]
        ),
    }
    source_ids = {
        str(row[0])
        for row in db.execute(
            f"""
            SELECT DISTINCT c.source_id FROM case_record c
            JOIN court ct ON ct.court_id=c.court_id
            WHERE {scope_clause}
            """,
            scope_params,
        )
    }

    matching_evidence: list[dict[str, Any]] = []
    observed_requested_scope = False
    snapshots = db.execute(
        """
        SELECT snapshot_id, source_id, query_fingerprint, retrieved_at,
               access_status, coverage_json, raw_json
        FROM source_snapshot
        ORDER BY retrieved_at DESC, snapshot_id DESC
        """
    ).fetchall()
    for snapshot in snapshots:
        raw = _json_mapping(snapshot["raw_json"])
        if raw is not None:
            query = raw.get("query")
            jurisdiction = (
                query.get("jurisdiction") if isinstance(query, Mapping) else None
            )
            metadata = query.get("query") if isinstance(query, Mapping) else None
            parameters = (
                metadata.get("parameters")
                if isinstance(metadata, Mapping)
                else None
            )
            if isinstance(jurisdiction, Mapping):
                values = {
                    str(jurisdiction.get("jurisdiction_id") or "").strip(),
                    str(jurisdiction.get("state_code") or "").strip(),
                    str(jurisdiction.get("county_fips") or "").strip(),
                }
                if requested_jurisdiction and requested_jurisdiction in values:
                    observed_requested_scope = True
                    source_ids.add(str(snapshot["source_id"]))
            if (
                requested_court
                and isinstance(parameters, Mapping)
                and str(parameters.get("court_id") or "").strip()
                == requested_court
            ):
                observed_requested_scope = True
                source_ids.add(str(snapshot["source_id"]))
        evidence = _court_query_evidence(snapshot, args, selector)
        if evidence is not None:
            matching_evidence.append(evidence)

    latest_by_source: dict[str, dict[str, Any]] = {}
    for evidence in matching_evidence:
        latest_by_source.setdefault(evidence["source_id"], evidence)
    latest = list(latest_by_source.values())
    authoritative_zero = bool(latest) and all(
        evidence["complete_zero"] for evidence in latest
    )
    scope_requested = bool(requested_jurisdiction or requested_court)
    scope_covered = (
        any(row_counts.values())
        if not scope_requested
        else observed_requested_scope or any(requested_counts.values())
    )
    return {
        "authoritative_zero": authoritative_zero,
        "requested_scope": {
            "operation": args.command,
            "selector": selector,
            "jurisdiction": requested_jurisdiction or None,
            "court_id": requested_court or None,
            "case_type": args.case_type,
            "filed_after": args.after,
            "filed_before": args.before,
            "document_type": getattr(args, "document_type", None),
            "case_number": getattr(args, "case_number", None),
        },
        "sidecar": {
            "row_counts": row_counts,
            "requested_scope_counts": requested_counts,
            "requested_scope_observed": observed_requested_scope,
            "scope_covered": scope_covered,
            "source_ids": sorted(source_ids),
        },
        "matching_query_evidence": latest,
    }


def _restriction_metadata(
    db: sqlite3.Connection,
    case_id: int,
    fallback_state: str,
) -> dict[str, Any]:
    row = db.execute(
        """
        SELECT source_id, event_type, effective_at
        FROM restriction_event
        WHERE case_id=?
        ORDER BY effective_at DESC, restriction_event_id DESC
        LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        return {
            "current_access_state": fallback_state,
            "restriction_event": None,
        }
    return {
        "current_access_state": fallback_state,
        "restriction_event": {
            "source_id": row["source_id"],
            "event_type": row["event_type"],
            "effective_at": row["effective_at"],
        },
    }


def _restricted_case_tombstones(
    db: sqlite3.Connection,
    selector: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    if args.command not in {"case", "docket", "documents"}:
        return [], None
    offset = _cursor_offset(args.cursor)
    conditions = [
        "c.access_state<>'public'",
        "(c.raw_case_number=? OR c.display_case_number=?)",
    ]
    params: list[Any] = [selector, selector]
    if args.court_id:
        conditions.append("c.court_id=?")
        params.append(args.court_id)
    if args.jurisdiction:
        conditions.append("(ct.state_code=? OR ct.county_geoid=?)")
        params.extend([args.jurisdiction.upper(), args.jurisdiction])
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT c.case_id, c.source_id, c.court_id, c.raw_case_number,
               c.access_state, ct.name AS court_name, ct.state_code,
               ct.county_geoid
        FROM case_record c
        JOIN court ct ON ct.court_id=c.court_id
        WHERE {' AND '.join(conditions)}
        ORDER BY c.case_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    return [
        {
            "canonical_ref": canonical_court_ref(
                row["source_id"],
                row["court_id"],
                row["raw_case_number"],
            ),
            "record_kind": "case_restriction_tombstone",
            "source_id": row["source_id"],
            "court": {
                "court_id": row["court_id"],
                "name": row["court_name"],
                "state_code": row["state_code"],
                "county_geoid": row["county_geoid"],
            },
            "raw_case_number": row["raw_case_number"],
            "access_state": row["access_state"],
            "restriction": _restriction_metadata(
                db,
                row["case_id"],
                row["access_state"],
            ),
        }
        for row in rows
    ], cursor


def _restricted_document_tombstones(
    db: sqlite3.Connection,
    selector: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    if args.command != "download":
        return [], None
    offset = _cursor_offset(args.cursor)
    conditions = [
        "d.native_document_id=?",
        (
            "(d.access_state<>'public' OR c.access_state<>'public' "
            "OR (d.docket_entry_id IS NOT NULL AND "
            "COALESCE(de.access_state, 'unknown')<>'public'))"
        ),
    ]
    params: list[Any] = [selector]
    if args.case_number:
        conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
        params.extend([args.case_number, args.case_number])
    if args.court_id:
        conditions.append("c.court_id=?")
        params.append(args.court_id)
    if args.jurisdiction:
        conditions.append("(ct.state_code=? OR ct.county_geoid=?)")
        params.extend([args.jurisdiction.upper(), args.jurisdiction])
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT d.document_id, d.source_id, d.native_document_id,
               d.access_state AS document_access_state,
               c.case_id, c.raw_case_number,
               c.access_state AS case_access_state,
               de.access_state AS docket_access_state
        FROM document_artifact d
        JOIN case_record c ON c.case_id=d.case_id
        JOIN court ct ON ct.court_id=c.court_id
        LEFT JOIN docket_entry de ON de.docket_entry_id=d.docket_entry_id
        WHERE {' AND '.join(conditions)}
        ORDER BY d.document_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        access_states = [
            state
            for state in (
                row["document_access_state"],
                row["case_access_state"],
                row["docket_access_state"],
            )
            if state and state != PUBLIC_STATE
        ]
        current_state = access_states[0] if access_states else "restricted"
        record = {
            "record_kind": "document_restriction_tombstone",
            "source_id": row["source_id"],
            "native_document_id": row["native_document_id"],
            "access_state": current_state,
            "restriction": _restriction_metadata(
                db,
                row["case_id"],
                current_state,
            ),
        }
        if args.case_number:
            record["case_number"] = row["raw_case_number"]
        records.append(record)
    return records, cursor


def _restricted_result(
    db: sqlite3.Connection,
    query: PublicRecordsQuery,
    selector: str,
    args: argparse.Namespace,
) -> PublicRecordsResult | None:
    if args.command == "download":
        records, cursor = _restricted_document_tombstones(
            db,
            selector,
            args,
        )
    else:
        records, cursor = _restricted_case_tombstones(
            db,
            selector,
            args,
        )
    if not records:
        return None
    return PublicRecordsResult.failure(
        query,
        ResultStatus.RESTRICTED,
        [
            PublicRecordsError(
                code="known_record_restricted",
                message=(
                    "the exact identifier is known locally, but its current "
                    "access state does not permit serving record contents"
                ),
                category="record_access",
                retryable=False,
                details={
                    "record_kind": records[0]["record_kind"],
                    "match_count": len(records),
                    "route_guidance": _court_route_guidance(args),
                },
            )
        ],
        records=records,
        next_cursor=cursor,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download_local(
    db, selector: str, args: argparse.Namespace, query: PublicRecordsQuery
) -> PublicRecordsResult:
    conditions, params = _case_filters(args)
    conditions.extend(
        [
            "d.access_state='public'",
            "d.native_document_id=?",
            (
                "(d.docket_entry_id IS NULL OR EXISTS("
                "SELECT 1 FROM docket_entry public_de "
                "WHERE public_de.docket_entry_id=d.docket_entry_id "
                "AND public_de.access_state='public'))"
            ),
        ]
    )
    params.append(selector)
    if args.case_number:
        conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
        params.extend([args.case_number, args.case_number])
    rows = db.execute(
        f"""
        SELECT d.*, c.raw_case_number, c.source_id AS case_source_id,
               c.court_id
        FROM document_artifact d
        JOIN case_record c ON c.case_id=d.case_id
        WHERE {' AND '.join(conditions)}
        ORDER BY d.document_id DESC
        LIMIT 2
        """,
        params,
    ).fetchall()
    if not rows:
        return PublicRecordsResult.success(query, [])
    if len(rows) > 1 and not args.case_number:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.HUMAN_REQUIRED,
            [
                PublicRecordsError(
                    code="ambiguous_document_id",
                    message=(
                        "document identifier matches multiple public cases; "
                        "provide --case-number"
                    ),
                    category="query_resolution",
                    retryable=False,
                    details={"match_count_at_least": 2},
                )
            ],
        )

    row = rows[0]
    storage_path = row["storage_path"]
    if not storage_path:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_not_stored",
                    message="public document metadata exists but no local artifact is stored",
                    category="local_store",
                    retryable=False,
                )
            ],
        )
    source_path = Path(storage_path)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path
    if not source_path.is_file():
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_missing",
                    message=f"stored artifact path does not exist: {storage_path}",
                    category="local_store",
                    retryable=False,
                )
            ],
        )
    actual_sha256 = _sha256_file(source_path)
    if row["sha256"] and actual_sha256.lower() != str(row["sha256"]).lower():
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="artifact_hash_mismatch",
                    message="stored artifact does not match its recorded SHA-256",
                    category="integrity",
                    retryable=False,
                    details={
                        "expected_sha256": row["sha256"],
                        "actual_sha256": actual_sha256,
                    },
                )
            ],
        )

    destination = None
    if args.destination:
        destination_path = Path(args.destination).expanduser()
        if destination_path.exists() and not args.overwrite:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.HUMAN_REQUIRED,
                [
                    PublicRecordsError(
                        code="destination_exists",
                        message="destination exists; pass --overwrite to replace it",
                        category="filesystem",
                        retryable=False,
                    )
                ],
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        destination = str(destination_path.resolve())

    record = {
        "canonical_ref": canonical_court_ref(
            row["case_source_id"],
            row["court_id"],
            row["raw_case_number"],
            "document",
            row["native_document_id"],
        ),
        "native_document_id": row["native_document_id"],
        "case_number": row["raw_case_number"],
        "court_id": row["court_id"],
        "sha256": actual_sha256,
        "mime_type": row["mime_type"],
        "bytes": source_path.stat().st_size,
        "download_status": "copied" if destination else "verified_local_artifact",
        "destination": destination,
    }
    return PublicRecordsResult.success(query, [record])


def _court_cache_miss_result(
    query: PublicRecordsQuery,
    coverage: Mapping[str, Any],
    args: argparse.Namespace,
) -> PublicRecordsResult:
    sidecar = coverage["sidecar"]
    scope_covered = bool(sidecar["scope_covered"])
    any_local_data = any(sidecar["row_counts"].values())
    if scope_covered:
        status = ResultStatus.PARTIAL
        code = "local_cache_miss"
    else:
        status = ResultStatus.UNAVAILABLE
        code = (
            "local_scope_not_covered"
            if any_local_data
            else "no_coverage"
        )
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=(
                    "no matching public record is cached, and no exact "
                    "source-query zero establishes an empty result"
                ),
                category="local_coverage",
                retryable=False,
                details={
                    "court_db": str(args.court_db),
                    "coverage": coverage,
                    "route_guidance": _court_route_guidance(args),
                },
            )
        ],
    )


def _local_result(args: argparse.Namespace) -> PublicRecordsResult:
    selector = " ".join(args.query.split()).strip()
    query = _query(LOCAL_SOURCE, args.command, selector, args)
    try:
        db = connect_courts(args.court_db)
        try:
            coverage = _court_local_coverage(db, args, selector)
            if args.command == "download":
                result = _download_local(db, selector, args, query)
                if result.status == ResultStatus.NO_RESULTS:
                    result = (
                        _restricted_result(db, query, selector, args)
                        or (
                            PublicRecordsResult.success(
                                query,
                                [],
                                warnings=[
                                    "Exact source-query zero preserved from "
                                    + ", ".join(
                                        f"{item['source_id']} at "
                                        f"{item['retrieved_at']}"
                                        for item in coverage[
                                            "matching_query_evidence"
                                        ]
                                    )
                                ],
                            )
                            if coverage["authoritative_zero"]
                            else _court_cache_miss_result(
                                query,
                                coverage,
                                args,
                            )
                        )
                    )
            else:
                records, cursor = LOCAL_HANDLERS[args.command](
                    db, selector, args
                )
                if records:
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=cursor,
                    )
                else:
                    result = (
                        _restricted_result(db, query, selector, args)
                        or (
                            PublicRecordsResult.success(
                                query,
                                [],
                                warnings=[
                                    "Exact source-query zero preserved from "
                                    + ", ".join(
                                        f"{item['source_id']} at "
                                        f"{item['retrieved_at']}"
                                        for item in coverage[
                                            "matching_query_evidence"
                                        ]
                                    )
                                ],
                            )
                            if coverage["authoritative_zero"]
                            else _court_cache_miss_result(
                                query,
                                coverage,
                                args,
                            )
                        )
                    )
        finally:
            db.close()
    except (OSError, sqlite3.Error, TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="local_sidecar_query_failed",
                    message=str(error),
                    category="local_store",
                    retryable=False,
                )
            ],
        )
    count = (
        len(result.records)
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}
        else None
    )
    log_search(canonical_json(query.to_dict()), LOCAL_SOURCE_ID, count)
    return result


def _catalog_source(detail: Mapping[str, Any]) -> SourceMetadata:
    source = detail["source"]
    roles = detail.get("roles") or ["court"]
    return SourceMetadata(
        source_id=source["source_id"],
        name=source["name"],
        source_role=",".join(roles),
        base_url=source.get("official_url"),
        metadata={
            "authority": source.get("authority"),
            "platform_family": source.get("platform_family"),
        },
    )


def _external_failure(
    args: argparse.Namespace,
    *,
    detail: Mapping[str, Any] | None,
    decision: Mapping[str, Any] | None,
    code: str,
    message: str,
    status: ResultStatus,
    details: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    source = (
        _catalog_source(detail)
        if detail is not None
        else SourceMetadata(
            source_id=args.source,
            name=args.source,
            source_role="unresolved_court_source",
        )
    )
    query = _query(source, args.command, args.query, args)
    error_details = {"access_decision": decision or {}}
    if details:
        error_details.update(details)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="source_access",
                retryable=False,
                details=error_details,
            )
        ],
    )


def _external_requested_action(
    args: argparse.Namespace,
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe the cataloged source operation represented by this route.

    A unified ``case`` lookup does not imply that the source has a direct case
    endpoint. Some portals expose case-number lookup through a case-search
    capability, so the action names that source operation while retaining the
    router operation for auditability.
    """
    supported_capabilities = {
        str(capability.get("name"))
        for capability in detail.get("capabilities", ())
        if capability.get("supported")
    }
    source_operation = args.command
    if args.command == "case" and "search_cases" in supported_capabilities:
        source_operation = "search"

    action = {
        "operation": source_operation,
        "selector": args.query,
        "court_id": args.court_id,
    }
    if source_operation != args.command:
        action["router_operation"] = args.command
    return action


def _external_result(args: argparse.Namespace) -> PublicRecordsResult:
    catalog = PublicRecordsCatalog(args.catalog_db)
    try:
        detail = catalog.show_source(args.source)
    except CatalogError as error:
        return _external_failure(
            args,
            detail=None,
            decision=None,
            code="source_not_registered",
            message=str(error),
            status=ResultStatus.UNAVAILABLE,
        )
    decision = catalog.machine_acquisition_decision(args.source)
    if not decision["allowed"]:
        status = ResultStatus(acquisition_result_status(decision))
        extra: dict[str, Any] = {
            "review": detail.get("latest_access_review"),
            "source_url": detail["source"]["official_url"],
            "terms_url": detail["source"].get("license_or_terms_url"),
            "requested_action": _external_requested_action(args, detail),
        }
        code = str(decision["reason_code"])
        if status is ResultStatus.HUMAN_REQUIRED:
            extra["manual_source_url"] = detail["source"]["official_url"]
        return _external_failure(
            args,
            detail=detail,
            decision=decision,
            code=code,
            message=decision["reason"],
            status=status,
            details=extra,
        )
    return _external_failure(
        args,
        detail=detail,
        decision=decision,
        code="adapter_not_implemented",
        message=(
            f"{args.source} has machine access in the catalog but no unified "
            "state-court router adapter"
        ),
        status=ResultStatus.UNAVAILABLE,
    )


def _sources_result(args: argparse.Namespace) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=CATALOG_SOURCE,
        jurisdiction=_jurisdiction(args.jurisdiction),
        query=QueryMetadata(
            operation="sources",
            parameters={"domain": "court", "jurisdiction": args.jurisdiction},
        ),
    )
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        rows = catalog.list_sources(domain="court", jurisdiction=args.jurisdiction)
        records = []
        for row in rows:
            decision = catalog.machine_acquisition_decision(row["source_id"])
            records.append({**row, "machine_acquisition": decision})
        return PublicRecordsResult.success(query, records)
    except (CatalogError, sqlite3.Error, ValueError) as error:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="catalog_query_failed",
                    message=str(error),
                    category="source_catalog",
                    retryable=False,
                )
            ],
        )


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "sources":
        return _sources_result(args).to_dict()
    result = (
        _local_result(args)
        if args.source == "local"
        else _external_result(args)
    )
    if args.source != "local":
        log_search(
            canonical_json(result.query.to_dict()),
            args.source,
            None,
        )
    return result.to_dict()


def _emit(payload: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        payload,
        args,
        summary=f"state courts {args.command} ({payload.get('status', 'unknown')})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    records = payload.get("records", [])
    print(
        f"State courts {args.command}: {payload.get('status')} "
        f"({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        label = (
            record.get("raw_case_number")
            or record.get("native_entry_id")
            or record.get("native_document_id")
            or record.get("source_id")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        default="local",
        help="Canonical source ID, or local (default)",
    )
    parser.add_argument("--jurisdiction", help="State code or county GEOID filter")
    parser.add_argument("--court-id", help="Canonical local court identifier")
    parser.add_argument("--case-type")
    parser.add_argument("--after", help="Filed on/after ISO date")
    parser.add_argument("--before", help="Filed on/before ISO date")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor")
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    parser.add_argument("--court-db", default=str(DEFAULT_COURT_DB))
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query normalized and catalogued state/local court records"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources", help="List catalogued court sources")
    sources.add_argument("--jurisdiction", help="State code or county GEOID")
    sources.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    add_output_args(sources)

    search = sub.add_parser("search", help="Search cases, parties, and attorneys")
    search.add_argument("query")
    _add_common(search)

    case = sub.add_parser("case", help="Look up a source-native case number")
    case.add_argument("query", metavar="CASE_NUMBER")
    _add_common(case)

    docket = sub.add_parser("docket", help="List public docket entries for a case")
    docket.add_argument("query", metavar="CASE_NUMBER")
    _add_common(docket)

    documents = sub.add_parser(
        "documents", help="List public document metadata for a case"
    )
    documents.add_argument("query", metavar="CASE_NUMBER")
    documents.add_argument("--document-type")
    _add_common(documents)

    download = sub.add_parser(
        "download", help="Verify or copy a public document from local storage"
    )
    download.add_argument("query", metavar="NATIVE_DOCUMENT_ID")
    download.add_argument("--case-number")
    download.add_argument("--destination")
    download.add_argument("--overwrite", action="store_true")
    _add_common(download)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    payload = execute(args)
    _emit(payload, args)


if __name__ == "__main__":
    main()
