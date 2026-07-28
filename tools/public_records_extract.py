#!/usr/bin/env python3
"""Validate and ingest document extractions with page-level provenance.

This module accepts extraction output from any OCR/parser/model stack. It
performs deterministic shape and value checks, writes each usable field to the
content-addressed public-record artifact store, and creates review work for
anything that needs adjudication. Extraction and review history are append-only.

Usage:
    uv run python tools/public_records_extract.py validate extraction.json
    uv run python tools/public_records_extract.py ingest extraction.json
    uv run python tools/public_records_extract.py queue
    uv run python tools/public_records_extract.py decide REVIEW_REF \
      --decision accepted --by analyst
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_artifacts import (
        DEFAULT_DB as DEFAULT_ARTIFACT_DB,
        DEFAULT_STORE as DEFAULT_ARTIFACT_STORE,
        PublicRecordsArtifactStore,
    )
    from tools.public_records_contract import canonical_json, utc_now_iso
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_artifacts import (
        DEFAULT_DB as DEFAULT_ARTIFACT_DB,
        DEFAULT_STORE as DEFAULT_ARTIFACT_STORE,
        PublicRecordsArtifactStore,
    )
    from public_records_contract import canonical_json, utc_now_iso


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW_DB = PROJECT_ROOT / "datasets" / "public_records_review.db"
EXTRACTION_SCHEMA_VERSION = "public-records-extraction/1.0"
VALIDATOR_NAME = "public_records_extract"
VALIDATOR_VERSION = "1"

DATE_FIELD_RE = re.compile(r"(?:^|_)(?:date|filed|entered|executed|recorded)(?:$|_)")
AMOUNT_FIELD_RE = re.compile(
    r"(?:^|_)(?:amount|price|consideration|value|balance|damages)(?:$|_)"
)
IDENTIFIER_FIELD_RE = re.compile(
    r"(?:^|_)(?:id|identifier|number|case_number|document_number|book|page)(?:$|_)"
)
ISO_DATE_RE = re.compile(r"^\d{4}(?:-\d{2})?(?:-\d{2})?$")
FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")

REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extraction_run (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ref TEXT NOT NULL UNIQUE,
    input_sha256 TEXT NOT NULL UNIQUE,
    parent_artifact_sha256 TEXT NOT NULL,
    evidence_artifact_sha256 TEXT NOT NULL,
    acquisition_id INTEGER,
    representation_id INTEGER,
    producer_name TEXT NOT NULL,
    producer_version TEXT NOT NULL,
    prompt_id TEXT,
    prompt_version TEXT,
    schema_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    field_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,
    validation_summary_json TEXT NOT NULL,
    raw_input_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_item (
    review_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_ref TEXT NOT NULL UNIQUE,
    run_id INTEGER NOT NULL REFERENCES extraction_run(run_id),
    field_index INTEGER NOT NULL,
    evidence_id INTEGER,
    field_name TEXT,
    reason_codes_json TEXT NOT NULL,
    current_decision TEXT NOT NULL DEFAULT 'pending',
    current_event_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, field_index)
);
CREATE INDEX IF NOT EXISTS idx_review_item_decision
    ON review_item(current_decision, created_at);

CREATE TABLE IF NOT EXISTS review_event (
    review_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_ref TEXT NOT NULL UNIQUE,
    review_item_id INTEGER NOT NULL REFERENCES review_item(review_item_id),
    decision TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    notes TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    decided_at TEXT NOT NULL,
    supersedes_event_id INTEGER REFERENCES review_event(review_event_id)
);
CREATE INDEX IF NOT EXISTS idx_review_event_item
    ON review_event(review_item_id, review_event_id);

CREATE TRIGGER IF NOT EXISTS extraction_run_no_update
BEFORE UPDATE ON extraction_run
BEGIN
    SELECT RAISE(ABORT, 'extraction runs are immutable');
END;
CREATE TRIGGER IF NOT EXISTS extraction_run_no_delete
BEFORE DELETE ON extraction_run
BEGIN
    SELECT RAISE(ABORT, 'extraction runs are immutable');
END;
CREATE TRIGGER IF NOT EXISTS review_event_no_update
BEFORE UPDATE ON review_event
BEGIN
    SELECT RAISE(ABORT, 'review events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS review_event_no_delete
BEFORE DELETE ON review_event
BEGIN
    SELECT RAISE(ABORT, 'review events are immutable');
END;
"""


class ExtractionError(RuntimeError):
    """Raised when extraction input or review state is invalid."""


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExtractionError(f"extraction file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"invalid extraction JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ExtractionError("extraction input must be a JSON object")
    return value


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtractionError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field)


def _version_pair(
    value: Mapping[str, Any], name_key: str, version_key: str
) -> tuple[str | None, str | None]:
    name = _optional_text(value.get(name_key), f"producer.{name_key}")
    version = _optional_text(value.get(version_key), f"producer.{version_key}")
    if (name is None) != (version is None):
        raise ExtractionError(
            f"producer.{name_key} and producer.{version_key} must be supplied together"
        )
    return name, version


def _parse_confidence(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExtractionError(f"{field} must be a number from 0 to 1")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ExtractionError(f"{field} must be a number from 0 to 1")
    return result


def _connect_review_db(path: str | Path = DEFAULT_REVIEW_DB) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.executescript(REVIEW_SCHEMA)
    db.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '1')"
    )
    db.commit()
    return db


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    for key in (
        "validation_summary_json",
        "raw_input_json",
        "reason_codes_json",
        "details_json",
    ):
        if key in item:
            item[key.removesuffix("_json")] = json.loads(item.pop(key))
    return item


def _text_for_representation(
    store: PublicRecordsArtifactStore, representation: Mapping[str, Any]
) -> str | None:
    path = store.artifact_path(str(representation["artifact_sha256"]))
    media_type = str(
        store.show("artifact", str(representation["artifact_sha256"])).get(
            "first_media_type"
        )
        or ""
    ).lower()
    if media_type and not (
        media_type.startswith("text/")
        or media_type in {"application/json", "application/xml"}
    ):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        if len(value) == 4:
            return 1 <= int(value) <= 9999
        if len(value) == 7:
            date.fromisoformat(f"{value}-01")
            return True
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _validate_amount(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["amount_not_object"]
    reasons: list[str] = []
    amount = value.get("amount_minor")
    if isinstance(amount, bool) or not isinstance(amount, int):
        reasons.append("amount_minor_not_integer")
    currency = value.get("currency")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        reasons.append("currency_not_iso_code")
    return reasons


def _validate_region(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return ["region_not_object"]
    bbox = ("x", "y", "width", "height")
    present = [key for key in bbox if key in value]
    if present and len(present) != len(bbox):
        return ["region_incomplete_bbox"]
    reasons: list[str] = []
    for key in present:
        coordinate = value[key]
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            reasons.append(f"region_{key}_not_number")
    return reasons


def _normalize_input(
    payload: Mapping[str, Any],
    store: PublicRecordsArtifactStore,
    *,
    review_below: float | None = None,
) -> dict[str, Any]:
    schema_version = _required_text(payload.get("schema_version"), "schema_version")
    if schema_version != EXTRACTION_SCHEMA_VERSION:
        raise ExtractionError(
            f"schema_version must be {EXTRACTION_SCHEMA_VERSION}"
        )

    parent_sha256 = _required_text(
        payload.get("artifact_sha256"), "artifact_sha256"
    ).lower()
    parent = store.show("artifact", parent_sha256)
    representation_id = payload.get("representation_id")
    if representation_id is None:
        raise ExtractionError("representation_id is required")
    representation = store.get_representation(str(representation_id))
    if representation["parent_artifact_sha256"] != parent_sha256:
        raise ExtractionError(
            "representation_id must derive from artifact_sha256"
        )
    evidence_sha256 = str(representation["artifact_sha256"])
    representation_text = _text_for_representation(store, representation)

    acquisition_id = payload.get("acquisition_id")
    acquisition = None
    if acquisition_id is not None:
        acquisition = store.get_acquisition(str(acquisition_id))
        if acquisition["artifact_sha256"] != parent_sha256:
            raise ExtractionError(
                "acquisition_id must refer to artifact_sha256"
            )

    producer_raw = payload.get("producer")
    if not isinstance(producer_raw, Mapping):
        raise ExtractionError("producer must be a JSON object")
    producer_name = _required_text(producer_raw.get("name"), "producer.name")
    producer_version = _required_text(
        producer_raw.get("version"), "producer.version"
    )
    prompt_id, prompt_version = _version_pair(
        producer_raw, "prompt_id", "prompt_version"
    )
    schema_id = _required_text(producer_raw.get("schema_id"), "producer.schema_id")
    extraction_schema_version = _required_text(
        producer_raw.get("schema_version"), "producer.schema_version"
    )

    fields_raw = payload.get("fields")
    if not isinstance(fields_raw, list):
        raise ExtractionError("fields must be a JSON array")

    normalized_fields: list[dict[str, Any]] = []
    for index, raw in enumerate(fields_raw):
        if not isinstance(raw, Mapping):
            normalized_fields.append(
                {
                    "index": index,
                    "name": None,
                    "value": None,
                    "validation_state": "invalid",
                    "reason_codes": ["field_not_object"],
                    "storable": False,
                }
            )
            continue

        reasons: list[str] = []
        name_value = raw.get("name")
        name = name_value.strip() if isinstance(name_value, str) else ""
        if not FIELD_NAME_RE.fullmatch(name):
            reasons.append("invalid_field_name")

        value = raw.get("value")
        quote = raw.get("exact_quote")
        if not isinstance(quote, str) or not quote:
            reasons.append("missing_exact_quote")
            quote = None
        elif representation_text is not None and quote not in representation_text:
            reasons.append("quote_not_found_in_representation")

        page_number = raw.get("page_number")
        if page_number is not None and (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        ):
            reasons.append("invalid_page_number")
            page_number = None
        page_label = raw.get("page_label")
        if page_label is not None and (
            not isinstance(page_label, str) or not page_label.strip()
        ):
            reasons.append("invalid_page_label")
            page_label = None
        elif isinstance(page_label, str):
            page_label = page_label.strip()
        region = raw.get("region")
        reasons.extend(_validate_region(region))
        if page_number is None and page_label is None and region is None and quote is None:
            reasons.append("missing_provenance_locator")

        try:
            confidence = _parse_confidence(
                raw.get("confidence"), f"fields[{index}].confidence"
            )
        except ExtractionError:
            confidence = 0.0
            reasons.append("invalid_confidence")
        ceiling_value = raw.get("confidence_ceiling", confidence)
        try:
            confidence_ceiling = _parse_confidence(
                ceiling_value, f"fields[{index}].confidence_ceiling"
            )
        except ExtractionError:
            confidence_ceiling = confidence
            reasons.append("invalid_confidence_ceiling")
        if confidence > confidence_ceiling:
            reasons.append("confidence_exceeds_ceiling")
            confidence_ceiling = confidence
        if review_below is not None and confidence < review_below:
            reasons.append("below_requested_review_threshold")

        if name and DATE_FIELD_RE.search(name) and not _valid_iso_date(value):
            reasons.append("invalid_iso_date")
        if name and AMOUNT_FIELD_RE.search(name):
            reasons.extend(_validate_amount(value))
        if name and IDENTIFIER_FIELD_RE.search(name):
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                reasons.append("invalid_identifier")
            elif not str(value).strip():
                reasons.append("blank_identifier")

        invalid_reasons = {
            "field_not_object",
            "invalid_field_name",
            "missing_exact_quote",
            "missing_provenance_locator",
            "invalid_page_number",
            "invalid_page_label",
            "region_not_object",
            "region_incomplete_bbox",
            "invalid_confidence",
            "invalid_confidence_ceiling",
            "confidence_exceeds_ceiling",
            "invalid_iso_date",
            "amount_not_object",
            "amount_minor_not_integer",
            "currency_not_iso_code",
            "invalid_identifier",
            "blank_identifier",
        }
        state = (
            "invalid"
            if invalid_reasons.intersection(reasons)
            else ("review" if reasons else "valid")
        )
        storable = bool(
            name
            and (
                page_number is not None
                or page_label is not None
                or region is not None
                or quote is not None
            )
        )
        normalized_fields.append(
            {
                "index": index,
                "name": name or None,
                "value": value,
                "page_number": page_number,
                "page_label": page_label,
                "region": region if isinstance(region, Mapping) else None,
                "exact_quote": quote,
                "confidence": confidence,
                "confidence_ceiling": confidence_ceiling,
                "metadata": (
                    dict(raw.get("metadata"))
                    if isinstance(raw.get("metadata"), Mapping)
                    else {}
                ),
                "validation_state": state,
                "reason_codes": sorted(set(reasons)),
                "storable": storable,
            }
        )

    counts = Counter(field["validation_state"] for field in normalized_fields)
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "artifact_sha256": parent["sha256"],
        "evidence_artifact_sha256": evidence_sha256,
        "acquisition_id": (
            acquisition["acquisition_id"] if acquisition is not None else None
        ),
        "representation_id": representation["representation_id"],
        "producer": {
            "name": producer_name,
            "version": producer_version,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "schema_id": schema_id,
            "schema_version": extraction_schema_version,
        },
        "document": (
            dict(payload.get("document"))
            if isinstance(payload.get("document"), Mapping)
            else {}
        ),
        "fields": normalized_fields,
        "summary": {
            "field_count": len(normalized_fields),
            "validation_states": dict(sorted(counts.items())),
            "representation_text_checked": representation_text is not None,
        },
        "input_sha256": _sha256_json(payload),
    }


def validate_extraction(
    payload: Mapping[str, Any],
    *,
    artifact_db: str | Path = DEFAULT_ARTIFACT_DB,
    artifact_store: str | Path = DEFAULT_ARTIFACT_STORE,
    review_below: float | None = None,
) -> dict[str, Any]:
    if review_below is not None:
        _parse_confidence(review_below, "review_below")
    with PublicRecordsArtifactStore(artifact_db, artifact_store) as store:
        normalized = _normalize_input(
            payload, store, review_below=review_below
        )
    return {"status": "ok", "validation": normalized}


def _insert_review_item(
    db: sqlite3.Connection,
    *,
    run_id: int,
    field: Mapping[str, Any],
    evidence_id: int | None,
) -> dict[str, Any]:
    now = utc_now_iso()
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO review_item(
            review_ref, run_id, field_index, evidence_id, field_name,
            reason_codes_json, current_decision, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            f"PRREVIEW:{uuid.uuid4()}",
            run_id,
            field["index"],
            evidence_id,
            field.get("name"),
            canonical_json(field.get("reason_codes", [])),
            now,
            now,
        ),
    )
    if cursor.lastrowid:
        row = db.execute(
            "SELECT * FROM review_item WHERE review_item_id=?",
            (cursor.lastrowid,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT * FROM review_item WHERE run_id=? AND field_index=?",
            (run_id, field["index"]),
        ).fetchone()
    assert row is not None
    return _row(row) or {}


def ingest_extraction(
    payload: Mapping[str, Any],
    *,
    artifact_db: str | Path = DEFAULT_ARTIFACT_DB,
    artifact_store: str | Path = DEFAULT_ARTIFACT_STORE,
    review_db: str | Path = DEFAULT_REVIEW_DB,
    review_below: float | None = None,
) -> dict[str, Any]:
    if review_below is not None:
        _parse_confidence(review_below, "review_below")
    with PublicRecordsArtifactStore(artifact_db, artifact_store) as store:
        normalized = _normalize_input(
            payload, store, review_below=review_below
        )
        db = _connect_review_db(review_db)
        try:
            existing = db.execute(
                "SELECT * FROM extraction_run WHERE input_sha256=?",
                (normalized["input_sha256"],),
            ).fetchone()
            if existing is not None:
                run = _row(existing) or {}
                reviews = [
                    _row(row) or {}
                    for row in db.execute(
                        "SELECT * FROM review_item WHERE run_id=? ORDER BY field_index",
                        (run["run_id"],),
                    )
                ]
                return {
                    "status": "ok",
                    "deduplicated_run": True,
                    "run": run,
                    "review_items": reviews,
                }

            producer = normalized["producer"]
            expected_evidence_count = sum(
                1 for field in normalized["fields"] if field["storable"]
            )
            with db:
                cursor = db.execute(
                    """
                    INSERT INTO extraction_run(
                        run_ref, input_sha256, parent_artifact_sha256,
                        evidence_artifact_sha256, acquisition_id,
                        representation_id, producer_name, producer_version,
                        prompt_id, prompt_version, schema_id, schema_version,
                        imported_at, field_count, evidence_count,
                        validation_summary_json, raw_input_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"PRX:{uuid.uuid4()}",
                        normalized["input_sha256"],
                        normalized["artifact_sha256"],
                        normalized["evidence_artifact_sha256"],
                        normalized["acquisition_id"],
                        normalized["representation_id"],
                        producer["name"],
                        producer["version"],
                        producer["prompt_id"],
                        producer["prompt_version"],
                        producer["schema_id"],
                        producer["schema_version"],
                        utc_now_iso(),
                        len(normalized["fields"]),
                        expected_evidence_count,
                        canonical_json(normalized["summary"]),
                        canonical_json(payload),
                    ),
                )
                run_id = int(cursor.lastrowid)

            evidence_items: list[dict[str, Any]] = []
            review_items: list[dict[str, Any]] = []
            for field in normalized["fields"]:
                evidence_id: int | None = None
                if field["storable"]:
                    result = store.add_evidence(
                        normalized["evidence_artifact_sha256"],
                        acquisition_id=normalized["acquisition_id"],
                        representation_id=normalized["representation_id"],
                        page_number=field["page_number"],
                        page_label=field["page_label"],
                        region=field["region"],
                        exact_quote=field["exact_quote"],
                        field_name=field["name"],
                        field_value=field["value"],
                        validation_state=field["validation_state"],
                        validator_name=VALIDATOR_NAME,
                        validator_version=VALIDATOR_VERSION,
                        validation_details={
                            "reason_codes": field["reason_codes"],
                            "input_sha256": normalized["input_sha256"],
                            "field_index": field["index"],
                        },
                        confidence=field["confidence"],
                        confidence_ceiling=field["confidence_ceiling"],
                        metadata={
                            **field["metadata"],
                            "extraction_schema": EXTRACTION_SCHEMA_VERSION,
                            "producer": producer,
                        },
                    )
                    evidence = result["evidence"]
                    evidence_id = int(evidence["evidence_id"])
                    evidence_items.append(evidence)
                if field["validation_state"] != "valid":
                    review_items.append(
                        _insert_review_item(
                            db,
                            run_id=run_id,
                            field=field,
                            evidence_id=evidence_id,
                        )
                    )

            db.commit()
            run = _row(
                db.execute(
                    "SELECT * FROM extraction_run WHERE run_id=?", (run_id,)
                ).fetchone()
            )
            return {
                "status": "ok",
                "deduplicated_run": False,
                "run": run,
                "validation": normalized["summary"],
                "evidence": evidence_items,
                "review_items": review_items,
            }
        finally:
            db.close()


def list_review_queue(
    *,
    review_db: str | Path = DEFAULT_REVIEW_DB,
    decision: str | None = "pending",
    run_ref: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    db = _connect_review_db(review_db)
    try:
        conditions: list[str] = []
        params: list[Any] = []
        if decision is not None:
            conditions.append("ri.current_decision=?")
            params.append(decision)
        if run_ref:
            conditions.append("er.run_ref=?")
            params.append(run_ref)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_sql = ""
        if limit is not None:
            if limit < 0:
                raise ExtractionError("limit must be zero or greater")
            limit_sql = " LIMIT ?"
            params.append(limit)
        rows = db.execute(
            f"""
            SELECT ri.*, er.run_ref, er.parent_artifact_sha256,
                   er.representation_id, er.producer_name, er.producer_version
            FROM review_item ri
            JOIN extraction_run er USING(run_id)
            {where}
            ORDER BY ri.created_at, ri.review_item_id
            {limit_sql}
            """,
            params,
        ).fetchall()
        items = [_row(row) or {} for row in rows]
        return {
            "status": "ok",
            "filters": {"decision": decision, "run_ref": run_ref, "limit": limit},
            "count": len(items),
            "review_items": items,
        }
    finally:
        db.close()


def decide_review(
    review_ref: str,
    *,
    decision: str,
    decided_by: str,
    notes: str | None = None,
    details: Mapping[str, Any] | None = None,
    review_db: str | Path = DEFAULT_REVIEW_DB,
) -> dict[str, Any]:
    normalized_ref = _required_text(review_ref, "review_ref")
    normalized_decision = _required_text(decision, "decision")
    normalized_by = _required_text(decided_by, "decided_by")
    if details is not None and not isinstance(details, Mapping):
        raise ExtractionError("details must be a JSON object")
    db = _connect_review_db(review_db)
    try:
        item = db.execute(
            "SELECT * FROM review_item WHERE review_ref=?", (normalized_ref,)
        ).fetchone()
        if item is None:
            raise ExtractionError(f"review item not found: {normalized_ref}")
        now = utc_now_iso()
        with db:
            cursor = db.execute(
                """
                INSERT INTO review_event(
                    event_ref, review_item_id, decision, decided_by, notes,
                    details_json, decided_at, supersedes_event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"PRREVIEW-EVENT:{uuid.uuid4()}",
                    item["review_item_id"],
                    normalized_decision,
                    normalized_by,
                    notes,
                    canonical_json(dict(details or {})),
                    now,
                    item["current_event_id"],
                ),
            )
            db.execute(
                """
                UPDATE review_item
                SET current_decision=?, current_event_id=?, updated_at=?
                WHERE review_item_id=?
                """,
                (
                    normalized_decision,
                    cursor.lastrowid,
                    now,
                    item["review_item_id"],
                ),
            )
        current = _row(
            db.execute(
                "SELECT * FROM review_item WHERE review_item_id=?",
                (item["review_item_id"],),
            ).fetchone()
        )
        event = _row(
            db.execute(
                "SELECT * FROM review_event WHERE review_event_id=?",
                (cursor.lastrowid,),
            ).fetchone()
        )
        return {"status": "ok", "review_item": current, "event": event}
    finally:
        db.close()


def review_history(
    review_ref: str, *, review_db: str | Path = DEFAULT_REVIEW_DB
) -> dict[str, Any]:
    db = _connect_review_db(review_db)
    try:
        item = db.execute(
            "SELECT * FROM review_item WHERE review_ref=?", (review_ref,)
        ).fetchone()
        if item is None:
            raise ExtractionError(f"review item not found: {review_ref}")
        events = [
            _row(row) or {}
            for row in db.execute(
                """
                SELECT * FROM review_event
                WHERE review_item_id=? ORDER BY review_event_id
                """,
                (item["review_item_id"],),
            )
        ]
        return {"status": "ok", "review_item": _row(item), "events": events}
    finally:
        db.close()


def _parse_json_object(value: str | None, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    raw = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"{field} is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ExtractionError(f"{field} must be a JSON object")
    return parsed


def _add_storage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--artifact-db", default=str(DEFAULT_ARTIFACT_DB))
    parser.add_argument("--artifact-store", default=str(DEFAULT_ARTIFACT_STORE))
    parser.add_argument("--review-db", default=str(DEFAULT_REVIEW_DB))
    add_output_args(parser)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate extracted public-record fields and manage review work"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("input")
    validate.add_argument("--review-below", type=float)
    _add_storage_args(validate)

    ingest = commands.add_parser("ingest")
    ingest.add_argument("input")
    ingest.add_argument("--review-below", type=float)
    _add_storage_args(ingest)

    queue = commands.add_parser("queue")
    queue.add_argument("--decision", default="pending")
    queue.add_argument("--all-decisions", action="store_true")
    queue.add_argument("--run-ref")
    queue.add_argument("--limit", type=int)
    _add_storage_args(queue)

    decide = commands.add_parser("decide")
    decide.add_argument("review_ref")
    decide.add_argument("--decision", required=True)
    decide.add_argument("--by", required=True)
    decide.add_argument("--notes")
    decide.add_argument("--details-json")
    _add_storage_args(decide)

    history = commands.add_parser("history")
    history.add_argument("review_ref")
    _add_storage_args(history)
    return parser


def _emit(result: Any, args: argparse.Namespace, summary: str) -> None:
    if write_output(result, args, summary=summary):
        return
    print(json.dumps(result, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command in {"validate", "ingest"}:
            payload = _read_json(args.input)
            if args.command == "validate":
                result = validate_extraction(
                    payload,
                    artifact_db=args.artifact_db,
                    artifact_store=args.artifact_store,
                    review_below=args.review_below,
                )
            else:
                result = ingest_extraction(
                    payload,
                    artifact_db=args.artifact_db,
                    artifact_store=args.artifact_store,
                    review_db=args.review_db,
                    review_below=args.review_below,
                )
        elif args.command == "queue":
            result = list_review_queue(
                review_db=args.review_db,
                decision=None if args.all_decisions else args.decision,
                run_ref=args.run_ref,
                limit=args.limit,
            )
        elif args.command == "decide":
            result = decide_review(
                args.review_ref,
                decision=args.decision,
                decided_by=args.by,
                notes=args.notes,
                details=_parse_json_object(args.details_json, "details_json"),
                review_db=args.review_db,
            )
        else:
            result = review_history(
                args.review_ref, review_db=args.review_db
            )
        _emit(result, args, f"public-record extraction {args.command}")
        return 0
    except (ExtractionError, ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
