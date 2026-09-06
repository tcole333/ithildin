#!/usr/bin/env python3
"""Query official District of Columbia court-calendar sources.

The D.C. Courts site publishes several useful calendar representations:

* Today's Superior Court Cases, as a filterable and natively paged HTML view;
* the same current-day data as a full JSON snapshot;
* the Criminal Attorney Case Calendar as a separate filterable HTML view;
* Tax Division calendar PDFs; and
* a year-filterable Court of Appeals calendar-artifact API.

These are hearing-discovery and calendar-artifact sources.  They complement,
but do not replace, the case histories and documents in Portal and eAccess.

Examples:
    uv run python tools/query_dc_superior_calendar.py sources --json
    uv run python tools/query_dc_superior_calendar.py filters --calendar today
    uv run python tools/query_dc_superior_calendar.py search \
        --case-number 2026-LTB-005132 --output /tmp/dc-today.json
    uv run python tools/query_dc_superior_calendar.py criminal \
        --case-number "2026 CTF 004287" --output /tmp/dc-criminal.json
    uv run python tools/query_dc_superior_calendar.py snapshot --limit 250
    uv run python tools/query_dc_superior_calendar.py artifacts --family tax
    uv run python tools/query_dc_superior_calendar.py appeals --year 2024
    uv run python tools/query_dc_superior_calendar.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_module
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

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
    )
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
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
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


STATE_CODE = "DC"
STATE_GEOID = "11"
COURT_ID = "us-dc-superior-court"
DC_TIMEZONE_NAME = "America/New_York"
DC_TIMEZONE = ZoneInfo(DC_TIMEZONE_NAME)

BASE_URL = "https://www.dccourts.gov"
CALENDAR_FAMILY_URL = (
    f"{BASE_URL}/superior-court/superior-court-case-calendars"
)
TODAY_URL = f"{CALENDAR_FAMILY_URL}/todays-superior-court-cases"
TODAY_REST_URL = f"{BASE_URL}/app-rest-api/todays-superior-court-cases"
CRIMINAL_URL = (
    f"{CALENDAR_FAMILY_URL}/criminal-attorney-case-calendar"
)
TAX_URL = (
    f"{BASE_URL}/superior-court/superior-court-divisions/"
    "tax-division/tax-case-calendar"
)
APPEALS_URL = (
    f"{BASE_URL}/court-of-appeals/court-of-appeals-case-calendars"
)
APPEALS_REST_URL = f"{BASE_URL}/app-rest-api/court-of-appeals-calendar"

CRIMINAL_ATTORNEY_PDF_URL = (
    f"{BASE_URL}/livexml/Attorney_Calendar_Internet.pdf"
)
CRIMINAL_COURT_PDF_URL = (
    f"{BASE_URL}/livexml/CRM_Court_Calendar_Internet.pdf"
)
APPEALS_WEEKLY_PANEL_URL = (
    f"{BASE_URL}/sites/default/files/COA-Panel-Weekly-PDFs/"
    "panel_calnotice.pdf"
)
PORTAL_URL = "https://portal-dc.tylertech.cloud/Portal"
EACCESS_URL = "https://eaccess.dccourts.gov/eaccess/home.page.3"

TODAY_SOURCE_ID = "us-dc-superior-court-today-calendar"
CRIMINAL_SOURCE_ID = "us-dc-superior-court-criminal-calendar"
TAX_SOURCE_ID = "us-dc-superior-court-tax-calendars"
APPEALS_SOURCE_ID = "us-dc-court-of-appeals-calendars"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3

# The gateway accepts an ordinary browser request shape and returned 403 to a
# short custom user agent during source verification.  This is transport
# configuration, not an access classification.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

TODAY_HEADERS = (
    "Party",
    "Case Number",
    "Division",
    "Courtroom",
    "Judge",
    "Time",
    "Case Type",
)
CRIMINAL_HEADERS = (
    "Defendant",
    "Event",
    "Charge",
    "Time",
    "Attorney",
    "Case Number",
    "Courtroom",
    "Judge",
)
TODAY_TEXT_FILTERS = ("party", "case_no")
TODAY_SELECT_FILTERS = ("judges", "courtroom")
CRIMINAL_TEXT_FILTERS = (
    "field_xml_defendant_value",
    "field_xml_timex_value",
    "event",
    "field_xml_charge_value",
    "field_xml_attorney_value",
    "field_xml_case_no_value",
)
CRIMINAL_SELECT_FILTERS = (
    "field_courtroom_link_target_id",
    "field_judge_link_target_id",
)

CURSOR_RE = re.compile(
    r"^dcsc:v1:(?P<kind>today|criminal):"
    r"(?P<fingerprint>[0-9a-f]{16}):page:(?P<page>\d+)$"
)
SNAPSHOT_CURSOR_RE = re.compile(
    r"^dcsc:v1:snapshot:(?P<fingerprint>[0-9a-f]{16}):"
    r"offset:(?P<offset>\d+)$"
)
TOTAL_RE = re.compile(r"\bTotal\s+([\d,]+)\s+items\b", re.I)

SOURCE_WARNINGS = (
    "Calendar rows are source-published hearing occurrences, not complete "
    "docket histories.",
    "The official daily-calendar page says confidential Family Court and "
    "juvenile matters are omitted, and directs Domestic Violence hearing "
    "lookups to the clerk.",
    "Schedules and counts can change; records preserve event and retrieval "
    "freshness separately.",
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="District of Columbia",
    state_code=STATE_CODE,
    locality="Washington",
    metadata={"government_level": "district_local"},
)

TODAY_METADATA = SourceMetadata(
    source_id=TODAY_SOURCE_ID,
    name="D.C. Superior Court Today's Cases",
    source_role="same_day_superior_court_hearing_calendar",
    base_url=TODAY_URL,
    dataset_id="dc-courts-todays-superior-court-cases",
    metadata={
        "authority": "District of Columbia Courts",
        "access": "anonymous_open",
        "representations": {
            "html_search": {
                "url": TODAY_URL,
                "native_page_origin": 0,
                "native_page_size": 10,
                "filters": [
                    *TODAY_TEXT_FILTERS,
                    *TODAY_SELECT_FILTERS,
                    "order",
                    "sort",
                ],
            },
            "rest_snapshot": {
                "url": TODAY_REST_URL,
                "response_shape": "full_current_array",
                "query_parameters_observed": "ignored",
            },
        },
        "complements": [PORTAL_URL, EACCESS_URL],
    },
)

CRIMINAL_METADATA = SourceMetadata(
    source_id=CRIMINAL_SOURCE_ID,
    name="D.C. Superior Court Criminal Attorney Case Calendar",
    source_role="same_day_criminal_case_hearing_calendar",
    base_url=CRIMINAL_URL,
    dataset_id="dc-courts-criminal-attorney-case-calendar",
    metadata={
        "authority": "District of Columbia Courts",
        "access": "anonymous_open",
        "native_page_origin": 0,
        "native_page_size": 10,
        "filters": [
            *CRIMINAL_TEXT_FILTERS,
            *CRIMINAL_SELECT_FILTERS,
            "order",
            "sort",
        ],
        "full_schedule_artifacts": [
            CRIMINAL_ATTORNEY_PDF_URL,
            CRIMINAL_COURT_PDF_URL,
        ],
        "refresh_statement": "updated_at_7_30pm_the_night_before",
        "complements": [EACCESS_URL],
    },
)

TAX_METADATA = SourceMetadata(
    source_id=TAX_SOURCE_ID,
    name="D.C. Superior Court Tax Case Calendars",
    source_role="tax_show_cause_and_mediation_calendar_artifacts",
    base_url=TAX_URL,
    dataset_id="dc-courts-tax-calendar-pdfs",
    metadata={
        "authority": "District of Columbia Courts",
        "access": "anonymous_open",
        "artifact_types": ["tax_show_cause", "tax_multi_door_mediation"],
        "complements": [PORTAL_URL, EACCESS_URL],
    },
)

APPEALS_METADATA = SourceMetadata(
    source_id=APPEALS_SOURCE_ID,
    name="D.C. Court of Appeals Calendars",
    source_role="appellate_regular_summary_and_weekly_panel_calendars",
    base_url=APPEALS_URL,
    dataset_id="dc-courts-appellate-calendar-index",
    metadata={
        "authority": "District of Columbia Courts",
        "access": "anonymous_open",
        "rest_index_url": APPEALS_REST_URL,
        "native_filter": "field_year_court_calendar_value[]",
        "weekly_panel_url": APPEALS_WEEKLY_PANEL_URL,
        "complements": ["us-dc-court-of-appeals-opinions-mojs"],
    },
)

SOURCE_METADATA_BY_ID = {
    TODAY_SOURCE_ID: TODAY_METADATA,
    CRIMINAL_SOURCE_ID: CRIMINAL_METADATA,
    TAX_SOURCE_ID: TAX_METADATA,
    APPEALS_SOURCE_ID: APPEALS_METADATA,
}


class DCCalendarQueryError(ValueError):
    """Structured caller-input error."""

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


@dataclass(frozen=True)
class FetchedText:
    text: str
    source_url: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class FetchedJSON:
    payload: Any
    source_url: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class CalendarPage:
    kind: str
    rows: tuple[Mapping[str, Any], ...]
    filters: Mapping[str, Any]
    native_page: int
    reported_total: int | None
    total_pages: int
    next_page: int | None
    no_results: bool
    page_last_updated: str | None
    schema_fingerprint: str


@dataclass(frozen=True)
class CalendarArtifact:
    family: str
    artifact_type: str
    label: str
    url: str
    page_last_updated: str | None = None
    year: int | None = None
    month: str | None = None


def _clean_text(value: Any) -> str | None:
    text = " ".join(str(value).split())
    return text or None


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return _clean_text(value)
    return None


def _response_date(headers: Mapping[str, Any]) -> str | None:
    value = _header(headers, "date")
    if value is None:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(DC_TIMEZONE).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _source_schema_error(
    message: str,
    *,
    url: str,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=url, details=details)


def _checked_status(response: Any, *, url: str) -> None:
    status_code = int(getattr(response, "status_code", 0))
    text = str(getattr(response, "text", ""))
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


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    value = _header(headers, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class DCCalendarClient:
    """D.C. Courts client with the verified request shape and bounded retries."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.headers = {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/json,"
                "application/pdf;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept: str | None = None,
    ) -> Any:
        response: Any | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            headers = dict(self.headers)
            if accept is not None:
                headers["Accept"] = accept
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=dict(params or {}),
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "D.C. Courts request failed",
                        url=url,
                        details={"error": str(error), "attempts": attempt},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code not in self.retry_policy.retry_statuses
                or attempt >= self.retry_policy.max_attempts
            ):
                break
            self.sleeper(
                self.retry_policy.delay(attempt, _retry_after(response))
            )
        if response is None:
            raise TransportError(
                "D.C. Courts request produced no response",
                url=url,
            )
        _checked_status(response, url=url)
        return response

    def html(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> FetchedText:
        response = self._request(
            url,
            params=params,
            accept="text/html,application/xhtml+xml,*/*;q=0.8",
        )
        headers = dict(getattr(response, "headers", {}) or {})
        content_type = _header(headers, "content-type")
        if content_type and "html" not in content_type.casefold():
            raise _source_schema_error(
                "D.C. Courts calendar page returned non-HTML content",
                url=url,
                details={"content_type": content_type},
            )
        response_url = str(getattr(response, "url", url))
        text = getattr(response, "text", "")
        return FetchedText(
            text=text if isinstance(text, str) else str(text),
            source_url=response_url,
            headers=headers,
        )

    def json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> FetchedJSON:
        response = self._request(
            url,
            params=params,
            accept="application/json,*/*;q=0.8",
        )
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise _source_schema_error(
                "D.C. Courts endpoint returned invalid JSON",
                url=url,
            ) from error
        return FetchedJSON(
            payload=payload,
            source_url=str(getattr(response, "url", url)),
            headers=dict(getattr(response, "headers", {}) or {}),
        )


def _page_last_updated(soup: BeautifulSoup) -> str | None:
    container = soup.select_one(".field-last-update")
    if container is None:
        return None
    match = re.search(
        r"Last\s+Updated\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})",
        container.get_text(" ", strip=True),
        re.I,
    )
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return match.group(1)


def _form_taxonomy(soup: BeautifulSoup, *, kind: str) -> dict[str, Any]:
    expected_text = (
        TODAY_TEXT_FILTERS if kind == "today" else CRIMINAL_TEXT_FILTERS
    )
    expected_select = (
        TODAY_SELECT_FILTERS if kind == "today" else CRIMINAL_SELECT_FILTERS
    )
    text_fields: list[dict[str, Any]] = []
    for name in expected_text:
        element = soup.find("input", attrs={"name": name})
        if element is None:
            raise _source_schema_error(
                f"D.C. {kind} calendar is missing native filter {name}",
                url=TODAY_URL if kind == "today" else CRIMINAL_URL,
            )
        text_fields.append(
            {
                "name": name,
                "label": _clean_text(element.get("placeholder")) or name,
                "maxlength": (
                    int(element["maxlength"])
                    if str(element.get("maxlength", "")).isdigit()
                    else None
                ),
            }
        )
    selects: list[dict[str, Any]] = []
    for name in expected_select:
        element = soup.find("select", attrs={"name": name})
        if element is None:
            raise _source_schema_error(
                f"D.C. {kind} calendar is missing native filter {name}",
                url=TODAY_URL if kind == "today" else CRIMINAL_URL,
            )
        options = [
            {
                "value": str(option.get("value", "")),
                "label": _clean_text(option.get_text(" ", strip=True)) or "",
                "selected": option.has_attr("selected"),
            }
            for option in element.find_all("option")
        ]
        selects.append({"name": name, "options": options})
    sort_fields: dict[str, str] = {}
    for anchor in soup.select("table thead th a[href]"):
        query = parse_qs(urlsplit(str(anchor.get("href"))).query)
        native_order = query.get("order", [None])[0]
        if native_order:
            label = _clean_text(anchor.get_text(" ", strip=True))
            if label:
                sort_fields[label] = native_order
    return {
        "text_fields": text_fields,
        "select_fields": selects,
        "sort_fields": sort_fields,
        "sort_directions": ["asc", "desc"],
        "page_parameter": "page",
        "page_origin": 0,
    }


def _find_calendar_table(
    soup: BeautifulSoup,
    expected_headers: Sequence[str],
) -> Tag | None:
    for table in soup.find_all("table"):
        headers = tuple(
            _clean_text(cell.get_text(" ", strip=True)) or ""
            for cell in table.select("thead th")
        )
        if headers == tuple(expected_headers):
            return table
    return None


def _native_page_from_link(anchor: Tag | None) -> int | None:
    if anchor is None:
        return None
    query = parse_qs(urlsplit(str(anchor.get("href", ""))).query)
    raw = query.get("page", [None])[0]
    return int(raw) if raw is not None and str(raw).isdigit() else None


def parse_calendar_html(
    html: str,
    *,
    kind: str,
    native_page: int = 0,
    source_url: str | None = None,
) -> CalendarPage:
    """Parse one source-native HTML result page without grouping its rows."""

    if kind not in {"today", "criminal"}:
        raise ValueError(f"unknown D.C. calendar kind: {kind}")
    expected_headers = TODAY_HEADERS if kind == "today" else CRIMINAL_HEADERS
    url = source_url or (TODAY_URL if kind == "today" else CRIMINAL_URL)
    soup = BeautifulSoup(str(html), "html.parser")
    taxonomy = _form_taxonomy(soup, kind=kind)
    table = _find_calendar_table(soup, expected_headers)
    empty = soup.select_one(".view-empty .empty-response") is not None
    if table is None and not empty:
        raise _source_schema_error(
            f"D.C. {kind} calendar has neither the expected table nor "
            "its no-results marker",
            url=url,
            details={"expected_headers": list(expected_headers)},
        )
    rows: list[dict[str, Any]] = []
    if table is not None:
        for row_index, table_row in enumerate(table.select("tbody tr")):
            cells = table_row.find_all("td", recursive=False)
            if len(cells) != len(expected_headers):
                raise _source_schema_error(
                    f"D.C. {kind} calendar row width changed",
                    url=url,
                    details={
                        "expected": len(expected_headers),
                        "observed": len(cells),
                        "native_page": native_page,
                        "row_index": row_index,
                    },
                )
            values = {
                header: _clean_text(cell.get_text(" ", strip=True))
                for header, cell in zip(expected_headers, cells, strict=True)
            }
            time_index = expected_headers.index("Time")
            time_element = cells[time_index].find("time")
            event_datetime = (
                _clean_text(time_element.get("datetime"))
                if time_element is not None
                else None
            )
            if event_datetime is None:
                raise _source_schema_error(
                    f"D.C. {kind} calendar row lacks an ISO event datetime",
                    url=url,
                    details={
                        "native_page": native_page,
                        "row_index": row_index,
                    },
                )
            courtroom_index = expected_headers.index("Courtroom")
            courtroom_anchor = cells[courtroom_index].find("a", href=True)
            values["_event_datetime"] = event_datetime
            values["_remote_hearing_url"] = (
                urljoin(url, str(courtroom_anchor["href"]))
                if courtroom_anchor is not None
                else None
            )
            values["_native_row_index"] = row_index
            rows.append(values)
    page_text = soup.get_text(" ", strip=True)
    total_match = TOTAL_RE.search(page_text)
    reported_total = (
        int(total_match.group(1).replace(",", "")) if total_match else None
    )
    next_page = _native_page_from_link(soup.select_one("a[rel='next']"))
    last_page = _native_page_from_link(
        soup.select_one(".pager__item--last a[href]")
    )
    if last_page is not None:
        total_pages = last_page + 1
    elif next_page is not None:
        total_pages = max(native_page + 2, next_page + 1)
    else:
        total_pages = 1 if (rows or empty) else 0
    observed_schema = {
        "kind": kind,
        "headers": list(expected_headers),
        "filters": taxonomy,
        "event_datetime_attribute": "time.datetime",
    }
    return CalendarPage(
        kind=kind,
        rows=tuple(rows),
        filters=taxonomy,
        native_page=native_page,
        reported_total=reported_total,
        total_pages=total_pages,
        next_page=next_page,
        no_results=empty and not rows,
        page_last_updated=_page_last_updated(soup),
        schema_fingerprint=schema_fingerprint(observed_schema),
    )


def parse_today_snapshot(payload: Any) -> tuple[Mapping[str, Any], ...]:
    """Validate the full-array current-day REST representation.

    The live feed can append fully blank objects with the normal row schema.
    Those contain no hearing occurrence and are omitted; partially populated
    rows continue through normalization so missing identity fields fail
    explicitly.
    """

    if not isinstance(payload, list):
        raise _source_schema_error(
            "D.C. today snapshot JSON root is not an array",
            url=TODAY_REST_URL,
            details={"root_type": type(payload).__name__},
        )
    required = {
        "courtroom_link",
        "party",
        "case_no",
        "judge_name",
        "location",
        "webexurl",
        "timex_timestamp",
        "division",
        "case_type",
    }
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise _source_schema_error(
                "D.C. today snapshot contains a non-object row",
                url=TODAY_REST_URL,
                details={"row_index": index},
            )
        missing = sorted(required - set(row))
        if missing:
            raise _source_schema_error(
                "D.C. today snapshot row schema changed",
                url=TODAY_REST_URL,
                details={"row_index": index, "missing": missing},
            )
        if all(_clean_text(row.get(field)) is None for field in required):
            continue
        rows.append(dict(row))
    return tuple(rows)


def _official_pdf_url(raw_url: str, *, page_url: str) -> str:
    url = urljoin(page_url, raw_url)
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname != "www.dccourts.gov"
        or not parts.path.casefold().endswith(".pdf")
    ):
        raise _source_schema_error(
            "D.C. calendar artifact link is not an official PDF URL",
            url=page_url,
            details={"artifact_url": url},
        )
    return url


def parse_artifact_index_html(
    html: str,
    *,
    family: str,
    page_url: str | None = None,
) -> tuple[CalendarArtifact, ...]:
    """Parse the criminal or Tax Division calendar artifact page."""

    if family not in {"criminal", "tax"}:
        raise ValueError(f"unknown artifact family: {family}")
    url = page_url or (CRIMINAL_URL if family == "criminal" else TAX_URL)
    soup = BeautifulSoup(str(html), "html.parser")
    page_updated = _page_last_updated(soup)
    artifacts: list[CalendarArtifact] = []
    for anchor in soup.find_all("a", href=True):
        raw_url = str(anchor["href"])
        if ".pdf" not in raw_url.casefold():
            continue
        label = _clean_text(anchor.get_text(" ", strip=True)) or "Calendar PDF"
        candidate = _official_pdf_url(raw_url, page_url=url)
        folded = f"{label} {candidate}".casefold()
        if family == "tax":
            if "tax" not in folded:
                continue
            if "mediation" in folded or "multi-door" in folded:
                artifact_type = "tax_multi_door_mediation"
            elif "show cause" in folded:
                artifact_type = "tax_show_cause"
            else:
                continue
        else:
            if "attorney_calendar_internet" not in folded:
                continue
            artifact_type = "criminal_attorney_schedule"
        artifacts.append(
            CalendarArtifact(
                family=family,
                artifact_type=artifact_type,
                label=label,
                url=candidate,
                page_last_updated=page_updated,
            )
        )
    if family == "criminal" and all(
        item.url != CRIMINAL_COURT_PDF_URL for item in artifacts
    ):
        artifacts.append(
            CalendarArtifact(
                family="criminal",
                artifact_type="criminal_court_schedule",
                label="Criminal Court Schedule",
                url=CRIMINAL_COURT_PDF_URL,
                page_last_updated=page_updated,
            )
        )
    if not artifacts:
        raise _source_schema_error(
            f"D.C. {family} calendar page contains no recognized artifacts",
            url=url,
        )
    unique: dict[str, CalendarArtifact] = {}
    for artifact in artifacts:
        unique.setdefault(artifact.url, artifact)
    return tuple(unique.values())


def parse_appeals_payload(payload: Any) -> tuple[CalendarArtifact, ...]:
    """Parse the native Court of Appeals calendar-artifact index."""

    if not isinstance(payload, list):
        raise _source_schema_error(
            "D.C. appeals calendar JSON root is not an array",
            url=APPEALS_REST_URL,
            details={"root_type": type(payload).__name__},
        )
    artifacts: list[CalendarArtifact] = []
    fields = {
        "field_year",
        "field_month_court_calendar",
        "field_pdf_archive_court_calendar",
        "field_pdf_archive_summary",
    }
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping) or not fields <= set(row):
            raise _source_schema_error(
                "D.C. appeals calendar row schema changed",
                url=APPEALS_REST_URL,
                details={"row_index": index},
            )
        try:
            year = int(row["field_year"])
        except (TypeError, ValueError) as error:
            raise _source_schema_error(
                "D.C. appeals calendar year is not numeric",
                url=APPEALS_REST_URL,
                details={"row_index": index, "value": row.get("field_year")},
            ) from error
        month = _clean_text(row["field_month_court_calendar"])
        if month is None:
            raise _source_schema_error(
                "D.C. appeals calendar month is blank",
                url=APPEALS_REST_URL,
                details={"row_index": index},
            )
        for artifact_type, field in (
            ("regular_calendar", "field_pdf_archive_court_calendar"),
            ("summary_calendar", "field_pdf_archive_summary"),
        ):
            raw_url = _clean_text(row[field])
            if raw_url is None:
                continue
            artifact_url = _official_pdf_url(raw_url, page_url=APPEALS_URL)
            artifacts.append(
                CalendarArtifact(
                    family="appeals",
                    artifact_type=artifact_type,
                    label=f"{month} {year} {artifact_type.replace('_', ' ')}",
                    url=artifact_url,
                    year=year,
                    month=month,
                )
            )
    return tuple(artifacts)


def source_manifest() -> dict[str, Any]:
    """Return source roles, representations, and explicit complements."""

    return {
        "family": "District of Columbia public court calendars",
        "sources": [
            metadata.to_dict()
            for metadata in (
                TODAY_METADATA,
                CRIMINAL_METADATA,
                TAX_METADATA,
                APPEALS_METADATA,
            )
        ],
        "operations": {
            "search": {
                "source_id": TODAY_SOURCE_ID,
                "representation": "html_search",
                "pagination": "native_zero_based_page",
            },
            "snapshot": {
                "source_id": TODAY_SOURCE_ID,
                "representation": "rest_full_current_array",
                "pagination": "local_offset_after_full_snapshot_fetch",
            },
            "criminal": {
                "source_id": CRIMINAL_SOURCE_ID,
                "representation": "html_search",
                "pagination": "native_zero_based_page",
            },
            "artifacts": {
                "source_ids": [CRIMINAL_SOURCE_ID, TAX_SOURCE_ID],
                "representation": "official_pdf_index",
            },
            "appeals": {
                "source_id": APPEALS_SOURCE_ID,
                "representation": "rest_artifact_index",
                "native_filter": "field_year_court_calendar_value[]",
            },
        },
        "complementary_case_systems": [
            {
                "source_id": "us-dc-superior-court-portal",
                "name": "D.C. Superior Court Portal",
                "url": PORTAL_URL,
                "coverage": (
                    "civil, civil tax, Auditor-Master, and probate case "
                    "histories and documents"
                ),
                "operation_states": {
                    "smart_search": {
                        "state": "human_verification_observed",
                        "observed_on": "2026-07-30",
                    }
                },
            },
            {
                "source_id": "us-dc-superior-eaccess",
                "name": "D.C. Superior Court eAccess",
                "url": EACCESS_URL,
                "coverage": (
                    "criminal, criminal tax, and Domestic Violence case "
                    "histories and available document images"
                ),
                "operation_states": {
                    "case_search": {
                        "state": "captcha_observed",
                        "observed_on": "2026-07-30",
                    }
                },
            },
        ],
        "coverage_notes": list(SOURCE_WARNINGS),
    }


def _filters_for_args(args: argparse.Namespace, *, kind: str) -> dict[str, str]:
    if kind == "today":
        values = {
            "party": args.party,
            "case_no": args.case_number,
            "judges": args.judge or "All",
            "courtroom": args.courtroom or "All",
            "order": args.order,
            "sort": args.sort,
        }
    else:
        values = {
            "field_xml_defendant_value": args.defendant,
            "field_xml_timex_value": args.time,
            "event": args.event,
            "field_xml_charge_value": args.charge,
            "field_xml_attorney_value": args.attorney,
            "field_xml_case_no_value": args.case_number,
            "field_courtroom_link_target_id": args.courtroom or "All",
            "field_judge_link_target_id": args.judge or "All",
            "order": args.order,
            "sort": args.sort,
        }
    return {
        key: str(value)
        for key, value in values.items()
        if value is not None and str(value) != ""
    }


def _query_key(kind: str, filters: Mapping[str, Any]) -> str:
    payload = {"kind": kind, "filters": dict(filters)}
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:16]


def _encode_page_cursor(
    kind: str,
    filters: Mapping[str, Any],
    page: int,
) -> str:
    return f"dcsc:v1:{kind}:{_query_key(kind, filters)}:page:{page}"


def _start_page(
    args: argparse.Namespace,
    *,
    kind: str,
    filters: Mapping[str, Any],
) -> int:
    cursor = getattr(args, "cursor", None)
    page = getattr(args, "page", None)
    if cursor and page is not None:
        raise DCCalendarQueryError(
            "ambiguous_pagination",
            "use either --cursor or --page for one calendar search",
        )
    if not cursor:
        return 0 if page is None else page
    match = CURSOR_RE.fullmatch(str(cursor))
    if match is None:
        raise DCCalendarQueryError(
            "invalid_cursor",
            "cursor does not match the D.C. calendar cursor format",
        )
    if match.group("kind") != kind:
        raise DCCalendarQueryError(
            "cursor_calendar_mismatch",
            "cursor belongs to a different D.C. calendar",
        )
    if match.group("fingerprint") != _query_key(kind, filters):
        raise DCCalendarQueryError(
            "cursor_query_mismatch",
            "cursor filters differ from this calendar query",
        )
    return int(match.group("page"))


def _parse_event_datetime(value: Any, *, source_url: str) -> datetime:
    text = _clean_text(value)
    if text is None:
        raise _source_schema_error(
            "D.C. calendar event datetime is blank",
            url=source_url,
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise _source_schema_error(
            "D.C. calendar event datetime is not ISO 8601",
            url=source_url,
            details={"value": text},
        ) from error
    if parsed.tzinfo is None:
        raise _source_schema_error(
            "D.C. calendar event datetime has no UTC offset",
            url=source_url,
            details={"value": text},
        )
    return parsed


def _row_identity(
    raw: Mapping[str, Any],
    *,
    kind: str,
) -> str:
    identity = {
        "kind": kind,
        "fields": {
            key: value
            for key, value in raw.items()
            if not str(key).startswith("_")
        },
        "event_datetime": raw.get("_event_datetime"),
        "remote_hearing_url": raw.get("_remote_hearing_url"),
    }
    return hashlib.sha256(canonical_json(identity).encode()).hexdigest()


def _html_hearing_records(
    pages: Sequence[tuple[CalendarPage, FetchedText]],
    *,
    kind: str,
) -> list[dict[str, Any]]:
    all_rows = [row for page, _fetch in pages for row in page.rows]
    identities = [_row_identity(row, kind=kind) for row in all_rows]
    totals = Counter(identities)
    seen: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    row_offset = 0
    source_id = TODAY_SOURCE_ID if kind == "today" else CRIMINAL_SOURCE_ID
    for page, fetched in pages:
        response_date = _response_date(fetched.headers)
        for raw in page.rows:
            identity = identities[row_offset]
            row_offset += 1
            duplicate_ordinal = seen[identity]
            seen[identity] += 1
            native_entry_id = (
                identity
                if totals[identity] == 1
                else f"{identity}:{duplicate_ordinal}"
            )
            case_number = _clean_text(raw.get("Case Number"))
            if case_number is None:
                raise _source_schema_error(
                    f"D.C. {kind} calendar row has no case number",
                    url=fetched.source_url,
                )
            event = _parse_event_datetime(
                raw.get("_event_datetime"),
                source_url=fetched.source_url,
            )
            common = {
                "canonical_ref": canonical_court_ref(
                    source_id,
                    COURT_ID,
                    case_number,
                    record_kind="calendar_hearing",
                    native_id=native_entry_id,
                ),
                "case_canonical_ref": canonical_court_ref(
                    source_id,
                    COURT_ID,
                    case_number,
                ),
                "source_id": source_id,
                "record_kind": "court_calendar_hearing_occurrence",
                "native_entry_id": native_entry_id,
                "identity_kind": "source_fields_sha256",
                "duplicate_ordinal": duplicate_ordinal,
                "raw_case_number": case_number,
                "case_number": case_number,
                "court": {
                    "court_id": COURT_ID,
                    "name": "Superior Court of the District of Columbia",
                    "level": "local_trial",
                },
                "event_type": "hearing",
                "event_datetime": event.isoformat(),
                "event_date": event.date().isoformat(),
                "event_time": event.timetz().isoformat(),
                "timezone": DC_TIMEZONE_NAME,
                "utc_offset": event.strftime("%z"),
                "courtroom": _clean_text(raw.get("Courtroom")),
                "judge": _clean_text(raw.get("Judge")),
                "remote_hearing_url": raw.get("_remote_hearing_url"),
                "source_url": fetched.source_url,
                "source_occurrence": {
                    "native_page": page.native_page,
                    "native_row_index": raw.get("_native_row_index"),
                    "reported_total": page.reported_total,
                    "reported_total_pages": page.total_pages,
                },
                "source_freshness": {
                    "calendar_date": event.date().isoformat(),
                    "response_date": response_date,
                    "page_content_last_updated": page.page_last_updated,
                    "refresh_statement": (
                        "updated_daily"
                        if kind == "today"
                        else "updated_at_7_30pm_the_night_before"
                    ),
                    "event_date_basis": "source_time_datetime_attribute",
                },
                "representation": "html_search",
                "raw": {
                    key: value
                    for key, value in raw.items()
                    if not str(key).startswith("_")
                },
            }
            if kind == "today":
                common.update(
                    {
                        "party": _clean_text(raw.get("Party")),
                        "division": _clean_text(raw.get("Division")),
                        "case_type": _clean_text(raw.get("Case Type")),
                    }
                )
            else:
                common.update(
                    {
                        "defendant": _clean_text(raw.get("Defendant")),
                        "event_name": _clean_text(raw.get("Event")),
                        "charge": _clean_text(raw.get("Charge")),
                        "attorney": _clean_text(raw.get("Attorney")),
                    }
                )
            records.append(common)
    return records


def _snapshot_event_datetime(
    raw_time: Any,
    *,
    response_date: str,
) -> datetime:
    text = _clean_text(raw_time)
    if text is None:
        raise _source_schema_error(
            "D.C. today snapshot time is blank",
            url=TODAY_REST_URL,
        )
    normalized = re.sub(r"\s+", " ", text).upper()
    parsed_time = None
    for pattern in ("%I:%M %p", "%I:%M:%S %p"):
        try:
            parsed_time = datetime.strptime(normalized, pattern).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise _source_schema_error(
            "D.C. today snapshot time format changed",
            url=TODAY_REST_URL,
            details={"value": text},
        )
    return datetime.combine(
        datetime.fromisoformat(response_date).date(),
        parsed_time,
        tzinfo=DC_TIMEZONE,
    )


def _snapshot_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    response_date: str,
    source_url: str,
) -> list[dict[str, Any]]:
    identities = [
        hashlib.sha256(canonical_json(dict(row)).encode()).hexdigest()
        for row in rows
    ]
    totals = Counter(identities)
    seen: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for row_index, (raw, identity) in enumerate(zip(rows, identities, strict=True)):
        duplicate_ordinal = seen[identity]
        seen[identity] += 1
        native_entry_id = (
            identity
            if totals[identity] == 1
            else f"{identity}:{duplicate_ordinal}"
        )
        case_number = _clean_text(raw.get("case_no"))
        if case_number is None:
            raise _source_schema_error(
                "D.C. today snapshot row has no case number",
                url=source_url,
                details={"row_index": row_index},
            )
        event = _snapshot_event_datetime(
            raw.get("timex_timestamp"),
            response_date=response_date,
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    TODAY_SOURCE_ID,
                    COURT_ID,
                    case_number,
                    record_kind="calendar_hearing",
                    native_id=native_entry_id,
                ),
                "case_canonical_ref": canonical_court_ref(
                    TODAY_SOURCE_ID,
                    COURT_ID,
                    case_number,
                ),
                "source_id": TODAY_SOURCE_ID,
                "record_kind": "court_calendar_hearing_occurrence",
                "native_entry_id": native_entry_id,
                "identity_kind": "source_fields_sha256",
                "duplicate_ordinal": duplicate_ordinal,
                "raw_case_number": case_number,
                "case_number": case_number,
                "court": {
                    "court_id": COURT_ID,
                    "name": "Superior Court of the District of Columbia",
                    "level": "local_trial",
                },
                "event_type": "hearing",
                "event_datetime": event.isoformat(),
                "event_date": event.date().isoformat(),
                "event_time": event.timetz().isoformat(),
                "timezone": DC_TIMEZONE_NAME,
                "utc_offset": event.strftime("%z"),
                "party": _clean_text(raw.get("party")),
                "division": _clean_text(raw.get("division")),
                "case_type": _clean_text(
                    html_module.unescape(str(raw.get("case_type", "")))
                ),
                "courtroom": _clean_text(
                    raw.get("courtroom_link") or raw.get("location")
                ),
                "judge": _clean_text(raw.get("judge_name")),
                "remote_hearing_url": _clean_text(raw.get("webexurl")),
                "source_url": source_url,
                "source_occurrence": {"snapshot_row_index": row_index},
                "source_freshness": {
                    "calendar_date": response_date,
                    "response_date": response_date,
                    "page_content_last_updated": None,
                    "refresh_statement": "current_day_snapshot",
                    "event_date_basis": (
                        "official_today_feed_and_http_response_date"
                    ),
                },
                "representation": "rest_snapshot",
                "raw": dict(raw),
            }
        )
    return records


def _artifact_record(
    artifact: CalendarArtifact,
    *,
    source_id: str,
    index_url: str,
    response_date: str | None,
) -> dict[str, Any]:
    digest = hashlib.sha256(artifact.url.encode()).hexdigest()
    return {
        "canonical_ref": f"DCCOURTARTIFACT:{source_id}:{digest}",
        "source_id": source_id,
        "record_kind": "court_calendar_artifact",
        "artifact_type": artifact.artifact_type,
        "label": artifact.label,
        "calendar_family": artifact.family,
        "calendar_year": artifact.year,
        "calendar_month": artifact.month,
        "document_url": artifact.url,
        "index_url": index_url,
        "source_freshness": {
            "response_date": response_date,
            "page_content_last_updated": artifact.page_last_updated,
            "document_freshness_basis": "document_internal_or_http_metadata",
        },
    }


def _source_for_args(args: argparse.Namespace) -> SourceMetadata:
    if args.command in {"search", "snapshot", "probe"}:
        return TODAY_METADATA
    if args.command == "filters":
        return (
            TODAY_METADATA
            if args.calendar == "today"
            else CRIMINAL_METADATA
        )
    if args.command == "criminal":
        return CRIMINAL_METADATA
    if args.command == "artifacts":
        return CRIMINAL_METADATA if args.family == "criminal" else TAX_METADATA
    if args.command == "appeals":
        return APPEALS_METADATA
    raise ValueError(f"unsupported D.C. calendar command: {args.command}")


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source = _source_for_args(args)
    parameters: dict[str, Any]
    cursor = getattr(args, "cursor", None)
    requested_limit = None
    if args.command == "search":
        parameters = _filters_for_args(args, kind="today")
        parameters["page"] = args.page
        parameters["max_pages"] = args.max_pages
    elif args.command == "criminal":
        parameters = _filters_for_args(args, kind="criminal")
        parameters["page"] = args.page
        parameters["max_pages"] = args.max_pages
    elif args.command == "snapshot":
        parameters = {"representation": "full_current_array"}
        requested_limit = args.limit
    elif args.command == "filters":
        parameters = {"calendar": args.calendar}
    elif args.command == "artifacts":
        parameters = {"family": args.family}
    elif args.command == "appeals":
        parameters = {"year": args.year}
    elif args.command == "probe":
        parameters = {"scope": "bounded_source_family"}
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={"access": "anonymous_open"},
        ),
    )


def _calendar_page_result(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
    *,
    kind: str,
) -> PublicRecordsResult:
    filters = _filters_for_args(args, kind=kind)
    start_page = _start_page(args, kind=kind, filters=filters)
    page_url = TODAY_URL if kind == "today" else CRIMINAL_URL
    pages: list[tuple[CalendarPage, FetchedText]] = []
    next_page: int | None = start_page
    visited_pages: set[int] = set()
    while next_page is not None and (
        args.max_pages is None or len(pages) < args.max_pages
    ):
        if next_page in visited_pages:
            raise _source_schema_error(
                f"D.C. {kind} calendar pagination repeated page {next_page}",
                url=page_url,
            )
        visited_pages.add(next_page)
        params = {**filters, "page": next_page}
        fetched = client.html(page_url, params=params)
        parsed = parse_calendar_html(
            fetched.text,
            kind=kind,
            native_page=next_page,
            source_url=fetched.source_url,
        )
        pages.append((parsed, fetched))
        next_page = parsed.next_page
    if not pages:
        raise _source_schema_error(
            f"D.C. {kind} calendar returned no native page",
            url=page_url,
        )
    records = _html_hearing_records(pages, kind=kind)
    artifact_refs = [item.source_url for _page, item in pages]
    if not records:
        if pages[0][0].no_results:
            return PublicRecordsResult.success(
                query,
                [],
                raw_artifact_refs=artifact_refs,
                warnings=SOURCE_WARNINGS,
            )
        raise _source_schema_error(
            f"D.C. {kind} calendar returned no rows without its empty marker",
            url=artifact_refs[0],
        )
    if next_page is not None:
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            next_cursor=_encode_page_cursor(kind, filters, next_page),
            raw_artifact_refs=artifact_refs,
            warnings=(
                *SOURCE_WARNINGS,
                "Additional source-native pages remain; next_cursor resumes "
                "the same filter set.",
            ),
        )
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=artifact_refs,
        warnings=SOURCE_WARNINGS,
    )


def _snapshot_result(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    offset = 0
    cursor_fingerprint: str | None = None
    if args.cursor:
        match = SNAPSHOT_CURSOR_RE.fullmatch(str(args.cursor))
        if match is None:
            raise DCCalendarQueryError(
                "invalid_cursor",
                "cursor does not match the D.C. snapshot cursor format",
            )
        offset = int(match.group("offset"))
        cursor_fingerprint = match.group("fingerprint")
    fetched = client.json(TODAY_REST_URL)
    rows = parse_today_snapshot(fetched.payload)
    snapshot_fingerprint = hashlib.sha256(
        canonical_json(rows).encode()
    ).hexdigest()[:16]
    if (
        cursor_fingerprint is not None
        and cursor_fingerprint != snapshot_fingerprint
    ):
        raise DCCalendarQueryError(
            "cursor_snapshot_changed",
            "the current-day snapshot changed since this cursor was issued",
            details={
                "cursor_snapshot": cursor_fingerprint,
                "current_snapshot": snapshot_fingerprint,
            },
        )
    source_array_rows = (
        len(fetched.payload) if isinstance(fetched.payload, list) else len(rows)
    )
    blank_placeholder_rows = source_array_rows - len(rows)
    response_date = _response_date(fetched.headers)
    if response_date is None:
        raise _source_schema_error(
            "D.C. today snapshot response lacks a usable HTTP Date header",
            url=fetched.source_url,
        )
    if offset > len(rows):
        raise DCCalendarQueryError(
            "cursor_offset_out_of_range",
            "snapshot cursor offset is beyond the current feed",
            details={"offset": offset, "feed_rows": len(rows)},
        )
    all_records = _snapshot_records(
        rows,
        response_date=response_date,
        source_url=fetched.source_url,
    )
    stop = None if args.limit is None else offset + args.limit
    records = all_records[offset:stop]
    selected = rows[offset:stop]
    next_offset = offset + len(selected)
    next_cursor = (
        f"dcsc:v1:snapshot:{snapshot_fingerprint}:offset:{next_offset}"
        if next_offset < len(rows)
        else None
    )
    snapshot_warnings = list(SOURCE_WARNINGS)
    if blank_placeholder_rows:
        snapshot_warnings.append(
            f"The source array included {blank_placeholder_rows} fully blank "
            "placeholder row(s), which carry no hearing occurrence."
        )
    if next_cursor:
        snapshot_warnings.append(
            "The source returned the full snapshot; this envelope contains "
            "a local slice and next_cursor resumes only while the source "
            "snapshot fingerprint still matches."
        )
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            next_cursor=next_cursor,
            raw_artifact_refs=[fetched.source_url],
            warnings=snapshot_warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=[fetched.source_url],
        warnings=snapshot_warnings,
    )


def _filter_result(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    kind = args.calendar
    url = TODAY_URL if kind == "today" else CRIMINAL_URL
    fetched = client.html(url, params={"page": 0})
    parsed = parse_calendar_html(
        fetched.text,
        kind=kind,
        native_page=0,
        source_url=fetched.source_url,
    )
    record = {
        "source_id": query.source.source_id,
        "record_kind": "court_calendar_filter_taxonomy",
        "calendar": kind,
        "filters": parsed.filters,
        "schema_fingerprint": parsed.schema_fingerprint,
        "source_url": fetched.source_url,
        "source_freshness": {
            "response_date": _response_date(fetched.headers),
            "page_content_last_updated": parsed.page_last_updated,
        },
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[fetched.source_url],
        warnings=SOURCE_WARNINGS,
    )


def _artifacts_result(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    url = CRIMINAL_URL if args.family == "criminal" else TAX_URL
    fetched = client.html(url)
    artifacts = parse_artifact_index_html(
        fetched.text,
        family=args.family,
        page_url=fetched.source_url,
    )
    records = [
        _artifact_record(
            artifact,
            source_id=query.source.source_id,
            index_url=fetched.source_url,
            response_date=_response_date(fetched.headers),
        )
        for artifact in artifacts
    ]
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=[fetched.source_url],
        warnings=SOURCE_WARNINGS,
    )


def _appeals_result(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    params = (
        {"field_year_court_calendar_value[]": args.year}
        if args.year is not None
        else None
    )
    fetched = client.json(APPEALS_REST_URL, params=params)
    artifacts = parse_appeals_payload(fetched.payload)
    records = [
        _artifact_record(
            artifact,
            source_id=APPEALS_SOURCE_ID,
            index_url=fetched.source_url,
            response_date=_response_date(fetched.headers),
        )
        for artifact in artifacts
    ]
    if args.year is None:
        records.append(
            _artifact_record(
                CalendarArtifact(
                    family="appeals",
                    artifact_type="weekly_panel_calendar",
                    label="Court of Appeals Weekly Panels",
                    url=APPEALS_WEEKLY_PANEL_URL,
                ),
                source_id=APPEALS_SOURCE_ID,
                index_url=APPEALS_URL,
                response_date=_response_date(fetched.headers),
            )
        )
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=[fetched.source_url],
        warnings=(
            *SOURCE_WARNINGS,
            "The appeals page says argument calendars are established about "
            "30 days ahead and can change.",
        ),
    )


def _probe_result(
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    today_fetch = client.html(TODAY_URL, params={"page": 0})
    today = parse_calendar_html(
        today_fetch.text,
        kind="today",
        native_page=0,
        source_url=today_fetch.source_url,
    )
    snapshot_fetch = client.json(TODAY_REST_URL)
    snapshot = parse_today_snapshot(snapshot_fetch.payload)
    snapshot_source_rows = (
        len(snapshot_fetch.payload)
        if isinstance(snapshot_fetch.payload, list)
        else len(snapshot)
    )
    criminal_fetch = client.html(CRIMINAL_URL, params={"page": 0})
    criminal = parse_calendar_html(
        criminal_fetch.text,
        kind="criminal",
        native_page=0,
        source_url=criminal_fetch.source_url,
    )
    tax_fetch = client.html(TAX_URL)
    tax = parse_artifact_index_html(
        tax_fetch.text,
        family="tax",
        page_url=tax_fetch.source_url,
    )
    appeals_fetch = client.json(APPEALS_REST_URL)
    appeals = parse_appeals_payload(appeals_fetch.payload)
    record = {
        "source_id": TODAY_SOURCE_ID,
        "record_kind": "court_calendar_source_probe",
        "operations": {
            "today_html": {
                "state": "ok",
                "returned_rows": len(today.rows),
                "reported_total": today.reported_total,
                "native_page": today.native_page,
                "next_page": today.next_page,
                "schema_fingerprint": today.schema_fingerprint,
            },
            "today_rest_snapshot": {
                "state": "ok",
                "returned_rows": len(snapshot),
                "source_array_rows": snapshot_source_rows,
                "blank_placeholder_rows_omitted": (
                    snapshot_source_rows - len(snapshot)
                ),
                "response_shape": "full_current_array",
            },
            "criminal_html": {
                "state": "ok",
                "returned_rows": len(criminal.rows),
                "reported_total": criminal.reported_total,
                "native_page": criminal.native_page,
                "next_page": criminal.next_page,
                "schema_fingerprint": criminal.schema_fingerprint,
            },
            "tax_artifacts": {
                "state": "ok",
                "returned_artifacts": len(tax),
            },
            "appeals_rest_index": {
                "state": "ok",
                "returned_artifacts": len(appeals),
                "native_year_filter": "field_year_court_calendar_value[]",
            },
        },
        "transport": {
            "request_shape": "ordinary_chrome_headers",
            "generic_custom_user_agent_observation": "azure_gateway_http_403",
        },
        "complementary_case_system_states": (
            source_manifest()["complementary_case_systems"]
        ),
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[
            today_fetch.source_url,
            snapshot_fetch.source_url,
            criminal_fetch.source_url,
            tax_fetch.source_url,
            appeals_fetch.source_url,
        ],
        warnings=SOURCE_WARNINGS,
    )


def _query_failure(
    query: PublicRecordsQuery,
    error: DCCalendarQueryError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="input",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "filters":
        return _filter_result(args, client, query)
    if args.command == "search":
        return _calendar_page_result(
            args,
            client,
            query,
            kind="today",
        )
    if args.command == "criminal":
        return _calendar_page_result(
            args,
            client,
            query,
            kind="criminal",
        )
    if args.command == "snapshot":
        return _snapshot_result(args, client, query)
    if args.command == "artifacts":
        return _artifacts_result(args, client, query)
    if args.command == "appeals":
        return _appeals_result(args, client, query)
    if args.command == "probe":
        return _probe_result(client, query)
    raise ValueError(f"unsupported D.C. calendar command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: DCCalendarClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute one D.C. Courts calendar-family operation."""

    if args.command == "sources":
        return source_manifest()
    query = build_query(args)
    source_client = client or DCCalendarClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except DCCalendarQueryError as error:
        result = _query_failure(query, error)
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
    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        try:
            log_search(
                canonical_json(query.to_dict()),
                query.source.source_id,
                count,
            )
        except Exception:
            pass
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _add_runtime_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    add_output_args(parser)


def _add_native_page_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page", type=_nonnegative_int)
    parser.add_argument("--cursor")
    parser.add_argument(
        "--max-pages",
        type=_positive_int,
        help=(
            "Maximum native pages to fetch; omitted traverses every "
            "advertised page"
        ),
    )
    parser.add_argument("--order", help="Native sort field from filters output")
    parser.add_argument("--sort", choices=("asc", "desc"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official District of Columbia court calendars"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Show source roles, representations, and complementary systems",
    )
    add_output_args(sources)

    filters = subparsers.add_parser(
        "filters",
        help="Fetch the source-native filter taxonomy",
    )
    filters.add_argument(
        "--calendar",
        choices=("today", "criminal"),
        default="today",
    )
    _add_runtime_output(filters)

    search = subparsers.add_parser(
        "search",
        help="Search Today's Superior Court Cases",
    )
    search.add_argument("--party")
    search.add_argument("--case-number")
    search.add_argument("--judge", help="Native judge value from filters output")
    search.add_argument(
        "--courtroom",
        help="Native courtroom value from filters output",
    )
    _add_native_page_args(search)
    _add_runtime_output(search)

    criminal = subparsers.add_parser(
        "criminal",
        help="Search the Criminal Attorney Case Calendar",
    )
    criminal.add_argument("--defendant")
    criminal.add_argument("--event")
    criminal.add_argument("--charge")
    criminal.add_argument("--time")
    criminal.add_argument("--attorney")
    criminal.add_argument("--case-number")
    criminal.add_argument(
        "--judge",
        help="Native judge value from filters output",
    )
    criminal.add_argument(
        "--courtroom",
        help="Native courtroom value from filters output",
    )
    _add_native_page_args(criminal)
    _add_runtime_output(criminal)

    snapshot = subparsers.add_parser(
        "snapshot",
        help="Read the complete current-day REST feed in local slices",
    )
    snapshot.add_argument(
        "--limit",
        type=_positive_int,
        help=(
            "Maximum snapshot rows to return; omitted retains the complete "
            "current feed"
        ),
    )
    snapshot.add_argument("--cursor")
    _add_runtime_output(snapshot)

    artifacts = subparsers.add_parser(
        "artifacts",
        help="List official criminal or Tax Division calendar PDFs",
    )
    artifacts.add_argument(
        "--family",
        choices=("criminal", "tax"),
        required=True,
    )
    _add_runtime_output(artifacts)

    appeals = subparsers.add_parser(
        "appeals",
        help="List Court of Appeals regular and summary calendar PDFs",
    )
    appeals.add_argument("--year", type=_positive_int)
    _add_runtime_output(appeals)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded checks across the public calendar family",
    )
    _add_runtime_output(probe)
    return parser


def _emit(
    payload: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    serialized = (
        payload.to_dict()
        if isinstance(payload, PublicRecordsResult)
        else dict(payload)
    )
    result_count = (
        len(payload.records) if isinstance(payload, PublicRecordsResult) else None
    )
    if write_output(
        serialized,
        args,
        summary=f"D.C. Courts calendar {args.command}",
        result_count=result_count,
    ):
        return
    print(json.dumps(serialized, indent=2, sort_keys=True))
    if isinstance(payload, PublicRecordsResult):
        for error in payload.errors:
            print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 1.0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0.0) < 0:
        parser.error("--minimum-interval cannot be negative")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
