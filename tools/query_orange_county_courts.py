#!/usr/bin/env python3
"""Query the Orange County, Florida public court hearing calendar.

The official my eClerk calendar exposes current and future hearing dates,
times, locations, captions, judges, and cancellation status through a
same-session HTML form. It does not expose past hearings or case-detail links.

Examples:
    uv run python tools/query_orange_county_courts.py search \
        --case-number 2020-CT-001540-A-O --json
    uv run python tools/query_orange_county_courts.py search \
        --date 2026-07-28 --limit 100 --output hearings.json
    uv run python tools/query_orange_county_courts.py search \
        --first-name Justin --last-name Douglas
    uv run python tools/query_orange_county_courts.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
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
    from tools.public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
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
    from public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-fl-orange-county-hearing-calendar"
COUNTY_GEOID = "12095"
STATE_CODE = "FL"
COURT_ID = "fl-ninth-judicial-circuit-orange-county"
COURT_NAME = "Orange County Courts, Ninth Judicial Circuit"
BASE_URL = "https://myeclerk.myorangeclerk.com"
CALENDAR_URL = f"{BASE_URL}/Court/Index"
EXPECTED_COLUMNS = (
    "Case Number",
    "Hearing Date",
    "Time Slot",
    "Location",
    "Name",
    "Judge",
    "Status",
)
SOURCE_WARNINGS = (
    "The calendar covers current and future hearing dates and locations; "
    "past hearings are not returned.",
    "Court dates and locations may change, and cancellation state is "
    "preserved from the source Status field.",
    "The calendar omits juvenile cases and does not expose case-detail links.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Orange County Clerk of Courts Hearing Calendar",
    source_role="county_circuit_current_future_hearing_calendar",
    base_url=CALENDAR_URL,
    dataset_id="myeclerk-court-index",
    metadata={
        "authority": "Orange County Clerk of Courts",
        "coverage": "Orange County Circuit and County Court hearings",
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "authentication": "none",
        "platform_family": "orange_county_myeclerk_mvc",
    },
)


@dataclass(frozen=True)
class OrangeHearingRow:
    """One source-native row from the hearing calendar table."""

    case_number: str
    hearing_date: str
    time_slot: str
    location: str | None
    caption: str
    judge: str
    status: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "case_number": self.case_number,
            "hearing_date": self.hearing_date,
            "time_slot": self.time_slot,
            "location": self.location,
            "caption": self.caption,
            "judge": self.judge,
            "status": self.status,
        }


@dataclass(frozen=True)
class OrangeCalendarPage:
    """One parsed GET or POST response from the calendar route."""

    request_verification_token: str
    form_action: str
    form_method: str
    form_values: Mapping[str, str]
    columns: tuple[str, ...]
    rows: tuple[OrangeHearingRow, ...]
    total_count: int | None
    alerts: tuple[str, ...]
    schema_fingerprint: str
    request_parameters: Mapping[str, str] | None = None


class OrangeCourtSelectionError(ValueError):
    """A caller selector cannot be represented by the official form."""

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


class OrangeCourtQueryError(ValueError):
    """The official form rejected a submitted search."""

    def __init__(self, alerts: Sequence[str]) -> None:
        normalized = tuple(value for value in alerts if value)
        message = "; ".join(normalized) or "Orange County calendar rejected the query"
        super().__init__(message)
        self.alerts = normalized


class _CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.form_action: str | None = None
        self.form_method: str | None = None
        self.form_values: dict[str, str] = {}
        self._in_calendar_form = False
        self._in_hearings_table = False
        self._current_row: list[str] | None = None
        self._current_cell: str | None = None
        self._cell_parts: list[str] = []
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self._alert_div_depth = 0
        self._alert_parts: list[str] = []
        self.alerts: list[str] = []
        self._span_depth = 0
        self._span_parts: list[str] = []
        self.spans: list[str] = []

    @staticmethod
    def _attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {
            key.lower(): value or ""
            for key, value in attrs
            if isinstance(key, str)
        }

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        attributes = self._attributes(attrs)

        if tag == "form":
            action = attributes.get("action", "")
            if urlparse(urljoin(CALENDAR_URL, action)).path.lower() == "/court/index":
                self._in_calendar_form = True
                self.form_action = action
                self.form_method = attributes.get("method", "get").lower()

        if tag == "input" and self._in_calendar_form:
            name = attributes.get("name")
            if name:
                self.form_values[name] = attributes.get("value", "")

        if tag == "table" and attributes.get("id", "").lower() == "hearings":
            self._in_hearings_table = True
        elif self._in_hearings_table and tag == "tr":
            self._current_row = []
        elif self._in_hearings_table and tag in {"th", "td"}:
            self._current_cell = tag
            self._cell_parts = []

        if self._alert_div_depth:
            if tag == "div":
                self._alert_div_depth += 1
        elif tag == "div" and attributes.get("role", "").lower() == "alert":
            self._alert_div_depth = 1
            self._alert_parts = []

        if tag == "span":
            if not self._span_depth:
                self._span_parts = []
            self._span_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "form" and self._in_calendar_form:
            self._in_calendar_form = False

        if self._in_hearings_table and tag in {"th", "td"}:
            text = _clean_text(" ".join(self._cell_parts)) or ""
            if self._current_cell == "th":
                self.headers.append(text)
            elif self._current_row is not None:
                self._current_row.append(text)
            self._current_cell = None
            self._cell_parts = []
        elif self._in_hearings_table and tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
        elif self._in_hearings_table and tag == "table":
            self._in_hearings_table = False

        if self._alert_div_depth and tag == "div":
            self._alert_div_depth -= 1
            if not self._alert_div_depth:
                alert = _clean_text(" ".join(self._alert_parts))
                if alert:
                    self.alerts.append(alert)
                self._alert_parts = []

        if self._span_depth and tag == "span":
            self._span_depth -= 1
            if not self._span_depth:
                span = _clean_text(" ".join(self._span_parts))
                if span:
                    self.spans.append(span)
                self._span_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._cell_parts.append(data)
        if self._alert_div_depth:
            self._alert_parts.append(data)
        if self._span_depth:
            self._span_parts.append(data)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _clean_text(value)
    if normalized is None:
        raise ValueError(f"Orange County calendar row lacks {field_name}")
    return normalized


def _source_schema_error(message: str, *, details: Mapping[str, Any] | None = None):
    return SourceSchemaError(message, url=CALENDAR_URL, details=details)


def parse_calendar_html(html: str) -> OrangeCalendarPage:
    """Parse and validate one official calendar response deterministically."""

    parser = _CalendarParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as error:
        raise _source_schema_error(
            "Orange County calendar HTML could not be parsed",
            details={"error": str(error)},
        ) from error

    token = _clean_text(parser.form_values.get("__RequestVerificationToken"))
    if token is None:
        raise _source_schema_error(
            "Orange County calendar form lacks an anti-forgery token"
        )
    if parser.form_action is None or parser.form_method != "post":
        raise _source_schema_error(
            "Orange County calendar form action or method changed",
            details={
                "form_action": parser.form_action,
                "form_method": parser.form_method,
            },
        )

    columns = tuple(parser.headers)
    if parser.alerts and not columns:
        return OrangeCalendarPage(
            request_verification_token=token,
            form_action=parser.form_action,
            form_method=parser.form_method,
            form_values=dict(parser.form_values),
            columns=(),
            rows=(),
            total_count=None,
            alerts=tuple(parser.alerts),
            schema_fingerprint=schema_fingerprint(
                inferred_schema([{"alert": value} for value in parser.alerts])
            ),
        )
    if columns != EXPECTED_COLUMNS:
        raise _source_schema_error(
            "Orange County calendar table columns changed",
            details={
                "expected_columns": list(EXPECTED_COLUMNS),
                "observed_columns": list(columns),
            },
        )

    rows: list[OrangeHearingRow] = []
    for index, values in enumerate(parser.rows):
        if len(values) != len(EXPECTED_COLUMNS):
            raise _source_schema_error(
                "Orange County calendar row width changed",
                details={"row_index": index, "cell_count": len(values)},
            )
        rows.append(
            OrangeHearingRow(
                case_number=_required_text(values[0], "case number"),
                hearing_date=_required_text(values[1], "hearing date"),
                time_slot=_required_text(values[2], "time slot"),
                location=_clean_text(values[3]),
                caption=_required_text(values[4], "caption"),
                judge=_required_text(values[5], "judge"),
                status=_clean_text(values[6]),
            )
        )

    total_match = None
    for span in parser.spans:
        total_match = re.fullmatch(
            (
                r"(?:(?P<count_before>\d[\d,]*)\s+"
                r"(?:Total\s+Hearings|Hearings?)(?:\s+.+)?"
                r"|Total\s+Hearings\s*:\s*(?P<count_after>\d[\d,]*))"
            ),
            span,
            flags=re.IGNORECASE,
        )
        if total_match is not None:
            break
    if total_match is None:
        raise _source_schema_error(
            "Orange County calendar response lacks a total-hearings count"
        )
    total_text = (
        total_match.group("count_before")
        or total_match.group("count_after")
    )
    total_count = int(total_text.replace(",", ""))
    if total_count != len(rows):
        raise _source_schema_error(
            "Orange County calendar row count does not match its total",
            details={"reported_total": total_count, "parsed_rows": len(rows)},
        )

    schema = schema_fingerprint(
        inferred_schema([row.to_dict() for row in rows])
        if rows
        else inferred_schema(
            [
                {
                    "case_number": "",
                    "hearing_date": "",
                    "time_slot": "",
                    "location": "",
                    "caption": "",
                    "judge": "",
                    "status": None,
                }
            ]
        )
    )
    return OrangeCalendarPage(
        request_verification_token=token,
        form_action=parser.form_action,
        form_method=parser.form_method,
        form_values=dict(parser.form_values),
        columns=columns,
        rows=tuple(rows),
        total_count=total_count,
        alerts=tuple(parser.alerts),
        schema_fingerprint=schema,
    )


def _checked_response(response: Any, *, url: str) -> str:
    status_code = int(getattr(response, "status_code", 0))
    text = getattr(response, "text", "")
    text = text if isinstance(text, str) else str(text)
    if status_code == 429:
        raise RateLimitedHTTPError(status_code, url=url, response_text=text)
    if status_code in {401, 403}:
        raise RestrictedHTTPError(status_code, url=url, response_text=text)
    if status_code == 451:
        raise TermsBlockedHTTPError(status_code, url=url, response_text=text)
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(status_code, url=url, response_text=text)
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(status_code, url=url, response_text=text)

    headers = getattr(response, "headers", {})
    content_type = ""
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).lower() == "content-type":
                content_type = str(value).lower()
                break
    if content_type and "html" not in content_type:
        raise _source_schema_error(
            "Orange County calendar returned a non-HTML response",
            details={"content_type": content_type},
        )
    return text


class OrangeCountyCourtsClient:
    """Same-session HTTP client for the public hearing-calendar form."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self._owns_session = session is None
        self.headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Ithildin public-record source adapter",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def bootstrap(self) -> OrangeCalendarPage:
        try:
            response = self.session.get(
                CALENDAR_URL,
                headers=self.headers,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TransportError(
                "Orange County calendar GET failed",
                url=CALENDAR_URL,
                details={"error": str(error)},
            ) from error
        return parse_calendar_html(
            _checked_response(response, url=CALENDAR_URL)
        )

    def _submit(
        self,
        bootstrap: OrangeCalendarPage,
        *,
        hearing_date: str | None = None,
        case_number: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        judge: str | None = None,
    ) -> OrangeCalendarPage:
        parameters = {
            "hearDate": hearing_date or "",
            "caseNumber": case_number or "",
            "firstName": first_name or "",
            "lastName": last_name or "",
            "judge": judge or "",
        }
        payload = {
            "__RequestVerificationToken": (
                bootstrap.request_verification_token
            ),
            **parameters,
        }
        target_url = urljoin(CALENDAR_URL, bootstrap.form_action)
        try:
            response = self.session.post(
                target_url,
                data=payload,
                headers={**self.headers, "Referer": CALENDAR_URL},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TransportError(
                "Orange County calendar POST failed",
                url=target_url,
                details={"error": str(error)},
            ) from error
        page = parse_calendar_html(
            _checked_response(response, url=target_url)
        )
        if page.alerts:
            raise OrangeCourtQueryError(page.alerts)
        return OrangeCalendarPage(
            request_verification_token=page.request_verification_token,
            form_action=page.form_action,
            form_method=page.form_method,
            form_values=page.form_values,
            columns=page.columns,
            rows=page.rows,
            total_count=page.total_count,
            alerts=page.alerts,
            schema_fingerprint=page.schema_fingerprint,
            request_parameters=parameters,
        )

    def search(
        self,
        *,
        hearing_date: str | None = None,
        case_number: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        judge: str | None = None,
    ) -> OrangeCalendarPage:
        bootstrap = self.bootstrap()
        return self._submit(
            bootstrap,
            hearing_date=hearing_date,
            case_number=case_number,
            first_name=first_name,
            last_name=last_name,
            judge=judge,
        )

    def probe(self) -> OrangeCalendarPage:
        bootstrap = self.bootstrap()
        probe_date = _clean_text(bootstrap.form_values.get("hearDate"))
        if probe_date is None:
            raise _source_schema_error(
                "Orange County calendar form lacks its default hearing date"
            )
        try:
            date.fromisoformat(probe_date)
        except ValueError as error:
            raise _source_schema_error(
                "Orange County calendar default hearing date changed format",
                details={"value": probe_date},
            ) from error
        return self._submit(bootstrap, hearing_date=probe_date)


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "orange-county-hearing-calendar",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "county_and_circuit",
        "official_url": CALENDAR_URL,
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_type": "current_future_hearing_calendar",
        "fields": [
            "case_number",
            "hearing_date",
            "time_slot",
            "location",
            "caption",
            "judge",
            "status",
        ],
        "past_hearings_available": False,
        "case_detail_link_available": False,
    }


def _event_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"Orange County hearing has unparseable date {value!r}"
        ) from error


def _event_time(value: str) -> str:
    try:
        return datetime.strptime(value.upper(), "%I:%M %p").time().isoformat()
    except ValueError as error:
        raise ValueError(
            f"Orange County hearing has unparseable time {value!r}"
        ) from error


def _identity_text(value: str | None) -> str:
    return (_clean_text(value) or "").casefold()


def _hearing_entry(row: OrangeHearingRow) -> dict[str, Any]:
    event_date = _event_date(row.hearing_date)
    event_time = _event_time(row.time_slot)
    identity_basis = {
        "case_number": _identity_text(row.case_number).upper(),
        "event_date": event_date,
        "event_time": event_time,
        "location": _identity_text(row.location),
        "judge": _identity_text(row.judge),
        "status": _identity_text(row.status),
    }
    digest = hashlib.sha256(
        canonical_json(identity_basis).encode("utf-8")
    ).hexdigest()
    return {
        "native_entry_id": f"calendar-hearing:{digest}",
        "identity_kind": "source_fields_sha256",
        "identity_basis": identity_basis,
        "event_type": "hearing",
        "event_code": None,
        "raw_text": "Court hearing",
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "source_event_date_raw": row.hearing_date,
        "source_event_time_raw": row.time_slot,
        "location": row.location,
        "judge": row.judge,
        "status": row.status,
        "native_status": row.status,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def normalize_cases(
    page: OrangeCalendarPage,
) -> list[dict[str, Any]]:
    """Group native hearing rows into deterministic case/docket records."""

    grouped: dict[str, list[OrangeHearingRow]] = {}
    case_numbers: dict[str, set[str]] = {}
    for row in page.rows:
        case_number = _required_text(row.case_number, "case number")
        key = _identity_text(case_number)
        grouped.setdefault(key, []).append(row)
        case_numbers.setdefault(key, set()).add(case_number)

    records: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = grouped[key]
        raw_case_number = sorted(
            case_numbers[key],
            key=lambda value: (value.casefold(), value),
        )[0]
        captions = sorted(
            {row.caption for row in rows},
            key=lambda value: (value.casefold(), value),
        )
        entries_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            entry = _hearing_entry(row)
            entries_by_id[entry["native_entry_id"]] = entry
        entries = sorted(
            entries_by_id.values(),
            key=lambda entry: (
                entry["event_date"],
                entry["event_time"],
                _identity_text(entry["location"]),
                _identity_text(entry["judge"]),
                _identity_text(entry["status"]),
            ),
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    raw_case_number,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "case",
                "court": _court_payload(),
                "raw_case_number": raw_case_number,
                "display_case_number": raw_case_number,
                "source_internal_id": None,
                "caption": captions[0],
                "caption_variants": captions,
                "case_type": None,
                "filing_date": None,
                "status": None,
                "access_state": "public",
                "certified_record": False,
                "source_url": CALENDAR_URL,
                "parties": [],
                "docket_entries": entries,
                "documents": [],
                "source_scope": _source_scope(),
                "search_metadata": {
                    "source_total_hearings": page.total_count,
                    "source_total_cases": len(grouped),
                    "request_parameters": dict(
                        page.request_parameters or {}
                    ),
                },
                "schema_fingerprint": page.schema_fingerprint,
                "raw": {
                    "hearing_rows": [
                        row.to_dict()
                        for row in sorted(
                            rows,
                            key=lambda value: (
                                _event_date(value.hearing_date),
                                _event_time(value.time_slot),
                                _identity_text(value.location),
                                _identity_text(value.judge),
                                _identity_text(value.status),
                            ),
                        )
                    ]
                },
            }
        )
    return records


def _search_selection(args: argparse.Namespace) -> dict[str, str | None]:
    hearing_date = _clean_text(getattr(args, "hearing_date", None))
    case_number = _clean_text(getattr(args, "case_number", None))
    first_name = _clean_text(getattr(args, "first_name", None))
    last_name = _clean_text(getattr(args, "last_name", None))
    judge = _clean_text(getattr(args, "judge", None))

    if hearing_date is not None:
        try:
            date.fromisoformat(hearing_date)
        except ValueError as error:
            raise OrangeCourtSelectionError(
                "invalid_hearing_date",
                "--date must be an ISO calendar date",
                details={"value": hearing_date},
            ) from error
    if bool(first_name) != bool(last_name):
        raise OrangeCourtSelectionError(
            "incomplete_name",
            "name search requires both --first-name and --last-name",
        )
    if not any((hearing_date, case_number, first_name, judge)):
        raise OrangeCourtSelectionError(
            "search_selector_required",
            "search requires a date, case number, full name, or judge",
        )
    return {
        "hearing_date": hearing_date,
        "case_number": case_number,
        "first_name": first_name,
        "last_name": last_name,
        "judge": judge,
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            "hearing_date": getattr(args, "hearing_date", None),
            "case_number": getattr(args, "case_number", None),
            "first_name": getattr(args, "first_name", None),
            "last_name": getattr(args, "last_name", None),
            "judge": getattr(args, "judge", None),
            "offset": getattr(args, "offset", 0),
        }
        requested_limit = args.limit
        cursor = f"orange-calendar:offset:{args.offset}"
    elif args.command == "probe":
        parameters = {"selector": "source_default_date"}
        requested_limit = 1
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Orange County, Florida",
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


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _access_failure(
    query: PublicRecordsQuery,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        return PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "acquisition_route_unavailable"
                    ),
                    message=str(decision.get("reason") or error),
                    category="access",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="acquisition_route_unavailable",
                message=str(error),
                category="access_control",
                retryable=False,
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
                details=decision,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: OrangeCourtSelectionError | OrangeCourtQueryError,
) -> PublicRecordsResult:
    if isinstance(error, OrangeCourtSelectionError):
        code = error.code
        details = error.details
    else:
        code = "source_validation_error"
        details = {"alerts": list(error.alerts)}
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    page: OrangeCalendarPage,
    *,
    limit: int,
    offset: int,
) -> PublicRecordsResult:
    records = normalize_cases(page)
    selected = records[offset : offset + limit]
    next_cursor = (
        f"orange-calendar:offset:{offset + limit}"
        if offset + limit < len(records)
        else None
    )
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _probe_record(page: OrangeCalendarPage) -> dict[str, Any]:
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{COURT_ID}/probe/hearing-calendar"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "probe",
        "source_url": CALENDAR_URL,
        "court": _court_payload(),
        "source_scope": _source_scope(),
        "request_parameters": dict(page.request_parameters or {}),
        "source_total_hearings": page.total_count,
        "table_columns": list(page.columns),
        "parsed_row_count": len(page.rows),
        "schema_fingerprint": page.schema_fingerprint,
    }


def _execute_command(
    args: argparse.Namespace,
    client: OrangeCountyCourtsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "search":
        selectors = _search_selection(args)
        page = client.search(**selectors)
        return _search_result(
            query,
            page,
            limit=args.limit,
            offset=args.offset,
        )
    if args.command == "probe":
        page = client.probe()
        return PublicRecordsResult.success(
            query,
            [_probe_record(page)],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Orange County court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: OrangeCountyCourtsClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one Orange County hearing-calendar operation."""

    query = build_query(args)
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (AcquisitionUnavailableError, CatalogError, OSError, ValueError) as error:
        result = _access_failure(query, error)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or OrangeCountyCourtsClient(timeout=args.timeout)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except (OrangeCourtSelectionError, OrangeCourtQueryError) as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
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
        summary=f"Orange County courts {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Orange County courts {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{len(record.get('docket_entries') or [])} hearings | "
                f"{record.get('caption') or '?'}"
            )
        else:
            print(
                f"  probe | {record.get('source_total_hearings')} hearings "
                f"on {record.get('request_parameters', {}).get('hearDate')}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_catalog_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official Orange County, Florida current/future "
            "court hearing calendar"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search current/future hearings by official form fields",
    )
    search.add_argument(
        "--date",
        dest="hearing_date",
        help="Hearing date as YYYY-MM-DD",
    )
    search.add_argument("--case-number")
    search.add_argument("--first-name")
    search.add_argument("--last-name")
    search.add_argument("--judge")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--offset", type=int, default=0)
    _add_catalog_and_output(search)

    probe = sub.add_parser(
        "probe",
        help="Verify the live form and hearing-table contract",
    )
    _add_catalog_and_output(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "offset", 0) < 0:
        parser.error("--offset must not be negative")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
