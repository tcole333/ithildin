#!/usr/bin/env python3
"""Query the Colorado Judicial Branch statewide trial-court docket calendar.

The official Drupal page exposes an anonymous form, replayable GET result
URLs, 20-row native pages, a court/options directory, and a source-generated
export link.  Result rows are hearing-calendar index rows rather than case
documents.

Examples:
    uv run python tools/query_colorado_judicial.py courts --json
    uv run python tools/query_colorado_judicial.py search \
        --courthouse 16_civil --date 2026-07-29 --output dockets.json
    uv run python tools/query_colorado_judicial.py search \
        --business-name "Example LLC" --date-range 1_month --limit 50
    uv run python tools/query_colorado_judicial.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
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


SOURCE_ID = "us-co-judicial-docket-search"
STATE_CODE = "CO"
STATE_GEOID = "08"
BASE_URL = "https://www.coloradojudicial.gov"
DOCKET_URL = f"{BASE_URL}/dockets"
DENVER_TIMEZONE = ZoneInfo("America/Denver")
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25

DATE_RANGES = (
    "6_month",
    "3_month",
    "1_month",
    "1_week",
    "today",
    "specific_date",
)
OPTION_FIELDS = (
    "district",
    "county",
    "courthouse",
    "court",
    "date_range",
    "case_class",
    "name_type",
    "attorney_type",
)
REQUIRED_FORM_FIELDS = frozenset(
    {
        "district",
        "county",
        "courthouse",
        "court",
        "division",
        "date_range",
        "specific_date",
        "four_digit_year",
        "case_class",
        "case_sequence",
        "name_type",
        "first_name",
        "last_name",
        "company_name",
        "attorney_type",
        "bar_number",
        "attorney_first_name",
        "attorney_last_name",
        "form_build_id",
        "form_id",
        "op",
    }
)
REQUIRED_ROW_FIELDS = frozenset(
    {
        "date",
        "time",
        "name",
        "case_number",
        "hearing_type",
        "location",
        "courtroom",
    }
)
ROW_LABELS = {
    "date": "date",
    "time": "time",
    "duration": "duration",
    "name": "name",
    "case number": "case_number",
    "hearing type": "hearing_type",
    "location": "location",
    "appearance type": "appearance_type",
    "courtroom": "courtroom",
}
VALID_EMPTY_TEXT = "Sorry, no results available. Please try another search."
CURSOR_VERSION = "v1"
CURSOR_PATTERN = re.compile(
    r"^colorado-judicial:v1:query:(?P<query>[0-9a-f]{64}):"
    r"page:(?P<page>\d+):row:(?P<row>\d+)$"
)

SOURCE_WARNINGS = (
    "This source is a statewide trial-court docket calendar and case-discovery "
    "index, not a case-document repository.",
    "The source Name field is preserved as a calendar index name without "
    "inferring a party role.",
    "The source-generated export route is evaluated separately from docket "
    "search availability.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Colorado Judicial Branch Docket Search",
    source_role="statewide_trial_court_docket_calendar",
    base_url=DOCKET_URL,
    dataset_id="colorado-judicial-dockets",
    metadata={
        "authority": "Colorado Judicial Branch",
        "state_code": STATE_CODE,
        "state_geoid": STATE_GEOID,
        "authentication": "none",
        "platform_family": "drupal_docket_search",
        "native_page_size_observed": 20,
        "source_generated_export": True,
    },
)


class ColoradoJudicialSelectionError(ValueError):
    """A caller selector cannot be represented by the official source."""

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


class ColoradoExportUnavailableError(PublicRecordsHTTPError):
    """The source advertised an export but did not return an artifact."""

    result_status = ResultStatus.UNAVAILABLE
    category = "source_export"
    retryable = True
    code = "source_export_unavailable"


@dataclass(frozen=True)
class SourceOption:
    value: str
    label: str
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "label": self.label,
            "selected": self.selected,
        }


@dataclass(frozen=True)
class ColoradoDocketRow:
    hearing_date: str
    hearing_time: str
    duration: str | None
    calendar_name: str
    case_number: str
    hearing_type: str
    location: str
    appearance_type: str | None
    courtroom: str
    extra_fields: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.hearing_date,
            "time": self.hearing_time,
            "duration": self.duration,
            "name": self.calendar_name,
            "case_number": self.case_number,
            "hearing_type": self.hearing_type,
            "location": self.location,
            "appearance_type": self.appearance_type,
            "courtroom": self.courtroom,
            "extra_fields": dict(self.extra_fields),
        }


@dataclass(frozen=True)
class ColoradoDocketPage:
    form_action: str
    form_method: str
    form_fields: tuple[str, ...]
    options: Mapping[str, tuple[SourceOption, ...]]
    rows: tuple[ColoradoDocketRow, ...]
    result_state: str
    total_count: int | None
    range_start: int | None
    range_end: int | None
    page_index: int
    next_page_url: str | None
    export_url: str | None
    printable_url: str | None
    messages: tuple[str, ...]
    schema_fingerprint: str
    directory_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class ColoradoSearchBatch:
    rows: tuple[ColoradoDocketRow, ...]
    source_total_count: int
    pages_fetched: int
    next_cursor: str | None
    first_page: ColoradoDocketPage


@dataclass(frozen=True)
class ColoradoExport:
    source_url: str
    content: bytes
    media_type: str | None
    filename: str | None
    status_code: int


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _clean_text(value)
    if normalized is None:
        raise ValueError(f"Colorado Judicial docket row lacks {field_name}")
    return normalized


def _source_schema_error(
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=DOCKET_URL, details=details)


def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {
        str(key).lower(): value or ""
        for key, value in attrs
        if key is not None
    }


def _classes(value: str) -> set[str]:
    return {part for part in value.split() if part}


class _DocketHTMLParser(HTMLParser):
    """Structural parser for the official Drupal form and result list."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.form_seen = False
        self.form_action: str | None = None
        self.form_method: str | None = None
        self.form_fields: list[str] = []
        self.options: dict[str, list[SourceOption]] = {}
        self.rows: list[dict[str, str]] = []
        self.count_text: str | None = None
        self.result_text_parts: list[str] = []
        self.export_href: str | None = None
        self.printable_href: str | None = None
        self.next_href: str | None = None

        self._form_depth = 0
        self._select_name: str | None = None
        self._option_value = ""
        self._option_selected = False
        self._option_parts: list[str] = []
        self._results_depth = 0
        self._count_depth = 0
        self._count_parts: list[str] = []
        self._row_depth = 0
        self._current_row: dict[str, str] | None = None
        self._p_depth = 0
        self._p_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        attributes = _attrs(attrs)
        classes = _classes(attributes.get("class", ""))

        if tag == "form" and attributes.get("id") == "docket-search-form":
            self.form_seen = True
            self._form_depth = 1
            self.form_action = attributes.get("action")
            self.form_method = attributes.get("method", "get").lower()
        elif self._form_depth and tag == "form":
            self._form_depth += 1

        if self._form_depth and tag in {"input", "select", "button"}:
            name = attributes.get("name")
            if name and name not in self.form_fields:
                self.form_fields.append(name)
            if (
                tag == "input"
                and name in {"name_type", "attorney_type"}
                and attributes.get("value")
            ):
                self.options.setdefault(name, []).append(
                    SourceOption(
                        value=attributes["value"],
                        label=attributes["value"],
                        selected="checked" in attributes,
                    )
                )
        if self._form_depth and tag == "select":
            self._select_name = attributes.get("name")
            if self._select_name:
                self.options.setdefault(self._select_name, [])
        elif self._select_name and tag == "option":
            self._option_value = attributes.get("value", "")
            self._option_selected = "selected" in attributes
            self._option_parts = []

        if (
            tag == "div"
            and "block-docket-search-results-block" in classes
        ):
            self._results_depth = 1
        elif self._results_depth and tag == "div":
            self._results_depth += 1

        if tag == "p" and "dockets-results-count" in classes:
            self._count_depth = 1
            self._count_parts = []

        if tag == "li" and "docket-result-item" in classes:
            self._row_depth = 1
            self._current_row = {}
        elif self._row_depth and tag == "li":
            self._row_depth += 1
        if self._row_depth and tag == "p":
            self._p_depth = 1
            self._p_parts = []
        elif self._p_depth and tag == "p":
            self._p_depth += 1

        if tag == "a":
            href = attributes.get("href")
            if attributes.get("id") == "download-docket-search-results-button":
                self.export_href = href
            if "docket-print-link" in classes:
                self.printable_href = href
            if "next" in attributes.get("rel", "").split():
                self.next_href = href

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._p_depth and tag == "p":
            self._p_depth -= 1
            if not self._p_depth and self._current_row is not None:
                text = _clean_text(" ".join(self._p_parts))
                if text and ":" in text:
                    label, value = text.split(":", 1)
                    key = ROW_LABELS.get(label.strip().casefold())
                    if key:
                        self._current_row[key] = value.strip()
                    else:
                        self._current_row[label.strip()] = value.strip()
                self._p_parts = []
        if self._row_depth and tag == "li":
            self._row_depth -= 1
            if not self._row_depth and self._current_row is not None:
                self.rows.append(self._current_row)
                self._current_row = None

        if self._count_depth and tag == "p":
            self._count_depth -= 1
            if not self._count_depth:
                self.count_text = _clean_text(" ".join(self._count_parts))
                self._count_parts = []

        if self._select_name and tag == "option":
            label = _clean_text(" ".join(self._option_parts)) or ""
            self.options[self._select_name].append(
                SourceOption(
                    value=self._option_value,
                    label=label,
                    selected=self._option_selected,
                )
            )
            self._option_parts = []
        elif self._select_name and tag == "select":
            self._select_name = None

        if self._results_depth and tag == "div":
            self._results_depth -= 1
        if self._form_depth and tag == "form":
            self._form_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._select_name and self._option_parts is not None:
            self._option_parts.append(data)
        if self._results_depth:
            self.result_text_parts.append(data)
        if self._count_depth:
            self._count_parts.append(data)
        if self._p_depth:
            self._p_parts.append(data)


def _option_contract(
    options: Mapping[str, tuple[SourceOption, ...]],
) -> dict[str, list[dict[str, str]]]:
    return {
        key: [
            {"value": option.value, "label": option.label}
            for option in values
        ]
        for key, values in sorted(options.items())
        if key in OPTION_FIELDS
    }


def parse_docket_html(
    html: str,
    *,
    page_url: str = DOCKET_URL,
) -> ColoradoDocketPage:
    """Parse and validate one official form/results response."""

    parser = _DocketHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as error:
        raise _source_schema_error(
            "Colorado Judicial docket HTML could not be parsed",
            details={"error": str(error)},
        ) from error

    if not parser.form_seen:
        raise _source_schema_error(
            "Colorado Judicial response lacks the docket search form"
        )
    action = parser.form_action or ""
    action_url = urljoin(DOCKET_URL, action)
    parsed_action = urlparse(action_url)
    if (
        parser.form_method != "post"
        or parsed_action.scheme != "https"
        or parsed_action.netloc != urlparse(BASE_URL).netloc
        or parsed_action.path != "/dockets"
    ):
        raise _source_schema_error(
            "Colorado Judicial docket form action or method changed",
            details={
                "form_action": action,
                "form_method": parser.form_method,
            },
        )
    missing_fields = sorted(
        REQUIRED_FORM_FIELDS.difference(parser.form_fields)
    )
    if missing_fields:
        raise _source_schema_error(
            "Colorado Judicial docket form fields changed",
            details={"missing_fields": missing_fields},
        )

    options = {
        key: tuple(values)
        for key, values in parser.options.items()
        if key in OPTION_FIELDS
    }
    missing_options = sorted(set(OPTION_FIELDS).difference(options))
    if missing_options:
        raise _source_schema_error(
            "Colorado Judicial docket option groups changed",
            details={"missing_option_groups": missing_options},
        )
    option_values = {
        key: {option.value for option in values}
        for key, values in options.items()
    }
    required_option_values = {
        "court": {"", "C", "D"},
        "date_range": set(DATE_RANGES),
        "name_type": {"individual", "company"},
        "attorney_type": {"name", "number"},
    }
    changed_groups = {
        key: sorted(required.difference(option_values.get(key, set())))
        for key, required in required_option_values.items()
        if not required.issubset(option_values.get(key, set()))
    }
    if changed_groups:
        raise _source_schema_error(
            "Colorado Judicial docket option values changed",
            details={"missing_values": changed_groups},
        )

    rows: list[ColoradoDocketRow] = []
    for index, raw in enumerate(parser.rows):
        missing = sorted(REQUIRED_ROW_FIELDS.difference(raw))
        if missing:
            raise _source_schema_error(
                "Colorado Judicial docket row fields changed",
                details={"row_index": index, "missing_fields": missing},
            )
        rows.append(
            ColoradoDocketRow(
                hearing_date=_required_text(raw.get("date"), "date"),
                hearing_time=_required_text(raw.get("time"), "time"),
                duration=_clean_text(raw.get("duration")),
                calendar_name=_required_text(raw.get("name"), "name"),
                case_number=_required_text(
                    raw.get("case_number"),
                    "case number",
                ),
                hearing_type=_required_text(
                    raw.get("hearing_type"),
                    "hearing type",
                ),
                location=_required_text(raw.get("location"), "location"),
                appearance_type=_clean_text(raw.get("appearance_type")),
                courtroom=_required_text(
                    raw.get("courtroom"),
                    "courtroom",
                ),
                extra_fields={
                    key: value
                    for key, value in raw.items()
                    if key not in set(ROW_LABELS.values())
                },
            )
        )

    count_match = None
    if parser.count_text:
        count_match = re.fullmatch(
            r"Showing\s+([\d,]+)-([\d,]+)\s+of\s+([\d,]+)\s+results\.",
            parser.count_text,
            flags=re.IGNORECASE,
        )
        if count_match is None:
            raise _source_schema_error(
                "Colorado Judicial result count format changed",
                details={"count_text": parser.count_text},
            )
    result_text = _clean_text(" ".join(parser.result_text_parts)) or ""
    valid_empty = VALID_EMPTY_TEXT.casefold() in result_text.casefold()
    range_start = range_end = total_count = None
    if count_match:
        range_start, range_end, total_count = (
            int(value.replace(",", "")) for value in count_match.groups()
        )
        if range_end - range_start + 1 != len(rows):
            raise _source_schema_error(
                "Colorado Judicial page range does not match parsed rows",
                details={
                    "range_start": range_start,
                    "range_end": range_end,
                    "parsed_rows": len(rows),
                },
            )
        if range_start < 1 or range_end > total_count:
            raise _source_schema_error(
                "Colorado Judicial result range is inconsistent",
                details={
                    "range_start": range_start,
                    "range_end": range_end,
                    "total_count": total_count,
                },
            )
        result_state = "results"
    elif valid_empty and not rows:
        result_state = "no_results"
        total_count = 0
    elif not rows:
        result_state = "not_searched"
    else:
        raise _source_schema_error(
            "Colorado Judicial rows lack result-count metadata"
        )

    page_values = parse_qs(urlparse(page_url).query).get("page", ["0"])
    try:
        page_index = int(page_values[-1])
    except ValueError as error:
        raise _source_schema_error(
            "Colorado Judicial page cursor changed format",
            details={"page": page_values[-1]},
        ) from error
    if page_index < 0:
        raise _source_schema_error(
            "Colorado Judicial returned a negative page cursor"
        )

    schema = {
        "kind": "colorado_judicial_drupal_docket",
        "form_action_path": parsed_action.path,
        "form_method": parser.form_method,
        "form_fields": sorted(parser.form_fields),
        "option_groups": sorted(options),
        "row_fields": sorted(REQUIRED_ROW_FIELDS | {"duration", "appearance_type"}),
        "count_pattern": "Showing START-END of TOTAL results.",
        "native_page_parameter": "page",
        "valid_empty_text": VALID_EMPTY_TEXT,
    }
    directory = _option_contract(options)
    return ColoradoDocketPage(
        form_action=action,
        form_method=parser.form_method or "",
        form_fields=tuple(sorted(parser.form_fields)),
        options=options,
        rows=tuple(rows),
        result_state=result_state,
        total_count=total_count,
        range_start=range_start,
        range_end=range_end,
        page_index=page_index,
        next_page_url=(
            urljoin(page_url, parser.next_href)
            if parser.next_href
            else None
        ),
        export_url=(
            urljoin(page_url, parser.export_href)
            if parser.export_href
            else None
        ),
        printable_url=(
            urljoin(page_url, parser.printable_href)
            if parser.printable_href
            else None
        ),
        messages=(result_text,) if result_text else (),
        schema_fingerprint=schema_fingerprint(schema),
        directory_fingerprint=schema_fingerprint(
            {"kind": "colorado_judicial_court_directory", "options": directory}
        ),
        source_url=page_url,
    )


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _retry_after(response: Any) -> float | None:
    raw = _response_header(response, "retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _checked_status(response: Any, *, url: str) -> int:
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
    return status_code


def _response_url(response: Any, fallback: str) -> str:
    value = getattr(response, "url", None)
    return str(value) if value else fallback


def _search_parameter_fingerprint(
    parameters: Mapping[str, str],
) -> str:
    """Identify the exact source-native selector set behind a continuation."""

    return hashlib.sha256(
        canonical_json(dict(parameters)).encode("utf-8")
    ).hexdigest()


def _cursor_position(
    cursor: str | None,
    *,
    parameters: Mapping[str, str] | None = None,
) -> tuple[int, int]:
    if cursor is None:
        return 0, 0
    match = CURSOR_PATTERN.fullmatch(cursor)
    if match is None:
        raise ColoradoJudicialSelectionError(
            "invalid_cursor",
            (
                "cursor must be a versioned Colorado Judicial continuation "
                "returned by a prior search"
            ),
            details={"cursor": cursor},
        )
    if parameters is not None:
        expected = _search_parameter_fingerprint(parameters)
        observed = match.group("query")
        if observed != expected:
            raise ColoradoJudicialSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to different Colorado Judicial search parameters",
                details={
                    "cursor_query_fingerprint": observed,
                    "search_query_fingerprint": expected,
                },
            )
    return int(match.group("page")), int(match.group("row"))


def _cursor(
    page: int,
    row: int,
    *,
    parameters: Mapping[str, str],
) -> str:
    query_fingerprint = _search_parameter_fingerprint(parameters)
    return (
        f"colorado-judicial:{CURSOR_VERSION}:query:{query_fingerprint}:"
        f"page:{page}:row:{row}"
    )


class ColoradoJudicialClient:
    """Rate-limited retrying client for anonymous docket GET routes."""

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
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> Any:
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
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
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            _checked_status(response, url=url)
            return response
        raise TransportError(
            "Colorado Judicial docket request failed",
            url=url,
            details={"error": str(last_error or "retry exhausted")},
        )

    def _html_page(
        self,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> ColoradoDocketPage:
        response = self._request(DOCKET_URL, params=params)
        content_type = (
            _response_header(response, "content-type") or ""
        ).casefold()
        if content_type and "html" not in content_type:
            raise _source_schema_error(
                "Colorado Judicial docket returned a non-HTML response",
                details={"content_type": content_type},
            )
        fallback = (
            f"{DOCKET_URL}?{urlencode(params)}"
            if params
            else DOCKET_URL
        )
        return parse_docket_html(
            getattr(response, "text", ""),
            page_url=_response_url(response, fallback),
        )

    def bootstrap(self) -> ColoradoDocketPage:
        return self._html_page()

    def search(
        self,
        parameters: Mapping[str, str],
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ColoradoSearchBatch:
        page_index, row_offset = _cursor_position(
            cursor,
            parameters=parameters,
        )
        if row_offset < 0:
            raise ColoradoJudicialSelectionError(
                "invalid_cursor",
                "cursor row must not be negative",
            )
        collected: list[ColoradoDocketRow] = []
        pages_fetched = 0
        first_page: ColoradoDocketPage | None = None
        source_total = 0
        next_cursor: str | None = None
        seen_pages: set[int] = set()

        while True:
            if page_index in seen_pages:
                raise _source_schema_error(
                    "Colorado Judicial native pagination stalled",
                    details={"page": page_index},
                )
            seen_pages.add(page_index)
            query: dict[str, str | int] = dict(parameters)
            if page_index:
                query["page"] = page_index
            page = self._html_page(params=query)
            pages_fetched += 1
            if first_page is None:
                first_page = page
                source_total = int(page.total_count or 0)
            elif page.total_count != source_total:
                raise _source_schema_error(
                    "Colorado Judicial result total changed during pagination",
                    details={
                        "first_total": source_total,
                        "observed_total": page.total_count,
                    },
                )
            if page.result_state == "not_searched":
                raise ColoradoJudicialSelectionError(
                    "source_validation_error",
                    "Colorado Judicial Branch did not execute the query",
                    details={"messages": list(page.messages)},
                )
            if page.result_state == "no_results":
                if page_index or row_offset:
                    raise ColoradoJudicialSelectionError(
                        "cursor_out_of_range",
                        "cursor points beyond the available result pages",
                    )
                return ColoradoSearchBatch(
                    rows=(),
                    source_total_count=0,
                    pages_fetched=pages_fetched,
                    next_cursor=None,
                    first_page=page,
                )
            if row_offset > len(page.rows):
                raise ColoradoJudicialSelectionError(
                    "cursor_out_of_range",
                    "cursor row points beyond the native result page",
                    details={
                        "page": page_index,
                        "row": row_offset,
                        "page_rows": len(page.rows),
                    },
                )

            available = list(page.rows[row_offset:])
            remaining = None if limit is None else limit - len(collected)
            if remaining is not None and remaining < len(available):
                collected.extend(available[:remaining])
                next_cursor = _cursor(
                    page_index,
                    row_offset + remaining,
                    parameters=parameters,
                )
                break
            collected.extend(available)
            if remaining is not None and remaining == len(available):
                if page.next_page_url:
                    next_cursor = _cursor(
                        page_index + 1,
                        0,
                        parameters=parameters,
                    )
                break
            if not page.next_page_url:
                break
            parsed_next = parse_qs(urlparse(page.next_page_url).query).get(
                "page",
                [],
            )
            if not parsed_next or not parsed_next[-1].isdigit():
                raise _source_schema_error(
                    "Colorado Judicial next-page link changed",
                    details={"next_page_url": page.next_page_url},
                )
            next_page = int(parsed_next[-1])
            if next_page <= page_index:
                raise _source_schema_error(
                    "Colorado Judicial next-page link did not advance",
                    details={
                        "page": page_index,
                        "next_page": next_page,
                    },
                )
            page_index = next_page
            row_offset = 0

        assert first_page is not None
        return ColoradoSearchBatch(
            rows=tuple(collected),
            source_total_count=source_total,
            pages_fetched=pages_fetched,
            next_cursor=next_cursor,
            first_page=first_page,
        )

    def export(
        self,
        parameters: Mapping[str, str],
    ) -> tuple[ColoradoDocketPage, ColoradoExport | None]:
        first_page = self._html_page(params=parameters)
        if first_page.result_state == "no_results":
            return first_page, None
        if first_page.result_state != "results":
            raise ColoradoJudicialSelectionError(
                "source_validation_error",
                "Colorado Judicial Branch did not execute the export query",
                details={"messages": list(first_page.messages)},
            )
        if not first_page.export_url:
            raise _source_schema_error(
                "Colorado Judicial result page lacks its export link"
            )
        response = self._request(first_page.export_url)
        status_code = int(getattr(response, "status_code", 0))
        content = getattr(response, "content", b"")
        if not isinstance(content, bytes):
            content = bytes(content)
        if status_code == 204 or not content:
            raise ColoradoExportUnavailableError(
                "Colorado Judicial export returned no artifact",
                url=first_page.export_url,
                details={"status_code": status_code},
            )
        disposition = _response_header(response, "content-disposition") or ""
        filename_match = re.search(
            r"""filename\*?=(?:UTF-8''|")?([^";]+)""",
            disposition,
            flags=re.IGNORECASE,
        )
        return first_page, ColoradoExport(
            source_url=first_page.export_url,
            content=content,
            media_type=_response_header(response, "content-type"),
            filename=(
                filename_match.group(1).strip()
                if filename_match
                else None
            ),
            status_code=status_code,
        )


def _offered_options(
    page: ColoradoDocketPage,
    name: str,
) -> tuple[SourceOption, ...]:
    values = page.options.get(name, ())
    return tuple(
        option
        for option in values
        if option.value not in {"", "-1"}
    )


def _resolve_option(
    page: ColoradoDocketPage,
    name: str,
    requested: str | None,
) -> str | None:
    if requested is None:
        return None
    raw = requested.strip()
    options = _offered_options(page, name)
    by_value = {option.value: option.value for option in options}
    if raw in by_value:
        return by_value[raw]
    by_label = {
        option.label.casefold(): option.value
        for option in options
    }
    resolved = by_label.get(raw.casefold())
    if resolved is not None:
        return resolved
    raise ColoradoJudicialSelectionError(
        "invalid_source_option",
        f"{requested!r} is not offered for --{name.replace('_', '-')}",
        details={
            "field": name,
            "value": requested,
            "available": [option.to_dict() for option in options],
        },
    )


def _iso_date(value: str, field_name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ColoradoJudicialSelectionError(
            "invalid_date_filter",
            f"{field_name} must be an ISO calendar date",
            details={"field": field_name, "value": value},
        ) from error


def search_parameters(
    args: argparse.Namespace,
    directory: ColoradoDocketPage,
    *,
    probe_defaults: bool = False,
) -> dict[str, str]:
    """Validate caller selectors and produce source-native GET parameters."""

    courthouse = getattr(args, "courthouse", None)
    specific_date = getattr(args, "specific_date", None)
    if probe_defaults:
        if courthouse is None:
            offered = _offered_options(directory, "courthouse")
            if not offered:
                raise _source_schema_error(
                    "Colorado Judicial court directory has no courthouses"
                )
            courthouse = offered[0].value
        if specific_date is None:
            specific_date = datetime.now(DENVER_TIMEZONE).date().isoformat()

    date_range = getattr(args, "date_range", None)
    if specific_date:
        if date_range and date_range != "specific_date":
            raise ColoradoJudicialSelectionError(
                "conflicting_date_filters",
                "--date cannot be combined with a non-specific --date-range",
            )
        date_range = "specific_date"
        specific_date = _iso_date(specific_date, "--date")
    else:
        date_range = date_range or "1_week"
        if date_range == "specific_date":
            raise ColoradoJudicialSelectionError(
                "specific_date_required",
                "--date-range specific_date requires --date",
            )

    individual_names = [
        _clean_text(getattr(args, "party_first_name", None)),
        _clean_text(getattr(args, "party_last_name", None)),
    ]
    business_name = _clean_text(getattr(args, "business_name", None))
    if business_name and any(individual_names):
        raise ColoradoJudicialSelectionError(
            "conflicting_party_filters",
            "business and individual party filters cannot be combined",
        )
    attorney_names = [
        _clean_text(getattr(args, "attorney_first_name", None)),
        _clean_text(getattr(args, "attorney_last_name", None)),
    ]
    bar_number = _clean_text(getattr(args, "attorney_bar_number", None))
    if bar_number and any(attorney_names):
        raise ColoradoJudicialSelectionError(
            "conflicting_attorney_filters",
            "attorney name and bar-number filters cannot be combined",
        )

    year = _clean_text(getattr(args, "case_year", None))
    sequence = _clean_text(getattr(args, "case_sequence", None))
    if year and not re.fullmatch(r"\d{4}", year):
        raise ColoradoJudicialSelectionError(
            "invalid_case_year",
            "--case-year must contain four digits",
        )
    if sequence and not re.fullmatch(r"\d{1,6}", sequence):
        raise ColoradoJudicialSelectionError(
            "invalid_case_sequence",
            "--case-sequence must contain one to six digits",
        )
    if bar_number and not re.fullmatch(r"\d{1,6}", bar_number):
        raise ColoradoJudicialSelectionError(
            "invalid_attorney_bar_number",
            "--attorney-bar-number must contain one to six digits",
        )

    parameters: dict[str, str] = {
        "date_range": date_range,
        "name_type": "company" if business_name else "individual",
        "attorney_type": "number" if bar_number else "name",
    }
    if specific_date:
        parameters["specific_date"] = specific_date
    option_inputs = {
        "district": getattr(args, "judicial_district", None),
        "county": getattr(args, "county", None),
        "courthouse": courthouse,
        "court": getattr(args, "court_type", None),
        "case_class": getattr(args, "case_class", None),
    }
    for source_name, value in option_inputs.items():
        resolved = _resolve_option(directory, source_name, value)
        if resolved is not None:
            parameters[source_name] = resolved
    text_inputs = {
        "division": getattr(args, "division", None),
        "four_digit_year": year,
        "case_sequence": sequence,
        "first_name": individual_names[0],
        "last_name": individual_names[1],
        "company_name": business_name,
        "bar_number": bar_number,
        "attorney_first_name": attorney_names[0],
        "attorney_last_name": attorney_names[1],
    }
    for key, value in text_inputs.items():
        normalized = _clean_text(value)
        if normalized is not None:
            parameters[key] = normalized

    non_date_fields = set(parameters).difference(
        {"date_range", "specific_date", "name_type", "attorney_type"}
    )
    if not non_date_fields:
        raise ColoradoJudicialSelectionError(
            "search_selector_required",
            "at least one filter in addition to date is required",
        )
    return parameters


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:48] or "court"


def _court_payload(location: str) -> dict[str, Any]:
    digest = hashlib.sha256(location.casefold().encode("utf-8")).hexdigest()
    level = "trial"
    lowered = location.casefold()
    for candidate in ("district", "county", "probate", "juvenile"):
        if candidate in lowered:
            level = candidate
            break
    return {
        "court_id": f"co-judicial-{_slug(location)}-{digest[:8]}",
        "native_court_id": f"location-name-sha256:{digest}",
        "name": location,
        "state_code": STATE_CODE,
        "county_geoid": None,
        "court_level": level,
        "official_url": DOCKET_URL,
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_type": "statewide_trial_court_docket_calendar",
        "fields": [
            "date",
            "time",
            "duration",
            "name",
            "case_number",
            "hearing_type",
            "location",
            "appearance_type",
            "courtroom",
        ],
        "native_pagination": True,
        "filing_images_available": False,
    }


def _event_date(value: str) -> str:
    for date_format in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Colorado Judicial hearing has unparseable date {value!r}")


def _event_time(value: str) -> str:
    for time_format in ("%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(
                value.upper(),
                time_format,
            ).time().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Colorado Judicial hearing has unparseable time {value!r}")


def normalize_row(
    row: ColoradoDocketRow,
    *,
    schema: str,
    source_url: str,
) -> dict[str, Any]:
    """Normalize one native result row as an ingestible docket wrapper."""

    event_date = _event_date(row.hearing_date)
    event_time = _event_time(row.hearing_time)
    court = _court_payload(row.location)
    case_ref = canonical_court_ref(
        SOURCE_ID,
        court["court_id"],
        row.case_number,
    )
    hearing_basis = {
        "case_number": row.case_number.strip().upper(),
        "event_date": event_date,
        "event_time": event_time,
        "duration": (_clean_text(row.duration) or "").casefold(),
        "hearing_type": row.hearing_type.casefold(),
        "location": row.location.casefold(),
        "appearance_type": (
            _clean_text(row.appearance_type) or ""
        ).casefold(),
        "courtroom": row.courtroom.casefold(),
    }
    hearing_digest = hashlib.sha256(
        canonical_json(hearing_basis).encode("utf-8")
    ).hexdigest()
    row_basis = {
        **hearing_basis,
        "calendar_name": row.calendar_name.casefold(),
    }
    row_digest = hashlib.sha256(
        canonical_json(row_basis).encode("utf-8")
    ).hexdigest()
    native_entry_id = f"docket-row:{row_digest}"
    hearing_id = f"calendar-hearing:{hearing_digest}"
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court["court_id"],
            row.case_number,
            "docket",
            native_entry_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "docket_entry",
        "case": {
            "canonical_ref": case_ref,
            "source_id": SOURCE_ID,
            "court": court,
            "raw_case_number": row.case_number,
            "display_case_number": row.case_number,
            "source_internal_id": None,
            "caption": None,
            "case_type": None,
            "filing_date": None,
            "status": None,
            "access_state": "public",
            "certified_record": False,
            "source_url": source_url,
            "parties": [],
            "documents": [],
            "source_scope": _source_scope(),
        },
        "native_entry_id": native_entry_id,
        "identity_kind": "source_fields_sha256",
        "identity_basis": row_basis,
        "hearing_id": hearing_id,
        "hearing_identity_basis": hearing_basis,
        "event_type": "scheduled_hearing",
        "event_code": row.hearing_type,
        "raw_text": row.hearing_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "source_event_date_raw": row.hearing_date,
        "source_event_time_raw": row.hearing_time,
        "duration_raw": row.duration,
        "calendar_name": row.calendar_name,
        "location": row.location,
        "appearance_type": row.appearance_type,
        "courtroom": row.courtroom,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "source_scope": _source_scope(),
        "source_fields": row.to_dict(),
        "schema_fingerprint": schema,
    }


def _directory_record(page: ColoradoDocketPage) -> dict[str, Any]:
    options = _option_contract(page.options)
    return {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/directory",
        "source_id": SOURCE_ID,
        "record_kind": "court_directory",
        "source_url": DOCKET_URL,
        "form_action": urlparse(urljoin(DOCKET_URL, page.form_action)).path,
        "form_method": page.form_method,
        "options": options,
        "counts": {key: len(value) for key, value in options.items()},
        "schema_fingerprint": page.schema_fingerprint,
        "directory_fingerprint": page.directory_fingerprint,
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters = {
        key: value
        for key, value in {
            "judicial_district": getattr(args, "judicial_district", None),
            "county": getattr(args, "county", None),
            "courthouse": getattr(args, "courthouse", None),
            "court_type": getattr(args, "court_type", None),
            "division": getattr(args, "division", None),
            "date_range": getattr(args, "date_range", None),
            "specific_date": getattr(args, "specific_date", None),
            "case_year": getattr(args, "case_year", None),
            "case_class": getattr(args, "case_class", None),
            "case_sequence": getattr(args, "case_sequence", None),
            "party_first_name": getattr(args, "party_first_name", None),
            "party_last_name": getattr(args, "party_last_name", None),
            "business_name": getattr(args, "business_name", None),
            "attorney_bar_number": getattr(
                args,
                "attorney_bar_number",
                None,
            ),
            "attorney_first_name": getattr(
                args,
                "attorney_first_name",
                None,
            ),
            "attorney_last_name": getattr(
                args,
                "attorney_last_name",
                None,
            ),
        }.items()
        if value not in {None, ""}
    }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Colorado",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
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
    error: ColoradoJudicialSelectionError,
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


def _write_export(
    artifact: ColoradoExport,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str]]:
    destination_value = getattr(args, "destination", None)
    destination = (
        Path(destination_value).expanduser()
        if destination_value
        else None
    )
    if destination is not None:
        if destination.exists() and not getattr(args, "overwrite", False):
            raise OSError(
                f"destination exists; pass --overwrite: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(artifact.content)
    digest = hashlib.sha256(artifact.content).hexdigest()
    record = {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/export/{digest}",
        "source_id": SOURCE_ID,
        "record_kind": "source_generated_export",
        "source_url": artifact.source_url,
        "status_code": artifact.status_code,
        "media_type": artifact.media_type,
        "source_filename": artifact.filename,
        "size": len(artifact.content),
        "sha256": digest,
        "storage_path": (
            str(destination.resolve()) if destination is not None else None
        ),
    }
    return record, [record["storage_path"]] if record["storage_path"] else []


def _execute_command(
    args: argparse.Namespace,
    client: ColoradoJudicialClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    directory = client.bootstrap()
    if args.command == "courts":
        return PublicRecordsResult.success(
            query,
            [_directory_record(directory)],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "search":
        parameters = search_parameters(args, directory)
        batch = client.search(
            parameters,
            limit=args.limit,
            cursor=args.cursor,
        )
        records = [
            normalize_row(
                row,
                schema=batch.first_page.schema_fingerprint,
                source_url=batch.first_page.source_url,
            )
            for row in batch.rows
        ]
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=batch.next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        parameters = search_parameters(
            args,
            directory,
            probe_defaults=True,
        )
        batch = client.search(parameters, limit=1)
        export_status = "not_advertised"
        if batch.first_page.export_url:
            try:
                _page, artifact = client.export(parameters)
                export_status = "available" if artifact else "no_results"
            except ColoradoExportUnavailableError:
                export_status = "unavailable"
        record = {
            "canonical_ref": f"STATECOURT:{SOURCE_ID}/probe/docket-search",
            "source_id": SOURCE_ID,
            "record_kind": "source_health_check",
            "source_url": DOCKET_URL,
            "query_parameters": parameters,
            "directory_counts": {
                key: len(_offered_options(directory, key))
                for key in OPTION_FIELDS
            },
            "result_state": batch.first_page.result_state,
            "source_total_count": batch.source_total_count,
            "parsed_row_count": len(batch.first_page.rows),
            "native_pagination": bool(batch.first_page.next_page_url),
            "export_link_advertised": bool(batch.first_page.export_url),
            "export_status": export_status,
            "schema_fingerprint": directory.schema_fingerprint,
            "directory_fingerprint": directory.directory_fingerprint,
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "export":
        parameters = search_parameters(args, directory)
        first_page, artifact = client.export(parameters)
        if artifact is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        record, refs = _write_export(artifact, args)
        record["schema_fingerprint"] = first_page.schema_fingerprint
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=refs,
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Colorado Judicial command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: ColoradoJudicialClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one statewide docket-calendar operation."""

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

    limits = decision.get("limits") or {}
    catalog_interval = float(limits.get("minimum_interval_seconds") or 0)
    source_client = client or ColoradoJudicialClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        rate_limiter=MinimumIntervalRateLimiter(
            max(args.minimum_interval, catalog_interval)
        ),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except ColoradoJudicialSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="export_write_failed",
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
        summary=f"Colorado Judicial {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Colorado Judicial {args.command}: {result.status.value} "
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
                f"{record.get('location') or '?'} | "
                f"{record.get('calendar_name') or '?'}"
            )
        else:
            print(f"  {record.get('record_kind') or 'record'}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
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


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--judicial-district")
    parser.add_argument("--county")
    parser.add_argument("--courthouse")
    parser.add_argument("--court-type")
    parser.add_argument("--division")
    parser.add_argument("--date-range", choices=DATE_RANGES)
    parser.add_argument(
        "--date",
        dest="specific_date",
        help="Specific hearing date as YYYY-MM-DD",
    )
    parser.add_argument("--case-year")
    parser.add_argument("--case-class")
    parser.add_argument("--case-sequence")
    parser.add_argument("--party-first-name")
    parser.add_argument("--party-last-name")
    parser.add_argument("--business-name")
    parser.add_argument("--attorney-bar-number")
    parser.add_argument("--attorney-first-name")
    parser.add_argument("--attorney-last-name")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official Colorado Judicial Branch statewide "
            "trial-court docket calendar"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    courts = subparsers.add_parser(
        "courts",
        help="Return the live judicial district/county/courthouse directory",
    )
    _add_runtime_and_output(courts)

    search = subparsers.add_parser(
        "search",
        help="Search docket-calendar rows and follow native pages",
    )
    _add_search_filters(search)
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Caller-selected maximum; omitted exhausts native pages",
    )
    search.add_argument(
        "--cursor",
        help="Continuation cursor returned by a prior search",
    )
    _add_runtime_and_output(search)

    export = subparsers.add_parser(
        "export",
        help="Fetch the source-generated export for a docket query",
    )
    _add_search_filters(export)
    export.add_argument("destination", nargs="?")
    export.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(export)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the live form, directory, search, and export status",
    )
    probe.add_argument("--courthouse")
    probe.add_argument("--date", dest="specific_date")
    probe.set_defaults(date_range=None)
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
