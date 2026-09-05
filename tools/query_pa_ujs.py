#!/usr/bin/env python3
"""Query Pennsylvania UJS Public Web Docket Sheets.

The official UJS Case Search is an anonymous, server-rendered ASP.NET form.
It supports exact docket, participant, organization, filing-date, and
appellate searches. Search results provide case and scheduled-event metadata
plus court-specific docket-sheet and Court Summary PDF routes.

Examples:
    uv run python tools/query_pa_ujs.py case "69 WAL 2026" --json
    uv run python tools/query_pa_ujs.py person PEREZ \
        --first-name JUNIOR --county Philadelphia --json
    uv run python tools/query_pa_ujs.py organization WALMART \
        --county Allegheny --output walmart.json
    uv run python tools/query_pa_ujs.py filed 2026-07-28 2026-07-28 \
        --county Philadelphia --output filed.json
    uv run python tools/query_pa_ujs.py report CP-51-CR-0007622-2022 \
        /tmp/pa-docket.pdf --output /tmp/pa-docket.json
    uv run python tools/query_pa_ujs.py probe --json
    uv run python tools/query_pa_ujs.py sentinel --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

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
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
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
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-pa-ujs-public-dockets"
STATE_CODE = "PA"
STATE_GEOID = "42"
BASE_URL = "https://ujsportal.pacourts.us"
CASE_SEARCH_URL = f"{BASE_URL}/CaseSearch"
CASE_INFORMATION_URL = f"{BASE_URL}/Home/CaseInformation"
OFFICIAL_HELP_URL = (
    "https://ujswebportalhelp.pacourts.us/Resources/"
    "PDF%20Documents/UJS%20Docket%20Sheets%20%28Case%20Search%29.pdf"
)
OFFICIAL_RECORDS_URL = "https://www.pacourts.us/public-records/public-records-forms"
OFFICIAL_OPINIONS_URL = (
    "https://www.pacourts.us/courts/supreme-court/court-opinions"
)

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
FILED_DATE_MAX_SPAN_DAYS = 180
SOURCE_RESULT_THRESHOLD_PER_SYSTEM = 501
COMMON_PLEAS_SENTINEL = "CP-51-CR-0007622-2022"
APPELLATE_SENTINEL = "69 WAL 2026"

_REQUIRED_SEARCH_MODES = frozenset(
    {
        "AppellateCourtName",
        "DateFiled",
        "DocketNumber",
        "Organization",
        "ParticipantName",
    }
)
_REQUIRED_RESULT_HEADERS = frozenset(
    {
        "CalendarEventDateTime",
        "CalendarEventID",
        "CalendarEventLocation",
        "CalendarEventStatus",
        "CalendarEventType",
        "CaseStatus",
        "ComplaintNumber",
        "CountyName",
        "CourtOffice",
        "CourtSystem",
        "DocketNumber",
        "FilingDate",
        "IncidentNumber",
        "OTN",
        "PrimaryParticipantDOB",
        "PrimaryParticipantName",
        "ShortCaption",
    }
)
_NO_RESULTS_RE = re.compile(r"\bno results found\b", re.IGNORECASE)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Pennsylvania UJS Public Web Docket Sheets",
    source_role="statewide_public_case_calendar_and_docket_sheet_index",
    base_url=CASE_SEARCH_URL,
    dataset_id="ujs-public-web-docket-sheets",
    metadata={
        "authority": "Unified Judicial System of Pennsylvania",
        "operator": "Administrative Office of Pennsylvania Courts",
        "state_code": STATE_CODE,
        "authentication": "none",
        "platform_family": "aspnet_server_rendered_form",
        "native_pagination": "none",
        "filed_date_max_span_days": FILED_DATE_MAX_SPAN_DAYS,
        "observed_result_threshold_per_court_system": (
            SOURCE_RESULT_THRESHOLD_PER_SYSTEM
        ),
        "case_information_url": CASE_INFORMATION_URL,
        "official_help_url": OFFICIAL_HELP_URL,
    },
)

SOURCE_WARNINGS = (
    "UJS docket sheets list case actions and filings but do not provide the "
    "underlying filed documents; those remain with the applicable clerk or "
    "prothonotary.",
    "The public search excludes source-designated nonpublic records and does "
    "not expose Courts of Common Pleas civil cases.",
    "Recent court-office entries may not yet appear in the public portal.",
)


class PAUJSError(RuntimeError):
    """Source, transport, or selection error with result-envelope semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})


class PAUJSSelectionError(PAUJSError):
    """The caller supplied an unsupported native search selection."""

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


class PAUJSSourceChangedError(PAUJSError):
    """The official portal no longer matches the verified source contract."""

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
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class PAUJSQueryIncompleteError(PAUJSError):
    """The source accepted a form POST but did not return a result grid."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "source_result_grid_missing",
            message,
            status=ResultStatus.PARTIAL,
            category="source_query",
            details=details,
        )


@dataclass(frozen=True)
class PAUJSBootstrap:
    """Verified search form fields and source-native bounds."""

    csrf_token: str
    action_url: str
    search_modes: tuple[str, ...]
    form_fields: tuple[str, ...]
    filed_date_max_span_days: int
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class PAUJSSearchPage:
    """One complete server-rendered source response."""

    rows: tuple[Mapping[str, Any], ...]
    authoritative_empty: bool
    unique_cases_by_system: Mapping[str, int]
    threshold_systems: tuple[str, ...]
    schema_fingerprint: str
    source_url: str

    @property
    def source_row_count(self) -> int:
        return len(self.rows)

    @property
    def source_unique_case_count(self) -> int:
        return len(
            {
                str(row.get("DocketNumber") or "").strip()
                for row in self.rows
                if str(row.get("DocketNumber") or "").strip()
            }
        )


@dataclass(frozen=True)
class PAUJSReport:
    """Downloaded official UJS report bytes and integrity metadata."""

    content: bytes
    source_url: str
    media_type: str
    sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise PAUJSSourceChangedError(
            "required_field_missing",
            f"Pennsylvania UJS result lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _schema_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _source_date(value: Any, field_name: str) -> tuple[str | None, str | None]:
    raw = _text(value)
    if raw is None:
        return None, None
    try:
        return raw, datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise PAUJSSourceChangedError(
            "date_format_changed",
            f"Pennsylvania UJS returned an invalid {field_name}: {raw}",
            details={"field": field_name, "value": raw},
        ) from error


def _source_datetime(
    value: Any,
    field_name: str,
) -> tuple[str | None, str | None]:
    raw = _text(value)
    if raw is None:
        return None, None
    for date_format in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(raw, date_format)
            return raw, parsed.isoformat(timespec="minutes")
        except ValueError:
            continue
    raise PAUJSSourceChangedError(
        "datetime_format_changed",
        f"Pennsylvania UJS returned an invalid {field_name}: {raw}",
        details={"field": field_name, "value": raw},
    )


def _iso_query_date(value: Any, field_name: str) -> date:
    normalized = _text(value)
    if normalized is None:
        raise PAUJSSelectionError(
            "date_required",
            f"{field_name} is required",
            details={"field": field_name},
        )
    try:
        return date.fromisoformat(normalized)
    except ValueError as error:
        raise PAUJSSelectionError(
            "date_invalid",
            f"{field_name} must use YYYY-MM-DD: {normalized}",
            details={"field": field_name, "value": normalized},
        ) from error


def _validated_date_pair(
    start: Any,
    end: Any,
    *,
    enforce_filed_span: bool,
) -> tuple[str, str]:
    start_date = _iso_query_date(start, "filed_after")
    end_date = _iso_query_date(end, "filed_before")
    if end_date < start_date:
        raise PAUJSSelectionError(
            "date_range_reversed",
            "filed_before must be on or after filed_after",
            details={
                "filed_after": start_date.isoformat(),
                "filed_before": end_date.isoformat(),
            },
        )
    span_days = (end_date - start_date).days
    if enforce_filed_span and span_days > FILED_DATE_MAX_SPAN_DAYS:
        raise PAUJSSelectionError(
            "filed_date_span_exceeded",
            "Date Filed search spans cannot exceed 180 days",
            details={
                "filed_after": start_date.isoformat(),
                "filed_before": end_date.isoformat(),
                "span_days": span_days,
                "source_max_span_days": FILED_DATE_MAX_SPAN_DAYS,
            },
        )
    return start_date.isoformat(), end_date.isoformat()


def parse_bootstrap(
    html: str,
    *,
    source_url: str = CASE_SEARCH_URL,
) -> PAUJSBootstrap:
    """Parse and verify the anonymous UJS Case Search form."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#case-search-form-id")
    if not isinstance(form, Tag):
        raise PAUJSSourceChangedError(
            "case_search_form_missing",
            "Pennsylvania UJS page lacks #case-search-form-id",
        )
    method = (_text(form.get("method")) or "get").casefold()
    if method != "post":
        raise PAUJSSourceChangedError(
            "case_search_method_changed",
            f"Pennsylvania UJS search form now uses {method}",
            details={"method": method},
        )
    token_input = form.find("input", attrs={"name": "__RequestVerificationToken"})
    csrf_token = _text(token_input.get("value")) if isinstance(token_input, Tag) else None
    if csrf_token is None:
        raise PAUJSSourceChangedError(
            "antiforgery_token_missing",
            "Pennsylvania UJS search form lacks its antiforgery token",
        )

    search_select = form.select_one("#SearchBy-Control select")
    if not isinstance(search_select, Tag):
        raise PAUJSSourceChangedError(
            "search_modes_missing",
            "Pennsylvania UJS search form lacks its Search By selector",
        )
    search_modes: list[str] = []
    for option in search_select.find_all("option"):
        if not isinstance(option, Tag):
            continue
        value = _text(option.get("value")) or _text(option.get_text(" ", strip=True))
        if value:
            search_modes.append(value)
    missing_modes = sorted(_REQUIRED_SEARCH_MODES.difference(search_modes))
    if missing_modes:
        raise PAUJSSourceChangedError(
            "search_modes_changed",
            "Pennsylvania UJS search form lacks verified public search modes",
            details={"missing": missing_modes, "observed": search_modes},
        )

    filed_start = form.find("input", attrs={"name": "FiledStartDate"})
    if not isinstance(filed_start, Tag):
        raise PAUJSSourceChangedError(
            "filed_date_control_missing",
            "Pennsylvania UJS search form lacks FiledStartDate",
        )
    raw_span = _text(
        filed_start.get("data-aopc-maxallowedlimit")
        or filed_start.get("data-aopc-maxAllowedLimit")
    )
    try:
        max_span = int(raw_span or "")
    except ValueError as error:
        raise PAUJSSourceChangedError(
            "filed_date_span_changed",
            "Pennsylvania UJS filing-date span is no longer numeric",
            details={"value": raw_span},
        ) from error
    if max_span != FILED_DATE_MAX_SPAN_DAYS:
        raise PAUJSSourceChangedError(
            "filed_date_span_changed",
            "Pennsylvania UJS filing-date span changed",
            details={
                "expected": FILED_DATE_MAX_SPAN_DAYS,
                "observed": max_span,
            },
        )

    fields = tuple(
        sorted(
            {
                field_name
                for element in form.find_all(["input", "select"])
                if isinstance(element, Tag)
                for field_name in [_text(element.get("name"))]
                if field_name
            }
        )
    )
    action = _text(form.get("action"))
    action_url = urljoin(source_url, action or urlsplit(source_url).path)
    contract = {
        "action_path": urlsplit(action_url).path,
        "fields": fields,
        "max_span_days": max_span,
        "method": method,
        "search_modes": search_modes,
    }
    return PAUJSBootstrap(
        csrf_token=csrf_token,
        action_url=action_url,
        search_modes=tuple(search_modes),
        form_fields=fields,
        filed_date_max_span_days=max_span,
        schema_fingerprint=_schema_fingerprint(contract),
        source_url=source_url,
    )


def _report_urls(cell: Tag, *, source_url: str) -> dict[str, str]:
    reports: dict[str, str] = {}
    for anchor in cell.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        label = _text(anchor.get("aria-label")) or _text(
            anchor.get_text(" ", strip=True)
        )
        if label is None:
            continue
        key = _slug(label)
        href = urljoin(source_url, str(anchor["href"]))
        parsed = urlsplit(href)
        if (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
        ) != (
            urlsplit(BASE_URL).scheme.casefold(),
            urlsplit(BASE_URL).netloc.casefold(),
        ):
            raise PAUJSSourceChangedError(
                "report_link_origin_changed",
                "Pennsylvania UJS returned a report link on another origin",
                details={"url": href},
            )
        existing = reports.get(key)
        if existing is not None and existing != href:
            raise PAUJSSourceChangedError(
                "report_link_conflict",
                "Pennsylvania UJS returned conflicting report links",
                details={"label": label, "urls": [existing, href]},
            )
        reports[key] = href
    return reports


def parse_search_page(
    html: str,
    *,
    source_url: str = CASE_SEARCH_URL,
) -> PAUJSSearchPage:
    """Parse the complete UJS result grid returned by one form POST."""

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#caseSearchResultGrid")
    if not isinstance(table, Tag):
        if isinstance(soup.select_one("form#case-search-form-id"), Tag):
            raise PAUJSQueryIncompleteError(
                "Pennsylvania UJS accepted the search but returned no result grid",
                details={
                    "source_url": source_url,
                    "native_pagination": "none",
                },
            )
        raise PAUJSSourceChangedError(
            "result_grid_missing",
            "Pennsylvania UJS response lacks both the search form and result grid",
        )

    header_tags = table.select("thead th")
    headers = [
        _text(header.get("data-aopc-headername"))
        or _text(header.get_text(" ", strip=True))
        for header in header_tags
    ]
    if any(header is None for header in headers):
        raise PAUJSSourceChangedError(
            "result_header_blank",
            "Pennsylvania UJS result grid contains a blank header identity",
        )
    normalized_headers = tuple(str(header) for header in headers)

    body_rows = table.select("tbody tr")
    if len(body_rows) == 1:
        cells = body_rows[0].find_all("td", recursive=False)
        if (
            len(cells) == 1
            and _NO_RESULTS_RE.search(cells[0].get_text(" ", strip=True))
        ):
            contract = {
                "headers": normalized_headers,
                "native_pagination": "none",
            }
            return PAUJSSearchPage(
                rows=(),
                authoritative_empty=True,
                unique_cases_by_system={},
                threshold_systems=(),
                schema_fingerprint=_schema_fingerprint(contract),
                source_url=source_url,
            )

    missing_headers = sorted(
        _REQUIRED_RESULT_HEADERS.difference(normalized_headers)
    )
    if missing_headers:
        raise PAUJSSourceChangedError(
            "result_headers_changed",
            "Pennsylvania UJS result grid lacks verified columns",
            details={
                "missing": missing_headers,
                "observed": list(normalized_headers),
            },
        )

    rows: list[dict[str, Any]] = []
    unique_by_system: dict[str, set[str]] = {}
    for row_number, row_tag in enumerate(body_rows, start=1):
        cells = row_tag.find_all("td", recursive=False)
        if len(cells) != len(normalized_headers):
            raise PAUJSSourceChangedError(
                "result_row_width_changed",
                "Pennsylvania UJS result row width no longer matches headers",
                details={
                    "row_number": row_number,
                    "headers": len(normalized_headers),
                    "cells": len(cells),
                },
            )
        row = {
            header: _text(cell.get_text(" ", strip=True))
            for header, cell in zip(normalized_headers, cells, strict=True)
        }
        docket_number = _required_text(
            row.get("DocketNumber"),
            "DocketNumber",
        )
        court_system = _required_text(row.get("CourtSystem"), "CourtSystem")
        row["DocketNumber"] = docket_number
        row["CourtSystem"] = court_system
        row["report_urls"] = _report_urls(cells[-1], source_url=source_url)
        rows.append(row)
        unique_by_system.setdefault(court_system, set()).add(docket_number)

    unique_counts = {
        system: len(dockets)
        for system, dockets in sorted(unique_by_system.items())
    }
    threshold_systems = tuple(
        system
        for system, count in unique_counts.items()
        if count >= SOURCE_RESULT_THRESHOLD_PER_SYSTEM
    )
    contract = {
        "headers": normalized_headers,
        "native_pagination": "none",
        "report_labels": sorted(
            {
                label
                for row in rows
                for label in (row.get("report_urls") or {})
            }
        ),
    }
    return PAUJSSearchPage(
        rows=tuple(rows),
        authoritative_empty=False,
        unique_cases_by_system=unique_counts,
        threshold_systems=threshold_systems,
        schema_fingerprint=_schema_fingerprint(contract),
        source_url=source_url,
    )


def _court_id(court_system: str, court_office: str | None) -> str:
    native_court_id = court_office or court_system
    return f"pa-ujs-{_slug(native_court_id)}"


def _court_payload(
    *,
    court_system: str,
    court_office: str | None,
    county: str | None,
) -> dict[str, Any]:
    native_court_id = court_office or court_system
    court_id = _court_id(court_system, court_office)
    court_name = f"Pennsylvania UJS {court_system}"
    if court_office:
        court_name = f"{court_name} ({court_office})"
    return {
        "id": court_id,
        "court_id": court_id,
        "native_court_id": native_court_id,
        "name": court_name,
        "court_system": court_system,
        "court_office": court_office,
        "court_level": court_system,
        "branch": court_office,
        "county": county,
        "state_code": STATE_CODE,
        "jurisdiction_id": STATE_GEOID,
        "official_url": CASE_SEARCH_URL,
    }


def normalize_records(
    page: PAUJSSearchPage,
    *,
    selection: Mapping[str, str],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Collapse calendar-event rows onto stable case-number records."""

    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in page.rows:
        docket_number = _required_text(row.get("DocketNumber"), "DocketNumber")
        court_system = _required_text(row.get("CourtSystem"), "CourtSystem")
        caption = _text(row.get("ShortCaption"))
        status = _text(row.get("CaseStatus"))
        filing_date_raw, filing_date = _source_date(
            row.get("FilingDate"),
            "filing date",
        )
        primary_participants = _text(row.get("PrimaryParticipantName"))
        primary_dobs = _text(row.get("PrimaryParticipantDOB"))
        county = _text(row.get("CountyName"))
        court_office = _text(row.get("CourtOffice"))
        reports = dict(row.get("report_urls") or {})
        existing = grouped.get(docket_number)
        if existing is None:
            court = _court_payload(
                court_system=court_system,
                court_office=court_office,
                county=county,
            )
            parties: list[dict[str, Any]] = []
            if primary_participants:
                parties.append(
                    {
                        "sequence_no": 1,
                        "raw_name": primary_participants,
                        "role": "primary_participant",
                        "native_role": "Primary Participant(s)",
                        "date_of_birth_raw": primary_dobs,
                        "composite_source_field": True,
                        "access_state": "public",
                    }
                )
            existing = {
                "record_kind": "case",
                "source_id": SOURCE_ID,
                "court": court,
                "raw_case_number": docket_number,
                "display_case_number": docket_number,
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    court["court_id"],
                    docket_number,
                ),
                "caption": caption,
                "status": status,
                "filing_date_raw": filing_date_raw,
                "filing_date": filing_date,
                "primary_participants_raw": primary_participants,
                "primary_participant_dates_of_birth_raw": primary_dobs,
                "parties": parties,
                "county": county,
                "court_office": court_office,
                "otn": _text(row.get("OTN")),
                "complaint_number": _text(row.get("ComplaintNumber")),
                "incident_number": _text(row.get("IncidentNumber")),
                "calendar_events": [],
                "report_urls": reports,
                "docket_sheet_url": reports.get("docket_sheet"),
                "court_summary_url": reports.get("court_summary"),
                "source_url": CASE_SEARCH_URL,
                "access_state": "public",
                "native_access_state": "anonymous UJS public case search",
                "certified_record": False,
                "schema_fingerprint": page.schema_fingerprint,
                "raw": {"search_rows": []},
            }
            grouped[docket_number] = existing
        else:
            invariant = (
                existing["court"]["court_system"],
                existing["caption"],
                existing["status"],
                existing["filing_date_raw"],
                existing["primary_participants_raw"],
                existing["county"],
                existing["court_office"],
            )
            observed = (
                court_system,
                caption,
                status,
                filing_date_raw,
                primary_participants,
                county,
                court_office,
            )
            if invariant != observed:
                raise PAUJSSourceChangedError(
                    "duplicate_case_conflict",
                    "Pennsylvania UJS returned conflicting case rows",
                    details={"docket_number": docket_number},
                )
            for key, url in reports.items():
                prior = existing["report_urls"].get(key)
                if prior is not None and prior != url:
                    raise PAUJSSourceChangedError(
                        "duplicate_case_report_conflict",
                        "Pennsylvania UJS returned conflicting case report URLs",
                        details={
                            "docket_number": docket_number,
                            "report_kind": key,
                        },
                    )
                existing["report_urls"][key] = url
                if key == "docket_sheet":
                    existing["docket_sheet_url"] = url
                elif key == "court_summary":
                    existing["court_summary_url"] = url

        event_id = _text(row.get("CalendarEventID"))
        event_type = _text(row.get("CalendarEventType"))
        event_status = _text(row.get("CalendarEventStatus"))
        event_date_raw, event_date = _source_datetime(
            row.get("CalendarEventDateTime"),
            "calendar event date",
        )
        event_location = _text(row.get("CalendarEventLocation"))
        has_calendar_event = any(
            (event_type, event_status, event_date_raw, event_location)
        ) or event_id not in {None, "0"}
        if has_calendar_event:
            event = {
                "native_event_id": event_id,
                "event_type": event_type,
                "status": event_status,
                "event_date_raw": event_date_raw,
                "event_date": event_date,
                "location": event_location,
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "calendar_event",
            }
            identity = canonical_json(event)
            if all(
                canonical_json(existing_event) != identity
                for existing_event in existing["calendar_events"]
            ):
                existing["calendar_events"].append(event)

        existing["raw"]["search_rows"].append(
            {
                key: value
                for key, value in row.items()
                if key != "report_urls"
            }
        )

    records = list(grouped.values())
    for record in records:
        docket_number = record["raw_case_number"]
        record["documents"] = [
            {
                "native_document_id": f"{docket_number}:{report_kind}",
                "document_type": report_kind,
                "source_url": report_url,
                "mime_type": "application/pdf",
                "certification_status": "portal_copy",
                "access_state": "public",
                "native_access_state": "anonymous UJS public report link",
            }
            for report_kind, report_url in sorted(
                record["report_urls"].items()
            )
        ]
        court_system = record["court"]["court_system"]
        record["search_metadata"] = {
            "selection": dict(selection),
            "source_result_rows": page.source_row_count,
            "source_unique_cases": page.source_unique_case_count,
            "unique_cases_by_court_system": dict(
                page.unique_cases_by_system
            ),
            "native_pagination": "none",
            "source_result_threshold_per_court_system": (
                SOURCE_RESULT_THRESHOLD_PER_SYSTEM
            ),
            "source_threshold_reached": (
                court_system in page.threshold_systems
            ),
        }
    if limit is not None:
        records = records[:limit]
    return records


def native_selection(args: argparse.Namespace) -> dict[str, str]:
    """Translate one CLI command into the exact source form fields."""

    selection: dict[str, str] = {}
    if args.command in {"case", "report"}:
        selection = {
            "SearchBy": "DocketNumber",
            "DocketNumber": _required_text(
                args.docket_number,
                "docket_number",
            ),
        }
    elif args.command == "person":
        selection = {
            "SearchBy": "ParticipantName",
            "ParticipantLastName": _required_text(
                args.last_name,
                "last_name",
            ),
        }
        optional = {
            "ParticipantFirstName": args.first_name,
            "ParticipantDateOfBirth": args.date_of_birth,
            "County": args.county,
            "DocketType": args.docket_type,
            "CaseStatus": args.case_status,
        }
        selection.update(
            {
                key: value
                for key, raw in optional.items()
                if (value := _text(raw)) is not None
            }
        )
        _add_optional_date_pair(selection, args)
    elif args.command == "organization":
        selection = {
            "SearchBy": "Organization",
            "OrganizationName": _required_text(
                args.organization_name,
                "organization_name",
            ),
        }
        optional = {
            "County": args.county,
            "DocketType": args.docket_type,
            "CaseCategory": args.case_category,
            "CaseStatus": args.case_status,
        }
        selection.update(
            {
                key: value
                for key, raw in optional.items()
                if (value := _text(raw)) is not None
            }
        )
        _add_optional_date_pair(selection, args)
    elif args.command == "filed":
        start, end = _validated_date_pair(
            args.filed_after,
            args.filed_before,
            enforce_filed_span=True,
        )
        selection = {
            "SearchBy": "DateFiled",
            "FiledStartDate": start,
            "FiledEndDate": end,
        }
        optional = {
            "County": args.county,
            "DocketType": args.docket_type,
            "CaseStatus": args.case_status,
        }
        selection.update(
            {
                key: value
                for key, raw in optional.items()
                if (value := _text(raw)) is not None
            }
        )
    elif args.command == "appellate":
        start, end = _validated_date_pair(
            args.filed_after,
            args.filed_before,
            enforce_filed_span=False,
        )
        selection = {
            "SearchBy": "AppellateCourtName",
            "AdvanceSearch": "true",
            "AppellateCourtName": _required_text(args.court, "court"),
            "FiledStartDate": start,
            "FiledEndDate": end,
        }
        optional = {
            "AppellatePartyLastName": args.party_last,
            "AppellatePartyFirstName": args.party_first,
            "AppellateOrganizationName": args.organization,
            "AppellateDistrict": args.district,
            "AppellateDocketType": args.docket_type,
            "AppellateCaseStatus": args.case_status,
        }
        selection.update(
            {
                key: value
                for key, raw in optional.items()
                if (value := _text(raw)) is not None
            }
        )
        if selection.get("AppellatePartyFirstName") and not selection.get(
            "AppellatePartyLastName"
        ):
            raise PAUJSSelectionError(
                "appellate_party_last_required",
                "--party-first requires --party-last",
            )
    elif args.command == "probe":
        selection = {"contract": "anonymous-antiforgery-case-search"}
    elif args.command == "sentinel":
        selection = {
            "common_pleas_docket": COMMON_PLEAS_SENTINEL,
            "appellate_docket": APPELLATE_SENTINEL,
        }
    return selection


def _add_optional_date_pair(
    selection: dict[str, str],
    args: argparse.Namespace,
) -> None:
    raw_start = _text(getattr(args, "filed_after", None))
    raw_end = _text(getattr(args, "filed_before", None))
    if (raw_start is None) != (raw_end is None):
        raise PAUJSSelectionError(
            "filed_date_pair_required",
            "--filed-after and --filed-before must be supplied together",
        )
    if raw_start is None:
        return
    start, end = _validated_date_pair(
        raw_start,
        raw_end,
        enforce_filed_span=False,
    )
    selection["FiledStartDate"] = start
    selection["FiledEndDate"] = end


class PAUJSClient:
    """Session-aware client for the official UJS public form and reports."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Any = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "Accept": "text/html,application/xhtml+xml,application/pdf",
            "User-Agent": self.user_agent,
            **dict(headers or {}),
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise PAUJSError(
                        "transport_error",
                        "Pennsylvania UJS request failed after "
                        f"{attempt} attempts: {error}",
                        category="transport",
                        retryable=True,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                retry_after: float | None = None
                raw_retry_after = response.headers.get("Retry-After")
                if raw_retry_after:
                    try:
                        retry_after = max(0.0, float(raw_retry_after))
                    except ValueError:
                        retry_after = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                raise PAUJSError(
                    "rate_limited" if status_code == 429 else "http_status_error",
                    f"Pennsylvania UJS returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit" if status_code == 429 else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise PAUJSError(
                    "source_access_failed",
                    f"Pennsylvania UJS returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code},
                )
            if status_code in {404, 410}:
                raise PAUJSSourceChangedError(
                    "source_route_missing",
                    f"Pennsylvania UJS route returned HTTP {status_code}",
                    details={"status_code": status_code, "url": url},
                )
            if status_code < 200 or status_code >= 300:
                raise PAUJSError(
                    "http_status_error",
                    f"Pennsylvania UJS returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code},
                )
            return response

        raise PAUJSError(
            "transport_error",
            f"Pennsylvania UJS request failed: {last_error}",
            category="transport",
            retryable=True,
        )

    def bootstrap(self) -> PAUJSBootstrap:
        response = self._request("GET", CASE_SEARCH_URL)
        response_url = str(getattr(response, "url", CASE_SEARCH_URL))
        return parse_bootstrap(response.text, source_url=response_url)

    def search(self, selection: Mapping[str, str]) -> PAUJSSearchPage:
        form = self.bootstrap()
        payload = {
            key: value
            for key, value in selection.items()
            if key != "contract"
        }
        payload["__RequestVerificationToken"] = form.csrf_token
        response = self._request(
            "POST",
            form.action_url,
            headers={
                "Origin": BASE_URL,
                "Referer": form.source_url,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=payload,
        )
        response_url = str(getattr(response, "url", form.action_url))
        return parse_search_page(response.text, source_url=response_url)

    def fetch_report(self, source_url: str) -> PAUJSReport:
        parsed = urlsplit(source_url)
        expected = urlsplit(BASE_URL)
        if (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
        ) != (
            expected.scheme.casefold(),
            expected.netloc.casefold(),
        ) or not parsed.path.startswith("/Report/"):
            raise PAUJSSelectionError(
                "report_url_invalid",
                "Report URL is not an official Pennsylvania UJS report route",
                details={"url": source_url},
            )
        response = self._request(
            "GET",
            source_url,
            headers={"Referer": CASE_SEARCH_URL},
        )
        media_type = (
            str(response.headers.get("Content-Type", ""))
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        content = bytes(response.content)
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise PAUJSSourceChangedError(
                "report_response_invalid",
                "Pennsylvania UJS report route did not return a PDF",
                details={
                    "content_type": media_type,
                    "magic_hex": content[:8].hex(),
                    "url": source_url,
                },
            )
        return PAUJSReport(
            content=content,
            source_url=source_url,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
        )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    requested_limit = getattr(args, "limit", None)
    try:
        parameters = native_selection(args)
    except PAUJSError:
        parameters = {
            key: value
            for key, value in vars(args).items()
            if key
            not in {
                "json_out",
                "max_attempts",
                "minimum_interval",
                "output",
                "timeout",
            }
            and not isinstance(value, Path)
        }
        if hasattr(args, "destination"):
            parameters["destination"] = str(args.destination)
    if args.command == "report":
        parameters = {
            **parameters,
            "report_kind": args.kind,
            "destination": str(args.destination),
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Pennsylvania",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
        ),
    )


def _make_client(args: argparse.Namespace) -> PAUJSClient:
    return PAUJSClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _error_result(
    query: PublicRecordsQuery,
    error: PAUJSError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
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
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    page: PAUJSSearchPage,
    *,
    selection: Mapping[str, str],
    limit: int | None,
) -> PublicRecordsResult:
    records = normalize_records(
        page,
        selection=selection,
        limit=limit,
    )
    warnings = list(SOURCE_WARNINGS)
    if limit is not None and len(records) < page.source_unique_case_count:
        warnings.append(
            f"Caller limit returned {len(records)} of "
            f"{page.source_unique_case_count} unique source cases."
        )
    if page.threshold_systems:
        systems = ", ".join(page.threshold_systems)
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="source_result_threshold_reached",
                    message=(
                        "Pennsylvania UJS returned at least "
                        f"{SOURCE_RESULT_THRESHOLD_PER_SYSTEM} unique cases "
                        f"for: {systems}; the portal provides no next page"
                    ),
                    category="source_ceiling",
                    retryable=False,
                    details={
                        "threshold_per_court_system": (
                            SOURCE_RESULT_THRESHOLD_PER_SYSTEM
                        ),
                        "court_systems": list(page.threshold_systems),
                        "unique_cases_by_court_system": dict(
                            page.unique_cases_by_system
                        ),
                        "native_pagination": "none",
                    },
                )
            ],
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=warnings,
    )


def _execute_command(
    args: argparse.Namespace,
    client: PAUJSClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command in {
        "case",
        "person",
        "organization",
        "filed",
        "appellate",
    }:
        selection = native_selection(args)
        page = client.search(selection)
        return _search_result(
            query,
            page,
            selection=selection,
            limit=getattr(args, "limit", None),
        )

    if args.command == "report":
        selection = native_selection(args)
        page = client.search(selection)
        records = normalize_records(page, selection=selection)
        normalized_docket = args.docket_number.casefold()
        case_record = next(
            (
                record
                for record in records
                if record["raw_case_number"].casefold() == normalized_docket
            ),
            None,
        )
        if case_record is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        report_url = case_record["report_urls"].get(args.kind)
        if report_url is None:
            raise PAUJSSelectionError(
                "report_kind_unavailable",
                f"{args.kind} is not available for {args.docket_number}",
                details={
                    "docket_number": args.docket_number,
                    "requested_kind": args.kind,
                    "available_kinds": sorted(case_record["report_urls"]),
                },
            )
        report = client.fetch_report(report_url)
        destination = Path(args.destination)
        if destination.exists() and not args.overwrite:
            raise PAUJSSelectionError(
                "destination_exists",
                f"destination exists; pass --overwrite: {destination}",
                details={"destination": str(destination)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(report.content)
        report_record = {
            "record_kind": args.kind,
            "source_id": SOURCE_ID,
            "court": case_record["court"],
            "raw_case_number": case_record["raw_case_number"],
            "canonical_ref": canonical_court_ref(
                SOURCE_ID,
                case_record["court"]["court_id"],
                case_record["raw_case_number"],
                record_kind=args.kind,
            ),
            "report_kind": args.kind,
            "source_url": report.source_url,
            "artifact_path": str(destination),
            "media_type": report.media_type,
            "byte_length": len(report.content),
            "sha256": report.sha256,
            "certified_record": False,
            "access_state": "public",
            "case_index_record": case_record,
        }
        return PublicRecordsResult.success(
            query,
            [report_record],
            raw_artifact_refs=[str(destination)],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "probe":
        form = client.bootstrap()
        record = {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "source_url": form.source_url,
            "search_action_url": form.action_url,
            "search_method": "POST",
            "antiforgery_token_present": bool(form.csrf_token),
            "search_modes": list(form.search_modes),
            "form_fields": list(form.form_fields),
            "filed_date_max_span_days": form.filed_date_max_span_days,
            "native_pagination": "none",
            "observed_result_threshold_per_court_system": (
                SOURCE_RESULT_THRESHOLD_PER_SYSTEM
            ),
            "schema_fingerprint": form.schema_fingerprint,
            "complementary_routes": [
                {
                    "role": "bulk_case_metadata_request",
                    "url": OFFICIAL_RECORDS_URL,
                },
                {
                    "role": "official_appellate_opinions_and_postings",
                    "url": OFFICIAL_OPINIONS_URL,
                },
                {
                    "role": "underlying_filing_and_certified_copy_fulfillment",
                    "route": "applicable county clerk or prothonotary",
                },
            ],
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "sentinel":
        sentinel_records: list[dict[str, Any]] = []
        for docket_number, expected_system in (
            (COMMON_PLEAS_SENTINEL, "Common Pleas"),
            (APPELLATE_SENTINEL, "Appellate"),
        ):
            selection = {
                "SearchBy": "DocketNumber",
                "DocketNumber": docket_number,
            }
            page = client.search(selection)
            records = normalize_records(page, selection=selection)
            record = next(
                (
                    item
                    for item in records
                    if item["raw_case_number"].casefold()
                    == docket_number.casefold()
                ),
                None,
            )
            if record is None:
                raise PAUJSSourceChangedError(
                    "sentinel_missing",
                    f"Pennsylvania UJS sentinel is no longer returned: "
                    f"{docket_number}",
                    details={"docket_number": docket_number},
                )
            if record["court"]["court_system"] != expected_system:
                raise PAUJSSourceChangedError(
                    "sentinel_court_system_changed",
                    f"Pennsylvania UJS sentinel court system changed: "
                    f"{docket_number}",
                    details={
                        "docket_number": docket_number,
                        "expected": expected_system,
                        "observed": record["court"]["court_system"],
                    },
                )
            if not record.get("docket_sheet_url"):
                raise PAUJSSourceChangedError(
                    "sentinel_report_missing",
                    f"Pennsylvania UJS sentinel lacks a docket-sheet link: "
                    f"{docket_number}",
                    details={"docket_number": docket_number},
                )
            record["sentinel"] = True
            sentinel_records.append(record)
        return PublicRecordsResult.success(
            query,
            sentinel_records,
            warnings=SOURCE_WARNINGS,
        )

    raise PAUJSSelectionError(
        "unsupported_command",
        f"unsupported Pennsylvania UJS command: {args.command}",
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: PAUJSClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Pennsylvania UJS operation."""

    query = build_query(args)
    if access_decision is not None and not access_decision.get(
        "allowed", False
    ):
        result = _decision_failure(query, access_decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except PAUJSError as error:
        result = _error_result(query, error)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="report_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
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
    finally:
        if owns_client:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Pennsylvania UJS {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Pennsylvania UJS {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        print(
            f"  {record.get('raw_case_number') or '?'} | "
            f"{record.get('court', {}).get('court_system') or '?'} | "
            f"{record.get('caption') or record.get('report_kind') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def _add_case_filters(
    parser: argparse.ArgumentParser,
    *,
    include_category: bool,
) -> None:
    parser.add_argument("--county")
    parser.add_argument("--filed-after", help="ISO filing-date start")
    parser.add_argument("--filed-before", help="ISO filing-date end")
    parser.add_argument("--docket-type")
    if include_category:
        parser.add_argument("--case-category")
    parser.add_argument("--case-status")
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-side result slice after the source response",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Pennsylvania UJS Public Web Docket Sheets",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    case = subparsers.add_parser(
        "case",
        help="Search one exact trial or appellate docket number",
    )
    case.add_argument("docket_number")
    _add_runtime_and_output(case)

    person = subparsers.add_parser(
        "person",
        help="Search by participant last name and source-native facets",
    )
    person.add_argument("last_name")
    person.add_argument("--first-name")
    person.add_argument("--date-of-birth", help="ISO date of birth")
    _add_case_filters(person, include_category=False)
    _add_runtime_and_output(person)

    organization = subparsers.add_parser(
        "organization",
        help="Search by organization name and source-native facets",
    )
    organization.add_argument("organization_name")
    _add_case_filters(organization, include_category=True)
    _add_runtime_and_output(organization)

    filed = subparsers.add_parser(
        "filed",
        help="Search a source-native filing-date span of at most 180 days",
    )
    filed.add_argument("filed_after", help="ISO filing-date start")
    filed.add_argument("filed_before", help="ISO filing-date end")
    filed.add_argument("--county")
    filed.add_argument("--docket-type")
    filed.add_argument("--case-status")
    filed.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-side result slice after the source response",
    )
    _add_runtime_and_output(filed)

    appellate = subparsers.add_parser(
        "appellate",
        help="Search an appellate court within a filing-date partition",
    )
    appellate.add_argument(
        "--court",
        choices=("Supreme", "Superior", "Commonwealth"),
        required=True,
    )
    appellate.add_argument("--filed-after", required=True)
    appellate.add_argument("--filed-before", required=True)
    appellate.add_argument("--party-last")
    appellate.add_argument("--party-first")
    appellate.add_argument("--organization")
    appellate.add_argument(
        "--district",
        choices=("Eastern", "Harrisburg", "Middle", "Western"),
    )
    appellate.add_argument("--docket-type")
    appellate.add_argument(
        "--case-status",
        choices=("Active", "Decided/Active", "Closed"),
    )
    appellate.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-side result slice after the source response",
    )
    _add_runtime_and_output(appellate)

    report = subparsers.add_parser(
        "report",
        help="Download an official docket-sheet or Court Summary PDF",
    )
    report.add_argument("docket_number")
    report.add_argument("destination", type=Path)
    report.add_argument(
        "--kind",
        choices=("docket_sheet", "court_summary"),
        default="docket_sheet",
    )
    report.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(report)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the anonymous form and publish its source-native bounds",
    )
    _add_runtime_and_output(probe)

    sentinel = subparsers.add_parser(
        "sentinel",
        help="Verify known Common Pleas and appellate docket/report rows",
    )
    _add_runtime_and_output(sentinel)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
