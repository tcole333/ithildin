#!/usr/bin/env python3
"""Unified property-record query router.

The router serves normalized local sidecar data by default and selects live
adapters through ``--source``. Source capabilities, access state, and reviewed
limits come from the central catalog.

Usage:
    uv run python tools/query_property.py sources --json
    uv run python tools/query_property.py owner "SMITH" --jurisdiction 37005
    uv run python tools/query_property.py parcel 3013467134 \
      --source us-nc-onemap-parcels --county-fips 005 --ingest
    uv run python tools/query_property.py address "7 TRAYMORE RD" \
      --source us-md-sdat-property-hidden --county-code 04
    uv run python tools/query_property.py parcel 1-1386-10 \
      --source us-nyc-acris
    uv run python tools/query_property.py chain 3013467134 --jurisdiction 37005
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping

try:
    from tools import (
        query_acris,
        query_cook_property,
        query_la_property,
        query_md_property,
        query_nc_property,
    )
    from tools.ingest_property_records import ingest_property_envelope
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
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
except ImportError:
    import query_acris
    import query_cook_property
    import query_la_property
    import query_md_property
    import query_nc_property
    from ingest_property_records import ingest_property_envelope
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
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )


LOCAL_SOURCE_ID = "local-property-records-sidecar"
CATALOG_SOURCE_ID = "local-public-records-catalog"
NC_SOURCE_ID = query_nc_property.SOURCE_ID
COOK_SOURCE_ID = query_cook_property.SOURCE_ID
MD_SOURCE_ID = query_md_property.SOURCE_ID
EBR_SOURCE_ID = query_la_property.SOURCE_ID
ACRIS_SOURCE_ID = query_acris.SOURCE_ID
FL_SOURCE_ID = "us-fl-dor-property-roll"
MASSGIS_SOURCE_ID = "us-ma-massgis-parcels"
HARRIS_SOURCE_ID = "us-tx-harris-hcad-property"
ACRIS_IMAGES_SOURCE_ID = "us-nyc-acris-images"

LOCAL_SOURCE = SourceMetadata(
    source_id=LOCAL_SOURCE_ID,
    name="Normalized property records sidecar",
    source_role="local_normalized_cache",
    metadata={
        "coverage_semantics": "cache_with_explicit_query_evidence",
        "assessor_ownership_caveat": (
            "Assessment-roll owners are source observations, not proof of title "
            "or beneficial ownership."
        ),
    },
)
CATALOG_SOURCE = SourceMetadata(
    source_id=CATALOG_SOURCE_ID,
    name="Public records source catalog",
    source_role="source_control_plane",
)


@dataclass(frozen=True)
class _LiveRoute:
    adapter: Any
    adapter_command: str
    translate: Callable[[argparse.Namespace, str], argparse.Namespace]


def _remote_common(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "limit": args.limit,
        "cursor": args.cursor,
        "page_size": args.page_size,
        "max_records": args.max_records,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "catalog_db": args.catalog_db,
        "output": None,
        "json_out": False,
    }


def _nc_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    county_fips = args.county_fips
    if (
        county_fips is None
        and args.jurisdiction
        and re.fullmatch(r"37\d{3}", args.jurisdiction)
    ):
        county_fips = args.jurisdiction
    return argparse.Namespace(
        **_remote_common(args),
        command=adapter_command,
        query=args.query,
        county_fips=county_fips,
        geometry=args.geometry or args.command == "map",
    )


def _cook_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    common = _remote_common(args)
    common.pop("max_records")
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        tax_year=args.tax_year,
    )


def _md_county_code(args: argparse.Namespace) -> str | None:
    if args.county_fips:
        return args.county_fips
    jurisdiction = str(args.jurisdiction or "").strip()
    if not jurisdiction or jurisdiction == "24":
        return None
    for code, (geoid, _name) in query_md_property.COUNTY_GEOIDS.items():
        if jurisdiction == geoid:
            return code
    return jurisdiction


def _md_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    common = _remote_common(args)
    common.pop("max_records")
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        county_code=_md_county_code(args),
    )


def _ebr_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    values = {
        **_remote_common(args),
        "command": adapter_command,
        "parish": query_la_property.DEFAULT_PARISH,
        "max_results": args.limit,
    }
    if adapter_command == "parcel":
        values["assessment_no"] = args.query
    else:
        values["query"] = args.query
    return argparse.Namespace(**values)


def _normalized_digits(value: str) -> str:
    return str(int(value)) if value and int(value) else "0"


def _acris_bbl(
    args: argparse.Namespace,
) -> tuple[str | None, str | None, str | None, str | None]:
    selector = " ".join(args.query.split()).strip()
    for name in query_acris.KNOWN_PROPERTIES:
        if selector.casefold() in name.casefold():
            return None, None, None, selector

    parts = re.findall(r"\d+", selector)
    if len(parts) == 1 and len(parts[0]) == 10:
        digits = parts[0]
        return (
            digits[0],
            _normalized_digits(digits[1:6]),
            _normalized_digits(digits[6:]),
            None,
        )
    if len(parts) == 3:
        return (
            _normalized_digits(parts[0]),
            _normalized_digits(parts[1]),
            _normalized_digits(parts[2]),
            None,
        )
    if len(parts) == 2:
        borough_by_geoid = {
            geoid: borough
            for borough, (geoid, _name) in query_acris.BOROUGH_METADATA.items()
        }
        borough = borough_by_geoid.get(str(args.jurisdiction or ""))
        if borough:
            return (
                borough,
                _normalized_digits(parts[0]),
                _normalized_digits(parts[1]),
                None,
            )
    return None, None, None, None


def _acris_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    values = {
        **_remote_common(args),
        "command": adapter_command,
        "max_docs": 1 if adapter_command == "document" else args.limit,
    }
    if adapter_command == "party":
        values.update(query=args.query, exact=False)
    elif adapter_command == "document":
        values["document_id"] = args.query
    else:
        borough, block, lot, property_name = _acris_bbl(args)
        values.update(
            borough=borough,
            block=block,
            lot=lot,
            property_name=property_name,
        )
    return argparse.Namespace(**values)


LIVE_ROUTES: dict[str, dict[str, _LiveRoute]] = {
    NC_SOURCE_ID: {
        "owner": _LiveRoute(query_nc_property, "owner", _nc_args),
        "address": _LiveRoute(query_nc_property, "address", _nc_args),
        "parcel": _LiveRoute(query_nc_property, "parcel", _nc_args),
        "map": _LiveRoute(query_nc_property, "parcel", _nc_args),
    },
    COOK_SOURCE_ID: {
        "parcel": _LiveRoute(query_cook_property, "parcel", _cook_args),
    },
    MD_SOURCE_ID: {
        "address": _LiveRoute(query_md_property, "address", _md_args),
        "parcel": _LiveRoute(query_md_property, "parcel", _md_args),
    },
    EBR_SOURCE_ID: {
        "owner": _LiveRoute(query_la_property, "owner", _ebr_args),
        "address": _LiveRoute(query_la_property, "address", _ebr_args),
        "parcel": _LiveRoute(query_la_property, "parcel", _ebr_args),
    },
    ACRIS_SOURCE_ID: {
        "owner": _LiveRoute(query_acris, "party", _acris_args),
        "parcel": _LiveRoute(query_acris, "address", _acris_args),
        "instrument": _LiveRoute(query_acris, "document", _acris_args),
        "chain": _LiveRoute(query_acris, "history", _acris_args),
    },
}

DIRECT_TOOL_GUIDANCE: dict[str, dict[str, Any]] = {
    NC_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_nc_property.py --help",
    },
    COOK_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_cook_property.py --help",
    },
    MD_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_md_property.py --help",
    },
    EBR_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_la_property.py --help",
    },
    ACRIS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_acris.py --help",
    },
    FL_SOURCE_ID: {
        "mode": "bulk_manifest",
        "direct_tool": "uv run python tools/query_fl_dor_property.py --help",
        "note": "Use the bulk adapter for release manifests and downloads.",
    },
    MASSGIS_SOURCE_ID: {
        "mode": "bulk_manifest",
        "direct_tool": "uv run python tools/query_massgis_property.py --help",
        "note": "Use the bulk adapter for municipal manifests and downloads.",
    },
    HARRIS_SOURCE_ID: {
        "mode": "bulk_manifest",
        "direct_tool": "uv run python tools/query_harris_property.py --help",
        "note": "Use the bulk adapter for HCAD release manifests and downloads.",
    },
    ACRIS_IMAGES_SOURCE_ID: {
        "mode": "action_planning",
        "direct_tool": (
            "uv run python tools/public_records_actions.py plan "
            "us-nyc-acris-images --operation open_selected_image "
            "--selector DOCUMENT_ID"
        ),
        "note": (
            "Image viewing and copy-service work is represented through "
            "catalog-backed actions."
        ),
    },
}


def _source_guidance(source_id: str) -> dict[str, Any]:
    guidance = dict(
        DIRECT_TOOL_GUIDANCE.get(
            source_id,
            {
                "mode": "catalog_only",
            },
        )
    )
    guidance["unified_operations"] = sorted(LIVE_ROUTES.get(source_id, {}))
    return guidance


def _jurisdiction(value: str | None) -> JurisdictionMetadata:
    value = str(value or "").strip()
    state_code = None
    county_fips = None
    name = "Local normalized property records"
    if value:
        name = f"Property jurisdiction {value}"
        if value.startswith("37"):
            state_code = "NC"
            county_fips = value if len(value) == 5 else None
    return JurisdictionMetadata(
        jurisdiction_id=value or "local",
        name=name,
        state_code=state_code,
        county_fips=county_fips,
    )


def _query(
    source: SourceMetadata,
    operation: str,
    selector: str | None,
    args: argparse.Namespace,
) -> PublicRecordsQuery:
    parameters = {
        "selector": selector,
        "source": getattr(args, "source", None),
        "jurisdiction": getattr(args, "jurisdiction", None),
        "tax_year": getattr(args, "tax_year", None),
    }
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction(getattr(args, "jurisdiction", None)),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
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


def _next_cursor(offset: int, limit: int, rows: list[sqlite3.Row]) -> tuple[list[sqlite3.Row], str | None]:
    if len(rows) <= limit:
        return rows, None
    return rows[:limit], f"sqlite:offset:{offset + limit}"


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _json_value(raw: Any) -> Any:
    if raw in (None, ""):
        return None
    try:
        return json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return raw


def _parcel_record(row: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(row)
    source_id = str(row["source_id"])
    geoid = str(row["jurisdiction_geoid"])
    native_id = str(row["native_parcel_id"])
    return {
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", native_id
        ),
        "parcel_id": row["parcel_id"],
        "source_id": source_id,
        "jurisdiction_geoid": geoid,
        "jurisdiction_name": row.get("jurisdiction_name"),
        "native_parcel_id": native_id,
        "roll_year": row.get("roll_year") or None,
        "effective_from": row.get("effective_from"),
        "effective_to": row.get("effective_to"),
        "source_good_through": row.get("source_good_through"),
    }


def _local_owner(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions = [
        "(oa.raw_owner_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR oa.normalized_owner_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
    ]
    params: list[Any] = [_like(selector), _like(selector)]
    if args.jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    if args.tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(args.tax_year))
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name,
               oa.ownership_assertion_id, oa.assertion_type,
               oa.raw_owner_name, oa.normalized_owner_name,
               oa.effective_from AS owner_effective_from,
               oa.effective_to AS owner_effective_to,
               oa.confidence, oa.claim_type, oa.evidence_ref, oa.source_quote
        FROM ownership_assertion oa
        JOIN parcel_snapshot p USING(parcel_id)
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {' AND '.join(conditions)}
        ORDER BY oa.raw_owner_name, p.jurisdiction_geoid,
                 p.native_parcel_id, oa.effective_from DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        record = _parcel_record(row)
        record["matched_owner"] = {
            "ownership_assertion_id": row["ownership_assertion_id"],
            "raw_name": row["raw_owner_name"],
            "normalized_name": row["normalized_owner_name"],
            "assertion_type": row["assertion_type"],
            "effective_from": row["owner_effective_from"] or None,
            "effective_to": row["owner_effective_to"],
            "confidence": row["confidence"],
            "claim_type": row["claim_type"],
            "evidence_ref": row["evidence_ref"],
            "source_quote": row["source_quote"],
        }
        records.append(record)
    return records, cursor


def _local_address(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions = [
        "(pa.raw_address LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR pa.normalized_address LIKE ? ESCAPE '\\' COLLATE NOCASE)"
    ]
    params: list[Any] = [_like(selector), _like(selector)]
    if args.jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    if args.tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(args.tax_year))
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name,
               pa.address_id, pa.address_role, pa.raw_address,
               pa.normalized_address, pa.city, pa.state, pa.postal_code,
               pa.effective_from AS address_effective_from,
               pa.effective_to AS address_effective_to
        FROM parcel_address pa
        JOIN parcel_snapshot p USING(parcel_id)
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {' AND '.join(conditions)}
        ORDER BY pa.raw_address, p.jurisdiction_geoid, p.native_parcel_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        record = _parcel_record(row)
        record["matched_address"] = {
            "address_id": row["address_id"],
            "role": row["address_role"],
            "raw": row["raw_address"],
            "normalized": row["normalized_address"],
            "city": row["city"],
            "state": row["state"],
            "postal_code": row["postal_code"],
            "effective_from": row["address_effective_from"] or None,
            "effective_to": row["address_effective_to"],
        }
        records.append(record)
    return records, cursor


def _local_parcel(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions = [
        "(p.native_parcel_id=? OR EXISTS("
        "SELECT 1 FROM parcel_alias pa "
        "WHERE pa.parcel_id=p.parcel_id AND pa.alias_value=?))"
    ]
    params: list[Any] = [selector, selector]
    if args.jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    if args.tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(args.tax_year))
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name
        FROM parcel_snapshot p
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {' AND '.join(conditions)}
        ORDER BY p.jurisdiction_geoid, p.native_parcel_id, p.roll_year DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        record = _parcel_record(row)
        record["aliases"] = [
            {
                "type": alias["alias_type"],
                "value": alias["alias_value"],
                "source_id": alias["source_id"],
                "effective_from": alias["effective_from"] or None,
                "effective_to": alias["effective_to"],
            }
            for alias in db.execute(
                """
                SELECT * FROM parcel_alias
                WHERE parcel_id=? ORDER BY alias_type, alias_value
                """,
                (row["parcel_id"],),
            )
        ]
        record["addresses"] = [
            {
                "role": address["address_role"],
                "raw": address["raw_address"],
                "normalized": address["normalized_address"],
                "city": address["city"],
                "state": address["state"],
                "postal_code": address["postal_code"],
            }
            for address in db.execute(
                """
                SELECT * FROM parcel_address
                WHERE parcel_id=? ORDER BY address_role, address_id
                """,
                (row["parcel_id"],),
            )
        ]
        records.append(record)
    return records, cursor


def _local_instrument(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    pattern = _like(selector)
    conditions = [
        "(ri.native_document_id=? "
        "OR ri.legal_description_raw LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR EXISTS(SELECT 1 FROM instrument_party ip "
        "WHERE ip.instrument_id=ri.instrument_id "
        "AND (ip.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR ip.normalized_name LIKE ? ESCAPE '\\' COLLATE NOCASE)))"
    ]
    params: list[Any] = [selector, pattern, pattern, pattern]
    if args.jurisdiction:
        conditions.append("ri.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT ri.*, j.name AS jurisdiction_name
        FROM recorded_instrument ri
        JOIN jurisdiction j ON j.geoid=ri.jurisdiction_geoid
        WHERE {' AND '.join(conditions)}
        ORDER BY ri.recording_date DESC, ri.native_document_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        parties = [
            {
                "sequence": party["sequence_no"],
                "role": party["role"],
                "raw_name": party["raw_name"],
                "normalized_name": party["normalized_name"],
                "raw_address": party["raw_address"],
            }
            for party in db.execute(
                """
                SELECT * FROM instrument_party
                WHERE instrument_id=? ORDER BY sequence_no, instrument_party_id
                """,
                (row["instrument_id"],),
            )
        ]
        parcels = [
            {
                **_parcel_record(parcel),
                "link_method": parcel["link_method"],
                "link_confidence": parcel["link_confidence"],
            }
            for parcel in db.execute(
                """
                SELECT p.*, j.name AS jurisdiction_name,
                       ip.link_method, ip.link_confidence
                FROM instrument_parcel ip
                JOIN parcel_snapshot p USING(parcel_id)
                JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
                WHERE ip.instrument_id=?
                ORDER BY p.jurisdiction_geoid, p.native_parcel_id
                """,
                (row["instrument_id"],),
            )
        ]
        records.append(
            {
                "canonical_ref": canonical_property_ref(
                    row["source_id"],
                    row["jurisdiction_geoid"],
                    "instrument",
                    row["native_document_id"],
                ),
                "instrument_id": row["instrument_id"],
                "source_id": row["source_id"],
                "jurisdiction_geoid": row["jurisdiction_geoid"],
                "jurisdiction_name": row["jurisdiction_name"],
                "native_document_id": row["native_document_id"],
                "instrument_type": row["instrument_type"],
                "book": row["book"],
                "page": row["page"],
                "execution_date": row["execution_date"],
                "recording_date": row["recording_date"],
                "consideration_minor": row["consideration_minor"],
                "currency": row["currency"],
                "legal_description_raw": row["legal_description_raw"],
                "source_url": row["source_url"],
                "parties": parties,
                "parcels": parcels,
            }
        )
    return records, cursor


def _find_parcels(
    db,
    selector: str,
    jurisdiction: str | None,
    tax_year: int | None,
    limit: int,
) -> list[sqlite3.Row]:
    conditions = [
        "(p.native_parcel_id=? OR EXISTS("
        "SELECT 1 FROM parcel_alias pa "
        "WHERE pa.parcel_id=p.parcel_id AND pa.alias_value=?))"
    ]
    params: list[Any] = [selector, selector]
    if jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(jurisdiction)
    if tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(tax_year))
    params.append(limit)
    return db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name
        FROM parcel_snapshot p
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {' AND '.join(conditions)}
        ORDER BY p.roll_year DESC LIMIT ?
        """,
        params,
    ).fetchall()


def _local_chain(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], None]:
    records = []
    for parcel in _find_parcels(
        db,
        selector,
        args.jurisdiction,
        args.tax_year,
        args.limit,
    ):
        parcel_id = parcel["parcel_id"]
        owners = [
            dict(row)
            for row in db.execute(
                """
                SELECT ownership_assertion_id, assertion_type, raw_owner_name,
                       normalized_owner_name, effective_from, effective_to,
                       confidence, claim_type, evidence_ref, source_quote
                FROM ownership_assertion
                WHERE parcel_id=?
                ORDER BY effective_from, ownership_assertion_id
                """,
                (parcel_id,),
            )
        ]
        sales = [
            {
                **dict(row),
                "raw": _json_value(row["raw_json"]),
            }
            for row in db.execute(
                """
                SELECT sale_event_id, source_id, native_sale_id, sale_date,
                       execution_date, recording_date, consideration_minor,
                       currency, qualification_code, derivation, instrument_id,
                       raw_json
                FROM sale_event
                WHERE parcel_id=?
                ORDER BY COALESCE(recording_date, execution_date, sale_date),
                         sale_event_id
                """,
                (parcel_id,),
            )
        ]
        instruments = [
            {
                "canonical_ref": canonical_property_ref(
                    row["source_id"],
                    row["jurisdiction_geoid"],
                    "instrument",
                    row["native_document_id"],
                ),
                **dict(row),
            }
            for row in db.execute(
                """
                SELECT ri.instrument_id, ri.source_id, ri.jurisdiction_geoid,
                       ri.native_document_id, ri.instrument_type,
                       ri.execution_date, ri.recording_date,
                       ri.consideration_minor, ri.currency,
                       ip.link_method, ip.link_confidence
                FROM instrument_parcel ip
                JOIN recorded_instrument ri USING(instrument_id)
                WHERE ip.parcel_id=?
                ORDER BY COALESCE(ri.recording_date, ri.execution_date),
                         ri.instrument_id
                """,
                (parcel_id,),
            )
        ]
        lineage = [
            dict(row)
            for row in db.execute(
                """
                SELECT predecessor_parcel_id, successor_parcel_id,
                       relationship, effective_date, source_id, evidence_ref
                FROM parcel_lineage
                WHERE predecessor_parcel_id=? OR successor_parcel_id=?
                ORDER BY effective_date
                """,
                (parcel_id, parcel_id),
            )
        ]
        gap_flags = []
        if not instruments:
            gap_flags.append("no_recorded_instrument_coverage")
        if owners and all(
            owner["assertion_type"] == "assessment_roll" for owner in owners
        ):
            gap_flags.append("assessment_owner_observations_only")
        if any(sale["instrument_id"] is None for sale in sales):
            gap_flags.append("sale_without_instrument_link")
        record = _parcel_record(parcel)
        record.update(
            {
                "ownership_assertions": owners,
                "sale_events": sales,
                "recorded_instruments": instruments,
                "parcel_lineage": lineage,
                "chain_analysis": {
                    "claim_type": "synthesis",
                    "confidence_ceiling": "medium",
                    "gap_flags": gap_flags,
                    "complete_chain_claimed": False,
                },
            }
        )
        records.append(record)
    return records, None


def _local_map(db, selector: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], None]:
    records = []
    for parcel in _find_parcels(
        db,
        selector,
        args.jurisdiction,
        args.tax_year,
        args.limit,
    ):
        for geometry in db.execute(
            """
            SELECT geometry_id, geometry_ref, geometry_format, crs,
                   source_resolution, accuracy_disclaimer, source_id,
                   snapshot_date
            FROM parcel_geometry
            WHERE parcel_id=?
            ORDER BY snapshot_date DESC, geometry_id DESC
            """,
            (parcel["parcel_id"],),
        ):
            record = _parcel_record(parcel)
            record["geometry"] = dict(geometry)
            record["geometry"]["surveyed_legal_boundary"] = False
            records.append(record)
    return records, None


LOCAL_HANDLERS: dict[
    str,
    Callable[[sqlite3.Connection, str, argparse.Namespace], tuple[list[dict[str, Any]], str | None]],
] = {
    "owner": _local_owner,
    "address": _local_address,
    "parcel": _local_parcel,
    "instrument": _local_instrument,
    "chain": _local_chain,
    "map": _local_map,
}


_PROPERTY_OPERATION_ALIASES = {
    "owner": {"owner", "party", "party_search"},
    "address": {"address", "address_search"},
    "parcel": {"parcel", "parcel_search"},
    "instrument": {"instrument", "document", "document_search"},
    "chain": {"chain", "history"},
    "map": {"map", "parcel"},
}
_SELECTOR_PARAMETER_KEYS = (
    "selector",
    "query",
    "assessment_no",
    "document_id",
    "parcel_id",
    "party_name",
    "owner",
    "address",
)


def _normalized_selector(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _property_query_evidence(
    observation: Mapping[str, Any],
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any] | None:
    observation = dict(observation)
    raw = _json_value(observation.get("raw_json"))
    if not isinstance(raw, Mapping):
        return None
    query = raw.get("query")
    if not isinstance(query, Mapping):
        return None
    source = query.get("source")
    jurisdiction = query.get("jurisdiction")
    metadata = query.get("query")
    if not all(isinstance(value, Mapping) for value in (source, jurisdiction, metadata)):
        return None
    if source.get("source_id") != observation.get("source_id"):
        return None
    if query.get("fingerprint") != observation.get("query_fingerprint"):
        return None

    operation = str(metadata.get("operation") or "").strip().casefold()
    if operation not in _PROPERTY_OPERATION_ALIASES.get(args.command, {args.command}):
        return None
    parameters = metadata.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    selectors = {
        _normalized_selector(parameters.get(key))
        for key in _SELECTOR_PARAMETER_KEYS
        if parameters.get(key) not in (None, "")
    }
    if {
        "borough",
        "block",
        "lot",
    }.issubset(parameters) and all(
        parameters.get(key) not in (None, "")
        for key in ("borough", "block", "lot")
    ):
        selectors.add(
            _normalized_selector(
                f"{parameters['borough']}-{parameters['block']}-{parameters['lot']}"
            )
        )
    if _normalized_selector(selector) not in selectors:
        return None

    evidence_jurisdiction = str(
        jurisdiction.get("jurisdiction_id") or ""
    ).strip()
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    if not requested_jurisdiction or evidence_jurisdiction != requested_jurisdiction:
        return None

    evidence_tax_year = next(
        (
            parameters.get(key)
            for key in ("tax_year", "roll_year", "assessment_year")
            if parameters.get(key) not in (None, "")
        ),
        None,
    )
    if args.tax_year is None:
        if evidence_tax_year is not None:
            return None
    elif str(evidence_tax_year or "") != str(args.tax_year):
        return None

    records = raw.get("records")
    complete_zero = (
        observation.get("access_status") == ResultStatus.NO_RESULTS.value
        and raw.get("status") == ResultStatus.NO_RESULTS.value
        and records == []
        and raw.get("next_cursor") is None
        and metadata.get("cursor") is None
        and bool(observation.get("retrieved_at"))
    )
    return {
        "source_id": observation["source_id"],
        "status": observation["access_status"],
        "retrieved_at": observation["retrieved_at"],
        "query_fingerprint": observation["query_fingerprint"],
        "jurisdiction": evidence_jurisdiction,
        "operation": operation,
        "tax_year": evidence_tax_year,
        "complete_zero": complete_zero,
    }


def _property_route_guidance(args: argparse.Namespace) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "discover": (
            "uv run python tools/query_property.py sources "
            "[--jurisdiction GEOID] --output FILE"
        ),
        "select_source": "--source SOURCE_ID",
        "catalog_sources": [],
    }
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        for source in catalog.list_sources(
            domain="property",
            jurisdiction=args.jurisdiction,
        ):
            source_id = source["source_id"]
            decision = catalog.machine_acquisition_decision(source_id)
            guidance["catalog_sources"].append(
                {
                    "source_id": source_id,
                    "official_url": source.get("official_url"),
                    "acquisition_status": acquisition_result_status(decision),
                    "query_guidance": _source_guidance(source_id),
                }
            )
    except (CatalogError, sqlite3.Error, ValueError) as error:
        guidance["catalog_error"] = str(error)
    return guidance


def _property_local_coverage(
    db: sqlite3.Connection,
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any]:
    row_counts = {
        "query_envelopes": int(
            db.execute(
                """
                SELECT COUNT(*) FROM source_observation
                WHERE record_kind='query_envelope'
                """
            ).fetchone()[0]
        ),
        "parcels": int(db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0]),
        "instruments": int(
            db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0]
        ),
    }
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    jurisdiction_counts = {"parcels": 0, "instruments": 0}
    source_ids: set[str] = set()
    if requested_jurisdiction:
        jurisdiction_counts = {
            "parcels": int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM parcel_snapshot
                    WHERE jurisdiction_geoid=?
                    """,
                    (requested_jurisdiction,),
                ).fetchone()[0]
            ),
            "instruments": int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM recorded_instrument
                    WHERE jurisdiction_geoid=?
                    """,
                    (requested_jurisdiction,),
                ).fetchone()[0]
            ),
        }
        source_ids.update(
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT source_id FROM parcel_snapshot
                WHERE jurisdiction_geoid=?
                UNION
                SELECT DISTINCT source_id FROM recorded_instrument
                WHERE jurisdiction_geoid=?
                """,
                (requested_jurisdiction, requested_jurisdiction),
            )
        )
    else:
        source_ids.update(
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT source_id FROM parcel_snapshot
                UNION
                SELECT DISTINCT source_id FROM recorded_instrument
                """
            )
        )

    matching_evidence: list[dict[str, Any]] = []
    observed_requested_scope = False
    observations = db.execute(
        """
        SELECT observation_id, source_id, query_fingerprint, retrieved_at,
               access_status, raw_json
        FROM source_observation
        WHERE record_kind='query_envelope'
        ORDER BY retrieved_at DESC, observation_id DESC
        """
    ).fetchall()
    for observation in observations:
        raw = _json_value(observation["raw_json"])
        if isinstance(raw, Mapping):
            raw_query = raw.get("query")
            raw_jurisdiction = (
                raw_query.get("jurisdiction")
                if isinstance(raw_query, Mapping)
                else None
            )
            observed_geoid = (
                str(raw_jurisdiction.get("jurisdiction_id") or "").strip()
                if isinstance(raw_jurisdiction, Mapping)
                else ""
            )
            if requested_jurisdiction and observed_geoid == requested_jurisdiction:
                observed_requested_scope = True
                source_ids.add(str(observation["source_id"]))
        evidence = _property_query_evidence(observation, args, selector)
        if evidence is not None:
            matching_evidence.append(evidence)

    latest_by_source: dict[str, dict[str, Any]] = {}
    for evidence in matching_evidence:
        latest_by_source.setdefault(evidence["source_id"], evidence)
    latest = list(latest_by_source.values())
    authoritative_zero = bool(latest) and all(
        evidence["complete_zero"] for evidence in latest
    )
    has_global_cache = any(row_counts.values())
    scope_covered = (
        has_global_cache
        if not requested_jurisdiction
        else observed_requested_scope or any(jurisdiction_counts.values())
    )
    return {
        "authoritative_zero": authoritative_zero,
        "requested_scope": {
            "operation": args.command,
            "selector": selector,
            "jurisdiction": requested_jurisdiction or None,
            "tax_year": args.tax_year,
        },
        "sidecar": {
            "row_counts": row_counts,
            "requested_jurisdiction_counts": jurisdiction_counts,
            "requested_scope_observed": observed_requested_scope,
            "scope_covered": scope_covered,
            "source_ids": sorted(source_ids),
        },
        "matching_query_evidence": latest,
    }


def _local_result(args: argparse.Namespace) -> PublicRecordsResult:
    selector = " ".join(args.query.split()).strip()
    query = _query(LOCAL_SOURCE, args.command, selector, args)
    try:
        db = connect_property(args.property_db)
        try:
            records, cursor = LOCAL_HANDLERS[args.command](db, selector, args)
            coverage = _property_local_coverage(db, args, selector)
        finally:
            db.close()
        if records:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=cursor,
            )
        elif coverage["authoritative_zero"]:
            evidence = coverage["matching_query_evidence"]
            result = PublicRecordsResult.success(
                query,
                [],
                warnings=[
                    "Exact source-query zero preserved from "
                    + ", ".join(
                        f"{item['source_id']} at {item['retrieved_at']}"
                        for item in evidence
                    )
                ],
            )
        else:
            scope_covered = coverage["sidecar"]["scope_covered"]
            result = PublicRecordsResult.failure(
                query,
                (
                    ResultStatus.PARTIAL
                    if scope_covered
                    else ResultStatus.UNAVAILABLE
                ),
                [
                    PublicRecordsError(
                        code=(
                            "local_cache_miss"
                            if scope_covered
                            else "local_scope_not_covered"
                        ),
                        message=(
                            "no matching normalized record is cached, and no "
                            "exact source-query zero establishes an empty result"
                        ),
                        category="local_coverage",
                        retryable=False,
                        details={
                            "coverage": coverage,
                            "route_guidance": _property_route_guidance(args),
                        },
                    )
                ],
            )
    except (sqlite3.Error, TypeError, ValueError) as error:
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
    roles = detail.get("roles") or ["public_record"]
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


def _access_failure(
    args: argparse.Namespace,
    *,
    detail: Mapping[str, Any] | None,
    decision: Mapping[str, Any] | None,
    code: str,
    message: str,
    status: ResultStatus,
) -> PublicRecordsResult:
    source = (
        _catalog_source(detail)
        if detail is not None
        else SourceMetadata(
            source_id=args.source,
            name=args.source,
            source_role="unresolved_property_source",
        )
    )
    query = _query(source, args.command, args.query, args)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="source_access",
                retryable=False,
                details={
                    "access_decision": decision or {},
                    "source_guidance": _source_guidance(args.source),
                },
            )
        ],
    )


def _live_result(
    args: argparse.Namespace,
) -> tuple[PublicRecordsResult, bool]:
    """Return ``(result, adapter_invoked)`` for one explicit external source."""
    catalog = PublicRecordsCatalog(args.catalog_db)
    try:
        detail = catalog.show_source(args.source)
    except CatalogError as error:
        return (
            _access_failure(
                args,
                detail=None,
                decision=None,
                code="source_not_registered",
                message=str(error),
                status=ResultStatus.UNAVAILABLE,
            ),
            False,
        )
    decision = catalog.machine_acquisition_decision(args.source)
    if not decision["allowed"]:
        status = ResultStatus(acquisition_result_status(decision))
        return (
            _access_failure(
                args,
                detail=detail,
                decision=decision,
                code=decision["reason_code"],
                message=decision["reason"],
                status=status,
            ),
            False,
        )

    source_routes = LIVE_ROUTES.get(args.source)
    if source_routes is None:
        guidance = _source_guidance(args.source)
        return (
            _access_failure(
                args,
                detail=detail,
                decision=decision,
                code="adapter_not_implemented",
                message=(
                    f"{args.source} has no unified direct-query adapter; "
                    f"use {guidance.get('direct_tool', 'the catalogued source route')}"
                ),
                status=ResultStatus.UNAVAILABLE,
            ),
            False,
        )
    route = source_routes.get(args.command)
    if route is None:
        return (
            _access_failure(
                args,
                detail=detail,
                decision=decision,
                code="capability_not_supported",
                message=(
                    f"{args.source} does not support unified operation "
                    f"{args.command}; supported operations: "
                    f"{', '.join(sorted(source_routes))}"
                ),
                status=ResultStatus.UNAVAILABLE,
            ),
            False,
        )

    adapter_args = route.translate(args, route.adapter_command)
    return (
        route.adapter.execute(
            adapter_args,
            access_decision=decision,
        ),
        True,
    )


def _sources_result(args: argparse.Namespace) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=CATALOG_SOURCE,
        jurisdiction=_jurisdiction(args.jurisdiction),
        query=QueryMetadata(
            operation="sources",
            parameters={"domain": "property", "jurisdiction": args.jurisdiction},
        ),
    )
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        rows = catalog.list_sources(
            domain="property", jurisdiction=args.jurisdiction
        )
        records = []
        for row in rows:
            decision = catalog.machine_acquisition_decision(row["source_id"])
            detail = catalog.show_source(row["source_id"])
            records.append(
                {
                    **row,
                    "capabilities": [
                        capability["name"]
                        for capability in detail.get("capabilities", ())
                        if capability.get("supported", True)
                    ],
                    "machine_acquisition": decision,
                    "query_guidance": _source_guidance(row["source_id"]),
                }
            )
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
    if args.source == "local":
        if args.ingest:
            raise ValueError("--ingest requires a live source")
        return _local_result(args).to_dict()

    result, adapter_invoked = _live_result(args)
    if not adapter_invoked:
        log_search(
            canonical_json(result.query.to_dict()),
            args.source,
            None,
        )
    payload = result.to_dict()
    if args.ingest:
        if not adapter_invoked:
            payload["ingest"] = {
                "status": "skipped",
                "reason": "no live adapter envelope was returned",
            }
        else:
            payload["ingest"] = ingest_property_envelope(
                payload, db_path=args.property_db
            )
    return payload


def _emit(payload: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        payload,
        args,
        summary=f"property {args.command} ({payload.get('status', 'unknown')})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    records = payload.get("records", [])
    print(f"Property {args.command}: {payload.get('status')} ({len(records)} records)")
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        label = (
            record.get("native_parcel_id")
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


def _add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query")
    parser.add_argument(
        "--source",
        default="local",
        help="Canonical catalog source ID, or local (default)",
    )
    parser.add_argument("--jurisdiction", help="State/county GEOID filter")
    parser.add_argument(
        "--county-code",
        "--county-fips",
        dest="county_fips",
        help="Optional source-specific county code, FIPS, or GEOID",
    )
    parser.add_argument(
        "--tax-year",
        type=int,
        help="Optional source tax or assessment year",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor")
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    parser.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Request source geometry where supported",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Normalize a live result when a sidecar ingester is available",
    )
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling for live source queries",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query normalized and catalogued property record sources"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources", help="List catalogued property sources")
    sources.add_argument("--jurisdiction", help="State/county GEOID filter")
    sources.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    add_output_args(sources)

    for command, help_text in (
        ("owner", "Search normalized owner observations"),
        ("address", "Search normalized situs or mailing addresses"),
        ("parcel", "Look up a native or alternate parcel identifier"),
        ("instrument", "Search recorded instruments and instrument parties"),
        ("chain", "Build a gap-labeled chain-of-title view"),
        ("map", "Return source-provided parcel geometry references"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        _add_query_args(command_parser)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "page_size", 1) <= 0 or (
        getattr(args, "max_records", None) is not None
        and args.max_records <= 0
    ):
        parser.error("--page-size must be positive; --max-records is optional")
    if getattr(args, "tax_year", None) is not None and args.tax_year <= 0:
        parser.error("--tax-year must be positive")
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    try:
        payload = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(payload, args)


if __name__ == "__main__":
    main()
