#!/usr/bin/env python3
"""Query Riverside County Superior Court calendars and tentative rulings.

The court publishes two anonymous, complementary record layers:

* eCourtCalendars JSON for the current day and next three business days; and
* a department directory of tentative-ruling PDF artifacts.

The eCalendar JSON response is complete for each selected department, area of
law, and date range.  Its visible grid pagination is client-side presentation,
not a transport page or collection ceiling.  With no caller ``--limit``, this
adapter retrieves the complete source-published window for every selected
source combination.

Direct HTTP clients currently receive 403 responses from both official hosts,
so live acquisition follows the public pages in an ordinary Chrome session.

Examples:
    uv run python tools/query_riverside_court.py calendar \
        --courthouse "Historic Court House" --department 8 \
        --area-of-law probate --output /tmp/riverside-calendar.json
    uv run python tools/query_riverside_court.py ruling-index \
        --output /tmp/riverside-rulings.json
    uv run python tools/query_riverside_court.py ruling PS1 \
        --download /tmp/riverside-ps1.pdf \
        --output /tmp/riverside-ps1.json
    uv run python tools/query_riverside_court.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
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
        utc_now_iso,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
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
        utc_now_iso,
    )


COURT_NAME = "Superior Court of California, County of Riverside"
COURT_ID = "ca-riverside-superior"
COUNTY_FIPS = "06065"
STATE_CODE = "CA"

SOURCE_FAMILY_ID = "us-ca-riverside-superior-court-public-records"
CALENDAR_SOURCE_ID = "us-ca-riverside-superior-court-ecalendar"
RULING_SOURCE_ID = "us-ca-riverside-superior-court-tentative-rulings"
PUBLIC_ACCESS_SOURCE_ID = "us-ca-riverside-superior-court-public-access"
PUBLIC_ACCESS_GUIDE_SOURCE_ID = (
    "us-ca-riverside-superior-court-public-access-guide"
)
NAME_INDEX_SOURCE_ID = "us-ca-riverside-superior-court-name-index-products"
CLERK_SEARCH_SOURCE_ID = "us-ca-riverside-superior-court-clerk-search"
RECORDS_SOURCE_ID = (
    "us-ca-riverside-superior-court-records-and-certified-copies"
)
PROBATE_NOTES_SOURCE_ID = "us-ca-riverside-superior-court-probate-notes"
HIGH_INTEREST_SOURCE_ID = (
    "us-ca-riverside-superior-court-high-interest-cases"
)
TRANSCRIPT_SOURCE_ID = "us-ca-riverside-superior-court-transcript-requests"
APPELLATE_DIVISION_SOURCE_ID = (
    "us-ca-riverside-superior-court-appellate-division"
)
FOURTH_DISTRICT_SOURCE_ID = (
    "us-ca-fourth-district-division-two-case-information"
)

COURT_SITE_URL = "https://www.riverside.courts.ca.gov"
CALENDAR_URL = "https://ecourtcalendars.riverside.courts.ca.gov/"
CALENDAR_INFO_URL = f"{COURT_SITE_URL}/online-services/court-calendars"
RULING_INDEX_URL = f"{COURT_SITE_URL}/online-services/tentative-rulings"
PUBLIC_ACCESS_INFO_URL = (
    f"{COURT_SITE_URL}/online-services/search-court-records-public-access"
)
PUBLIC_ACCESS_URL = "https://epublic-access.riverside.courts.ca.gov/public-portal/"
PURCHASE_INDEXES_URL = f"{COURT_SITE_URL}/online-services/purchase-indexes"
CLERK_SEARCH_URL = "https://rrs.riverside.courts.ca.gov/"
LOCAL_FORMS_URL = (
    "https://riverside.courts.ca.gov/mServices/LocalForms/local-forms.php"
)
CERTIFIED_COPY_FORM_URL = (
    "https://riverside.courts.ca.gov/system/files/ri-mc011.pdf"
)
PROBATE_INFORMATION_URL = (
    f"{COURT_SITE_URL}/self-help/estates-wills-trusts"
)
HIGH_INTEREST_CASES_URL = (
    f"{COURT_SITE_URL}/general-information/media-information/"
    "high-interest-cases"
)
TRANSCRIPT_REQUEST_URL = "https://transcriptrequest.riverside.courts.ca.gov/"
APPEALS_URL = f"{COURT_SITE_URL}/divisions/appeals"
FOURTH_DISTRICT_SEARCH_URL = (
    "https://appellatecases.courtinfo.ca.gov/search.cfm?dist=42"
)

COMPLEMENT_SOURCE_IDS_BY_URL = {
    PUBLIC_ACCESS_URL: PUBLIC_ACCESS_SOURCE_ID,
    PUBLIC_ACCESS_INFO_URL: PUBLIC_ACCESS_GUIDE_SOURCE_ID,
    PURCHASE_INDEXES_URL: NAME_INDEX_SOURCE_ID,
    CLERK_SEARCH_URL: CLERK_SEARCH_SOURCE_ID,
    LOCAL_FORMS_URL: RECORDS_SOURCE_ID,
    PROBATE_INFORMATION_URL: PROBATE_NOTES_SOURCE_ID,
    HIGH_INTEREST_CASES_URL: HIGH_INTEREST_SOURCE_ID,
    TRANSCRIPT_REQUEST_URL: TRANSCRIPT_SOURCE_ID,
    APPEALS_URL: APPELLATE_DIVISION_SOURCE_ID,
    FOURTH_DISTRICT_SEARCH_URL: FOURTH_DISTRICT_SOURCE_ID,
}

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_RETRY_ATTEMPTS = 3
CURSOR_PREFIX = "riverside-court-calendar:v1:"
CURSOR_VERSION = 1
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
BROWSER_HELPER_PATH = Path(__file__).with_name(
    "_riverside_court_browser_helper.js"
)

CALENDAR_REQUIRED_KEYS = frozenset(
    {
        "case_name",
        "case_number",
        "date_time",
        "event_name",
        "source_courthouse",
        "source_department",
        "source_area_of_law",
    }
)

CALENDAR_WARNINGS = (
    "eCourtCalendars is a current hearing publication, not a complete case "
    "index, register of actions, or document repository.",
    "The source publishes the current day and next three business days; that "
    "source window is separate from any caller result limit.",
)
RULING_WARNINGS = (
    "The directory can retain old department PDFs and no-tentative "
    "placeholders; directory membership and artifact dates are reported "
    "separately.",
    "A tentative ruling is not necessarily the final order entered after the "
    "hearing.",
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_FIPS,
    name="Riverside County, California",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Riverside County",
    metadata={
        "court_id": COURT_ID,
        "court_name": COURT_NAME,
    },
)

CALENDAR_SOURCE = SourceMetadata(
    source_id=CALENDAR_SOURCE_ID,
    name="Riverside Superior Court eCourtCalendars",
    source_role="county_superior_court_current_hearing_calendar",
    base_url=CALENDAR_URL,
    dataset_id="riverside-superior-court-ecalendar",
    metadata={
        "authority": COURT_NAME,
        "calendar_information_url": CALENDAR_INFO_URL,
        "authentication": "none",
        "transport": "headed_chrome",
        "source_window": "current day plus next three business days",
        "native_response_paging": None,
        "visible_grid_paging": "client_side_only",
        "areas_of_law_observed": [
            "Civil",
            "Criminal",
            "Probate",
            "Traffic",
        ],
    },
)

RULING_SOURCE = SourceMetadata(
    source_id=RULING_SOURCE_ID,
    name="Riverside Superior Court Tentative Rulings",
    source_role="county_superior_court_tentative_ruling_publications",
    base_url=RULING_INDEX_URL,
    dataset_id="riverside-superior-court-tentative-rulings",
    metadata={
        "authority": COURT_NAME,
        "authentication": "none",
        "transport": "headed_chrome",
        "artifact_format": "pdf",
        "publication_model": "department directory",
    },
)


class RiversideCourtError(RuntimeError):
    """Source, transport, selection, or parser error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: str = "source",
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.status = status
        self.retryable = retryable
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class RiversideSelectionError(RiversideCourtError):
    """The requested value does not select a verified source operation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


class RiversideSourceChangedError(RiversideCourtError):
    """The official source no longer matches the verified contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="source_schema",
            status=ResultStatus.SOURCE_CHANGED,
            details=details,
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _normalized_department(value: Any) -> str:
    normalized = re.sub(
        r"^department\s+",
        "",
        _clean(value) or "",
        flags=re.I,
    )
    return re.sub(r"\s+", "", normalized).upper()


def _pacific_today() -> str:
    return datetime.now(PACIFIC_TZ).date().isoformat()


def _family_source() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_FAMILY_ID,
        name="Riverside Superior Court Public Record Sources",
        source_role="county_superior_court_source_family",
        base_url=CALENDAR_INFO_URL,
        dataset_id="riverside-superior-court-public-records",
        metadata={
            "authority": COURT_NAME,
            "implemented_sources": [
                CALENDAR_SOURCE_ID,
                RULING_SOURCE_ID,
            ],
        },
    )


def _query(
    source: SourceMetadata,
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata=metadata or {},
        ),
    )


def _run_browser_helper(
    selection: Mapping[str, Any],
    *,
    timeout: float,
    minimum_interval: float,
    max_attempts: int,
) -> Mapping[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise RiversideCourtError(
            "browser_runtime_missing",
            "Node.js is required for the Riverside court browser transport",
            category="runtime",
        )
    if not BROWSER_HELPER_PATH.is_file():
        raise RiversideCourtError(
            "browser_helper_missing",
            f"Riverside court browser helper not found: {BROWSER_HELPER_PATH}",
            category="runtime",
        )
    command = [
        node,
        str(BROWSER_HELPER_PATH),
        canonical_json(selection),
        str(timeout),
        str(minimum_interval),
        str(max_attempts),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RiversideCourtError(
            "browser_helper_timeout",
            "Riverside court browser acquisition did not complete",
            category="transport",
            retryable=True,
            details={"execution_timeout_seconds": 900},
        ) from error
    except OSError as error:
        raise RiversideCourtError(
            "browser_helper_failed",
            f"Could not start the Riverside court browser helper: {error}",
            category="runtime",
        ) from error
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RiversideCourtError(
            "browser_helper_invalid",
            "Riverside court browser helper did not return JSON",
            category="runtime",
            details={
                "return_code": completed.returncode,
                "stderr": completed.stderr[-1000:],
            },
        ) from error
    if not isinstance(payload, Mapping):
        raise RiversideCourtError(
            "browser_helper_invalid",
            "Riverside court browser helper returned a non-object payload",
            category="runtime",
        )
    if payload.get("ok") is not True:
        raw_error = payload.get("error")
        details = dict(raw_error) if isinstance(raw_error, Mapping) else {}
        raw_status = details.pop("status", ResultStatus.UNAVAILABLE.value)
        try:
            status = ResultStatus(str(raw_status))
        except ValueError:
            status = ResultStatus.UNAVAILABLE
        nested_details = details.pop("details", {})
        raise RiversideCourtError(
            str(details.pop("code", "browser_helper_failed")),
            str(
                details.pop(
                    "message",
                    "Riverside court browser acquisition failed",
                )
            ),
            status=status,
            category=str(details.pop("category", "transport")),
            retryable=bool(details.pop("retryable", False)),
            details=(
                dict(nested_details)
                if isinstance(nested_details, Mapping)
                else {}
            ),
        )
    return payload


class RiversideCourtClient:
    """Thin wrapper around the browser transport, replaceable in tests."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        browser_runner: Callable[..., Mapping[str, Any]] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval cannot be negative")
        if retry_attempts <= 0:
            raise ValueError("retry_attempts must be positive")
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.retry_attempts = retry_attempts
        self._browser_runner = browser_runner or _run_browser_helper

    def run(self, selection: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._browser_runner(
            selection,
            timeout=self.timeout,
            minimum_interval=self.minimum_interval,
            max_attempts=self.retry_attempts,
        )

    def close(self) -> None:
        return None


def _calendar_parameters(
    *,
    courthouse: str | None,
    department: str | None,
    area_of_law: str | None,
    start_date: str | None,
    end_date: str | None,
    anchor_date: str,
) -> dict[str, Any]:
    return {
        "courthouse": _clean(courthouse),
        "department": (
            _normalized_department(department) if _clean(department) else None
        ),
        "area_of_law": (
            (_clean(area_of_law) or "").title() if _clean(area_of_law) else None
        ),
        "start_date": _clean(start_date),
        "end_date": _clean(end_date),
        "anchor_date": anchor_date,
    }


def _calendar_identity(parameters: Mapping[str, Any]) -> str:
    return sha256_fingerprint(
        {
            "source_id": CALENDAR_SOURCE_ID,
            "operation": "calendar",
            "parameters": parameters,
        }
    )


def _encode_cursor(
    *,
    offset: int,
    query_identity: str,
    snapshot_identity: str,
) -> str:
    payload = canonical_json(
        {
            "version": CURSOR_VERSION,
            "offset": offset,
            "query_identity": query_identity,
            "snapshot_identity": snapshot_identity,
        }
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return CURSOR_PREFIX + token


def _decode_cursor(
    cursor: str,
    *,
    query_identity: str,
    snapshot_identity: str,
) -> int:
    if not cursor.startswith(CURSOR_PREFIX):
        raise RiversideSelectionError(
            "invalid_cursor",
            "Riverside calendar cursor has an unknown prefix",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding)
        payload = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RiversideSelectionError(
            "invalid_cursor",
            "Riverside calendar cursor is malformed",
        ) from error
    if not isinstance(payload, Mapping):
        raise RiversideSelectionError(
            "invalid_cursor",
            "Riverside calendar cursor is not an object",
        )
    if payload.get("version") != CURSOR_VERSION:
        raise RiversideSelectionError(
            "invalid_cursor_version",
            "Riverside calendar cursor version is unsupported",
        )
    if payload.get("query_identity") != query_identity:
        raise RiversideSelectionError(
            "cursor_query_mismatch",
            "Riverside calendar cursor belongs to a different query",
        )
    if payload.get("snapshot_identity") != snapshot_identity:
        raise RiversideSelectionError(
            "cursor_snapshot_changed",
            "Riverside calendar publication changed since the cursor was issued",
            details={
                "cursor_snapshot": payload.get("snapshot_identity"),
                "current_snapshot": snapshot_identity,
            },
        )
    offset = payload.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise RiversideSelectionError(
            "invalid_cursor_offset",
            "Riverside calendar cursor has an invalid offset",
        )
    return offset


def _split_source_text(value: Any) -> list[str]:
    raw = str(value or "")
    parts = re.split(r"<br\s*/?>|\r?\n", raw, flags=re.I)
    return [cleaned for item in parts if (cleaned := _clean(item))]


def _normalize_calendar_record(
    source_record: Mapping[str, Any],
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    missing = sorted(
        key
        for key in CALENDAR_REQUIRED_KEYS
        if key not in source_record
    )
    if missing:
        raise RiversideSourceChangedError(
            "calendar_record_schema_changed",
            "Riverside eCalendar record lacks verified fields",
            details={"missing": missing},
        )
    case_number = _clean(source_record.get("case_number"))
    case_name = _clean(source_record.get("case_name"))
    date_time = _clean(source_record.get("date_time"))
    courthouse = _clean(source_record.get("source_courthouse"))
    department = _clean(source_record.get("source_department"))
    area_of_law = _clean(source_record.get("source_area_of_law"))
    if not all(
        [case_number, case_name, date_time, courthouse, department, area_of_law]
    ):
        raise RiversideSourceChangedError(
            "calendar_record_identity_missing",
            "Riverside eCalendar record lacks a stable hearing identity",
            details={
                "case_number": case_number,
                "case_name": case_name,
                "date_time": date_time,
                "courthouse": courthouse,
                "department": department,
                "area_of_law": area_of_law,
            },
        )
    try:
        datetime.fromisoformat(date_time)
    except ValueError as error:
        raise RiversideSourceChangedError(
            "calendar_datetime_changed",
            "Riverside eCalendar returned a non-ISO hearing datetime",
            details={"date_time": date_time},
        ) from error
    hearings = _split_source_text(source_record.get("event_name"))
    attorneys = _split_source_text(source_record.get("attorney"))
    identity_payload = {
        "court_id": COURT_ID,
        "case_number": case_number,
        "date_time": date_time,
        "courthouse": courthouse,
        "department": department,
        "area_of_law": area_of_law,
        "hearings": hearings,
    }
    address_parts = [
        _clean(source_record.get("address1")),
        _clean(source_record.get("address2")),
        _clean(source_record.get("city")),
        _clean(source_record.get("state")),
        _clean(source_record.get("zip_code")),
    ]
    return {
        "canonical_ref": (
            "RIVERSIDE-CALENDAR:"
            + hashlib.sha256(
                canonical_json(identity_payload).encode("utf-8")
            ).hexdigest()
        ),
        "source_id": CALENDAR_SOURCE_ID,
        "record_kind": "court_calendar_event",
        "court": {
            "court_id": COURT_ID,
            "name": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "state_code": STATE_CODE,
        },
        "case_number": case_number,
        "case_name": case_name,
        "case_type": _clean(source_record.get("case_type")),
        "area_of_law": area_of_law,
        "hearing": {
            "date_time": date_time,
            "date": date_time[:10],
            "time": date_time[11:19] if len(date_time) >= 19 else None,
            "names": hearings,
            "special_status": _clean(source_record.get("special_status")),
        },
        "courthouse": {
            "name": courthouse,
            "source_id": str(source_record.get("source_location_id") or ""),
            "address": ", ".join(part for part in address_parts if part),
        },
        "department": _normalized_department(department),
        "department_label": department,
        "department_source_id": str(
            source_record.get("source_department_id") or ""
        ),
        "judicial_officer": _clean(source_record.get("judge_name")),
        "judicial_officer_role": _clean(source_record.get("judge_role")),
        "attorneys": attorneys,
        "charge_data": _split_source_text(source_record.get("charge_data")),
        "source_payload": dict(source_record),
        "retrieved_at": retrieved_at,
    }


def _calendar_sort_key(record: Mapping[str, Any]) -> tuple[str, ...]:
    hearing = record.get("hearing")
    courthouse = record.get("courthouse")
    return (
        str(hearing.get("date_time") if isinstance(hearing, Mapping) else ""),
        str(courthouse.get("name") if isinstance(courthouse, Mapping) else ""),
        str(record.get("department") or ""),
        str(record.get("area_of_law") or ""),
        str(record.get("case_number") or ""),
        str(record.get("case_name") or ""),
        str(record.get("canonical_ref") or ""),
    )


def _validate_calendar_payload(payload: Mapping[str, Any]) -> None:
    business_days = payload.get("business_days")
    selector_tree = payload.get("selector_tree")
    records = payload.get("records")
    if (
        not isinstance(business_days, Sequence)
        or isinstance(business_days, (str, bytes))
        or not business_days
        or not all(
            isinstance(item, str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item)
            for item in business_days
        )
    ):
        raise RiversideSourceChangedError(
            "calendar_business_days_changed",
            "Riverside eCalendar returned an invalid business-day window",
        )
    if (
        not isinstance(selector_tree, Sequence)
        or isinstance(selector_tree, (str, bytes))
        or not selector_tree
    ):
        raise RiversideSourceChangedError(
            "calendar_selector_tree_changed",
            "Riverside eCalendar returned no source selector tree",
        )
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise RiversideSourceChangedError(
            "calendar_records_changed",
            "Riverside eCalendar returned a non-list record payload",
        )


def calendar_search(
    *,
    courthouse: str | None = None,
    department: str | None = None,
    area_of_law: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    anchor_date: str | None = None,
    client: RiversideCourtClient | Any | None = None,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Retrieve the complete selected source window, then apply caller paging."""

    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise RiversideSelectionError(
            "invalid_limit",
            "Riverside calendar limit must be a positive integer",
        )
    anchor = anchor_date or _pacific_today()
    for field_name, value in (
        ("anchor_date", anchor),
        ("start_date", start_date),
        ("end_date", end_date),
    ):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise RiversideSelectionError(
                    f"invalid_{field_name}",
                    f"{field_name} must use YYYY-MM-DD",
                    details={field_name: value},
                ) from error
    if start_date and end_date and start_date > end_date:
        raise RiversideSelectionError(
            "invalid_date_range",
            "Riverside calendar start date is after end date",
        )
    parameters = _calendar_parameters(
        courthouse=courthouse,
        department=department,
        area_of_law=area_of_law,
        start_date=start_date,
        end_date=end_date,
        anchor_date=anchor,
    )
    source_client = client or RiversideCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    payload = source_client.run(
        {
            "operation": "calendar",
            "anchor_date": anchor,
            "courthouse": parameters["courthouse"],
            "department": parameters["department"],
            "area_of_law": parameters["area_of_law"],
            "start_date": parameters["start_date"],
            "end_date": parameters["end_date"],
        }
    )
    _validate_calendar_payload(payload)
    raw_records = payload["records"]
    normalized = [
        _normalize_calendar_record(record, retrieved_at=retrieved_at)
        for record in raw_records
        if isinstance(record, Mapping)
    ]
    if len(normalized) != len(raw_records):
        raise RiversideSourceChangedError(
            "calendar_record_type_changed",
            "Riverside eCalendar returned a non-object record",
        )
    normalized.sort(key=_calendar_sort_key)
    seen_refs: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for record in normalized:
        canonical_ref = record["canonical_ref"]
        if canonical_ref in seen_refs:
            continue
        seen_refs.add(canonical_ref)
        deduplicated.append(record)
    snapshot_identity = sha256_fingerprint(
        {
            "business_days": payload["business_days"],
            "selected_date_range": payload.get("selected_date_range"),
            "selected_combinations": payload.get("selected_combinations"),
            "records": [
                {
                    "canonical_ref": record["canonical_ref"],
                    "source_payload": record["source_payload"],
                }
                for record in deduplicated
            ],
        }
    )
    query_identity = _calendar_identity(parameters)
    start_offset = 0
    if cursor:
        start_offset = _decode_cursor(
            cursor,
            query_identity=query_identity,
            snapshot_identity=snapshot_identity,
        )
    if start_offset > len(deduplicated):
        raise RiversideSelectionError(
            "cursor_offset_out_of_range",
            "Riverside calendar cursor offset is beyond this publication",
            details={
                "offset": start_offset,
                "source_total": len(deduplicated),
            },
        )
    end_offset = (
        min(start_offset + limit, len(deduplicated))
        if limit is not None
        else len(deduplicated)
    )
    records = deduplicated[start_offset:end_offset]
    next_cursor = None
    if end_offset < len(deduplicated):
        next_cursor = _encode_cursor(
            offset=end_offset,
            query_identity=query_identity,
            snapshot_identity=snapshot_identity,
        )
    source_requests = payload.get("source_requests")
    raw_refs = [str(payload.get("url") or CALENDAR_URL)]
    if isinstance(source_requests, Sequence) and not isinstance(
        source_requests,
        (str, bytes),
    ):
        raw_refs.extend(str(value) for value in source_requests)
    query = _query(
        CALENDAR_SOURCE,
        "calendar",
        parameters,
        limit=limit,
        cursor=cursor,
        metadata={
            "bounds": {
                "caller_limit": limit,
                "caller_start_offset": start_offset,
                "source_window": payload["business_days"],
                "selected_source_date_range": payload.get(
                    "selected_date_range"
                ),
                "selected_source_combinations": payload.get(
                    "selected_combinations"
                ),
                "transport_response_paging": None,
                "visible_grid_paging": "client_side_only",
                "bounded_probe": False,
            },
            "coverage": {
                "source_rows_before_caller_paging": len(deduplicated),
                "raw_rows_before_deduplication": len(raw_records),
                "returned": len(records),
                "next_offset": end_offset if next_cursor else None,
            },
            "snapshot": {
                "identity": snapshot_identity,
                "query_identity": query_identity,
            },
        },
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        next_cursor=next_cursor,
        raw_artifact_refs=raw_refs,
        warnings=CALENDAR_WARNINGS,
    )


def _filename_dates(filename: str) -> list[str]:
    dates: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"(?<!\d)(\d{6}|\d{8})(?!\d)", filename):
        formats = ("%m%d%y",) if len(token) == 6 else ("%m%d%Y",)
        for format_string in formats:
            try:
                parsed = datetime.strptime(token, format_string).date()
            except ValueError:
                continue
            value = parsed.isoformat()
            if value not in seen:
                seen.add(value)
                dates.append(value)
            break
    return dates


def parse_ruling_directory(
    html: str,
    *,
    response_url: str = RULING_INDEX_URL,
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    """Parse every PDF linked by the current ruling directory."""

    retrieved_at = retrieved_at or utc_now_iso()
    soup = BeautifulSoup(html, "html.parser")
    headings = [
        _clean(heading.get_text(" ", strip=True))
        for heading in soup.find_all("h1")
    ]
    if "Tentative Rulings" not in headings:
        raise RiversideSourceChangedError(
            "ruling_directory_identity_changed",
            "Riverside ruling directory lacks its verified heading",
            details={"headings": headings},
        )
    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        artifact_url = urljoin(response_url, str(anchor["href"]))
        parsed = urlparse(artifact_url)
        if (
            parsed.hostname not in {
                "www.riverside.courts.ca.gov",
                "riverside.courts.ca.gov",
            }
            or not parsed.path.startswith("/system/files/")
            or not parsed.path.lower().endswith(".pdf")
        ):
            continue
        if artifact_url in seen_urls:
            continue
        seen_urls.add(artifact_url)
        label = _clean(anchor.get_text(" ", strip=True))
        department_match = re.search(
            r"\bDepartment\s+([A-Z0-9]+)\b",
            label or "",
            re.I,
        )
        if not label or not department_match:
            raise RiversideSourceChangedError(
                "ruling_department_label_changed",
                "Riverside ruling link lacks a department label",
                details={"label": label, "url": artifact_url},
            )
        department = _normalized_department(department_match.group(1))
        judicial_officer = None
        if " - " in label:
            judicial_officer = _clean(label.split(" - ", 1)[1])
            judicial_officer = re.sub(
                r"^Honorable\s+",
                "",
                judicial_officer or "",
                flags=re.I,
            ).strip() or None
        courthouse_heading = anchor.find_previous("h4")
        courthouse = _clean(
            courthouse_heading.get_text(" ", strip=True)
            if courthouse_heading
            else None
        )
        region_button = anchor.find_previous("button")
        region = _clean(
            region_button.get_text(" ", strip=True)
            if region_button
            else None
        )
        folder_match = re.search(
            r"/system/files/(\d{4}-\d{2})/",
            parsed.path,
        )
        artifact_month = folder_match.group(1) if folder_match else None
        filename = unquote(parsed.path.rsplit("/", 1)[-1])
        filename_dates = _filename_dates(filename)
        no_tentatives_hint = bool(
            re.search(
                r"no[\s_-]*(?:tentatives?|trs?)",
                filename,
                re.I,
            )
        )
        records.append(
            {
                "canonical_ref": (
                    "RIVERSIDE-RULING-INDEX:"
                    + hashlib.sha256(
                        artifact_url.encode("utf-8")
                    ).hexdigest()
                ),
                "source_id": RULING_SOURCE_ID,
                "record_kind": "tentative_ruling_artifact_index",
                "court": {
                    "court_id": COURT_ID,
                    "name": COURT_NAME,
                    "county_fips": COUNTY_FIPS,
                    "state_code": STATE_CODE,
                },
                "region": region,
                "courthouse": courthouse,
                "department": department,
                "judicial_officer": judicial_officer,
                "label": label,
                "artifact_url": artifact_url,
                "artifact_format": "pdf",
                "artifact_path_month": artifact_month,
                "artifact_filename": filename,
                "artifact_filename_date_candidates": filename_dates,
                "filename_indicates_no_tentatives": no_tentatives_hint,
                "directory_state": "linked_by_current_directory",
                "directory_url": response_url,
                "retrieved_at": retrieved_at,
            }
        )
    if not records:
        raise RiversideSourceChangedError(
            "ruling_artifacts_missing",
            "Riverside ruling directory exposes no department PDFs",
        )
    records.sort(
        key=lambda record: (
            record.get("region") or "",
            record.get("courthouse") or "",
            record["department"],
            record["artifact_url"],
        )
    )
    return records


def ruling_index(
    *,
    department: str | None = None,
    client: RiversideCourtClient | Any | None = None,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Return every directory artifact without imposing a local row cap."""

    source_client = client or RiversideCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    payload = source_client.run({"operation": "ruling_index"})
    html = payload.get("html")
    response_url = str(payload.get("url") or RULING_INDEX_URL)
    if not isinstance(html, str):
        raise RiversideSourceChangedError(
            "ruling_directory_payload_changed",
            "Riverside browser transport returned no ruling-directory HTML",
        )
    records = parse_ruling_directory(
        html,
        response_url=response_url,
        retrieved_at=retrieved_at,
    )
    unfiltered_count = len(records)
    if department:
        wanted = _normalized_department(department)
        records = [
            record for record in records if record["department"] == wanted
        ]
    path_month_counts: dict[str, int] = {}
    for record in records:
        month = record.get("artifact_path_month") or "unknown"
        path_month_counts[str(month)] = path_month_counts.get(str(month), 0) + 1
    query = _query(
        RULING_SOURCE,
        "ruling-index",
        {
            "department": (
                _normalized_department(department) if department else None
            ),
        },
        metadata={
            "bounds": {
                "caller_limit": None,
                "transport": "one current directory page",
                "source_window": "department artifacts linked by the directory",
            },
            "coverage": {
                "directory_artifacts_before_filter": unfiltered_count,
                "returned": len(records),
                "artifact_path_month_counts_after_filter": path_month_counts,
            },
        },
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        raw_artifact_refs=[response_url],
        warnings=RULING_WARNINGS,
    )


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract layout-preserving text from one verified ruling PDF."""

    with tempfile.TemporaryDirectory(prefix="riverside-court-pdf-") as temp_dir:
        pdf_path = Path(temp_dir) / "ruling.pdf"
        pdf_path.write_bytes(pdf_bytes)
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise RiversideCourtError(
                "pdftotext_unavailable",
                "pdftotext is required to extract tentative-ruling text",
                category="local_dependency",
            ) from error
        if completed.returncode != 0:
            raise RiversideCourtError(
                "ruling_pdf_extraction_failed",
                "pdftotext could not extract the Riverside ruling artifact",
                category="artifact_parse",
                details={
                    "stderr": completed.stderr.decode(
                        "utf-8",
                        errors="replace",
                    )[-1000:],
                },
            )
        text = completed.stdout.decode("utf-8", errors="replace")
        if not _clean(text):
            raise RiversideSourceChangedError(
                "ruling_pdf_empty_text",
                "Riverside ruling PDF yielded no extractable text",
            )
        return text


def _riverside_case_numbers(text: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(r"\b[A-Z]{2,6}\d{6,10}\b", text, re.I):
        candidates.append((match.start(), match.group(0).upper()))
    for match in re.finditer(r"\b([A-Z]{2,6})\s+(\d{7,10})\b", text, re.I):
        candidates.append(
            (match.start(), (match.group(1) + match.group(2)).upper())
        )
    candidates.sort()
    seen: set[str] = set()
    case_numbers: list[str] = []
    for _, value in candidates:
        if value in seen:
            continue
        seen.add(value)
        case_numbers.append(value)
    return case_numbers


def parse_ruling_text(text: str) -> dict[str, Any]:
    """Extract durable header fields and retain the complete source text."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    hearing_match = re.search(
        r"Tentative Rulings?\s+for\s+"
        r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        normalized,
        re.I,
    )
    hearing_date = None
    if hearing_match:
        try:
            hearing_date = datetime.strptime(
                hearing_match.group(1),
                "%B %d, %Y",
            ).date().isoformat()
        except ValueError:
            hearing_date = None
    department_match = re.search(
        r"^\s*Department\s+([A-Z0-9]+)\s*$",
        normalized,
        re.I | re.M,
    )
    matter_numbers = [
        int(match.group(1))
        for match in re.finditer(
            r"^\s*(\d+)\.\s*$",
            normalized,
            re.M,
        )
    ]
    case_numbers = _riverside_case_numbers(normalized)
    no_tentatives = bool(
        re.search(
            r"^\s*No Tentative Rulings?\b",
            normalized,
            re.I | re.M,
        )
        and not matter_numbers
        and not case_numbers
    )
    return {
        "hearing_date": hearing_date,
        "department": (
            _normalized_department(department_match.group(1))
            if department_match
            else None
        ),
        "case_numbers": case_numbers,
        "matter_numbers": matter_numbers,
        "matter_count": len(matter_numbers),
        "no_tentative_rulings": no_tentatives,
        "text": normalized,
        "text_sha256": hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest(),
    }


def ruling_document(
    department: str,
    *,
    client: RiversideCourtClient | Any | None = None,
    retrieved_at: str | None = None,
    download_path: Path | None = None,
    include_text: bool = True,
    text_extractor: Callable[[bytes], str] = extract_pdf_text,
) -> PublicRecordsResult:
    """Fetch one directory-selected PDF and optionally extract full text."""

    wanted = _normalized_department(department)
    if not wanted:
        raise RiversideSelectionError(
            "department_required",
            "Riverside ruling department is required",
        )
    source_client = client or RiversideCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    payload = source_client.run(
        {
            "operation": "ruling_pdf",
            "department": wanted,
        }
    )
    index_html = payload.get("index_html")
    index_url = str(payload.get("index_url") or RULING_INDEX_URL)
    artifact = payload.get("artifact")
    if not isinstance(index_html, str) or not isinstance(artifact, Mapping):
        raise RiversideSourceChangedError(
            "ruling_artifact_payload_changed",
            "Riverside browser transport returned an invalid ruling payload",
        )
    index_records = parse_ruling_directory(
        index_html,
        response_url=index_url,
        retrieved_at=retrieved_at,
    )
    matches = [
        record for record in index_records if record["department"] == wanted
    ]
    if len(matches) != 1:
        raise RiversideSelectionError(
            (
                "ruling_not_published"
                if not matches
                else "ruling_department_ambiguous"
            ),
            (
                f"Riverside ruling department {wanted} matched "
                f"{len(matches)} directory artifacts"
            ),
        )
    index_record = matches[0]
    artifact_url = _clean(artifact.get("url"))
    if artifact_url != index_record["artifact_url"]:
        raise RiversideSourceChangedError(
            "ruling_artifact_mismatch",
            "Riverside browser artifact does not match the directory link",
            details={
                "directory_url": index_record["artifact_url"],
                "artifact_url": artifact_url,
            },
        )
    encoded = artifact.get("base64")
    if not isinstance(encoded, str):
        raise RiversideSourceChangedError(
            "ruling_artifact_bytes_missing",
            "Riverside browser transport returned no PDF bytes",
        )
    try:
        pdf_bytes = base64.b64decode(encoded, validate=True)
    except binascii.Error as error:
        raise RiversideSourceChangedError(
            "ruling_artifact_base64_invalid",
            "Riverside browser transport returned invalid PDF encoding",
        ) from error
    if not pdf_bytes.startswith(b"%PDF-"):
        raise RiversideSourceChangedError(
            "ruling_artifact_not_pdf",
            "Riverside ruling artifact is not a PDF",
            details={
                "content_type": artifact.get("content_type"),
                "magic": pdf_bytes[:16].hex(),
            },
        )
    if download_path:
        download_path.parent.mkdir(parents=True, exist_ok=True)
        download_path.write_bytes(pdf_bytes)
    parsed_text: dict[str, Any] = {
        "hearing_date": None,
        "department": None,
        "case_numbers": [],
        "matter_numbers": [],
        "matter_count": 0,
        "no_tentative_rulings": None,
        "text": None,
        "text_sha256": None,
    }
    if include_text:
        parsed_text = parse_ruling_text(text_extractor(pdf_bytes))
        parsed_department = parsed_text.get("department")
        if parsed_department and parsed_department != wanted:
            raise RiversideSourceChangedError(
                "ruling_department_mismatch",
                "Riverside ruling PDF names a different department",
                details={
                    "directory_department": wanted,
                    "pdf_department": parsed_department,
                },
            )
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    record = {
        "canonical_ref": f"RIVERSIDE-RULING:{digest}",
        "source_id": RULING_SOURCE_ID,
        "record_kind": "tentative_ruling_document",
        "court": index_record["court"],
        "region": index_record.get("region"),
        "courthouse": index_record.get("courthouse"),
        "department": wanted,
        "judicial_officer": index_record.get("judicial_officer"),
        "hearing_date": parsed_text.get("hearing_date"),
        "case_numbers": parsed_text.get("case_numbers", []),
        "matter_numbers": parsed_text.get("matter_numbers", []),
        "matter_count": parsed_text.get("matter_count", 0),
        "no_tentative_rulings": parsed_text.get(
            "no_tentative_rulings"
        ),
        "text": parsed_text.get("text"),
        "text_sha256": parsed_text.get("text_sha256"),
        "artifact": {
            "url": artifact_url,
            "format": "pdf",
            "content_type": _clean(artifact.get("content_type")),
            "sha256": digest,
            "bytes": len(pdf_bytes),
            "etag": _clean(artifact.get("etag")),
            "last_modified": _clean(artifact.get("last_modified")),
            "local_path": str(download_path) if download_path else None,
            "text_extraction": (
                "pdftotext-layout" if include_text else "not_requested"
            ),
        },
        "directory_record": index_record,
        "retrieved_at": retrieved_at,
        "complementary_routes": complementary_routes(),
    }
    query = _query(
        RULING_SOURCE,
        "ruling",
        {
            "department": wanted,
            "include_text": include_text,
        },
        metadata={
            "bounds": {
                "caller_limit": 1,
                "transport": "one directory page and one matched PDF",
                "source_window": "artifact linked by the current directory",
            }
        },
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
        raw_artifact_refs=[index_url, artifact_url],
        warnings=RULING_WARNINGS,
    )


def complementary_routes() -> list[dict[str, Any]]:
    """Return distinct official and appellate record representations."""

    return [
        {
            "source": "Riverside Superior Court Public Access",
            "url": PUBLIC_ACCESS_URL,
            "access": "account required; case-number lookup and calendars",
            "adds": (
                "name index, register of actions, up-to-seven-day calendars, "
                "and eligible document downloads"
            ),
            "cost": (
                "case-number register lookup is distinct from paid name-index "
                "credits and per-page document downloads"
            ),
        },
        {
            "source": "Riverside Court Public Access coverage guide",
            "url": PUBLIC_ACCESS_INFO_URL,
            "access": "anonymous information page",
            "adds": (
                "case-family and courthouse coverage dates, name-search "
                "pricing, purged-record notice, and copy routes"
            ),
        },
        {
            "source": "Riverside Court name-index products",
            "url": PURCHASE_INDEXES_URL,
            "access": "order form and payment",
            "adds": (
                "monthly or quarterly Civil, Family Law, and Probate party "
                "indexes with party types, other parties, and case numbers"
            ),
            "coverage": (
                "Riverside Civil from October 1996, Family Law from July "
                "1992, countywide Probate from March 1994; eastern-region "
                "Civil and Family Law from 1991 or 1992"
            ),
        },
        {
            "source": "Riverside clerk-performed record search",
            "url": CLERK_SEARCH_URL,
            "access": "request submission",
            "adds": (
                "case-number search when the online portal does not surface "
                "a record; document copies are requested separately"
            ),
        },
        {
            "source": "Riverside record search and certified-copy forms",
            "url": LOCAL_FORMS_URL,
            "artifact_url": CERTIFIED_COPY_FORM_URL,
            "access": "form submission and applicable fees",
            "adds": (
                "records searches and civil, criminal, family, probate, and "
                "traffic copies or certifications"
            ),
        },
        {
            "source": "Riverside Probate Notes",
            "url": PROBATE_INFORMATION_URL,
            "access": "anonymous current publication",
            "adds": (
                "upcoming probate matter summaries, deficiencies, parties, "
                "case numbers, hearing types, and examiner information"
            ),
        },
        {
            "source": "Riverside high-interest case pages",
            "url": HIGH_INTEREST_CASES_URL,
            "access": "anonymous",
            "adds": (
                "court-curated case identifiers and public documents for "
                "selected matters"
            ),
        },
        {
            "source": "Riverside transcript request",
            "url": TRANSCRIPT_REQUEST_URL,
            "access": "request submission",
            "adds": "reporter transcript acquisition by case and hearing date",
        },
        {
            "source": "Riverside Appeals Department",
            "url": APPEALS_URL,
            "access": "anonymous information and filing routes",
            "adds": (
                "trial-court appellate-division procedures and record "
                "preparation routes"
            ),
        },
        {
            "source": "California Fourth District Court of Appeal, Division Two",
            "url": FOURTH_DISTRICT_SEARCH_URL,
            "access": "anonymous",
            "adds": (
                "appellate case metadata and opinions that can preserve "
                "Riverside trial-case facts and procedural history"
            ),
        },
    ]


def source_records() -> list[dict[str, Any]]:
    records = [
        {
            "source_id": SOURCE_FAMILY_ID,
            "record_kind": "source_manifest",
            "name": _family_source().name,
            "url": CALENDAR_INFO_URL,
            "implemented_source_ids": [
                CALENDAR_SOURCE_ID,
                RULING_SOURCE_ID,
            ],
        },
        {
            "source_id": CALENDAR_SOURCE_ID,
            "record_kind": "implemented_source",
            "name": CALENDAR_SOURCE.name,
            "url": CALENDAR_URL,
            "implemented_operations": ["calendar", "probe"],
            "coverage": (
                "current day plus next three source-generated business days"
            ),
            "transport": "headed Chrome plus complete JSON responses",
        },
        {
            "source_id": RULING_SOURCE_ID,
            "record_kind": "implemented_source",
            "name": RULING_SOURCE.name,
            "url": RULING_INDEX_URL,
            "implemented_operations": [
                "ruling-index",
                "ruling",
                "probe",
            ],
            "coverage": "all department PDF links in the current directory",
            "artifact_format": "pdf",
        },
    ]
    records.extend(
        {
            "source_id": COMPLEMENT_SOURCE_IDS_BY_URL[route["url"]],
            "record_kind": "complementary_source",
            **route,
        }
        for route in complementary_routes()
    )
    return records


def probe_sources(
    *,
    client: RiversideCourtClient | Any | None = None,
    anchor_date: str | None = None,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Run a bounded live contract probe without enumerating every calendar."""

    source_client = client or RiversideCourtClient()
    anchor = anchor_date or _pacific_today()
    retrieved_at = retrieved_at or utc_now_iso()
    payload = source_client.run(
        {
            "operation": "probe",
            "anchor_date": anchor,
        }
    )
    calendar_payload = payload.get("calendar")
    ruling_payload = payload.get("ruling_index")
    if not isinstance(calendar_payload, Mapping) or not isinstance(
        ruling_payload,
        Mapping,
    ):
        raise RiversideSourceChangedError(
            "probe_payload_changed",
            "Riverside browser probe returned an invalid component payload",
        )
    _validate_calendar_payload(calendar_payload)
    calendar_records = [
        _normalize_calendar_record(record, retrieved_at=retrieved_at)
        for record in calendar_payload["records"]
        if isinstance(record, Mapping)
    ]
    ruling_html = ruling_payload.get("html")
    if not isinstance(ruling_html, str):
        raise RiversideSourceChangedError(
            "probe_ruling_payload_changed",
            "Riverside browser probe returned no ruling-directory HTML",
        )
    ruling_records = parse_ruling_directory(
        ruling_html,
        response_url=str(ruling_payload.get("url") or RULING_INDEX_URL),
        retrieved_at=retrieved_at,
    )
    selector_tree = calendar_payload["selector_tree"]
    department_count = 0
    area_count = 0
    for location in selector_tree:
        if not isinstance(location, Mapping):
            continue
        departments = location.get("departments")
        if not isinstance(departments, Sequence) or isinstance(
            departments,
            (str, bytes),
        ):
            continue
        department_count += len(departments)
        for department in departments:
            if not isinstance(department, Mapping):
                continue
            areas = department.get("areas")
            if isinstance(areas, Sequence) and not isinstance(
                areas,
                (str, bytes),
            ):
                area_count += len(areas)
    path_month_counts: dict[str, int] = {}
    for ruling in ruling_records:
        month = ruling.get("artifact_path_month") or "unknown"
        path_month_counts[str(month)] = path_month_counts.get(str(month), 0) + 1
    record = {
        "canonical_ref": (
            "RIVERSIDE-COURT-PROBE:"
            + sha256_fingerprint(
                {
                    "business_days": calendar_payload["business_days"],
                    "calendar_records": [
                        item["canonical_ref"] for item in calendar_records
                    ],
                    "ruling_artifacts": [
                        item["canonical_ref"] for item in ruling_records
                    ],
                }
            )
        ),
        "source_id": SOURCE_FAMILY_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "ecalendar": {
            "business_days": calendar_payload["business_days"],
            "courthouse_count": len(selector_tree),
            "department_count": department_count,
            "department_area_combinations": area_count,
            "probe_selection": {
                "courthouse": "Historic Court House",
                "department": "8",
                "area_of_law": "Probate",
            },
            "probe_rows": len(calendar_records),
            "native_response_paging": None,
            "visible_grid_paging": "client_side_only",
        },
        "tentative_rulings": {
            "directory_artifact_count": len(ruling_records),
            "artifact_path_month_counts": path_month_counts,
            "artifacts_downloaded": 0,
        },
        "probe_bounds": {
            "calendar_department_area_combinations_queried": 1,
            "calendar_source_business_days_queried": len(
                calendar_payload["business_days"]
            ),
            "ruling_directory_pages": 1,
            "ruling_artifacts_downloaded": 0,
            "probe_is_not_full_calendar_enumeration": True,
        },
        "retrieved_at": retrieved_at,
    }
    query = _query(
        _family_source(),
        "probe",
        {"anchor_date": anchor},
        metadata={
            "bounds": record["probe_bounds"],
        },
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
        raw_artifact_refs=[
            str(calendar_payload.get("url") or CALENDAR_URL),
            str(ruling_payload.get("url") or RULING_INDEX_URL),
        ],
        warnings=(*CALENDAR_WARNINGS, *RULING_WARNINGS),
    )


def _failure_result(
    source: SourceMetadata,
    operation: str,
    parameters: Mapping[str, Any],
    error: RiversideCourtError,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsResult:
    contract_limit = (
        limit
        if (
            not isinstance(limit, bool)
            and isinstance(limit, int)
            and limit > 0
        )
        else None
    )
    return PublicRecordsResult.failure(
        _query(
            source,
            operation,
            parameters,
            limit=contract_limit,
            cursor=cursor,
        ),
        error.status,
        [error.to_contract_error()],
        warnings=(
            CALENDAR_WARNINGS
            if source.source_id == CALENDAR_SOURCE_ID
            else RULING_WARNINGS
        ),
    )


def _best_effort_log(
    operation: str,
    parameters: Mapping[str, Any],
    result: PublicRecordsResult,
) -> None:
    try:
        log_search(
            canonical_json(
                {"operation": operation, "parameters": parameters}
            ),
            result.query.source.source_id,
            len(result.records),
        )
    except Exception:
        return


def _client_from_args(args: argparse.Namespace) -> RiversideCourtClient:
    return RiversideCourtClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _add_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="browser operation timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="minimum seconds between source data requests",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="bounded browser attempts for transient failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Riverside County Superior Court calendars and "
            "tentative rulings"
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    sources_parser = subparsers.add_parser(
        "sources",
        help="Describe implemented and complementary record sources",
    )
    _add_request_args(sources_parser)

    calendar_parser = subparsers.add_parser(
        "calendar",
        aliases=["search"],
        help="Query the source-published eCalendar window",
    )
    calendar_parser.add_argument("--courthouse")
    calendar_parser.add_argument("--department")
    calendar_parser.add_argument(
        "--area-of-law",
        choices=("civil", "criminal", "probate", "traffic"),
    )
    calendar_parser.add_argument("--start-date")
    calendar_parser.add_argument("--end-date")
    calendar_parser.add_argument(
        "--limit",
        type=int,
        help=(
            "caller result bound; omit to return every selected source row"
        ),
    )
    calendar_parser.add_argument("--cursor")
    _add_request_args(calendar_parser)

    ruling_index_parser = subparsers.add_parser(
        "ruling-index",
        help="List every PDF linked by the current ruling directory",
    )
    ruling_index_parser.add_argument("--department")
    _add_request_args(ruling_index_parser)

    ruling_parser = subparsers.add_parser(
        "ruling",
        help="Fetch and extract one directory-selected ruling PDF",
    )
    ruling_parser.add_argument("department")
    ruling_parser.add_argument(
        "--download",
        type=Path,
        help="save the exact source PDF to this path",
    )
    ruling_parser.add_argument(
        "--no-text",
        action="store_true",
        help="return artifact metadata without PDF text extraction",
    )
    _add_request_args(ruling_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Run a bounded calendar and ruling-directory health probe",
    )
    _add_request_args(probe_parser)
    return parser


def execute(
    args: argparse.Namespace,
    *,
    client: RiversideCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source-family operation and return a canonical envelope."""

    if args.command == "sources":
        return PublicRecordsResult.success(
            _query(_family_source(), "sources", {}),
            source_records(),
            warnings=(*CALENDAR_WARNINGS, *RULING_WARNINGS),
        )

    source_client = client or _client_from_args(args)
    owns_client = client is None
    try:
        if args.command in {"calendar", "search"}:
            result = calendar_search(
                courthouse=args.courthouse,
                department=args.department,
                area_of_law=args.area_of_law,
                start_date=args.start_date,
                end_date=args.end_date,
                limit=args.limit,
                cursor=args.cursor,
                client=source_client,
            )
            if log_results:
                _best_effort_log(
                    "calendar",
                    result.query.query.to_dict()["parameters"],
                    result,
                )
        elif args.command == "ruling-index":
            result = ruling_index(
                department=args.department,
                client=source_client,
            )
            if log_results:
                _best_effort_log(
                    "ruling-index",
                    {"department": args.department},
                    result,
                )
        elif args.command == "ruling":
            result = ruling_document(
                args.department,
                client=source_client,
                download_path=args.download,
                include_text=not args.no_text,
            )
            if log_results:
                _best_effort_log(
                    "ruling",
                    {"department": args.department},
                    result,
                )
        elif args.command == "probe":
            result = probe_sources(client=source_client)
        else:
            raise ValueError(
                f"unknown Riverside court command: {args.command}"
            )
    except RiversideCourtError as error:
        if args.command in {"calendar", "search"}:
            parameters = _calendar_parameters(
                courthouse=args.courthouse,
                department=args.department,
                area_of_law=args.area_of_law,
                start_date=args.start_date,
                end_date=args.end_date,
                anchor_date=_pacific_today(),
            )
            result = _failure_result(
                CALENDAR_SOURCE,
                "calendar",
                parameters,
                error,
                limit=args.limit,
                cursor=args.cursor,
            )
        elif args.command == "ruling":
            result = _failure_result(
                RULING_SOURCE,
                "ruling",
                {
                    "department": _normalized_department(args.department),
                    "include_text": not args.no_text,
                },
                error,
            )
        else:
            result = _failure_result(
                (
                    RULING_SOURCE
                    if args.command == "ruling-index"
                    else _family_source()
                ),
                args.command,
                {},
                error,
            )
    finally:
        if owns_client:
            source_client.close()
    return result


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
    *,
    summary: str,
) -> None:
    payload = result.to_dict()
    if not write_output(
        payload,
        args,
        summary=summary,
        result_count=len(result.records),
    ):
        print(json.dumps(payload, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    result = execute(args)
    summary = f"Riverside County court {args.command} ({result.status.value})"
    _emit(result, args, summary=summary)
    return (
        0
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}
        else 2
    )


if __name__ == "__main__":
    sys.exit(main())
