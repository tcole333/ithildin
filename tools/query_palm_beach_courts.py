#!/usr/bin/env python3
"""Query Palm Beach County Clerk eCaseView through its public guest UI.

The portal's case pages are tied to a browser session, so this adapter delegates
the UI interaction to ``_pbc_court_browser_helper.js`` and normalizes the
returned public fields into the shared state/local-court result contract.

Examples:
    uv run python tools/query_palm_beach_courts.py search KRAFT --json
    uv run python tools/query_palm_beach_courts.py search \
        50-2019-MM-002346-AXXX-NB --search-scope case-number --json
    uv run python tools/query_palm_beach_courts.py case \
        50-2019-MM-002346-AXXX-NB --output case.json
    uv run python tools/query_palm_beach_courts.py docket \
        50-2019-MM-002346-AXXX-NB --limit 100 --output docket.json
    uv run python tools/query_palm_beach_courts.py download \
        50-2019-MM-002346-AXXX-NB 5 /tmp/din-5.pdf --json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import acquisition_result_status
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
    from tools.public_records_http import inferred_schema, schema_fingerprint
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import acquisition_result_status
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
    from public_records_http import inferred_schema, schema_fingerprint
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-fl-palm-beach-ecaseview"
STATE_CODE = "FL"
COUNTY_GEOID = "12099"
BASE_URL = "https://appsgp.mypalmbeachclerk.com/ecaseview"
SEARCH_URL = f"{BASE_URL}/Search"
HELPER_PATH = Path(__file__).with_name("_pbc_court_browser_helper.js")

GENERIC_COURT_ID = "fl-15-palm-beach"
CIRCUIT_COURT_ID = "fl-15-palm-beach-circuit"
COUNTY_COURT_ID = "fl-15-palm-beach-county"

SOURCE_WARNINGS = (
    "Broad searches that reach 200 displayed matches have reached eCaseView's "
    "published recent-result ceiling.",
    "Online images are uncertified public copies; eCaseView preserves separate "
    "states for public images, View on Request, requests in process, and entries "
    "without an online image.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Palm Beach County Clerk eCaseView",
    source_role="county_clerk_case_index_docket_and_public_images",
    base_url=BASE_URL,
    dataset_id="ecaseview-public-guest",
    metadata={
        "authority": "Palm Beach County Clerk of the Circuit Court & Comptroller",
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "judicial_circuit": "15",
        "authentication": "public_guest_session",
        "platform_family": "palm_beach_ecaseview",
        "source_result_ceiling": 200,
    },
)

_COUNTY_CASE_CODES = frozenset({"CC", "CO", "CT", "MM", "SC", "TR"})
_CIRCUIT_CASE_CODES = frozenset(
    {"CA", "CF", "CJ", "CP", "DP", "DR", "GA", "MH"}
)

HelperRunner = Callable[[Sequence[str], float], Mapping[str, Any]]


class PalmBeachSelectionError(ValueError):
    """A requested selector or cursor cannot be represented by this adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


class PalmBeachBrowserError(RuntimeError):
    """The browser helper could not complete a source operation."""

    def __init__(
        self,
        message: str,
        *,
        error_type: str = "Error",
        document_state: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.document_state = document_state
        self.details = dict(details or {})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _field(row: Mapping[str, Any], *names: str) -> str | None:
    folded = {str(key).strip().casefold(): value for key, value in row.items()}
    for name in names:
        value = folded.get(name.casefold())
        normalized = _text(value)
        if normalized is not None:
            return normalized
    return None


def _source_schema(payload: Mapping[str, Any]) -> str:
    return schema_fingerprint(inferred_schema([payload]))


def _date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for date_format in (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M",
    ):
        try:
            parsed = datetime.strptime(normalized, date_format)
        except ValueError:
            continue
        if "%H" in date_format or "%I" in date_format:
            return parsed.isoformat(timespec="minutes")
        return parsed.date().isoformat()
    return None


def _case_code(case_number: str) -> str | None:
    match = re.search(r"(?:^|-)\d{4}-([A-Z]{2})(?:-|$)", case_number.upper())
    return match.group(1) if match else None


def _court_kind(
    *,
    case_number: str,
    court_type: str | None = None,
    case_type: str | None = None,
) -> str:
    label = " ".join(
        value.casefold() for value in (court_type, case_type) if value
    )
    if any(
        token in label
        for token in (
            "county",
            "misdemeanor",
            "traffic",
            "small claim",
            "municipal",
        )
    ):
        return "county"
    if any(
        token in label
        for token in (
            "circuit",
            "felony",
            "family",
            "probate",
            "guardianship",
            "juvenile",
        )
    ):
        return "circuit"
    code = _case_code(case_number)
    if code in _COUNTY_CASE_CODES:
        return "county"
    if code in _CIRCUIT_CASE_CODES:
        return "circuit"
    return "generic"


def _court_payload(
    *,
    case_number: str,
    court_type: str | None = None,
    case_type: str | None = None,
) -> dict[str, Any]:
    kind = _court_kind(
        case_number=case_number,
        court_type=court_type,
        case_type=case_type,
    )
    if kind == "county":
        court_id = COUNTY_COURT_ID
        name = "Palm Beach County Court, Fifteenth Judicial Circuit"
        level = "county"
    elif kind == "circuit":
        court_id = CIRCUIT_COURT_ID
        name = "Palm Beach Circuit Court, Fifteenth Judicial Circuit"
        level = "circuit"
    else:
        court_id = GENERIC_COURT_ID
        name = "Palm Beach Courts, Fifteenth Judicial Circuit"
        level = None
    return {
        "court_id": court_id,
        "native_court_id": _text(court_type) or kind,
        "name": name,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": level,
        "division": _text(court_type),
        "official_url": BASE_URL,
    }


def _case_record(
    *,
    case_number: str,
    court_type: str | None,
    case_type: str | None,
    caption: str | None,
    filing_date: str | None,
    status: str | None,
    source_url: str | None,
    native_access_state: str,
    schema: str,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    court = _court_payload(
        case_number=case_number,
        court_type=court_type,
        case_type=case_type,
    )
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court["court_id"],
            case_number,
            native_id=case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": caption,
        "case_type": case_type,
        "filing_date": filing_date,
        "status": status,
        "access_state": "public",
        "native_access_state": native_access_state,
        "certified_record": False,
        "source_url": source_url or SEARCH_URL,
        "parties": [],
        "attorneys": [],
        "judicial_assignments": [],
        "docket_entries": [],
        "case_events": [],
        "documents": [],
        "schema_fingerprint": schema,
        "raw": dict(raw),
    }


def normalize_search_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalize every displayed eCaseView search row."""

    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("eCaseView search response has no records array")
    schema = _source_schema(payload)
    normalized: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, Mapping):
            raise ValueError("eCaseView search record is not an object")
        case_number = _field(row, "Case Number", "case_number")
        if case_number is None:
            raise ValueError("eCaseView search record has no case number")
        court_type = _field(row, "Court Type")
        case_type = _field(row, "Case Type")
        href = _field(row, "case_href")
        record = _case_record(
            case_number=case_number,
            court_type=court_type,
            case_type=case_type,
            caption=_field(row, "Case Style", "Caption"),
            filing_date=_date(_field(row, "File Date", "Filing Date")),
            status=_field(row, "Status"),
            source_url=urljoin(f"{BASE_URL}/", href) if href else SEARCH_URL,
            native_access_state="public_guest_search",
            schema=schema,
            raw=row,
        )
        record["arrest_date"] = _date(_field(row, "Arrest Date"))
        record["source_total_reported"] = payload.get("total_reported")
        record["source_ceiling_reached"] = bool(
            payload.get("source_ceiling_reached")
        )
        normalized.append(record)
    return normalized


def _raw_name(row: Mapping[str, Any]) -> str | None:
    parts = [
        _field(row, "First Name"),
        _field(row, "Middle Name"),
        _field(row, "Last Name"),
        _field(row, "Suffix"),
    ]
    return " ".join(value for value in parts if value) or _field(row, "Name")


def _people(
    rows: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    parties: list[dict[str, Any]] = []
    attorneys: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return parties, attorneys, assignments
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            continue
        raw_name = _raw_name(row)
        role = _field(row, "Party Type", "Role")
        if raw_name is None or role is None:
            continue
        role_key = re.sub(r"[^a-z0-9]+", "_", role.casefold()).strip("_")
        common = {
            "raw_name": raw_name,
            "source_role": role,
            "source_sequence_no": index,
            "raw_dob": _field(row, "DOB", "Date of Birth"),
            "raw": dict(row),
        }
        if "judge" in role.casefold():
            assignments.append(
                {
                    "officer": {"raw_name": raw_name},
                    "assignment_role": role,
                    "source_sequence_no": index,
                    "raw": dict(row),
                }
            )
        elif "attorney" in role.casefold() or "counsel" in role.casefold():
            attorneys.append(
                {
                    "raw_name": raw_name,
                    "role": role_key,
                    "source_role": role,
                    "party_role": "unresolved",
                    "representation_status": "unresolved",
                    "raw": dict(row),
                }
            )
        else:
            parties.append(
                {
                    "sequence_no": index,
                    "role": role_key or "party",
                    **common,
                }
            )
    return parties, attorneys, assignments


def _document_state(row: Mapping[str, Any]) -> tuple[str, str, str]:
    label = _field(row, "Document State") or ""
    folded = label.casefold()
    handler = (_field(row, "view_handler") or "").casefold()
    action = (_field(row, "view_form_action") or "").casefold()
    if "process" in folded:
        return "view_on_request_in_process", "restricted", label
    if (
        "request" in folded
        or "locked" in folded
        or folded == "vor"
        or handler == "vorimage"
        or "vorstatus=" in action
    ):
        return "view_on_request", "restricted", label
    if (
        "view image" in folded
        or "image available" in folded
        or handler == "viewimage"
    ):
        return "public", "public", label or "image_available"
    return "not_available_online", "unknown", label or "not_available_online"


def _docket_entries(
    case_number: str,
    rows: Any,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        din = _field(row, "DIN", "source_din")
        if din is None:
            continue
        native_id = f"{case_number}:{din}"
        source_state, access_state, native_state = _document_state(row)
        action = _field(row, "view_form_action")
        source_url = (
            urljoin(f"{BASE_URL}/", action)
            if action
            else f"{BASE_URL}/CaseData/Dockets"
        )
        filed_date = _date(_field(row, "Effective Date"))
        description = _field(row, "Description")
        documents = []
        if source_state != "not_available_online":
            documents.append(
                {
                    "native_document_id": native_id,
                    "docket_entry_native_id": native_id,
                    "document_type": "docket_filing",
                    "filed_date": filed_date,
                    "source_url": source_url,
                    "mime_type": (
                        "application/pdf"
                        if source_state == "public"
                        else None
                    ),
                    "certification_status": (
                        "uncertified_online_copy"
                        if source_state == "public"
                        else None
                    ),
                    "access_state": access_state,
                    "native_access_state": native_state,
                    "source_access_state": source_state,
                    "source_docket_id": _field(row, "source_docket_id"),
                    "din": din,
                    "description": description,
                    "certified_copy_available": bool(
                        row.get("certified_copy_available")
                    ),
                    "raw": dict(row),
                }
            )
        output.append(
            {
                "native_entry_id": native_id,
                "sequence_no": din,
                "event_code": "docket_entry",
                "raw_text": description,
                "filed_date": filed_date,
                "entered_date": filed_date,
                "notes": _field(row, "Notes"),
                "document_available": source_state
                in {
                    "public",
                    "view_on_request",
                    "view_on_request_in_process",
                },
                "access_state": "public",
                "native_access_state": "public_guest_docket",
                "source_document_state": source_state,
                "source_document_state_label": native_state,
                "source_docket_id": _field(row, "source_docket_id"),
                "documents": documents,
                "raw": dict(row),
            }
        )
    return output


def _court_events(case_number: str, rows: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output
    seen: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        source_date = _field(row, "Date")
        source_time = _field(row, "Time")
        combined = " ".join(value for value in (source_date, source_time) if value)
        identity = {
            "date": source_date,
            "time": source_time,
            "description": _field(row, "Description"),
            "location": _field(row, "Location"),
            "room": _field(row, "Room"),
            "notes": _field(row, "Notes"),
        }
        digest = sha256_fingerprint(identity)[:24]
        seen[digest] = seen.get(digest, 0) + 1
        output.append(
            {
                "native_event_id": (
                    f"{case_number}:court-event:{digest}:{seen[digest]}"
                ),
                "event_type": "court_event",
                "native_event_type": identity["description"],
                "event_date": _date(combined),
                "source_date_raw": source_date,
                "source_time_raw": source_time,
                "description": identity["description"],
                "location": identity["location"],
                "room": identity["room"],
                "notes": identity["notes"],
                "assertion_kind": "docket_metadata",
                "raw": dict(row),
            }
        )
    return output


def _charges(rows: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        output.append(
            {
                "count": _field(row, "Count"),
                "statute": _field(row, "Statute"),
                "description": _field(row, "Description"),
                "disposition": _field(row, "Disposition"),
                "disposition_date": _date(_field(row, "Disposition Date")),
                "offense_date": _date(_field(row, "Offense Date")),
                "plea": _field(row, "Plea"),
                "raw": dict(row),
            }
        )
    return output


def _charge_events(
    case_number: str,
    charges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    events = []
    for index, charge in enumerate(charges, start=1):
        count = _text(charge.get("count")) or str(index)
        events.append(
            {
                "native_event_id": f"{case_number}:charge:{count}",
                "event_type": "charge",
                "event_date": charge.get("offense_date"),
                "disposition": charge.get("disposition"),
                "assertion_kind": "charge",
                "count": count,
                "statute": charge.get("statute"),
                "description": charge.get("description"),
                "disposition_date": charge.get("disposition_date"),
                "plea": charge.get("plea"),
                "raw": dict(charge.get("raw") or charge),
            }
        )
    return events


def normalize_case_bundle(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize all public tabs from one session-bound case bundle."""

    if payload.get("found") is False:
        return None
    banner = payload.get("banner")
    banner = banner if isinstance(banner, Mapping) else {}
    case_info = payload.get("case_info")
    case_info = case_info if isinstance(case_info, Mapping) else {}
    case_number = _field(banner, "case_number", "Case Number")
    if case_number is None:
        raise ValueError("eCaseView case bundle has no case number")
    court_type = _field(case_info, "Court Type")
    case_type = _field(case_info, "Case Type")
    record = _case_record(
        case_number=case_number,
        court_type=court_type,
        case_type=case_type or _case_code(case_number),
        caption=_field(banner, "case_style", "Case Style"),
        filing_date=_date(_field(case_info, "File Date", "Filing Date")),
        status=_field(case_info, "Status", "Case Status"),
        source_url=_field(payload, "source_url"),
        native_access_state=(
            _field(banner, "access_level", "Access Level")
            or "public_guest_case"
        ),
        schema=_source_schema(payload),
        raw=payload,
    )
    parties, attorneys, assignments = _people(payload.get("parties"))
    charges = _charges(payload.get("charges"))
    events = _court_events(case_number, payload.get("court_events"))
    events.extend(_charge_events(case_number, charges))
    record.update(
        {
            "parties": parties,
            "attorneys": attorneys,
            "judicial_assignments": assignments,
            "docket_entries": _docket_entries(
                case_number,
                payload.get("dockets"),
            ),
            "case_events": events,
            "charges": charges,
            "sentences": payload.get("sentences")
            if isinstance(payload.get("sentences"), list)
            else [],
            "fees": payload.get("fees")
            if isinstance(payload.get("fees"), list)
            else [],
            "warrants": payload.get("warrants")
            if isinstance(payload.get("warrants"), list)
            else [],
            "arrests": payload.get("arrests")
            if isinstance(payload.get("arrests"), list)
            else [],
            "case_info": dict(case_info),
            "section_urls": dict(payload.get("section_urls") or {}),
            "division": _field(case_info, "Division", "Division Name"),
            "incident_number": _field(case_info, "Incident Number"),
            "arrest_date": _date(_field(case_info, "Arrest Date")),
            "offense_date": _date(_field(case_info, "Offense Date")),
            "source_access_level": _field(
                banner,
                "access_level",
                "Access Level",
            ),
        }
    )
    return record


def _download_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    case_number = _field(payload, "case_number")
    din = _field(payload, "din")
    if case_number is None or din is None:
        raise ValueError("eCaseView download receipt lacks case number or DIN")
    court = _court_payload(case_number=case_number)
    native_id = f"{case_number}:{din}"
    document = {
        "native_document_id": native_id,
        "document_type": "docket_filing",
        "filed_date": _date(_field(payload, "effective_date")),
        "source_url": _field(payload, "source_url"),
        "sha256": _field(payload, "sha256"),
        "mime_type": _field(payload, "mime_type") or "application/pdf",
        "storage_path": _field(payload, "destination"),
        "certification_status": "uncertified_online_copy",
        "access_state": "public",
        "native_access_state": (
            _field(payload, "document_state") or "public"
        ),
        "din": din,
        "source_docket_id": _field(payload, "source_docket_id"),
        "byte_count": payload.get("byte_count"),
        "suggested_filename": _field(payload, "suggested_filename"),
        "raw": dict(payload),
    }
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court["court_id"],
            case_number,
            native_id=case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": _field(payload, "case_style"),
        "case_type": _case_code(case_number),
        "filing_date": None,
        "status": None,
        "access_state": "public",
        "native_access_state": "public_guest_case",
        "certified_record": False,
        "source_url": SEARCH_URL,
        "parties": [],
        "attorneys": [],
        "judicial_assignments": [],
        "docket_entries": [],
        "case_events": [],
        "documents": [document],
        "schema_fingerprint": _source_schema(payload),
        "raw": dict(payload),
    }


def _parse_helper_error(stderr: str) -> PalmBeachBrowserError:
    lines = [line for line in stderr.splitlines() if line.strip()]
    if lines:
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping):
            error = payload.get("error")
            if isinstance(error, Mapping):
                return PalmBeachBrowserError(
                    str(error.get("message") or "eCaseView helper failed"),
                    error_type=str(error.get("type") or "Error"),
                    document_state=_text(error.get("document_state")),
                    details=(
                        error.get("details")
                        if isinstance(error.get("details"), Mapping)
                        else {}
                    ),
                )
    return PalmBeachBrowserError(
        stderr.strip() or "eCaseView helper failed without an error payload"
    )


def run_browser_helper(
    arguments: Sequence[str],
    timeout: float,
) -> Mapping[str, Any]:
    """Run the local browser helper and decode its one-object JSON response."""

    node = shutil.which("node")
    if node is None:
        raise PalmBeachBrowserError(
            "Node.js is required to run the eCaseView browser helper",
            error_type="RuntimeDependencyError",
        )
    try:
        process = subprocess.run(
            [node, str(HELPER_PATH), *map(str, arguments)],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise PalmBeachBrowserError(
            f"eCaseView browser helper exceeded {timeout:g} seconds",
            error_type="TimeoutError",
            details={"timeout_seconds": timeout},
        ) from error
    if process.returncode:
        raise _parse_helper_error(process.stderr)
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise PalmBeachBrowserError(
            "eCaseView browser helper returned invalid JSON",
            error_type="SourcePayloadError",
            details={"stdout_excerpt": process.stdout[:500]},
        ) from error
    if not isinstance(payload, Mapping):
        raise PalmBeachBrowserError(
            "eCaseView browser helper returned a non-object payload",
            error_type="SourcePayloadError",
        )
    return payload


def _cursor_offset(cursor: str | None, operation: str) -> int:
    if cursor is None:
        return 0
    match = re.fullmatch(
        rf"pbc:{re.escape(operation)}:offset:(\d+)",
        cursor,
    )
    if match is None:
        raise PalmBeachSelectionError(
            "invalid_cursor",
            f"Cursor does not belong to Palm Beach {operation}: {cursor}",
            details={"cursor": cursor, "operation": operation},
        )
    return int(match.group(1))


def _slice(
    values: Sequence[dict[str, Any]],
    *,
    operation: str,
    cursor: str | None,
    limit: int | None,
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(cursor, operation)
    if offset >= len(values):
        return [], None
    stop = len(values) if limit is None else min(len(values), offset + limit)
    next_cursor = (
        f"pbc:{operation}:offset:{stop}" if stop < len(values) else None
    )
    return list(values[offset:stop]), next_cursor


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            "query": args.query,
            "search_scope": args.search_scope,
            "match_mode": args.match_mode,
            "first_name": args.first_name,
        }
        requested_limit = args.limit
        cursor = args.cursor
    elif args.command in {"case", "docket", "documents"}:
        parameters = {"case_number": args.case_number}
        if args.command in {"docket", "documents"}:
            requested_limit = args.limit
            cursor = args.cursor
    elif args.command == "download":
        parameters = {
            "case_number": args.case_number,
            "din": args.din,
            "destination": str(args.destination),
            "overwrite": args.overwrite,
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Palm Beach County, Florida",
            state_code=STATE_CODE,
            county_fips=COUNTY_GEOID,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "The selected acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=decision,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: PalmBeachSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _browser_failure(
    query: PublicRecordsQuery,
    error: PalmBeachBrowserError,
) -> PublicRecordsResult:
    state = error.document_state
    if state in {"view_on_request", "view_on_request_in_process"}:
        status = ResultStatus.RESTRICTED
        category = "document_access"
    elif state == "not_available_online":
        status = ResultStatus.UNAVAILABLE
        category = "document_access"
    elif error.error_type in {"TimeoutError"}:
        status = ResultStatus.UNAVAILABLE
        category = "transport"
    elif error.error_type in {"SourcePayloadError"}:
        status = ResultStatus.SOURCE_CHANGED
        category = "source_schema"
    else:
        status = ResultStatus.UNAVAILABLE
        category = "browser_runtime"
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=state
                or re.sub(
                    r"(?<!^)(?=[A-Z])",
                    "_",
                    error.error_type,
                ).lower(),
                message=str(error),
                category=category,
                retryable=error.error_type == "TimeoutError",
                details={
                    **error.details,
                    "error_type": error.error_type,
                    "document_state": state,
                },
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    payload: Mapping[str, Any],
    *,
    args: argparse.Namespace,
) -> PublicRecordsResult:
    records = normalize_search_records(payload)
    page, next_cursor = _slice(
        records,
        operation="search",
        cursor=args.cursor,
        limit=args.limit,
    )
    if not payload.get("source_ceiling_reached"):
        return PublicRecordsResult.success(
            query,
            page,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.PARTIAL,
        [
            PublicRecordsError(
                code="source_result_ceiling",
                message=(
                    "eCaseView displayed its maximum 200 recent matches; "
                    "additional matching cases may exist"
                ),
                category="source_limit",
                retryable=False,
                details={
                    "source_total_reported": payload.get("total_reported"),
                    "displayed_records": len(records),
                    "source_result_ceiling": 200,
                },
            )
        ],
        records=page,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _case_collection_result(
    query: PublicRecordsQuery,
    record: dict[str, Any] | None,
    *,
    operation: str,
    cursor: str | None,
    limit: int | None,
) -> PublicRecordsResult:
    if record is None:
        return PublicRecordsResult.success(query, [], warnings=SOURCE_WARNINGS)
    if operation == "case":
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    entries = list(record["docket_entries"])
    selected, next_cursor = _slice(
        entries,
        operation=operation,
        cursor=cursor,
        limit=limit,
    )
    if not selected:
        return PublicRecordsResult.success(query, [], warnings=SOURCE_WARNINGS)
    record = dict(record)
    record["docket_entries"] = selected
    record["source_docket_entry_count"] = len(entries)
    if operation == "documents":
        record["source_document_count"] = sum(
            len(entry.get("documents") or []) for entry in entries
        )
    return PublicRecordsResult.success(
        query,
        [record],
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    runner: HelperRunner,
) -> PublicRecordsResult:
    if args.command == "runtime-check":
        payload = runner(["runtime-check"], args.timeout)
        record = {
            "record_kind": "source_runtime",
            "source_id": SOURCE_ID,
            "schema_fingerprint": _source_schema(payload),
            **dict(payload),
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        payload = runner(["probe"], args.timeout)
        record = {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "schema_fingerprint": _source_schema(payload),
            **dict(payload),
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "search":
        helper_args = [
            "search",
            args.query,
            "--scope",
            args.search_scope,
            "--mode",
            args.match_mode,
        ]
        if args.first_name:
            helper_args.extend(["--first-name", args.first_name])
        payload = runner(helper_args, args.timeout)
        return _search_result(query, payload, args=args)
    if args.command in {"case", "docket", "documents"}:
        payload = runner(["case", args.case_number], args.timeout)
        record = normalize_case_bundle(payload)
        return _case_collection_result(
            query,
            record,
            operation=args.command,
            cursor=getattr(args, "cursor", None),
            limit=getattr(args, "limit", None),
        )
    if args.command == "download":
        helper_args = [
            "download",
            args.case_number,
            args.din,
            str(args.destination),
        ]
        if args.overwrite:
            helper_args.append("--overwrite")
        payload = runner(helper_args, args.timeout)
        record = _download_record(payload)
        destination = _field(payload, "destination")
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[destination] if destination else (),
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Palm Beach court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    helper_runner: HelperRunner | None = None,
) -> PublicRecordsResult:
    """Execute one Palm Beach eCaseView operation."""

    query = build_query(args)
    if access_decision is not None and not access_decision.get("allowed", False):
        result = _decision_failure(query, access_decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    runner = helper_runner or run_browser_helper
    try:
        result = _execute_command(args, query, runner)
    except PalmBeachSelectionError as error:
        result = _selection_failure(query, error)
    except PalmBeachBrowserError as error:
        if error.document_state in {"case_not_found", "document_not_found"}:
            result = PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        else:
            result = _browser_failure(query, error)
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


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Maximum browser-helper runtime in seconds",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the Palm Beach County Clerk public eCaseView portal"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    runtime = sub.add_parser(
        "runtime-check",
        help="Check the local Node, Playwright, and browser runtime",
    )
    _add_common(runtime)

    probe = sub.add_parser(
        "probe",
        help="Open the guest search form and validate its principal controls",
    )
    _add_common(probe)

    search = sub.add_parser(
        "search",
        help="Search by party/company name or full case number",
    )
    search.add_argument("query")
    search.add_argument(
        "--search-scope",
        choices=("party", "case-number"),
        default="party",
    )
    search.add_argument(
        "--match-mode",
        choices=("exact", "starts-with"),
        default="exact",
        help="Party-name match mode; case-number searches are exact",
    )
    search.add_argument("--first-name")
    search.add_argument(
        "--limit",
        type=int,
        help="Return at most this many displayed records",
    )
    search.add_argument("--cursor")
    _add_common(search)

    case = sub.add_parser(
        "case",
        help="Fetch all public case tabs for one full case number",
    )
    case.add_argument("case_number")
    _add_common(case)

    for command, help_text in (
        ("docket", "Fetch and page through all displayed docket entries"),
        (
            "documents",
            "Fetch docket entries with their public/request image states",
        ),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument("case_number")
        command_parser.add_argument(
            "--limit",
            type=int,
            help="Return at most this many entries",
        )
        command_parser.add_argument("--cursor")
        _add_common(command_parser)

    download = sub.add_parser(
        "download",
        help="Download one public docket image by full case number and DIN",
    )
    download.add_argument("case_number")
    download.add_argument("din")
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_common(download)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Palm Beach eCaseView {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"{result.status.value}: {len(result.records)} record(s)")
    for error in result.errors:
        print(f"{error.code}: {error.message}", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if (
        args.command == "search"
        and args.search_scope == "case-number"
        and args.first_name
    ):
        parser.error("--first-name applies only to party searches")
    if (
        args.command == "search"
        and args.search_scope == "case-number"
        and args.match_mode != "exact"
    ):
        parser.error("case-number searches use --match-mode exact")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
