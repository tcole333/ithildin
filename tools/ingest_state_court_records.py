#!/usr/bin/env python3
"""Ingest canonical state/local court result envelopes into the court sidecar.

Every valid public-record result envelope becomes an immutable
``source_snapshot``. Successful and partial envelopes may additionally project
canonical case records into the normalized court tables. Access states and
restriction events are copied as source observations; this module does not
make source-access decisions.

Usage:
    uv run python tools/ingest_state_court_records.py ingest result.json
    uv run python tools/ingest_state_court_records.py ingest result.json \
        --court-db /tmp/state_courts.db --output /tmp/ingest-report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        RESULT_SCHEMA_VERSION,
        ResultStatus,
        canonical_json,
    )
    from tools.public_records_store import (
        DEFAULT_COURT_DB,
        canonical_access_state,
        canonical_assertion_kind,
        canonical_court_ref,
        canonical_restriction_event,
        connect_courts,
        court_case_identity_key,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import (
        RESULT_SCHEMA_VERSION,
        ResultStatus,
        canonical_json,
    )
    from public_records_store import (
        DEFAULT_COURT_DB,
        canonical_access_state,
        canonical_assertion_kind,
        canonical_court_ref,
        canonical_restriction_event,
        connect_courts,
        court_case_identity_key,
    )


PROJECTABLE_STATUSES = frozenset(
    {
        ResultStatus.OK.value,
        ResultStatus.PARTIAL.value,
    }
)
SNAPSHOT_STATUSES = frozenset(status.value for status in ResultStatus)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OHIO_REPORTER_SINGLE_CASE_NUMBER_RE = re.compile(
    r"^[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*$"
)
_NEW_MEXICO_CASE_NUMBER_RE = re.compile(
    r"^(?P<court_type>[A-Z])-(?P<court_location>\d{1,4})-"
    r"(?P<case_category>[A-Z0-9]{1,2})-(?P<case_number>\d{1,10})$"
)
_CONNECTICUT_DOCKET_RE = re.compile(
    r"^(?P<location>[A-Z0-9]{3})-(?P<category>[A-Z]{2})-"
    r"(?P<year>\d{2})-(?P<number>\d{7})-(?P<suffix>[A-Z])$"
)
DOCKET_HEARING_COLUMNS = (
    "event_type",
    "event_time",
    "judge",
    "location",
    "status",
)
EUGENE_MUNICIPAL_SOURCE_ID = "us-or-eugene-municipal-record-search"
FLORIDA_ACIS_SOURCE_ID = "us-fl-acis"
FLORIDA_NINTH_OPINIONS_SOURCE_ID = (
    "us-fl-ninth-circuit-appellate-opinions-archive"
)
OSCEOLA_BENCHMARK_SOURCE_ID = "us-fl-osceola-benchmark-courts"
OSCEOLA_REPORT_SOURCE_IDS = frozenset(
    {
        "us-fl-osceola-court-hearing-calendar",
        "us-fl-osceola-mortgage-foreclosure-schedule",
    }
)
FLORIDA_COURT_DIRECTORY_DATA_SOURCE_IDS = frozenset(
    {
        "us-fl-state-court-location-directory",
        "us-fl-virtual-courtroom-directory",
        "us-fl-osca-public-records-request",
        "us-fl-trial-court-statistical-reference-guide",
    }
)
DC_APPELLATE_CASES_SOURCE_ID = "us-dc-court-of-appeals-case-search"
DC_COURT_DIRECTORY_SOURCE_IDS = frozenset(
    {
        "us-dc-superior-court-judicial-directory",
        "us-dc-court-of-appeals-judicial-directory",
    }
)
DC_OPINIONS_SOURCE_ID = "us-dc-court-of-appeals-opinions-mojs"
DC_CALENDAR_HEARING_SOURCE_IDS = frozenset(
    {
        "us-dc-superior-court-today-calendar",
        "us-dc-superior-court-criminal-calendar",
    }
)
EDVA_BANKRUPTCY_SOURCE_ID = "us-va-ed-bankruptcy-pacer-recap"
FRESNO_CALENDAR_SOURCE_ID = "us-ca-fresno-superior-court-daily-calendar"
FRESNO_RULINGS_SOURCE_ID = "us-ca-fresno-superior-court-tentative-rulings"
FRESNO_PROBATE_SOURCE_ID = "us-ca-fresno-superior-court-probate-examiner-notes"
CALIFORNIA_COURT_DIRECTORY_SOURCE_ID = "us-ca-superior-court-directory"
CALIFORNIA_OPINIONS_SOURCE_ID = "us-ca-judicial-branch-opinions"
GEORGIA_COURT_DIRECTORY_SOURCE_ID = (
    "us-ga-aoc-court-personnel-directory"
)
GEORGIA_COURT_ACCESS_SOURCE_IDS = frozenset(
    {
        "us-ga-aoc-eaccess-court-records-directory",
        "us-ga-aoc-efile-court-records-directory",
    }
)
GEORGIA_AGGREGATE_COURT_DATA_SOURCE_IDS = frozenset(
    {
        "us-ga-aoc-caseload-dashboards",
        "us-ga-superior-court-workload-assessments",
    }
)
GEORGIA_SUPREME_DOCKET_SOURCE_ID = "us-ga-supreme-court-public-docket"
GEORGIA_SUPREME_PUBLICATION_SOURCE_IDS = frozenset(
    {
        "us-ga-supreme-court-opinions",
        "us-ga-supreme-court-certiorari-grants",
        "us-ga-supreme-court-certiorari-denials",
        "us-ga-supreme-court-application-grant-orders",
    }
)
SAN_DIEGO_COURT_INDEX_SOURCE_ID = "us-ca-san-diego-superior-court-index"
SANTA_CLARA_SOURCE_IDS = frozenset(
    {
        "us-ca-santa-clara-court-publications",
        "us-ca-santa-clara-tentative-rulings",
        "us-ca-santa-clara-civil-case-index-product",
        "us-ca-santa-clara-criminal-case-index-product",
        "us-ca-santa-clara-public-case-portal",
    }
)
FRESNO_CASE_RECORD_SOURCE_IDS = frozenset(
    {
        FRESNO_CALENDAR_SOURCE_ID,
        FRESNO_RULINGS_SOURCE_ID,
        FRESNO_PROBATE_SOURCE_ID,
    }
)
ORANGE_CALENDAR_SOURCE_ID = "us-ca-orange-superior-court-calendar"
ORANGE_RULING_SOURCE_IDS = frozenset(
    {
        "us-ca-orange-superior-court-civil-tentative-rulings",
        "us-ca-orange-superior-court-family-tentative-rulings",
        "us-ca-orange-superior-court-probate-tentative-rulings",
    }
)
ORANGE_CASE_RECORD_SOURCE_IDS = frozenset(
    {ORANGE_CALENDAR_SOURCE_ID, *ORANGE_RULING_SOURCE_IDS}
)
RIVERSIDE_CALENDAR_SOURCE_ID = "us-ca-riverside-superior-court-ecalendar"
RIVERSIDE_RULING_SOURCE_ID = "us-ca-riverside-superior-court-tentative-rulings"
RIVERSIDE_CASE_RECORD_SOURCE_IDS = frozenset(
    {RIVERSIDE_CALENDAR_SOURCE_ID, RIVERSIDE_RULING_SOURCE_ID}
)
LOS_ANGELES_NAME_INDEX_SOURCE_ID = "us-ca-los-angeles-superior-civil-name-index"
QLD_ECOURTS_SOURCE_ID = "au-qld-ecourts-civil"
MARYLAND_ESTATE_SOURCE_ID = "us-md-estate-search"
MARYLAND_ESTATE_NOTICE_SOURCE_ID = "us-md-estate-legal-notices"
MARYLAND_ESTATE_CLAIM_SOURCE_ID = "us-md-estate-claims"
MARYLAND_ESTATE_SUPPLEMENT_SOURCE_IDS = frozenset(
    {
        MARYLAND_ESTATE_NOTICE_SOURCE_ID,
        MARYLAND_ESTATE_CLAIM_SOURCE_ID,
    }
)
MARYLAND_BUSINESS_OPINIONS_SOURCE_ID = "us-md-business-technology-opinions"
MARYLAND_JUDGMENT_LIENS_SOURCE_ID = "us-md-judgment-liens"
MARYLAND_OPINIONS_SOURCE_ID = "us-md-appellate-opinions"
MARYLAND_PUBLIC_CASES_SOURCE_ID = "us-md-mdec-public-cases"
NEW_JERSEY_TAX_COURT_SOURCE_ID = "us-nj-tax-court-property-cases"
NEW_JERSEY_TAX_COURT_OPINIONS_SOURCE_ID = "us-nj-tax-court-opinions"
WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID = "us-wa-appellate-opinions"
VA_GENERAL_DISTRICT_SOURCE_ID = "us-va-general-district-court-case-information"
MARYLAND_ESTATE_COUNTY_GEOIDS = {
    "Allegany County": "24001",
    "Anne Arundel County": "24003",
    "Baltimore County": "24005",
    "Calvert County": "24009",
    "Caroline County": "24011",
    "Carroll County": "24013",
    "Cecil County": "24015",
    "Charles County": "24017",
    "Dorchester County": "24019",
    "Frederick County": "24021",
    "Garrett County": "24023",
    "Harford County": "24025",
    "Howard County": "24027",
    "Kent County": "24029",
    "Montgomery County": "24031",
    "Prince George's County": "24033",
    "Queen Anne's County": "24035",
    "St. Mary's County": "24037",
    "Somerset County": "24039",
    "Talbot County": "24041",
    "Washington County": "24043",
    "Wicomico County": "24045",
    "Worcester County": "24047",
    "Baltimore City": "24510",
}
MICHIGAN_APPELLATE_SOURCE_ID = "us-mi-appellate-case-opinion-order-search"
MICHIGAN_BUSINESS_COURT_SOURCE_ID = "us-mi-business-court-search"
MICHIGAN_BUSINESS_COURT_COLLECTION_ID = (
    "us-mi-business-court-document-collection"
)
CONNECTICUT_CIVIL_FAMILY_SOURCE_ID = (
    "us-ct-superior-court-civil-family-case-lookup"
)
NEW_MEXICO_CASE_LOOKUP_SOURCE_ID = "us-nm-judiciary-case-lookup"
TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID = (
    "us-tx-supreme-orders-opinions"
)
TEXAS_TAMES_SOURCE_ID = "us-tx-appellate-tames"
FRANKLIN_CIO_SOURCE_ID = "us-oh-franklin-common-pleas-cio"
FRANKLIN_MUNICIPAL_SOURCE_ID = "us-oh-franklin-municipal-court-records"
FRANKLIN_PROBATE_SOURCE_ID = "us-oh-franklin-probate-netdata"
DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID = (
    "us-oh-delaware-common-pleas-courtview"
)
LICKING_COMMON_PLEAS_SOURCE_ID = "us-oh-licking-common-pleas-remote-records"
OHIO_REPORTER_DECISIONS_SOURCE_ID = "us-oh-reporter-of-decisions"
OHIO_SUPREME_COURT_SOURCE_ID = "us-oh-supreme-court-public-docket"
WISCONSIN_COURT_DIRECTORY_SOURCE_ID = "us-wi-court-directory"
WISCONSIN_WSCCA_SOURCE_ID = "us-wi-wscca-public"
WISCONSIN_OPINIONS_SOURCE_ID = "us-wi-court-opinions"
OREGON_TYLER_MUNICIPAL_SOURCE_IDS = frozenset(
    {
        "us-or-clackamas-county-justice-record-search",
        "us-or-corvallis-municipal-record-search",
        EUGENE_MUNICIPAL_SOURCE_ID,
        "us-tribal-grand-ronde-record-search",
        "us-or-hermiston-municipal-record-search",
        "us-or-linn-county-justice-record-search",
        "us-or-medford-municipal-record-search",
        "us-or-springfield-municipal-record-search",
    }
)
OJCIN_DELIVERY_RECEIPT_SCHEMA_VERSION = "oregon-ojcin-delivery-receipt/1.0"


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None


def _integer(value: Any, field_name: str, *, nullable: bool = True) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error


def _float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric") from error


def _boolean_int(value: Any, field_name: str, *, nullable: bool = False) -> int | None:
    if value is None:
        return None if nullable else 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in {0, 1}:
        return value
    raise ValueError(f"{field_name} must be boolean")


def _sha256(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = _required_text(value, field_name).lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")
    return normalized


def _access_state(value: Any, field_name: str) -> tuple[str, str]:
    native_label = _required_text(value, field_name)
    return canonical_access_state(native_label), native_label


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _sequence(value: Any, field_name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    return value


def _json(value: Any) -> str:
    return canonical_json(value)


def _ensure_docket_hearing_columns(db: sqlite3.Connection) -> None:
    """Add nullable source-published hearing fields to older sidecars."""

    existing = {
        str(row["name"]) for row in db.execute("PRAGMA table_info(docket_entry)")
    }
    for column in DOCKET_HEARING_COLUMNS:
        if column not in existing:
            db.execute(f'ALTER TABLE docket_entry ADD COLUMN "{column}" TEXT')
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_docket_calendar_event
        ON docket_entry(event_type, event_date, event_time)
        """
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_metadata(
    envelope: Mapping[str, Any],
    *,
    artifact_path: str | Path | None,
    artifact_sha256: str | None,
) -> tuple[str | None, str | None]:
    path_value: str | None
    if artifact_path is not None:
        path_value = str(Path(artifact_path).expanduser())
    else:
        path_value = _optional_text(envelope.get("raw_artifact_path"))
        if path_value is None:
            refs = envelope.get("raw_artifact_refs")
            if isinstance(refs, list) and refs and isinstance(refs[0], str):
                path_value = refs[0]

    expected_sha = _sha256(
        artifact_sha256 or envelope.get("raw_artifact_sha256"),
        "raw_artifact_sha256",
    )
    if path_value is None:
        return None, expected_sha

    candidate = Path(path_value).expanduser()
    if candidate.is_file():
        resolved = candidate.resolve()
        actual_sha = _file_sha256(resolved)
        if expected_sha is not None and actual_sha != expected_sha:
            raise ValueError("raw artifact SHA-256 does not match the artifact file")
        return str(resolved), actual_sha
    return path_value, expected_sha


def validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the shared result envelope and return its core lineage."""
    if not isinstance(envelope, Mapping):
        raise ValueError("result envelope must be an object")
    schema_version = _required_text(
        envelope.get("schema_version"),
        "schema_version",
    )
    if schema_version != RESULT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported result schema {schema_version}; "
            f"expected {RESULT_SCHEMA_VERSION}"
        )
    status = _required_text(envelope.get("status"), "status")
    if status not in SNAPSHOT_STATUSES:
        raise ValueError(f"unsupported result status: {status}")
    retrieved_at = _required_text(envelope.get("retrieved_at"), "retrieved_at")
    query = _mapping(envelope.get("query"), "query")
    source = _mapping(query.get("source"), "query.source")
    source_id = _required_text(source.get("source_id"), "query.source.source_id")
    query_fingerprint = _required_text(
        query.get("fingerprint"),
        "query.fingerprint",
    )
    records = _sequence(envelope.get("records"), "records")
    if status == ResultStatus.OK.value and not records:
        raise ValueError("ok envelopes must contain at least one record")
    if status == ResultStatus.NO_RESULTS.value and records:
        raise ValueError("no_results envelopes cannot contain records")
    if status not in PROJECTABLE_STATUSES and records:
        raise ValueError(f"{status} envelopes cannot contain projectable records")
    warnings = _sequence(envelope.get("warnings"), "warnings")
    errors = _sequence(envelope.get("errors"), "errors")
    return {
        "schema_version": schema_version,
        "status": status,
        "retrieved_at": retrieved_at,
        "query": query,
        "source": source,
        "source_id": source_id,
        "query_fingerprint": query_fingerprint,
        "records": records,
        "warnings": warnings,
        "errors": errors,
    }


def _schema_fingerprint(
    envelope: Mapping[str, Any],
    records: Sequence[Any],
) -> str | None:
    direct = _sha256(envelope.get("schema_fingerprint"), "schema_fingerprint")
    if direct:
        return direct
    observed: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            continue
        value = record.get("schema_fingerprint")
        if isinstance(value, str) and _SHA256_RE.fullmatch(value.lower()):
            observed.add(value.lower())
    return next(iter(observed)) if len(observed) == 1 else None


def _coverage(
    lineage: Mapping[str, Any], envelope: Mapping[str, Any]
) -> dict[str, Any]:
    query = lineage["query"]
    query_metadata = query.get("query")
    return {
        "jurisdiction": query.get("jurisdiction"),
        "operation": (
            query_metadata.get("operation")
            if isinstance(query_metadata, Mapping)
            else None
        ),
        "parameters": (
            query_metadata.get("parameters")
            if isinstance(query_metadata, Mapping)
            else None
        ),
        "requested_limit": (
            query_metadata.get("requested_limit")
            if isinstance(query_metadata, Mapping)
            else None
        ),
        "cursor": (
            query_metadata.get("cursor")
            if isinstance(query_metadata, Mapping)
            else None
        ),
        "record_count": len(lineage["records"]),
        "next_cursor": envelope.get("next_cursor"),
    }


def _insert_snapshot(
    db: sqlite3.Connection,
    envelope: Mapping[str, Any],
    lineage: Mapping[str, Any],
    *,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> int:
    source_url = _optional_text(lineage["source"].get("base_url"))
    cursor = db.execute(
        """
        INSERT INTO source_snapshot(
            source_id, query_fingerprint, source_url, retrieved_at,
            access_status, coverage_json, schema_fingerprint,
            raw_artifact_sha256, raw_artifact_path, raw_json, warning_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lineage["source_id"],
            lineage["query_fingerprint"],
            source_url,
            lineage["retrieved_at"],
            lineage["status"],
            _json(_coverage(lineage, envelope)),
            _schema_fingerprint(envelope, lineage["records"]),
            raw_artifact_sha256,
            raw_artifact_path,
            _json(envelope),
            _json(lineage["warnings"]),
        ),
    )
    return int(cursor.lastrowid)


def _upsert_court(
    db: sqlite3.Connection,
    source_id: str,
    court_data: Mapping[str, Any],
) -> str:
    parent = court_data.get("parent")
    parent_court_id = _optional_text(court_data.get("parent_court_id"))
    if parent is not None:
        parent_mapping = _mapping(parent, "court.parent")
        nested_parent_id = _upsert_court(db, source_id, parent_mapping)
        if parent_court_id is not None and parent_court_id != nested_parent_id:
            raise ValueError("court parent identifiers disagree")
        parent_court_id = nested_parent_id

    court_id = _required_text(court_data.get("court_id"), "court.court_id")
    native_court_id = _required_text(
        court_data.get("native_court_id"),
        "court.native_court_id",
    )
    db.execute(
        """
        INSERT INTO court(
            court_id, source_id, native_court_id, name, state_code,
            county_geoid, court_level, division, branch, parent_court_id,
            official_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(court_id) DO UPDATE SET
            source_id=excluded.source_id,
            native_court_id=excluded.native_court_id,
            name=excluded.name,
            state_code=excluded.state_code,
            county_geoid=excluded.county_geoid,
            court_level=excluded.court_level,
            division=excluded.division,
            branch=excluded.branch,
            parent_court_id=excluded.parent_court_id,
            official_url=excluded.official_url
        """,
        (
            court_id,
            source_id,
            native_court_id,
            _required_text(court_data.get("name"), "court.name"),
            _required_text(court_data.get("state_code"), "court.state_code").upper(),
            _optional_text(court_data.get("county_geoid")),
            _optional_text(court_data.get("court_level", court_data.get("level"))),
            _optional_text(court_data.get("division")),
            _optional_text(court_data.get("branch")),
            parent_court_id,
            _optional_text(court_data.get("official_url")),
        ),
    )
    return court_id


def _case_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    nested = record.get("case")
    if not isinstance(nested, Mapping):
        return dict(record)
    payload = dict(nested)
    for key in (
        "parties",
        "attorneys",
        "representations",
        "judicial_assignments",
        "docket_entries",
        "case_events",
        "events",
        "calendar_events",
        "case_relations",
        "documents",
        "claims",
        "restriction_events",
    ):
        if key in record and key not in payload:
            payload[key] = record[key]
    if "native_entry_id" in record:
        payload.setdefault("docket_entries", []).append(
            {
                key: value
                for key, value in record.items()
                if key not in {"case", "canonical_ref"}
            }
        )
    elif "native_document_id" in record:
        payload.setdefault("documents", []).append(
            {
                key: value
                for key, value in record.items()
                if key not in {"case", "canonical_ref", "docket_entry"}
            }
        )
    return payload


def _upsert_case(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    envelope_source_id: str,
    snapshot_id: int,
) -> tuple[int, str, str, str, str]:
    observation_source_id = (
        _optional_text(payload.get("source_id")) or envelope_source_id
    )
    if observation_source_id not in {
        envelope_source_id,
        _optional_text(payload.get("record_identity_source_id")),
    }:
        raise ValueError("case source_id does not match envelope source_id")
    source_id = (
        _optional_text(payload.get("record_identity_source_id"))
        or observation_source_id
    )
    identity_crosswalk_only = bool(payload.get("identity_crosswalk_only"))
    if source_id != envelope_source_id and not identity_crosswalk_only:
        raise ValueError("cross-source case identity requires identity_crosswalk_only")
    court_id = _upsert_court(
        db,
        source_id,
        _mapping(payload.get("court"), "case.court"),
    )
    raw_case_number = _required_text(
        payload.get("raw_case_number", payload.get("case_number")),
        "case.raw_case_number",
    )
    source_internal_id = _optional_text(payload.get("source_internal_id"))
    case_identity_key = court_case_identity_key(
        raw_case_number,
        source_internal_id,
    )
    access_state, native_access_state = _access_state(
        payload.get("access_state"),
        "case.access_state",
    )
    preserve_existing_case_fields = bool(payload.get("preserve_existing_case_fields"))
    if identity_crosswalk_only:
        conflict_action = "DO NOTHING"
    elif preserve_existing_case_fields:
        conflict_action = """
        DO UPDATE SET
            raw_case_number=excluded.raw_case_number,
            display_case_number=COALESCE(
                excluded.display_case_number,
                case_record.display_case_number
            ),
            source_internal_id=COALESCE(
                excluded.source_internal_id,
                case_record.source_internal_id
            ),
            caption=COALESCE(excluded.caption, case_record.caption),
            case_type=COALESCE(excluded.case_type, case_record.case_type),
            filing_date=COALESCE(excluded.filing_date, case_record.filing_date),
            disposition_date=COALESCE(
                excluded.disposition_date,
                case_record.disposition_date
            ),
            status=COALESCE(excluded.status, case_record.status),
            access_state=excluded.access_state,
            native_access_state=excluded.native_access_state,
            certified_record=excluded.certified_record,
            source_url=COALESCE(excluded.source_url, case_record.source_url),
            snapshot_id=excluded.snapshot_id,
            raw_json=COALESCE(case_record.raw_json, excluded.raw_json)
        """
    else:
        conflict_action = """
        DO UPDATE SET
            raw_case_number=excluded.raw_case_number,
            display_case_number=excluded.display_case_number,
            source_internal_id=excluded.source_internal_id,
            caption=excluded.caption,
            case_type=excluded.case_type,
            filing_date=excluded.filing_date,
            disposition_date=excluded.disposition_date,
            status=excluded.status,
            access_state=excluded.access_state,
            native_access_state=excluded.native_access_state,
            certified_record=excluded.certified_record,
            source_url=excluded.source_url,
            snapshot_id=excluded.snapshot_id,
            raw_json=excluded.raw_json
        """
    db.execute(
        f"""
        INSERT INTO case_record(
            source_id, court_id, raw_case_number, display_case_number,
            source_internal_id, caption, case_type, filing_date,
            disposition_date, status, access_state, native_access_state,
            certified_record,
            source_url, snapshot_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, court_id, case_identity_key) {conflict_action}
        """,
        (
            source_id,
            court_id,
            raw_case_number,
            _optional_text(payload.get("display_case_number")),
            source_internal_id,
            _optional_text(payload.get("caption")),
            _optional_text(payload.get("case_type")),
            _optional_text(payload.get("filing_date")),
            _optional_text(payload.get("disposition_date")),
            _optional_text(payload.get("status")),
            access_state,
            native_access_state,
            _boolean_int(payload.get("certified_record"), "case.certified_record"),
            _optional_text(payload.get("source_url")),
            snapshot_id,
            _json(payload),
        ),
    )
    row = db.execute(
        """
        SELECT case_id FROM case_record
        WHERE source_id=? AND court_id=? AND case_identity_key=?
        """,
        (source_id, court_id, case_identity_key),
    ).fetchone()
    assert row is not None
    return (
        int(row["case_id"]),
        source_id,
        court_id,
        access_state,
        native_access_state,
    )


def _upsert_party(
    db: sqlite3.Connection,
    case_id: int,
    party: Mapping[str, Any],
    *,
    sequence_no: int,
    case_access_state: str,
    case_native_access_state: str,
) -> int:
    role = _required_text(party.get("role"), "party.role")
    raw_name = _required_text(
        party.get("raw_name", party.get("name")), "party.raw_name"
    )
    if "access_state" in party:
        access_state, native_access_state = _access_state(
            party.get("access_state"),
            "party.access_state",
        )
    else:
        access_state = case_access_state
        native_access_state = case_native_access_state
    db.execute(
        """
        INSERT INTO case_party(
            case_id, sequence_no, role, raw_name, normalized_name, entity_kind,
            core_entity_id, resolution_confidence, resolution_status,
            access_state, native_access_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id, sequence_no, role, raw_name) DO UPDATE SET
            normalized_name=excluded.normalized_name,
            entity_kind=excluded.entity_kind,
            core_entity_id=excluded.core_entity_id,
            resolution_confidence=excluded.resolution_confidence,
            resolution_status=excluded.resolution_status,
            access_state=excluded.access_state,
            native_access_state=excluded.native_access_state
        """,
        (
            case_id,
            sequence_no,
            role,
            raw_name,
            _optional_text(party.get("normalized_name")),
            _optional_text(party.get("entity_kind")),
            _integer(party.get("core_entity_id"), "party.core_entity_id"),
            _float(
                party.get("resolution_confidence"),
                "party.resolution_confidence",
            ),
            _optional_text(party.get("resolution_status")) or "unreviewed",
            access_state,
            native_access_state,
        ),
    )
    row = db.execute(
        """
        SELECT case_party_id FROM case_party
        WHERE case_id=? AND sequence_no=? AND role=? AND raw_name=?
        """,
        (case_id, sequence_no, role, raw_name),
    ).fetchone()
    assert row is not None
    return int(row["case_party_id"])


def _upsert_attorney(
    db: sqlite3.Connection,
    source_id: str,
    attorney: Mapping[str, Any],
) -> int:
    raw_name = _required_text(
        attorney.get("raw_name", attorney.get("name")),
        "attorney.raw_name",
    )
    bar_id = _optional_text(attorney.get("bar_id")) or ""
    db.execute(
        """
        INSERT INTO attorney(
            source_id, raw_name, normalized_name, bar_id, firm_name
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id, raw_name, bar_id) DO UPDATE SET
            normalized_name=excluded.normalized_name,
            firm_name=excluded.firm_name
        """,
        (
            source_id,
            raw_name,
            _optional_text(attorney.get("normalized_name")),
            bar_id,
            _optional_text(attorney.get("firm_name")),
        ),
    )
    row = db.execute(
        """
        SELECT attorney_id FROM attorney
        WHERE source_id=? AND raw_name=? AND bar_id=?
        """,
        (source_id, raw_name, bar_id),
    ).fetchone()
    assert row is not None
    return int(row["attorney_id"])


def _upsert_representation(
    db: sqlite3.Connection,
    *,
    case_id: int,
    case_party_id: int,
    attorney_id: int,
    representation: Mapping[str, Any],
) -> None:
    effective_from = _optional_text(representation.get("effective_from")) or ""
    db.execute(
        """
        INSERT INTO case_representation(
            case_id, case_party_id, attorney_id, effective_from,
            effective_to, source_entry_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id, attorney_id, case_party_id, effective_from)
        DO UPDATE SET
            effective_to=excluded.effective_to,
            source_entry_id=excluded.source_entry_id
        """,
        (
            case_id,
            case_party_id,
            attorney_id,
            effective_from,
            _optional_text(representation.get("effective_to")),
            _optional_text(representation.get("source_entry_id")),
        ),
    )


def _party_reference(
    representation: Mapping[str, Any],
    parties: Sequence[dict[str, Any]],
) -> int | None:
    reference = representation.get("party")
    reference_mapping = reference if isinstance(reference, Mapping) else representation
    index = _integer(reference_mapping.get("party_index"), "party_index")
    if index is not None:
        if index < 0 or index >= len(parties):
            raise ValueError("representation party_index is out of range")
        return int(parties[index]["case_party_id"])
    sequence_no = _integer(
        reference_mapping.get(
            "party_sequence_no",
            reference_mapping.get("party_sequence"),
        ),
        "party_sequence_no",
    )
    raw_name = _optional_text(
        reference_mapping.get(
            "party_raw_name",
            reference_mapping.get("represented_party_name"),
        )
    )
    role = _optional_text(reference_mapping.get("party_role"))
    if sequence_no is None and raw_name is None and role is None:
        return None
    matches = [
        item
        for item in parties
        if (sequence_no is None or item["sequence_no"] == sequence_no)
        and (raw_name is None or item["raw_name"] == raw_name)
        and (role is None or item["role"] == role)
    ]
    if len(matches) == 1:
        return int(matches[0]["case_party_id"])
    if len(matches) > 1:
        raise ValueError("representation party reference is ambiguous")
    return None


def _project_parties_and_attorneys(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    case_access_state: str,
    case_native_access_state: str,
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    party_rows: list[dict[str, Any]] = []
    for index, value in enumerate(_sequence(payload.get("parties"), "case.parties")):
        party = _mapping(value, f"case.parties[{index}]")
        sequence_no = _integer(
            party.get("sequence_no", party.get("sequence", index + 1)),
            f"case.parties[{index}].sequence_no",
            nullable=False,
        )
        assert sequence_no is not None
        party_id = _upsert_party(
            db,
            case_id,
            party,
            sequence_no=sequence_no,
            case_access_state=case_access_state,
            case_native_access_state=case_native_access_state,
        )
        party_rows.append(
            {
                "case_party_id": party_id,
                "sequence_no": sequence_no,
                "role": _required_text(party.get("role"), "party.role"),
                "raw_name": _required_text(
                    party.get("raw_name", party.get("name")),
                    "party.raw_name",
                ),
            }
        )
        counts["parties"] += 1
        for attorney_index, attorney_value in enumerate(
            _sequence(
                party.get("attorneys"),
                f"case.parties[{index}].attorneys",
            )
        ):
            representation = _mapping(
                attorney_value,
                f"case.parties[{index}].attorneys[{attorney_index}]",
            )
            attorney_data = representation.get("attorney")
            attorney = (
                _mapping(attorney_data, "representation.attorney")
                if attorney_data is not None
                else representation
            )
            attorney_id = _upsert_attorney(db, source_id, attorney)
            _upsert_representation(
                db,
                case_id=case_id,
                case_party_id=party_id,
                attorney_id=attorney_id,
                representation=representation,
            )
            counts["attorneys"] += 1
            counts["representations"] += 1

    representation_values = list(
        _sequence(payload.get("representations"), "case.representations")
    )
    representation_values.extend(_sequence(payload.get("attorneys"), "case.attorneys"))
    for index, value in enumerate(representation_values):
        representation = _mapping(value, f"case.representations[{index}]")
        attorney_data = representation.get("attorney")
        attorney = (
            _mapping(attorney_data, "representation.attorney")
            if attorney_data is not None
            else representation
        )
        attorney_id = _upsert_attorney(db, source_id, attorney)
        counts["attorneys"] += 1
        party_id = _party_reference(representation, party_rows)
        if party_id is None:
            continue
        _upsert_representation(
            db,
            case_id=case_id,
            case_party_id=party_id,
            attorney_id=attorney_id,
            representation=representation,
        )
        counts["representations"] += 1
    return party_rows


def _project_assignments(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    counts: dict[str, int],
) -> None:
    values = _sequence(
        payload.get("judicial_assignments"),
        "case.judicial_assignments",
    )
    for index, value in enumerate(values):
        assignment = _mapping(value, f"case.judicial_assignments[{index}]")
        officer_data = assignment.get("officer")
        officer = (
            _mapping(officer_data, "judicial_assignment.officer")
            if officer_data is not None
            else assignment
        )
        raw_name = _required_text(
            officer.get("raw_name", officer.get("name")),
            "judicial_officer.raw_name",
        )
        native_officer_id = _optional_text(officer.get("native_officer_id")) or ""
        db.execute(
            """
            INSERT INTO judicial_officer(
                source_id, raw_name, normalized_name, native_officer_id
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(source_id, raw_name, native_officer_id) DO UPDATE SET
                normalized_name=excluded.normalized_name
            """,
            (
                source_id,
                raw_name,
                _optional_text(officer.get("normalized_name")),
                native_officer_id,
            ),
        )
        row = db.execute(
            """
            SELECT judicial_officer_id FROM judicial_officer
            WHERE source_id=? AND raw_name=? AND native_officer_id=?
            """,
            (source_id, raw_name, native_officer_id),
        ).fetchone()
        assert row is not None
        officer_id = int(row["judicial_officer_id"])
        role = _required_text(
            assignment.get("assignment_role", assignment.get("role")),
            "judicial_assignment.assignment_role",
        )
        effective_from = _optional_text(assignment.get("effective_from")) or ""
        db.execute(
            """
            INSERT INTO case_assignment(
                case_id, judicial_officer_id, assignment_role,
                effective_from, effective_to
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(
                case_id, judicial_officer_id, assignment_role, effective_from
            ) DO UPDATE SET effective_to=excluded.effective_to
            """,
            (
                case_id,
                officer_id,
                role,
                effective_from,
                _optional_text(assignment.get("effective_to")),
            ),
        )
        counts["judicial_officers"] += 1
        counts["assignments"] += 1


def _project_case_relations(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    snapshot_id: int,
    counts: dict[str, int],
) -> None:
    """Project relation-ready case references while retaining their raw form.

    An appellate source can identify an originating trial or lower-appellate
    case even when that court's own portal is not integrated. Store the source
    assertion as a limited related-case row, retain any explicitly linked
    representation on that row, and preserve the source-native relation type.
    """

    parent_court = _mapping(payload.get("court"), "case.court")
    state_code = _required_text(
        parent_court.get("state_code"),
        "case.court.state_code",
    ).upper()
    values = _sequence(
        payload.get("case_relations"),
        "case.case_relations",
    )
    for index, value in enumerate(values):
        relation = _mapping(value, f"case.case_relations[{index}]")
        relation_kind = _optional_text(relation.get("relation_type"))
        if relation_kind not in {
            "originating_trial_case",
            "originating_case_or_agency_matter",
            "originating_appellate_case",
        }:
            continue

        raw_case_number = _required_text(
            relation.get("raw_case_number"),
            f"case.case_relations[{index}].raw_case_number",
        )
        county = _optional_text(relation.get("county"))
        is_lower_appellate = relation_kind == "originating_appellate_case"
        court_name = _optional_text(relation.get("court_name")) or (
            f"{state_code} appellate court"
            if is_lower_appellate
            else f"{county} trial court"
            if county
            else f"{state_code} trial court"
        )
        court_level = _optional_text(relation.get("court_level")) or (
            "appellate"
            if is_lower_appellate
            else "originating"
            if relation_kind == "originating_case_or_agency_matter"
            else "trial"
        )
        court_identity = {
            "state_code": state_code,
            "county": county,
            "court_name": court_name,
            "court_level": court_level,
        }
        court_digest = hashlib.sha256(
            _json(court_identity).encode("utf-8")
        ).hexdigest()[:20]
        related_identity = {
            **court_identity,
            "raw_case_number": raw_case_number,
        }
        related_digest = hashlib.sha256(
            _json(related_identity).encode("utf-8")
        ).hexdigest()[:20]
        generated_court_id = (
            f"{state_code.casefold()}-originating-appellate-{court_digest}"
            if is_lower_appellate
            else f"{state_code.casefold()}-originating-trial-{court_digest}"
        )
        generated_native_court_id = (
            f"originating-appellate:{court_digest}"
            if is_lower_appellate
            else f"originating-trial:{court_digest}"
        )
        relation_documents = list(
            _sequence(
                relation.get("documents"),
                f"case.case_relations[{index}].documents",
            )
        )
        related_payload: dict[str, Any] = {
            "source_id": source_id,
            "court": {
                "court_id": (
                    _optional_text(relation.get("court_id"))
                    or generated_court_id
                ),
                "native_court_id": (
                    _optional_text(relation.get("native_court_id"))
                    or generated_native_court_id
                ),
                "name": court_name,
                "state_code": state_code,
                "county_geoid": _optional_text(relation.get("county_geoid")),
                "court_level": court_level,
                "official_url": _optional_text(relation.get("court_url")),
            },
            "raw_case_number": raw_case_number,
            "display_case_number": raw_case_number,
            "source_internal_id": (
                _optional_text(relation.get("source_internal_id"))
                or (
                    f"originating-appellate:{related_digest}"
                    if is_lower_appellate
                    else f"originating-trial:{related_digest}"
                )
            ),
            "caption": (
                _optional_text(relation.get("caption"))
                if is_lower_appellate
                else _optional_text(payload.get("caption"))
            ),
            "access_state": _optional_text(relation.get("access_state")) or "public",
            "native_access_state": _optional_text(
                relation.get("native_access_state")
            ),
            "certified_record": False,
            "source_url": (
                _optional_text(relation.get("source_url"))
                or _optional_text(payload.get("source_url"))
            ),
            "relation_source": {
                **dict(relation),
                "normalized_relation_type": "appealed_to",
            },
            "documents": relation_documents,
        }
        (
            related_case_id,
            _related_source_id,
            _related_court_id,
            related_access_state,
            related_native_access_state,
        ) = _upsert_case(
            db,
            related_payload,
            envelope_source_id=source_id,
            snapshot_id=snapshot_id,
        )
        counts["related_courts"] += 1
        counts["related_cases"] += 1
        if relation_documents:
            _project_docket_and_documents(
                db,
                related_payload,
                case_id=related_case_id,
                source_id=source_id,
                snapshot_id=snapshot_id,
                case_access_state=related_access_state,
                case_native_access_state=related_native_access_state,
                counts=counts,
            )

        judge = _optional_text(relation.get("judge"))
        if judge is not None:
            _project_assignments(
                db,
                {
                    "judicial_assignments": [
                        {
                            "assignment_role": "trial_court_judge",
                            "officer": {"raw_name": judge},
                        }
                    ]
                },
                case_id=related_case_id,
                source_id=source_id,
                counts=counts,
            )

        if related_case_id == case_id:
            continue
        normalized_relation_type = "appealed_to"
        db.execute(
            """
            INSERT INTO case_relation(
                from_case_id, to_case_id, relation_type, source_id,
                evidence_ref
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(from_case_id, to_case_id, relation_type)
            DO UPDATE SET
                source_id=excluded.source_id,
                evidence_ref=excluded.evidence_ref
            """,
            (
                related_case_id,
                case_id,
                normalized_relation_type,
                source_id,
                _optional_text(relation.get("evidence_ref"))
                or _optional_text(relation.get("native_relation_id"))
                or _optional_text(relation.get("source_url")),
            ),
        )
        counts["case_relations"] += 1


def _upsert_docket_entry(
    db: sqlite3.Connection,
    entry: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    snapshot_id: int,
    case_access_state: str,
    case_native_access_state: str,
) -> int:
    native_entry_id = _required_text(
        entry.get("native_entry_id"),
        "docket_entry.native_entry_id",
    )
    if "access_state" in entry:
        access_state, native_access_state = _access_state(
            entry.get("access_state"),
            "docket_entry.access_state",
        )
    else:
        access_state = case_access_state
        native_access_state = case_native_access_state
    db.execute(
        """
        INSERT INTO docket_entry(
            case_id, source_id, native_entry_id, sequence_no, subsequence_no,
            event_code, event_type, raw_text, filed_date, entered_date,
            event_date, event_time, judge, location, status, filer_raw,
            document_available, access_state, native_access_state, snapshot_id,
            raw_json
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(case_id, native_entry_id) DO UPDATE SET
            source_id=excluded.source_id,
            sequence_no=excluded.sequence_no,
            subsequence_no=excluded.subsequence_no,
            event_code=excluded.event_code,
            event_type=excluded.event_type,
            raw_text=excluded.raw_text,
            filed_date=excluded.filed_date,
            entered_date=excluded.entered_date,
            event_date=excluded.event_date,
            event_time=excluded.event_time,
            judge=excluded.judge,
            location=excluded.location,
            status=excluded.status,
            filer_raw=excluded.filer_raw,
            document_available=excluded.document_available,
            access_state=excluded.access_state,
            native_access_state=excluded.native_access_state,
            snapshot_id=excluded.snapshot_id,
            raw_json=excluded.raw_json
        """,
        (
            case_id,
            source_id,
            native_entry_id,
            _optional_text(entry.get("sequence_no", entry.get("sequence"))),
            _optional_text(entry.get("subsequence_no", entry.get("subsequence"))),
            _optional_text(entry.get("event_code")),
            _optional_text(entry.get("event_type")),
            _optional_text(entry.get("raw_text", entry.get("text"))),
            _optional_text(entry.get("filed_date")),
            _optional_text(entry.get("entered_date")),
            _optional_text(entry.get("event_date")),
            _optional_text(entry.get("event_time")),
            _optional_text(entry.get("judge")),
            _optional_text(entry.get("location")),
            _optional_text(entry.get("status")),
            _optional_text(entry.get("filer_raw")),
            _boolean_int(
                entry.get("document_available"),
                "docket_entry.document_available",
                nullable=True,
            ),
            access_state,
            native_access_state,
            snapshot_id,
            _json(entry),
        ),
    )
    row = db.execute(
        """
        SELECT docket_entry_id FROM docket_entry
        WHERE case_id=? AND native_entry_id=?
        """,
        (case_id, native_entry_id),
    ).fetchone()
    assert row is not None
    return int(row["docket_entry_id"])


def _upsert_document(
    db: sqlite3.Connection,
    document: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    case_access_state: str,
    case_native_access_state: str,
    docket_entry_id: int | None,
) -> int:
    native_document_id = _required_text(
        document.get("native_document_id"),
        "document.native_document_id",
    )
    document_sha256 = _sha256(document.get("sha256"), "document.sha256")
    row = db.execute(
        """
        SELECT document_id FROM document_artifact
        WHERE case_id=? AND native_document_id=?
          AND (
              sha256=? OR (sha256 IS NULL AND ? IS NULL)
          )
        ORDER BY document_id LIMIT 1
        """,
        (
            case_id,
            native_document_id,
            document_sha256,
            document_sha256,
        ),
    ).fetchone()
    if "access_state" in document:
        access_state, native_access_state = _access_state(
            document.get("access_state"),
            "document.access_state",
        )
        explicit_native_state = _optional_text(document.get("native_access_state"))
        if explicit_native_state is not None:
            native_access_state = explicit_native_state
    else:
        access_state = case_access_state
        native_access_state = case_native_access_state
    values = (
        docket_entry_id,
        source_id,
        _optional_text(document.get("document_type")),
        _optional_text(document.get("filed_date")),
        _optional_text(document.get("source_url")),
        document_sha256,
        _optional_text(document.get("mime_type")),
        _integer(document.get("page_count"), "document.page_count"),
        _optional_text(document.get("storage_path")),
        _optional_text(document.get("ocr_status")),
        _optional_text(document.get("certification_status")),
        access_state,
        native_access_state,
        _optional_text(document.get("acquired_at")),
    )
    if row is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                case_id, docket_entry_id, source_id, native_document_id,
                document_type, filed_date, source_url, sha256, mime_type,
                page_count, storage_path, ocr_status, certification_status,
                access_state, native_access_state, acquired_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, *values[:2], native_document_id, *values[2:]),
        )
        return int(cursor.lastrowid)
    document_id = int(row["document_id"])
    db.execute(
        """
        UPDATE document_artifact SET
            docket_entry_id=?, source_id=?, document_type=?, filed_date=?,
            source_url=?, sha256=?, mime_type=?, page_count=?, storage_path=?,
            ocr_status=?, certification_status=?, access_state=?,
            native_access_state=?, acquired_at=?
        WHERE document_id=?
        """,
        (*values, document_id),
    )
    return document_id


def _project_docket_and_documents(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    snapshot_id: int,
    case_access_state: str,
    case_native_access_state: str,
    counts: dict[str, int],
) -> dict[str, int]:
    docket_ids: dict[str, int] = {}
    for index, value in enumerate(
        _sequence(payload.get("docket_entries"), "case.docket_entries")
    ):
        entry = _mapping(value, f"case.docket_entries[{index}]")
        entry_id = _upsert_docket_entry(
            db,
            entry,
            case_id=case_id,
            source_id=source_id,
            snapshot_id=snapshot_id,
            case_access_state=case_access_state,
            case_native_access_state=case_native_access_state,
        )
        native_entry_id = _required_text(
            entry.get("native_entry_id"),
            "docket_entry.native_entry_id",
        )
        docket_ids[native_entry_id] = entry_id
        counts["docket_entries"] += 1
        for document_index, document_value in enumerate(
            _sequence(
                entry.get("documents"),
                f"case.docket_entries[{index}].documents",
            )
        ):
            document = _mapping(
                document_value,
                f"case.docket_entries[{index}].documents[{document_index}]",
            )
            _upsert_document(
                db,
                document,
                case_id=case_id,
                source_id=source_id,
                case_access_state=case_access_state,
                case_native_access_state=case_native_access_state,
                docket_entry_id=entry_id,
            )
            counts["documents"] += 1

    for index, value in enumerate(
        _sequence(payload.get("documents"), "case.documents")
    ):
        document = _mapping(value, f"case.documents[{index}]")
        entry_native_id = _optional_text(
            document.get(
                "docket_entry_native_id",
                document.get("native_entry_id"),
            )
        )
        entry_id = None
        if entry_native_id is not None:
            entry_id = docket_ids.get(entry_native_id)
            if entry_id is None:
                row = db.execute(
                    """
                    SELECT docket_entry_id FROM docket_entry
                    WHERE case_id=? AND native_entry_id=?
                    """,
                    (case_id, entry_native_id),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        "document references an unknown docket entry: "
                        f"{entry_native_id}"
                    )
                entry_id = int(row["docket_entry_id"])
        _upsert_document(
            db,
            document,
            case_id=case_id,
            source_id=source_id,
            case_access_state=case_access_state,
            case_native_access_state=case_native_access_state,
            docket_entry_id=entry_id,
        )
        counts["documents"] += 1
    return docket_ids


def _project_events(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    snapshot_id: int,
    docket_ids: Mapping[str, int],
    counts: dict[str, int],
) -> None:
    values = payload.get(
        "case_events",
        payload.get("events", payload.get("calendar_events")),
    )
    for index, value in enumerate(_sequence(values, "case.case_events")):
        event = _mapping(value, f"case.case_events[{index}]")
        event_type = _required_text(event.get("event_type"), "case_event.event_type")
        event_date = _optional_text(event.get("event_date"))
        native_event_id = _optional_text(event.get("native_event_id")) or ""
        assertion_label = _optional_text(event.get("assertion_kind"))
        native_assertion_kind = (
            _optional_text(event.get("native_assertion_kind")) or assertion_label
        )
        assertion_kind = (
            canonical_assertion_kind(assertion_label)
            if assertion_label is not None
            else "docket_metadata"
        )
        source_entry_native_id = _optional_text(
            event.get(
                "source_entry_native_id",
                event.get("docket_entry_native_id"),
            )
        )
        source_entry_id = None
        if source_entry_native_id is not None:
            source_entry_id = docket_ids.get(source_entry_native_id)
            if source_entry_id is None:
                row = db.execute(
                    """
                    SELECT docket_entry_id FROM docket_entry
                    WHERE case_id=? AND native_entry_id=?
                    """,
                    (case_id, source_entry_native_id),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        "case event references an unknown docket entry: "
                        f"{source_entry_native_id}"
                    )
                source_entry_id = int(row["docket_entry_id"])
        row = db.execute(
            """
            SELECT case_event_id FROM case_event
            WHERE case_id=? AND source_id=? AND event_type=?
              AND (event_date=? OR (event_date IS NULL AND ? IS NULL))
              AND native_event_id=?
            ORDER BY case_event_id LIMIT 1
            """,
            (
                case_id,
                source_id,
                event_type,
                event_date,
                event_date,
                native_event_id,
            ),
        ).fetchone()
        update_values = (
            _optional_text(event.get("filed_date")),
            _optional_text(event.get("entered_date")),
            _optional_text(event.get("disposition")),
            assertion_kind,
            native_assertion_kind,
            source_entry_id,
            snapshot_id,
            _json(event),
        )
        if row is None:
            db.execute(
                """
                INSERT INTO case_event(
                    case_id, source_id, native_event_id, event_type,
                    event_date, filed_date, entered_date, disposition,
                    assertion_kind, native_assertion_kind, source_entry_id,
                    snapshot_id, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    source_id,
                    native_event_id,
                    event_type,
                    event_date,
                    *update_values,
                ),
            )
        else:
            db.execute(
                """
                UPDATE case_event SET
                    filed_date=?, entered_date=?, disposition=?,
                    assertion_kind=?, native_assertion_kind=?, source_entry_id=?,
                    snapshot_id=?, raw_json=?
                WHERE case_event_id=?
                """,
                (*update_values, int(row["case_event_id"])),
            )
        counts["case_events"] += 1


def _project_restrictions(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    counts: dict[str, int],
) -> None:
    for index, value in enumerate(
        _sequence(
            payload.get("restriction_events"),
            "case.restriction_events",
        )
    ):
        event = _mapping(value, f"case.restriction_events[{index}]")
        native_event_type = _required_text(
            event.get("event_type"),
            "restriction_event.event_type",
        )
        event_type = canonical_restriction_event(native_event_type)
        effective_at = _required_text(
            event.get("effective_at"),
            "restriction_event.effective_at",
        )
        direction_ref = _optional_text(event.get("direction_ref"))
        row = db.execute(
            """
            SELECT restriction_event_id FROM restriction_event
            WHERE case_id=? AND source_id=? AND event_type=?
              AND native_event_type=? AND effective_at=?
              AND (
                  direction_ref=? OR
                  (direction_ref IS NULL AND ? IS NULL)
              )
            ORDER BY restriction_event_id LIMIT 1
            """,
            (
                case_id,
                source_id,
                event_type,
                native_event_type,
                effective_at,
                direction_ref,
                direction_ref,
            ),
        ).fetchone()
        if row is None:
            db.execute(
                """
                INSERT INTO restriction_event(
                    case_id, source_id, event_type, native_event_type,
                    effective_at, reason, direction_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    source_id,
                    event_type,
                    native_event_type,
                    effective_at,
                    _optional_text(event.get("reason")),
                    direction_ref,
                ),
            )
        else:
            db.execute(
                """
                UPDATE restriction_event SET reason=?
                WHERE restriction_event_id=?
                """,
                (
                    _optional_text(event.get("reason")),
                    int(row["restriction_event_id"]),
                ),
            )
        counts["restriction_events"] += 1


def _claim_native_id(claim: Mapping[str, Any]) -> str:
    for field_name in (
        "native_claim_id",
        "claim_uuid",
        "source_internal_id",
        "source_namespace_id",
    ):
        value = _optional_text(claim.get(field_name))
        if value is not None:
            return value
    raise ValueError(
        "case claim requires native_claim_id, claim_uuid, "
        "source_internal_id, or source_namespace_id"
    )


def _sparse_integer(value: Any, field_name: str) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _integer(value, field_name)


def _claim_access_state(
    claim: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    access_value = _optional_text(claim.get("access_state"))
    native_value = _optional_text(claim.get("native_access_state"))
    if access_value is None and native_value is None:
        return None, None
    basis = access_value or native_value
    assert basis is not None
    return canonical_access_state(basis), native_value or basis


def _project_claims(
    db: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    case_id: int,
    source_id: str,
    snapshot_id: int,
    counts: dict[str, int],
) -> None:
    for index, value in enumerate(_sequence(payload.get("claims"), "case.claims")):
        claim = _mapping(value, f"case.claims[{index}]")
        native_claim_id = _claim_native_id(claim)
        access_state, native_access_state = _claim_access_state(claim)
        amount_value = (
            claim.get("amount_minor")
            if "amount_minor" in claim
            else claim.get("amount")
        )
        claimant_value = (
            claim.get("claimant_raw")
            if "claimant_raw" in claim
            else claim.get("claimant")
        )
        if isinstance(claimant_value, Mapping):
            claimant_value = (
                claimant_value.get("raw_name")
                or claimant_value.get("name")
                or claimant_value.get("display_name")
            )
        db.execute(
            """
            INSERT INTO case_claim(
                case_id, source_id, native_claim_id, sequence_no,
                claim_type, claim_date, claimant_raw, amount_minor,
                currency, status, limited_stub, access_state,
                native_access_state, snapshot_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id, native_claim_id) DO UPDATE SET
                source_id=excluded.source_id,
                sequence_no=excluded.sequence_no,
                claim_type=excluded.claim_type,
                claim_date=excluded.claim_date,
                claimant_raw=excluded.claimant_raw,
                amount_minor=excluded.amount_minor,
                currency=excluded.currency,
                status=excluded.status,
                limited_stub=excluded.limited_stub,
                access_state=excluded.access_state,
                native_access_state=excluded.native_access_state,
                snapshot_id=excluded.snapshot_id,
                raw_json=excluded.raw_json
            """,
            (
                case_id,
                source_id,
                native_claim_id,
                _sparse_integer(
                    claim.get("sequence_no", claim.get("sequence")),
                    "claim.sequence_no",
                ),
                _optional_text(claim.get("claim_type", claim.get("type"))),
                _optional_text(claim.get("claim_date", claim.get("filed_date"))),
                _optional_text(claimant_value),
                _sparse_integer(amount_value, "claim.amount_minor"),
                _optional_text(claim.get("currency")),
                _optional_text(claim.get("status")),
                _boolean_int(
                    claim.get("limited_stub"),
                    "claim.limited_stub",
                    nullable=True,
                ),
                access_state,
                native_access_state,
                snapshot_id,
                _json(claim),
            ),
        )
        counts["claims"] += 1


def _record_case_source_occurrence(
    db: sqlite3.Connection,
    record: Mapping[str, Any],
    *,
    case_id: int,
    record_identity_source_id: str,
    snapshot_id: int,
) -> None:
    """Link a source-native discovery row to its canonical case identity."""

    source_id = _required_text(
        record.get("source_id"),
        "case_source_occurrence.source_id",
    )
    source_result_id = _optional_text(record.get("source_result_id"))
    if source_result_id is None:
        source_result_id = hashlib.sha256(_json(record).encode("utf-8")).hexdigest()
    db.execute(
        """
        INSERT INTO case_source_occurrence(
            case_id, source_id, record_identity_source_id, snapshot_id,
            record_kind, source_internal_id, source_result_id,
            canonical_ref, matched_party_name, case_type, filing_date,
            filing_location, source_url, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, snapshot_id, source_result_id) DO UPDATE SET
            case_id=excluded.case_id,
            record_identity_source_id=excluded.record_identity_source_id,
            record_kind=excluded.record_kind,
            source_internal_id=excluded.source_internal_id,
            canonical_ref=excluded.canonical_ref,
            matched_party_name=excluded.matched_party_name,
            case_type=excluded.case_type,
            filing_date=excluded.filing_date,
            filing_location=excluded.filing_location,
            source_url=excluded.source_url,
            raw_json=excluded.raw_json
        """,
        (
            case_id,
            source_id,
            record_identity_source_id,
            snapshot_id,
            _optional_text(record.get("record_kind")) or "case_source_occurrence",
            _optional_text(record.get("source_internal_id")),
            source_result_id,
            _optional_text(record.get("canonical_ref")),
            _optional_text(record.get("matched_party_name")),
            _optional_text(record.get("case_type")),
            _optional_text(record.get("filing_date")),
            _optional_text(record.get("filing_location")),
            _optional_text(record.get("source_url")),
            _json(record),
        ),
    )


def _project_case(
    db: sqlite3.Connection,
    record: Mapping[str, Any],
    *,
    source_id: str,
    snapshot_id: int,
    counts: dict[str, int],
) -> str:
    payload = _case_payload(record)
    (
        case_id,
        case_source_id,
        court_id,
        case_access_state,
        case_native_access_state,
    ) = _upsert_case(
        db,
        payload,
        envelope_source_id=source_id,
        snapshot_id=snapshot_id,
    )
    counts["courts"] += 1
    counts["cases"] += 1
    if payload.get("identity_crosswalk_only"):
        occurrence_value = payload.get("identity_source_occurrence")
        occurrence = (
            _mapping(
                occurrence_value,
                "case.identity_source_occurrence",
            )
            if isinstance(occurrence_value, Mapping)
            else record
        )
        _record_case_source_occurrence(
            db,
            occurrence,
            case_id=case_id,
            record_identity_source_id=case_source_id,
            snapshot_id=snapshot_id,
        )
        return canonical_court_ref(
            case_source_id,
            court_id,
            _required_text(
                payload.get("raw_case_number", payload.get("case_number")),
                "case.raw_case_number",
            ),
        )
    for index, value in enumerate(
        _sequence(
            payload.get("source_occurrences"),
            "case.source_occurrences",
        )
    ):
        occurrence = _mapping(
            value,
            f"case.source_occurrences[{index}]",
        )
        _record_case_source_occurrence(
            db,
            occurrence,
            case_id=case_id,
            record_identity_source_id=case_source_id,
            snapshot_id=snapshot_id,
        )
    _project_parties_and_attorneys(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        case_access_state=case_access_state,
        case_native_access_state=case_native_access_state,
        counts=counts,
    )
    _project_assignments(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        counts=counts,
    )
    _project_case_relations(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        snapshot_id=snapshot_id,
        counts=counts,
    )
    _project_claims(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        snapshot_id=snapshot_id,
        counts=counts,
    )
    docket_ids = _project_docket_and_documents(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        snapshot_id=snapshot_id,
        case_access_state=case_access_state,
        case_native_access_state=case_native_access_state,
        counts=counts,
    )
    _project_events(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        snapshot_id=snapshot_id,
        docket_ids=docket_ids,
        counts=counts,
    )
    _project_restrictions(
        db,
        payload,
        case_id=case_id,
        source_id=case_source_id,
        counts=counts,
    )
    return canonical_court_ref(
        case_source_id,
        court_id,
        _required_text(
            payload.get("raw_case_number", payload.get("case_number")),
            "case.raw_case_number",
        ),
        native_id=_optional_text(payload.get("source_internal_id")),
    )


def _has_projectable_case_shape(record: Mapping[str, Any]) -> bool:
    """Return whether a record exposes the adapter-neutral case shape."""

    nested = record.get("case")
    payload = nested if isinstance(nested, Mapping) else record
    court = payload.get("court")
    case_number = payload.get(
        "raw_case_number",
        payload.get("case_number"),
    )
    return isinstance(court, Mapping) and _optional_text(case_number) is not None


def _normalize_eugene_documents(
    documents: Any,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, value in enumerate(_sequence(documents, "case.documents")):
        document = dict(_mapping(value, f"case.documents[{index}]"))
        source_url = _optional_text(document.get("source_url", document.get("url")))
        if source_url is None:
            continue
        document.setdefault(
            "native_document_id",
            "url:" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24],
        )
        document.setdefault(
            "document_type",
            _optional_text(document.get("label")) or "published_case_document",
        )
        document["source_url"] = source_url
        document.setdefault("access_state", "public")
        normalized.append(document)
    return normalized


def _eugene_projection_records(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    """Return case-shaped Tyler projections with tenant identity retained."""

    if record.get("record_kind") != "calendar_session":
        normalized = dict(record)
        normalized["documents"] = _normalize_eugene_documents(
            normalized.get("documents")
        )
        return [normalized]

    cases = record.get("cases")
    if not isinstance(cases, list):
        return []
    court = _mapping(record.get("court"), "calendar_session.court")
    session_id = _required_text(
        record.get("native_session_id"),
        "calendar_session.native_session_id",
    )
    event_time = None
    start_at = _optional_text(record.get("start_at"))
    if start_at and "T" in start_at:
        event_time = start_at.split("T", 1)[1]
    projections: list[dict[str, Any]] = []
    for index, value in enumerate(cases):
        case = _mapping(value, f"calendar_session.cases[{index}]")
        raw_case_number = _required_text(
            case.get("raw_case_number"),
            "calendar_session.case.raw_case_number",
        )
        defendant_name = _optional_text(case.get("defendant_name"))
        attorney_name = _optional_text(case.get("attorney"))
        projections.append(
            {
                "source_id": source_id,
                "record_kind": "case",
                "court": dict(court),
                "raw_case_number": raw_case_number,
                "caption": defendant_name,
                "access_state": "public",
                "source_url": _optional_text(
                    case.get("detail_url", record.get("detail_url"))
                ),
                "parties": (
                    [
                        {
                            "name": defendant_name,
                            "role": "defendant",
                            "attorneys": (
                                [{"raw_name": attorney_name}] if attorney_name else []
                            ),
                        }
                    ]
                    if defendant_name
                    else []
                ),
                "docket_entries": [
                    {
                        "native_entry_id": f"calendar:{session_id}:{raw_case_number}",
                        "event_code": "municipal_calendar_session",
                        "event_type": "hearing",
                        "raw_text": " | ".join(
                            value
                            for value in (
                                _optional_text(record.get("docket_name")),
                                _optional_text(case.get("offense")),
                            )
                            if value
                        ),
                        "event_date": _optional_text(record.get("date")),
                        "event_time": event_time
                        or _optional_text(record.get("time_raw")),
                        "judge": _optional_text(record.get("judge")),
                        "location": _optional_text(record.get("courtroom")),
                        "document_available": False,
                    }
                ],
                "documents": [],
                "calendar_session": {
                    "native_session_id": session_id,
                    "calendar_code": record.get("calendar_code"),
                    "room_code": record.get("room_code"),
                    "source_fields": record.get("source_fields"),
                    "case_occurrence": dict(case),
                },
            }
        )
    return projections


def _florida_acis_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project case-bearing ACIS calendar events without inventing case state."""

    if _optional_text(record.get("record_kind")) != "calendar_event":
        return [dict(record)]
    event_id = _required_text(
        record.get("native_event_id"),
        "florida_acis.native_event_id",
    )
    court = dict(_mapping(record.get("court"), "florida_acis.court"))
    cases = _sequence(record.get("cases"), "florida_acis.cases")
    event_name = _optional_text(record.get("event_name"))
    event_type = _optional_text(record.get("event_type"))
    event_location = " | ".join(
        value
        for value in (
            _optional_text(record.get("location")),
            _optional_text(record.get("room")),
        )
        if value
    )
    projected: list[dict[str, Any]] = []
    for index, value in enumerate(cases):
        case = _mapping(value, f"florida_acis.cases[{index}]")
        case_number = _required_text(
            case.get("raw_case_number"),
            "florida_acis.case.raw_case_number",
        )
        event_at = _optional_text(
            case.get("event_date", record.get("event_date"))
        )
        event_date = event_at
        event_time = None
        if event_at and "T" in event_at:
            event_date, event_time = event_at.split("T", 1)
        hearing_type = (
            _optional_text(case.get("event_type"))
            or event_type
            or "court_hearing"
        )
        occurrence_ref = (
            _optional_text(case.get("canonical_ref"))
            or f"calendar:{event_id}:{case_number}:{index + 1}"
        )
        projected.append(
            {
                "source_id": FLORIDA_ACIS_SOURCE_ID,
                "record_kind": "case",
                "court": dict(court),
                "raw_case_number": case_number,
                "display_case_number": _optional_text(
                    case.get("display_case_number")
                )
                or case_number,
                "source_internal_id": _optional_text(
                    case.get("case_instance_uuid")
                    or case.get("source_internal_id")
                ),
                "caption": _optional_text(case.get("caption")),
                "access_state": "public",
                "certified_record": False,
                "source_url": (
                    _optional_text(case.get("source_url"))
                    or _optional_text(record.get("source_url"))
                ),
                "docket_entries": [
                    {
                        "native_entry_id": occurrence_ref,
                        "sequence_no": case.get("order"),
                        "event_code": "appellate_calendar_hearing",
                        "event_type": hearing_type,
                        "raw_text": " | ".join(
                            value
                            for value in (event_name, hearing_type)
                            if value
                        )
                        or "Appellate calendar hearing",
                        "event_date": event_date,
                        "event_time": event_time,
                        "location": event_location or None,
                        "status": _optional_text(case.get("status")),
                        "document_available": False,
                        "access_state": "public",
                    }
                ],
                "florida_acis_calendar_occurrence": {
                    "native_event_id": event_id,
                    "event_name": event_name,
                    "event_type": event_type,
                    "event_date": record.get("event_date"),
                    "panel_flag": record.get("panel_flag"),
                    "case_occurrence": dict(case),
                },
            }
        )
    return projected


def _dc_calendar_projection_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    """Project one D.C. calendar occurrence as a case-linked hearing entry."""

    if record.get("record_kind") != "court_calendar_hearing_occurrence":
        return dict(record)

    court = dict(_mapping(record.get("court"), "dc_calendar.court"))
    court.setdefault("state_code", "DC")
    court.setdefault(
        "native_court_id",
        _required_text(court.get("court_id"), "dc_calendar.court.court_id"),
    )
    party_name = _optional_text(record.get("party"))
    defendant_name = _optional_text(record.get("defendant"))
    caption = party_name or defendant_name
    parties: list[dict[str, Any]] = []
    if caption:
        party = {
            "raw_name": caption,
            "role": "calendar_party" if party_name else "defendant",
            "access_state": "public",
        }
        attorney_name = _optional_text(record.get("attorney"))
        if attorney_name:
            party["attorneys"] = [{"raw_name": attorney_name}]
        parties.append(party)

    event_text = " | ".join(
        value
        for value in (
            _optional_text(record.get("event_name")),
            _optional_text(record.get("charge")),
            _optional_text(record.get("division")),
            _optional_text(record.get("case_type")),
        )
        if value
    )
    native_entry_id = _required_text(
        record.get("native_entry_id"),
        "dc_calendar.native_entry_id",
    )
    return {
        "source_id": source_id,
        "record_kind": "case",
        "court": court,
        "raw_case_number": _required_text(
            record.get("raw_case_number", record.get("case_number")),
            "dc_calendar.raw_case_number",
        ),
        "caption": caption,
        "case_type": _optional_text(record.get("case_type")),
        "access_state": "public",
        "source_url": _optional_text(record.get("source_url")),
        "parties": parties,
        "docket_entries": [
            {
                "native_entry_id": native_entry_id,
                "event_code": (
                    _optional_text(record.get("event_name")) or "calendar_hearing"
                ),
                "event_type": "hearing",
                "raw_text": event_text or "Court calendar hearing",
                "event_date": _optional_text(record.get("event_date")),
                "event_time": _optional_text(record.get("event_time")),
                "judge": _optional_text(record.get("judge")),
                "location": _optional_text(record.get("courtroom")),
                "document_available": False,
                "access_state": "public",
                "event_datetime": record.get("event_datetime"),
                "timezone": record.get("timezone"),
                "utc_offset": record.get("utc_offset"),
                "remote_hearing_url": record.get("remote_hearing_url"),
                "source_occurrence": record.get("source_occurrence"),
                "source_freshness": record.get("source_freshness"),
                "representation": record.get("representation"),
            }
        ],
        "calendar_occurrence": dict(record),
    }


def _los_angeles_name_index_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Crosswalk a purchased name-index match to its case-family identity."""

    if record.get("record_kind") != "case_index_match":
        return dict(record)
    record_identity_source_id = _required_text(
        record.get("record_identity_source_id"),
        "la_name_index.record_identity_source_id",
    )
    projected = dict(record)
    projected["record_identity_source_id"] = record_identity_source_id
    projected["identity_crosswalk_only"] = True
    projected["identity_source_occurrence"] = dict(record)
    projected["source_internal_id"] = None
    projected["parties"] = []
    projected["access_state"] = "public"
    projected["native_access_state"] = (
        _optional_text(record.get("access_state")) or "purchased_name_index_result"
    )
    return projected


def _osceola_stable_id(prefix: str, value: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_json(value).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


def _osceola_court(record: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(record.get("court"), "osceola.court")
    court_id = _required_text(source.get("court_id"), "osceola.court.court_id")
    return {
        **dict(source),
        "court_id": court_id,
        "native_court_id": (
            _optional_text(source.get("native_court_id")) or court_id
        ),
        "name": _required_text(source.get("name"), "osceola.court.name"),
        "state_code": "FL",
        "county_geoid": "12097",
        "official_url": (
            _optional_text(source.get("official_url"))
            or "https://courts.osceolaclerk.com/BenchmarkWeb/Home.aspx/Search"
        ),
    }


def _osceola_docket_entry(
    record: Mapping[str, Any],
    *,
    sequence_no: int | None = None,
) -> dict[str, Any]:
    native_entry_id = _required_text(
        record.get("native_entry_id"),
        "osceola.docket.native_entry_id",
    )
    native_state = (
        _optional_text(record.get("source_document_state"))
        or "benchmark_public_docket_metadata"
    )
    access_state = {
        "public_image_metadata": "public",
        "view_on_request": "restricted",
        "not_available_online": "unknown",
    }.get(native_state, "public")
    documents = []
    for index, value in enumerate(
        _sequence(record.get("documents"), "osceola.docket.documents")
    ):
        source_document = _mapping(
            value,
            f"osceola.docket.documents[{index}]",
        )
        source_access_state = (
            _optional_text(source_document.get("source_access_state"))
            or native_state
        )
        document_access_state = (
            _optional_text(source_document.get("access_state"))
            or access_state
        )
        documents.append(
            {
                "native_document_id": _required_text(
                    source_document.get("native_document_id"),
                    f"osceola.docket.documents[{index}].native_document_id",
                ),
                "document_type": "docket_document_metadata",
                "filed_date": _optional_text(record.get("entry_date")),
                "access_state": document_access_state,
                "native_access_state": source_access_state,
                "certification_status": "metadata_only",
                "document_metadata_available": source_document.get(
                    "document_metadata_available"
                ),
                "request_available": source_document.get("request_available"),
                "osceola_source_fields": dict(source_document),
            }
        )
    return {
        "native_entry_id": native_entry_id,
        "sequence_no": sequence_no,
        "event_code": "docket_entry",
        "event_type": "docket_entry",
        "raw_text": _optional_text(record.get("entry_text")),
        "filed_date": _optional_text(record.get("entry_date")),
        "event_date": _optional_text(record.get("entry_date")),
        "document_available": record.get("document_available"),
        "access_state": access_state,
        "native_access_state": native_state,
        "request_handoff": record.get("request_handoff"),
        "documents": documents,
        "osceola_source_fields": dict(record),
    }


def _osceola_parties(
    record: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attorney_values = [
        _mapping(value, f"osceola.attorneys[{index}]")
        for index, value in enumerate(
            _sequence(record.get("attorneys"), "osceola.attorneys")
        )
    ]
    attorneys_by_id = {
        native_id: attorney
        for attorney in attorney_values
        for native_id in [
            _optional_text(attorney.get("native_attorney_id"))
        ]
        if native_id is not None
    }
    linked_ids: set[str] = set()
    parties: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("parties"), "osceola.parties")
    ):
        source_party = _mapping(value, f"osceola.parties[{index}]")
        raw_name = _optional_text(source_party.get("raw_name"))
        if raw_name is None:
            continue
        representations = []
        for attorney_id_value in _sequence(
            source_party.get("attorney_ids"),
            f"osceola.parties[{index}].attorney_ids",
        ):
            attorney_id = _optional_text(attorney_id_value)
            source_attorney = (
                attorneys_by_id.get(attorney_id)
                if attorney_id is not None
                else None
            )
            if source_attorney is None:
                continue
            linked_ids.add(attorney_id)
            representations.append(
                {
                    "raw_name": _required_text(
                        source_attorney.get("raw_name"),
                        "osceola.attorney.raw_name",
                    ),
                    "native_attorney_id": attorney_id,
                    "source_role": source_attorney.get("source_role"),
                    "osceola_source_fields": dict(source_attorney),
                }
            )
        parties.append(
            {
                "sequence_no": index + 1,
                "role": (
                    _optional_text(source_party.get("role"))
                    or "party"
                ),
                "raw_name": raw_name,
                "access_state": "public",
                "native_access_state": "benchmark_published_party",
                "native_party_id": source_party.get("native_party_id"),
                "source_role": source_party.get("source_role"),
                "attorneys": representations,
                "osceola_source_fields": dict(source_party),
            }
        )
    unlinked_attorneys = [
        {
            "raw_name": _required_text(
                attorney.get("raw_name"),
                "osceola.attorney.raw_name",
            ),
            "native_attorney_id": attorney.get("native_attorney_id"),
            "source_role": attorney.get("source_role"),
            "osceola_source_fields": dict(attorney),
        }
        for attorney in attorney_values
        if _optional_text(attorney.get("native_attorney_id")) not in linked_ids
    ]
    return parties, unlinked_attorneys


def _osceola_search_parties(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    parties = []
    for index, value in enumerate(
        _sequence(record.get("search_matches"), "osceola.search_matches")
    ):
        match = _mapping(value, f"osceola.search_matches[{index}]")
        raw_name = _optional_text(match.get("matched_party_name"))
        if raw_name is None:
            continue
        parties.append(
            {
                "sequence_no": index + 1,
                "role": (
                    (_optional_text(match.get("party_type")) or "search_match")
                    .casefold()
                ),
                "raw_name": raw_name,
                "access_state": "public",
                "native_access_state": "benchmark_case_search_match",
                "native_party_id": match.get("native_party_id"),
                "birth_year": match.get("birth_year"),
                "alias": match.get("alias"),
                "osceola_source_fields": dict(match),
            }
        )
    return parties


def _osceola_claims(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for index, value in enumerate(
        _sequence(record.get("charges"), "osceola.charges")
    ):
        charge = _mapping(value, f"osceola.charges[{index}]")
        native_charge_id = _optional_text(charge.get("native_charge_id"))
        if native_charge_id is None:
            native_charge_id = _osceola_stable_id(
                "osceola-charge",
                {
                    "sequence": index + 1,
                    "description": charge.get("description"),
                    "level": charge.get("level"),
                    "degree": charge.get("degree"),
                },
            )
        claims.append(
            {
                "native_claim_id": native_charge_id,
                "sequence_no": index + 1,
                "claim_type": "case_charge",
                "status": (
                    _optional_text(charge.get("disposition"))
                    or _optional_text(charge.get("plea"))
                ),
                "limited_stub": True,
                "access_state": "public",
                "native_access_state": "benchmark_published_charge_summary",
                "description": charge.get("description"),
                "level": charge.get("level"),
                "degree": charge.get("degree"),
                "plea": charge.get("plea"),
                "disposition": charge.get("disposition"),
                "disposition_date": charge.get("disposition_date"),
                "osceola_source_fields": dict(charge),
            }
        )
    return claims


def _osceola_case_events(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = []
    for index, value in enumerate(
        _sequence(record.get("case_events"), "osceola.case_events")
    ):
        event = _mapping(value, f"osceola.case_events[{index}]")
        native_event_id = _optional_text(event.get("native_event_id"))
        if native_event_id is None:
            native_event_id = _osceola_stable_id(
                "osceola-case-event",
                {
                    "sequence": index + 1,
                    "event_type": event.get("event_type"),
                    "event_date": event.get("event_date"),
                    "result": event.get("result"),
                },
            )
        events.append(
            {
                "native_event_id": native_event_id,
                "event_type": (
                    _optional_text(event.get("event_type"))
                    or "case_event"
                ),
                "event_date": _optional_text(event.get("event_date")),
                "disposition": _optional_text(event.get("result")),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "benchmark_published_case_event",
                "judge": event.get("judge"),
                "location": event.get("location"),
                "event_date_raw": event.get("event_date_raw"),
                "osceola_source_fields": dict(event),
            }
        )
    return events


def _osceola_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project Benchmark case-bearing rows while keeping reports snapshot-only."""

    if _optional_text(record.get("source_id")) != OSCEOLA_BENCHMARK_SOURCE_ID:
        raise ValueError("Osceola Benchmark record has the wrong source_id")
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "case",
        "case_search_hit",
        "docket_entry",
        "document_page_metadata",
    }:
        return []

    case_number = _required_text(
        record.get("raw_case_number"),
        "osceola.raw_case_number",
    )
    source_url = (
        _optional_text(record.get("source_url"))
        or "https://courts.osceolaclerk.com/BenchmarkWeb/Home.aspx/Search"
    )
    projected: dict[str, Any] = {
        "source_id": OSCEOLA_BENCHMARK_SOURCE_ID,
        "record_kind": "case",
        "court": _osceola_court(record),
        "raw_case_number": case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number"))
            or case_number
        ),
        "source_internal_id": _optional_text(record.get("source_internal_id")),
        "caption": _optional_text(record.get("caption")),
        "case_type": _optional_text(record.get("case_type")),
        "filing_date": _optional_text(record.get("filing_date")),
        "status": _optional_text(record.get("status")),
        "access_state": "public",
        "native_access_state": (
            "benchmark_full_public_case"
            if record_kind == "case"
            else "benchmark_partial_case_observation"
        ),
        "certified_record": False,
        "source_url": source_url,
        "preserve_existing_case_fields": record_kind != "case",
        "partial_case_shell": record_kind != "case",
        "parties": [],
        "attorneys": [],
        "claims": [],
        "docket_entries": [],
        "case_events": [],
        "documents": [],
        "osceola_source_occurrence": dict(record),
    }

    if record_kind == "case_search_hit":
        projected["parties"] = _osceola_search_parties(record)
        projected["citation_number"] = record.get("citation_number")
        projected["arresting_case_number"] = record.get(
            "arresting_case_number"
        )
        projected["source_result_row_count"] = record.get(
            "source_result_row_count"
        )
        return [projected]

    if record_kind == "case":
        parties, unlinked_attorneys = _osceola_parties(record)
        projected["parties"] = parties
        projected["attorneys"] = unlinked_attorneys
        projected["claims"] = _osceola_claims(record)
        projected["docket_entries"] = [
            _osceola_docket_entry(
                _mapping(value, f"osceola.docket_entries[{index}]"),
                sequence_no=index + 1,
            )
            for index, value in enumerate(
                _sequence(
                    record.get("docket_entries"),
                    "osceola.docket_entries",
                )
            )
        ]
        projected["case_events"] = _osceola_case_events(record)
        judge = _optional_text(record.get("judge"))
        if judge is not None:
            projected["judicial_assignments"] = [
                {
                    "assignment_role": "presiding_judge",
                    "officer": {"raw_name": judge},
                }
            ]
        projected["status_date"] = record.get("status_date")
        projected["charges"] = record.get("charges")
        projected["charge_details"] = record.get("charge_details")
        projected["fees"] = record.get("fees")
        projected["additional_cases"] = record.get("additional_cases")
        projected["related_cases"] = record.get("related_cases")
        return [projected]

    if record_kind == "docket_entry":
        projected["docket_entries"] = [_osceola_docket_entry(record)]
        return [projected]

    document_id = _required_text(
        record.get("native_document_id"),
        "osceola.document.native_document_id",
    )
    projected["documents"] = [
        {
            "native_document_id": document_id,
            "document_type": "docket_page_metadata",
            "source_url": _optional_text(
                record.get("image_url", record.get("source_url"))
            ),
            "page_count": 1,
            "access_state": (
                _optional_text(record.get("access_state")) or "unknown"
            ),
            "native_access_state": (
                _optional_text(record.get("source_access_state"))
                or "benchmark_document_page_metadata"
            ),
            "certification_status": "metadata_only",
            "benchmark_docket_id": record.get("native_entry_id"),
            "document_extension": record.get("document_extension"),
            "document_sequence": record.get("document_sequence"),
            "page_sequence": record.get("page_sequence"),
            "source_table_id": record.get("source_table_id"),
            "hide_page": record.get("hide_page"),
            "redact_status": record.get("redact_status"),
            "session_context": record.get("session_context"),
            "osceola_source_fields": dict(record),
        }
    ]
    return [projected]


def _california_opinion_event_id(
    *,
    court_id: str,
    appellate_case_number: str,
    opinion_identifier: str,
    decision_date: str,
) -> str:
    identity = {
        "source_id": CALIFORNIA_OPINIONS_SOURCE_ID,
        "court_id": court_id,
        "appellate_case_number": appellate_case_number,
        "opinion_identifier": opinion_identifier,
        "decision_date": decision_date,
    }
    digest = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()
    return f"ca-opinion-publication:{digest}"


def _california_opinion_documents(
    record: Mapping[str, Any],
    *,
    docket_entry_native_id: str,
    decision_date: str,
    opinion_identifier: str,
    document_version: str,
) -> list[dict[str, Any]]:
    source_documents = record.get("documents")
    if source_documents is None:
        source_documents = record.get("formats")
    documents: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, value in enumerate(
        _sequence(source_documents, "california_opinion.documents")
    ):
        source_document = _mapping(
            value,
            f"california_opinion.documents[{index}]",
        )
        source_url = _required_text(
            source_document.get("url", source_document.get("source_url")),
            f"california_opinion.documents[{index}].url",
        )
        document_format = _required_text(
            source_document.get("format"),
            f"california_opinion.documents[{index}].format",
        ).casefold()
        identity = (source_url, document_format)
        if identity in seen:
            continue
        seen.add(identity)
        official_path = urlsplit(source_url).path
        identity_digest = hashlib.sha256(
            _json(
                {
                    "official_document_path": official_path,
                    "format": document_format,
                }
            ).encode("utf-8")
        ).hexdigest()
        documents.append(
            {
                "native_document_id": f"ca-opinion-document:{identity_digest}",
                "docket_entry_native_id": docket_entry_native_id,
                "document_type": f"appellate_opinion_{document_format}",
                "filed_date": decision_date,
                "source_url": source_url,
                "mime_type": _optional_text(
                    source_document.get(
                        "media_type",
                        source_document.get("mime_type"),
                    )
                ),
                "access_state": "public",
                "native_access_state": (
                    f"official_{document_version}_{document_format}_link"
                ),
                "format": document_format,
                "document_version": document_version,
                "opinion_identifier": opinion_identifier,
                "official_document_path": official_path,
            }
        )
    return documents


def _california_opinion_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project current opinion occurrences as sparse appellate case shells."""

    if _optional_text(record.get("source_id")) != CALIFORNIA_OPINIONS_SOURCE_ID:
        raise ValueError("California opinion record has the wrong source_id")
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "appellate_opinion_index_entry",
        "appellate_opinion_detail",
    }:
        return []

    appellate_case_number = _required_text(
        record.get("appellate_case_number", record.get("case_number")),
        "california_opinion.appellate_case_number",
    )
    opinion_identifier = _required_text(
        record.get("opinion_identifier"),
        "california_opinion.opinion_identifier",
    )
    decision_date = _required_text(
        record.get("decision_date"),
        "california_opinion.decision_date",
    )
    collection = _required_text(
        record.get("collection"),
        "california_opinion.collection",
    )
    publication_status = _required_text(
        record.get("publication_status"),
        "california_opinion.publication_status",
    )
    document_version = _required_text(
        record.get("document_version"),
        "california_opinion.document_version",
    )
    citation_status = _required_text(
        record.get("citation_status"),
        "california_opinion.citation_status",
    )
    court_source = _mapping(
        record.get("court"),
        "california_opinion.court",
    )
    court_id = _required_text(
        court_source.get("court_id"),
        "california_opinion.court.court_id",
    )
    court = {
        "court_id": court_id,
        "native_court_id": (
            _optional_text(court_source.get("native_filter_id")) or court_id
        ),
        "name": _required_text(
            court_source.get("name"),
            "california_opinion.court.name",
        ),
        "state_code": _required_text(
            court_source.get("state_code"),
            "california_opinion.court.state_code",
        ),
        "court_level": (
            _optional_text(
                court_source.get("court_level", court_source.get("level"))
            )
            or ("supreme" if court_id == "ca-supreme-court" else "appellate")
        ),
        "official_url": "https://courts.ca.gov/opinions",
    }
    event_id = _california_opinion_event_id(
        court_id=court_id,
        appellate_case_number=appellate_case_number,
        opinion_identifier=opinion_identifier,
        decision_date=decision_date,
    )
    documents = _california_opinion_documents(
        record,
        docket_entry_native_id=event_id,
        decision_date=decision_date,
        opinion_identifier=opinion_identifier,
        document_version=document_version,
    )
    source_scope_value = record.get("source_scope")
    source_scope = (
        dict(source_scope_value)
        if isinstance(source_scope_value, Mapping)
        else {
            "current_window_days": 120 if collection == "published" else 60,
            "complete_appellate_docket": False,
            "complete_filing_set": False,
            "opinion_publication": True,
        }
    )
    source_url = _optional_text(record.get("source_url"))
    case_information_url = _optional_text(record.get("case_information_url"))
    official_reports_search_url = _optional_text(
        record.get("official_reports_search_url")
    )
    citings_archive_url = _optional_text(record.get("citings_archive_url"))
    title = _optional_text(record.get("title"))
    event = {
        "native_entry_id": event_id,
        "event_code": "appellate_opinion_publication",
        "event_type": "appellate_opinion_publication",
        "raw_text": title,
        "filed_date": decision_date,
        "event_date": decision_date,
        "status": publication_status,
        "document_available": bool(documents),
        "access_state": "public",
        "native_access_state": "official_current_opinion_publication",
        "collection": collection,
        "publication_status": publication_status,
        "publication_label": record.get("publication_label"),
        "citation_status": citation_status,
        "document_version": document_version,
        "opinion_identifier": opinion_identifier,
        "opinion_identifier_suffix": record.get("opinion_identifier_suffix"),
        "appellate_case_number": appellate_case_number,
        "source_url": source_url,
        "detail_url": record.get("detail_url"),
        "case_information_complement": {
            "source_id": "us-ca-appellate-case-information",
            "url": case_information_url,
            "role": "case_chronology_and_older_opinion_lookup",
        },
        "corrected_official_reports": {
            "included": bool(
                record.get("corrected_official_reports_text_included", False)
            ),
            "search_url": official_reports_search_url,
            "role": "corrected_official_reports_text",
        },
        "citings_archive": (
            {
                "url": citings_archive_url,
                "role": "ancillary_source_snapshot",
                "independent_corroboration": False,
            }
            if citings_archive_url
            else None
        ),
        "source_scope": source_scope,
        "documents": documents,
        "california_opinion_source_occurrence": dict(record),
    }
    return [
        {
            "source_id": CALIFORNIA_OPINIONS_SOURCE_ID,
            "record_kind": "case",
            "court": court,
            "raw_case_number": appellate_case_number,
            "display_case_number": appellate_case_number,
            "source_internal_id": appellate_case_number,
            "caption": title,
            "case_type": "appellate",
            "disposition_date": decision_date,
            "access_state": "public",
            "native_access_state": "official_partial_opinion_case_shell",
            "certified_record": False,
            "source_url": case_information_url or source_url,
            "preserve_existing_case_fields": True,
            "parties": [],
            "docket_entries": [event],
            "partial_case_shell": True,
            "case_information_url": case_information_url,
            "opinion_feed_scope": source_scope,
            "california_opinion_source_occurrence": dict(record),
        }
    ]


def _fresno_projection_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    """Project one Fresno hearing, tentative ruling, or examiner note."""

    record_kind = _optional_text(record.get("record_kind"))
    projectable_kinds = {
        "court_hearing",
        "tentative_ruling",
        "tentative_ruling_continuance",
        "tentative_ruling_must_appear",
        "probate_examiner_note",
    }
    if record_kind not in projectable_kinds:
        return dict(record)

    court_value = record.get("court")
    court = dict(court_value) if isinstance(court_value, Mapping) else {}
    court.setdefault("court_id", "ca-fresno-superior-court")
    court.setdefault("native_court_id", "ca-fresno-superior-court")
    court.setdefault(
        "name",
        "Superior Court of California, County of Fresno",
    )
    court.setdefault("state_code", "CA")
    court.setdefault("county_geoid", "06019")
    court.setdefault("level", "county_trial")
    source_url = _optional_text(record.get("source_url"))
    canonical_ref = _required_text(
        record.get("canonical_ref"),
        "fresno.canonical_ref",
    )
    case_number = _required_text(
        record.get("case_number"),
        "fresno.case_number",
    )
    caption = _optional_text(record.get("case_style"))

    if record_kind == "court_hearing":
        entry = {
            "native_entry_id": canonical_ref,
            "event_code": "hearing",
            "event_type": "hearing",
            "raw_text": (
                _optional_text(record.get("source_text")) or "Court calendar hearing"
            ),
            "event_date": _optional_text(record.get("hearing_date")),
            "event_time": _optional_text(record.get("hearing_time")),
            "judge": _optional_text(record.get("judge")),
            "location": _optional_text(record.get("department")),
            "status": _optional_text(record.get("status_or_custody")),
            "document_available": False,
            "access_state": "public",
            "hearing_type": record.get("hearing_type"),
            "attorney": record.get("attorney"),
            "filing_or_prosecuting_agency_number": record.get(
                "filing_or_prosecuting_agency_number"
            ),
            "calendar_layout": record.get("calendar_layout"),
            "provenance": record.get("provenance"),
        }
        documents: list[dict[str, Any]] = []
        case_type = None
    elif record_kind == "probate_examiner_note":
        entry = {
            "native_entry_id": canonical_ref,
            "event_code": "probate_note",
            "event_type": "probate_examiner_note",
            "raw_text": _required_text(
                record.get("note_text"),
                "fresno.note_text",
            ),
            "event_date": _optional_text(record.get("hearing_date")),
            "entered_date": _optional_text(record.get("date_printed")),
            "document_available": False,
            "access_state": "public",
            "reviewer_initials": record.get("reviewer_initials"),
            "record_lineage": record.get("record_lineage"),
            "provenance": record.get("provenance"),
        }
        documents = []
        case_type = "probate"
    else:
        entry = {
            "native_entry_id": canonical_ref,
            "event_code": record_kind,
            "event_type": "tentative_ruling",
            "raw_text": (
                _optional_text(record.get("source_text")) or "Civil tentative ruling"
            ),
            "event_date": _optional_text(record.get("hearing_date")),
            "entered_date": _optional_text(record.get("issued_date")),
            "location": (
                f"Department {record['department']}"
                if record.get("department") is not None
                else None
            ),
            "status": "tentative",
            "document_available": source_url is not None,
            "access_state": "public",
            "motion": record.get("motion"),
            "tentative_ruling": record.get("tentative_ruling"),
            "explanation": record.get("explanation"),
            "issued_by_initials": record.get("issued_by_initials"),
            "continued_to_date": record.get("continued_to_date"),
            "continued_to_time": record.get("continued_to_time"),
            "continued_to_department": record.get("continued_to_department"),
            "oral_argument": record.get("oral_argument"),
            "provenance": record.get("provenance"),
        }
        provenance = record.get("provenance")
        provenance_values = dict(provenance) if isinstance(provenance, Mapping) else {}
        artifact_sha256 = _optional_text(
            provenance_values.get(
                "artifact_sha256",
                provenance_values.get("sha256"),
            )
        )
        documents = (
            [
                {
                    "native_document_id": (
                        f"tentative-pdf:{artifact_sha256}"
                        if artifact_sha256
                        else "tentative-url:"
                        + hashlib.sha256(source_url.encode()).hexdigest()
                    ),
                    "document_type": "civil_tentative_ruling_pdf",
                    "filed_date": _optional_text(record.get("hearing_date")),
                    "source_url": source_url,
                    "sha256": artifact_sha256,
                    "mime_type": "application/pdf",
                    "access_state": "public",
                }
            ]
            if source_url
            else []
        )
        case_type = "civil"

    return {
        "source_id": source_id,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "caption": caption,
        "case_type": case_type,
        "access_state": "public",
        "source_url": source_url,
        "docket_entries": [entry],
        "documents": documents,
        "fresno_source_occurrence": dict(record),
    }


def _orange_projection_records(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    """Project Orange hearing occurrences and case-bearing ruling PDFs."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {"court_hearing", "tentative_ruling_document"}:
        return [dict(record)]

    court_value = record.get("court")
    court = dict(court_value) if isinstance(court_value, Mapping) else {}
    court.setdefault("court_id", "ca-orange-superior")
    court.setdefault("native_court_id", "ca-orange-superior")
    court.setdefault(
        "name",
        "Superior Court of California, County of Orange",
    )
    court.setdefault("state_code", "CA")
    court.setdefault("county_geoid", "06059")
    court.setdefault("level", "county_trial")
    canonical_ref = _required_text(
        record.get("canonical_ref"),
        "orange.canonical_ref",
    )

    if record_kind == "court_hearing":
        case = _mapping(record.get("case"), "orange.case")
        hearing = _mapping(record.get("hearing"), "orange.hearing")
        case_number = _required_text(
            case.get("case_number"),
            "orange.case.case_number",
        )
        title_parties = case.get("title_parties")
        parties = (
            [dict(value) for value in title_parties]
            if isinstance(title_parties, Sequence)
            and not isinstance(title_parties, (str, bytes))
            else []
        )
        event_text = " | ".join(
            value
            for value in (
                _optional_text(hearing.get("hearing_type")),
                _optional_text(hearing.get("department")),
                _optional_text(hearing.get("location_code")),
            )
            if value
        )
        return [
            {
                "source_id": source_id,
                "record_kind": "case",
                "court": court,
                "raw_case_number": case_number,
                "caption": _optional_text(case.get("case_title")),
                "case_type": (
                    _optional_text(case.get("case_type"))
                    or _optional_text(case.get("case_category"))
                ),
                "access_state": "public",
                "source_url": _optional_text(record.get("source_url")),
                "parties": parties,
                "docket_entries": [
                    {
                        "native_entry_id": canonical_ref,
                        "event_code": (
                            _optional_text(hearing.get("hearing_type"))
                            or "calendar_hearing"
                        ),
                        "event_type": "hearing",
                        "raw_text": event_text or "Court calendar hearing",
                        "event_date": _optional_text(hearing.get("date")),
                        "event_time": _optional_text(hearing.get("time")),
                        "location": " | ".join(
                            value
                            for value in (
                                _optional_text(hearing.get("location_code")),
                                _optional_text(hearing.get("department")),
                            )
                            if value
                        ),
                        "document_available": False,
                        "access_state": "public",
                        "hearing_type": hearing.get("hearing_type"),
                    }
                ],
                "orange_source_occurrence": dict(record),
            }
        ]

    case_numbers_value = record.get("case_numbers")
    case_numbers = (
        [str(value).strip() for value in case_numbers_value if str(value).strip()]
        if isinstance(case_numbers_value, Sequence)
        and not isinstance(case_numbers_value, (str, bytes))
        else []
    )
    if not case_numbers:
        return [dict(record)]
    hearing = _mapping(record.get("hearing"), "orange.hearing")
    artifact = _mapping(record.get("artifact"), "orange.artifact")
    artifact_url = _optional_text(artifact.get("url"))
    division = _optional_text(record.get("division")) or "trial"
    document = {
        "native_document_id": canonical_ref,
        "document_type": f"{division}_tentative_ruling_pdf",
        "filed_date": _optional_text(hearing.get("date")),
        "source_url": artifact_url,
        "sha256": _optional_text(artifact.get("sha256")),
        "mime_type": "application/pdf",
        "access_state": "public",
        "artifact_bytes": artifact.get("bytes"),
        "last_modified": artifact.get("last_modified"),
        "text_sha256": record.get("text_sha256"),
    }
    return [
        {
            "source_id": source_id,
            "record_kind": "case",
            "court": court,
            "raw_case_number": case_number,
            "case_type": division,
            "access_state": "public",
            "source_url": artifact_url,
            "docket_entries": [
                {
                    "native_entry_id": f"{canonical_ref}:{case_number}",
                    "event_code": "tentative_ruling",
                    "event_type": "tentative_ruling",
                    "raw_text": (
                        _optional_text(record.get("text"))
                        or f"{division.title()} tentative ruling"
                    ),
                    "event_date": _optional_text(hearing.get("date")),
                    "event_time": _optional_text(hearing.get("time")),
                    "judge": _optional_text(record.get("judicial_officer")),
                    "location": (
                        f"Department {record['department']}"
                        if record.get("department")
                        else None
                    ),
                    "status": "tentative",
                    "document_available": artifact_url is not None,
                    "access_state": "public",
                    "publication_state": "tentative",
                    "document": dict(document),
                }
            ],
            "documents": [dict(document)],
            "orange_source_occurrence": dict(record),
        }
        for case_number in case_numbers
    ]


def _riverside_projection_records(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    """Project Riverside hearings and case-bearing ruling PDFs."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "court_calendar_event",
        "tentative_ruling_document",
    }:
        return [dict(record)]

    court_value = record.get("court")
    court = dict(court_value) if isinstance(court_value, Mapping) else {}
    court.setdefault("court_id", "ca-riverside-superior")
    court.setdefault("native_court_id", "ca-riverside-superior")
    court.setdefault(
        "name",
        "Superior Court of California, County of Riverside",
    )
    court.setdefault("state_code", "CA")
    court.setdefault("county_geoid", "06065")
    court.setdefault("level", "county_trial")
    canonical_ref = _required_text(
        record.get("canonical_ref"),
        "riverside.canonical_ref",
    )

    if record_kind == "court_calendar_event":
        case_number = _required_text(
            record.get("case_number"),
            "riverside.case_number",
        )
        hearing = _mapping(record.get("hearing"), "riverside.hearing")
        courthouse_value = record.get("courthouse")
        courthouse = (
            dict(courthouse_value) if isinstance(courthouse_value, Mapping) else {}
        )
        event_names = hearing.get("names")
        event_name_values = (
            [str(value).strip() for value in event_names if str(value).strip()]
            if isinstance(event_names, Sequence)
            and not isinstance(event_names, (str, bytes))
            else []
        )
        attorneys_value = record.get("attorneys")
        attorneys = (
            [
                {"raw_name": str(value).strip()}
                for value in attorneys_value
                if str(value).strip()
            ]
            if isinstance(attorneys_value, Sequence)
            and not isinstance(attorneys_value, (str, bytes))
            else []
        )
        location = " | ".join(
            value
            for value in (
                _optional_text(courthouse.get("name")),
                _optional_text(record.get("department_label")),
                _optional_text(courthouse.get("address")),
            )
            if value
        )
        return [
            {
                "source_id": source_id,
                "record_kind": "case",
                "court": court,
                "raw_case_number": case_number,
                "caption": _optional_text(record.get("case_name")),
                "case_type": (
                    _optional_text(record.get("case_type"))
                    or _optional_text(record.get("area_of_law"))
                ),
                "access_state": "public",
                "attorneys": attorneys,
                "docket_entries": [
                    {
                        "native_entry_id": canonical_ref,
                        "event_code": (
                            event_name_values[0]
                            if event_name_values
                            else "calendar_hearing"
                        ),
                        "event_type": "hearing",
                        "raw_text": (
                            " | ".join(event_name_values) or "Court calendar hearing"
                        ),
                        "event_date": _optional_text(hearing.get("date")),
                        "event_time": _optional_text(hearing.get("time")),
                        "judge": _optional_text(record.get("judicial_officer")),
                        "location": location or None,
                        "status": _optional_text(hearing.get("special_status")),
                        "document_available": False,
                        "access_state": "public",
                        "hearing_type": event_name_values,
                        "charge_data": record.get("charge_data"),
                    }
                ],
                "riverside_source_occurrence": dict(record),
            }
        ]

    case_numbers_value = record.get("case_numbers")
    case_numbers = (
        list(
            dict.fromkeys(
                str(value).strip() for value in case_numbers_value if str(value).strip()
            )
        )
        if isinstance(case_numbers_value, Sequence)
        and not isinstance(case_numbers_value, (str, bytes))
        else []
    )
    if not case_numbers:
        return [dict(record)]
    artifact = _mapping(record.get("artifact"), "riverside.artifact")
    artifact_url = _optional_text(artifact.get("url"))
    document = {
        "native_document_id": canonical_ref,
        "document_type": "tentative_ruling_pdf",
        "filed_date": _optional_text(record.get("hearing_date")),
        "source_url": artifact_url,
        "sha256": _optional_text(artifact.get("sha256")),
        "mime_type": (
            _optional_text(artifact.get("content_type")) or "application/pdf"
        ),
        "storage_path": _optional_text(artifact.get("local_path")),
        "access_state": "public",
        "artifact_bytes": artifact.get("bytes"),
        "last_modified": artifact.get("last_modified"),
        "text_sha256": record.get("text_sha256"),
    }
    return [
        {
            "source_id": source_id,
            "record_kind": "case",
            "court": court,
            "raw_case_number": case_number,
            "case_type": "trial",
            "access_state": "public",
            "source_url": artifact_url,
            "docket_entries": [
                {
                    "native_entry_id": f"{canonical_ref}:{case_number}",
                    "event_code": "tentative_ruling",
                    "event_type": "tentative_ruling",
                    "raw_text": (
                        _optional_text(record.get("text")) or "Tentative ruling"
                    ),
                    "event_date": _optional_text(record.get("hearing_date")),
                    "judge": _optional_text(record.get("judicial_officer")),
                    "location": (
                        f"Department {record['department']}"
                        if record.get("department")
                        else None
                    ),
                    "status": "tentative",
                    "document_available": artifact_url is not None,
                    "access_state": "public",
                    "publication_state": "tentative",
                    "directory_record": record.get("directory_record"),
                    "document": dict(document),
                }
            ],
            "documents": [dict(document)],
            "riverside_source_occurrence": dict(record),
        }
        for case_number in case_numbers
    ]


def _qld_party_name(party: Mapping[str, Any]) -> str | None:
    """Return the source-published display name without losing company names."""

    family_or_company = _optional_text(party.get("last_company_name"))
    given_names = _optional_text(party.get("first_name"))
    if given_names and family_or_company:
        return f"{given_names} {family_or_company}"
    return family_or_company or given_names


def _qld_ecourts_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one registry-disambiguated Queensland civil case."""

    if record.get("record_type") not in {
        "court_case",
        "court_case_search_hit",
    }:
        return dict(record)

    court_code = _required_text(
        record.get("court_code"),
        "qld_ecourts.court_code",
    ).upper()
    originating_location_code = _required_text(
        record.get("originating_location_code"),
        "qld_ecourts.originating_location_code",
    ).upper()
    file_number = _required_text(
        record.get("file_number"),
        "qld_ecourts.file_number",
    )
    evidence_ref = _required_text(
        record.get("evidence_ref"),
        "qld_ecourts.evidence_ref",
    )
    source_internal_id = evidence_ref.split(":", 1)[-1]
    court_label = _optional_text(record.get("court_name")) or court_code
    court_name = (
        court_label
        if court_label.casefold().startswith("queensland ")
        else f"Queensland {court_label} Court"
    )
    court_id = {
        "SUPRE": "qld-supreme-court",
        "DISTR": "qld-district-court",
    }.get(court_code, f"qld-{court_code.casefold()}-court")

    parties: list[dict[str, Any]] = []
    for value in _sequence(record.get("parties"), "qld_ecourts.parties"):
        party = _mapping(value, "qld_ecourts.party")
        raw_name = _qld_party_name(party)
        if raw_name is None:
            continue
        normalized_party: dict[str, Any] = {
            "raw_name": raw_name,
            "role": _optional_text(party.get("party_role")) or "party",
            "entity_kind": (
                "organization"
                if _optional_text(party.get("acn"))
                or not _optional_text(party.get("first_name"))
                else "person"
            ),
            "access_state": "public",
            "qld_source_fields": dict(party),
        }
        representative = _optional_text(party.get("representative"))
        if representative:
            normalized_party["attorneys"] = [
                {
                    "raw_name": representative,
                    "firm_name": representative,
                }
            ]
        parties.append(normalized_party)

    events: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("events"), "qld_ecourts.events")
    ):
        event = _mapping(value, f"qld_ecourts.events[{index}]")
        event_type = _optional_text(event.get("event_type")) or "court_event"
        event_digest = hashlib.sha256(_json(event).encode("utf-8")).hexdigest()[:16]
        events.append(
            {
                "native_event_id": (
                    f"{source_internal_id}:EVENT-{index + 1}:{event_digest}"
                ),
                "event_type": event_type,
                "event_date": _optional_text(event.get("date_iso")),
                "disposition": _optional_text(event.get("result")),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "ecourts_event_table",
                "qld_source_fields": dict(event),
            }
        )

    documents: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("documents"), "qld_ecourts.documents")
    ):
        document = _mapping(value, f"qld_ecourts.documents[{index}]")
        document_ref = (
            _optional_text(document.get("evidence_ref"))
            or f"{evidence_ref}:DOC-ROW-{index + 1}"
        )
        documents.append(
            {
                "native_document_id": document_ref,
                "document_type": _optional_text(document.get("document_type")),
                "filed_date": _optional_text(document.get("date_filed_iso")),
                "page_count": document.get("pages"),
                "access_state": "public",
                "native_access_state": "metadata_public_copy_request_required",
                "qld_source_fields": dict(document),
            }
        )

    return {
        "source_id": QLD_ECOURTS_SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": court_id,
            "native_court_id": court_code,
            "name": court_name,
            "state_code": "QLD",
            "level": "state_trial",
            "division": court_label,
            "official_url": _optional_text(record.get("source_url")),
        },
        "raw_case_number": file_number,
        "source_internal_id": source_internal_id,
        "caption": _optional_text(record.get("case_name")),
        "case_type": (_optional_text(record.get("proceeding_type")) or "civil"),
        "filing_date": _optional_text(record.get("date_filed_iso")),
        "access_state": "public",
        "native_access_state": "public_case_and_document_metadata",
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "parties": parties,
        "case_events": events,
        "documents": documents,
        "originating_registry": {
            "code": originating_location_code,
            "name": _optional_text(record.get("originating_location")),
        },
        "current_registry": {
            "code": _optional_text(record.get("current_location_code")),
            "name": _optional_text(record.get("current_location")),
        },
        "related_files": record.get("related_files"),
        "status_notices": record.get("status_notices"),
        "qld_source_occurrence": dict(record),
    }


def _wisconsin_wscca_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    document = dict(value)
    event_sequence = document.get("native_event_sequence")
    projected = {
        "native_document_id": _required_text(
            document.get("native_document_id"),
            "wisconsin_wscca.document.native_document_id",
        ),
        "document_type": (
            _optional_text(document.get("document_type"))
            or _optional_text(document.get("document_name"))
            or "appellate_case_document"
        ),
        "filed_date": _optional_text(document.get("filed_date")),
        "source_url": _optional_text(document.get("source_url")),
        "mime_type": _optional_text(
            document.get("mime_type", document.get("media_type"))
        ),
        "page_count": document.get("page_count"),
        "sha256": _optional_text(document.get("sha256")),
        "storage_path": _optional_text(
            document.get("storage_path", document.get("local_path"))
        ),
        "certification_status": _optional_text(document.get("certification_status")),
        "access_state": "public",
        "native_access_state": (
            _optional_text(document.get("artifact_state"))
            or _optional_text(document.get("access_state"))
            or "source_listed_public_document"
        ),
        "wscca_source_fields": document,
    }
    if event_sequence is not None:
        projected["docket_entry_native_id"] = str(event_sequence)
    return projected


def _wisconsin_wscca_docket_entry(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    entry = dict(value)
    raw_text = " | ".join(
        text
        for text in (
            _optional_text(entry.get("title")),
            _optional_text(entry.get("description")),
            _optional_text(entry.get("comment")),
            _optional_text(entry.get("detail")),
        )
        if text
    )
    linked_documents = entry.get("linked_documents")
    return {
        "native_entry_id": _required_text(
            entry.get("native_entry_id"),
            "wisconsin_wscca.docket_entry.native_entry_id",
        ),
        "sequence_no": _optional_text(
            entry.get("native_event_sequence", entry.get("native_entry_id"))
        ),
        "event_code": (
            _optional_text(entry.get("native_event_code"))
            or _optional_text(entry.get("phase"))
            or "appellate_docket_update"
        ),
        "event_type": "appellate_docket_entry",
        "raw_text": raw_text or None,
        "filed_date": _optional_text(entry.get("filed_date")),
        "entered_date": _optional_text(entry.get("published_at")),
        "event_date": (
            _optional_text(entry.get("filed_date"))
            or _optional_text(entry.get("published_at"))
        ),
        "document_available": bool(linked_documents or entry.get("linked_source_urls")),
        "access_state": "public",
        "native_access_state": (
            _optional_text(entry.get("access_state"))
            or "source_published_docket_metadata"
        ),
        "wscca_source_fields": entry,
    }


def _wisconsin_wscca_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project WSCCA cases and case-linked child records into one identity."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {"case", "docket_entry", "document", "document_artifact"}:
        return dict(record)
    court_value = record.get("court")
    case_number = _optional_text(record.get("raw_case_number"))
    if not isinstance(court_value, Mapping) or case_number is None:
        return dict(record)

    court = dict(court_value)
    court.setdefault("native_court_id", court.get("court_id"))
    court.setdefault("official_url", _optional_text(record.get("source_url")))
    projected: dict[str, Any] = {
        "source_id": WISCONSIN_WSCCA_SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number")) or case_number
        ),
        "source_internal_id": case_number,
        "caption": _optional_text(record.get("caption")),
        "case_type": (_optional_text(record.get("case_type")) or "appellate"),
        "filing_date": _optional_text(record.get("filing_date")),
        "disposition_date": _optional_text(record.get("disposition_date")),
        "status": _optional_text(record.get("status", record.get("disposition"))),
        "access_state": "public",
        "native_access_state": (
            _optional_text(record.get("access_state")) or "wscca_public_metadata"
        ),
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "wscca_source_occurrence": dict(record),
    }

    if record_kind == "case":
        parties: list[dict[str, Any]] = []
        party_sequence_by_native: dict[str, int] = {}
        for value in _sequence(record.get("parties"), "wisconsin_wscca.parties"):
            party = _mapping(value, "wisconsin_wscca.party")
            raw_name = _optional_text(party.get("raw_name"))
            if raw_name is None:
                continue
            sequence_no = len(parties) + 1
            native_sequence = _optional_text(party.get("native_party_sequence"))
            if native_sequence is not None:
                party_sequence_by_native[native_sequence] = sequence_no
            roles = [
                role
                for role in (
                    _optional_text(item)
                    for item in _sequence(
                        party.get("roles"),
                        "wisconsin_wscca.party.roles",
                    )
                )
                if role
            ]
            parties.append(
                {
                    "sequence_no": sequence_no,
                    "role": " / ".join(roles) or "party",
                    "raw_name": raw_name,
                    "access_state": "public",
                    "native_access_state": (
                        _optional_text(party.get("native_visibility_state"))
                        or "wscca_public_party"
                    ),
                    "wscca_source_fields": dict(party),
                }
            )
        for value in _sequence(
            record.get("interested_parties"),
            "wisconsin_wscca.interested_parties",
        ):
            party = _mapping(value, "wisconsin_wscca.interested_party")
            raw_name = _optional_text(party.get("raw_name"))
            if raw_name is None:
                continue
            parties.append(
                {
                    "sequence_no": len(parties) + 1,
                    "role": _optional_text(party.get("role")) or "interested_party",
                    "raw_name": raw_name,
                    "access_state": "public",
                    "native_access_state": (
                        _optional_text(party.get("native_visibility_state"))
                        or "wscca_public_interested_party"
                    ),
                    "wscca_source_fields": dict(party),
                }
            )
        projected["parties"] = parties

        representations: list[dict[str, Any]] = []
        for value in _sequence(
            record.get("attorneys"),
            "wisconsin_wscca.attorneys",
        ):
            attorney = _mapping(value, "wisconsin_wscca.attorney")
            raw_name = _optional_text(attorney.get("raw_name"))
            if raw_name is None:
                continue
            native_party_sequence = _optional_text(
                attorney.get("native_party_sequence")
            )
            representation: dict[str, Any] = {
                "raw_name": raw_name,
                "effective_from": _optional_text(attorney.get("entered_date")),
                "effective_to": _optional_text(attorney.get("withdrawn_date")),
                "wscca_source_fields": dict(attorney),
            }
            party_sequence = party_sequence_by_native.get(native_party_sequence or "")
            if party_sequence is not None:
                representation["party_sequence_no"] = party_sequence
            representations.append(representation)
        projected["representations"] = representations

        docket_entries = [
            _wisconsin_wscca_docket_entry(_mapping(value, "wscca.docket_entry"))
            for value in _sequence(
                record.get("docket_entries"),
                "wisconsin_wscca.docket_entries",
            )
        ]
        projected["docket_entries"] = docket_entries
        known_docket_ids = {entry["native_entry_id"] for entry in docket_entries}
        documents = [
            _wisconsin_wscca_document(_mapping(value, "wscca.document"))
            for value in _sequence(
                record.get("documents"),
                "wisconsin_wscca.documents",
            )
        ]
        for document in documents:
            if document.get("docket_entry_native_id") not in known_docket_ids:
                document.pop("docket_entry_native_id", None)
        projected["documents"] = documents
        projected["case_relations"] = [
            {
                "relation_type": "originating_trial_case",
                "raw_case_number": related_case_number,
                "county": _optional_text(relation.get("county")),
                "court_name": (
                    f"{_optional_text(relation.get('county'))} County Circuit Court"
                    if _optional_text(relation.get("county"))
                    else "Wisconsin Circuit Court"
                ),
                "judge": (
                    _optional_text(relation.get("responsible_circuit_court_judge"))
                    or _optional_text(relation.get("circuit_court_judge"))
                ),
                "source_url": _optional_text(relation.get("source_url")),
                "native_relation_id": (
                    f"{_optional_text(relation.get('county')) or 'wisconsin'}:"
                    f"{related_case_number}"
                ),
                "access_state": "public",
                "wscca_source_fields": dict(relation),
            }
            for value in _sequence(
                record.get("linked_circuit_cases"),
                "wisconsin_wscca.linked_circuit_cases",
            )
            for relation in [_mapping(value, "wisconsin_wscca.linked_circuit_case")]
            for related_case_number in [_optional_text(relation.get("raw_case_number"))]
            if related_case_number is not None
        ]
        return projected

    projected["preserve_existing_case_fields"] = True
    if record_kind == "docket_entry":
        projected["docket_entries"] = [_wisconsin_wscca_docket_entry(record)]
    else:
        projected["documents"] = [_wisconsin_wscca_document(record)]
    return projected


def _wisconsin_opinion_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project structured publication records without treating them as dockets."""

    record_kind = _optional_text(record.get("record_kind"))
    projectable_kinds = {
        "appellate_opinion_index",
        "appellate_order_index",
        "summary_disposition_index",
        "full_text_search_hit",
        "opinion_release_notice",
    }
    if record_kind not in projectable_kinds:
        return dict(record)
    case_number = _optional_text(record.get("normalized_appellate_case_number"))
    court_value = record.get("court")
    if case_number is None or not isinstance(court_value, Mapping):
        return dict(record)

    court = dict(court_value)
    court.setdefault("native_court_id", court.get("court_id"))
    native_entry_id: str
    event_date: str | None
    document: dict[str, Any] | None = None
    if record_kind in {
        "appellate_opinion_index",
        "appellate_order_index",
        "summary_disposition_index",
    }:
        source_document = _mapping(
            record.get("document"),
            "wisconsin_opinion.document",
        )
        native_document_id = _required_text(
            source_document.get("native_document_id"),
            "wisconsin_opinion.document.native_document_id",
        )
        native_entry_id = f"{record_kind}:{native_document_id}"
        event_date = _optional_text(
            record.get("decision_date", record.get("issued_date"))
        )
        document = {
            **dict(source_document),
            "docket_entry_native_id": native_entry_id,
            "mime_type": _optional_text(source_document.get("mime_type")),
            "access_state": "public",
            "native_access_state": "official_publication_pdf",
            "wisconsin_publication_identity": {
                "case_number": case_number,
                "native_document_id": native_document_id,
                "native_document_id_type": source_document.get(
                    "native_document_id_type"
                ),
            },
        }
        preserve_existing = False
    elif record_kind == "full_text_search_hit":
        native_document_id = _optional_text(record.get("native_document_id"))
        if native_document_id is None:
            return dict(record)
        native_entry_id = f"full_text_search_hit:{native_document_id}"
        event_date = _optional_text(record.get("indexed_date"))
        document = {
            "native_document_id": native_document_id,
            "document_type": (
                _optional_text(record.get("native_document_type"))
                or "official_opinion_full_text"
            ),
            "filed_date": event_date,
            "source_url": _optional_text(
                record.get("document_url", record.get("source_url"))
            ),
            "mime_type": _optional_text(record.get("mime_type")),
            "docket_entry_native_id": native_entry_id,
            "access_state": "public",
            "native_access_state": "official_full_text_search_hit",
            "wisconsin_full_text_occurrence": dict(record),
        }
        preserve_existing = True
    else:
        native_entry_id = _optional_text(record.get("native_guid")) or _required_text(
            record.get("canonical_ref"),
            "wisconsin_opinion.release.canonical_ref",
        )
        event_date = _optional_text(record.get("release_date"))
        preserve_existing = True

    caption = _optional_text(record.get("caption")) or (
        _optional_text(record.get("native_title"))
        if record_kind != "full_text_search_hit"
        else None
    )
    event_text = " | ".join(
        text
        for text in (
            caption,
            _optional_text(record.get("publication_status")),
            _optional_text(record.get("snippet")),
            _optional_text(record.get("source_title")),
        )
        if text
    )
    entry = {
        "native_entry_id": native_entry_id,
        "event_code": record_kind,
        "event_type": "appellate_publication",
        "raw_text": event_text or None,
        "filed_date": event_date,
        "event_date": event_date,
        "status": _optional_text(record.get("publication_status")),
        "document_available": document is not None,
        "access_state": "public",
        "native_access_state": (
            "official_incremental_release_feed"
            if record_kind == "opinion_release_notice"
            else "official_publication_index"
        ),
        "wisconsin_publication_occurrence": dict(record),
    }
    return {
        "source_id": WISCONSIN_OPINIONS_SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": (
            _optional_text(record.get("raw_case_number")) or case_number
        ),
        "source_internal_id": case_number,
        "caption": caption,
        "case_type": "appellate",
        "disposition_date": event_date,
        "status": _optional_text(record.get("publication_status")),
        "access_state": "public",
        "native_access_state": "official_appellate_publication_metadata",
        "certified_record": False,
        "source_url": (
            _optional_text(record.get("index_url"))
            or _optional_text(record.get("source_url"))
        ),
        "preserve_existing_case_fields": preserve_existing,
        "docket_entries": [entry],
        "documents": [document] if document is not None else [],
        "wisconsin_publication_occurrence": dict(record),
    }


def _dc_appellate_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project D.C. C-Track search hits and full cases into one case identity."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "case",
        "case_search_hit",
        "participant_search_hit",
    }:
        return dict(record)
    case_number = _optional_text(
        record.get("raw_case_number", record.get("appellate_case_number"))
    )
    if case_number is None:
        return dict(record)

    parties: list[dict[str, Any]] = []
    if record_kind == "participant_search_hit":
        participant_name = _optional_text(record.get("participant_name"))
        if participant_name:
            parties.append(
                {
                    "sequence_no": 1,
                    "role": (
                        _optional_text(record.get("appellate_role")) or "participant"
                    ),
                    "raw_name": participant_name,
                    "access_state": "public",
                    "native_access_state": "ctrack_participant_search_result",
                    "dc_ctrack_source_fields": dict(record),
                }
            )
    else:
        for value in _sequence(
            record.get("parties"),
            "dc_appellate.parties",
        ):
            party = _mapping(value, "dc_appellate.party")
            raw_name = _optional_text(party.get("party_name", party.get("raw_name")))
            if raw_name is None:
                continue
            attorneys = [
                {
                    "raw_name": attorney_name,
                    "bar_id": (
                        _optional_text(attorney.get("bar_number"))
                        or _optional_text(attorney.get("bar_id"))
                    ),
                    "firm_name": _optional_text(attorney.get("firm_name")),
                    "dc_ctrack_source_fields": dict(attorney),
                }
                for attorney_value in _sequence(
                    party.get("attorneys"),
                    "dc_appellate.party.attorneys",
                )
                for attorney in [
                    _mapping(attorney_value, "dc_appellate.party.attorney")
                ]
                for attorney_name in [_optional_text(attorney.get("name"))]
                if attorney_name is not None
            ]
            parties.append(
                {
                    "sequence_no": len(parties) + 1,
                    "role": (_optional_text(party.get("appellate_role")) or "party"),
                    "raw_name": raw_name,
                    "attorneys": attorneys,
                    "access_state": "public",
                    "native_access_state": "ctrack_public_party",
                    "dc_ctrack_source_fields": dict(party),
                }
            )

    docket_entries = [
        {
            "native_entry_id": native_event_id,
            "sequence_no": native_event_id,
            "event_code": (
                _optional_text(event.get("description")) or "appellate_docket_event"
            ),
            "event_type": "appellate_docket_event",
            "raw_text": " | ".join(
                value
                for value in (
                    _optional_text(event.get("description")),
                    _optional_text(event.get("result")),
                )
                if value
            )
            or None,
            "filed_date": _optional_text(event.get("event_date")),
            "event_date": _optional_text(event.get("event_date")),
            "status": _optional_text(event.get("status")),
            "document_available": bool(event.get("document_locator")),
            "access_state": "public",
            "native_access_state": (
                _optional_text(event.get("document_state"))
                or "ctrack_public_docket_event"
            ),
            "dc_ctrack_source_fields": dict(event),
        }
        for value in _sequence(
            record.get("docket_events"),
            "dc_appellate.docket_events",
        )
        for event in [_mapping(value, "dc_appellate.docket_event")]
        for native_event_id in [_optional_text(event.get("native_event_id"))]
        if native_event_id is not None
    ]
    known_event_ids = {entry["native_entry_id"] for entry in docket_entries}
    documents: list[dict[str, Any]] = []
    for value in _sequence(record.get("documents"), "dc_appellate.documents"):
        document = _mapping(value, "dc_appellate.document")
        native_document_id = _optional_text(document.get("native_document_id"))
        if native_document_id is None:
            continue
        projected_document: dict[str, Any] = {
            "native_document_id": native_document_id,
            "document_type": (
                _optional_text(document.get("document_title"))
                or "appellate_case_filing"
            ),
            "source_url": _optional_text(
                document.get("download_url", document.get("source_url"))
            ),
            "mime_type": _optional_text(document.get("mime_type")),
            "access_state": "public",
            "native_access_state": (
                _optional_text(document.get("access_state"))
                or "ctrack_source_linked_document"
            ),
            "dc_ctrack_source_fields": dict(document),
        }
        source_event_id = _optional_text(document.get("source_event_id"))
        if source_event_id in known_event_ids:
            projected_document["docket_entry_native_id"] = source_event_id
        documents.append(projected_document)

    originating_case_number = _optional_text(record.get("originating_case_number"))
    case_relations = (
        [
            {
                "relation_type": "originating_case_or_agency_matter",
                "raw_case_number": originating_case_number,
                "court_name": "D.C. Superior Court or originating agency",
                "court_level": "originating",
                "native_relation_id": (f"{case_number}:{originating_case_number}"),
                "source_url": _optional_text(record.get("source_url")),
                "access_state": "public",
                "dc_ctrack_source_routes": list(
                    _sequence(
                        record.get("related_source_routes"),
                        "dc_appellate.related_source_routes",
                    )
                ),
            }
        ]
        if originating_case_number
        else []
    )
    return {
        "source_id": DC_APPELLATE_CASES_SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": "us-dc-court-of-appeals",
            "native_court_id": "us-dc-court-of-appeals",
            "name": "District of Columbia Court of Appeals",
            "state_code": "DC",
            "court_level": "appellate",
            "official_url": _optional_text(record.get("source_url")),
        },
        "raw_case_number": case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number")) or case_number
        ),
        "source_internal_id": _optional_text(record.get("source_internal_id")),
        "caption": _optional_text(record.get("caption")),
        "case_type": (
            _optional_text(record.get("classification"))
            or _optional_text(record.get("case_subtype"))
            or _optional_text(record.get("case_type"))
        ),
        "filing_date": (
            _optional_text(record.get("filed_date"))
            or _optional_text(record.get("appeal_filed_date"))
        ),
        "status": _optional_text(record.get("status")),
        "access_state": "public",
        "native_access_state": (
            _optional_text(record.get("access_state")) or "ctrack_public_case_metadata"
        ),
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "preserve_existing_case_fields": record_kind != "case",
        "parties": parties,
        "docket_entries": docket_entries,
        "documents": documents,
        "case_relations": case_relations,
        "dc_ctrack_source_occurrence": dict(record),
    }


def _maryland_public_case_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one recent MDEC cases-filed report row."""

    if record.get("record_kind") != "recent_case_filing":
        return dict(record)
    case_number = _optional_text(record.get("case_number"))
    court_id = _optional_text(record.get("court_id"))
    court_name = _optional_text(record.get("court_name"))
    if case_number is None or court_id is None or court_name is None:
        return dict(record)

    parties = [
        {
            "sequence_no": index,
            "role": _optional_text(party.get("role")) or "party",
            "raw_name": published_name,
            "access_state": "public",
            "native_access_state": "source_published_recent_filing_party",
            "maryland_report_source_fields": dict(party),
        }
        for index, value in enumerate(
            _sequence(record.get("parties"), "maryland_public_cases.parties"),
            start=1,
        )
        for party in [_mapping(value, "maryland_public_cases.party")]
        for published_name in [_optional_text(party.get("published_name"))]
        if published_name is not None
    ]
    claims = [
        {
            "native_claim_id": (
                f"charge:{_optional_text(charge.get('charge_number')) or index}"
            ),
            "sequence_no": index,
            "claim_type": "criminal_charge",
            "claim_date": _optional_text(record.get("filing_date")),
            "status": "reported_at_filing",
            "limited_stub": True,
            "access_state": "public",
            "native_access_state": "source_published_charge_description",
            "description": _optional_text(charge.get("description")),
            "maryland_report_source_fields": dict(charge),
        }
        for index, value in enumerate(
            _sequence(record.get("charges"), "maryland_public_cases.charges"),
            start=1,
        )
        for charge in [_mapping(value, "maryland_public_cases.charge")]
    ]
    return {
        "source_id": MARYLAND_PUBLIC_CASES_SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": court_id,
            "native_court_id": court_id,
            "name": court_name,
            "state_code": "MD",
            "court_level": "trial",
            "official_url": _optional_text(record.get("source_document_url")),
        },
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": _optional_text(record.get("case_caption")),
        "case_type": _optional_text(record.get("case_type")),
        "filing_date": _optional_text(record.get("filing_date")),
        "access_state": "public",
        "native_access_state": "mdec_recent_cases_filed_report",
        "certified_record": False,
        "source_url": _optional_text(record.get("source_document_url")),
        "parties": parties,
        "claims": claims,
        "maryland_report_source_occurrence": dict(record),
    }


def _maryland_estate_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one Register of Wills estate row or docket occurrence."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "estate_case_index",
        "estate_case_detail",
        "estate_docket_event",
    }:
        return dict(record)
    estate_number = _optional_text(record.get("estate_number"))
    county = _optional_text(record.get("county"))
    court_id = _optional_text(record.get("court_id"))
    if estate_number is None or county is None or court_id is None:
        return dict(record)

    source_url = _optional_text(record.get("source_url"))
    decedent_name = _optional_text(record.get("decedent_name"))
    parties: list[dict[str, Any]] = []
    if decedent_name is not None:
        parties.append(
            {
                "sequence_no": len(parties) + 1,
                "role": "decedent",
                "raw_name": decedent_name,
                "entity_kind": "person",
                "access_state": "public",
                "native_access_state": "rownet_published_decedent",
            }
        )
    for alias_value in _sequence(
        record.get("aliases"),
        "maryland_estate.aliases",
    ):
        alias = _optional_text(alias_value)
        if alias is None:
            continue
        parties.append(
            {
                "sequence_no": len(parties) + 1,
                "role": "decedent_alias",
                "raw_name": alias,
                "entity_kind": "person",
                "access_state": "public",
                "native_access_state": "rownet_published_alias",
            }
        )
    for value in _sequence(
        record.get("personal_representatives"),
        "maryland_estate.personal_representatives",
    ):
        representative = _mapping(
            value,
            "maryland_estate.personal_representative",
        )
        name = _optional_text(representative.get("name"))
        if name is None:
            continue
        parties.append(
            {
                "sequence_no": len(parties) + 1,
                "role": (
                    _optional_text(representative.get("role"))
                    or "personal_representative"
                ),
                "raw_name": name,
                "access_state": "public",
                "native_access_state": ("rownet_published_personal_representative"),
                "published_address_raw": _optional_text(
                    representative.get("address_raw")
                ),
            }
        )

    attorneys = [
        {
            "raw_name": name,
            "maryland_estate_source_fields": dict(attorney),
        }
        for value in _sequence(
            record.get("attorneys"),
            "maryland_estate.attorneys",
        )
        for attorney in [_mapping(value, "maryland_estate.attorney")]
        for name in [_optional_text(attorney.get("name"))]
        if name is not None
    ]
    case_events = []
    for event_type, field_name in (
        ("decedent_date_of_death", "date_of_death"),
        ("estate_opened", "date_opened"),
        ("will_dated", "will_date"),
        ("will_probated", "probate_date"),
        ("estate_closed", "date_closed"),
    ):
        event_date = _optional_text(record.get(field_name))
        if event_date is None:
            continue
        case_events.append(
            {
                "native_event_id": f"{event_type}:{event_date}",
                "event_type": event_type,
                "event_date": event_date,
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "rownet_estate_detail",
            }
        )

    docket_entries: list[dict[str, Any]] = []
    if record_kind == "estate_docket_event":
        native_entry_id = (
            _optional_text(record.get("native_section_id"))
            or _optional_text(record.get("source_internal_id"))
            or _optional_text(record.get("canonical_ref"))
        )
        if native_entry_id is None:
            return dict(record)
        description = _optional_text(record.get("description"))
        docket_number = _optional_text(record.get("docket_number"))
        docket_code = _optional_text(record.get("docket_code"))
        page_count = record.get("page_count")
        raw_text = " | ".join(
            value
            for value in (
                docket_number,
                docket_code,
                description,
                f"{page_count} pages" if page_count is not None else None,
            )
            if value
        )
        docket_entries.append(
            {
                "native_entry_id": native_entry_id,
                "sequence_no": record.get("event_sequence"),
                "event_code": docket_code,
                "event_type": "estate_docket_event",
                "raw_text": raw_text or None,
                "filed_date": _optional_text(record.get("filed_on")),
                "event_date": _optional_text(record.get("filed_on")),
                "document_available": False,
                "access_state": "public",
                "native_access_state": "rownet_estate_docket_index",
                "copy_available": bool(record.get("copy_available")),
                "maryland_estate_source_fields": dict(record),
            }
        )

    estate_type = (
        None
        if record_kind == "estate_docket_event"
        else (
            _optional_text(record.get("estate_type_description"))
            or _optional_text(record.get("estate_type"))
            or "estate"
        )
    )
    return {
        "source_id": MARYLAND_ESTATE_SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": court_id,
            "native_court_id": court_id,
            "name": f"{county} Register of Wills",
            "state_code": "MD",
            "county_geoid": MARYLAND_ESTATE_COUNTY_GEOIDS.get(county),
            "court_level": "probate",
            "official_url": source_url,
        },
        "raw_case_number": estate_number,
        "display_case_number": estate_number,
        "caption": (
            f"Estate of {decedent_name}" if decedent_name is not None else None
        ),
        "case_type": estate_type,
        "filing_date": (
            _optional_text(record.get("filing_date"))
            or _optional_text(record.get("date_opened"))
        ),
        "disposition_date": _optional_text(record.get("date_closed")),
        "status": _optional_text(record.get("estate_status")),
        "access_state": "public",
        "native_access_state": (
            "rownet_estate_detail"
            if record_kind == "estate_case_detail"
            else "rownet_estate_index"
        ),
        "certified_record": False,
        "source_url": source_url,
        "preserve_existing_case_fields": (record_kind != "estate_case_detail"),
        "parties": parties,
        "attorneys": attorneys,
        "docket_entries": docket_entries,
        "case_events": case_events,
        "maryland_estate_source_occurrence": dict(record),
    }


def _maryland_judgment_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one judgment/lien index or detail event without merging events."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "judgment_lien_index_event",
        "judgment_lien_detail_event",
    }:
        return dict(record)
    case_number = _optional_text(record.get("case_number"))
    court_name = (
        _optional_text(record.get("court"))
        or _optional_text(record.get("county"))
        or "Maryland Circuit Court"
    )
    canonical_ref = _optional_text(record.get("canonical_ref"))
    if case_number is None or canonical_ref is None:
        return dict(record)
    court_slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        court_name.casefold(),
    ).strip("-")
    event_date = (
        _optional_text(record.get("event_date"))
        or _optional_text(record.get("entry_date"))
        or _optional_text(record.get("judgment_entered_date"))
    )
    names_for = [
        name
        for value in _sequence(
            record.get("names_for"),
            "maryland_judgment.names_for",
        )
        for name in [_optional_text(value)]
        if name is not None
    ]
    names_against = [
        name
        for value in _sequence(
            record.get("names_against"),
            "maryland_judgment.names_against",
        )
        for name in [_optional_text(value)]
        if name is not None
    ]
    parties = [
        {
            "sequence_no": index,
            "role": role,
            "raw_name": raw_name,
            "access_state": "public",
            "native_access_state": "judgment_index_name_label",
        }
        for index, (role, raw_name) in enumerate(
            [
                *(("name_for", name) for name in names_for),
                *(("name_against", name) for name in names_against),
            ],
            start=1,
        )
    ]
    amount_minor = record.get("judgment_amount_minor_units")
    event_kind = _optional_text(record.get("event_kind")) or record_kind
    raw_text = " | ".join(
        value
        for value in (
            event_kind,
            _optional_text(record.get("case_status", record.get("status"))),
            (
                f"amount {record.get('judgment_amount_raw')}"
                if record.get("judgment_amount_raw")
                else None
            ),
            (
                f"book/page {record.get('book_page')}"
                if record.get("book_page")
                else None
            ),
        )
        if value
    )
    return {
        "source_id": MARYLAND_JUDGMENT_LIENS_SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": f"us-md-{court_slug or 'circuit'}-circuit",
            "native_court_id": court_name,
            "name": court_name,
            "state_code": "MD",
            "court_level": "trial",
            "official_url": _optional_text(
                record.get("detail_url", record.get("source_result_url"))
            ),
        },
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "status": _optional_text(record.get("case_status", record.get("status"))),
        "access_state": "public",
        "native_access_state": "maryland_judgment_lien_public_index",
        "certified_record": False,
        "source_url": _optional_text(
            record.get("detail_url", record.get("source_result_url"))
        ),
        "preserve_existing_case_fields": True,
        "parties": parties,
        "docket_entries": [
            {
                "native_entry_id": canonical_ref,
                "sequence_no": _optional_text(record.get("event_sequence")),
                "event_code": event_kind,
                "event_type": "judgment_or_lien_event",
                "raw_text": raw_text or None,
                "filed_date": event_date,
                "event_date": event_date,
                "status": _optional_text(
                    record.get("case_status", record.get("status"))
                ),
                "document_available": False,
                "access_state": "public",
                "native_access_state": record_kind,
                "maryland_judgment_source_fields": dict(record),
            }
        ],
        "claims": [
            {
                "native_claim_id": canonical_ref,
                "sequence_no": record.get("event_sequence"),
                "claim_type": "judgment_or_lien_index_event",
                "claim_date": event_date,
                "claimant_raw": " / ".join(names_for) or None,
                "amount_minor": amount_minor,
                "currency": _optional_text(record.get("judgment_amount_currency")),
                "status": _optional_text(
                    record.get("case_status", record.get("status"))
                ),
                "limited_stub": True,
                "access_state": "public",
                "native_access_state": record_kind,
                "maryland_judgment_source_fields": dict(record),
            }
        ],
        "maryland_judgment_source_occurrence": dict(record),
    }


def _maryland_opinion_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a reported or unreported publication onto appellate case identity."""

    if _optional_text(record.get("record_kind")) != "appellate_disposition":
        return dict(record)
    case_number = _optional_text(
        record.get("raw_case_number", record.get("display_case_number"))
    )
    court_value = record.get("court")
    native_entry_id = _optional_text(record.get("native_entry_id"))
    if (
        case_number is None
        or native_entry_id is None
        or not isinstance(court_value, Mapping)
    ):
        return dict(record)

    court = dict(court_value)
    court.setdefault("native_court_id", court.get("court_id"))
    decision_date = _optional_text(
        record.get("decision_date", record.get("filed_date"))
    )
    publication_status = (
        _optional_text(record.get("publication_status")) or "appellate_publication"
    )
    publication_kind = (
        _optional_text(record.get("publication_kind")) or "appellate_opinion"
    )
    parties = [
        {
            "sequence_no": index,
            "role": _optional_text(party.get("role")) or "party",
            "raw_name": raw_name,
            "access_state": "public",
            "native_access_state": "official_unreported_opinion_index_party",
            "maryland_opinion_source_fields": dict(party),
        }
        for index, value in enumerate(
            _sequence(record.get("parties"), "maryland_opinion.parties"),
            start=1,
        )
        for party in [_mapping(value, "maryland_opinion.party")]
        for raw_name in [_optional_text(party.get("raw_name", party.get("name")))]
        if raw_name is not None
    ]

    document_value = record.get("document")
    document = dict(document_value) if isinstance(document_value, Mapping) else None
    if document is not None:
        document.update(
            {
                "access_state": "public",
                "native_access_state": (f"official_{publication_status}_appellate_pdf"),
                "maryland_publication_identity": {
                    "case_number": case_number,
                    "publication_status": publication_status,
                    "native_document_id": document.get("native_document_id"),
                },
            }
        )

    event_text = " | ".join(
        value
        for value in (
            _optional_text(record.get("caption")),
            _optional_text(record.get("citation")),
            _optional_text(record.get("filing_note")),
        )
        if value
    )
    docket_entry = {
        "native_entry_id": native_entry_id,
        "event_code": publication_kind,
        "event_type": "appellate_publication",
        "raw_text": event_text or None,
        "filed_date": decision_date,
        "event_date": decision_date,
        "judge": _optional_text(record.get("judge")),
        "status": publication_status,
        "document_available": document is not None,
        "access_state": "public",
        "native_access_state": (f"official_{publication_status}_appellate_index"),
        "publication_status": publication_status,
        "publication_kind": publication_kind,
        "full_text_status": record.get("full_text_status"),
        "citation": record.get("citation"),
        "correction_dates": record.get("correction_dates"),
        "source_date_raw": record.get("source_date_raw"),
        "index_url": record.get("index_url"),
        "provenance": record.get("provenance"),
        "maryland_opinion_source_occurrence": dict(record),
    }
    if document is not None:
        docket_entry["documents"] = [document]

    judge = _optional_text(record.get("judge"))
    return {
        "source_id": MARYLAND_OPINIONS_SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number")) or case_number
        ),
        "source_internal_id": case_number,
        "caption": _optional_text(record.get("caption")),
        "case_type": "appellate",
        "disposition_date": decision_date,
        "status": publication_status,
        "access_state": "public",
        "native_access_state": "official_appellate_publication_metadata",
        "certified_record": False,
        "source_url": (
            _optional_text(record.get("index_url"))
            or _optional_text(record.get("source_url"))
        ),
        "preserve_existing_case_fields": True,
        "parties": parties,
        "judicial_assignments": (
            [
                {
                    "raw_name": judge,
                    "assignment_role": "published_opinion_judge_or_author",
                    "effective_from": decision_date,
                }
            ]
            if judge
            else []
        ),
        "docket_entries": [docket_entry],
        "maryland_opinion_source_occurrence": dict(record),
    }


def _maryland_business_opinion_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project one selective trial publication onto each stated case identity."""

    if _optional_text(record.get("record_kind")) != "published_trial_court_opinion":
        return [dict(record)]
    publication_id = _optional_text(record.get("publication_designation"))
    court_value = record.get("court")
    if publication_id is None or not isinstance(court_value, Mapping):
        return [dict(record)]

    court = dict(court_value)
    court.setdefault("native_court_id", court.get("court_id"))
    provenance_value = record.get("provenance")
    provenance = dict(provenance_value) if isinstance(provenance_value, Mapping) else {}
    source_url = _optional_text(provenance.get("source_url"))
    court.setdefault("official_url", source_url)

    case_numbers = [
        value
        for item in _sequence(
            record.get("case_numbers_at_source"),
            "maryland_business_opinion.case_numbers_at_source",
        )
        for value in [_optional_text(item)]
        if value is not None
    ]
    primary_case_number = _optional_text(record.get("case_number"))
    if primary_case_number is not None and not case_numbers:
        case_numbers.append(primary_case_number)
    source_case_number_supplied = bool(case_numbers)
    if not case_numbers:
        case_numbers = [f"MDBT-PUBLICATION:{publication_id}"]

    filed_date = _optional_text(record.get("filed_date"))
    documents: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("documents"),
            "maryland_business_opinion.documents",
        ),
        start=1,
    ):
        source_document = _mapping(
            value,
            f"maryland_business_opinion.documents[{index - 1}]",
        )
        document_url = _required_text(
            source_document.get("source_url"),
            "maryland_business_opinion.document.source_url",
        )
        native_identity = (
            _optional_text(source_document.get("native_path")) or document_url
        )
        document = dict(source_document)
        document.update(
            {
                "native_document_id": (f"{publication_id}:{native_identity}"),
                "document_type": (
                    _optional_text(source_document.get("document_type"))
                    or "publication_document"
                ),
                "filed_date": filed_date,
                "source_url": document_url,
                "mime_type": _optional_text(
                    source_document.get(
                        "media_type",
                        source_document.get("mime_type"),
                    )
                ),
                "access_state": "public",
                "native_access_state": (
                    "official_business_technology_source_listed_attachment"
                ),
                "maryland_business_document_identity": {
                    "publication_designation": publication_id,
                    "exact_source_url": document_url,
                    "native_path": source_document.get("native_path"),
                    "source_link_state": source_document.get("source_link_state"),
                    "source_link_anomalies": source_document.get(
                        "source_link_anomalies"
                    ),
                },
            }
        )
        documents.append(document)

    source_notes = [
        value
        for item in _sequence(
            record.get("source_notes"),
            "maryland_business_opinion.source_notes",
        )
        for value in [_optional_text(item)]
        if value is not None
    ]
    event_text = " | ".join(
        value
        for value in (
            _optional_text(record.get("caption")),
            publication_id,
            _optional_text(record.get("counsel")),
            " / ".join(source_notes) or None,
        )
        if value
    )
    judge = _optional_text(record.get("judge"))
    projections: list[dict[str, Any]] = []
    for case_number in case_numbers:
        docket_entry = {
            "native_entry_id": publication_id,
            "event_code": "business_technology_publication",
            "event_type": "trial_court_publication",
            "raw_text": event_text,
            "filed_date": filed_date,
            "event_date": filed_date,
            "judge": judge,
            "status": "published",
            "document_available": bool(documents),
            "access_state": "public",
            "native_access_state": ("official_selective_trial_court_publication_index"),
            "publication_designation": publication_id,
            "publication_designation_at_source": record.get(
                "publication_designation_at_source"
            ),
            "publication_year": record.get("publication_year"),
            "publication_number": record.get("publication_number"),
            "date_precision": record.get("date_precision"),
            "source_omissions": record.get("source_omissions"),
            "source_link_anomalies": record.get("source_link_anomalies"),
            "provenance": provenance,
            "documents": [dict(document) for document in documents],
            "maryland_business_opinion_source_occurrence": dict(record),
        }
        projections.append(
            {
                "source_id": MARYLAND_BUSINESS_OPINIONS_SOURCE_ID,
                "record_kind": "case",
                "court": dict(court),
                "raw_case_number": case_number,
                "display_case_number": (
                    case_number if source_case_number_supplied else publication_id
                ),
                "source_internal_id": case_number,
                "caption": _optional_text(record.get("caption")),
                "case_type": "business_and_technology",
                "status": "published_trial_court_opinion",
                "access_state": "public",
                "native_access_state": (
                    "official_selective_trial_court_publication_metadata"
                ),
                "certified_record": False,
                "source_url": source_url,
                "preserve_existing_case_fields": True,
                "source_case_number_state": (
                    "supplied"
                    if source_case_number_supplied
                    else "omitted_publication_identity_fallback"
                ),
                "judicial_assignments": (
                    [
                        {
                            "raw_name": judge,
                            "assignment_role": (
                                "business_technology_publication_judge"
                            ),
                            "effective_from": filed_date,
                        }
                    ]
                    if judge
                    else []
                ),
                "docket_entries": [docket_entry],
                "maryland_business_opinion_source_occurrence": dict(record),
            }
        )
    return projections


def _new_jersey_tax_court_opinion_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project each opinion occurrence onto every source-visible docket."""

    record_type = _optional_text(record.get("record_type"))
    if record_type not in {
        "tax_court_opinion_index_entry",
        "tax_court_opinion_document",
    }:
        return [dict(record)]

    docket_numbers = [
        normalized
        for value in _sequence(
            record.get("docket_numbers"),
            "new_jersey_tax_court_opinion.docket_numbers",
        )
        for normalized in [_optional_text(value)]
        if normalized is not None
    ]
    if not docket_numbers:
        return [dict(record)]

    court_value = record.get("court")
    if isinstance(court_value, Mapping):
        court = dict(court_value)
    else:
        court = {
            "court_id": "nj-tax-court",
            "name": "Tax Court of New Jersey",
            "state_code": "NJ",
            "level": "trial",
        }
    court_id = _required_text(
        court.get("court_id"),
        "new_jersey_tax_court_opinion.court.court_id",
    )
    if court_id != "nj-tax-court":
        raise ValueError(
            "new_jersey_tax_court_opinion.court.court_id must be nj-tax-court"
        )
    court.setdefault("native_court_id", court_id)
    source_url = _required_text(
        record.get("source_url"),
        "new_jersey_tax_court_opinion.source_url",
    )
    court.setdefault("official_url", source_url)

    publication_status = (
        _optional_text(record.get("publication_status"))
        or "source_collection_not_stated"
    )
    title = _optional_text(record.get("title"))
    posted_date = _optional_text(record.get("posted_date"))
    document_value = record.get("document")
    index_document = (
        _mapping(document_value, "new_jersey_tax_court_opinion.document")
        if isinstance(document_value, Mapping)
        else None
    )

    documents: list[dict[str, Any]] = []
    if record_type == "tax_court_opinion_index_entry":
        if index_document is None:
            raise ValueError(
                "new_jersey_tax_court_opinion index entry must include document"
            )
        document_id = _required_text(
            index_document.get("document_id"),
            "new_jersey_tax_court_opinion.document.document_id",
        )
        document_url = _required_text(
            index_document.get("source_url"),
            "new_jersey_tax_court_opinion.document.source_url",
        )
        documents.append(
            {
                "native_document_id": document_id,
                "document_type": "tax_court_opinion",
                "filed_date": posted_date,
                "source_url": document_url,
                "mime_type": (
                    _optional_text(index_document.get("media_type"))
                    or "application/pdf"
                ),
                "access_state": "public",
                "native_access_state": "official_tax_court_opinion_index_link",
            }
        )
        occurrence = _mapping(
            record.get("index_entry"),
            "new_jersey_tax_court_opinion.index_entry",
        )
        occurrence_id = _required_text(
            occurrence.get("occurrence_id"),
            "new_jersey_tax_court_opinion.index_entry.occurrence_id",
        )
        summary_value = record.get("summary")
        summary = (
            _mapping(summary_value, "new_jersey_tax_court_opinion.summary")
            if isinstance(summary_value, Mapping)
            else {}
        )
        event_text = " | ".join(
            value
            for value in (
                title,
                _optional_text(record.get("docket_label_raw")),
                _optional_text(summary.get("text")),
            )
            if value
        )
        docket_entries = [
            {
                "native_entry_id": occurrence_id,
                "event_code": f"tax_court_opinion_{publication_status}",
                "event_type": "tax_court_opinion_index_occurrence",
                "raw_text": event_text or None,
                "filed_date": posted_date,
                "event_date": posted_date,
                "status": publication_status,
                "document_available": True,
                "access_state": "public",
                "native_access_state": (
                    f"official_tax_court_{publication_status}_opinion_index"
                ),
                "opinion_document_id": document_id,
                "opinion_document_url": document_url,
                "new_jersey_tax_court_opinion_source_occurrence": dict(record),
            }
        ]
        native_access_state = (
            f"official_tax_court_{publication_status}_opinion_index"
        )
    else:
        document_id = _required_text(
            record.get("document_id"),
            "new_jersey_tax_court_opinion.document_id",
        )
        content_hash_scope = _required_text(
            record.get("content_hash_scope"),
            "new_jersey_tax_court_opinion.content_hash_scope",
        )
        retrieval_transport = _required_text(
            record.get("retrieval_transport"),
            "new_jersey_tax_court_opinion.retrieval_transport",
        )
        native_access_state = (
            "official_tax_court_opinion_original_pdf"
            if content_hash_scope == "original_pdf_bytes"
            else "official_tax_court_opinion_reader_extracted_representation"
        )
        documents.append(
            {
                "native_document_id": document_id,
                "document_type": "tax_court_opinion",
                "source_url": source_url,
                "sha256": _required_text(
                    record.get("content_sha256"),
                    "new_jersey_tax_court_opinion.content_sha256",
                ),
                "mime_type": _required_text(
                    record.get("media_type"),
                    "new_jersey_tax_court_opinion.media_type",
                ),
                "page_count": record.get("page_count"),
                "storage_path": _optional_text(record.get("saved_path")),
                "ocr_status": (
                    "reader_extracted_text"
                    if content_hash_scope == "reader_extracted_text"
                    else None
                ),
                "certification_status": content_hash_scope,
                "access_state": "public",
                "native_access_state": native_access_state,
                "retrieval_transport": retrieval_transport,
                "content_hash_scope": content_hash_scope,
            }
        )
        docket_entries = []

    projections: list[dict[str, Any]] = []
    for docket_number in dict.fromkeys(docket_numbers):
        projections.append(
            {
                "source_id": NEW_JERSEY_TAX_COURT_OPINIONS_SOURCE_ID,
                "record_kind": "case",
                "court": dict(court),
                "raw_case_number": docket_number,
                "display_case_number": docket_number,
                "source_internal_id": docket_number,
                "caption": title,
                "case_type": "local_property_tax",
                "access_state": "public",
                "native_access_state": native_access_state,
                "certified_record": False,
                "source_url": source_url,
                "preserve_existing_case_fields": True,
                "docket_entries": [dict(entry) for entry in docket_entries],
                "documents": [dict(document) for document in documents],
                "new_jersey_tax_court_opinion_source_record": dict(record),
            }
        )
    return projections


def _washington_opinion_values(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return list(value)
    return [] if value is None else [value]


def _washington_opinion_case_numbers(
    record: Mapping[str, Any],
) -> list[str]:
    """Return every source-visible appellate docket in one opinion record."""

    fields_value = record.get("fields")
    fields = fields_value if isinstance(fields_value, Mapping) else {}
    values: list[Any] = []
    for candidate in (
        record.get("case_numbers"),
        record.get("case_number"),
        fields.get("docket_numbers"),
        fields.get("docket_number"),
    ):
        values.extend(_washington_opinion_values(candidate))

    case_numbers: list[str] = []
    for value in values:
        text = _optional_text(value)
        if text is None:
            continue
        for case_number in re.findall(
            r"(?<![\d,])((?:\d{1,3},\d{3}|\d{4,7})-\d)(?!\d)",
            text,
        ):
            if case_number not in case_numbers:
                case_numbers.append(case_number)
    return case_numbers


def _washington_opinion_date(record: Mapping[str, Any]) -> str | None:
    fields_value = record.get("fields")
    fields = fields_value if isinstance(fields_value, Mapping) else {}
    for candidate in (
        record.get("file_date"),
        record.get("publication_date"),
        fields.get("file_date"),
    ):
        text = _optional_text(candidate)
        if text is None:
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        try:
            return parsedate_to_datetime(text).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            pass
        for date_format in ("%b. %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, date_format).date().isoformat()
            except ValueError:
                continue
    return None


def _washington_opinion_filename(
    record: Mapping[str, Any],
) -> str | None:
    filename = _optional_text(record.get("opinion_filename"))
    if filename is not None:
        return filename
    for key in ("information_url", "source_url"):
        url = _optional_text(record.get(key))
        if url is None:
            continue
        filename = _optional_text(
            (parse_qs(urlsplit(url).query).get("filename") or [None])[0]
        )
        if filename is not None:
            return filename
    return None


def _washington_opinion_court(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    court_label = _optional_text(record.get("court"))
    division = _optional_text(record.get("division"))
    court_level_code = _optional_text(record.get("court_level_code"))
    normalized_label = (court_label or "").casefold()

    division_key: str | None = None
    for key, aliases in {
        "i": ("i", "1", "division i", "division 1"),
        "ii": ("ii", "2", "division ii", "division 2"),
        "iii": ("iii", "3", "division iii", "division 3"),
    }.items():
        division_at_source = (division or "").strip().casefold()
        if division_at_source in aliases or re.search(
            rf"\bdivision\s+(?:{key}|{aliases[1]})\b",
            normalized_label,
        ):
            division_key = key
            break

    if "supreme court" in normalized_label or court_level_code == "S":
        court_id = "wa-supreme-court"
        name = "Washington Supreme Court"
        native_court_id = "S"
        division_name = None
    elif division_key is not None:
        court_id = f"wa-court-of-appeals-division-{division_key}"
        division_name = f"Division {division_key.upper()}"
        name = f"Washington Court of Appeals {division_name}"
        native_court_id = division_name
    elif "court of appeals" in normalized_label or court_level_code == "C":
        court_id = "wa-court-of-appeals"
        name = "Washington Court of Appeals"
        native_court_id = "C"
        division_name = division
    else:
        court_id = "wa-appellate-courts"
        name = "Washington Appellate Courts"
        native_court_id = "statewide-appellate-opinion-index"
        division_name = division

    return {
        "court_id": court_id,
        "native_court_id": native_court_id,
        "name": name,
        "state_code": "WA",
        "court_level": "appellate",
        "division": division_name,
        "official_url": (
            _optional_text(record.get("information_url"))
            or _optional_text(record.get("source_url"))
        ),
    }


def _washington_opinion_document_id(
    document_kind: str,
    *,
    url: str,
    filename: str | None,
) -> str:
    if document_kind == "information" and filename is not None:
        source_key = filename
    else:
        source_key = Path(urlsplit(url).path).name
        if not source_key:
            source_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return f"wa-opinion-{document_kind}:{source_key}"


def _washington_opinion_documents(
    record: Mapping[str, Any],
    *,
    filed_date: str | None,
) -> list[dict[str, Any]]:
    record_kind = _optional_text(record.get("record_kind"))
    filename = _washington_opinion_filename(record)
    documents: list[dict[str, Any]] = []

    information_url = _optional_text(record.get("information_url"))
    information_sha256: str | None = None
    if record_kind == "appellate_opinion_information":
        information_url = _optional_text(record.get("source_url"))
        information_sha256 = _optional_text(
            record.get("source_document_sha256")
        )
    elif record_kind == "appellate_opinion_pdf_artifact":
        information_sha256 = _optional_text(record.get("information_sha256"))

    if information_url is not None:
        documents.append(
            {
                "native_document_id": _washington_opinion_document_id(
                    "information",
                    url=information_url,
                    filename=filename,
                ),
                "document_type": "appellate_opinion_information_page",
                "filed_date": filed_date,
                "source_url": information_url,
                "sha256": information_sha256,
                "mime_type": "text/html",
                "access_state": "public",
                "native_access_state": (
                    "official_appellate_opinion_information_page_bytes"
                    if information_sha256 is not None
                    else "official_appellate_opinion_information_page_link"
                ),
            }
        )

    pdf_urls: list[str] = []
    for value in _washington_opinion_values(record.get("pdf_urls")):
        url = _optional_text(value)
        if url is not None and url not in pdf_urls:
            pdf_urls.append(url)
    pdf_url = _optional_text(record.get("pdf_url"))
    if pdf_url is not None and pdf_url not in pdf_urls:
        pdf_urls.append(pdf_url)
    if record_kind == "appellate_opinion_pdf_artifact":
        artifact_url = _optional_text(record.get("source_url"))
        if artifact_url is not None and artifact_url not in pdf_urls:
            pdf_urls.append(artifact_url)

    for url in pdf_urls:
        is_retrieved_artifact = (
            record_kind == "appellate_opinion_pdf_artifact"
            and url == _optional_text(record.get("source_url"))
        )
        documents.append(
            {
                "native_document_id": _washington_opinion_document_id(
                    "pdf",
                    url=url,
                    filename=filename,
                ),
                "document_type": "appellate_opinion",
                "filed_date": filed_date,
                "source_url": url,
                "sha256": (
                    _optional_text(record.get("sha256"))
                    if is_retrieved_artifact
                    else None
                ),
                "mime_type": (
                    _optional_text(record.get("media_type"))
                    if is_retrieved_artifact
                    else "application/pdf"
                ),
                "storage_path": (
                    _optional_text(record.get("artifact_path"))
                    if is_retrieved_artifact
                    else None
                ),
                "access_state": "public",
                "native_access_state": (
                    "official_appellate_opinion_pdf_bytes"
                    if is_retrieved_artifact
                    else "official_appellate_opinion_pdf_link"
                ),
            }
        )
    return documents


def _washington_opinion_occurrence_id(
    record: Mapping[str, Any],
) -> str:
    occurrence_identity = {
        "record_kind": record.get("record_kind"),
        "opinion_filename": _washington_opinion_filename(record),
        "feed_id": record.get("feed_id"),
        "list_scope": record.get("list_scope"),
        "list_year": record.get("list_year"),
        "court_level_code": record.get("court_level_code"),
        "publication_status_code": record.get("publication_status_code"),
        "route_provenance": record.get("route_provenance"),
        "canonical_ref": record.get("canonical_ref"),
    }
    digest = hashlib.sha256(
        _json(occurrence_identity).encode("utf-8")
    ).hexdigest()
    return f"wa-opinion-occurrence:{digest}"


def _washington_opinion_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project an opinion record onto each docket without merging publications."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "appellate_opinion",
        "appellate_opinion_information",
        "appellate_opinion_pdf_artifact",
    }:
        return [dict(record)]
    case_numbers = _washington_opinion_case_numbers(record)
    if not case_numbers:
        return [dict(record)]

    fields_value = record.get("fields")
    fields = fields_value if isinstance(fields_value, Mapping) else {}
    caption = (
        _optional_text(record.get("caption"))
        or _optional_text(fields.get("title_of_case"))
    )
    filed_date = _washington_opinion_date(record)
    source_url = (
        _optional_text(record.get("information_url"))
        or _optional_text(record.get("source_url"))
    )
    publication_status = (
        _optional_text(record.get("publication_status"))
        or _optional_text(record.get("publication_status_code"))
        or _optional_text(record.get("publication_notice"))
        or "appellate_opinion"
    )
    documents = _washington_opinion_documents(
        record,
        filed_date=filed_date,
    )

    docket_entries: list[dict[str, Any]] = []
    if record_kind != "appellate_opinion_pdf_artifact":
        event_text = " | ".join(
            value
            for value in (
                caption,
                _optional_text(record.get("file_contains")),
                _optional_text(record.get("publication_notice")),
            )
            if value
        )
        docket_entries.append(
            {
                "native_entry_id": _washington_opinion_occurrence_id(record),
                "event_code": record_kind,
                "event_type": "appellate_opinion_publication",
                "raw_text": event_text or None,
                "filed_date": filed_date,
                "event_date": filed_date,
                "status": publication_status,
                "document_available": bool(documents),
                "access_state": "public",
                "native_access_state": (
                    "official_appellate_opinion_information_page"
                    if record_kind == "appellate_opinion_information"
                    else "official_appellate_opinion_index_occurrence"
                ),
                "information_url": record.get("information_url"),
                "pdf_urls": [
                    document["source_url"]
                    for document in documents
                    if document["document_type"] == "appellate_opinion"
                ],
                "washington_opinion_source_occurrence": dict(record),
            }
        )

    assignments: list[dict[str, Any]] = []
    for field_name, role in (
        ("authored_by", "opinion_author"),
        ("concurring", "opinion_concurrence"),
    ):
        for value in _washington_opinion_values(fields.get(field_name)):
            judge = _optional_text(value)
            if judge is None:
                continue
            assignments.append(
                {
                    "raw_name": judge,
                    "assignment_role": role,
                    "effective_from": filed_date,
                }
            )

    court = _washington_opinion_court(record)
    return [
        {
            "source_id": WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID,
            "record_kind": "case",
            "court": dict(court),
            "raw_case_number": case_number,
            "display_case_number": case_number,
            "source_internal_id": case_number,
            "caption": caption,
            "case_type": "appellate",
            "disposition_date": filed_date,
            "status": publication_status,
            "access_state": "public",
            "native_access_state": "official_appellate_opinion_publication",
            "certified_record": False,
            "source_url": source_url,
            "preserve_existing_case_fields": True,
            "judicial_assignments": [
                dict(assignment) for assignment in assignments
            ],
            "docket_entries": [dict(entry) for entry in docket_entries],
            "documents": [dict(document) for document in documents],
            "washington_opinion_source_record": dict(record),
        }
        for case_number in case_numbers
    ]


def _new_jersey_tax_court_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one report row without collapsing property occurrences."""

    if (
        _optional_text(record.get("record_type"))
        != "tax_court_property_case_parcel_row"
    ):
        return dict(record)
    case = _mapping(record.get("case"), "new_jersey_tax_court.case")
    property_data = _mapping(
        record.get("property"),
        "new_jersey_tax_court.property",
    )
    dataset = _mapping(
        record.get("dataset"),
        "new_jersey_tax_court.dataset",
    )
    source_record = _mapping(
        record.get("source_record"),
        "new_jersey_tax_court.source_record",
    )
    docket_number = _required_text(
        case.get("docket_number_raw"),
        "new_jersey_tax_court.case.docket_number_raw",
    )
    occurrence_id = _required_text(
        record.get("source_occurrence_id"),
        "new_jersey_tax_court.source_occurrence_id",
    )
    entered_value = case.get("entered_date")
    entered = (
        _mapping(
            entered_value,
            "new_jersey_tax_court.case.entered_date",
        )
        if isinstance(entered_value, Mapping)
        else {}
    )
    entered_date = _optional_text(entered.get("iso"))
    dataset_id = _required_text(
        dataset.get("id"),
        "new_jersey_tax_court.dataset.id",
    )
    county = _optional_text(property_data.get("county_name"))
    property_labels = [
        value
        for value in (
            f"county {county}" if county else None,
            (
                f"block {property_data.get('block')}"
                if property_data.get("block")
                else None
            ),
            (f"lot {property_data.get('lot')}" if property_data.get("lot") else None),
            (
                f"unit {property_data.get('unit')}"
                if property_data.get("unit")
                else None
            ),
            (
                f"assessment year {property_data.get('assessment_year_raw')}"
                if property_data.get("assessment_year_raw")
                else None
            ),
        )
        if value
    ]
    caption = _optional_text(case.get("title"))
    raw_text = " | ".join(
        value
        for value in (
            caption,
            _optional_text(dataset.get("label")) or dataset_id,
            *property_labels,
        )
        if value
    )
    source_url = (
        _optional_text(source_record.get("landing_url"))
        or _optional_text(source_record.get("artifact_url"))
        or "https://www.njcourts.gov/courts/tax/docketed-cases"
    )
    docket_entry = {
        "native_entry_id": occurrence_id,
        "sequence_no": source_record.get("row_number"),
        "event_code": f"tax_court_{dataset_id}_report_row",
        "event_type": "tax_court_property_case_report_occurrence",
        "raw_text": raw_text or None,
        "filed_date": entered_date,
        "entered_date": entered_date,
        "event_date": entered_date,
        "location": county,
        "document_available": False,
        "access_state": "public",
        "native_access_state": "official_current_tax_court_report_row",
        "dataset": dict(dataset),
        "property_components": dict(property_data),
        "normalization_issues": record.get("normalization_issues"),
        "source_record": dict(source_record),
        "new_jersey_tax_court_source_occurrence": dict(record),
    }
    return {
        "source_id": NEW_JERSEY_TAX_COURT_SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": "nj-tax-court",
            "native_court_id": "nj-tax-court",
            "name": "New Jersey Tax Court",
            "state_code": "NJ",
            "court_level": "trial",
            "official_url": source_url,
        },
        "raw_case_number": docket_number,
        "display_case_number": (
            _optional_text(case.get("docket_number")) or docket_number
        ),
        "source_internal_id": docket_number,
        "caption": caption,
        "case_type": "local_property_tax",
        "filing_date": entered_date,
        "status": None,
        "access_state": "public",
        "native_access_state": "official_current_tax_court_report",
        "certified_record": False,
        "source_url": source_url,
        "preserve_existing_case_fields": True,
        "docket_entries": [docket_entry],
        "new_jersey_tax_court_source_occurrence": dict(record),
    }


def _va_general_district_court(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one court component without assigning geographic semantics."""

    source_code = _required_text(
        record.get("court_source_code"),
        "va_general_district.court_source_code",
    )
    if re.fullmatch(r"\d{3}", source_code) is None:
        raise ValueError(
            "va_general_district.court_source_code must be a three-digit "
            "application court-component code"
        )
    court_id = _required_text(
        record.get("court_id"),
        "va_general_district.court_id",
    )
    if court_id != f"va-gdc-{source_code}":
        raise ValueError(
            "va_general_district court_id does not match court_source_code"
        )
    return {
        "court_id": court_id,
        "native_court_id": source_code,
        "name": _required_text(
            record.get("court_name"),
            "va_general_district.court_name",
        ),
        "state_code": "VA",
        "court_level": "general_district",
        "official_url": (
            _optional_text(record.get("source_url"))
            or "https://eapps.courts.state.va.us/gdcourts/landing.do?landing=landing"
        ),
    }


def _va_general_district_row_values(
    row: Mapping[str, Any],
    field_name: str,
) -> Mapping[str, Any]:
    return _mapping(row.get("values"), f"{field_name}.values")


def _va_general_district_raw_text(row: Mapping[str, Any]) -> str | None:
    source_values = row.get("source_values")
    if not isinstance(source_values, Mapping):
        return None
    return (
        " | ".join(
            value
            for value in (
                _optional_text(source_value) for source_value in source_values.values()
            )
            if value
        )
        or None
    )


def _va_general_district_entry_id(
    kind: str,
    identity: Mapping[str, Any],
) -> str:
    digest = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()
    return f"va-gdc:{kind}:{digest}"


def _va_general_district_docket_entries(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    section_states = _mapping(
        record.get("section_states"),
        "va_general_district.section_states",
    )
    for index, value in enumerate(
        _sequence(record.get("hearings"), "va_general_district.hearings"),
        start=1,
    ):
        row = _mapping(value, f"va_general_district.hearings[{index - 1}]")
        values = _va_general_district_row_values(
            row,
            f"va_general_district.hearings[{index - 1}]",
        )
        identity = {
            "case_number": record.get("raw_case_number"),
            "sequence": index,
            "date": values.get("date"),
            "time": values.get("time"),
            "hearing_type": values.get("hearing_type"),
            "courtroom": values.get("courtroom"),
        }
        entries.append(
            {
                "native_entry_id": _va_general_district_entry_id(
                    "hearing",
                    identity,
                ),
                "sequence_no": index,
                "event_code": "hearing",
                "event_type": "hearing",
                "raw_text": _va_general_district_raw_text(row),
                "event_date": _optional_text(values.get("date_iso")),
                "event_time": _optional_text(values.get("time")),
                "location": _optional_text(values.get("courtroom")),
                "status": _optional_text(values.get("result")),
                "document_available": False,
                "access_state": "public",
                "native_access_state": "published_case_information_section",
                "section_state": section_states.get("hearing_information"),
                "hearing_type": values.get("hearing_type"),
                "source_row": dict(row),
            }
        )
    for index, value in enumerate(
        _sequence(
            record.get("service_process"),
            "va_general_district.service_process",
        ),
        start=1,
    ):
        row = _mapping(
            value,
            f"va_general_district.service_process[{index - 1}]",
        )
        values = _va_general_district_row_values(
            row,
            f"va_general_district.service_process[{index - 1}]",
        )
        identity = {
            "case_number": record.get("raw_case_number"),
            "sequence": index,
            "person_served": values.get("person_served"),
            "process_type": values.get("process_type"),
            "date_issued": values.get("date_issued"),
            "plaintiff": values.get("plaintiff"),
        }
        entries.append(
            {
                "native_entry_id": _va_general_district_entry_id(
                    "service-process",
                    identity,
                ),
                "sequence_no": index,
                "event_code": "service_process",
                "event_type": "service_process",
                "raw_text": _va_general_district_raw_text(row),
                "event_date": (
                    _optional_text(values.get("date_served_iso"))
                    or _optional_text(values.get("date_issued_iso"))
                ),
                "status": _optional_text(values.get("how_served")),
                "document_available": False,
                "access_state": "public",
                "native_access_state": "published_case_information_section",
                "section_state": section_states.get("service_process"),
                "source_row": dict(row),
            }
        )
    return entries


def _va_general_district_parties(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project only names whose source section states an explicit party role."""

    parties: list[dict[str, Any]] = []
    if _optional_text(record.get("division_code")) == "V":
        role_fields = (
            ("plaintiff", "plaintiffs"),
            ("defendant", "defendants"),
        )
        for role, field in role_fields:
            for value in _sequence(
                record.get(field),
                f"va_general_district.{field}",
            ):
                row = _mapping(value, f"va_general_district.{field}[]")
                values = _va_general_district_row_values(
                    row,
                    f"va_general_district.{field}[]",
                )
                raw_name = _optional_text(values.get("name"))
                if raw_name is None:
                    continue
                parties.append(
                    {
                        "sequence_no": len(parties) + 1,
                        "role": role,
                        "raw_name": raw_name,
                    }
                )
    else:
        defendant = record.get("defendant")
        if isinstance(defendant, Mapping):
            raw_name = _optional_text(defendant.get("name"))
            if raw_name is not None:
                parties.append(
                    {
                        "sequence_no": 1,
                        "role": "defendant",
                        "raw_name": raw_name,
                    }
                )
    return parties


def _va_general_district_search_projection(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Link one search row to a case without promoting candidate semantics."""

    occurrence_identity = {
        "query_role": record.get("query_role"),
        "court_id": record.get("court_id"),
        "raw_case_number": record.get("raw_case_number"),
        "source_native_page": record.get("source_native_page"),
        "source_native_row": record.get("source_native_row"),
        "source_values": record.get("source_values"),
    }
    source_result_id = _va_general_district_entry_id(
        "search-result",
        occurrence_identity,
    )
    occurrence = {
        "source_id": VA_GENERAL_DISTRICT_SOURCE_ID,
        "source_result_id": source_result_id,
        "record_kind": "case_search_hit",
        "canonical_ref": record.get("canonical_ref"),
        "source_url": record.get("source_url"),
        "query_role": record.get("query_role"),
        "court_source_code": record.get("court_source_code"),
        "source_native_page": record.get("source_native_page"),
        "source_native_row": record.get("source_native_row"),
        "source_values": record.get("source_values"),
        "values": record.get("values"),
        "source_detail_locator": record.get("source_detail_locator"),
        "search_metadata": record.get("search_metadata"),
    }
    return {
        "source_id": VA_GENERAL_DISTRICT_SOURCE_ID,
        "record_kind": "case_search_hit",
        "court": _va_general_district_court(record),
        "raw_case_number": _required_text(
            record.get("raw_case_number"),
            "va_general_district.raw_case_number",
        ),
        "access_state": "public",
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "identity_crosswalk_only": True,
        "identity_source_occurrence": occurrence,
        "court_source_code": record.get("court_source_code"),
        "division_code": record.get("division_code"),
        "source_record": dict(record),
    }


def _va_general_district_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project Virginia GDC search occurrences and full case metadata."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind == "case_search_hit":
        return _va_general_district_search_projection(record)
    if record_kind != "case":
        return dict(record)

    division = _required_text(
        record.get("division_code"),
        "va_general_district.division_code",
    )
    if division not in {"V", "T"}:
        raise ValueError("va_general_district.division_code must be V or T")
    case_type = _optional_text(record.get("case_type"))
    if division == "T":
        charge = record.get("charge")
        if isinstance(charge, Mapping):
            case_type = _optional_text(charge.get("case_type"))
    section_states = _mapping(
        record.get("section_states"),
        "va_general_district.section_states",
    )
    document_access = _mapping(
        record.get("document_access"),
        "va_general_district.document_access",
    )
    return {
        "source_id": VA_GENERAL_DISTRICT_SOURCE_ID,
        "record_kind": "case",
        "court": _va_general_district_court(record),
        "raw_case_number": _required_text(
            record.get("raw_case_number"),
            "va_general_district.raw_case_number",
        ),
        "display_case_number": _optional_text(record.get("raw_case_number")),
        "caption": None,
        "case_type": case_type,
        "filing_date": _optional_text(record.get("filed_date_iso")),
        "status": None,
        "access_state": "public",
        "native_access_state": "published_case_information",
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "parties": _va_general_district_parties(record),
        "docket_entries": _va_general_district_docket_entries(record),
        "documents": [],
        "court_source_code": record.get("court_source_code"),
        "court_source_code_semantics": (
            "source-published application court-component identifier"
        ),
        "division_code": division,
        "division_name": record.get("division_name"),
        "case_data_status_code": record.get("case_data_status_code"),
        "case_data_status": record.get("case_data_status"),
        "section_states": dict(section_states),
        "sections": record.get("sections"),
        "document_access": dict(document_access),
        "date_of_birth_at_source": record.get("date_of_birth_at_source"),
        "date_of_birth_state": record.get("date_of_birth_state"),
        "source_record": dict(record),
    }


def _michigan_appellate_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project Michigan case, opinion, and order rows onto case identity."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "appellate_case_index",
        "appellate_opinion",
        "appellate_order",
    }:
        return dict(record)
    if record.get("case_number_resolved") is not True:
        return dict(record)
    case_number = _optional_text(record.get("raw_case_number"))
    court_value = record.get("court")
    if case_number is None or not isinstance(court_value, Mapping):
        return dict(record)

    court = dict(court_value)
    court.setdefault("native_court_id", court.get("court_id"))
    court.setdefault(
        "official_url",
        _optional_text(record.get("case_url", record.get("source_url"))),
    )
    event_date = _optional_text(record.get("filing_or_release_date"))
    source_url = _optional_text(record.get("case_url")) or _optional_text(
        record.get("source_url")
    )
    attorneys = [
        {
            "raw_name": raw_name,
            "bar_id": (
                _optional_text(attorney.get("bar_number"))
                or _optional_text(attorney.get("p_number"))
            ),
            "michigan_appellate_source_fields": dict(attorney),
        }
        for value in _sequence(
            record.get("attorneys"),
            "michigan_appellate.attorneys",
        )
        for attorney in [_mapping(value, "michigan_appellate.attorney")]
        for raw_name in [_optional_text(attorney.get("name"))]
        if raw_name is not None
    ]
    projected: dict[str, Any] = {
        "source_id": MICHIGAN_APPELLATE_SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": _optional_text(record.get("caption")),
        "case_type": "appellate",
        "filing_date": (event_date if record_kind == "appellate_case_index" else None),
        "disposition_date": (
            event_date if record_kind != "appellate_case_index" else None
        ),
        "status": (
            _optional_text(record.get("case_status"))
            or _optional_text(record.get("decision"))
        ),
        "access_state": "public",
        "native_access_state": "official_appellate_search_result",
        "certified_record": False,
        "source_url": source_url,
        "attorneys": attorneys,
        "michigan_appellate_source_occurrence": dict(record),
    }
    if record_kind == "appellate_case_index":
        return projected

    document_value = record.get("document")
    document = dict(document_value) if isinstance(document_value, Mapping) else None
    native_document_id = (
        _optional_text(document.get("native_document_id"))
        if document is not None
        else None
    )
    canonical_ref = _optional_text(record.get("canonical_ref"))
    native_entry_id = (
        f"{record_kind}:{native_document_id}"
        if native_document_id is not None
        else canonical_ref
    )
    if native_entry_id is None:
        return dict(record)
    event_status = _optional_text(record.get("decision")) or _optional_text(
        record.get("case_status")
    )
    docket_entry = {
        "native_entry_id": native_entry_id,
        "event_code": record_kind,
        "event_type": "appellate_publication",
        "raw_text": " | ".join(
            value
            for value in (
                _optional_text(record.get("caption")),
                event_status,
            )
            if value
        )
        or None,
        "filed_date": event_date,
        "event_date": event_date,
        "status": event_status,
        "document_available": document is not None,
        "access_state": "public",
        "native_access_state": "official_appellate_publication_index",
        "michigan_appellate_source_fields": dict(record),
    }
    projected["preserve_existing_case_fields"] = True
    projected["docket_entries"] = [docket_entry]
    if document is not None and native_document_id is not None:
        document.update(
            {
                "docket_entry_native_id": native_entry_id,
                "access_state": "public",
                "native_access_state": "official_appellate_pdf",
                "michigan_appellate_publication_identity": {
                    "record_kind": record_kind,
                    "case_number": case_number,
                    "native_document_id": native_document_id,
                },
            }
        )
        projected["documents"] = [document]
    return projected


def _michigan_business_court_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project a publication row without inventing a trial-court assignment."""

    if (
        _optional_text(record.get("record_kind"))
        != "business_court_document_search_occurrence"
    ):
        return []

    source_occurrence_id = _required_text(
        record.get("source_occurrence_id"),
        "michigan_business_court.source_occurrence_id",
    )
    document = _mapping(
        record.get("document"),
        "michigan_business_court.document",
    )
    native_document_id = _required_text(
        document.get("native_document_id"),
        "michigan_business_court.document.native_document_id",
    )
    document_url = _required_text(
        document.get("source_url"),
        "michigan_business_court.document.source_url",
    )
    record_source_url = (
        _optional_text(record.get("source_url")) or document_url
    )

    observation_value = record.get("case_number_observation")
    raw_case_label: str | None = None
    candidate_basis = "source_caseNumber_label"
    candidates: list[str] = []
    if observation_value is not None:
        observation = _mapping(
            observation_value,
            "michigan_business_court.case_number_observation",
        )
        raw_case_label = _optional_text(observation.get("raw"))
        candidate_basis = (
            _optional_text(observation.get("candidate_basis"))
            or candidate_basis
        )
        for index, value in enumerate(
            _sequence(
                observation.get("candidates"),
                "michigan_business_court.case_number_observation.candidates",
            )
        ):
            candidate = _required_text(
                value,
                "michigan_business_court."
                f"case_number_observation.candidates[{index}]",
            )
            if candidate not in candidates:
                candidates.append(candidate)

    publication_date = _optional_text(record.get("pleading_or_order_date"))
    case_name = _optional_text(record.get("case_name_observation"))
    title = _optional_text(record.get("title"))
    source_row = _mapping(
        record.get("source_row"),
        "michigan_business_court.source_row",
    )
    source_omissions = [
        field_name
        for field_name, value in (
            ("pleadingOrderDate", publication_date),
            ("caseName", case_name),
            ("caseNumber", raw_case_label),
        )
        if value is None
    ]
    court = {
        "court_id": MICHIGAN_BUSINESS_COURT_COLLECTION_ID,
        "native_court_id": MICHIGAN_BUSINESS_COURT_COLLECTION_ID,
        "name": "Michigan Business Court Document Collection",
        "state_code": "MI",
        "court_level": "trial_publication_collection",
        "official_url": (
            "https://www.courts.michigan.gov/business-court-search/"
        ),
    }
    document_projection = {
        "native_document_id": native_document_id,
        "document_type": "business_court_document",
        "filed_date": publication_date,
        "source_url": document_url,
        "mime_type": (
            _optional_text(document.get("mime_type")) or "application/pdf"
        ),
        "access_state": "public",
        "native_access_state": "official_business_court_pdf_link",
        "michigan_business_court_document_identity": dict(document),
    }
    event_text = " | ".join(
        value for value in (title, case_name, raw_case_label) if value
    )

    case_identities = (
        [
            {
                "raw_case_number": candidate,
                "display_case_number": candidate,
                "identity_state": "source_case_number_candidate",
                "candidate": candidate,
                "candidate_index": index,
            }
            for index, candidate in enumerate(candidates, start=1)
        ]
        if candidates
        else [
            {
                "raw_case_number": (
                    f"MI-BUSINESS-DOCUMENT:{native_document_id}"
                ),
                "display_case_number": native_document_id,
                "identity_state": "document_identity_fallback",
                "candidate": None,
                "candidate_index": None,
            }
        ]
    )

    projections: list[dict[str, Any]] = []
    for identity in case_identities:
        identity_state = str(identity["identity_state"])
        candidate = identity["candidate"]
        occurrence_qualifier = hashlib.sha256(
            _json(
                {
                    "identity_state": identity_state,
                    "candidate": candidate,
                    "native_document_id": native_document_id,
                }
            ).encode("utf-8")
        ).hexdigest()[:16]
        qualified_occurrence_id = (
            f"{source_occurrence_id}:{identity_state}:{occurrence_qualifier}"
        )
        source_occurrence = {
            **dict(record),
            "source_result_id": qualified_occurrence_id,
            "source_internal_id": source_occurrence_id,
            "filing_date": publication_date,
            "source_url": record_source_url,
            "case_candidate_projection": {
                "identity_state": identity_state,
                "candidate": candidate,
                "candidate_index": identity["candidate_index"],
                "candidate_basis": candidate_basis,
                "canonical_trial_case_asserted": False,
            },
        }
        docket_entry = {
            "native_entry_id": f"search-occurrence:{source_occurrence_id}",
            "event_code": "business_court_document_search_occurrence",
            "event_type": "trial_court_publication_index_occurrence",
            "raw_text": event_text or None,
            "filed_date": publication_date,
            "event_date": publication_date,
            "status": "published_in_business_court_collection",
            "document_available": True,
            "access_state": "public",
            "native_access_state": (
                "official_business_court_document_search_row"
            ),
            "source_occurrence_id": source_occurrence_id,
            "native_page": source_row.get("native_page"),
            "native_row": source_row.get("native_row"),
            "michigan_business_court_source_occurrence": dict(record),
        }
        projections.append(
            {
                "source_id": MICHIGAN_BUSINESS_COURT_SOURCE_ID,
                "record_kind": "case",
                "court": dict(court),
                "raw_case_number": identity["raw_case_number"],
                "display_case_number": identity["display_case_number"],
                "source_internal_id": (
                    f"{identity_state}:{identity['raw_case_number']}"
                ),
                "caption": case_name,
                "case_type": "business_court_publication_candidate",
                "access_state": "public",
                "native_access_state": (
                    "official_business_court_document_collection"
                ),
                "certified_record": False,
                "source_url": record_source_url,
                "preserve_existing_case_fields": True,
                "source_occurrences": [source_occurrence],
                "docket_entries": [docket_entry],
                "documents": [dict(document_projection)],
                "case_number_identity": {
                    "identity_state": identity_state,
                    "raw_source_label": raw_case_label,
                    "candidate": candidate,
                    "candidate_index": identity["candidate_index"],
                    "candidate_basis": candidate_basis,
                    "canonical_trial_case_asserted": False,
                },
                "source_omissions": source_omissions,
                "selected_query_context": record.get(
                    "selected_query_context"
                ),
                "court_locator_candidates": record.get(
                    "court_locator_candidates"
                ),
                "michigan_business_court_source_record": dict(record),
            }
        )
    return projections


def _texas_supreme_publication_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project one official hand-down occurrence without flattening its context."""

    if (
        _optional_text(record.get("record_kind"))
        != "supreme_court_release_case"
    ):
        return []
    if (
        _optional_text(record.get("source_id"))
        != TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID
    ):
        raise ValueError(
            "Texas Supreme publication record has the wrong source_id"
        )

    case_number = _required_text(
        record.get("raw_case_number"),
        "texas_supreme_publication.raw_case_number",
    )
    release_date = _required_text(
        record.get("release_date"),
        "texas_supreme_publication.release_date",
    )
    occurrence_id = _required_text(
        record.get("release_occurrence_id"),
        "texas_supreme_publication.release_occurrence_id",
    )
    court = _mapping(
        record.get("court"),
        "texas_supreme_publication.court",
    )

    documents: list[dict[str, Any]] = []
    document_values: list[Any] = []
    release_artifact = record.get("release_artifact")
    if release_artifact is not None:
        document_values.append(release_artifact)
    document_values.extend(
        _sequence(
            record.get("release_documents"),
            "texas_supreme_publication.release_documents",
        )
    )
    document_values.extend(
        _sequence(
            record.get("case_documents"),
            "texas_supreme_publication.case_documents",
        )
    )
    seen_documents: set[tuple[str, str | None]] = set()
    for index, value in enumerate(document_values):
        document = _mapping(
            value,
            f"texas_supreme_publication.documents[{index}]",
        )
        native_document_id = _required_text(
            document.get("native_document_id"),
            "texas_supreme_publication.document.native_document_id",
        )
        source_url = _required_text(
            document.get("source_url"),
            "texas_supreme_publication.document.source_url",
        )
        identity = (native_document_id, _optional_text(document.get("sha256")))
        if identity in seen_documents:
            continue
        seen_documents.add(identity)
        documents.append(
            {
                "native_document_id": native_document_id,
                "document_type": _optional_text(
                    document.get("document_type")
                ),
                "filed_date": release_date,
                "source_url": source_url,
                "sha256": _optional_text(document.get("sha256")),
                "mime_type": (
                    _optional_text(document.get("media_type"))
                    or "application/pdf"
                ),
                "access_state": "public",
                "native_access_state": (
                    "official_texas_supreme_publication_pdf"
                ),
                "docket_entry_native_id": occurrence_id,
                "texas_supreme_document_identity": dict(document),
            }
        )

    action = _optional_text(record.get("action_heading_raw"))
    section = _optional_text(record.get("section_heading_raw"))
    disposition = _optional_text(record.get("disposition_text"))
    raw_case_text = _required_text(
        record.get("raw_case_text"),
        "texas_supreme_publication.raw_case_text",
    )
    event = {
        "native_entry_id": occurrence_id,
        "event_code": "supreme_court_hand_down",
        "event_type": "official_release_publication_occurrence",
        "raw_text": " | ".join(
            value
            for value in (section, action, raw_case_text, disposition)
            if value
        ),
        "filed_date": release_date,
        "event_date": release_date,
        "status": action or section,
        "document_available": bool(documents),
        "access_state": "public",
        "native_access_state": (
            "official_texas_supreme_orders_and_opinions_release"
        ),
        "release_occurrence_id": occurrence_id,
        "section_heading_raw": section,
        "action_heading_raw": action,
        "disposition_text": disposition,
        "detail_text": record.get("detail_text"),
        "participation_text": record.get("participation_text"),
        "documents": [dict(document) for document in documents],
        "texas_supreme_publication_source_occurrence": dict(record),
    }
    source_occurrence = {
        "source_id": TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID,
        "record_kind": "supreme_court_release_case",
        "source_internal_id": case_number,
        "source_result_id": occurrence_id,
        "case_type": "supreme_court_publication",
        "filing_date": release_date,
        "filing_location": _optional_text(
            record.get("originating_county_candidate")
        ),
        "source_url": _optional_text(record.get("source_url")),
        "record_identity_source_candidate": TEXAS_TAMES_SOURCE_ID,
        "independent_corroboration": False,
        "raw_case_text": raw_case_text,
        "lower_court_candidate": record.get("lower_court_candidate"),
        "release_occurrence": dict(record),
    }
    return [
        {
            "source_id": TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID,
            "record_kind": "case",
            "court": dict(court),
            "raw_case_number": case_number,
            "display_case_number": (
                _optional_text(record.get("display_case_number"))
                or case_number
            ),
            "source_internal_id": case_number,
            "caption": _optional_text(record.get("caption")),
            "case_type": "supreme_court_publication",
            "disposition_date": release_date,
            "status": action or section,
            "access_state": "public",
            "native_access_state": (
                "official_partial_texas_supreme_publication_shell"
            ),
            "certified_record": False,
            "source_url": _optional_text(record.get("source_url")),
            "preserve_existing_case_fields": True,
            "partial_case_shell": True,
            "parties": [],
            "source_occurrences": [source_occurrence],
            "docket_entries": [event],
            "record_identity_source_candidate": TEXAS_TAMES_SOURCE_ID,
            "independent_corroboration": False,
            "originating_county_candidate": record.get(
                "originating_county_candidate"
            ),
            "lower_court_candidate": record.get("lower_court_candidate"),
            "texas_supreme_publication_source_record": dict(record),
        }
    ]


def _dc_opinion_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one opinion/MOJ index row without conflating publication types."""

    projected = dict(record)
    if record.get("record_kind") != "appellate_disposition":
        return projected

    native_entry_id = _required_text(
        record.get("native_entry_id"),
        "dc_opinion.native_entry_id",
    )
    publication_kind = (
        _optional_text(record.get("publication_kind"))
        or "unclassified_appellate_disposition"
    )
    decision_date = _optional_text(record.get("decision_date"))
    disposition = _optional_text(record.get("disposition"))
    court = dict(_mapping(record.get("court"), "dc_opinion.court"))
    court.setdefault(
        "native_court_id",
        _required_text(court.get("court_id"), "dc_opinion.court.court_id"),
    )
    document_value = record.get("document")
    document = dict(document_value) if isinstance(document_value, Mapping) else None
    entry = {
        "native_entry_id": native_entry_id,
        "event_code": publication_kind,
        "event_type": "appellate_disposition",
        "raw_text": " | ".join(
            value
            for value in (
                publication_kind,
                disposition,
            )
            if value
        ),
        "event_date": decision_date,
        "judge": _optional_text(record.get("judge")),
        "status": disposition,
        "document_available": document is not None,
        "access_state": "public",
        "publication_kind": publication_kind,
        "publication_kind_basis": record.get("publication_kind_basis"),
        "full_text_status": record.get("full_text_status"),
        "appeal_numbers": record.get("appeal_numbers"),
        "index_url": record.get("index_url"),
        "provenance": record.get("provenance"),
        "documents": [document] if document is not None else [],
    }
    projected.update(
        {
            "case_type": "appellate",
            "court": court,
            "disposition_date": decision_date,
            "status": disposition,
            "access_state": "public",
            "certified_record": False,
            "source_url": (
                _optional_text(record.get("index_url"))
                or _optional_text(record.get("source_url"))
            ),
            "docket_entries": [entry],
        }
    )
    return projected


def _san_diego_court_index_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project only the adapter's normalized case-index and new-filing rows."""

    if _optional_text(record.get("record_kind")) != "case":
        return []
    if _optional_text(record.get("source_id")) != SAN_DIEGO_COURT_INDEX_SOURCE_ID:
        raise ValueError("San Diego Court Index record has the wrong source_id")
    projected = dict(record)
    projected.setdefault("certified_record", False)
    projected.setdefault(
        "native_access_state",
        "official_court_index_not_official_case_record",
    )
    return [projected]


def _georgia_supreme_publication_court(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    source_court = _mapping(
        record.get("court"),
        "georgia_supreme_publication.court",
    )
    court_id = _optional_text(source_court.get("court_id"))
    if court_id != "us-ga-supreme-court":
        raise ValueError(
            "Georgia Supreme Court publication has an unexpected court_id"
        )
    return {
        "court_id": court_id,
        "native_court_id": court_id,
        "name": (
            _optional_text(source_court.get("name"))
            or "Supreme Court of Georgia"
        ),
        "state_code": "GA",
        "court_level": (
            _optional_text(source_court.get("court_level"))
            or "state_supreme"
        ),
        "official_url": (
            _optional_text(source_court.get("official_url"))
            or "https://www.gasupreme.us"
        ),
    }


def _georgia_supreme_publication_revision_events(
    record: Mapping[str, Any],
    *,
    source_id: str,
    publication_id: str,
) -> list[dict[str, Any]]:
    """Add stable identities and normalized dates to published revisions."""

    normalized: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("revision_events"),
            "georgia_supreme_publication.revision_events",
        )
    ):
        revision = _mapping(
            value,
            f"georgia_supreme_publication.revision_events[{index}]",
        )
        event_type = _required_text(
            revision.get("event_type"),
            (
                "georgia_supreme_publication."
                f"revision_events[{index}].event_type"
            ),
        )
        date_texts = [
            _required_text(
                date_value,
                (
                    "georgia_supreme_publication."
                    f"revision_events[{index}].date_texts"
                ),
            )
            for date_value in _sequence(
                revision.get("date_texts"),
                (
                    "georgia_supreme_publication."
                    f"revision_events[{index}].date_texts"
                ),
            )
        ]
        event_dates_iso: list[str] = []
        for date_text in date_texts:
            parsed = None
            for date_format in ("%m-%d-%Y", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(
                        date_text,
                        date_format,
                    ).date()
                except ValueError:
                    continue
                break
            if parsed is not None:
                event_dates_iso.append(parsed.isoformat())
        identity = {
            "source_id": source_id,
            "publication_id": publication_id,
            "event_type": event_type,
            "source_note_raw": revision.get("source_note_raw"),
            "date_texts": date_texts,
        }
        normalized.append(
            {
                **dict(revision),
                "native_revision_event_id": (
                    "ga-supreme-publication-revision:"
                    + hashlib.sha256(
                        _json(identity).encode("utf-8")
                    ).hexdigest()[:24]
                ),
                "event_type": event_type,
                "date_texts": date_texts,
                "event_dates_iso": event_dates_iso,
                "publication_id": publication_id,
                "component_source_id": source_id,
            }
        )
    return normalized


def _georgia_supreme_publication_document(
    value: Any,
    *,
    source_id: str,
    publication_id: str,
    publication_date: str,
    representation_role: str,
    originating_court: str,
    originating_case_numbers: list[str],
    independent_corroboration: bool,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    source_url = _optional_text(
        value.get("source_url", value.get("document_url"))
    )
    if source_url is None:
        return None
    native_document_id = _required_text(
        value.get("native_document_id"),
        "georgia_supreme_publication.document.native_document_id",
    )
    document = dict(value)
    document.update(
        {
            "native_document_id": native_document_id,
            "document_type": (
                _optional_text(value.get("document_type"))
                or "supreme_court_publication"
            ),
            "filed_date": publication_date,
            "source_url": source_url,
            "mime_type": (
                _optional_text(value.get("mime_type"))
                or "application/pdf"
            ),
            "access_state": "public",
            "native_access_state": (
                "official_linked_lower_appellate_representation"
                if originating_court == "Court of Appeals of Georgia"
                else "official_supreme_court_publication_pdf"
            ),
            "component_source_id": source_id,
            "publication_id": publication_id,
            "representation_role": representation_role,
            "originating_court": originating_court,
            "originating_case_numbers": originating_case_numbers,
            "independent_corroboration": independent_corroboration,
            "exact_document_identity": {
                "native_document_id": native_document_id,
                "source_url": source_url,
            },
        }
    )
    return document


def _georgia_supreme_publication_relations(
    record: Mapping[str, Any],
    *,
    source_id: str,
    publication_id: str,
    publication_date: str,
) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    publication_type = _required_text(
        record.get("publication_type"),
        "georgia_supreme_publication.publication_type",
    )
    for index, value in enumerate(
        _sequence(
            record.get("lower_appellate_cases"),
            "georgia_supreme_publication.lower_appellate_cases",
        )
    ):
        lower_case = _mapping(
            value,
            (
                "georgia_supreme_publication."
                f"lower_appellate_cases[{index}]"
            ),
        )
        case_number = _required_text(
            lower_case.get("case_number"),
            (
                "georgia_supreme_publication."
                f"lower_appellate_cases[{index}].case_number"
            ),
        )
        lower_document = _georgia_supreme_publication_document(
            lower_case,
            source_id=source_id,
            publication_id=publication_id,
            publication_date=publication_date,
            representation_role="originating_appellate_opinion_crosswalk",
            originating_court="Court of Appeals of Georgia",
            originating_case_numbers=[case_number],
            independent_corroboration=False,
        )
        relations.append(
            {
                "relation_type": "originating_appellate_case",
                "native_relation_type": (
                    f"{publication_type}_originating_appellate_case"
                ),
                "raw_case_number": case_number,
                "court_id": "us-ga-court-of-appeals",
                "native_court_id": "us-ga-court-of-appeals",
                "court_name": "Court of Appeals of Georgia",
                "court_level": "state_intermediate_appellate",
                "court_url": "https://www.gaappeals.us",
                "source_internal_id": case_number,
                "source_url": (
                    _optional_text(lower_case.get("document_url"))
                    or _optional_text(record.get("source_url"))
                ),
                "access_state": "public",
                "native_access_state": (
                    "official_supreme_court_appellate_crosswalk"
                ),
                "native_relation_id": (
                    f"{publication_id}:court-of-appeals:{case_number}"
                ),
                "evidence_ref": (
                    _optional_text(record.get("canonical_ref"))
                    or publication_id
                ),
                "documents": (
                    [lower_document] if lower_document is not None else []
                ),
                "publication_id": publication_id,
                "component_source_id": source_id,
                "representation": {
                    "originating_court": (
                        _optional_text(lower_case.get("originating_court"))
                        or "Court of Appeals of Georgia"
                    ),
                    "republication_context": lower_case.get(
                        "republication_context"
                    ),
                    "independent_corroboration": False,
                    "source_fields": dict(lower_case),
                },
            }
        )
    return relations


def _georgia_supreme_publication_projection_records(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    """Project case-bearing publications as sparse appellate case shells."""

    if _optional_text(record.get("source_id")) != source_id:
        raise ValueError(
            "Georgia Supreme Court publication record has the wrong source_id"
        )
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "supreme_court_opinion_publication",
        "supreme_court_certiorari_grant_publication",
        "supreme_court_certiorari_denial_list_entry",
        "supreme_court_application_grant_order",
    }:
        return []

    case_numbers: list[str] = []
    for value in _sequence(
        record.get("case_numbers"),
        "georgia_supreme_publication.case_numbers",
    ):
        case_number = _required_text(
            value,
            "georgia_supreme_publication.case_numbers",
        ).upper()
        if case_number not in case_numbers:
            case_numbers.append(case_number)
    if not case_numbers:
        return []

    publication_id = _required_text(
        record.get("publication_id"),
        "georgia_supreme_publication.publication_id",
    )
    publication_type = _required_text(
        record.get("publication_type"),
        "georgia_supreme_publication.publication_type",
    )
    publication_date = _required_text(
        record.get("publication_date"),
        "georgia_supreme_publication.publication_date",
    )
    publication_year = _integer(
        record.get("publication_year"),
        "georgia_supreme_publication.publication_year",
        nullable=False,
    )
    assert publication_year is not None
    event_id = f"ga-supreme-publication:{publication_id}"
    normalized_revisions = _georgia_supreme_publication_revision_events(
        record,
        source_id=source_id,
        publication_id=publication_id,
    )

    primary_document_value = {
        "supreme_court_opinion_publication": record.get("document"),
        "supreme_court_certiorari_grant_publication": record.get(
            "supreme_court_document"
        ),
        "supreme_court_certiorari_denial_list_entry": record.get(
            "supplemental_document"
        ),
        "supreme_court_application_grant_order": record.get("document"),
    }[record_kind]
    primary_document = _georgia_supreme_publication_document(
        primary_document_value,
        source_id=source_id,
        publication_id=publication_id,
        publication_date=publication_date,
        representation_role=(
            "supreme_court_opinion"
            if publication_type == "opinion"
            else "supreme_court_certiorari_grant_order"
            if publication_type == "certiorari_grant"
            else "supreme_court_denial_linked_supplement"
            if publication_type == "certiorari_denial"
            else f"supreme_court_{publication_type}_order"
        ),
        originating_court="Supreme Court of Georgia",
        originating_case_numbers=case_numbers,
        independent_corroboration=False,
    )
    relations = _georgia_supreme_publication_relations(
        record,
        source_id=source_id,
        publication_id=publication_id,
        publication_date=publication_date,
    )
    disposition = _optional_text(record.get("disposition"))
    version_notice = _optional_text(record.get("version_notice"))
    version_state = _optional_text(record.get("version_state"))
    source_url = (
        _optional_text(record.get("source_url"))
        or _optional_text(record.get("index_url"))
    )
    occurrence = dict(record)
    occurrence_identity = {
        "publication_id": publication_id,
        "component_source_id": source_id,
        "record_kind": record_kind,
        "publication_type": publication_type,
        "publication_year": publication_year,
        "publication_date": publication_date,
        "case_numbers": case_numbers,
        "multi_case_publication": bool(
            record.get("multi_case_publication")
        ),
    }
    event = {
        "native_entry_id": event_id,
        "event_code": publication_type,
        "event_type": publication_type,
        "raw_text": _optional_text(record.get("published_title")),
        "filed_date": publication_date,
        "event_date": publication_date,
        "status": disposition or version_state,
        "document_available": primary_document is not None,
        "access_state": "public",
        "native_access_state": (
            "official_supreme_court_decision_publication_occurrence"
        ),
        "component_source_id": source_id,
        "publication_id": publication_id,
        "publication_type": publication_type,
        "publication_year": publication_year,
        "publication_date": publication_date,
        "disposition": disposition,
        "application_type": record.get("application_type"),
        "version_state": version_state,
        "version_notice": version_notice,
        "revision_note_raw": record.get("revision_note_raw"),
        "revision_events": record.get("revision_events", []),
        "normalized_revision_events": normalized_revisions,
        "multi_case_identity": occurrence_identity,
        "source_url": source_url,
        "index_url": record.get("index_url"),
        "page_updated_at": record.get("page_updated_at"),
        "source_document_sha256": record.get("source_document_sha256"),
        "source_document_bytes": record.get("source_document_bytes"),
        "documents": (
            [primary_document] if primary_document is not None else []
        ),
        "ga_supreme_publication_source_occurrence": occurrence,
    }
    court = _georgia_supreme_publication_court(record)
    projected: list[dict[str, Any]] = []
    for case_number in case_numbers:
        projected.append(
            {
                "source_id": source_id,
                "record_kind": "case",
                "court": court,
                "raw_case_number": case_number,
                "display_case_number": case_number,
                "source_internal_id": case_number,
                "caption": _optional_text(record.get("caption")),
                "case_type": "appellate",
                "disposition_date": publication_date,
                "status": disposition,
                "access_state": "public",
                "native_access_state": (
                    "official_partial_supreme_court_publication_shell"
                ),
                "certified_record": False,
                "source_url": source_url,
                "preserve_existing_case_fields": True,
                "partial_case_shell": True,
                "parties": [],
                "docket_entries": [event],
                "case_relations": relations,
                "component_source_id": source_id,
                "publication_id": publication_id,
                "publication_type": publication_type,
                "publication_year": publication_year,
                "publication_date": publication_date,
                "disposition": disposition,
                "application_type": record.get("application_type"),
                "version_state": version_state,
                "version_notice": version_notice,
                "revision_note_raw": record.get("revision_note_raw"),
                "revision_events": record.get("revision_events", []),
                "normalized_revision_events": normalized_revisions,
                "multi_case_identity": occurrence_identity,
                "ga_supreme_publication_source_occurrence": occurrence,
            }
        )
    return projected


def _georgia_supreme_court(record: Mapping[str, Any]) -> dict[str, Any]:
    source_court = _mapping(record.get("court"), "georgia_supreme.court")
    court_id = _optional_text(source_court.get("court_id"))
    if court_id != "us-ga-supreme-court":
        raise ValueError(
            "Georgia Supreme Court docket record has an unexpected court_id"
        )
    return {
        "court_id": court_id,
        "native_court_id": court_id,
        "name": (
            _optional_text(source_court.get("name"))
            or "Supreme Court of Georgia"
        ),
        "state_code": "GA",
        "court_level": (
            _optional_text(source_court.get("court_level")) or "supreme"
        ),
        "official_url": (
            _optional_text(record.get("portal_url"))
            or "https://pubdoc.gasupreme.gov/ui/"
        ),
    }


def _georgia_supreme_attorneys(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("attorneys"), "georgia_supreme.attorneys")
    ):
        attorney = _mapping(value, f"georgia_supreme.attorneys[{index}]")
        raw_name = _optional_text(
            attorney.get("display_name", attorney.get("raw_name"))
        )
        if raw_name is None:
            continue
        projected.append(
            {
                "raw_name": raw_name,
                "firm_name": _optional_text(attorney.get("firm")),
                "party_type": _optional_text(attorney.get("party_type")),
                "title": _optional_text(attorney.get("title")),
                "contact": {
                    "address": attorney.get("address"),
                    "phone": _optional_text(attorney.get("phone")),
                },
                "ga_supreme_source_fields": dict(attorney),
            }
        )

    match = record.get("attorney_search_match")
    if not projected and isinstance(match, Mapping):
        raw_name = " ".join(
            value
            for value in (
                _optional_text(match.get("first_name")),
                _optional_text(match.get("last_name")),
            )
            if value
        )
        if raw_name:
            projected.append(
                {
                    "raw_name": raw_name,
                    "party_type": _optional_text(match.get("party_type")),
                    "party_type_native_id": _optional_text(
                        match.get("party_type_native_id")
                    ),
                    "ga_supreme_source_fields": dict(match),
                }
            )
    return projected


def _georgia_supreme_docket_entries(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("docket_entries"),
            "georgia_supreme.docket_entries",
        )
    ):
        entry = _mapping(
            value,
            f"georgia_supreme.docket_entries[{index}]",
        )
        native_entry_id = _required_text(
            entry.get("event_id"),
            f"georgia_supreme.docket_entries[{index}].event_id",
        )
        filing_type = _optional_text(entry.get("filing_type"))
        filed_at = _optional_text(entry.get("filed_at"))
        order_type = _optional_text(entry.get("order_type"))
        order_date = _optional_text(entry.get("order_date"))
        docketed_in_error = entry.get("docketed_in_error")
        if docketed_in_error not in {None, True, False}:
            raise ValueError(
                "Georgia Supreme Court docketed_in_error must be boolean or null"
            )
        entries.append(
            {
                "native_entry_id": native_entry_id,
                "sequence_no": entry.get("sequence", index + 1),
                "event_code": filing_type or order_type or "docket_event",
                "event_type": (
                    "filing_and_order"
                    if filing_type and order_type
                    else "order"
                    if order_type
                    else "filing"
                ),
                "raw_text": " | ".join(
                    item for item in (filing_type, order_type) if item
                )
                or None,
                "filed_date": filed_at,
                "event_date": order_date or filed_at,
                "status": (
                    "docketed_in_error" if docketed_in_error is True else None
                ),
                "document_available": None,
                "access_state": "public",
                "native_access_state": (
                    "official_docket_metadata_clerk_copy_request"
                ),
                "filing_type": filing_type,
                "filing_date_time": filed_at,
                "order_type": order_type,
                "order_date": order_date,
                "docketed_in_error": docketed_in_error,
                "document_access": (
                    _optional_text(entry.get("document_access"))
                    or "request_from_clerk"
                ),
                "document_url": entry.get("document_url"),
                "request_from_clerk": True,
                "ga_supreme_source_fields": dict(entry),
            }
        )
    return entries


def _georgia_supreme_case_events(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    case_number = _required_text(
        record.get("case_number"),
        "georgia_supreme.case_number",
    )
    events: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("judgments"), "georgia_supreme.judgments")
    ):
        judgment = _mapping(
            value,
            f"georgia_supreme.judgments[{index}]",
        )
        identity = {
            "case_number": case_number,
            "judgment": judgment.get("judgment"),
            "judgment_line": judgment.get("judgment_line"),
            "judgment_date": judgment.get("judgment_date"),
        }
        native_event_id = (
            "ga-supreme-judgment:"
            + hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()[:20]
        )
        events.append(
            {
                "native_event_id": native_event_id,
                "event_type": "judgment",
                "event_date": _optional_text(judgment.get("judgment_date")),
                "disposition": _optional_text(judgment.get("judgment")),
                "assertion_kind": "judgment",
                "native_assertion_kind": (
                    "supreme_court_judgment_metadata"
                ),
                "judgment_line": _optional_text(
                    judgment.get("judgment_line")
                ),
                "ga_supreme_source_fields": dict(judgment),
            }
        )

    calendar_value = record.get("calendar")
    if isinstance(calendar_value, Mapping):
        calendar = dict(calendar_value)
        if any(value not in {None, "", False} for value in calendar.values()):
            identity = {
                "case_number": case_number,
                "calendar": calendar.get("calendar"),
                "argument_date": calendar.get("argument_date"),
                "is_calendar_case": calendar.get("is_calendar_case"),
            }
            events.append(
                {
                    "native_event_id": (
                        "ga-supreme-calendar:"
                        + hashlib.sha256(
                            _json(identity).encode("utf-8")
                        ).hexdigest()[:20]
                    ),
                    "event_type": "appellate_calendar_assignment",
                    "event_date": _optional_text(
                        calendar.get("argument_date")
                    ),
                    "assertion_kind": "docket_metadata",
                    "native_assertion_kind": (
                        "supreme_court_calendar_metadata"
                    ),
                    "calendar": _optional_text(calendar.get("calendar")),
                    "is_calendar_case": calendar.get("is_calendar_case"),
                    "argument_date_is_provisional": calendar.get(
                        "argument_date_is_provisional"
                    ),
                    "ga_supreme_source_fields": calendar,
                }
            )
    return events


def _georgia_supreme_case_relations(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    county = _optional_text(record.get("county"))
    if county is None:
        return []
    case_number = _required_text(
        record.get("case_number"),
        "georgia_supreme.case_number",
    )
    source_url = (
        _optional_text(record.get("source_url"))
        or _optional_text(record.get("detail_api_url"))
    )
    return [
        {
            "relation_type": "originating_trial_case",
            "raw_case_number": lower_case_number,
            "county": county,
            "court_level": "trial",
            "native_relation_id": (
                f"{case_number}:originating:{lower_case_number}"
            ),
            "source_url": source_url,
            "access_state": "public",
        }
        for value in _sequence(
            record.get("lower_court_case_numbers"),
            "georgia_supreme.lower_court_case_numbers",
        )
        for lower_case_number in [_optional_text(value)]
        if lower_case_number is not None
    ]


def _georgia_supreme_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project case index/detail rows while retaining all other source rows."""

    if _optional_text(record.get("source_id")) != GEORGIA_SUPREME_DOCKET_SOURCE_ID:
        raise ValueError(
            "Georgia Supreme Court docket record has the wrong source_id"
        )
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "supreme_court_case_index",
        "supreme_court_case_detail",
    }:
        return []

    case_number = _required_text(
        record.get("case_number"),
        "georgia_supreme.case_number",
    )
    judgments = (
        _sequence(record.get("judgments"), "georgia_supreme.judgments")
        if record_kind == "supreme_court_case_detail"
        else []
    )
    judgment_dates = sorted(
        date_value
        for value in judgments
        for judgment in [_mapping(value, "georgia_supreme.judgment")]
        for date_value in [_optional_text(judgment.get("judgment_date"))]
        if date_value is not None
    )
    source_url = (
        _optional_text(record.get("source_url"))
        or _optional_text(record.get("detail_api_url"))
        or _optional_text(record.get("portal_url"))
    )
    description = _optional_text(record.get("description"))
    case_type_code = _optional_text(record.get("case_type_code"))
    projected = {
        "source_id": GEORGIA_SUPREME_DOCKET_SOURCE_ID,
        "record_kind": "case",
        "court": _georgia_supreme_court(record),
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": _optional_text(record.get("case_style")),
        "case_type": description or case_type_code,
        "filing_date": _optional_text(record.get("docket_date")),
        "disposition_date": judgment_dates[-1] if judgment_dates else None,
        "status": _optional_text(record.get("case_status")),
        "access_state": "public",
        "native_access_state": "official_recent_supreme_court_public_docket",
        "certified_record": False,
        "source_url": source_url,
        "preserve_existing_case_fields": (
            record_kind == "supreme_court_case_index"
        ),
        "parties": [],
        "attorneys": _georgia_supreme_attorneys(record),
        "docket_entries": _georgia_supreme_docket_entries(record),
        "case_events": _georgia_supreme_case_events(record),
        "case_relations": _georgia_supreme_case_relations(record),
        "case_type_code": case_type_code,
        "description": description,
        "county": _optional_text(record.get("county")),
        "lower_court_case_numbers": list(
            _sequence(
                record.get("lower_court_case_numbers"),
                "georgia_supreme.lower_court_case_numbers",
            )
        ),
        "calendar": record.get("calendar"),
        "document_inventory": record.get("document_inventory"),
        "attorney_search_match": record.get("attorney_search_match"),
        "ga_supreme_source_record": dict(record),
    }
    return [projected]


def _edva_bankruptcy_document_source_url(
    document: Mapping[str, Any],
) -> str | None:
    for field_name in ("download_url", "filepath_ia"):
        value = _optional_text(document.get(field_name))
        if value is not None and urlsplit(value).scheme in {"http", "https"}:
            return value
    return None


def _edva_bankruptcy_native_id(value: Any, field_name: str) -> str:
    native_id = _optional_text(value)
    if native_id is None:
        raise ValueError(f"{field_name} must identify a CourtListener record")
    return native_id


def _edva_bankruptcy_projection_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a CourtListener docket without implying official completeness."""

    if record.get("record_kind") != "federal_bankruptcy_docket":
        return dict(record)

    docket_id = _edva_bankruptcy_native_id(
        record.get("courtlistener_docket_id"),
        "edva_bankruptcy.courtlistener_docket_id",
    )
    docket_number = _required_text(
        record.get("docket_number"),
        "edva_bankruptcy.docket_number",
    )
    source_docket_url = _optional_text(record.get("source_docket_url"))
    coverage = dict(_mapping(record.get("coverage"), "edva_bankruptcy.coverage"))
    coverage_gap = bool(coverage.get("document_access_gap"))
    docket_entries: list[dict[str, Any]] = []
    source_occurrences: list[dict[str, Any]] = [
        {
            "source_id": EDVA_BANKRUPTCY_SOURCE_ID,
            "source_result_id": f"courtlistener:docket:{docket_id}",
            "record_kind": "federal_bankruptcy_docket",
            "source_internal_id": docket_id,
            "canonical_ref": record.get("canonical_ref"),
            "filing_date": record.get("date_filed"),
            "source_url": source_docket_url,
            "coverage": coverage,
            "internet_archive": record.get("internet_archive"),
            "access_paths": record.get("access_paths"),
            "source_record": dict(record),
        }
    ]

    for entry_index, value in enumerate(
        _sequence(record.get("entries"), "edva_bankruptcy.entries")
    ):
        entry = _mapping(
            value,
            f"edva_bankruptcy.entries[{entry_index}]",
        )
        entry_id = _edva_bankruptcy_native_id(
            entry.get("courtlistener_entry_id"),
            (
                "edva_bankruptcy.entries"
                f"[{entry_index}].courtlistener_entry_id"
            ),
        )
        documents: list[dict[str, Any]] = []
        source_documents = _sequence(
            entry.get("recap_documents"),
            f"edva_bankruptcy.entries[{entry_index}].recap_documents",
        )
        for document_index, document_value in enumerate(source_documents):
            document = _mapping(
                document_value,
                (
                    f"edva_bankruptcy.entries[{entry_index}]"
                    f".recap_documents[{document_index}]"
                ),
            )
            document_id = _edva_bankruptcy_native_id(
                document.get("courtlistener_document_id"),
                (
                    f"edva_bankruptcy.entries[{entry_index}]"
                    f".recap_documents[{document_index}]"
                    ".courtlistener_document_id"
                ),
            )
            source_url = _edva_bankruptcy_document_source_url(document)
            is_available = bool(document.get("is_available"))
            documents.append(
                {
                    "native_document_id": document_id,
                    "document_type": (
                        _optional_text(document.get("description"))
                        or "RECAP docket document"
                    ),
                    "filed_date": _optional_text(entry.get("date_filed")),
                    "source_url": source_url,
                    "page_count": document.get("page_count"),
                    "access_state": (
                        "public" if is_available else "metadata_only"
                    ),
                    "native_access_state": (
                        "recap_archive_document_available"
                        if is_available
                        else "recap_archive_document_metadata_only"
                    ),
                    "canonical_ref": document.get("canonical_ref"),
                    "document_number": document.get("document_number"),
                    "attachment_number": document.get("attachment_number"),
                    "pacer_doc_id": document.get("pacer_doc_id"),
                    "is_available": is_available,
                    "download_url": document.get("download_url"),
                    "filepath_local": document.get("filepath_local"),
                    "filepath_ia": document.get("filepath_ia"),
                    "recap_source_record": dict(document),
                }
            )
            source_occurrences.append(
                {
                    "source_id": EDVA_BANKRUPTCY_SOURCE_ID,
                    "source_result_id": (
                        f"courtlistener:docket:{docket_id}:entry:{entry_id}:"
                        f"document:{document_id}"
                    ),
                    "record_kind": "federal_bankruptcy_docket_document",
                    "source_internal_id": document_id,
                    "canonical_ref": document.get("canonical_ref"),
                    "filing_date": entry.get("date_filed"),
                    "source_url": source_url,
                    "courtlistener_docket_id": docket_id,
                    "courtlistener_entry_id": entry_id,
                    "document_number": document.get("document_number"),
                    "attachment_number": document.get("attachment_number"),
                    "pacer_doc_id": document.get("pacer_doc_id"),
                    "is_available": is_available,
                    "page_count": document.get("page_count"),
                    "download_url": document.get("download_url"),
                    "filepath_local": document.get("filepath_local"),
                    "filepath_ia": document.get("filepath_ia"),
                    "source_record": dict(document),
                }
            )

        docket_entries.append(
            {
                "native_entry_id": entry_id,
                "sequence_no": entry.get("entry_number"),
                "event_type": "bankruptcy_docket_entry",
                "raw_text": _optional_text(entry.get("description")),
                "filed_date": _optional_text(entry.get("date_filed")),
                "document_available": any(
                    bool(document.get("is_available"))
                    for document in source_documents
                    if isinstance(document, Mapping)
                ),
                "access_state": "public",
                "native_access_state": "courtlistener_recap_docket_entry",
                "canonical_ref": entry.get("canonical_ref"),
                "documents": documents,
                "recap_source_record": dict(entry),
            }
        )
        source_occurrences.append(
            {
                "source_id": EDVA_BANKRUPTCY_SOURCE_ID,
                "source_result_id": (
                    f"courtlistener:docket:{docket_id}:entry:{entry_id}"
                ),
                "record_kind": "federal_bankruptcy_docket_entry",
                "source_internal_id": entry_id,
                "canonical_ref": entry.get("canonical_ref"),
                "filing_date": entry.get("date_filed"),
                "source_url": source_docket_url,
                "courtlistener_docket_id": docket_id,
                "entry_number": entry.get("entry_number"),
                "source_record": dict(entry),
            }
        )

    restriction_events: list[dict[str, Any]] = []
    date_blocked = _optional_text(record.get("date_blocked"))
    if date_blocked is not None:
        restriction_events.append(
            {
                "event_type": "courtlistener_docket_blocked",
                "effective_at": date_blocked,
                "reason": (
                    "CourtListener reports a RECAP archive access gap; this "
                    "does not establish sealing or absence on the official "
                    "PACER/ECF docket."
                ),
                "direction_ref": record.get("canonical_ref"),
            }
        )

    return {
        "source_id": EDVA_BANKRUPTCY_SOURCE_ID,
        "record_kind": "case",
        "court": dict(_mapping(record.get("court"), "edva_bankruptcy.court")),
        "raw_case_number": docket_number,
        "display_case_number": docket_number,
        "source_internal_id": docket_id,
        "caption": _optional_text(record.get("case_name")),
        "case_type": "bankruptcy",
        "filing_date": _optional_text(record.get("date_filed")),
        "disposition_date": _optional_text(record.get("date_terminated")),
        "status": (
            "terminated"
            if _optional_text(record.get("date_terminated")) is not None
            else None
        ),
        "access_state": "public",
        "native_access_state": (
            "courtlistener_recap_archive_with_coverage_gap"
            if coverage_gap
            else "courtlistener_recap_archive_observation"
        ),
        "certified_record": False,
        "source_url": source_docket_url,
        "docket_entries": docket_entries,
        "restriction_events": restriction_events,
        "source_occurrences": source_occurrences,
        "pacer_case_id": record.get("pacer_case_id"),
        "date_blocked": record.get("date_blocked"),
        "coverage": coverage,
        "internet_archive": record.get("internet_archive"),
        "access_paths": record.get("access_paths"),
        "recap_source_record": dict(record),
    }


def _ohio_county_court_payload(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    """Fill the stable court fields omitted by some source result rows."""

    court_value = record.get("court")
    court = (
        dict(_mapping(court_value, "ohio_county_court.court"))
        if isinstance(court_value, Mapping)
        else {}
    )
    defaults = {
        FRANKLIN_CIO_SOURCE_ID: {
            "court_id": "oh-franklin-common-pleas",
            "native_court_id": "franklin-common-pleas",
            "name": "Franklin County Court of Common Pleas",
            "state_code": "OH",
            "county_geoid": "39049",
            "court_level": "common_pleas",
            "official_url": (
                "https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/"
            ),
        },
        FRANKLIN_MUNICIPAL_SOURCE_ID: {
            "court_id": "oh-franklin-municipal-court",
            "native_court_id": "franklin-municipal-court",
            "name": "Franklin County Municipal Court",
            "state_code": "OH",
            "county_geoid": "39049",
            "court_level": "municipal",
            "official_url": "https://www.fcmcclerk.com/case/search/",
        },
        DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID: {
            "court_id": "oh-delaware-common-pleas",
            "native_court_id": "oh-delaware-common-pleas",
            "name": "Delaware County Court of Common Pleas",
            "state_code": "OH",
            "county_geoid": "39041",
            "court_level": "common_pleas",
            "official_url": (
                "https://court.co.delaware.oh.us/eservices/home.page"
            ),
        },
    }[source_id]
    if "jurisdiction_id" in court and "county_geoid" not in court:
        court["county_geoid"] = court["jurisdiction_id"]
    for key, value in defaults.items():
        court.setdefault(key, value)
    return court


def _case_index_occurrence_projection(
    record: Mapping[str, Any],
    *,
    source_id: str,
    native_access_state: str,
) -> dict[str, Any]:
    """Project a party-index occurrence while retaining its observation ID."""

    normalized_case_number = _required_text(
        record.get("normalized_case_number"),
        "case_index_occurrence.normalized_case_number",
    )
    native_occurrence_id = _required_text(
        record.get("native_occurrence_id"),
        "case_index_occurrence.native_occurrence_id",
    )
    raw_name = _required_text(
        record.get("raw_name", record.get("name")),
        "case_index_occurrence.raw_name",
    )
    party_role = _optional_text(record.get("party_role")) or "source_index_party"
    metadata_value = record.get("source_metadata")
    metadata = metadata_value if isinstance(metadata_value, Mapping) else {}
    source_url = (
        _optional_text(record.get("source_url"))
        or _optional_text(metadata.get("source_url"))
    )
    occurrence = {
        **dict(record),
        "source_id": source_id,
        "source_result_id": native_occurrence_id,
        "source_internal_id": native_occurrence_id,
        "matched_party_name": raw_name,
        "source_url": source_url,
    }
    party = {
        "sequence_no": 1,
        "role": party_role,
        "raw_name": raw_name,
        "access_state": _optional_text(record.get("access_state")) or "public",
        "native_access_state": native_access_state,
        "source_occurrence_id": native_occurrence_id,
        "source_index_observation": dict(record),
    }
    return {
        "source_id": source_id,
        "record_kind": "case",
        "court": _ohio_county_court_payload(record, source_id=source_id),
        "raw_case_number": normalized_case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number"))
            or normalized_case_number
        ),
        "case_type": _optional_text(record.get("case_type")),
        "filing_date": _optional_text(record.get("filing_date")),
        "status": _optional_text(record.get("status")),
        "access_state": _optional_text(record.get("access_state")) or "public",
        "native_access_state": native_access_state,
        "certified_record": False,
        "source_url": source_url,
        "parties": [party],
        "source_occurrences": [occurrence],
        "preserve_existing_case_fields": True,
        "case_index_source_record": dict(record),
    }


def _franklin_cio_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project one exact CIO case without inferring parties or documents."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind == "case_index_occurrence":
        return [
            _case_index_occurrence_projection(
                record,
                source_id=FRANKLIN_CIO_SOURCE_ID,
                native_access_state=(
                    "anonymous CIO ordered party-index observation"
                ),
            )
        ]
    if record_kind != "case":
        return []
    normalized_case_number = _required_text(
        record.get("normalized_case_number"),
        "franklin_cio.normalized_case_number",
    )
    court = _ohio_county_court_payload(
        record,
        source_id=FRANKLIN_CIO_SOURCE_ID,
    )

    parties: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("parties"), "franklin_cio.parties")
    ):
        source_party = dict(
            _mapping(value, f"franklin_cio.parties[{index}]")
        )
        parties.append(
            {
                **source_party,
                "sequence_no": source_party.get("sequence_no", index + 1),
                "role": _required_text(
                    source_party.get("role"),
                    f"franklin_cio.parties[{index}].role",
                ),
                "raw_name": _required_text(
                    source_party.get("raw_name"),
                    f"franklin_cio.parties[{index}].raw_name",
                ),
                "access_state": (
                    _optional_text(source_party.get("access_state"))
                    or "public"
                ),
                "native_access_state": (
                    _optional_text(
                        source_party.get("native_access_state")
                    )
                    or "CIO case party"
                ),
                "franklin_source_party": source_party,
            }
        )

    case_events: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("case_schedule"),
            "franklin_cio.case_schedule",
        )
    ):
        source_event = dict(
            _mapping(value, f"franklin_cio.case_schedule[{index}]")
        )
        sequence_no = source_event.get("sequence_no", index + 1)
        description = _required_text(
            source_event.get("description"),
            f"franklin_cio.case_schedule[{index}].description",
        )
        identity = {
            "source_id": FRANKLIN_CIO_SOURCE_ID,
            "case_number": normalized_case_number,
            "sequence_no": sequence_no,
            "date_raw": source_event.get("date_raw"),
            "description": description,
        }
        digest = hashlib.sha256(
            _json(identity).encode("utf-8")
        ).hexdigest()
        case_events.append(
            {
                **source_event,
                "native_event_id": f"franklin:schedule:{digest[:24]}",
                "event_type": "case_schedule_event",
                "event_date": _optional_text(source_event.get("date")),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "CIO case schedule",
                "description": description,
                "franklin_source_schedule": source_event,
            }
        )

    docket_entries: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("docket_entries"),
            "franklin_cio.docket_entries",
        )
    ):
        source_entry = dict(
            _mapping(value, f"franklin_cio.docket_entries[{index}]")
        )
        projected_entry = dict(source_entry)
        projected_entry["event_code"] = _optional_text(
            source_entry.get("category_code")
        )
        projected_entry["event_type"] = (
            _optional_text(source_entry.get("category"))
            or "docket_entry"
        )
        projected_entry["raw_text"] = _required_text(
            source_entry.get("description"),
            f"franklin_cio.docket_entries[{index}].description",
        )
        projected_entry["documents"] = []
        projected_entry["franklin_source_entry"] = source_entry
        docket_entries.append(projected_entry)

    documents: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("documents"), "franklin_cio.documents")
    ):
        source_document = dict(
            _mapping(value, f"franklin_cio.documents[{index}]")
        )
        native_document_id = _required_text(
            source_document.get("native_document_id"),
            f"franklin_cio.documents[{index}].native_document_id",
        )
        emitted_entry_ids = [
            _required_text(
                entry_id,
                (
                    f"franklin_cio.documents[{index}]"
                    ".docket_entry_ids[]"
                ),
            )
            for entry_id in _sequence(
                source_document.get("docket_entry_ids"),
                (
                    f"franklin_cio.documents[{index}]"
                    ".docket_entry_ids"
                ),
            )
        ]
        docket_entry_ids = list(dict.fromkeys(emitted_entry_ids))
        pages_raw = _optional_text(source_document.get("pages_raw"))
        page_count = (
            int(pages_raw)
            if pages_raw is not None and re.fullmatch(r"\d+", pages_raw)
            else None
        )
        documents.append(
            {
                **source_document,
                "native_document_id": native_document_id,
                "docket_entry_native_id": (
                    docket_entry_ids[0] if docket_entry_ids else None
                ),
                "docket_entry_ids": docket_entry_ids,
                "page_count": page_count,
                "franklin_source_document": source_document,
            }
        )

    judge = _optional_text(record.get("judge"))
    projected: dict[str, Any] = {
        "source_id": FRANKLIN_CIO_SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": normalized_case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number"))
            or normalized_case_number
        ),
        "case_type": (
            _optional_text(record.get("case_description"))
            or _optional_text(record.get("case_type_family"))
            or _optional_text(record.get("case_type_code"))
        ),
        "filing_date": _optional_text(record.get("filing_date")),
        "status": _optional_text(record.get("status")),
        "access_state": (
            _optional_text(record.get("access_state")) or "public"
        ),
        "native_access_state": (
            _optional_text(record.get("native_access_state"))
            or "anonymous CIO exact-case detail"
        ),
        "certified_record": bool(record.get("certified_record", False)),
        "source_url": _optional_text(record.get("source_url")),
        "parties": parties,
        "judicial_assignments": (
            [
                {
                    "assignment_role": "trial_court_judge",
                    "officer": {"raw_name": judge},
                    "courtroom_raw": record.get("courtroom_raw"),
                }
            ]
            if judge is not None
            else []
        ),
        "case_events": case_events,
        "docket_entries": docket_entries,
        "documents": documents,
        "query_case_number_raw": record.get("query_case_number_raw"),
        "source_case_number_raw": record.get("source_case_number_raw"),
        "normalized_case_number": normalized_case_number,
        "case_year": record.get("case_year"),
        "case_type_code": record.get("case_type_code"),
        "case_type_family": record.get("case_type_family"),
        "case_sequence_raw": record.get("case_sequence_raw"),
        "case_sequence_normalized": record.get(
            "case_sequence_normalized"
        ),
        "courtroom_raw": record.get("courtroom_raw"),
        "case_schedule": record.get("case_schedule"),
        "docket_retrieval": record.get("docket_retrieval"),
        "franklin_source_record": dict(record),
    }
    return [projected]


def _ohio_county_date(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _franklin_municipal_event(
    record: Mapping[str, Any],
    *,
    normalized_case_number: str,
    event_family: str,
    index: int,
) -> dict[str, Any]:
    source_event = dict(record)
    event_date = _ohio_county_date(
        source_event.get(
            "date",
            source_event.get(
                "event_date",
                source_event.get(
                    "disposition_date",
                    source_event.get("status_date"),
                ),
            ),
        )
    )
    description = next(
        (
            value
            for value in (
                _optional_text(source_event.get("title")),
                _optional_text(source_event.get("event")),
                _optional_text(source_event.get("type")),
                _optional_text(source_event.get("disposition_code")),
                _optional_text(source_event.get("status")),
            )
            if value is not None
        ),
        event_family,
    )
    identity = {
        "case_number": normalized_case_number,
        "event_family": event_family,
        "source_ordinal": source_event.get("source_ordinal", index),
        "source_event": source_event,
    }
    digest = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()[:24]
    return {
        **source_event,
        "native_event_id": f"franklin-municipal:{event_family}:{digest}",
        "event_type": event_family,
        "event_date": event_date,
        "description": description,
        "assertion_kind": "docket_metadata",
        "native_assertion_kind": f"FCMC {event_family} row",
        "franklin_municipal_source_event": source_event,
    }


def _franklin_municipal_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project FCMC party occurrences and exact case detail."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind == "case_index_occurrence":
        return [
            _case_index_occurrence_projection(
                record,
                source_id=FRANKLIN_MUNICIPAL_SOURCE_ID,
                native_access_state=(
                    "anonymous FCMC case-party search occurrence"
                ),
            )
        ]
    if record_kind != "case":
        return []

    normalized_case_number = _required_text(
        record.get("normalized_case_number"),
        "franklin_municipal.normalized_case_number",
    )
    parties: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("parties"), "franklin_municipal.parties")
    ):
        source_party = dict(
            _mapping(value, f"franklin_municipal.parties[{index}]")
        )
        parties.append(
            {
                **source_party,
                "sequence_no": source_party.get("source_ordinal", index + 1),
                "role": (
                    _optional_text(source_party.get("type"))
                    or _optional_text(source_party.get("party_role"))
                    or "source_case_party"
                ),
                "raw_name": _required_text(
                    source_party.get("name"),
                    f"franklin_municipal.parties[{index}].name",
                ),
                "access_state": "public",
                "native_access_state": "FCMC exact-case party section",
                "franklin_municipal_source_party": source_party,
            }
        )

    attorneys: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("attorneys"), "franklin_municipal.attorneys")
    ):
        source_attorney = dict(
            _mapping(value, f"franklin_municipal.attorneys[{index}]")
        )
        party_type = _optional_text(source_attorney.get("party_type"))
        party_role = None
        representation_role = party_type
        if party_type and " - " in party_type:
            party_role, representation_role = party_type.split(" - ", 1)
        attorneys.append(
            {
                **source_attorney,
                "raw_name": _required_text(
                    source_attorney.get("name"),
                    f"franklin_municipal.attorneys[{index}].name",
                ),
                "party_role": party_role,
                "representation_role": representation_role,
                "franklin_municipal_source_attorney": source_attorney,
            }
        )

    docket_entries: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("docket_entries"),
            "franklin_municipal.docket_entries",
        )
    ):
        source_entry = dict(
            _mapping(value, f"franklin_municipal.docket_entries[{index}]")
        )
        title = _optional_text(source_entry.get("title")) or "docket_entry"
        detail = _optional_text(source_entry.get("detail"))
        docket_entries.append(
            {
                **source_entry,
                "sequence_no": source_entry.get("source_ordinal", index + 1),
                "event_type": title,
                "raw_text": "\n".join(
                    text for text in (title, detail) if text is not None
                ),
                "filed_date": _ohio_county_date(source_entry.get("date")),
                "document_available": False,
                "documents": [],
                "franklin_municipal_source_entry": source_entry,
            }
        )

    dispositions = [
        dict(_mapping(value, f"franklin_municipal.dispositions[{index}]"))
        for index, value in enumerate(
            _sequence(
                record.get("dispositions"),
                "franklin_municipal.dispositions",
            )
        )
    ]
    source_events = [
        dict(_mapping(value, f"franklin_municipal.events[{index}]"))
        for index, value in enumerate(
            _sequence(record.get("events"), "franklin_municipal.events")
        )
    ]
    case_events = [
        _franklin_municipal_event(
            source_event,
            normalized_case_number=normalized_case_number,
            event_family="disposition",
            index=index,
        )
        for index, source_event in enumerate(dispositions, start=1)
    ]
    case_events.extend(
        _franklin_municipal_event(
            source_event,
            normalized_case_number=normalized_case_number,
            event_family="case_event",
            index=index,
        )
        for index, source_event in enumerate(source_events, start=1)
    )
    judges = list(
        dict.fromkeys(
            value
            for value in (
                _optional_text(disposition.get("judge"))
                for disposition in dispositions
            )
            if value is not None
        )
    )
    metadata_value = record.get("source_metadata")
    metadata = metadata_value if isinstance(metadata_value, Mapping) else {}
    source_url = (
        _optional_text(record.get("source_url"))
        or _optional_text(metadata.get("source_url"))
    )
    disposition_date = next(
        (
            _ohio_county_date(value.get("disposition_date"))
            for value in dispositions
            if _optional_text(value.get("disposition_date")) is not None
        ),
        None,
    )
    projected = {
        "source_id": FRANKLIN_MUNICIPAL_SOURCE_ID,
        "record_kind": "case",
        "court": _ohio_county_court_payload(
            record,
            source_id=FRANKLIN_MUNICIPAL_SOURCE_ID,
        ),
        "raw_case_number": normalized_case_number,
        "display_case_number": (
            _optional_text(record.get("display_case_number"))
            or normalized_case_number
        ),
        "caption": _optional_text(record.get("caption")),
        "case_type": _optional_text(record.get("case_type")),
        "filing_date": _ohio_county_date(record.get("filing_date")),
        "disposition_date": disposition_date,
        "status": _optional_text(record.get("status")),
        "access_state": "public",
        "native_access_state": "anonymous FCMC exact-case detail",
        "certified_record": False,
        "source_url": source_url,
        "parties": parties,
        "attorneys": attorneys,
        "judicial_assignments": [
            {
                "assignment_role": "disposition_judge",
                "officer": {"raw_name": judge},
            }
            for judge in judges
        ],
        "case_events": case_events,
        "docket_entries": docket_entries,
        "documents": [],
        "defendant_information": record.get("defendant_information"),
        "case_details": record.get("case_details"),
        "charges": record.get("charges"),
        "dispositions": record.get("dispositions"),
        "financial_summary": record.get("financial_summary"),
        "receipts": record.get("receipts"),
        "document_access": record.get("document_access"),
        "franklin_municipal_source_record": dict(record),
    }
    return [projected]


def _delaware_case_number(record: Mapping[str, Any]) -> str:
    published = _required_text(
        record.get(
            "normalized_case_number",
            record.get(
                "display_case_number",
                record.get("case_number"),
            ),
        ),
        "delaware_common_pleas.case_number",
    )
    compact = re.sub(r"[^A-Za-z0-9]+", "", published).upper()
    return compact or published


def _delaware_docket_entry(
    record: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    source_entry = dict(record)
    native_entry_id = _required_text(
        source_entry.get(
            "docket_occurrence_id",
            source_entry.get("native_entry_id"),
        ),
        "delaware_common_pleas.docket_occurrence_id",
    )
    description = (
        _optional_text(source_entry.get("description"))
        or "docket_entry"
    )
    docket_text = _optional_text(source_entry.get("docket_text"))
    return {
        **source_entry,
        "native_entry_id": native_entry_id,
        "sequence_no": source_entry.get("source_index", index),
        "event_type": description,
        "raw_text": "\n".join(
            value for value in (description, docket_text) if value is not None
        ),
        "filed_date": _ohio_county_date(
            source_entry.get("date", source_entry.get("filed_date"))
        ),
        "document_available": bool(
            source_entry.get("document_link_present")
            or source_entry.get("document_id")
        ),
        "documents": [],
        "delaware_courtview_source_entry": source_entry,
    }


def _delaware_document(
    record: Mapping[str, Any],
    *,
    docket_entry_native_id: str | None = None,
) -> dict[str, Any]:
    source_document = dict(record)
    native_document_id = _required_text(
        source_document.get(
            "document_id",
            source_document.get("native_document_id"),
        ),
        "delaware_common_pleas.document_id",
    )
    sha256 = _optional_text(
        source_document.get("artifact_sha256", source_document.get("sha256"))
    )
    return {
        **source_document,
        "native_document_id": native_document_id,
        "docket_entry_native_id": docket_entry_native_id,
        "document_type": (
            _optional_text(source_document.get("description"))
            or "courtview_filing_image"
        ),
        "filed_date": _ohio_county_date(
            source_document.get("filed_date", source_document.get("date"))
        ),
        "source_url": _optional_text(source_document.get("source_url")),
        "sha256": sha256,
        "mime_type": _optional_text(
            source_document.get(
                "artifact_content_type",
                source_document.get("mime_type"),
            )
        ),
        "storage_path": _optional_text(
            source_document.get(
                "artifact_path",
                source_document.get("storage_path"),
            )
        ),
        "access_state": "public",
        "native_access_state": (
            _optional_text(source_document.get("document_access_state"))
            or "CourtView filing image listing"
        ),
        "delaware_courtview_source_document": source_document,
    }


def _delaware_common_pleas_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project CourtView occurrences, cases, dockets, and filing images."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind == "party_case_occurrence":
        normalized_case_number = _delaware_case_number(record)
        native_occurrence_id = _required_text(
            record.get("native_occurrence_id"),
            "delaware_common_pleas.native_occurrence_id",
        )
        normalized_occurrence = {
            **dict(record),
            "record_kind": "case_index_occurrence",
            "source_id": DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
            "court": _ohio_county_court_payload(
                record,
                source_id=DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
            ),
            "normalized_case_number": normalized_case_number,
            "display_case_number": (
                _optional_text(record.get("display_case_number"))
                or _optional_text(record.get("case_number"))
                or normalized_case_number
            ),
            "native_occurrence_id": native_occurrence_id,
            "raw_name": _required_text(
                record.get("party_name"),
                "delaware_common_pleas.party_name",
            ),
            "party_role": _optional_text(record.get("party_type")),
            "filing_date": _optional_text(
                record.get("file_date", record.get("filing_date"))
            ),
            "status": _optional_text(
                record.get("case_status", record.get("status"))
            ),
            "case_type": _optional_text(record.get("case_type")),
            "access_state": "public",
            "source_url": _optional_text(record.get("source_url")),
        }
        return [
            _case_index_occurrence_projection(
                normalized_occurrence,
                source_id=DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                native_access_state=(
                    "headed CourtView exhaustive party-index occurrence"
                ),
            )
        ]

    if record_kind == "case":
        normalized_case_number = _delaware_case_number(record)
        parties: list[dict[str, Any]] = []
        for index, value in enumerate(
            _sequence(record.get("parties"), "delaware_common_pleas.parties")
        ):
            source_party = dict(
                _mapping(value, f"delaware_common_pleas.parties[{index}]")
            )
            attorneys: list[dict[str, Any]] = []
            for attorney_index, attorney_value in enumerate(
                _sequence(
                    source_party.get("attorneys"),
                    f"delaware_common_pleas.parties[{index}].attorneys",
                )
            ):
                source_attorney = dict(
                    _mapping(
                        attorney_value,
                        "delaware_common_pleas."
                        f"parties[{index}].attorneys[{attorney_index}]",
                    )
                )
                attorney_name = _optional_text(
                    source_attorney.get(
                        "Attorney",
                        source_attorney.get(
                            "raw_name",
                            source_attorney.get("name"),
                        ),
                    )
                )
                if attorney_name is None:
                    continue
                attorneys.append(
                    {
                        **source_attorney,
                        "raw_name": attorney_name,
                        "bar_id": _optional_text(
                            source_attorney.get(
                                "Bar Code",
                                source_attorney.get("bar_id"),
                            )
                        ),
                        "delaware_courtview_source_attorney": source_attorney,
                    }
                )
            raw_name = _optional_text(
                source_party.get(
                    "party_name",
                    source_party.get(
                        "party_company",
                        source_party.get("name"),
                    ),
                )
            )
            if raw_name is None:
                continue
            role = (
                _optional_text(source_party.get("party_type"))
                or _optional_text(source_party.get("type"))
                or _optional_text(source_party.get("role"))
                or "source_case_party"
            )
            parties.append(
                {
                    **source_party,
                    "sequence_no": source_party.get(
                        "source_ordinal",
                        source_party.get("source_index", index + 1),
                    ),
                    "role": role,
                    "raw_name": raw_name,
                    "attorneys": attorneys,
                    "access_state": "public",
                    "native_access_state": "CourtView exact-case party section",
                    "delaware_courtview_source_party": source_party,
                }
            )
        source_docket = [
            dict(_mapping(value, f"delaware_common_pleas.docket[{index}]"))
            for index, value in enumerate(
                _sequence(record.get("docket"), "delaware_common_pleas.docket")
            )
        ]
        docket_entries = [
            _delaware_docket_entry(value, index=index)
            for index, value in enumerate(source_docket, start=1)
        ]
        documents = [
            _delaware_document(
                value,
                docket_entry_native_id=_optional_text(
                    value.get("docket_occurrence_id")
                ),
            )
            for value in source_docket
            if value.get("document_link_present") and value.get("document_id")
        ]
        judge = _optional_text(record.get("judge"))
        return [
            {
                "source_id": DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                "record_kind": "case",
                "court": _ohio_county_court_payload(
                    record,
                    source_id=DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                ),
                "raw_case_number": normalized_case_number,
                "display_case_number": (
                    _optional_text(record.get("display_case_number"))
                    or _optional_text(record.get("case_number"))
                    or normalized_case_number
                ),
                "caption": _optional_text(record.get("caption")),
                "case_type": _optional_text(record.get("case_type")),
                "filing_date": _optional_text(
                    record.get("file_date", record.get("filing_date"))
                ),
                "status": _optional_text(
                    record.get("case_status", record.get("status"))
                ),
                "access_state": "public",
                "native_access_state": "headed CourtView exact-case detail",
                "certified_record": False,
                "source_url": _optional_text(record.get("source_url")),
                "parties": parties,
                "judicial_assignments": (
                    [
                        {
                            "assignment_role": "case_judge",
                            "officer": {"raw_name": judge},
                        }
                    ]
                    if judge is not None
                    else []
                ),
                "docket_entries": docket_entries,
                "documents": documents,
                "courtview_events": record.get("events"),
                "courtview_financial_tables": record.get("financial_tables"),
                "source_search_occurrences": record.get(
                    "source_search_occurrences"
                ),
                "delaware_courtview_source_record": dict(record),
            }
        ]

    if record_kind == "docket_entry":
        normalized_case_number = _delaware_case_number(record)
        return [
            {
                "source_id": DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                "record_kind": "case",
                "court": _ohio_county_court_payload(
                    record,
                    source_id=DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                ),
                "raw_case_number": normalized_case_number,
                "display_case_number": (
                    _optional_text(record.get("display_case_number"))
                    or _optional_text(record.get("case_number"))
                ),
                "access_state": "public",
                "native_access_state": "headed CourtView docket occurrence",
                "source_url": _optional_text(record.get("source_url")),
                "docket_entries": [_delaware_docket_entry(record, index=1)],
                "preserve_existing_case_fields": True,
            }
        ]

    if record_kind in {"case_document_listing", "case_document_artifact"}:
        normalized_case_number = _delaware_case_number(record)
        docket_entry_id = _optional_text(record.get("docket_occurrence_id"))
        docket_entries = (
            [_delaware_docket_entry(record, index=1)]
            if docket_entry_id is not None
            else []
        )
        return [
            {
                "source_id": DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                "record_kind": "case",
                "court": _ohio_county_court_payload(
                    record,
                    source_id=DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID,
                ),
                "raw_case_number": normalized_case_number,
                "display_case_number": (
                    _optional_text(record.get("display_case_number"))
                    or _optional_text(record.get("case_number"))
                ),
                "caption": _optional_text(record.get("caption")),
                "access_state": "public",
                "native_access_state": (
                    "retrieved CourtView filing image"
                    if record_kind == "case_document_artifact"
                    else "CourtView filing image listing"
                ),
                "source_url": _optional_text(record.get("source_url")),
                "docket_entries": docket_entries,
                "documents": [
                    _delaware_document(
                        record,
                        docket_entry_native_id=docket_entry_id,
                    )
                ],
                "preserve_existing_case_fields": True,
            }
        ]
    return []


def _franklin_probate_date(value: Any) -> str | None:
    """Normalize the two date forms observed in Franklin Probate records."""

    text = _optional_text(value)
    if text is None or text.casefold() in {"n/a", "case is open"}:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _franklin_probate_case_identity(
    record: Mapping[str, Any],
) -> tuple[str, str]:
    case_number = _required_text(
        record.get("case_number"),
        "franklin_probate.case_number",
    )
    suffix = _optional_text(record.get("case_suffix")) or ""
    raw_case_number = f"{case_number}{suffix}"
    selector_suffix = ";;" if not suffix else f"{suffix};" if len(suffix) == 1 else suffix
    return raw_case_number, f"{case_number}{selector_suffix}"


def _franklin_probate_court(record: Mapping[str, Any]) -> dict[str, Any]:
    source_court = dict(
        _mapping(record.get("court"), "franklin_probate.court")
    )
    court_id = _required_text(
        source_court.get("court_id"),
        "franklin_probate.court.court_id",
    )
    if court_id != "oh-franklin-county-probate-court":
        raise ValueError("Franklin Probate record has an unexpected court_id")
    county_geoid = _optional_text(
        source_court.get("county_geoid", source_court.get("county_fips"))
    )
    if county_geoid != "39049":
        raise ValueError("Franklin Probate record has an unexpected county GEOID")
    return {
        **source_court,
        "native_court_id": court_id,
        "county_geoid": county_geoid,
        "official_url": (
            "https://probate.franklincountyohio.gov/"
            "Record-Search/General-Case-Search"
        ),
    }


def _franklin_probate_occurrence(
    record: Mapping[str, Any],
    *,
    filing_date: str | None = None,
) -> dict[str, Any]:
    occurrence = dict(record)
    occurrence["source_id"] = FRANKLIN_PROBATE_SOURCE_ID
    occurrence["source_internal_id"] = record.get("source_native_id")
    occurrence["filing_date"] = filing_date
    if _optional_text(record.get("discovery_operation")) == "fiduciary":
        occurrence["matched_party_name"] = record.get("fiduciary_name")
    return occurrence


def _franklin_probate_case_base(
    record: Mapping[str, Any],
    *,
    preserve_existing_case_fields: bool,
) -> dict[str, Any]:
    raw_case_number, case_selector = _franklin_probate_case_identity(record)
    filing_date = _franklin_probate_date(
        record.get("date_opened_raw", record.get("opened_date_raw"))
    )
    closed_raw = _optional_text(
        record.get("date_closed_raw", record.get("closed_date_raw"))
    )
    disposition_date = _franklin_probate_date(closed_raw)
    status = _optional_text(record.get("status_code"))
    if closed_raw is not None and closed_raw.casefold() == "case is open":
        status = "open"
    elif disposition_date is not None and status is None:
        status = "closed"
    return {
        "source_id": FRANKLIN_PROBATE_SOURCE_ID,
        "record_kind": "case",
        "court": _franklin_probate_court(record),
        "raw_case_number": raw_case_number,
        "display_case_number": (
            _optional_text(record.get("case_number_display_raw"))
            or raw_case_number
        ),
        "source_internal_id": case_selector,
        "caption": _optional_text(record.get("case_name")),
        "case_type": _optional_text(record.get("case_type")),
        "filing_date": filing_date,
        "disposition_date": disposition_date,
        "status": status,
        "access_state": "public",
        "native_access_state": "official anonymous NetData record",
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "preserve_existing_case_fields": preserve_existing_case_fields,
        "source_occurrences": [
            _franklin_probate_occurrence(record, filing_date=filing_date)
        ],
        "case_type_code": record.get("case_type_code"),
        "case_subtype": record.get("case_subtype"),
        "status_code": record.get("status_code"),
        "aka_raw": record.get("aka_raw"),
        "bond_amount_raw": record.get("bond_amount_raw"),
        "related_cases_raw": record.get("related_cases_raw"),
        "franklin_probate_source_record": dict(record),
    }


def _franklin_probate_fiduciary_party(
    record: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw_name = _optional_text(record.get("fiduciary_name"))
    if raw_name is None:
        return None
    fiduciary_number = _optional_text(record.get("fiduciary_number"))
    sequence_no = (
        int(fiduciary_number)
        if fiduciary_number is not None and fiduciary_number.isdigit()
        else 1
    )
    appointment_date = _franklin_probate_date(
        record.get("appointment_date_raw")
    )
    termination_date = _franklin_probate_date(
        record.get("termination_date_raw")
    )
    attorneys: list[dict[str, Any]] = []
    attorney_name = _optional_text(record.get("attorney_name"))
    if attorney_name is not None:
        attorneys.append(
            {
                "raw_name": attorney_name,
                "bar_id": _optional_text(record.get("attorney_number")),
                "effective_from": appointment_date,
                "effective_to": termination_date,
                "source_entry_id": _optional_text(
                    record.get("source_native_id")
                ),
                "franklin_probate_source_fields": {
                    "attorney_number": record.get("attorney_number"),
                    "attorney_detail_url": record.get("attorney_detail_url"),
                },
            }
        )
    return {
        "sequence_no": sequence_no,
        "role": "fiduciary",
        "raw_name": raw_name,
        "native_party_id": fiduciary_number,
        "access_state": "public",
        "native_access_state": "official NetData fiduciary roster",
        "fiduciary_title_code": record.get(
            "fiduciary_title_code",
            record.get("title_code"),
        ),
        "fiduciary_title": record.get(
            "fiduciary_title",
            record.get("title_description"),
        ),
        "appointment_date": appointment_date,
        "termination_date": termination_date,
        "attorneys": attorneys,
        "franklin_probate_source_fields": dict(record),
    }


def _franklin_probate_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project case-linked NetData rows and retain other rows as snapshots."""

    record_kind = _optional_text(record.get("record_kind"))
    if record_kind in {"probate_case_index", "probate_case"}:
        projected = _franklin_probate_case_base(
            record,
            preserve_existing_case_fields=record_kind == "probate_case_index",
        )
        return [projected]

    if record_kind in {"probate_docket_entry", "probate_docket_summary"}:
        projected = _franklin_probate_case_base(
            record,
            preserve_existing_case_fields=True,
        )
        projected["docket_entries"] = [
            {
                "native_entry_id": _required_text(
                    record.get("source_native_id"),
                    "franklin_probate.docket.source_native_id",
                ),
                "sequence_no": record.get("source_position"),
                "event_code": record.get("code"),
                "event_type": record_kind,
                "raw_text": record.get("description"),
                "filed_date": _franklin_probate_date(record.get("date_raw")),
                "event_date": _franklin_probate_date(record.get("date_raw")),
                "document_available": None,
                "access_state": "public",
                "native_access_state": "official NetData docket row",
                "reference_raw": record.get("reference_raw"),
                "receipt_raw": record.get("receipt_raw"),
                "cost_raw": record.get("cost_raw"),
                "franklin_probate_source_fields": dict(record),
            }
        ]
        return [projected]

    if record_kind in {"probate_fiduciary", "probate_fiduciary_detail"}:
        projected = _franklin_probate_case_base(
            record,
            preserve_existing_case_fields=True,
        )
        party = _franklin_probate_fiduciary_party(record)
        projected["parties"] = [party] if party is not None else []
        return [projected]

    return []


def _ohio_supreme_court() -> dict[str, Any]:
    return {
        "court_id": "oh-supreme-court",
        "native_court_id": "oh-supreme-court",
        "name": "Supreme Court of Ohio",
        "state_code": "OH",
        "court_level": "state_supreme",
        "official_url": (
            "https://www.supremecourt.ohio.gov/clerk/ecms/"
        ),
    }


def _ohio_reporter_court(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    court_id = _required_text(
        record.get("court_id"),
        "ohio_reporter.court_id",
    )
    if court_id == "oh-supreme-court":
        court_level = "state_supreme"
    elif court_id.startswith("oh-court-of-appeals-district-"):
        court_level = "appellate"
    elif court_id == "oh-court-of-claims":
        court_level = "specialized"
    else:
        court_level = "judicial_publication_component"
    return {
        "court_id": court_id,
        "native_court_id": court_id,
        "name": _required_text(
            record.get("court_name"),
            "ohio_reporter.court_name",
        ),
        "state_code": "OH",
        "court_level": court_level,
        "official_url": (
            "https://www.supremecourt.ohio.gov/ROD/docs/Default.aspx"
        ),
    }


def _new_mexico_case_lookup_date(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return text


def _new_mexico_case_lookup_court(
    record: Mapping[str, Any],
    *,
    case_number: str,
) -> dict[str, Any]:
    match = _NEW_MEXICO_CASE_NUMBER_RE.fullmatch(case_number)
    if match is None:
        raise ValueError(
            "New Mexico Case Lookup case number has an invalid court identity"
        )
    native_court_id = (
        f"{match.group('court_type')}-{match.group('court_location')}"
    )
    court_id = f"nm-case-lookup-{native_court_id.casefold()}"
    court = _mapping(record.get("court"), "new_mexico_case_lookup.court")
    if _optional_text(court.get("court_id")) != court_id:
        raise ValueError(
            "New Mexico Case Lookup court_id disagrees with the case number"
        )
    if (
        _optional_text(court.get("source_native_court_code"))
        != native_court_id
    ):
        raise ValueError(
            "New Mexico Case Lookup native court code disagrees with the "
            "case number"
        )
    return {
        "court_id": court_id,
        "native_court_id": native_court_id,
        "name": _required_text(
            court.get("name"),
            "new_mexico_case_lookup.court.name",
        ),
        "state_code": "NM",
        "court_level": (
            _optional_text(court.get("level")) or "source_published_court"
        ),
        "official_url": (
            "https://caselookup.nmcourts.gov/caselookup/app"
        ),
    }


def _new_mexico_case_lookup_party(
    value: Mapping[str, Any],
    *,
    sequence_no: int,
) -> dict[str, Any]:
    party = dict(value)
    raw_name = _required_text(
        party.get("name"),
        "new_mexico_case_lookup.party.name",
    )
    role = (
        _optional_text(party.get("role"))
        or _optional_text(party.get("role_code"))
        or "party"
    )
    attorneys = [
        {
            "raw_name": attorney_name,
            "native_access_state": (
                "official_case_lookup_attorney_appearance"
            ),
            "new_mexico_case_lookup_source_attorney": dict(attorney),
        }
        for index, attorney_value in enumerate(
            _sequence(
                party.get("attorneys"),
                "new_mexico_case_lookup.party.attorneys",
            )
        )
        for attorney in [
            _mapping(
                attorney_value,
                (
                    "new_mexico_case_lookup.party.attorneys"
                    f"[{index}]"
                ),
            )
        ]
        for attorney_name in [_optional_text(attorney.get("name"))]
        if attorney_name is not None
    ]
    return {
        "sequence_no": sequence_no,
        "role": role,
        "raw_name": raw_name,
        "access_state": "public",
        "native_access_state": "official_case_lookup_party",
        "attorneys": attorneys,
        "role_code": party.get("role_code"),
        "party_number": party.get("party_number"),
        "new_mexico_case_lookup_source_party": party,
    }


def _new_mexico_case_lookup_claims(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    complaint_date = next(
        (
            _new_mexico_case_lookup_date(
                _mapping(
                    complaint.get("fields"),
                    "new_mexico_case_lookup.complaint.fields",
                ).get("complaint_date")
            )
            for index, complaint_value in enumerate(
                _sequence(
                    record.get("complaint_records"),
                    "new_mexico_case_lookup.complaint_records",
                )
            )
            for complaint in [
                _mapping(
                    complaint_value,
                    (
                        "new_mexico_case_lookup.complaint_records"
                        f"[{index}]"
                    ),
                )
            ]
        ),
        None,
    )
    claims: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("cause_records"),
            "new_mexico_case_lookup.cause_records",
        ),
        start=1,
    ):
        cause = dict(
            _mapping(
                value,
                f"new_mexico_case_lookup.cause_records[{index - 1}]",
            )
        )
        fields = dict(
            _mapping(
                cause.get("fields"),
                (
                    "new_mexico_case_lookup.cause_records"
                    f"[{index - 1}].fields"
                ),
            )
        )
        description = _optional_text(fields.get("coa_description"))
        sequence = _optional_text(fields.get("coa_sequence")) or str(index)
        source_child_id = _optional_text(cause.get("source_child_id"))
        if source_child_id is None or not source_child_id.startswith(
            "derived:"
        ):
            raise ValueError(
                "New Mexico Case Lookup cause requires its stable derived "
                "source_child_id"
            )
        if cause.get("source_child_id_kind") != (
            "derived_from_published_fields_and_duplicate_ordinal"
        ):
            raise ValueError(
                "New Mexico Case Lookup cause identity kind changed"
            )
        identity = source_child_id
        claims.append(
            {
                "native_claim_id": (
                    "nm-case-lookup:cause:"
                    + identity.removeprefix("derived:")
                ),
                "sequence_no": (
                    int(sequence) if sequence.isdigit() else index
                ),
                "claim_type": "civil_cause_of_action",
                "claim_date": complaint_date,
                "status": None,
                "limited_stub": False,
                "access_state": "public",
                "native_access_state": (
                    "official_case_lookup_cause_of_action"
                ),
                "description": description,
                "source_sequence": sequence,
                "new_mexico_case_lookup_source_cause": cause,
            }
        )
    return claims


def _new_mexico_case_lookup_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project discovery occurrences and exact cases onto one case identity."""

    if (
        _optional_text(record.get("source_id"))
        != NEW_MEXICO_CASE_LOOKUP_SOURCE_ID
    ):
        raise ValueError("New Mexico Case Lookup record has the wrong source_id")
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "case_party_search_hit",
        "new_mexico_case_detail",
    }:
        return []

    case_number = _required_text(
        record.get("case_number"),
        "new_mexico_case_lookup.case_number",
    )
    court = _new_mexico_case_lookup_court(
        record,
        case_number=case_number,
    )
    exact = record_kind == "new_mexico_case_detail"
    source_url = (
        _optional_text(record.get("source_url"))
        or "https://caselookup.nmcourts.gov/caselookup/app"
    )
    parties: list[dict[str, Any]] = []
    if exact:
        parties = [
            _new_mexico_case_lookup_party(
                _mapping(
                    value,
                    f"new_mexico_case_lookup.parties[{index}]",
                ),
                sequence_no=index + 1,
            )
            for index, value in enumerate(
                _sequence(
                    record.get("parties"),
                    "new_mexico_case_lookup.parties",
                )
            )
        ]

    docket_entries = [
        {
            "native_entry_id": native_entry_id,
            "sequence_no": index + 1,
            "event_code": _optional_text(entry.get("event_description")),
            "event_type": "register_of_actions_activity",
            "raw_text": " | ".join(
                value
                for value in (
                    _optional_text(entry.get("event_description")),
                    _optional_text(entry.get("detail_text")),
                    _optional_text(entry.get("event_result")),
                )
                if value is not None
            )
            or None,
            "filed_date": _optional_text(entry.get("event_date")),
            "event_date": _optional_text(entry.get("event_date")),
            "status": _optional_text(entry.get("event_result")),
            "document_available": False,
            "access_state": "public",
            "native_access_state": (
                "official_case_lookup_register_metadata"
            ),
            "party_type": entry.get("party_type"),
            "party_number": entry.get("party_number"),
            "amount_raw": entry.get("amount_raw"),
            "native_entry_id_kind": entry.get("native_entry_id_kind"),
            "new_mexico_case_lookup_source_entry": dict(entry),
        }
        for index, value in enumerate(
            _sequence(
                record.get("register_of_actions"),
                "new_mexico_case_lookup.register_of_actions",
            )
        )
        for entry in [
            _mapping(
                value,
                (
                    "new_mexico_case_lookup.register_of_actions"
                    f"[{index}]"
                ),
            )
        ]
        for native_entry_id in [
            _required_text(
                entry.get("native_entry_id"),
                (
                    "new_mexico_case_lookup.register_of_actions"
                    f"[{index}].native_entry_id"
                ),
            )
        ]
        if (
            native_entry_id.startswith("derived:")
            and entry.get("native_entry_id_kind")
            == "derived_from_published_row_fields_and_duplicate_ordinal"
        )
    ]
    if exact and len(docket_entries) != len(
        _sequence(
            record.get("register_of_actions"),
            "new_mexico_case_lookup.register_of_actions",
        )
    ):
        raise ValueError(
            "New Mexico Case Lookup register identity contract changed"
        )
    judge_history = [
        dict(
            _mapping(
                value,
                (
                    "new_mexico_case_lookup.judge_assignment_history"
                    f"[{index}]"
                ),
            )
        )
        for index, value in enumerate(
            _sequence(
                record.get("judge_assignment_history"),
                "new_mexico_case_lookup.judge_assignment_history",
            )
        )
    ]
    case_events = [
        {
            "native_event_id": _required_text(
                event.get("assignment_event_id"),
                (
                    "new_mexico_case_lookup.judge_assignment_history"
                    f"[{index}].assignment_event_id"
                ),
            ),
            "event_type": "judge_assignment_history",
            "event_date": _optional_text(event.get("assignment_date")),
            "disposition": None,
            "assertion_kind": "docket_metadata",
            "native_assertion_kind": (
                "official_case_lookup_judge_assignment_history"
            ),
            "judge_name": event.get("judge_name"),
            "sequence_number": event.get("sequence_number"),
            "assignment_event_description": event.get(
                "assignment_event_description"
            ),
            "new_mexico_case_lookup_source_event": event,
        }
        for index, event in enumerate(judge_history)
    ]
    if exact and any(
        not str(event["native_event_id"]).startswith("derived:")
        or judge_history[index].get("assignment_event_id_kind")
        != "derived_from_published_row_fields_and_duplicate_ordinal"
        for index, event in enumerate(case_events)
    ):
        raise ValueError(
            "New Mexico Case Lookup judge-history identity contract changed"
        )
    judicial_assignments = [
        {
            "raw_name": judge_name,
            "assignment_role": "historical_case_assignment",
            "effective_from": _optional_text(event.get("assignment_date")),
            "assignment_event_description": event.get(
                "assignment_event_description"
            ),
            "new_mexico_case_lookup_source_assignment": event,
        }
        for event in judge_history
        for judge_name in [_optional_text(event.get("judge_name"))]
        if judge_name is not None
        and not judge_name.casefold().startswith("awaiting")
    ]
    current_judge = _optional_text(record.get("current_judge"))
    if (
        exact
        and current_judge is not None
        and not current_judge.casefold().startswith("awaiting")
    ):
        judicial_assignments.append(
            {
                "raw_name": current_judge,
                "assignment_role": "current_judge",
                "effective_from": None,
            }
        )

    occurrence_id = (
        _optional_text(record.get("source_occurrence_id"))
        or f"exact-case:{case_number}"
    )
    occurrence = {
        "source_id": NEW_MEXICO_CASE_LOOKUP_SOURCE_ID,
        "record_kind": record_kind,
        "source_result_id": occurrence_id,
        "canonical_ref": _optional_text(record.get("canonical_ref")),
        "matched_party_name": (
            _optional_text(
                _mapping(
                    record.get("matched_party"),
                    "new_mexico_case_lookup.matched_party",
                ).get("name")
            )
            if not exact
            else None
        ),
        "filing_date": _optional_text(record.get("filing_date")),
        "source_url": source_url,
        "source_record": dict(record),
    }
    category_parts = case_number.split("-", 3)
    return [
        {
            "source_id": NEW_MEXICO_CASE_LOOKUP_SOURCE_ID,
            "record_kind": "case",
            "court": court,
            "raw_case_number": case_number,
            "display_case_number": case_number,
            "caption": _optional_text(record.get("caption")),
            "case_type": (
                category_parts[2] if len(category_parts) == 4 else None
            ),
            "filing_date": _optional_text(record.get("filing_date")),
            "disposition_date": None,
            "status": None,
            "access_state": "public",
            "native_access_state": (
                "official_anonymous_case_lookup_exact_case"
                if exact
                else "official_anonymous_case_lookup_party_search_index"
            ),
            "certified_record": False,
            "source_url": source_url,
            "preserve_existing_case_fields": not exact,
            "partial_case_shell": not exact,
            "parties": parties,
            "docket_entries": docket_entries if exact else [],
            "documents": [],
            "claims": (
                _new_mexico_case_lookup_claims(record) if exact else []
            ),
            "judicial_assignments": (
                judicial_assignments if exact else []
            ),
            "case_events": case_events if exact else [],
            "source_occurrences": [occurrence],
            "documents_available": False,
            "complaint_records": record.get("complaint_records"),
            "cause_records": record.get("cause_records"),
            "disposition_records": record.get("disposition_records"),
            "case_detail_sections": record.get("case_detail_sections"),
            "judge_assignment_history": record.get(
                "judge_assignment_history"
            ),
            "new_mexico_case_lookup_source_record": dict(record),
        }
    ]


def _ohio_reporter_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Attach a WebCite publication only when a case join is published."""

    if (
        _optional_text(record.get("source_id"))
        != OHIO_REPORTER_DECISIONS_SOURCE_ID
    ):
        raise ValueError("Ohio Reporter record has the wrong source_id")
    if _optional_text(record.get("record_kind")) != "judicial_publication":
        return []

    case_number = _optional_text(record.get("case_number"))
    if (
        case_number is None
        or _OHIO_REPORTER_SINGLE_CASE_NUMBER_RE.fullmatch(case_number) is None
    ):
        return []
    webcite = _required_text(
        record.get("webcite", record.get("publication_identity")),
        "ohio_reporter.webcite",
    )
    decided_date = _optional_text(record.get("decided_date"))
    posted_date = _optional_text(record.get("posted_date"))
    event_date = decided_date or posted_date
    native_document_id = _required_text(
        record.get("native_document_id"),
        "ohio_reporter.native_document_id",
    )
    source_url = _optional_text(
        record.get("search_url", record.get("source_url"))
    )
    occurrence = {
        "source_id": OHIO_REPORTER_DECISIONS_SOURCE_ID,
        "record_kind": "judicial_publication",
        "source_result_id": webcite,
        "canonical_ref": _optional_text(record.get("canonical_ref")),
        "case_type": "judicial_publication_join",
        "filing_date": posted_date or decided_date,
        "source_url": source_url,
        "publication_identity": webcite,
        "case_number_role": "optional_case_join",
        "independent_corroboration": False,
        "ohio_reporter_source_occurrence": dict(record),
    }
    return [
        {
            "source_id": OHIO_REPORTER_DECISIONS_SOURCE_ID,
            "record_kind": "case",
            "court": _ohio_reporter_court(record),
            "raw_case_number": case_number,
            "display_case_number": case_number,
            "caption": _optional_text(record.get("caption")),
            "case_type": "judicial_publication_join",
            "access_state": "public",
            "native_access_state": (
                "official Reporter publication with source case-number join"
            ),
            "certified_record": False,
            "source_url": source_url,
            "preserve_existing_case_fields": True,
            "partial_case_shell": True,
            "source_occurrences": [occurrence],
            "case_events": [
                {
                    "native_event_id": webcite,
                    "event_type": "judicial_publication",
                    "event_date": event_date,
                    "filed_date": posted_date,
                    "assertion_kind": "docket_metadata",
                    "native_assertion_kind": (
                        "official Reporter publication metadata"
                    ),
                    "publication_identity": webcite,
                    "case_number_role": "optional_case_join",
                    "independent_corroboration": False,
                    "ohio_reporter_source_publication": dict(record),
                }
            ],
            "documents": [
                {
                    "native_document_id": native_document_id,
                    "document_type": "official_judicial_publication_pdf",
                    "filed_date": posted_date or decided_date,
                    "source_url": _optional_text(
                        record.get("document_url")
                    ),
                    "mime_type": (
                        _optional_text(record.get("document_media_type"))
                        or "application/pdf"
                    ),
                    "access_state": "public",
                    "native_access_state": (
                        "official Reporter publication PDF representation"
                    ),
                    "publication_identity": webcite,
                    "case_number_role": "optional_case_join",
                    "independent_corroboration": False,
                    "ohio_reporter_source_document": {
                        "document_ref": record.get("document_ref"),
                        "native_document_id": native_document_id,
                        "document_url": record.get("document_url"),
                    },
                }
            ],
            "publication_identity": webcite,
            "case_number_role": "optional_case_join",
            "independent_corroboration": False,
            "ohio_reporter_source_record": dict(record),
        }
    ]


def _ohio_supreme_parties(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("parties"), "ohio_supreme.parties")
    ):
        party = dict(
            _mapping(value, f"ohio_supreme.parties[{index}]")
        )
        raw_name = _optional_text(party.get("name"))
        role = _optional_text(party.get("role"))
        if raw_name is None or role is None:
            continue
        attorneys: list[dict[str, Any]] = []
        for attorney_index, attorney_value in enumerate(
            _sequence(
                party.get("attorneys"),
                f"ohio_supreme.parties[{index}].attorneys",
            )
        ):
            attorney = dict(
                _mapping(
                    attorney_value,
                    (
                        f"ohio_supreme.parties[{index}]"
                        f".attorneys[{attorney_index}]"
                    ),
                )
            )
            attorney_name = _optional_text(attorney.get("name"))
            if attorney_name is None:
                continue
            registration_number = _optional_text(
                attorney.get("attorney_registration_number")
            )
            attorneys.append(
                {
                    "raw_name": attorney_name,
                    "bar_id": registration_number,
                    "attorney_registration_number": registration_number,
                    "counsel_of_record": bool(
                        attorney.get("counsel_of_record")
                    ),
                    "ohio_supreme_source_attorney": attorney,
                }
            )
        projected.append(
            {
                "sequence_no": index + 1,
                "role": role,
                "raw_name": raw_name,
                "pro_se": bool(party.get("pro_se")),
                "attorneys": attorneys,
                "ohio_supreme_source_party": party,
            }
        )
    return projected


def _ohio_supreme_docket_entries(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(
            record.get("docket_entries"),
            "ohio_supreme.docket_entries",
        )
    ):
        entry = dict(
            _mapping(value, f"ohio_supreme.docket_entries[{index}]")
        )
        native_entry_id = _required_text(
            entry.get("native_docket_entry_id"),
            (
                f"ohio_supreme.docket_entries[{index}]"
                ".native_docket_entry_id"
            ),
        )
        filing_parties = entry.get("filing_parties")
        filer_raw = (
            _optional_text(filing_parties)
            if isinstance(filing_parties, str)
            else (
                _json(filing_parties)
                if filing_parties is not None and filing_parties != ""
                else None
            )
        )
        entries.append(
            {
                "native_entry_id": native_entry_id,
                "sequence_no": index + 1,
                "event_code": _optional_text(entry.get("docket_code")),
                "event_type": (
                    _optional_text(entry.get("docket_type"))
                    or "docket_entry"
                ),
                "raw_text": _optional_text(entry.get("description")),
                "filed_date": _optional_text(entry.get("date_filed")),
                "filer_raw": filer_raw,
                "document_available": (
                    _optional_text(entry.get("native_document_id"))
                    is not None
                ),
                "access_state": "public",
                "native_access_state": (
                    "official eCMS docket-entry metadata"
                ),
                "filing_parties": filing_parties,
                "document_name": entry.get("document_name"),
                "native_document_id": entry.get("native_document_id"),
                "document_url": entry.get("document_url"),
                "ohio_supreme_source_docket_entry": entry,
            }
        )
    return entries


def _ohio_supreme_documents(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    docket_dates = {
        str(entry.get("native_docket_entry_id")): _optional_text(
            entry.get("date_filed")
        )
        for value in _sequence(
            record.get("docket_entries"),
            "ohio_supreme.docket_entries",
        )
        for entry in [_mapping(value, "ohio_supreme.docket_entry")]
        if entry.get("native_docket_entry_id") is not None
    }
    decision_dates = {
        str(decision.get("native_document_id")): _optional_text(
            decision.get("release_date")
        )
        for value in _sequence(
            record.get("decisions"),
            "ohio_supreme.decisions",
        )
        for decision in [_mapping(value, "ohio_supreme.decision")]
        if decision.get("native_document_id") is not None
    }
    documents: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("documents"), "ohio_supreme.documents")
    ):
        document = dict(
            _mapping(value, f"ohio_supreme.documents[{index}]")
        )
        native_document_id = _required_text(
            document.get("native_document_id"),
            (
                f"ohio_supreme.documents[{index}]"
                ".native_document_id"
            ),
        )
        section = _required_text(
            document.get("document_section"),
            f"ohio_supreme.documents[{index}].document_section",
        )
        linked_entry_id = _optional_text(
            document.get("linked_docket_entry_id")
        )
        documents.append(
            {
                "native_document_id": native_document_id,
                "docket_entry_native_id": linked_entry_id,
                "document_type": (
                    "docket_filing"
                    if section == "DocketItems"
                    else "decision_document"
                ),
                "filed_date": (
                    docket_dates.get(linked_entry_id)
                    if linked_entry_id is not None
                    else decision_dates.get(native_document_id)
                ),
                "source_url": _optional_text(document.get("source_url")),
                "mime_type": "application/pdf",
                "access_state": "public",
                "native_access_state": "official public eCMS PDF",
                "document_name": document.get("document_name"),
                "document_section": section,
                "ohio_supreme_source_document": document,
            }
        )
    return documents


def _ohio_supreme_decision_events(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("decisions"), "ohio_supreme.decisions")
    ):
        decision = dict(
            _mapping(value, f"ohio_supreme.decisions[{index}]")
        )
        identity = (
            _optional_text(decision.get("canonical_ref"))
            or _json(
                {
                    "case_number": record.get("case_number"),
                    "release_date": decision.get("release_date"),
                    "description_text": decision.get("description_text"),
                    "occurrence": index + 1,
                }
            )
        )
        events.append(
            {
                "native_event_id": (
                    "ohio-supreme:decision:"
                    + hashlib.sha256(
                        identity.encode("utf-8")
                    ).hexdigest()[:24]
                ),
                "event_type": "decision",
                "event_date": _optional_text(
                    decision.get("release_date")
                ),
                "disposition": (
                    _optional_text(decision.get("description_text"))
                    if bool(decision.get("disposes_case"))
                    else None
                ),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": (
                    "source-described eCMS decision item"
                ),
                "disposes_case": bool(decision.get("disposes_case")),
                "document_name": decision.get("document_name"),
                "native_document_id": decision.get(
                    "native_document_id"
                ),
                "linked_urls": decision.get("linked_urls"),
                "ohio_supreme_source_decision": decision,
            }
        )
    return events


def _ohio_supreme_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project eCMS search/detail records without using internal locators."""

    if _optional_text(record.get("source_id")) != OHIO_SUPREME_COURT_SOURCE_ID:
        raise ValueError("Ohio Supreme Court record has the wrong source_id")
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind not in {
        "state_supreme_court_case_index",
        "state_supreme_court_case",
    }:
        return []
    case_number = _required_text(
        record.get("case_number"),
        "ohio_supreme.case_number",
    )
    exact = record_kind == "state_supreme_court_case"
    decisions = (
        _sequence(record.get("decisions"), "ohio_supreme.decisions")
        if exact
        else []
    )
    disposing_dates = sorted(
        release_date
        for value in decisions
        for decision in [_mapping(value, "ohio_supreme.decision")]
        for release_date in [_optional_text(decision.get("release_date"))]
        if release_date is not None and bool(decision.get("disposes_case"))
    )
    projected = {
        "source_id": OHIO_SUPREME_COURT_SOURCE_ID,
        "record_kind": "case",
        "court": _ohio_supreme_court(),
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "caption": _optional_text(record.get("caption")),
        "case_type": _optional_text(record.get("case_type")),
        "filing_date": _optional_text(record.get("date_filed")),
        "disposition_date": (
            disposing_dates[-1] if disposing_dates else None
        ),
        "status": _optional_text(record.get("status")),
        "access_state": "public",
        "native_access_state": (
            "official anonymous eCMS exact-case response"
            if exact
            else "official anonymous eCMS case-search index"
        ),
        "certified_record": False,
        "source_url": _optional_text(record.get("source_url")),
        "preserve_existing_case_fields": not exact,
        "partial_case_shell": not exact,
        "parties": _ohio_supreme_parties(record) if exact else [],
        "docket_entries": (
            _ohio_supreme_docket_entries(record) if exact else []
        ),
        "documents": _ohio_supreme_documents(record) if exact else [],
        "case_events": (
            _ohio_supreme_decision_events(record) if exact else []
        ),
        "source_internal_case_locator": record.get(
            "source_internal_case_locator"
        ),
        "source_search_id": record.get("source_search_id"),
        "prior_jurisdiction": record.get("prior_jurisdiction"),
        "decisions": record.get("decisions"),
        "case_issues": record.get("case_issues"),
        "retrieval": record.get("retrieval"),
        "ohio_supreme_source_record": dict(record),
    }
    return [projected]


def _connecticut_docket(value: Any) -> tuple[str, str, str]:
    docket = _required_text(value, "connecticut.docket").upper()
    match = _CONNECTICUT_DOCKET_RE.fullmatch(docket)
    if match is None:
        raise ValueError("Connecticut record has an invalid normalized docket")
    return docket, match.group("location"), match.group("category")


def _connecticut_court(
    docket: str,
    location_code: str,
    source_court: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    expected_court_id = f"ct-superior-court-{location_code.casefold()}"
    source = dict(source_court or {})
    observed_court_id = _optional_text(source.get("court_id"))
    if observed_court_id is not None and observed_court_id != expected_court_id:
        raise ValueError(
            "Connecticut case court identity does not match its docket"
        )
    return {
        "court_id": expected_court_id,
        "native_court_id": location_code,
        "name": _optional_text(source.get("name"))
        or "Connecticut Superior Court",
        "state_code": "CT",
        "court_level": "trial",
        "branch": _optional_text(source.get("location")),
        "official_url": _optional_text(source.get("source_url")),
        "connecticut_source_court": source,
        "docket_identity": docket,
    }


def _connecticut_party(
    value: Any,
    *,
    index: int,
) -> dict[str, Any]:
    party = dict(_mapping(value, f"connecticut.parties[{index}]"))
    publisher_number = _required_text(
        party.get("publisher_party_number"),
        f"connecticut.parties[{index}].publisher_party_number",
    )
    role = _required_text(
        party.get("category"),
        f"connecticut.parties[{index}].category",
    )
    attorneys: list[dict[str, Any]] = []
    appearance_duplicate_counts: dict[str, int] = {}
    for appearance_index, appearance_value in enumerate(
        _sequence(
            party.get("appearances"),
            f"connecticut.parties[{index}].appearances",
        )
    ):
        appearance = dict(
            _mapping(
                appearance_value,
                (
                    f"connecticut.parties[{index}].appearances"
                    f"[{appearance_index}]"
                ),
            )
        )
        appearance_type = _optional_text(appearance.get("appearance_type"))
        display_name = _optional_text(appearance.get("display_name"))
        if (
            appearance_type is None
            or "attorney" not in appearance_type.casefold()
            or display_name is None
        ):
            continue
        appearance_tuple_hash = hashlib.sha256(
            _json(appearance).encode("utf-8")
        ).hexdigest()
        duplicate_ordinal = (
            appearance_duplicate_counts.get(appearance_tuple_hash, 0) + 1
        )
        appearance_duplicate_counts[appearance_tuple_hash] = duplicate_ordinal
        attorneys.append(
            {
                "raw_name": display_name,
                "bar_id": _optional_text(
                    appearance.get("publisher_juris_number")
                ),
                "effective_from": _optional_text(
                    appearance.get("file_date")
                ),
                "source_entry_id": (
                    f"party:{publisher_number}:appearance:"
                    f"{appearance_tuple_hash}:{duplicate_ordinal}"
                ),
                "source_entry_id_kind": (
                    "derived_from_complete_published_appearance_tuple_and_"
                    "identical_tuple_ordinal"
                ),
                "native_access_state": (
                    "official_case_detail_attorney_appearance"
                ),
                "connecticut_source_appearance": appearance,
            }
        )
    return {
        "sequence_no": index + 1,
        "role": role,
        "raw_name": _required_text(
            party.get("name"),
            f"connecticut.parties[{index}].name",
        ),
        "resolution_status": "unreviewed",
        "access_state": "public",
        "native_access_state": "official_case_detail_party",
        "attorneys": attorneys,
        "publisher_party_number": publisher_number,
        "appearance_status": party.get("appearance_status"),
        "connecticut_source_party": party,
    }


def _connecticut_docket_entry(value: Any, *, index: int) -> dict[str, Any]:
    entry = dict(_mapping(value, f"connecticut.docket_entries[{index}]"))
    document_number = _optional_text(
        entry.get("publisher_document_number")
    )
    entry_number = _optional_text(entry.get("publisher_entry_number"))
    identity_basis = _required_text(
        entry.get("identity_basis"),
        f"connecticut.docket_entries[{index}].identity_basis",
    )
    if document_number is not None:
        native_entry_id = f"document:{document_number}"
        if identity_basis != "publisher_document_number":
            raise ValueError("Connecticut DocumentNo identity basis changed")
    elif entry_number is not None:
        native_entry_id = f"entry:{entry_number}"
        if identity_basis != "publisher_entry_number":
            raise ValueError("Connecticut entry-number identity basis changed")
    else:
        canonical_ref = _required_text(
            entry.get("canonical_ref"),
            f"connecticut.docket_entries[{index}].canonical_ref",
        )
        derived_id = canonical_ref.rsplit("/", 1)[-1]
        if (
            identity_basis != "published_field_tuple"
            or not derived_id.startswith("derived-")
        ):
            raise ValueError("Connecticut derived docket identity changed")
        native_entry_id = f"tuple:{derived_id}"
    raw_text = " | ".join(
        part
        for part in (
            _optional_text(entry.get("description")),
            _optional_text(entry.get("additional_description")),
            _optional_text(entry.get("result")),
            _optional_text(entry.get("notes")),
        )
        if part is not None
    ) or None
    return {
        "native_entry_id": native_entry_id,
        "sequence_no": entry_number or str(index + 1),
        "event_type": "motion_pleading_document_case_status",
        "raw_text": raw_text,
        "filed_date": _optional_text(entry.get("file_date")),
        "status": _optional_text(entry.get("result")),
        "filer_raw": _optional_text(entry.get("filed_by")),
        "document_available": document_number is not None,
        "access_state": "public",
        "native_access_state": "official_case_detail_docket_metadata",
        "publisher_entry_number": entry_number,
        "publisher_document_number": document_number,
        "document_url": entry.get("document_url"),
        "connecticut_source_entry": entry,
    }


def _connecticut_case_events(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, value in enumerate(
        _sequence(record.get("scheduled_events"), "connecticut.scheduled_events")
    ):
        event = dict(
            _mapping(value, f"connecticut.scheduled_events[{index}]")
        )
        publisher_number = _required_text(
            event.get("publisher_event_number"),
            f"connecticut.scheduled_events[{index}].publisher_event_number",
        )
        events.append(
            {
                "native_event_id": f"scheduled:{publisher_number}",
                "event_type": "scheduled_court_event",
                "event_date": _optional_text(event.get("date")),
                "disposition": _optional_text(event.get("status")),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "official_scheduled_event",
                "connecticut_source_event": event,
            }
        )
    for index, value in enumerate(
        _sequence(record.get("history"), "connecticut.history")
    ):
        event = dict(_mapping(value, f"connecticut.history[{index}]"))
        canonical_ref = _required_text(
            event.get("canonical_ref"),
            f"connecticut.history[{index}].canonical_ref",
        )
        if event.get("identity_basis") != "published_transfer_field_tuple":
            raise ValueError("Connecticut transfer-history identity changed")
        events.append(
            {
                "native_event_id": canonical_ref,
                "event_type": "case_transfer",
                "event_date": _optional_text(event.get("transfer_date")),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "official_transfer_history",
                "connecticut_source_event": event,
            }
        )
    for index, value in enumerate(
        _sequence(record.get("notices"), "connecticut.notices")
    ):
        event = dict(_mapping(value, f"connecticut.notices[{index}]"))
        publisher_notice_id = _required_text(
            event.get("publisher_notice_id"),
            f"connecticut.notices[{index}].publisher_notice_id",
        )
        events.append(
            {
                "native_event_id": f"notice:{publisher_notice_id}",
                "event_type": "published_case_notice",
                "event_date": _optional_text(event.get("published_date")),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "official_case_notice",
                "publisher_publication_set_id": event.get(
                    "publisher_publication_set_id"
                ),
                "connecticut_source_event": event,
            }
        )
    disposition_value = record.get("disposition")
    disposition = (
        dict(_mapping(disposition_value, "connecticut.disposition"))
        if disposition_value is not None
        else {}
    )
    if any(_optional_text(value) for value in disposition.values()):
        identity = hashlib.sha256(
            _json(
                {
                    "date_raw": disposition.get("date_raw"),
                    "description": disposition.get("description"),
                    "judge_or_magistrate": disposition.get(
                        "judge_or_magistrate"
                    ),
                }
            ).encode("utf-8")
        ).hexdigest()
        events.append(
            {
                "native_event_id": f"disposition:{identity}",
                "event_type": "published_case_disposition",
                "event_date": _optional_text(disposition.get("date")),
                "disposition": _optional_text(
                    disposition.get("description")
                ),
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "official_case_detail_disposition",
                "connecticut_source_event": disposition,
            }
        )
    return events


def _connecticut_download_projection(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    docket_value = _optional_text(record.get("docket"))
    if docket_value is None:
        return []
    docket, location_code, case_category = _connecticut_docket(docket_value)
    document_number = _required_text(
        record.get("publisher_document_number"),
        "connecticut.publisher_document_number",
    )
    metadata = dict(
        _mapping(record.get("filing_metadata"), "connecticut.filing_metadata")
    )
    if _optional_text(metadata.get("publisher_document_number")) != document_number:
        raise ValueError("Connecticut downloaded PDF metadata identity changed")
    artifact_path = Path(
        _required_text(record.get("artifact_path"), "connecticut.artifact_path")
    )
    if not artifact_path.is_file():
        raise ValueError("Connecticut downloaded PDF artifact is missing")
    content = artifact_path.read_bytes()
    if not content.startswith(b"%PDF-"):
        raise ValueError("Connecticut downloaded artifact is not a PDF")
    expected_sha256 = _sha256(record.get("sha256"), "connecticut.sha256")
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if expected_sha256 != observed_sha256:
        raise ValueError("Connecticut downloaded PDF SHA-256 does not match")
    expected_length = _integer(
        record.get("byte_length"),
        "connecticut.byte_length",
        nullable=False,
    )
    if expected_length != len(content):
        raise ValueError("Connecticut downloaded PDF byte length does not match")
    if _required_text(record.get("content_type"), "connecticut.content_type") != (
        "application/pdf"
    ):
        raise ValueError("Connecticut downloaded artifact media type changed")
    native_entry_id = f"document:{document_number}"
    source_url = _required_text(record.get("source_url"), "connecticut.source_url")
    return [
        {
            "source_id": CONNECTICUT_CIVIL_FAMILY_SOURCE_ID,
            "record_kind": "case",
            "court": _connecticut_court(docket, location_code),
            "raw_case_number": docket,
            "display_case_number": docket,
            "case_type": case_category,
            "status": None,
            "access_state": "public",
            "native_access_state": "official_validated_filing_pdf",
            "certified_record": False,
            "source_url": source_url,
            "preserve_existing_case_fields": True,
            "partial_case_shell": True,
            "parties": [],
            "docket_entries": [
                {
                    "native_entry_id": native_entry_id,
                    "sequence_no": _optional_text(
                        metadata.get("publisher_entry_number")
                    ),
                    "event_type": "motion_pleading_document_case_status",
                    "raw_text": _optional_text(metadata.get("description")),
                    "filed_date": _optional_text(metadata.get("file_date")),
                    "status": _optional_text(metadata.get("result")),
                    "filer_raw": _optional_text(metadata.get("filed_by")),
                    "document_available": True,
                    "access_state": "public",
                    "native_access_state": "official_case_detail_docket_metadata",
                    "publisher_document_number": document_number,
                    "connecticut_source_entry": metadata,
                }
            ],
            "documents": [
                {
                    "native_document_id": document_number,
                    "docket_entry_native_id": native_entry_id,
                    "document_type": _optional_text(
                        metadata.get("description")
                    ),
                    "filed_date": _optional_text(metadata.get("file_date")),
                    "source_url": source_url,
                    "sha256": observed_sha256,
                    "mime_type": "application/pdf",
                    "storage_path": str(artifact_path),
                    "access_state": "public",
                    "native_access_state": "official_downloaded_filing_pdf",
                }
            ],
            "connecticut_source_record": dict(record),
        }
    ]


def _connecticut_projection_records(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if _optional_text(record.get("source_id")) != CONNECTICUT_CIVIL_FAMILY_SOURCE_ID:
        raise ValueError("Connecticut record has the wrong source_id")
    record_kind = _optional_text(record.get("record_kind"))
    if record_kind == "party_search_occurrence":
        return []
    if record_kind == "connecticut_case_filing_pdf":
        return _connecticut_download_projection(record)
    if record_kind != "connecticut_superior_court_case":
        return []
    docket, location_code, case_category = _connecticut_docket(
        record.get("docket")
    )
    source_court = _mapping(record.get("court"), "connecticut.court")
    disposition_value = record.get("disposition")
    disposition = (
        _mapping(disposition_value, "connecticut.disposition")
        if disposition_value is not None
        else {}
    )
    return [
        {
            "source_id": CONNECTICUT_CIVIL_FAMILY_SOURCE_ID,
            "record_kind": "case",
            "court": _connecticut_court(
                docket,
                location_code,
                source_court,
            ),
            "raw_case_number": docket,
            "display_case_number": docket,
            "caption": _optional_text(record.get("caption")),
            "case_type": _optional_text(record.get("case_type_code"))
            or case_category,
            "filing_date": _optional_text(record.get("file_date")),
            "disposition_date": _optional_text(disposition.get("date")),
            "status": None,
            "access_state": "public",
            "native_access_state": "official_anonymous_exact_case_detail",
            "certified_record": False,
            "source_url": _optional_text(record.get("source_url")),
            "parties": [
                _connecticut_party(value, index=index)
                for index, value in enumerate(
                    _sequence(record.get("parties"), "connecticut.parties")
                )
            ],
            "docket_entries": [
                _connecticut_docket_entry(value, index=index)
                for index, value in enumerate(
                    _sequence(
                        record.get("docket_entries"),
                        "connecticut.docket_entries",
                    )
                )
            ],
            "documents": [],
            "case_events": _connecticut_case_events(record),
            "case_category": record.get("case_category"),
            "case_type_description": record.get("case_type_description"),
            "return_date": record.get("return_date"),
            "property_address_raw": record.get("property_address_raw"),
            "list_type": record.get("list_type"),
            "trial_list_claim": record.get("trial_list_claim"),
            "last_action_date": record.get("last_action_date"),
            "schedule_as_of": record.get("schedule_as_of"),
            "information_updated_as_of": record.get(
                "information_updated_as_of"
            ),
            "filing_documents_metadata_only": record.get("filing_documents"),
            "connecticut_source_record": dict(record),
        }
    ]


def _projection_records_for_source(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    """Apply a source-family projection without obscuring dispatch order."""

    if source_id == FLORIDA_ACIS_SOURCE_ID:
        return _florida_acis_projection_records(record)
    if source_id == FLORIDA_NINTH_OPINIONS_SOURCE_ID:
        return []
    if source_id in FLORIDA_COURT_DIRECTORY_DATA_SOURCE_IDS:
        return []
    if source_id == OSCEOLA_BENCHMARK_SOURCE_ID:
        return _osceola_projection_records(record)
    if source_id in OSCEOLA_REPORT_SOURCE_IDS:
        return []
    if source_id in FRESNO_CASE_RECORD_SOURCE_IDS:
        return [_fresno_projection_record(record, source_id=source_id)]
    if source_id == CALIFORNIA_COURT_DIRECTORY_SOURCE_ID:
        return []
    if source_id == CALIFORNIA_OPINIONS_SOURCE_ID:
        return _california_opinion_projection_records(record)
    if source_id == GEORGIA_COURT_DIRECTORY_SOURCE_ID:
        return []
    if source_id in GEORGIA_COURT_ACCESS_SOURCE_IDS:
        return []
    if source_id in GEORGIA_AGGREGATE_COURT_DATA_SOURCE_IDS:
        return []
    if source_id == GEORGIA_SUPREME_DOCKET_SOURCE_ID:
        return _georgia_supreme_projection_records(record)
    if source_id == EDVA_BANKRUPTCY_SOURCE_ID:
        return [_edva_bankruptcy_projection_record(record)]
    if source_id in GEORGIA_SUPREME_PUBLICATION_SOURCE_IDS:
        return _georgia_supreme_publication_projection_records(
            record,
            source_id=source_id,
        )
    if source_id in SANTA_CLARA_SOURCE_IDS:
        return []
    if source_id == SAN_DIEGO_COURT_INDEX_SOURCE_ID:
        return _san_diego_court_index_projection_records(record)
    if source_id in ORANGE_CASE_RECORD_SOURCE_IDS:
        return _orange_projection_records(record, source_id=source_id)
    if source_id in RIVERSIDE_CASE_RECORD_SOURCE_IDS:
        return _riverside_projection_records(record, source_id=source_id)
    if source_id == QLD_ECOURTS_SOURCE_ID:
        return [_qld_ecourts_projection_record(record)]
    if source_id == WISCONSIN_COURT_DIRECTORY_SOURCE_ID:
        return []
    if source_id in DC_COURT_DIRECTORY_SOURCE_IDS:
        return []
    if source_id == WISCONSIN_WSCCA_SOURCE_ID:
        return [_wisconsin_wscca_projection_record(record)]
    if source_id == WISCONSIN_OPINIONS_SOURCE_ID:
        return [_wisconsin_opinion_projection_record(record)]
    if source_id == DC_APPELLATE_CASES_SOURCE_ID:
        return [_dc_appellate_projection_record(record)]
    if source_id == MARYLAND_PUBLIC_CASES_SOURCE_ID:
        return [_maryland_public_case_projection_record(record)]
    if source_id == MARYLAND_ESTATE_SOURCE_ID:
        return [_maryland_estate_projection_record(record)]
    if source_id in MARYLAND_ESTATE_SUPPLEMENT_SOURCE_IDS:
        return []
    if source_id == MARYLAND_JUDGMENT_LIENS_SOURCE_ID:
        return [_maryland_judgment_projection_record(record)]
    if source_id == MARYLAND_OPINIONS_SOURCE_ID:
        return [_maryland_opinion_projection_record(record)]
    if source_id == MARYLAND_BUSINESS_OPINIONS_SOURCE_ID:
        return _maryland_business_opinion_projection_records(record)
    if source_id == NEW_JERSEY_TAX_COURT_OPINIONS_SOURCE_ID:
        return _new_jersey_tax_court_opinion_projection_records(record)
    if source_id == WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID:
        return _washington_opinion_projection_records(record)
    if source_id == NEW_JERSEY_TAX_COURT_SOURCE_ID:
        return [_new_jersey_tax_court_projection_record(record)]
    if source_id == VA_GENERAL_DISTRICT_SOURCE_ID:
        return [_va_general_district_projection_record(record)]
    if source_id == MICHIGAN_APPELLATE_SOURCE_ID:
        return [_michigan_appellate_projection_record(record)]
    if source_id == MICHIGAN_BUSINESS_COURT_SOURCE_ID:
        return _michigan_business_court_projection_records(record)
    if source_id == CONNECTICUT_CIVIL_FAMILY_SOURCE_ID:
        return _connecticut_projection_records(record)
    if source_id == NEW_MEXICO_CASE_LOOKUP_SOURCE_ID:
        return _new_mexico_case_lookup_projection_records(record)
    if source_id == TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID:
        return _texas_supreme_publication_projection_records(record)
    if source_id == DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID:
        return _delaware_common_pleas_projection_records(record)
    if source_id == LICKING_COMMON_PLEAS_SOURCE_ID:
        return []
    if source_id == FRANKLIN_MUNICIPAL_SOURCE_ID:
        return _franklin_municipal_projection_records(record)
    if source_id == FRANKLIN_PROBATE_SOURCE_ID:
        return _franklin_probate_projection_records(record)
    if source_id == FRANKLIN_CIO_SOURCE_ID:
        return _franklin_cio_projection_records(record)
    if source_id == OHIO_REPORTER_DECISIONS_SOURCE_ID:
        return _ohio_reporter_projection_records(record)
    if source_id == OHIO_SUPREME_COURT_SOURCE_ID:
        return _ohio_supreme_projection_records(record)
    if source_id == LOS_ANGELES_NAME_INDEX_SOURCE_ID:
        return [_los_angeles_name_index_projection_record(record)]
    if source_id in DC_CALENDAR_HEARING_SOURCE_IDS:
        return [_dc_calendar_projection_record(record, source_id=source_id)]
    if source_id in OREGON_TYLER_MUNICIPAL_SOURCE_IDS:
        return _eugene_projection_records(record, source_id=source_id)
    if source_id == DC_OPINIONS_SOURCE_ID:
        return [_dc_opinion_projection_record(record)]
    return [dict(record)]


def ingest_court_data_delivery_receipt(
    receipt: Mapping[str, Any],
    *,
    court_db: str | Path = DEFAULT_COURT_DB,
) -> dict[str, Any]:
    """Persist an OJD delivery receipt and its byte-level file inventory."""

    if not isinstance(receipt, Mapping):
        raise ValueError("delivery receipt must be an object")
    if receipt.get("schema_version") != OJCIN_DELIVERY_RECEIPT_SCHEMA_VERSION:
        raise ValueError(
            "unsupported delivery receipt schema; expected "
            f"{OJCIN_DELIVERY_RECEIPT_SCHEMA_VERSION}"
        )
    receipt_id = _required_text(receipt.get("receipt_id"), "receipt_id")
    if not _SHA256_RE.fullmatch(receipt_id.lower()):
        raise ValueError("receipt_id must be a SHA-256 hex digest")
    product = _mapping(receipt.get("product"), "product")
    source_id = _required_text(product.get("source_id"), "product.source_id")
    delivery = _mapping(receipt.get("delivery"), "delivery")
    delivery_version = _required_text(
        delivery.get("version"),
        "delivery.version",
    )
    received_at = _required_text(
        delivery.get("received_at"),
        "delivery.received_at",
    )
    artifact_set_sha256 = _required_text(
        receipt.get("artifact_set_sha256"),
        "artifact_set_sha256",
    ).lower()
    if not _SHA256_RE.fullmatch(artifact_set_sha256):
        raise ValueError("artifact_set_sha256 must be a SHA-256 hex digest")
    files = _sequence(receipt.get("files"), "files")
    declared_file_count = _integer(
        receipt.get("file_count"),
        "file_count",
        nullable=False,
    )
    if declared_file_count != len(files):
        raise ValueError("file_count does not match files")
    total_size = _integer(
        receipt.get("total_size_bytes"),
        "total_size_bytes",
        nullable=False,
    )
    assert total_size is not None
    observed_total_size = 0
    normalized_files: list[dict[str, Any]] = []
    for index, value in enumerate(files):
        file_record = dict(_mapping(value, f"files[{index}]"))
        relative_path = _required_text(
            file_record.get("relative_path"),
            f"files[{index}].relative_path",
        )
        size_bytes = _integer(
            file_record.get("size_bytes"),
            f"files[{index}].size_bytes",
            nullable=False,
        )
        if size_bytes is None or size_bytes < 0:
            raise ValueError(f"files[{index}].size_bytes must be nonnegative")
        file_sha256 = _required_text(
            file_record.get("sha256"),
            f"files[{index}].sha256",
        ).lower()
        if not _SHA256_RE.fullmatch(file_sha256):
            raise ValueError(f"files[{index}].sha256 must be a SHA-256 digest")
        observed_total_size += size_bytes
        normalized_files.append(
            {
                **file_record,
                "relative_path": relative_path,
                "size_bytes": size_bytes,
                "sha256": file_sha256,
            }
        )
    if observed_total_size != total_size:
        raise ValueError("total_size_bytes does not match files")

    payload_lineage_key = hashlib.sha256(
        _json(
            {
                "product_id": source_id,
                "delivery_version": delivery_version,
                "artifact_set_sha256": artifact_set_sha256,
            }
        ).encode("utf-8")
    ).hexdigest()
    interpretation = _mapping(
        receipt.get("interpretation"),
        "interpretation",
    )
    if interpretation.get("rows_interpreted") is not False:
        raise ValueError("delivery receipt must preserve rows_interpreted=false")
    if interpretation.get("records_parsed") != 0:
        raise ValueError("delivery receipt must preserve records_parsed=0")

    db = connect_courts(court_db)
    try:
        with db:
            db.execute(
                """
                INSERT INTO court_data_delivery_receipt(
                    receipt_id, source_id, product_id, product_name,
                    system_name, publisher, delivery_version, received_at,
                    received_at_basis, provider_reference, correction_state,
                    delivery_scope_note, specification_refs_json,
                    case_document_refs_json, artifact_root,
                    artifact_set_sha256, payload_lineage_key, file_count,
                    total_size_bytes, interpretation_json, created_at, raw_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?
                )
                ON CONFLICT(receipt_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    product_id=excluded.product_id,
                    product_name=excluded.product_name,
                    system_name=excluded.system_name,
                    publisher=excluded.publisher,
                    delivery_version=excluded.delivery_version,
                    received_at=excluded.received_at,
                    received_at_basis=excluded.received_at_basis,
                    provider_reference=excluded.provider_reference,
                    correction_state=excluded.correction_state,
                    delivery_scope_note=excluded.delivery_scope_note,
                    specification_refs_json=excluded.specification_refs_json,
                    case_document_refs_json=excluded.case_document_refs_json,
                    artifact_root=excluded.artifact_root,
                    artifact_set_sha256=excluded.artifact_set_sha256,
                    payload_lineage_key=excluded.payload_lineage_key,
                    file_count=excluded.file_count,
                    total_size_bytes=excluded.total_size_bytes,
                    interpretation_json=excluded.interpretation_json,
                    raw_json=excluded.raw_json
                """,
                (
                    receipt_id.lower(),
                    source_id,
                    source_id,
                    _optional_text(product.get("name")),
                    _optional_text(product.get("system")),
                    _optional_text(product.get("publisher")),
                    delivery_version,
                    received_at,
                    _optional_text(delivery.get("received_at_basis")),
                    _optional_text(delivery.get("provider_reference")),
                    _optional_text(delivery.get("correction_state")),
                    _optional_text(delivery.get("delivery_scope_note")),
                    _json(delivery.get("specification_refs") or []),
                    _json(delivery.get("case_document_refs") or []),
                    _optional_text(receipt.get("artifact_root")),
                    artifact_set_sha256,
                    payload_lineage_key,
                    len(normalized_files),
                    total_size,
                    _json(interpretation),
                    _optional_text(receipt.get("created_at")),
                    _json(receipt),
                ),
            )
            db.execute(
                "DELETE FROM court_data_delivery_file WHERE receipt_id=?",
                (receipt_id.lower(),),
            )
            for file_record in normalized_files:
                db.execute(
                    """
                    INSERT INTO court_data_delivery_file(
                        receipt_id, relative_path, absolute_path, size_bytes,
                        sha256, format_observation_json, zip_members_json,
                        raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        receipt_id.lower(),
                        file_record["relative_path"],
                        _optional_text(file_record.get("absolute_path")),
                        file_record["size_bytes"],
                        file_record["sha256"],
                        _json(file_record.get("format_observation")),
                        _json(file_record.get("zip_members") or []),
                        _json(file_record),
                    ),
                )
    finally:
        db.close()
    return {
        "status": "ingested",
        "source_id": source_id,
        "receipt_id": receipt_id.lower(),
        "payload_lineage_key": payload_lineage_key,
        "artifact_set_sha256": artifact_set_sha256,
        "files_ingested": len(normalized_files),
        "case_rows_projected": 0,
        "court_db": str(Path(court_db)),
    }


def ingest_envelope(
    envelope: Mapping[str, Any],
    *,
    court_db: str | Path = DEFAULT_COURT_DB,
    artifact_path: str | Path | None = None,
    artifact_sha256: str | None = None,
) -> dict[str, Any]:
    """Persist one result envelope and transactionally project canonical cases."""
    lineage = validate_envelope(envelope)
    raw_path, raw_sha256 = _artifact_metadata(
        envelope,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
    )
    counts = {
        "courts": 0,
        "related_courts": 0,
        "cases": 0,
        "related_cases": 0,
        "case_relations": 0,
        "parties": 0,
        "attorneys": 0,
        "representations": 0,
        "judicial_officers": 0,
        "assignments": 0,
        "claims": 0,
        "docket_entries": 0,
        "case_events": 0,
        "documents": 0,
        "restriction_events": 0,
    }
    refs: list[str] = []
    snapshot_only_count = 0
    snapshot_only_kinds: dict[str, int] = {}
    db = connect_courts(court_db)
    try:
        db.execute("BEGIN IMMEDIATE")
        _ensure_docket_hearing_columns(db)
        snapshot_id = _insert_snapshot(
            db,
            envelope,
            lineage,
            raw_artifact_path=raw_path,
            raw_artifact_sha256=raw_sha256,
        )
        if lineage["status"] in PROJECTABLE_STATUSES:
            for index, value in enumerate(lineage["records"]):
                record = _mapping(value, f"records[{index}]")
                projection_records = _projection_records_for_source(
                    record,
                    source_id=lineage["source_id"],
                )
                projectable_projection_records = [
                    projection_record
                    for projection_record in projection_records
                    if _has_projectable_case_shape(projection_record)
                ]
                if not projectable_projection_records:
                    snapshot_only_count += 1
                    record_kind = (
                        _optional_text(record.get("record_kind")) or "untyped_record"
                    )
                    snapshot_only_kinds[record_kind] = (
                        snapshot_only_kinds.get(record_kind, 0) + 1
                    )
                for projection_record in projectable_projection_records:
                    refs.append(
                        _project_case(
                            db,
                            projection_record,
                            source_id=lineage["source_id"],
                            snapshot_id=snapshot_id,
                            counts=counts,
                        )
                    )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {
        "status": "ingested",
        "source_id": lineage["source_id"],
        "source_status": lineage["status"],
        "snapshot_id": snapshot_id,
        "query_fingerprint": lineage["query_fingerprint"],
        "raw_artifact_path": raw_path,
        "raw_artifact_sha256": raw_sha256,
        "projected": counts,
        "snapshot_only": {
            "record_count": snapshot_only_count,
            "record_kinds": dict(sorted(snapshot_only_kinds.items())),
        },
        "canonical_refs": refs,
        "court_db": str(Path(court_db)),
    }


def _load_envelope(path: str) -> dict[str, Any]:
    if path == "-":
        value = json.load(sys.stdin)
    else:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("result envelope must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest shared public-record envelopes into the court sidecar"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Ingest one JSON result envelope")
    ingest.add_argument("input", help="Envelope JSON path, or - for stdin")
    ingest.add_argument("--court-db", default=str(DEFAULT_COURT_DB))
    ingest.add_argument(
        "--artifact",
        help="Exact raw artifact path; defaults to the input JSON file",
    )
    ingest.add_argument("--artifact-sha256")
    add_output_args(ingest)
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command != "ingest":
        raise ValueError(f"unsupported command: {args.command}")
    envelope = _load_envelope(args.input)
    artifact = args.artifact
    if artifact is None and args.input != "-":
        artifact = args.input
    return ingest_envelope(
        envelope,
        court_db=args.court_db,
        artifact_path=artifact,
        artifact_sha256=args.artifact_sha256,
    )


def _emit(result: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        result,
        args,
        summary=(
            f"State court envelope {result['source_status']} "
            f"snapshot #{result['snapshot_id']}"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(
        f"Snapshot #{result['snapshot_id']} preserved for "
        f"{result['source_id']} ({result['source_status']}); "
        f"{result['projected']['cases']} cases projected"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = execute(args)
        _emit(result, args)
        return 0
    except (OSError, sqlite3.Error, TypeError, ValueError) as error:
        if getattr(args, "json_out", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "command": args.command,
                        "error": str(error),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
