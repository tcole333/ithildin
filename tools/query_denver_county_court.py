#!/usr/bin/env python3
"""Query the Denver County Court public daily docket.

The official public portal accepts a courtroom and court date through a
same-session HTML form.  It returns the complete matching docket as a
server-rendered table; the page's DataTables configuration disables paging.

Examples:
    uv run python tools/query_denver_county_court.py search \
        --courtroom 3A --date 2026-07-29 --output docket.json
    uv run python tools/query_denver_county_court.py search \
        --courtroom 3A --date 2026-07-29 --limit 25 --offset 25 --json
    uv run python tools/query_denver_county_court.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

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
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-co-denver-county-court-public-docket"
STATE_CODE = "CO"
COUNTY_GEOID = "08031"
COURT_ID = "co-denver-county-court"
COURT_NAME = "Denver County Court"
BASE_URL = "https://public.denvercountycourt.org"
DOCKET_URL = f"{BASE_URL}/Docket/Docket"
CASE_HISTORY_URL = f"{BASE_URL}/Case/CaseHistory"
DENVER_TIMEZONE = ZoneInfo("America/Denver")
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25

EXPECTED_COLUMNS = (
    "Case No",
    "AB/TK",
    "Defendant",
    "Status",
    "Language",
    "Case Type",
    "Scheduled Hearing",
    "Time",
    "Disposition",
    "DV",
    "Counsel",
    "DOB",
    "Charge",
    "Charge",
)
REQUIRED_HEADER_KEYS = frozenset(
    {
        "case_number",
        "ab_tk",
        "defendant",
        "status",
        "language",
        "case_type",
        "scheduled_hearing",
        "time",
        "disposition",
        "dv",
        "counsel",
        "dob",
        "charge",
    }
)
HEADER_ALIASES = {
    "case no": "case_number",
    "case number": "case_number",
    "ab tk": "ab_tk",
    "defendant": "defendant",
    "status": "status",
    "language": "language",
    "case type": "case_type",
    "scheduled hearing": "scheduled_hearing",
    "time": "time",
    "disposition": "disposition",
    "dv": "dv",
    "counsel": "counsel",
    "dob": "dob",
    "charge": "charge",
    "violations": "charge",
}
SOURCE_WARNINGS = (
    "This source is a courtroom-and-date docket calendar, not a filing-image "
    "repository.",
    "The result table is delivered in one server-rendered response; the "
    "portal configures client-side search and sorting with paging disabled.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Denver County Court Public Docket",
    source_role="county_court_daily_docket_calendar",
    base_url=DOCKET_URL,
    dataset_id="denver-county-court-public-docket",
    metadata={
        "authority": "Denver County Court",
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "authentication": "none",
        "platform_family": "denver_county_court_public_portal",
        "native_pagination": False,
        "client_side_table_search": True,
        "case_history_url": CASE_HISTORY_URL,
    },
)


class DenverCourtSelectionError(ValueError):
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


@dataclass(frozen=True)
class DocketCell:
    """One parsed table cell and its useful source attributes."""

    text: str | None
    href: str | None = None
    data_order: str | None = None


@dataclass(frozen=True)
class DenverDocketRow:
    """One native daily-docket result row."""

    case_number: str
    ab_tk: str | None
    defendant: str | None
    status: str | None
    language: str | None
    case_type: str | None
    scheduled_hearing: str | None
    hearing_time: str | None
    disposition: str | None
    domestic_violence_indicator: str | None
    counsel: str | None
    date_of_birth: str | None
    violations: tuple[str, ...]
    case_history_url: str | None
    source_time_order_raw: str | None
    extra_fields: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "ab_tk": self.ab_tk,
            "defendant": self.defendant,
            "status": self.status,
            "language": self.language,
            "case_type": self.case_type,
            "scheduled_hearing": self.scheduled_hearing,
            "hearing_time": self.hearing_time,
            "disposition": self.disposition,
            "domestic_violence_indicator": (
                self.domestic_violence_indicator
            ),
            "counsel": self.counsel,
            "date_of_birth": self.date_of_birth,
            "violations": list(self.violations),
            "case_history_url": self.case_history_url,
            "source_time_order_raw": self.source_time_order_raw,
            "extra_fields": dict(self.extra_fields),
        }


@dataclass(frozen=True)
class DenverDocketPage:
    """A validated GET or POST response from the daily-docket route."""

    form_action: str
    form_method: str
    token: str
    courtroom_options: tuple[str, ...]
    selected_courtroom: str | None
    court_date: str | None
    captcha_enabled: bool
    columns: tuple[str, ...]
    rows: tuple[DenverDocketRow, ...]
    schema_fingerprint: str
    request_parameters: Mapping[str, str] | None = None


class _DocketHTMLParser(HTMLParser):
    """Small source-specific parser with no browser-DOM dependency."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.form_seen = False
        self.form_action: str | None = None
        self.form_method: str | None = None
        self.token_seen = False
        self.token = ""
        self.court_date_seen = False
        self.court_date = ""
        self.room_select_seen = False
        self.room_options: list[str] = []
        self.selected_room: str | None = None
        self.captcha_seen = False
        self.captcha_value: str | None = None
        self.table_seen = False
        self.headers: list[str] = []
        self.rows: list[list[DocketCell]] = []

        self._in_form = False
        self._in_room_select = False
        self._in_option = False
        self._option_value = ""
        self._option_has_value = False
        self._option_selected = False
        self._option_parts: list[str] = []
        self._in_table = False
        self._current_row: list[DocketCell] | None = None
        self._cell_tag: str | None = None
        self._cell_parts: list[str] = []
        self._cell_href: str | None = None
        self._cell_data_order: str | None = None

    @staticmethod
    def _attrs(
        attrs: list[tuple[str, str | None]],
    ) -> dict[str, str]:
        return {
            str(key).lower(): value or ""
            for key, value in attrs
            if key is not None
        }

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        attributes = self._attrs(attrs)

        if tag == "form" and attributes.get("id") == "docketForm":
            self.form_seen = True
            self._in_form = True
            self.form_action = attributes.get("action")
            self.form_method = attributes.get("method", "get").lower()

        if self._in_form and tag == "input":
            name = attributes.get("name")
            if name == "token":
                self.token_seen = True
                self.token = attributes.get("value", "")
            elif name == "Court_Date":
                self.court_date_seen = True
                self.court_date = attributes.get("value", "")

        if (
            self._in_form
            and tag == "select"
            and attributes.get("name") == "SelectedCourtroom"
        ):
            self.room_select_seen = True
            self._in_room_select = True
        elif self._in_room_select and tag == "option":
            self._in_option = True
            self._option_value = attributes.get("value", "")
            self._option_has_value = "value" in attributes
            self._option_selected = "selected" in attributes
            self._option_parts = []

        if (
            tag == "div"
            and attributes.get("id") == "captchaEnabledConfigDocket"
        ):
            self.captcha_seen = True
            self.captcha_value = attributes.get("data-captcha-enabled")

        if tag == "table" and attributes.get("id") == "DocketTable":
            self.table_seen = True
            self._in_table = True
        elif self._in_table and tag == "tr":
            self._current_row = []
        elif self._in_table and tag in {"th", "td"}:
            self._cell_tag = tag
            self._cell_parts = []
            self._cell_href = None
            self._cell_data_order = attributes.get("data-order") or None
        elif self._cell_tag is not None and tag == "a":
            self._cell_href = attributes.get("href") or self._cell_href

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "form" and self._in_form:
            self._in_form = False
        elif tag == "select" and self._in_room_select:
            self._in_room_select = False
        elif tag == "option" and self._in_option:
            option_text = _clean_text(" ".join(self._option_parts))
            value = (
                _clean_text(self._option_value)
                if self._option_has_value
                else option_text
            )
            if value:
                self.room_options.append(value)
            if self._option_selected:
                self.selected_room = value
            self._in_option = False

        if self._in_table and tag in {"th", "td"}:
            text = _clean_text(" ".join(self._cell_parts))
            if self._cell_tag == "th":
                self.headers.append(text or "")
            elif self._current_row is not None:
                self._current_row.append(
                    DocketCell(
                        text=text,
                        href=self._cell_href,
                        data_order=self._cell_data_order,
                    )
                )
            self._cell_tag = None
            self._cell_parts = []
            self._cell_href = None
            self._cell_data_order = None
        elif self._in_table and tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
        elif self._in_table and tag == "table":
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_option:
            self._option_parts.append(data)
        if self._cell_tag is not None:
            self._cell_parts.append(data)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    decoded = html_lib.unescape(str(value))
    normalized = " ".join(
        decoded.replace("\x00", "").replace("\xa0", " ").split()
    ).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _clean_text(value)
    if normalized is None:
        raise ValueError(f"Denver County Court row lacks {field_name}")
    return normalized


def _header_key(value: str) -> str:
    normalized = " ".join(
        re.sub(r"[^a-z0-9]+", " ", value.casefold()).split()
    )
    return HEADER_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _source_schema_error(
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=DOCKET_URL, details=details)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    observed: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in observed:
            observed.add(value)
            result.append(value)
    return tuple(result)


def _first_cell(
    cells_by_key: Mapping[str, list[DocketCell]],
    key: str,
) -> DocketCell:
    values = cells_by_key.get(key)
    return values[0] if values else DocketCell(None)


def _violations(cells: Sequence[DocketCell]) -> tuple[str, ...]:
    values: list[str] = []
    observed: set[str] = set()
    source_cells = cells[1:] if len(cells) > 1 else cells
    for cell in source_cells:
        if not cell.text:
            continue
        for item in cell.text.split("^"):
            normalized = _clean_text(item)
            if normalized and normalized not in observed:
                observed.add(normalized)
                values.append(normalized)
    return tuple(values)


def parse_docket_html(html: str) -> DenverDocketPage:
    """Parse and validate one official Denver daily-docket response."""

    parser = _DocketHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as error:
        raise _source_schema_error(
            "Denver County Court docket HTML could not be parsed",
            details={"error": str(error)},
        ) from error

    if not parser.form_seen:
        raise _source_schema_error(
            "Denver County Court response lacks the docket search form"
        )
    expected_action = urlparse(DOCKET_URL)
    resolved_action = urlparse(
        urljoin(DOCKET_URL, parser.form_action or "")
    )
    action_path = resolved_action.path.casefold()
    if (
        action_path != "/docket/docket"
        or parser.form_method != "post"
        or resolved_action.scheme.casefold()
        != expected_action.scheme.casefold()
        or resolved_action.netloc.casefold()
        != expected_action.netloc.casefold()
    ):
        raise _source_schema_error(
            "Denver County Court docket form action or method changed",
            details={
                "form_action": parser.form_action,
                "form_method": parser.form_method,
            },
        )
    if not parser.token_seen:
        raise _source_schema_error(
            "Denver County Court docket form lacks its token field"
        )
    if not parser.room_select_seen or not parser.room_options:
        raise _source_schema_error(
            "Denver County Court docket form lacks courtroom options"
        )
    if not parser.court_date_seen:
        raise _source_schema_error(
            "Denver County Court docket form lacks its court-date field"
        )
    if not parser.captcha_seen or parser.captcha_value not in {"True", "False"}:
        raise _source_schema_error(
            "Denver County Court CAPTCHA configuration is missing or changed",
            details={"value": parser.captcha_value},
        )
    if parser.captcha_value == "True":
        raise _source_schema_error(
            "Denver County Court enabled CAPTCHA on the docket form"
        )
    if not parser.table_seen:
        raise _source_schema_error(
            "Denver County Court response lacks the docket result table"
        )

    columns = tuple(parser.headers)
    header_keys = tuple(_header_key(value) for value in columns)
    missing_headers = sorted(REQUIRED_HEADER_KEYS - set(header_keys))
    if missing_headers:
        raise _source_schema_error(
            "Denver County Court docket table lacks required headers",
            details={
                "missing_headers": missing_headers,
                "observed_columns": list(columns),
            },
        )
    if header_keys.count("charge") != 2:
        raise _source_schema_error(
            "Denver County Court docket charge columns changed",
            details={
                "charge_column_count": header_keys.count("charge"),
                "observed_columns": list(columns),
            },
        )

    rows: list[DenverDocketRow] = []
    known_keys = set(REQUIRED_HEADER_KEYS)
    for row_index, cells in enumerate(parser.rows):
        if len(cells) != len(columns):
            raise _source_schema_error(
                "Denver County Court docket row width changed",
                details={
                    "row_index": row_index,
                    "cell_count": len(cells),
                    "header_count": len(columns),
                },
            )
        cells_by_key: dict[str, list[DocketCell]] = {}
        for key, cell in zip(header_keys, cells, strict=True):
            cells_by_key.setdefault(key, []).append(cell)

        case_cell = _first_cell(cells_by_key, "case_number")
        case_number = _required_text(case_cell.text, "case number")
        time_cell = _first_cell(cells_by_key, "time")
        extra_fields: dict[str, Any] = {}
        for key, values in cells_by_key.items():
            if key in known_keys:
                continue
            extracted = [cell.text for cell in values]
            extra_fields[key] = (
                extracted[0] if len(extracted) == 1 else extracted
            )

        case_history_url = (
            urljoin(DOCKET_URL, case_cell.href)
            if case_cell.href
            else None
        )
        rows.append(
            DenverDocketRow(
                case_number=case_number,
                ab_tk=_first_cell(cells_by_key, "ab_tk").text,
                defendant=_first_cell(cells_by_key, "defendant").text,
                status=_first_cell(cells_by_key, "status").text,
                language=_first_cell(cells_by_key, "language").text,
                case_type=_first_cell(cells_by_key, "case_type").text,
                scheduled_hearing=_first_cell(
                    cells_by_key,
                    "scheduled_hearing",
                ).text,
                hearing_time=time_cell.text,
                disposition=_first_cell(cells_by_key, "disposition").text,
                domestic_violence_indicator=_first_cell(
                    cells_by_key,
                    "dv",
                ).text,
                counsel=_first_cell(cells_by_key, "counsel").text,
                date_of_birth=_first_cell(cells_by_key, "dob").text,
                violations=_violations(cells_by_key.get("charge", [])),
                case_history_url=case_history_url,
                source_time_order_raw=time_cell.data_order,
                extra_fields=extra_fields,
            )
        )

    declared_schema = {
        "kind": "denver_county_court_html_form_table",
        "form": {
            "action_path": action_path,
            "method": parser.form_method,
            "fields": ["SelectedCourtroom", "Court_Date", "token"],
            "captcha_enabled": False,
        },
        "columns": [
            {
                "position": index,
                "label": label,
                "key": header_keys[index],
            }
            for index, label in enumerate(columns)
        ],
    }
    return DenverDocketPage(
        form_action=parser.form_action or "",
        form_method=parser.form_method or "",
        token=parser.token,
        courtroom_options=_unique(parser.room_options),
        selected_courtroom=parser.selected_room,
        court_date=_clean_text(parser.court_date),
        captcha_enabled=False,
        columns=columns,
        rows=tuple(rows),
        schema_fingerprint=schema_fingerprint(declared_schema),
    )


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _checked_response(response: Any, *, url: str) -> str:
    status_code = int(getattr(response, "status_code", 0))
    text = getattr(response, "text", "")
    text = text if isinstance(text, str) else str(text)
    if status_code == 429:
        raise RateLimitedHTTPError(
            status_code,
            url=url,
            response_text=text,
        )
    if status_code in {401, 403}:
        raise RestrictedHTTPError(
            status_code,
            url=url,
            response_text=text,
        )
    if status_code == 451:
        raise TermsBlockedHTTPError(
            status_code,
            url=url,
            response_text=text,
        )
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(
            status_code,
            url=url,
            response_text=text,
        )
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(
            status_code,
            url=url,
            response_text=text,
        )
    content_type = (_response_header(response, "content-type") or "").casefold()
    if content_type and "html" not in content_type:
        raise _source_schema_error(
            "Denver County Court returned a non-HTML response",
            details={"content_type": content_type},
        )
    return text


def _retry_after(response: Any) -> float | None:
    value = _response_header(response, "retry-after")
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return max(0.0, parsed)


def _search_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise DenverCourtSelectionError(
            "invalid_court_date",
            "--date must be an ISO calendar date",
            details={"value": value},
        ) from error


def _source_date(value: str | None) -> date:
    normalized = _required_text(value, "court date")
    for date_format in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, date_format).date()
        except ValueError:
            continue
    raise _source_schema_error(
        "Denver County Court returned an unparseable court date",
        details={"value": normalized},
    )


class DenverCountyCourtClient:
    """Rate-limited, retrying same-session client for the public form."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: MinimumIntervalRateLimiter | Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or MinimumIntervalRateLimiter(
            DEFAULT_MINIMUM_INTERVAL
        )
        self.sleeper = sleeper
        self._owns_session = session is None
        self.headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Ithildin public-record source adapter",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> str:
        last_transport_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    data=data,
                    headers={
                        **self.headers,
                        **({"Referer": DOCKET_URL} if method == "POST" else {}),
                    },
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_transport_error = error
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(
                        attempt,
                        _retry_after(response),
                    )
                )
                continue
            return _checked_response(response, url=url)

        raise TransportError(
            "Denver County Court request failed",
            url=url,
            details={"error": str(last_transport_error or "retry exhausted")},
        )

    def bootstrap(self) -> DenverDocketPage:
        return parse_docket_html(self._request("GET", DOCKET_URL))

    def _submit(
        self,
        bootstrap: DenverDocketPage,
        *,
        courtroom: str,
        court_date: str,
    ) -> DenverDocketPage:
        if courtroom not in bootstrap.courtroom_options:
            raise DenverCourtSelectionError(
                "invalid_courtroom",
                f"Courtroom {courtroom!r} is not offered by the source",
                details={
                    "courtroom": courtroom,
                    "available_courtrooms": list(
                        bootstrap.courtroom_options
                    ),
                },
            )
        parsed_date = _search_date(court_date)
        payload = {
            "SelectedCourtroom": courtroom,
            "Court_Date": parsed_date.strftime("%m/%d/%Y"),
            "token": bootstrap.token,
        }
        target_url = urljoin(DOCKET_URL, bootstrap.form_action)
        page = parse_docket_html(
            self._request("POST", target_url, data=payload)
        )
        if page.selected_courtroom != courtroom:
            raise _source_schema_error(
                "Denver County Court did not retain the submitted courtroom",
                details={
                    "requested": courtroom,
                    "observed": page.selected_courtroom,
                },
            )
        if _source_date(page.court_date) != parsed_date:
            raise _source_schema_error(
                "Denver County Court did not retain the submitted court date",
                details={
                    "requested": court_date,
                    "observed": page.court_date,
                },
            )
        return replace(page, request_parameters=dict(payload))

    def search(
        self,
        *,
        courtroom: str,
        court_date: str,
    ) -> DenverDocketPage:
        return self._submit(
            self.bootstrap(),
            courtroom=courtroom,
            court_date=court_date,
        )

    def probe(
        self,
        *,
        courtroom: str | None = None,
        court_date: str | None = None,
    ) -> DenverDocketPage:
        bootstrap = self.bootstrap()
        selected_room = courtroom or bootstrap.courtroom_options[0]
        selected_date = court_date or datetime.now(
            DENVER_TIMEZONE
        ).date().isoformat()
        return self._submit(
            bootstrap,
            courtroom=selected_room,
            court_date=selected_date,
        )


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "denver-county-court",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "county",
        "official_url": DOCKET_URL,
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_type": "daily_docket_calendar",
        "selectors": ["courtroom", "court_date"],
        "fields": [
            "case_number",
            "ab_tk",
            "defendant",
            "status",
            "language",
            "case_type",
            "scheduled_hearing",
            "time",
            "disposition",
            "dv",
            "counsel",
            "dob",
            "violations",
        ],
        "native_pagination": False,
        "filing_images_available": False,
    }


def _identity_text(value: str | None) -> str:
    return (_clean_text(value) or "").casefold()


def _event_time(value: str | None) -> str | None:
    normalized = _clean_text(value)
    if normalized is None:
        return None
    for time_format in ("%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(
                normalized.upper(),
                time_format,
            ).time().isoformat()
        except ValueError:
            continue
    raise _source_schema_error(
        "Denver County Court returned an unparseable hearing time",
        details={"value": normalized},
    )


def normalize_rows(page: DenverDocketPage) -> list[dict[str, Any]]:
    """Normalize each native row as an ingestible docket-entry wrapper."""

    event_date = _source_date(page.court_date).isoformat()
    courtroom = _required_text(
        page.selected_courtroom,
        "selected courtroom",
    )
    records: list[dict[str, Any]] = []
    for row in page.rows:
        event_time = _event_time(row.hearing_time)
        identity_basis = {
            "case_number": _identity_text(row.case_number).upper(),
            "ab_tk": _identity_text(row.ab_tk).upper(),
            "courtroom": _identity_text(courtroom).upper(),
            "hearing_date": event_date,
            "hearing_time": event_time or "",
            "scheduled_hearing": _identity_text(row.scheduled_hearing),
            "case_type": _identity_text(row.case_type),
        }
        digest = hashlib.sha256(
            canonical_json(identity_basis).encode("utf-8")
        ).hexdigest()
        native_entry_id = f"daily-docket:{digest}"
        parties = (
            [
                {
                    "sequence_no": 1,
                    "role": "Defendant",
                    "raw_name": row.defendant,
                    "access_state": "public",
                }
            ]
            if row.defendant
            else []
        )
        case_url = row.case_history_url or DOCKET_URL
        case_canonical_ref = canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            row.case_number,
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    row.case_number,
                    "docket",
                    native_entry_id,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "docket_entry",
                "case": {
                    "canonical_ref": case_canonical_ref,
                    "source_id": SOURCE_ID,
                    "court": _court_payload(),
                    "raw_case_number": row.case_number,
                    "display_case_number": row.case_number,
                    "source_internal_id": None,
                    "caption": None,
                    "case_type": row.case_type,
                    "filing_date": None,
                    "status": None,
                    "access_state": "public",
                    "certified_record": False,
                    "source_url": case_url,
                    "parties": parties,
                    "documents": [],
                    "source_scope": _source_scope(),
                },
                "native_entry_id": native_entry_id,
                "identity_kind": "source_fields_sha256",
                "identity_basis": identity_basis,
                "event_type": "scheduled_hearing",
                "event_code": row.scheduled_hearing,
                "raw_text": row.scheduled_hearing or "Scheduled hearing",
                "filed_date": None,
                "entered_date": None,
                "event_date": event_date,
                "event_time": event_time,
                "source_event_date_raw": page.court_date,
                "source_event_time_raw": row.hearing_time,
                "courtroom": courtroom,
                "defendant_name": row.defendant,
                "case_type": row.case_type,
                "status": row.status,
                "native_status": row.status,
                "disposition": row.disposition,
                "counsel": row.counsel,
                "violations": list(row.violations),
                "ab_tk": row.ab_tk,
                "language": row.language,
                "domestic_violence_indicator": (
                    row.domestic_violence_indicator
                ),
                "date_of_birth": row.date_of_birth,
                "case_history_url": row.case_history_url,
                "document_available": False,
                "access_state": "public",
                "documents": [],
                "source_scope": _source_scope(),
                "source_fields": row.to_dict(),
                "schema_fingerprint": page.schema_fingerprint,
            }
        )
    return records


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command in {"search", "calendar"}:
        parameters = {
            "courtroom": args.courtroom,
            "court_date": args.court_date,
            "offset": args.offset,
        }
        requested_limit = args.limit
        if args.offset:
            cursor = f"denver-county-docket:offset:{args.offset}"
    elif args.command == "probe":
        parameters = {
            "courtroom": args.courtroom,
            "court_date": args.court_date,
        }
        requested_limit = 1
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Denver County, Colorado",
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
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
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
    error: DenverCourtSelectionError,
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


def _search_result(
    query: PublicRecordsQuery,
    page: DenverDocketPage,
    *,
    limit: int | None,
    offset: int,
) -> PublicRecordsResult:
    records = normalize_rows(page)
    selected = records[offset:] if limit is None else records[offset : offset + limit]
    next_cursor = None
    if limit is not None and offset + limit < len(records):
        next_cursor = f"denver-county-docket:offset:{offset + limit}"
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _probe_record(page: DenverDocketPage) -> dict[str, Any]:
    public_request_parameters = {
        key: value
        for key, value in dict(page.request_parameters or {}).items()
        if key != "token"
    }
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{COURT_ID}/probe/daily-docket"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "source_health_check",
        "source_url": DOCKET_URL,
        "court": _court_payload(),
        "source_scope": _source_scope(),
        "request_parameters": public_request_parameters,
        "courtroom_count": len(page.courtroom_options),
        "courtrooms": list(page.courtroom_options),
        "table_columns": list(page.columns),
        "parsed_row_count": len(page.rows),
        "captcha_enabled": page.captcha_enabled,
        "schema_fingerprint": page.schema_fingerprint,
    }


def _execute_command(
    args: argparse.Namespace,
    client: DenverCountyCourtClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command in {"search", "calendar"}:
        page = client.search(
            courtroom=args.courtroom,
            court_date=args.court_date,
        )
        return _search_result(
            query,
            page,
            limit=args.limit,
            offset=args.offset,
        )
    if args.command == "probe":
        page = client.probe(
            courtroom=args.courtroom,
            court_date=args.court_date,
        )
        return PublicRecordsResult.success(
            query,
            [_probe_record(page)],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Denver County Court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: DenverCountyCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one daily-docket search or source probe."""

    query = build_query(args)
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (
        AcquisitionUnavailableError,
        CatalogError,
        OSError,
        ValueError,
    ) as error:
        result = _access_failure(query, error)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    decision_limits = decision.get("limits") or {}
    catalog_interval = float(
        decision_limits.get("minimum_interval_seconds") or 0
    )
    source_client = client or DenverCountyCourtClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(
            max_attempts=getattr(args, "max_attempts", 3),
        ),
        rate_limiter=MinimumIntervalRateLimiter(
            max(
                getattr(
                    args,
                    "minimum_interval",
                    DEFAULT_MINIMUM_INTERVAL,
                ),
                catalog_interval,
            )
        ),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except DenverCourtSelectionError as error:
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
    if log_results:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Denver County Court {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Denver County Court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "docket_entry":
            print(
                f"  {record.get('case', {}).get('raw_case_number') or '?'} | "
                f"{record.get('event_date') or '?'} "
                f"{record.get('event_time') or ''} | "
                f"{record.get('courtroom') or '?'} | "
                f"{record.get('defendant_name') or '?'}"
            )
        else:
            print(
                f"  probe | {record.get('parsed_row_count')} rows | "
                f"{record.get('courtroom_count')} courtrooms"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Denver County Court daily docket"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Fetch the docket for one source courtroom and date",
    )
    search.add_argument("--courtroom", required=True)
    search.add_argument(
        "--date",
        dest="court_date",
        required=True,
        help="Court date as YYYY-MM-DD",
    )
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Return at most this many rows from the complete source response",
    )
    search.add_argument("--offset", type=_nonnegative_int, default=0)
    _add_runtime_and_output(search)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the live GET form and POST result-table contract",
    )
    probe.add_argument("--courtroom")
    probe.add_argument(
        "--date",
        dest="court_date",
        help="Probe date as YYYY-MM-DD; defaults to the Denver local date",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if getattr(args, "court_date", None):
        _search_date(args.court_date)
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
