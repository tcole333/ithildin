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
from pathlib import Path
from typing import Any

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
    )


PROJECTABLE_STATUSES = frozenset(
    {
        ResultStatus.OK.value,
        ResultStatus.PARTIAL.value,
    }
)
SNAPSHOT_STATUSES = frozenset(status.value for status in ResultStatus)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
            raise ValueError(
                "raw artifact SHA-256 does not match the artifact file"
            )
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
        raise ValueError(
            f"{status} envelopes cannot contain projectable records"
        )
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


def _coverage(lineage: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
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
            _optional_text(
                court_data.get("court_level", court_data.get("level"))
            ),
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
        "documents",
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
    source_id = _optional_text(payload.get("source_id")) or envelope_source_id
    if source_id != envelope_source_id:
        raise ValueError("case source_id does not match envelope source_id")
    court_id = _upsert_court(
        db,
        source_id,
        _mapping(payload.get("court"), "case.court"),
    )
    raw_case_number = _required_text(
        payload.get("raw_case_number", payload.get("case_number")),
        "case.raw_case_number",
    )
    access_state, native_access_state = _access_state(
        payload.get("access_state"),
        "case.access_state",
    )
    db.execute(
        """
        INSERT INTO case_record(
            source_id, court_id, raw_case_number, display_case_number,
            source_internal_id, caption, case_type, filing_date,
            disposition_date, status, access_state, native_access_state,
            certified_record,
            source_url, snapshot_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, court_id, raw_case_number) DO UPDATE SET
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
        """,
        (
            source_id,
            court_id,
            raw_case_number,
            _optional_text(payload.get("display_case_number")),
            _optional_text(payload.get("source_internal_id")),
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
        WHERE source_id=? AND court_id=? AND raw_case_number=?
        """,
        (source_id, court_id, raw_case_number),
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
    raw_name = _required_text(party.get("raw_name", party.get("name")), "party.raw_name")
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
    representation_values.extend(
        _sequence(payload.get("attorneys"), "case.attorneys")
    )
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
            event_code, raw_text, filed_date, entered_date, event_date,
            filer_raw, document_available, access_state, native_access_state,
            snapshot_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id, native_entry_id) DO UPDATE SET
            source_id=excluded.source_id,
            sequence_no=excluded.sequence_no,
            subsequence_no=excluded.subsequence_no,
            event_code=excluded.event_code,
            raw_text=excluded.raw_text,
            filed_date=excluded.filed_date,
            entered_date=excluded.entered_date,
            event_date=excluded.event_date,
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
            _optional_text(
                entry.get("subsequence_no", entry.get("subsequence"))
            ),
            _optional_text(entry.get("event_code")),
            _optional_text(entry.get("raw_text", entry.get("text"))),
            _optional_text(entry.get("filed_date")),
            _optional_text(entry.get("entered_date")),
            _optional_text(entry.get("event_date")),
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
    values = payload.get("case_events", payload.get("events"))
    for index, value in enumerate(_sequence(values, "case.case_events")):
        event = _mapping(value, f"case.case_events[{index}]")
        event_type = _required_text(event.get("event_type"), "case_event.event_type")
        event_date = _optional_text(event.get("event_date"))
        native_event_id = _optional_text(event.get("native_event_id")) or ""
        native_assertion_kind = _optional_text(event.get("assertion_kind"))
        assertion_kind = (
            canonical_assertion_kind(native_assertion_kind)
            if native_assertion_kind is not None
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
    )


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
        "cases": 0,
        "parties": 0,
        "attorneys": 0,
        "representations": 0,
        "judicial_officers": 0,
        "assignments": 0,
        "docket_entries": 0,
        "case_events": 0,
        "documents": 0,
        "restriction_events": 0,
    }
    refs: list[str] = []
    db = connect_courts(court_db)
    try:
        db.execute("BEGIN IMMEDIATE")
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
                refs.append(
                    _project_case(
                        db,
                        record,
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
