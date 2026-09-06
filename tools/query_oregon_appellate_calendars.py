#!/usr/bin/env python3
"""Query Oregon's official Supreme Court and Court of Appeals calendars.

The historical ``web.courts.oregon.gov/sclist`` and ``/coadocket`` entry
points now redirect to Oregon Judicial Department error-path pages.  Their
current official replacements are separate SharePoint-backed calendar pages.
This adapter keeps those calendars as distinct source components while using
the public list API behind each page so server continuations are not lost.

Examples:
    uv run python tools/query_oregon_appellate_calendars.py search \
        --court coa --current --output /tmp/oregon-coa-calendar.json
    uv run python tools/query_oregon_appellate_calendars.py search \
        --court supreme --case-number S072119
    uv run python tools/query_oregon_appellate_calendars.py probe --court coa
    uv run python tools/query_oregon_appellate_calendars.py probe \
        --court supreme
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urljoin
from zoneinfo import ZoneInfo

import requests
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
    )
    from tools.public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceChangedHTTPError,
        SourceSchemaError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
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
    )
    from public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceChangedHTTPError,
        SourceSchemaError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


STATE_CODE = "OR"
STATE_GEOID = "41"
OREGON_TIMEZONE = ZoneInfo("America/Los_Angeles")
SHAREPOINT_ORIGIN = "https://www.courts.oregon.gov"
SHAREPOINT_WEB = f"{SHAREPOINT_ORIGIN}/courts/appellate/go"
API_PAGE_SIZE = 100
CURSOR_VERSION = 1
CURSOR_PREFIX = "orappcal:v1:"

COURT_OF_APPEALS_SOURCE_ID = "us-or-court-of-appeals-calendar"
SUPREME_COURT_SOURCE_ID = "us-or-supreme-court-calendar"
SOURCE_IDS = (
    COURT_OF_APPEALS_SOURCE_ID,
    SUPREME_COURT_SOURCE_ID,
)

COURT_OF_APPEALS_LEGACY_URL = "https://web.courts.oregon.gov/coadocket"
SUPREME_COURT_LEGACY_URL = "https://web.courts.oregon.gov/sclist"
COURT_OF_APPEALS_PAGE_URL = (
    f"{SHAREPOINT_WEB}/Pages/coa-calendar.aspx"
)
SUPREME_COURT_PAGE_URL = f"{SHAREPOINT_WEB}/Pages/sc-calendar.aspx"


@dataclass(frozen=True)
class CalendarSource:
    """One separately attributable Oregon appellate calendar component."""

    key: str
    source_id: str
    name: str
    source_role: str
    dataset_id: str
    court_id: str
    native_court_id: str
    court_name: str
    court_level: str
    legacy_url: str
    page_url: str
    list_title: str
    list_path: str
    view_name: str
    view_current_only: bool
    selected_fields: tuple[str, ...]
    required_fields: frozenset[str]

    @property
    def list_root(self) -> str:
        encoded = quote(self.list_title, safe="")
        return (
            f"{SHAREPOINT_WEB}/_api/web/lists/"
            f"getbytitle(%27{encoded}%27)"
        )

    @property
    def items_url(self) -> str:
        return f"{self.list_root}/items"

    @property
    def view_url(self) -> str:
        encoded = quote(self.view_name, safe="")
        return (
            f"{self.list_root}/views/getbytitle(%27{encoded}%27)"
        )

    @property
    def view_fields_url(self) -> str:
        return f"{self.view_url}/ViewFields"

    @property
    def item_form_root(self) -> str:
        return f"{SHAREPOINT_ORIGIN}{self.list_path}/DispForm.aspx"


COURT_OF_APPEALS = CalendarSource(
    key="coa",
    source_id=COURT_OF_APPEALS_SOURCE_ID,
    name="Oregon Court of Appeals Calendar",
    source_role="court_of_appeals_submission_and_oral_argument_calendar",
    dataset_id="oregon-ojd-sharepoint-orctrack-current",
    court_id="or-court-of-appeals",
    native_court_id="oregon-court-of-appeals",
    court_name="Oregon Court of Appeals",
    court_level="appellate",
    legacy_url=COURT_OF_APPEALS_LEGACY_URL,
    page_url=COURT_OF_APPEALS_PAGE_URL,
    list_title="ORCTrack",
    list_path="/courts/appellate/go/Lists/ORCTrack",
    view_name="CurrentNoGroup",
    view_current_only=False,
    selected_fields=(
        "ID",
        "GUID",
        "Title",
        "Date",
        "Time",
        "Time24Hour",
        "Location",
        "CaseNbr",
        "CaseType",
        "Panel",
        "SubmissionForm",
        "SequenceNbr",
        "Status",
        "Comments",
        "Modified",
        "Created",
    ),
    required_fields=frozenset(
        {
            "ID",
            "GUID",
            "Title",
            "Date",
            "Time",
            "Time24Hour",
            "Location",
            "CaseNbr",
            "CaseType",
            "Panel",
            "SubmissionForm",
            "SequenceNbr",
            "Status",
            "Comments",
            "Modified",
            "Created",
        }
    ),
)

SUPREME_COURT = CalendarSource(
    key="supreme",
    source_id=SUPREME_COURT_SOURCE_ID,
    name="Oregon Supreme Court Calendar",
    source_role="supreme_court_oral_argument_calendar_and_brief_links",
    dataset_id="oregon-ojd-sharepoint-supreme-court-calendar",
    court_id="or-supreme-court",
    native_court_id="oregon-supreme-court",
    court_name="Oregon Supreme Court",
    court_level="supreme",
    legacy_url=SUPREME_COURT_LEGACY_URL,
    page_url=SUPREME_COURT_PAGE_URL,
    list_title="Supreme Court Calendar",
    list_path="/courts/appellate/go/Lists/SupremeCourtCalendar",
    view_name="Current",
    view_current_only=True,
    selected_fields=(
        "ID",
        "GUID",
        "Title",
        "Date",
        "Location",
        "SCNumber",
        "CANumber",
        "Attorneys",
        "Comments",
        "Issues",
        "Justices",
        "HearingID",
        "SequenceNbr",
        "Status",
        "Attachments",
        "AttachmentFiles/FileName",
        "AttachmentFiles/ServerRelativeUrl",
        "Modified",
        "Created",
    ),
    required_fields=frozenset(
        {
            "ID",
            "GUID",
            "Title",
            "Date",
            "Location",
            "SCNumber",
            "CANumber",
            "Attorneys",
            "Comments",
            "Issues",
            "Justices",
            "HearingID",
            "SequenceNbr",
            "Status",
            "Attachments",
            "AttachmentFiles",
            "Modified",
            "Created",
        }
    ),
)

SOURCES = {
    "coa": COURT_OF_APPEALS,
    "court-of-appeals": COURT_OF_APPEALS,
    "supreme": SUPREME_COURT,
    "supreme-court": SUPREME_COURT,
}


def _source_metadata(spec: CalendarSource) -> SourceMetadata:
    return SourceMetadata(
        source_id=spec.source_id,
        name=spec.name,
        source_role=spec.source_role,
        base_url=spec.page_url,
        dataset_id=spec.dataset_id,
        metadata={
            "authority": "Oregon Judicial Department",
            "state_code": STATE_CODE,
            "authentication": "none",
            "platform_family": "oregon_sharepoint_calendar_list",
            "legacy_entrypoint": spec.legacy_url,
            "current_official_page": spec.page_url,
            "sharepoint_list_title": spec.list_title,
            "sharepoint_list_path": spec.list_path,
            "sharepoint_view_name": spec.view_name,
            "api_page_size": API_PAGE_SIZE,
            "complements": [
                "us-or-appellate-record-search",
                "us-or-law-library-supreme-briefs",
                "us-or-law-library-coa-briefs",
            ],
        },
    )


COURT_OF_APPEALS_SOURCE_METADATA = _source_metadata(COURT_OF_APPEALS)
SUPREME_COURT_SOURCE_METADATA = _source_metadata(SUPREME_COURT)
SOURCE_METADATA_BY_ID = {
    COURT_OF_APPEALS_SOURCE_ID: COURT_OF_APPEALS_SOURCE_METADATA,
    SUPREME_COURT_SOURCE_ID: SUPREME_COURT_SOURCE_METADATA,
}

COMMON_WARNINGS = (
    "Appellate calendars can change after publication; each result preserves "
    "the source retrieval timestamp and list-item revision metadata.",
    "The adapter follows every SharePoint continuation before applying local "
    "filters or result pagination.",
)
COURT_OF_APPEALS_WARNINGS = (
    *COMMON_WARNINGS,
    "The Court of Appeals source distinguishes submissions from oral "
    "arguments and publishes the argument format as a separate field.",
)
SUPREME_COURT_WARNINGS = (
    *COMMON_WARNINGS,
    "Supreme Court issue summaries are source-authored media aids and are "
    "preserved separately from the case caption and calendar event.",
    "Published SharePoint attachments are returned as official document links "
    "without downloading their contents.",
)


def _warnings(spec: CalendarSource) -> tuple[str, ...]:
    if spec is COURT_OF_APPEALS:
        return COURT_OF_APPEALS_WARNINGS
    return SUPREME_COURT_WARNINGS


@dataclass(frozen=True)
class CalendarFetch:
    """A complete traversal of one public SharePoint list."""

    rows: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    requests_made: int
    schema: Mapping[str, Any]
    schema_fingerprint: str
    item_ids: tuple[int, ...]


@dataclass(frozen=True)
class CursorState:
    """Opaque local page state bound to a query and source snapshot."""

    source_id: str
    query_fingerprint: str
    snapshot_fingerprint: str
    offset: int
    anchor: str


class OregonAppellateCalendarSelectionError(ValueError):
    """A source, filter, or continuation selector is invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(
        str(value).replace("\x00", "").replace("\u200b", "").split()
    ).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ValueError(f"Oregon appellate calendar {field_name} is blank")
    return normalized


def _html_text(value: Any) -> str | None:
    if value is None:
        return None
    soup = BeautifulSoup(str(value), "html.parser")
    lines = []
    for line in soup.get_text("\n", strip=True).splitlines():
        normalized = _text(line)
        if normalized:
            lines.append(normalized)
    return "\n".join(lines) or None


def _integer(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _oregon_today() -> date:
    return datetime.now(OREGON_TIMEZONE).date()


def _parse_iso_date(
    value: str | None,
    field_name: str,
) -> date | None:
    if value is None:
        return None
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError as error:
        raise OregonAppellateCalendarSelectionError(
            "invalid_date",
            f"{field_name} must use YYYY-MM-DD",
            details={"value": value},
        ) from error


def _source_datetime(value: Any) -> datetime:
    raw = _required_text(value, "Date")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"Oregon appellate calendar Date is not ISO 8601: {raw!r}"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=OREGON_TIMEZONE)
    return parsed.astimezone(OREGON_TIMEZONE)


def _event_temporal(
    spec: CalendarSource,
    row: Mapping[str, Any],
) -> tuple[str, str | None, str]:
    source_value = _source_datetime(row.get("Date"))
    if spec is COURT_OF_APPEALS:
        raw_time = _text(row.get("Time24Hour") or row.get("Time"))
        if raw_time is None:
            raise ValueError("Court of Appeals calendar row lacks event time")
        parsed_time: datetime | None = None
        for fmt in ("%H:%M", "%I:%M %p"):
            try:
                parsed_time = datetime.strptime(raw_time, fmt)
                break
            except ValueError:
                continue
        if parsed_time is None:
            raise ValueError(
                f"Court of Appeals event time is invalid: {raw_time!r}"
            )
        local_value = datetime(
            source_value.year,
            source_value.month,
            source_value.day,
            parsed_time.hour,
            parsed_time.minute,
            tzinfo=OREGON_TIMEZONE,
        )
    else:
        local_value = source_value
    return (
        local_value.date().isoformat(),
        local_value.strftime("%H:%M"),
        local_value.isoformat(),
    )


def _event_type(
    spec: CalendarSource,
    row: Mapping[str, Any],
) -> tuple[str, str]:
    if spec is SUPREME_COURT:
        return "oral_argument", "ORAL_ARGUMENT"
    form = (_text(row.get("SubmissionForm")) or "").casefold()
    if form.startswith("oral argument"):
        return "oral_argument", "ORAL_ARGUMENT"
    if "submission" in form:
        return "submission", "SUBMISSION"
    return "appellate_calendar_event", "APPELLATE_CALENDAR_EVENT"


def _case_number_variants(
    spec: CalendarSource,
    row: Mapping[str, Any],
) -> list[str]:
    candidates: list[str] = []
    if spec is COURT_OF_APPEALS:
        values = (row.get("CaseNbr"),)
    else:
        values = (row.get("SCNumber"), row.get("CANumber"))
    for value in values:
        normalized = _text(value)
        if normalized is None:
            continue
        for part in re.split(r"\s*(?:/|,|;)\s*", normalized):
            part_value = _text(part)
            if part_value and part_value not in candidates:
                candidates.append(part_value)
        if normalized not in candidates:
            candidates.insert(0, normalized)
    return candidates


def _primary_case_number(
    spec: CalendarSource,
    row: Mapping[str, Any],
) -> str:
    variants = _case_number_variants(spec, row)
    if not variants:
        raise ValueError("Oregon appellate calendar row lacks a case number")
    if spec is SUPREME_COURT:
        supreme = _text(row.get("SCNumber"))
        if supreme:
            return supreme
    return variants[0]


def _court_payload(spec: CalendarSource) -> dict[str, Any]:
    return {
        "court_id": spec.court_id,
        "native_court_id": spec.native_court_id,
        "name": spec.court_name,
        "state_code": STATE_CODE,
        "county_geoid": None,
        "court_level": spec.court_level,
        "official_url": spec.page_url,
    }


def _document_type(file_name: str) -> str:
    lowered = file_name.casefold()
    if "brief" in lowered or re.search(r"\d+br[a-z]", lowered):
        return "appellate_brief"
    return "calendar_attachment"


def _attachment_documents(
    spec: CalendarSource,
    row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    values = row.get("AttachmentFiles")
    if not isinstance(values, list):
        return []
    item_id = _integer(row.get("ID"))
    documents: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            continue
        file_name = _text(value.get("FileName"))
        relative_url = _text(value.get("ServerRelativeUrl"))
        if file_name is None or relative_url is None:
            continue
        encoded_path = quote(relative_url, safe="/:")
        source_url = urljoin(SHAREPOINT_ORIGIN, encoded_path)
        mime_type = mimetypes.guess_type(file_name)[0]
        native_id = (
            f"sharepoint-attachment:{item_id or 'unknown'}:"
            f"{file_name}"
        )
        documents.append(
            {
                "native_document_id": native_id,
                "document_name": file_name,
                "file_name": file_name,
                "document_type": _document_type(file_name),
                "source_url": source_url,
                "mime_type": mime_type,
                "metadata_available": True,
                "file_retrievable": True,
                "access_state": "public",
                "sequence_no": index + 1,
                "raw": dict(value),
            }
        )
    return documents


def _panel_values(value: Any) -> list[str]:
    if isinstance(value, list):
        candidates = value
    else:
        candidates = re.split(r"\s*;\s*", _text(value) or "")
    values: list[str] = []
    for candidate in candidates:
        normalized = _text(candidate)
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def _normalize_event(
    spec: CalendarSource,
    row: Mapping[str, Any],
    *,
    source_schema_fingerprint: str,
    retrieval: Mapping[str, Any],
) -> dict[str, Any]:
    case_number = _primary_case_number(spec, row)
    variants = _case_number_variants(spec, row)
    caption = _required_text(row.get("Title"), "Title")
    item_id = _integer(row.get("ID"))
    if item_id is None or item_id <= 0:
        raise ValueError("Oregon appellate calendar ID must be positive")
    guid = _required_text(row.get("GUID"), "GUID")
    event_date, event_time, event_datetime = _event_temporal(spec, row)
    event_type, event_code = _event_type(spec, row)
    panel = (
        _panel_values(row.get("Panel"))
        if spec is COURT_OF_APPEALS
        else _panel_values(row.get("Justices"))
    )
    documents = _attachment_documents(spec, row)
    list_item_url = f"{spec.item_form_root}?ID={item_id}"
    raw_status = _text(row.get("Status"))
    source_format = _text(row.get("SubmissionForm"))
    native_entry_id = f"sharepoint-item:{guid}"
    entry = {
        "native_entry_id": native_entry_id,
        "backend": "oregon_ojd_sharepoint",
        "source_namespace_id": f"OR_OJD_CALENDAR:{guid}",
        "identity_kind": "sharepoint_list_item",
        "identity_basis": {
            "list_title": spec.list_title,
            "item_id": item_id,
            "item_guid": guid,
        },
        "sequence_no": _integer(row.get("SequenceNbr")),
        "event_code": event_code,
        "event_type": event_type,
        "raw_text": source_format or f"{spec.court_name} calendar event",
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "event_datetime": event_datetime,
        "source_event_datetime_raw": _text(row.get("Date")),
        "location": _text(row.get("Location")),
        "judge": "; ".join(panel) or None,
        "panel": panel,
        "argument_format": source_format,
        "status": raw_status,
        "native_status": raw_status,
        "comments": _html_text(row.get("Comments")),
        "document_available": bool(documents),
        "access_state": "public",
        "documents": documents,
        "source_url": list_item_url,
        "raw": dict(row),
    }
    return {
        "canonical_ref": canonical_court_ref(
            spec.source_id,
            spec.court_id,
            case_number,
        ),
        "source_id": spec.source_id,
        "record_kind": "case",
        "backend": "oregon_ojd_sharepoint",
        "court": _court_payload(spec),
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "case_number_variants": variants,
        "source_internal_id": None,
        "caption": caption,
        "caption_variants": [caption],
        "case_type": _text(row.get("CaseType")),
        "case_type_variants": (
            [_text(row.get("CaseType"))]
            if _text(row.get("CaseType"))
            else []
        ),
        "filing_date": None,
        "status": raw_status,
        "access_state": "public",
        "certified_record": False,
        "source_url": spec.page_url,
        "native_record_url": list_item_url,
        "attorneys_text": _html_text(row.get("Attorneys")),
        "issues_summary": _html_text(row.get("Issues")),
        "comments": _html_text(row.get("Comments")),
        "parties": [],
        "docket_entries": [entry],
        "documents": [],
        "source_scope": {
            "legacy_entrypoint": spec.legacy_url,
            "current_official_page": spec.page_url,
            "sharepoint_list_title": spec.list_title,
            "sharepoint_list_path": spec.list_path,
            "sharepoint_view_name": spec.view_name,
            "list_item_id": item_id,
            "list_item_guid": guid,
            "source_modified_at": _text(row.get("Modified")),
            "source_created_at": _text(row.get("Created")),
        },
        "search_metadata": dict(retrieval),
        "schema_fingerprint": source_schema_fingerprint,
        "raw": dict(row),
    }


def _merge_distinct(target: list[Any], values: Sequence[Any]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def normalize_cases(
    spec: CalendarSource,
    rows: Sequence[Mapping[str, Any]],
    *,
    source_schema_fingerprint: str,
    retrieval: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Normalize and group calendar list items by source-native case number."""

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        normalized = _normalize_event(
            spec,
            row,
            source_schema_fingerprint=source_schema_fingerprint,
            retrieval=retrieval,
        )
        key = _required_text(normalized.get("raw_case_number"), "case number")
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = normalized
            continue
        _merge_distinct(
            existing["case_number_variants"],
            normalized["case_number_variants"],
        )
        _merge_distinct(
            existing["caption_variants"],
            normalized["caption_variants"],
        )
        _merge_distinct(
            existing["case_type_variants"],
            normalized["case_type_variants"],
        )
        existing["docket_entries"].extend(normalized["docket_entries"])
        for field_name in ("attorneys_text", "issues_summary", "comments"):
            if existing.get(field_name) is None and normalized.get(field_name):
                existing[field_name] = normalized[field_name]

    records = list(grouped.values())
    for record in records:
        record["docket_entries"].sort(
            key=lambda entry: (
                str(entry.get("event_datetime") or ""),
                entry.get("sequence_no") or 0,
                str(entry.get("native_entry_id") or ""),
            )
        )
    records.sort(
        key=lambda record: (
            str(record["docket_entries"][0].get("event_datetime") or ""),
            str(record.get("raw_case_number") or ""),
        )
    )
    return records


def parse_page_contract(
    html: str,
    spec: CalendarSource,
) -> dict[str, Any]:
    """Extract the current official page's declared SharePoint list contract."""

    soup = BeautifulSoup(html, "html.parser")
    component = soup.find("data-tables-web-part")
    if component is None:
        raise SourceSchemaError(
            f"{spec.name} page lacks its data-tables component",
            url=spec.page_url,
        )
    params = component.get("params")
    if not isinstance(params, str):
        raise SourceSchemaError(
            f"{spec.name} page has no component parameters",
            url=spec.page_url,
        )
    marker = "webPartProperties:"
    marker_index = params.find(marker)
    if marker_index < 0:
        raise SourceSchemaError(
            f"{spec.name} page lacks webPartProperties",
            url=spec.page_url,
        )
    candidate = params[marker_index + len(marker) :].lstrip()
    try:
        properties, _ = json.JSONDecoder().raw_decode(candidate)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise SourceSchemaError(
            f"{spec.name} page properties are not valid JSON",
            url=spec.page_url,
        ) from error
    if not isinstance(properties, Mapping):
        raise SourceSchemaError(
            f"{spec.name} page properties are not an object",
            url=spec.page_url,
        )
    observed_list = _text(properties.get("sharePointListUrl"))
    observed_view = _text(properties.get("sharePointViewName"))
    if observed_list != spec.list_path or observed_view != spec.view_name:
        raise SourceSchemaError(
            f"{spec.name} page points to an unexpected list or view",
            url=spec.page_url,
            details={
                "expected_list": spec.list_path,
                "observed_list": observed_list,
                "expected_view": spec.view_name,
                "observed_view": observed_view,
            },
        )
    return {
        "data_source": _text(properties.get("dataSource")),
        "sharepoint_web_url": _text(properties.get("sharePointWebUrl")),
        "sharepoint_list_url": observed_list,
        "sharepoint_view_name": observed_view,
        "table_caption": _text(properties.get("tableCaption")),
        "pagination_enabled": bool(properties.get("paginationEnabled")),
        "search_enabled": bool(properties.get("searchEnabled")),
        "sort_enabled": bool(properties.get("sortEnabled")),
        "filter_enabled": bool(properties.get("filterEnabled")),
        "attachment_links_requested": spec is SUPREME_COURT,
    }


def _checked_response(response: Any, *, url: str) -> Any:
    status = int(getattr(response, "status_code", 0) or 0)
    if 200 <= status < 300:
        return response
    text = str(getattr(response, "text", "") or "")
    if status in {401, 403}:
        raise RestrictedHTTPError(
            status,
            url=url,
            response_text=text,
        )
    if status == 429:
        raise RateLimitedHTTPError(
            status,
            url=url,
            response_text=text,
        )
    if status in {404, 410}:
        raise SourceChangedHTTPError(
            status,
            url=url,
            response_text=text,
        )
    raise HTTPStatusError(
        status,
        url=url,
        response_text=text,
    )


class OregonAppellateCalendarClient:
    """Retrying public client for Oregon's appellate SharePoint calendars."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = 30.0,
        max_attempts: int = 3,
        minimum_interval: float = 0.0,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.minimum_interval = minimum_interval
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at: float | None = None
        self._owns_session = session is None
        self.request_count = 0
        self.headers = {
            "User-Agent": "Ithildin public-record source adapter",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _wait(self) -> None:
        if self._last_request_at is not None:
            remaining = self.minimum_interval - (
                self._clock() - self._last_request_at
            )
            if remaining > 0:
                self._sleeper(remaining)
        self._last_request_at = self._clock()

    def _get(
        self,
        url: str,
        *,
        accept: str,
        params: Mapping[str, Any] | None = None,
        allow_redirects: bool = True,
    ) -> Any:
        last_error: PublicRecordsHTTPError | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    url,
                    params=dict(params or {}),
                    headers={**self.headers, "Accept": accept},
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
                return _checked_response(response, url=url)
            except requests.RequestException as error:
                last_error = TransportError(
                    f"{spec_name_from_url(url)} request failed",
                    url=url,
                    details={"error": str(error)},
                )
            except PublicRecordsHTTPError as error:
                last_error = error
            retryable = (
                last_error.retryable
                or isinstance(last_error, RateLimitedHTTPError)
                or (
                    isinstance(last_error, HTTPStatusError)
                    and last_error.status_code >= 500
                )
            )
            if not retryable or attempt >= self.max_attempts:
                raise last_error
            self._sleeper(min(0.25 * (2 ** (attempt - 1)), 5.0))
        assert last_error is not None
        raise last_error

    def _get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], str]:
        response = self._get(
            url,
            accept="application/json;odata=nometadata",
            params=params,
        )
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SourceSchemaError(
                "Oregon appellate calendar endpoint did not return JSON",
                url=url,
            ) from error
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Oregon appellate calendar JSON must be an object",
                url=url,
            )
        return payload, str(getattr(response, "url", url) or url)

    def page_contract(self, spec: CalendarSource) -> dict[str, Any]:
        response = self._get(
            spec.page_url,
            accept="text/html,application/xhtml+xml",
        )
        return parse_page_contract(str(response.text), spec)

    def legacy_contract(self, spec: CalendarSource) -> dict[str, Any]:
        response = self._get(
            spec.legacy_url,
            accept="text/html,application/xhtml+xml",
            allow_redirects=True,
        )
        final_url = str(getattr(response, "url", spec.legacy_url))
        history = []
        for value in getattr(response, "history", ()) or ():
            history.append(
                {
                    "status_code": int(getattr(value, "status_code", 0) or 0),
                    "url": str(getattr(value, "url", "") or ""),
                    "location": _text(
                        getattr(value, "headers", {}).get("Location")
                        if isinstance(getattr(value, "headers", {}), Mapping)
                        else None
                    ),
                }
            )
        migrated = (
            "aspxerrorpath=" in final_url.casefold()
            or any(
                "aspxerrorpath=" in str(item.get("location") or "").casefold()
                for item in history
            )
        )
        return {
            "requested_url": spec.legacy_url,
            "final_url": final_url,
            "status_code": int(getattr(response, "status_code", 0) or 0),
            "redirect_count": len(history),
            "redirect_chain": history,
            "migrated_to_error_path": migrated,
        }

    def view_contract(self, spec: CalendarSource) -> dict[str, Any]:
        payload, _ = self._get_json(
            spec.view_url,
            params={
                "$select": (
                    "Title,ViewQuery,RowLimit,Paged,DefaultView"
                )
            },
        )
        fields_payload, _ = self._get_json(spec.view_fields_url)
        fields = fields_payload.get("Items")
        if not isinstance(fields, list) or any(
            not isinstance(value, str) for value in fields
        ):
            raise SourceSchemaError(
                f"{spec.name} view fields are missing",
                url=spec.view_fields_url,
            )
        row_limit = _integer(payload.get("RowLimit"))
        if row_limit is None or row_limit <= 0:
            raise SourceSchemaError(
                f"{spec.name} view has no positive row limit",
                url=spec.view_url,
            )
        return {
            "title": _required_text(payload.get("Title"), "view Title"),
            "view_query": _text(payload.get("ViewQuery")),
            "row_limit": row_limit,
            "paged": bool(payload.get("Paged")),
            "default_view": bool(payload.get("DefaultView")),
            "view_fields": list(fields),
        }

    def list_contract(self, spec: CalendarSource) -> dict[str, Any]:
        payload, _ = self._get_json(
            spec.list_root,
            params={
                "$select": (
                    "Title,Id,ItemCount,LastItemModifiedDate,"
                    "RootFolder/ServerRelativeUrl"
                ),
                "$expand": "RootFolder",
            },
        )
        title = _required_text(payload.get("Title"), "list Title")
        item_count = _integer(payload.get("ItemCount"))
        root = payload.get("RootFolder")
        if title != spec.list_title:
            raise SourceSchemaError(
                f"{spec.name} list title changed",
                url=spec.list_root,
                details={
                    "expected_title": spec.list_title,
                    "observed_title": title,
                },
            )
        if item_count is None or item_count < 0:
            raise SourceSchemaError(
                f"{spec.name} list item count is invalid",
                url=spec.list_root,
            )
        if not isinstance(root, Mapping):
            raise SourceSchemaError(
                f"{spec.name} list root metadata is missing",
                url=spec.list_root,
            )
        root_path = _required_text(
            root.get("ServerRelativeUrl"),
            "list root path",
        )
        if root_path != spec.list_path:
            raise SourceSchemaError(
                f"{spec.name} list root path changed",
                url=spec.list_root,
                details={
                    "expected_path": spec.list_path,
                    "observed_path": root_path,
                },
            )
        return {
            "title": title,
            "list_id": _required_text(payload.get("Id"), "list Id"),
            "item_count": item_count,
            "last_item_modified_at": _text(
                payload.get("LastItemModifiedDate")
            ),
            "server_relative_url": root_path,
        }

    def fetch(self, spec: CalendarSource) -> CalendarFetch:
        start_request_count = self.request_count
        params: Mapping[str, Any] | None = {
            "$select": ",".join(spec.selected_fields),
            "$orderby": "ID",
            "$top": API_PAGE_SIZE,
        }
        if spec is SUPREME_COURT:
            params = {**params, "$expand": "AttachmentFiles"}
        url: str | None = spec.items_url
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        seen_ids: set[int] = set()
        pages = 0
        while url is not None:
            request_key = canonical_json(
                {"url": url, "params": dict(params or {})}
            )
            if request_key in seen_urls:
                raise SourceSchemaError(
                    f"{spec.name} pagination repeated a continuation",
                    url=url,
                )
            seen_urls.add(request_key)
            payload, effective_url = self._get_json(url, params=params)
            pages += 1
            values = payload.get("value")
            if not isinstance(values, list) or any(
                not isinstance(value, Mapping) for value in values
            ):
                raise SourceSchemaError(
                    f"{spec.name} list response lacks a value array",
                    url=url,
                )
            for value in values:
                row = dict(value)
                missing = sorted(
                    field
                    for field in spec.required_fields
                    if field not in row
                )
                if missing:
                    raise SourceSchemaError(
                        f"{spec.name} list row is missing expected fields",
                        url=url,
                        details={"missing_fields": missing},
                    )
                item_id = _integer(row.get("ID"))
                if item_id is None or item_id <= 0:
                    raise SourceSchemaError(
                        f"{spec.name} list row has an invalid ID",
                        url=url,
                    )
                if item_id in seen_ids:
                    raise SourceSchemaError(
                        f"{spec.name} pagination repeated item {item_id}",
                        url=url,
                    )
                seen_ids.add(item_id)
                rows.append(row)
            next_url = (
                payload.get("odata.nextLink")
                or payload.get("@odata.nextLink")
                or payload.get("__next")
            )
            if next_url is not None and not isinstance(next_url, str):
                raise SourceSchemaError(
                    f"{spec.name} continuation is not text",
                    url=url,
                )
            url = urljoin(effective_url, next_url) if next_url else None
            params = None
        rows.sort(key=lambda row: int(row["ID"]))
        schema = (
            inferred_schema(rows)
            if rows
            else {
                "kind": "declared_empty_list",
                "fields": sorted(spec.required_fields),
            }
        )
        return CalendarFetch(
            rows=tuple(rows),
            pages_fetched=pages,
            requests_made=self.request_count - start_request_count,
            schema=schema,
            schema_fingerprint=schema_fingerprint(schema),
            item_ids=tuple(int(row["ID"]) for row in rows),
        )


def spec_name_from_url(url: str) -> str:
    if "Supreme" in url or "sclist" in url or "sc-calendar" in url:
        return "Oregon Supreme Court calendar"
    if "ORCTrack" in url or "coadocket" in url or "coa-calendar" in url:
        return "Oregon Court of Appeals calendar"
    return "Oregon appellate calendar"


def _resolve_spec(value: Any) -> CalendarSource:
    normalized = (_text(value) or "").casefold()
    spec = SOURCES.get(normalized)
    if spec is None:
        raise OregonAppellateCalendarSelectionError(
            "unknown_court",
            "Court must be coa or supreme",
            details={"court": value},
        )
    return spec


def _matches_case_number(
    spec: CalendarSource,
    row: Mapping[str, Any],
    selector: str,
) -> bool:
    requested = selector.casefold()
    return any(
        variant.casefold() == requested
        for variant in _case_number_variants(spec, row)
    )


def _row_search_text(
    spec: CalendarSource,
    row: Mapping[str, Any],
) -> str:
    values: list[Any] = [
        row.get("Title"),
        row.get("Location"),
        row.get("CaseNbr"),
        row.get("CaseType"),
        row.get("Panel"),
        row.get("SubmissionForm"),
        row.get("SCNumber"),
        row.get("CANumber"),
        _html_text(row.get("Attorneys")),
        _html_text(row.get("Issues")),
        _html_text(row.get("Comments")),
    ]
    values.extend(_panel_values(row.get("Justices")))
    return "\n".join(str(value) for value in values if _text(value)).casefold()


def _filter_rows(
    spec: CalendarSource,
    rows: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    date_after = _parse_iso_date(
        getattr(args, "date_after", None),
        "--after",
    )
    date_before = _parse_iso_date(
        getattr(args, "date_before", None),
        "--before",
    )
    current = bool(getattr(args, "current", False))
    if current:
        today = _oregon_today()
        date_after = max(date_after, today) if date_after else today
    if date_after and date_before and date_after > date_before:
        raise OregonAppellateCalendarSelectionError(
            "invalid_date_range",
            "--after cannot be later than --before",
            details={
                "date_after": date_after.isoformat(),
                "date_before": date_before.isoformat(),
            },
        )
    case_number = _text(getattr(args, "case_number", None))
    query_text = _text(getattr(args, "query_text", None))
    event_types = tuple(getattr(args, "event_types", None) or ())
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        event_date = date.fromisoformat(_event_temporal(spec, row)[0])
        if date_after and event_date < date_after:
            continue
        if date_before and event_date > date_before:
            continue
        if case_number and not _matches_case_number(spec, row, case_number):
            continue
        if query_text and query_text.casefold() not in _row_search_text(spec, row):
            continue
        event_type, _ = _event_type(spec, row)
        if event_types and event_type.replace("_", "-") not in event_types:
            continue
        selected.append(row)
    selected.sort(
        key=lambda row: (
            _event_temporal(spec, row)[2],
            _integer(row.get("SequenceNbr")) or 0,
            _primary_case_number(spec, row),
            _integer(row.get("ID")) or 0,
        )
    )
    return selected, {
        "date_after": date_after.isoformat() if date_after else None,
        "date_before": date_before.isoformat() if date_before else None,
        "current": current,
        "case_number": case_number,
        "query_text": query_text,
        "event_types": list(event_types),
    }


def _identity_snapshot(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_fingerprint(
        [
            {
                "canonical_ref": record.get("canonical_ref"),
                "events": [
                    {
                        "native_entry_id": entry.get("native_entry_id"),
                        "modified": (
                            entry.get("raw", {}).get("Modified")
                            if isinstance(entry.get("raw"), Mapping)
                            else None
                        ),
                    }
                    for entry in record.get("docket_entries", [])
                    if isinstance(entry, Mapping)
                ],
            }
            for record in records
        ]
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source_id": state.source_id,
        "q": state.query_fingerprint,
        "snapshot": state.snapshot_fingerprint,
        "offset": state.offset,
        "anchor": state.anchor,
    }
    encoded = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(value: str | None) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise OregonAppellateCalendarSelectionError(
            "invalid_cursor",
            "Oregon appellate calendar cursor has an unknown prefix",
            status=ResultStatus.SOURCE_CHANGED,
            category="pagination",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise OregonAppellateCalendarSelectionError(
            "invalid_cursor",
            "Oregon appellate calendar cursor is malformed",
            status=ResultStatus.SOURCE_CHANGED,
            category="pagination",
        ) from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or not isinstance(payload.get("source_id"), str)
        or not isinstance(payload.get("q"), str)
        or not isinstance(payload.get("snapshot"), str)
        or not isinstance(payload.get("anchor"), str)
        or isinstance(payload.get("offset"), bool)
        or not isinstance(payload.get("offset"), int)
        or payload["offset"] <= 0
    ):
        raise OregonAppellateCalendarSelectionError(
            "invalid_cursor",
            "Oregon appellate calendar cursor fields are invalid",
            status=ResultStatus.SOURCE_CHANGED,
            category="pagination",
        )
    return CursorState(
        source_id=payload["source_id"],
        query_fingerprint=payload["q"],
        snapshot_fingerprint=payload["snapshot"],
        offset=payload["offset"],
        anchor=payload["anchor"],
    )


def _paginate_records(
    spec: CalendarSource,
    records: Sequence[Mapping[str, Any]],
    *,
    query_identity: Mapping[str, Any],
    limit: int | None,
    cursor_value: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise OregonAppellateCalendarSelectionError(
            "invalid_limit",
            "Oregon appellate calendar limit must be a positive integer",
        )
    query_fingerprint = sha256_fingerprint(query_identity)
    snapshot_fingerprint = _identity_snapshot(records)
    cursor = _decode_cursor(cursor_value)
    offset = 0
    if cursor is not None:
        if cursor.source_id != spec.source_id:
            raise OregonAppellateCalendarSelectionError(
                "cursor_source_mismatch",
                "Oregon appellate calendar cursor belongs to another source",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        if cursor.query_fingerprint != query_fingerprint:
            raise OregonAppellateCalendarSelectionError(
                "cursor_query_mismatch",
                "Oregon appellate calendar cursor belongs to another query",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        if cursor.snapshot_fingerprint != snapshot_fingerprint:
            raise OregonAppellateCalendarSelectionError(
                "cursor_snapshot_changed",
                "Oregon appellate calendar rows changed since the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
                details={
                    "cursor_snapshot": cursor.snapshot_fingerprint,
                    "current_snapshot": snapshot_fingerprint,
                },
            )
        offset = cursor.offset
        if offset >= len(records):
            raise OregonAppellateCalendarSelectionError(
                "cursor_offset_out_of_range",
                "Oregon appellate calendar cursor exceeds the result set",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        previous = records[offset - 1]
        if previous.get("canonical_ref") != cursor.anchor:
            raise OregonAppellateCalendarSelectionError(
                "cursor_anchor_changed",
                "Oregon appellate calendar cursor boundary changed",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
    end = len(records) if limit is None else min(len(records), offset + limit)
    selected = list(records[offset:end])
    next_cursor = None
    if end < len(records):
        anchor = _required_text(
            records[end - 1].get("canonical_ref"),
            "cursor anchor",
        )
        next_cursor = _encode_cursor(
            CursorState(
                source_id=spec.source_id,
                query_fingerprint=query_fingerprint,
                snapshot_fingerprint=snapshot_fingerprint,
                offset=end,
                anchor=anchor,
            )
        )
    return selected, next_cursor


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {
        "court": getattr(args, "court", None),
    }
    for name in (
        "date_after",
        "date_before",
        "current",
        "case_number",
        "query_text",
        "event_types",
    ):
        if hasattr(args, name):
            value = getattr(args, name)
            if value not in (None, (), [], False):
                values[name] = value
    return values


def _decision_metadata(
    decision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if decision is None:
        return {"mode": "direct_public_route", "allowed": True}
    return {
        key: decision[key]
        for key in (
            "source_id",
            "allowed",
            "access_class",
            "automation_disposition",
            "reason_code",
            "limits",
        )
        if key in decision
    }


def build_query(
    args: argparse.Namespace,
    spec: CalendarSource,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    raw_limit = getattr(args, "limit", None)
    requested_limit = (
        raw_limit
        if isinstance(raw_limit, int)
        and not isinstance(raw_limit, bool)
        and raw_limit > 0
        else None
    )
    return PublicRecordsQuery(
        source=SOURCE_METADATA_BY_ID[spec.source_id],
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Oregon",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
            metadata={
                "access_decision": _decision_metadata(access_decision),
            },
        ),
    )


def _default_access_decision(spec: CalendarSource) -> dict[str, Any]:
    return {
        "source_id": spec.source_id,
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
        "limits": {},
    }


def _access_failure(
    query: PublicRecordsQuery,
    spec: CalendarSource,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    disposition = _text(decision.get("automation_disposition"))
    status = {
        "human_required": ResultStatus.HUMAN_REQUIRED,
        "restricted": ResultStatus.RESTRICTED,
        "terms_blocked": ResultStatus.TERMS_BLOCKED,
    }.get(disposition or "", ResultStatus.UNAVAILABLE)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or f"{spec.name} acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=_warnings(spec),
    )


def _selection_failure(
    query: PublicRecordsQuery,
    spec: CalendarSource,
    error: OregonAppellateCalendarSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=_warnings(spec),
    )


def _search_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    spec: CalendarSource,
    fetched: CalendarFetch,
) -> PublicRecordsResult:
    filtered_rows, filters = _filter_rows(spec, fetched.rows, args)
    retrieval = {
        "source_pages_fetched": fetched.pages_fetched,
        "source_requests_made": fetched.requests_made,
        "source_rows_fetched": len(fetched.rows),
        "source_pagination_complete": True,
        "source_page_size": API_PAGE_SIZE,
        "filters": filters,
    }
    records = normalize_cases(
        spec,
        filtered_rows,
        source_schema_fingerprint=fetched.schema_fingerprint,
        retrieval=retrieval,
    )
    selected, next_cursor = _paginate_records(
        spec,
        records,
        query_identity={
            "source_id": spec.source_id,
            "operation": "search",
            "filters": filters,
        },
        limit=getattr(args, "limit", None),
        cursor_value=getattr(args, "cursor", None),
    )
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
        raw_artifact_refs=(spec.page_url, spec.items_url),
        warnings=_warnings(spec),
    )


def _eligible_view_count(
    spec: CalendarSource,
    rows: Sequence[Mapping[str, Any]],
) -> int:
    if not spec.view_current_only:
        return len(rows)
    today = _oregon_today()
    return sum(
        date.fromisoformat(_event_temporal(spec, row)[0]) >= today
        for row in rows
    )


def _probe_result(
    query: PublicRecordsQuery,
    spec: CalendarSource,
    client: OregonAppellateCalendarClient | Any,
) -> PublicRecordsResult:
    legacy = client.legacy_contract(spec)
    page = client.page_contract(spec)
    view = client.view_contract(spec)
    source_list = client.list_contract(spec)
    fetched = client.fetch(spec)
    count_matches = source_list["item_count"] == len(fetched.rows)
    eligible_count = _eligible_view_count(spec, fetched.rows)
    row_limit = int(view["row_limit"])
    official_view_may_truncate = eligible_count > row_limit
    attachment_items = sum(
        bool(row.get("AttachmentFiles")) for row in fetched.rows
    )
    attachment_documents = sum(
        len(value)
        for row in fetched.rows
        if isinstance((value := row.get("AttachmentFiles")), list)
    )
    component_status = {
        "legacy_entrypoint": (
            "migrated"
            if legacy.get("migrated_to_error_path")
            else "ok"
        ),
        "current_official_page": "ok",
        "sharepoint_list_api": "ok" if count_matches else "partial",
        "official_page_view": (
            "partial" if official_view_may_truncate else "ok"
        ),
        "adapter_acquisition": "ok" if count_matches else "partial",
    }
    warnings = list(_warnings(spec))
    if legacy.get("migrated_to_error_path"):
        warnings.append(
            f"The historical entrypoint {spec.legacy_url} currently redirects "
            "to an OJD error-path page; acquisition uses the current official "
            f"calendar page at {spec.page_url}."
        )
    if official_view_may_truncate:
        warnings.append(
            f"The official page view row limit is {row_limit}, below the "
            f"{eligible_count} list rows eligible for that view; the adapter "
            "followed the list API and preserved all source pages."
        )
    if not count_matches:
        warnings.append(
            f"The SharePoint list reports {source_list['item_count']} items, "
            f"while the public traversal returned {len(fetched.rows)}."
        )
    record = {
        "source_id": spec.source_id,
        "record_kind": "probe",
        "court": _court_payload(spec),
        "legacy_entrypoint": legacy,
        "page_contract": page,
        "view_contract": view,
        "list_contract": source_list,
        "checks": {
            "component_status": component_status,
            "list_item_count": len(fetched.rows),
            "declared_list_item_count": source_list["item_count"],
            "declared_and_fetched_item_counts_match": count_matches,
            "official_view_eligible_item_count": eligible_count,
            "official_view_row_limit": row_limit,
            "official_view_may_truncate": official_view_may_truncate,
            "source_pages_fetched": fetched.pages_fetched,
            "source_requests_made": fetched.requests_made,
            "source_pagination_complete": True,
            "attachment_item_count": attachment_items,
            "attachment_document_count": attachment_documents,
            "oldest_event_date": (
                min(
                    _event_temporal(spec, row)[0]
                    for row in fetched.rows
                )
                if fetched.rows
                else None
            ),
            "newest_event_date": (
                max(
                    _event_temporal(spec, row)[0]
                    for row in fetched.rows
                )
                if fetched.rows
                else None
            ),
        },
        "schema_fingerprints": {
            "page_contract": sha256_fingerprint(page),
            "view_contract": sha256_fingerprint(view),
            "list_contract": sha256_fingerprint(source_list),
            "list_items": fetched.schema_fingerprint,
        },
        "source_urls": {
            "legacy": spec.legacy_url,
            "current_page": spec.page_url,
            "list_api": spec.items_url,
        },
    }
    result_kwargs = {
        "raw_artifact_refs": (
            spec.legacy_url,
            spec.page_url,
            spec.items_url,
        ),
        "warnings": warnings,
    }
    if count_matches:
        return PublicRecordsResult.success(query, [record], **result_kwargs)
    return PublicRecordsResult.failure(
        query,
        ResultStatus.PARTIAL,
        [
            PublicRecordsError(
                code="source_list_count_mismatch",
                message=(
                    "The complete continuation traversal did not match the "
                    "SharePoint list's declared item count"
                ),
                category="completeness",
                retryable=False,
                details={
                    "declared_item_count": source_list["item_count"],
                    "fetched_item_count": len(fetched.rows),
                },
            )
        ],
        records=[record],
        **result_kwargs,
    )


def _execute_command(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    spec: CalendarSource,
    client: OregonAppellateCalendarClient | Any,
) -> PublicRecordsResult:
    if args.command == "search":
        return _search_result(args, query, spec, client.fetch(spec))
    if args.command == "probe":
        return _probe_result(query, spec, client)
    raise ValueError(f"unsupported Oregon appellate calendar command: {args.command}")


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
    spec: CalendarSource,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), spec.source_id, count)
    except Exception:
        pass


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: OregonAppellateCalendarClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one separately sourced Oregon appellate calendar operation."""

    spec = _resolve_spec(getattr(args, "court", None))
    decision = (
        dict(access_decision)
        if access_decision is not None
        else _default_access_decision(spec)
    )
    query = build_query(args, spec, access_decision=decision)
    decision_source = decision.get("source_id")
    if decision_source is not None and decision_source != spec.source_id:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message="Access decision belongs to another source component",
                    category="access",
                    retryable=False,
                    details={
                        "decision_source_id": decision_source,
                        "query_source_id": spec.source_id,
                    },
                )
            ],
            warnings=_warnings(spec),
        )
        if log_results:
            _best_effort_log(query, result, spec)
        return result
    if not decision.get("allowed", False):
        result = _access_failure(query, spec, decision)
        if log_results:
            _best_effort_log(query, result, spec)
        return result

    raw_limit = getattr(args, "limit", None)
    selection_error: OregonAppellateCalendarSelectionError | None = None
    if raw_limit is not None and (
        isinstance(raw_limit, bool)
        or not isinstance(raw_limit, int)
        or raw_limit <= 0
    ):
        selection_error = OregonAppellateCalendarSelectionError(
            "invalid_limit",
            "Oregon appellate calendar limit must be a positive integer",
        )
    if selection_error is not None:
        result = _selection_failure(query, spec, selection_error)
        if log_results:
            _best_effort_log(query, result, spec)
        return result

    source_client = client or OregonAppellateCalendarClient(
        timeout=float(getattr(args, "timeout", 30.0)),
        max_attempts=int(getattr(args, "max_attempts", 3)),
        minimum_interval=float(getattr(args, "minimum_interval", 0.0)),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, query, spec, source_client)
    except OregonAppellateCalendarSelectionError as error:
        result = _selection_failure(query, spec, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=_warnings(spec),
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
            warnings=_warnings(spec),
        )
    finally:
        if owns_client:
            source_client.close()
    if log_results:
        _best_effort_log(query, result, spec)
    return result


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
    *,
    output_writer: Callable[..., bool] = write_output,
) -> None:
    payload = result.to_dict()
    label = str(getattr(args, "court", "appellate"))
    if output_writer(
        payload,
        args,
        summary=(
            f"Oregon {label} calendar {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Oregon {label} calendar {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{len(record.get('docket_entries') or [])} event(s) | "
                f"{record.get('caption') or '?'}"
            )
        else:
            checks = record.get("checks") or {}
            print(
                f"  probe | {checks.get('list_item_count', 0)} list rows | "
                f"{checks.get('source_pages_fetched', 0)} source page(s)"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--court",
        required=True,
        choices=("coa", "court-of-appeals", "supreme", "supreme-court"),
        help="Select the separately attributed appellate calendar source",
    )


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    parser.add_argument("--minimum-interval", type=float, default=0.0)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Oregon's separately published Supreme Court and Court of "
            "Appeals calendars"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search all accessible list rows, then apply local filters",
    )
    _add_source(search)
    search.add_argument("--after", dest="date_after")
    search.add_argument("--before", dest="date_before")
    search.add_argument(
        "--current",
        action="store_true",
        help="Explicitly limit results to today and later",
    )
    search.add_argument("--case-number")
    search.add_argument(
        "--query",
        dest="query_text",
        help="Text match across captions, cases, panels, attorneys, and issues",
    )
    search.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        choices=("oral-argument", "submission"),
        help="Repeat to select normalized event types",
    )
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Local case page size; omitted returns every matching case",
    )
    search.add_argument("--cursor")
    _add_runtime(search)

    probe = sub.add_parser(
        "probe",
        help="Verify the legacy migration, current page, view, and list API",
    )
    _add_source(probe)
    _add_runtime(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
