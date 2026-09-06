#!/usr/bin/env python3
"""Plan and enqueue source-specific public-record acquisition actions.

The source catalog describes machine, account, licensed, paid, request, and
physical-access routes. This tool turns any catalog entry into a reproducible
``human_actions`` work item without embedding source-specific behavior in query
adapters.

Usage:
    uv run python tools/public_records_actions.py plan us-in-iocs-bulk \
      --operation obtain_feed --selector "civil case metadata"
    uv run python tools/public_records_actions.py enqueue us-ny-nyscef \
      --operation fetch_document --selector "156728/2019 document 42"
    uv run python tools/public_records_actions.py list --source us-ny-nyscef
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from tools.lead_tracker import get_db
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        PublicRecordsCatalog,
    )
    from tools.public_records_contract import canonical_json, sha256_fingerprint
except ImportError:
    from lead_tracker import get_db
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        PublicRecordsCatalog,
    )
    from public_records_contract import canonical_json, sha256_fingerprint


ACTION_SCHEMA_VERSION = "public-records-action/1.0"
ACTION_TYPES = (
    "foia_request",
    "paid_lookup",
    "manual_verification",
    "account_access",
    "physical_records",
    "legal_filing",
    "interview",
    "purchase",
    "configuration",
    "other",
)
PRIORITIES = ("critical", "high", "medium", "low")
STATUSES = ("pending", "in_progress", "completed", "blocked", "cancelled")


class PublicRecordsActionError(ValueError):
    """Raised when an action request cannot be represented."""


def _clean_text(value: Any, field_name: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise PublicRecordsActionError(f"{field_name} is required")
        return None
    text = " ".join(str(value).split()).strip()
    if required and not text:
        raise PublicRecordsActionError(f"{field_name} is required")
    return text or None


def _action_type_suggestions(detail: Mapping[str, Any]) -> list[str]:
    """Return non-binding queue types suggested by catalog metadata."""
    source = detail["source"]
    review = detail.get("latest_access_review") or {}
    authentication = str(source.get("authentication") or "").casefold()
    fees = str(source.get("fees") or "").casefold()
    access_class = review.get("access_class") or source.get("access_class")
    suggestions: list[str] = []
    if any(token in authentication for token in ("account", "login", "subscription")):
        suggestions.append("account_access")
    if access_class == "D" or any(
        token in fees for token in ("paid", "fee", "transaction", "tier")
    ):
        suggestions.extend(("purchase", "paid_lookup"))
    if access_class == "E":
        suggestions.extend(("physical_records", "foia_request"))
    suggestions.extend(("manual_verification", "other"))
    return list(dict.fromkeys(suggestions))


def build_action(
    catalog: PublicRecordsCatalog,
    *,
    source_id: str,
    operation: str,
    selector: str | None = None,
    jurisdiction: str | None = None,
    court_or_office: str | None = None,
    requested_fields: Sequence[str] = (),
    action_type: str | None = None,
    priority: str = "medium",
    related_lead_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic action proposal from current catalog metadata."""
    source_id = _clean_text(source_id, "source_id", required=True) or ""
    operation = _clean_text(operation, "operation", required=True) or ""
    selector = _clean_text(selector, "selector")
    jurisdiction = _clean_text(jurisdiction, "jurisdiction")
    court_or_office = _clean_text(court_or_office, "court_or_office")
    notes = _clean_text(notes, "notes")
    if priority not in PRIORITIES:
        raise PublicRecordsActionError(f"unsupported priority: {priority}")
    if related_lead_id is not None and related_lead_id <= 0:
        raise PublicRecordsActionError("related_lead_id must be positive")

    detail = catalog.show_source(source_id)
    suggestions = _action_type_suggestions(detail)
    selected_type = action_type or suggestions[0]
    if selected_type not in ACTION_TYPES:
        raise PublicRecordsActionError(f"unsupported action type: {selected_type}")

    fields = [
        field
        for item in requested_fields
        if (field := _clean_text(item, "requested_fields[]"))
    ]
    request = {
        "source_id": source_id,
        "operation": operation,
        "selector": selector,
        "jurisdiction": jurisdiction,
        "court_or_office": court_or_office,
        "requested_fields": fields,
    }
    fingerprint = sha256_fingerprint(request)
    source = detail["source"]
    payload = {
        "schema_version": ACTION_SCHEMA_VERSION,
        "action_fingerprint": fingerprint,
        "source": {
            "source_id": source_id,
            "name": source["name"],
            "official_url": source.get("official_url"),
            "domain": source.get("domain"),
            "authority": source.get("authority"),
            "authentication": source.get("authentication"),
            "fees": source.get("fees"),
        },
        "request": request,
        "capabilities": detail.get("capabilities") or [],
        "latest_access_review": detail.get("latest_access_review"),
        "suggested_action_types": suggestions,
        "selected_action_type": selected_type,
        "priority": priority,
        "related_lead_id": related_lead_id,
        "notes": notes,
    }
    return payload


def enqueue_action(
    action: Mapping[str, Any],
    *,
    force: bool = False,
    db_factory=get_db,
) -> dict[str, Any]:
    """Insert an action idempotently while an equivalent item remains active."""
    payload = dict(action)
    description = canonical_json(payload)
    source = payload["source"]
    request = payload["request"]
    action_type = payload["selected_action_type"]
    priority = payload["priority"]
    title = f"{source['name']}: {request['operation']}"
    db = db_factory()
    try:
        existing = None
        if not force:
            existing = db.execute(
                """
                SELECT * FROM human_actions
                WHERE description=? AND status IN ('pending', 'in_progress', 'blocked')
                ORDER BY id DESC LIMIT 1
                """,
                (description,),
            ).fetchone()
        if existing is not None:
            return {
                "status": "existing",
                "action_id": int(existing["id"]),
                "action": payload,
            }
        cursor = db.execute(
            """
            INSERT INTO human_actions(
                title, description, action_type, priority, related_lead_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                action_type,
                priority,
                payload.get("related_lead_id"),
                payload.get("notes"),
            ),
        )
        db.commit()
        return {
            "status": "enqueued",
            "action_id": int(cursor.lastrowid),
            "action": payload,
        }
    finally:
        db.close()


def list_actions(
    *,
    source_id: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    db_factory=get_db,
) -> list[dict[str, Any]]:
    """List public-record action items, including their structured payloads."""
    if status is not None and status not in STATUSES:
        raise PublicRecordsActionError(f"unsupported status: {status}")
    if limit is not None and limit <= 0:
        raise PublicRecordsActionError("limit must be positive")
    conditions = ["description LIKE ?"]
    params: list[Any] = [f'%{ACTION_SCHEMA_VERSION}%']
    if status:
        conditions.append("status=?")
        params.append(status)
    sql = (
        "SELECT * FROM human_actions WHERE "
        + " AND ".join(conditions)
        + " ORDER BY id DESC"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    db = db_factory()
    try:
        rows = db.execute(sql, params).fetchall()
    finally:
        db.close()
    records = []
    for row in rows:
        record = dict(row)
        try:
            payload = json.loads(record["description"])
        except (TypeError, json.JSONDecodeError):
            continue
        if source_id and payload.get("source", {}).get("source_id") != source_id:
            continue
        record["action"] = payload
        records.append(record)
    return records


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan and enqueue catalog-backed public-record actions"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "enqueue"):
        command = sub.add_parser(name)
        command.add_argument("source_id")
        command.add_argument("--operation", required=True)
        command.add_argument("--selector")
        command.add_argument("--jurisdiction")
        command.add_argument("--court-or-office")
        command.add_argument("--requested-field", action="append", default=[])
        command.add_argument("--action-type", choices=ACTION_TYPES)
        command.add_argument("--priority", choices=PRIORITIES, default="medium")
        command.add_argument("--related-lead-id", type=int)
        command.add_argument("--notes")
        command.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
        if name == "enqueue":
            command.add_argument("--force", action="store_true")
        add_output_args(command)

    command = sub.add_parser("list")
    command.add_argument("--source")
    command.add_argument("--status", choices=STATUSES)
    command.add_argument("--limit", type=int)
    add_output_args(command)
    return parser


def execute(args: argparse.Namespace) -> Any:
    if args.command == "list":
        return list_actions(
            source_id=args.source,
            status=args.status,
            limit=args.limit,
        )
    catalog = PublicRecordsCatalog(Path(args.catalog_db))
    action = build_action(
        catalog,
        source_id=args.source_id,
        operation=args.operation,
        selector=args.selector,
        jurisdiction=args.jurisdiction,
        court_or_office=args.court_or_office,
        requested_fields=args.requested_field,
        action_type=args.action_type,
        priority=args.priority,
        related_lead_id=args.related_lead_id,
        notes=args.notes,
    )
    if args.command == "plan":
        return action
    return enqueue_action(action, force=args.force)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        payload = execute(args)
    except (PublicRecordsActionError, sqlite3.Error, ValueError) as error:
        parser.error(str(error))
        return
    count = len(payload) if isinstance(payload, list) else 1
    if write_output(
        payload,
        args,
        summary=f"public-record actions: {count}",
    ):
        return
    print(json.dumps(payload, indent=2 if args.json_out else None, sort_keys=True))


if __name__ == "__main__":
    main()
