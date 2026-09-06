#!/usr/bin/env python3
"""Query Georgia AOC's public Court Personnel Directory.

The directory is a current-state personnel snapshot published by the Judicial
Council of Georgia / Administrative Office of the Courts through public Knack
views. Search and detail operations use only the published view-scoped GET
routes exposed by the application.

Examples:
    uv run python tools/query_georgia_court_directory.py manifest --json
    uv run python tools/query_georgia_court_directory.py search \
        --directory-section "Superior Court Clerks" --output /tmp/ga-clerks.json
    uv run python tools/query_georgia_court_directory.py search \
        --court-class Superior --county Fulton --details --json
    uv run python tools/query_georgia_court_directory.py detail \
        58af01d3ce9168f520c4cec9 --json
    uv run python tools/query_georgia_court_directory.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

import requests

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
        system_trust_session,
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
        system_trust_session,
    )


SOURCE_ID = "us-ga-aoc-court-personnel-directory"
STATE_CODE = "GA"
STATE_GEOID = "13"
AUTHORITY = (
    "Judicial Council of Georgia, Administrative Office of the Courts"
)
LANDING_URL = "https://georgiacourts.gov/georgia-courts-directory/"
APP_URL = "https://georgiacourts.knack.com/gcd2/"
APP_ID = "582a4334ad388bdb3448f61a"
LOADER_URL = f"https://loader.knack.com/v1/applications/{APP_ID}"
SEARCH_SCENE = "scene_1"
SEARCH_VIEW = "view_5"
DETAIL_SCENE = "scene_4"
DETAIL_VIEW = "view_6"
SEARCH_API_URL = (
    f"https://api.knack.com/v1/pages/{SEARCH_SCENE}/views/"
    f"{SEARCH_VIEW}/records"
)
DETAIL_API_URL = (
    f"https://api.knack.com/v1/pages/{DETAIL_SCENE}/views/"
    f"{DETAIL_VIEW}/records"
)
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_PAGE_SIZE = 100
DEFAULT_LIMIT = 100
CURSOR_VERSION = "v1"
CURSOR_RE = re.compile(
    r"^ga-aoc-directory:v1:query:(?P<query>[0-9a-f]{16}):"
    r"size:(?P<size>[1-9][0-9]*):page:(?P<page>[1-9][0-9]*):"
    r"row:(?P<row>[0-9]+)$"
)
TAG_RE = re.compile(r"<[^>]+>")

SEARCH_FIELD_DEFINITIONS: Mapping[str, Mapping[str, str]] = {
    "first": {
        "label": "First",
        "field": "field_1",
        "operator": "contains",
        "result_field": "field_1",
    },
    "middle": {
        "label": "Middle",
        "field": "field_4",
        "operator": "contains",
        "result_field": "field_4",
    },
    "last": {
        "label": "Last",
        "field": "field_2",
        "operator": "contains",
        "result_field": "field_2",
    },
    "city": {
        "label": "City",
        "field": "field_79",
        "operator": "contains",
        "result_field": "field_8",
        "input_scope": (
            "source concatenation of ordinary city, municipal-judge city, "
            "and chief-municipal-judge city"
        ),
    },
    "county": {
        "label": "County",
        "field": "field_15",
        "operator": "contains",
        "result_field": "field_15",
    },
    "circuit": {
        "label": "Circuit",
        "field": "field_14",
        "operator": "contains",
        "result_field": "field_14",
    },
    "court_class": {
        "label": "Court Class",
        "field": "field_18",
        "operator": "is",
        "result_field": "detail_only",
    },
    "directory_section": {
        "label": "Directory Section",
        "field": "field_19",
        "operator": "is",
        "result_field": "detail_only",
    },
}

DETAIL_FIELD_DEFINITIONS: Mapping[str, Mapping[str, str]] = {
    "prefix_or_title": {
        "field": "field_3",
        "source_label": "Prefix",
    },
    "chief_magistrate_indicator": {
        "field": "field_26",
        "source_model_name": "ChiefMagistrate",
    },
    "first": {"field": "field_1", "source_label": "First"},
    "middle": {"field": "field_4", "source_label": "Middle"},
    "last": {"field": "field_2", "source_label": "Last"},
    "suffix": {"field": "field_5", "source_label": "Suffix"},
    "address_1": {"field": "field_6"},
    "address_2": {"field": "field_7"},
    "address_3": {"field": "field_20"},
    "city": {"field": "field_8"},
    "state": {"field": "field_9"},
    "postal_code": {"field": "field_10"},
    "phone": {"field": "field_11"},
    "fax": {"field": "field_12"},
    "email": {"field": "field_13"},
    "county": {"field": "field_15"},
    "circuit": {"field": "field_14"},
    "municipal_judge_city": {"field": "field_27"},
    "chief_municipal_judge_city": {"field": "field_28"},
    "court_class": {"field": "field_18"},
    "accountability_court_type": {"field": "field_85"},
    "judicial_administration": {"field": "field_86"},
    "directory_section": {"field": "field_19"},
    "council_or_agency": {"field": "field_84"},
    "display_email": {"field": "field_99"},
}

COURT_CLASS_OPTIONS = (
    "Accountability Court",
    "Appeals",
    "Court of Appeals of Georgia",
    "Federal",
    "Judicial Council/Administrative Office of the Courts",
    "Juvenile",
    "Magistrate",
    "Municipal",
    "Probate",
    "Special",
    "State",
    "Superior",
    "Supreme Court of Georgia",
    "US Bankruptcy",
    "US District",
    "US Magistrate",
    "n/a",
    "State-wide Business Court",
)

DIRECTORY_SECTION_OPTIONS = (
    "Accountability Court Coordinators",
    "Council of Magistrate Court Judges",
    "Court Administrators",
    "Court Councils and Agencies",
    "Court of Appeals",
    "Court of Appeals of Georgia",
    "District Attorneys",
    "Eleventh Circuit Court of Appeals",
    "Judicial Administrative Districts",
    "Juvenile Court Clerks",
    "Juvenile Court Judges",
    "Magistrate Court Judges",
    "Magistrate Judges",
    "Municipal Court Judges",
    "Office of State Administrative Hearings",
    "Probate Court Judges",
    "Public Defenders",
    "Senior Judges",
    "Solicitors General",
    "Special Courts",
    "State Court Clerks",
    "State Court Judges",
    "Superior Court Clerks",
    "Superior Court Judges",
    "Supreme Court",
    "US Bankruptcy Court",
    "US District Court-Middle and Southern",
    "US District Court-Northern",
    "n/a",
)

SEARCH_RESULT_FIELDS = frozenset(
    {
        "id",
        "field_3",
        "field_1",
        "field_4",
        "field_2",
        "field_8",
        "field_15",
        "field_14",
    }
)
DETAIL_SENTINEL_FIELDS = frozenset(
    {
        "id",
        "field_1",
        "field_2",
        "field_18_raw",
        "field_19_raw",
        "field_99_raw",
    }
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Georgia AOC Court Personnel Directory",
    source_role="official_statewide_court_personnel_directory",
    base_url=LANDING_URL,
    dataset_id=f"knack:{APP_ID}:{SEARCH_SCENE}:{SEARCH_VIEW}",
    metadata={
        "authority": AUTHORITY,
        "application_url": APP_URL,
        "application_id": APP_ID,
        "access": "anonymous_published_view",
        "coverage": "current_directory_snapshot",
        "case_records": False,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Georgia",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_court_personnel_directory"},
)

SOURCE_WARNINGS = (
    "The directory is a current personnel snapshot, not a historical roster "
    "or case index.",
    "Court Class and Directory Section are separate source classifications and "
    "are returned separately.",
    "The native City search field also searches municipal-judge city fields; "
    "the compact result view displays only the ordinary City field.",
    "The source field labeled Prefix also contains job titles in some records; "
    "the adapter preserves it as prefix_or_title rather than inferring a role.",
    "Continuation cursors are bound to filters and page size, but the publisher "
    "can update the current snapshot between separate calls.",
    "Official local court and county sites, Georgia AOC case-access routes, and "
    "GSCCCA systems provide complementary records under their own authority.",
)


class GeorgiaDirectorySelectionError(ValueError):
    """Structured caller selection or cursor error."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query",
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class DirectoryPage:
    """One native Knack result page."""

    records: tuple[Mapping[str, Any], ...]
    current_page: int
    total_pages: int
    total_records: int
    requested_page_size: int
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class DirectoryDetail:
    """One exact record from the published detail view."""

    record: Mapping[str, Any]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class DirectorySearchBatch:
    """Bounded records and continuation state across native pages."""

    records: tuple[Mapping[str, Any], ...]
    source_total_count: int
    source_total_pages: int
    pages_fetched: int
    requests_made: int
    next_cursor: str | None
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        value = (
            value.get("label")
            or value.get("name")
            or value.get("identifier")
            or value.get("value")
        )
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value if item is not None)
    cleaned = html.unescape(TAG_RE.sub(" ", str(value)))
    cleaned = " ".join(cleaned.split())
    return cleaned or None


def _source_value(record: Mapping[str, Any], field: str) -> Any:
    raw_field = f"{field}_raw"
    return record[raw_field] if raw_field in record else record.get(field)


def _field_text(record: Mapping[str, Any], field: str) -> str | None:
    return _text(_source_value(record, field))


def _choice_values(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    normalized: list[str] = []
    for item in values:
        text = _text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _source_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _schema_fingerprint(
    payload: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> str:
    """Fingerprint response structure without hashing mutable row values."""

    return sha256_fingerprint(
        {
            "container_fields": sorted(str(key) for key in payload),
            "record_field_sets": sorted(
                {
                    tuple(sorted(str(key) for key in record))
                    for record in records
                }
            ),
        }
    )


def _integer_field(
    payload: Mapping[str, Any],
    name: str,
    *,
    source_url: str,
) -> int:
    value = payload.get(name)
    if isinstance(value, bool):
        value = None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            f"Georgia directory {name} is not an integer",
            url=source_url,
            details={"value": value},
        ) from error
    return parsed


def parse_search_page(
    payload: Any,
    *,
    requested_page: int,
    requested_page_size: int,
    source_url: str = SEARCH_API_URL,
) -> DirectoryPage:
    """Validate and normalize one published search-view response."""

    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "Georgia directory search response is not an object",
            url=source_url,
        )
    records_value = payload.get("records")
    if not isinstance(records_value, list):
        raise SourceSchemaError(
            "Georgia directory search response has no records array",
            url=source_url,
        )
    current_page = _integer_field(
        payload,
        "current_page",
        source_url=source_url,
    )
    total_pages = _integer_field(
        payload,
        "total_pages",
        source_url=source_url,
    )
    total_records = _integer_field(
        payload,
        "total_records",
        source_url=source_url,
    )
    if current_page != requested_page:
        raise SourceSchemaError(
            "Georgia directory returned a different native page",
            url=source_url,
            details={
                "requested_page": requested_page,
                "current_page": current_page,
            },
        )
    if total_pages < 0 or total_records < 0:
        raise SourceSchemaError(
            "Georgia directory returned negative pagination values",
            url=source_url,
        )
    expected_pages = (
        (total_records + requested_page_size - 1) // requested_page_size
        if total_records
        else 0
    )
    if total_pages != expected_pages:
        raise SourceSchemaError(
            "Georgia directory pagination totals are inconsistent",
            url=source_url,
            details={
                "total_records": total_records,
                "total_pages": total_pages,
                "expected_pages": expected_pages,
                "requested_page_size": requested_page_size,
            },
        )
    if total_pages and current_page > total_pages:
        raise GeorgiaDirectorySelectionError(
            "cursor_out_of_range",
            "continuation cursor points beyond Georgia directory results",
            details={
                "current_page": current_page,
                "total_pages": total_pages,
            },
        )
    if not total_pages and current_page != 1:
        raise GeorgiaDirectorySelectionError(
            "cursor_out_of_range",
            "continuation cursor points beyond an empty result set",
        )
    if len(records_value) > requested_page_size:
        raise SourceSchemaError(
            "Georgia directory returned more rows than requested",
            url=source_url,
            details={
                "row_count": len(records_value),
                "requested_page_size": requested_page_size,
            },
        )

    records: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(records_value):
        if not isinstance(item, Mapping):
            raise SourceSchemaError(
                "Georgia directory search row is not an object",
                url=source_url,
                details={"row_index": index},
            )
        missing = sorted(SEARCH_RESULT_FIELDS - set(item))
        if missing:
            raise SourceSchemaError(
                "Georgia directory search fields changed",
                url=source_url,
                details={"row_index": index, "missing_fields": missing},
            )
        record_id = _text(item.get("id"))
        if not record_id:
            raise SourceSchemaError(
                "Georgia directory search row has no record ID",
                url=source_url,
                details={"row_index": index},
            )
        if record_id in seen_ids:
            raise SourceSchemaError(
                "Georgia directory repeated a record ID on one page",
                url=source_url,
                details={"record_id": record_id},
            )
        seen_ids.add(record_id)
        records.append(dict(item))
    if total_records and not records:
        raise SourceSchemaError(
            "Georgia directory returned an empty page inside result bounds",
            url=source_url,
            details={
                "current_page": current_page,
                "total_pages": total_pages,
            },
        )
    return DirectoryPage(
        records=tuple(records),
        current_page=current_page,
        total_pages=total_pages,
        total_records=total_records,
        requested_page_size=requested_page_size,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(payload, records),
    )


def parse_detail(
    payload: Any,
    *,
    requested_record_id: str,
    source_url: str,
) -> DirectoryDetail:
    """Validate one record from the public detail view."""

    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "Georgia directory detail response is not an object",
            url=source_url,
        )
    missing = sorted(DETAIL_SENTINEL_FIELDS - set(payload))
    if missing:
        raise SourceSchemaError(
            "Georgia directory detail fields changed",
            url=source_url,
            details={"missing_fields": missing},
        )
    observed_id = _text(payload.get("id"))
    if observed_id != requested_record_id:
        raise SourceSchemaError(
            "Georgia directory detail returned a different record",
            url=source_url,
            details={
                "requested_record_id": requested_record_id,
                "observed_record_id": observed_id,
            },
        )
    record = dict(payload)
    return DirectoryDetail(
        record=record,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(record, [record]),
    )


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return _text(value)
    return None


def _retry_after(response: Any) -> float | None:
    value = _response_header(response, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _checked_status(response: Any, *, url: str) -> None:
    status_code = int(getattr(response, "status_code", 0))
    response_text = str(getattr(response, "text", ""))
    if status_code == 429:
        raise RateLimitedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code in {401, 403}:
        raise RestrictedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code == 451:
        raise TermsBlockedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(
            status_code,
            url=url,
            response_text=response_text,
        )


class GeorgiaCourtDirectoryClient:
    """Paced client for the directory's published Knack views."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.request_count = 0
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Ithildin public-record source adapter",
            "X-Knack-Application-Id": APP_ID,
            "X-Knack-REST-API-Key": "knack",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> Any:
        response: Any | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=dict(params or {}),
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Georgia court directory request failed",
                        url=url,
                        details={"error": str(error), "attempts": attempt},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(getattr(response, "status_code", 0))
            if allow_not_found and status_code == 404:
                return response
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
            "Georgia court directory request produced no response",
            url=url,
        )

    @staticmethod
    def _json(response: Any, *, url: str) -> Any:
        try:
            return response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SourceSchemaError(
                "Georgia court directory returned invalid JSON",
                url=url,
            ) from error

    def search_page(
        self,
        filters: Sequence[Mapping[str, str]],
        *,
        page: int,
        page_size: int,
    ) -> DirectoryPage:
        params: dict[str, Any] = {
            "page": page,
            "rows_per_page": page_size,
        }
        if filters:
            params["filters"] = canonical_json(list(filters))
        response = self._request(SEARCH_API_URL, params=params)
        source_url = str(getattr(response, "url", SEARCH_API_URL))
        return parse_search_page(
            self._json(response, url=source_url),
            requested_page=page,
            requested_page_size=page_size,
            source_url=source_url,
        )

    def detail(self, record_id: str) -> DirectoryDetail | None:
        clean_id = record_id.strip()
        if not clean_id:
            raise GeorgiaDirectorySelectionError(
                "record_id_required",
                "Georgia directory record ID must not be blank",
            )
        url = f"{DETAIL_API_URL}/{quote(clean_id, safe='')}"
        response = self._request(url, allow_not_found=True)
        if int(getattr(response, "status_code", 0)) == 404:
            return None
        source_url = str(getattr(response, "url", url))
        return parse_detail(
            self._json(response, url=source_url),
            requested_record_id=clean_id,
            source_url=source_url,
        )

    def search(
        self,
        filters: Sequence[Mapping[str, str]],
        *,
        limit: int | None,
        cursor: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> DirectorySearchBatch:
        if limit is not None and limit <= 0:
            raise GeorgiaDirectorySelectionError(
                "invalid_limit",
                "search limit must be positive",
            )
        if page_size <= 0:
            raise GeorgiaDirectorySelectionError(
                "invalid_page_size",
                "page size must be positive",
            )
        page_number, row_offset = _cursor_position(
            cursor,
            filters=filters,
            page_size=page_size,
        )
        start_request_count = self.request_count
        collected: list[Mapping[str, Any]] = []
        seen_ids: set[str] = set()
        pages_fetched = 0
        source_total: int | None = None
        source_total_pages: int | None = None
        source_urls: list[str] = []
        schema_fingerprints: list[str] = []
        next_cursor: str | None = None

        while True:
            page = self.search_page(
                filters,
                page=page_number,
                page_size=page_size,
            )
            pages_fetched += 1
            source_urls.append(page.source_url)
            if page.schema_fingerprint not in schema_fingerprints:
                schema_fingerprints.append(page.schema_fingerprint)
            if source_total is None:
                source_total = page.total_records
                source_total_pages = page.total_pages
            elif (
                page.total_records != source_total
                or page.total_pages != source_total_pages
            ):
                raise SourceSchemaError(
                    "Georgia directory totals changed during pagination",
                    url=page.source_url,
                    details={
                        "initial_total_records": source_total,
                        "observed_total_records": page.total_records,
                        "initial_total_pages": source_total_pages,
                        "observed_total_pages": page.total_pages,
                    },
                )

            if row_offset > len(page.records):
                raise GeorgiaDirectorySelectionError(
                    "cursor_out_of_range",
                    "cursor row points beyond the native Georgia directory page",
                    details={
                        "page": page_number,
                        "row": row_offset,
                        "page_rows": len(page.records),
                    },
                )
            available = list(page.records[row_offset:])
            remaining = None if limit is None else limit - len(collected)
            if remaining is not None and remaining < len(available):
                selected = available[:remaining]
                for record in selected:
                    record_id = str(record["id"])
                    if record_id in seen_ids:
                        raise SourceSchemaError(
                            "Georgia directory repeated a record across pages",
                            url=page.source_url,
                            details={"record_id": record_id},
                        )
                    seen_ids.add(record_id)
                collected.extend(selected)
                next_cursor = _cursor(
                    filters,
                    page_size=page_size,
                    page=page_number,
                    row=row_offset + remaining,
                )
                break

            collected.extend(available)
            for record in available:
                record_id = str(record["id"])
                if record_id in seen_ids:
                    raise SourceSchemaError(
                        "Georgia directory repeated a record across pages",
                        url=page.source_url,
                        details={"record_id": record_id},
                    )
                seen_ids.add(record_id)

            if remaining is not None and remaining == len(available):
                if page_number < page.total_pages:
                    next_cursor = _cursor(
                        filters,
                        page_size=page_size,
                        page=page_number + 1,
                        row=0,
                    )
                break
            if page_number >= page.total_pages:
                break
            page_number += 1
            row_offset = 0

        return DirectorySearchBatch(
            records=tuple(collected),
            source_total_count=int(source_total or 0),
            source_total_pages=int(source_total_pages or 0),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - start_request_count,
            next_cursor=next_cursor,
            source_urls=tuple(dict.fromkeys(source_urls)),
            schema_fingerprints=tuple(schema_fingerprints),
        )


def build_filters(
    values: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    """Translate semantic CLI fields to published Knack view rules."""

    filters: list[dict[str, str]] = []
    for name, definition in SEARCH_FIELD_DEFINITIONS.items():
        value = _text(values.get(name))
        if value is None:
            continue
        filters.append(
            {
                "field": definition["field"],
                "operator": definition["operator"],
                "value": value,
            }
        )
    return tuple(filters)


def _filter_fingerprint(filters: Sequence[Mapping[str, str]]) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "source_id": SOURCE_ID,
                "filters": list(filters),
            }
        ).encode("utf-8")
    ).hexdigest()[:16]


def _cursor_position(
    cursor: str | None,
    *,
    filters: Sequence[Mapping[str, str]],
    page_size: int,
) -> tuple[int, int]:
    if cursor is None:
        return 1, 0
    match = CURSOR_RE.fullmatch(cursor)
    if match is None:
        raise GeorgiaDirectorySelectionError(
            "invalid_cursor",
            "cursor does not match the Georgia directory cursor format",
        )
    if match.group("query") != _filter_fingerprint(filters):
        raise GeorgiaDirectorySelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Georgia directory filters",
        )
    if int(match.group("size")) != page_size:
        raise GeorgiaDirectorySelectionError(
            "cursor_page_size_mismatch",
            "cursor was issued for a different Georgia directory page size",
        )
    return int(match.group("page")), int(match.group("row"))


def _cursor(
    filters: Sequence[Mapping[str, str]],
    *,
    page_size: int,
    page: int,
    row: int,
) -> str:
    return (
        f"ga-aoc-directory:{CURSOR_VERSION}:"
        f"query:{_filter_fingerprint(filters)}:"
        f"size:{page_size}:page:{page}:row:{row}"
    )


def _selection_context(
    values: Mapping[str, Any],
) -> dict[str, str]:
    return {
        name: text
        for name in SEARCH_FIELD_DEFINITIONS
        if (text := _text(values.get(name))) is not None
    }


def _person(record: Mapping[str, Any]) -> dict[str, Any]:
    parts = {
        "prefix_or_title": _field_text(record, "field_3"),
        "first": _field_text(record, "field_1"),
        "middle": _field_text(record, "field_4"),
        "last": _field_text(record, "field_2"),
        "suffix": _field_text(record, "field_5"),
    }
    display_name = " ".join(value for value in parts.values() if value)
    return {**parts, "display_name": display_name or None}


def _detail_ui_url(record_id: str) -> str:
    return f"{APP_URL}#directory-entries/{quote(record_id, safe='')}/"


def normalize_search_record(
    raw: Mapping[str, Any],
    *,
    selection_context: Mapping[str, str],
    schema_fingerprint: str | None = None,
    query_observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a compact search row without inventing detail classifications."""

    record_id = str(raw["id"])
    return {
        "canonical_ref": f"GA-AOC-COURT-PERSONNEL:{record_id}",
        "source_id": SOURCE_ID,
        "record_kind": "court_personnel_directory_entry",
        "native_record_id": record_id,
        "source_url": _detail_ui_url(record_id),
        "snapshot_only": True,
        "snapshot_state": "search_result",
        "person": _person(raw),
        "location": {
            "city": _field_text(raw, "field_8"),
            "county": _field_text(raw, "field_15"),
            "circuit": _field_text(raw, "field_14"),
        },
        "classifications": {
            "court_classes": None,
            "directory_sections": None,
            "detail_state": "not_fetched",
        },
        "selection_context": dict(selection_context),
        "query_observation": dict(query_observation or {}),
        "provenance": {
            "application_id": APP_ID,
            "scene_id": SEARCH_SCENE,
            "view_id": SEARCH_VIEW,
            "schema_fingerprint": schema_fingerprint,
        },
        "raw_fields": {"search": dict(raw)},
    }


def normalize_detail_record(
    detail: DirectoryDetail,
    *,
    search_raw: Mapping[str, Any] | None = None,
    selection_context: Mapping[str, str] | None = None,
    query_observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize full public detail fields while preserving the raw payload."""

    raw = detail.record
    record_id = str(raw["id"])
    raw_email = _field_text(raw, "field_13")
    display_email = _source_bool(_source_value(raw, "field_99"))
    fake_email = bool(
        raw_email and "@fake-email.com" in raw_email.casefold()
    )
    if raw_email and display_email and not fake_email:
        email_visibility = "published"
        email = raw_email
    elif fake_email:
        email_visibility = "source_placeholder"
        email = None
    elif raw_email:
        email_visibility = "not_displayed_by_source"
        email = None
    else:
        email_visibility = "not_present"
        email = None

    raw_fields: dict[str, Any] = {"detail": dict(raw)}
    if search_raw is not None:
        raw_fields["search"] = dict(search_raw)
    return {
        "canonical_ref": f"GA-AOC-COURT-PERSONNEL:{record_id}",
        "source_id": SOURCE_ID,
        "record_kind": "court_personnel_directory_entry",
        "native_record_id": record_id,
        "source_url": _detail_ui_url(record_id),
        "snapshot_only": True,
        "snapshot_state": "detail",
        "person": _person(raw),
        "location": {
            "address_lines": [
                value
                for field in ("field_6", "field_7", "field_20")
                if (value := _field_text(raw, field)) is not None
            ],
            "city": _field_text(raw, "field_8"),
            "state": _field_text(raw, "field_9"),
            "postal_code": _field_text(raw, "field_10"),
            "county": _field_text(raw, "field_15"),
            "circuit": _field_text(raw, "field_14"),
            "municipal_judge_city": _field_text(raw, "field_27"),
            "chief_municipal_judge_city": _field_text(raw, "field_28"),
        },
        "contact": {
            "phone": _field_text(raw, "field_11"),
            "fax": _field_text(raw, "field_12"),
            "email": email,
            "email_visibility": email_visibility,
            "source_display_email": display_email,
        },
        "classifications": {
            "court_classes": _choice_values(_source_value(raw, "field_18")),
            "directory_sections": _choice_values(
                _source_value(raw, "field_19")
            ),
            "accountability_court_type": _field_text(raw, "field_85"),
            "judicial_administration": _field_text(raw, "field_86"),
            "council_or_agency": _field_text(raw, "field_84"),
            "chief_magistrate_indicator": _field_text(raw, "field_26"),
            "detail_state": "complete",
        },
        "selection_context": dict(selection_context or {}),
        "query_observation": dict(query_observation or {}),
        "provenance": {
            "application_id": APP_ID,
            "scene_id": DETAIL_SCENE,
            "view_id": DETAIL_VIEW,
            "schema_fingerprint": detail.schema_fingerprint,
        },
        "raw_fields": raw_fields,
    }


def source_manifest() -> dict[str, Any]:
    """Describe the verified views, filters, classifications, and complements."""

    return {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/manifest",
        "source_id": SOURCE_ID,
        "record_kind": "source_manifest",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "published_application": {
            "landing_url": LANDING_URL,
            "application_url": APP_URL,
            "application_id": APP_ID,
            "loader_metadata_url": LOADER_URL,
            "access": "anonymous_published_view",
        },
        "operations": {
            "search": {
                "method": "GET",
                "url": SEARCH_API_URL,
                "scene_id": SEARCH_SCENE,
                "view_id": SEARCH_VIEW,
                "pagination": {
                    "page_parameter": "page",
                    "page_size_parameter": "rows_per_page",
                    "verified_page_size": DEFAULT_PAGE_SIZE,
                    "continuation": "filter-bound page-and-row cursor",
                },
            },
            "detail": {
                "method": "GET",
                "url_template": f"{DETAIL_API_URL}/{{record_id}}",
                "scene_id": DETAIL_SCENE,
                "view_id": DETAIL_VIEW,
                "identity": "exact native record ID",
            },
            "probe": {
                "requests": 2,
                "search_filter": {
                    "directory_section": "Superior Court Clerks"
                },
                "verification": (
                    "search result followed by exact public detail read"
                ),
            },
        },
        "public_request_headers": {
            "X-Knack-Application-Id": APP_ID,
            "X-Knack-REST-API-Key": "knack",
        },
        "search_fields": [
            {"name": name, **dict(definition)}
            for name, definition in SEARCH_FIELD_DEFINITIONS.items()
        ],
        "detail_fields": [
            {"name": name, **dict(definition)}
            for name, definition in DETAIL_FIELD_DEFINITIONS.items()
        ],
        "classifications": {
            "court_class": {
                "field": "field_18",
                "options": list(COURT_CLASS_OPTIONS),
            },
            "directory_section": {
                "field": "field_19",
                "options": list(DIRECTORY_SECTION_OPTIONS),
            },
            "relationship": (
                "independent source fields; neither is derived from the other"
            ),
        },
        "observed_source_anomalies": [
            {
                "field": "field_3",
                "source_label": "Prefix",
                "observation": (
                    "values can be honorifics or job titles such as Chief "
                    "Deputy Clerk"
                ),
                "adapter_field": "person.prefix_or_title",
            },
            {
                "field": "field_79",
                "source_label": "City search",
                "observation": (
                    "searches field_8, field_27, and field_28 while compact "
                    "results display only field_8"
                ),
            },
            {
                "field": "field_26",
                "source_model_name": "ChiefMagistrate",
                "observation": (
                    "behaves as an indicator value and is not normalized as "
                    "a general personnel role"
                ),
            },
            {
                "fields": ["field_13", "field_99"],
                "observation": (
                    "the detail view conditionally displays email using the "
                    "display flag and suppresses source placeholder addresses"
                ),
            },
        ],
        "snapshot_semantics": {
            "snapshot_only": True,
            "historical_roster": False,
            "case_index": False,
        },
        "complements": [
            {
                "name": "Georgia AOC eAccess court-record routing",
                "url": "https://georgiacourts.gov/eaccess-court-records/",
                "authority": AUTHORITY,
                "role": (
                    "routes users to participating county and provider case "
                    "record systems"
                ),
            },
            {
                "name": "Georgia AOC eFile court-record routing",
                "url": "https://georgiacourts.gov/efile-court-records/",
                "authority": AUTHORITY,
                "role": "maps courts to their official e-filing providers",
            },
            {
                "name": "Official local court and county sites",
                "url": LANDING_URL,
                "authority": "the relevant court or county",
                "role": (
                    "local rosters, office contacts, calendars, and records "
                    "that can be more current or more detailed"
                ),
            },
            {
                "name": (
                    "Georgia Superior Court Clerks' Cooperative Authority"
                ),
                "url": "https://www.gsccca.org/",
                "authority": (
                    "Georgia Superior Court Clerks' Cooperative Authority"
                ),
                "role": (
                    "separate statewide indices and clerk-administered record "
                    "systems, including real-estate and civil-filing products"
                ),
            },
        ],
        "coverage_notes": list(SOURCE_WARNINGS),
    }


def _args_filter_values(args: argparse.Namespace) -> dict[str, Any]:
    return {
        name: getattr(args, name, None)
        for name in SEARCH_FIELD_DEFINITIONS
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        filter_values = _args_filter_values(args)
        filters = build_filters(filter_values)
        parameters = {
            "filters": list(filters),
            "selection": _selection_context(filter_values),
            "page_size": args.page_size,
            "include_details": bool(args.details),
        }
        requested_limit = None if args.all else args.limit
        cursor = args.cursor
    elif args.command == "detail":
        parameters = {"record_id": args.record_id}
    elif args.command == "probe":
        parameters = {
            "directory_section": "Superior Court Clerks",
            "sample_size": 1,
        }
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _search_result(
    args: argparse.Namespace,
    client: GeorgiaCourtDirectoryClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    filter_values = _args_filter_values(args)
    filters = build_filters(filter_values)
    selection = _selection_context(filter_values)
    batch = client.search(
        filters,
        limit=None if args.all else args.limit,
        cursor=args.cursor,
        page_size=args.page_size,
    )
    schema_fingerprint = (
        batch.schema_fingerprints[0]
        if len(batch.schema_fingerprints) == 1
        else sha256_fingerprint(list(batch.schema_fingerprints))
    )
    query_observation = {
        "source_total_count": batch.source_total_count,
        "source_total_pages": batch.source_total_pages,
        "native_pages_fetched": batch.pages_fetched,
        "search_requests_made": batch.requests_made,
    }
    records = [
        normalize_search_record(
            raw,
            selection_context=selection,
            schema_fingerprint=schema_fingerprint,
            query_observation=query_observation,
        )
        for raw in batch.records
    ]
    raw_refs = list(batch.source_urls)
    if args.details:
        hydrated: list[dict[str, Any]] = []
        for index, raw in enumerate(batch.records):
            try:
                detail = client.detail(str(raw["id"]))
            except PublicRecordsHTTPError as error:
                hydrated.extend(records[index:])
                return failure_result(
                    query,
                    error,
                    records=hydrated,
                    next_cursor=batch.next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
            if detail is None:
                record = dict(records[index])
                classifications = dict(record["classifications"])
                classifications["detail_state"] = "not_found"
                record["classifications"] = classifications
                hydrated.append(record)
                continue
            hydrated.append(
                normalize_detail_record(
                    detail,
                    search_raw=raw,
                    selection_context=selection,
                    query_observation=query_observation,
                )
            )
            raw_refs.append(detail.source_url)
        records = hydrated
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        raw_artifact_refs=tuple(dict.fromkeys(raw_refs)),
        warnings=SOURCE_WARNINGS,
    )


def _probe_result(
    client: GeorgiaCourtDirectoryClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    filters = build_filters(
        {"directory_section": "Superior Court Clerks"}
    )
    before_requests = int(getattr(client, "request_count", 0))
    batch = client.search(filters, limit=1, page_size=1)
    if not batch.records:
        raise SourceSchemaError(
            "Georgia directory probe returned no Superior Court Clerks",
            url=SEARCH_API_URL,
        )
    record_id = str(batch.records[0]["id"])
    detail = client.detail(record_id)
    if detail is None:
        raise SourceSchemaError(
            "Georgia directory probe detail record disappeared",
            url=f"{DETAIL_API_URL}/{quote(record_id, safe='')}",
        )
    normalized = normalize_detail_record(
        detail,
        search_raw=batch.records[0],
        selection_context={"directory_section": "Superior Court Clerks"},
    )
    sections = normalized["classifications"]["directory_sections"]
    if "Superior Court Clerks" not in sections:
        raise SourceSchemaError(
            "Georgia directory detail did not preserve the probe filter",
            url=detail.source_url,
            details={
                "record_id": record_id,
                "directory_sections": sections,
            },
        )
    requests_made = int(getattr(client, "request_count", 0)) - before_requests
    if requests_made and requests_made != 2:
        raise SourceSchemaError(
            "Georgia directory bounded probe request count changed",
            url=SEARCH_API_URL,
            details={"requests_made": requests_made, "expected": 2},
        )
    probe = {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/probe",
        "source_id": SOURCE_ID,
        "record_kind": "source_probe",
        "source_url": LANDING_URL,
        "snapshot_only": True,
        "stable_contract": {
            "application_id": APP_ID,
            "search_view": {
                "scene_id": SEARCH_SCENE,
                "view_id": SEARCH_VIEW,
            },
            "detail_view": {
                "scene_id": DETAIL_SCENE,
                "view_id": DETAIL_VIEW,
            },
            "filter": list(filters),
            "identity": "exact native record ID",
        },
        "schema_contract": {
            "search": list(batch.schema_fingerprints),
            "detail": detail.schema_fingerprint,
        },
        "rolling_observation": {
            "matching_total_records": batch.source_total_count,
            "sample_record_id": record_id,
            "sample_display_name": normalized["person"]["display_name"],
            "sample_directory_sections": sections,
        },
        "requests_made": requests_made or 2,
    }
    return PublicRecordsResult.success(
        query,
        [probe],
        raw_artifact_refs=(*batch.source_urls, detail.source_url),
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: GeorgiaCourtDirectoryClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one isolated Georgia court-directory operation."""

    query = build_query(args)
    source_client = client
    owns_client = False
    try:
        if args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [source_manifest()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            if source_client is None:
                source_client = GeorgiaCourtDirectoryClient(
                    timeout=args.timeout,
                    minimum_interval=args.minimum_interval,
                    retry_policy=RetryPolicy(
                        max_attempts=args.max_attempts,
                        backoff_initial=args.retry_backoff,
                    ),
                )
                owns_client = True
            if args.command == "search":
                result = _search_result(args, source_client, query)
            elif args.command == "detail":
                detail = source_client.detail(args.record_id)
                records = (
                    [normalize_detail_record(detail)]
                    if detail is not None
                    else []
                )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    raw_artifact_refs=(
                        [detail.source_url] if detail is not None else []
                    ),
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                result = _probe_result(source_client, query)
            else:
                raise ValueError(
                    f"unsupported Georgia directory command: {args.command}"
                )
    except GeorgiaDirectorySelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
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
        if owns_client and source_client is not None:
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
        summary=f"Georgia court directory {args.command}",
        result_count=(
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Georgia court directory {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "court_personnel_directory_entry":
            person = record.get("person", {})
            location = record.get("location", {})
            print(
                f"  {person.get('display_name') or '?'} | "
                f"{location.get('county') or location.get('city') or '?'}"
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


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    parser.add_argument(
        "--retry-backoff",
        type=_nonnegative_float,
        default=0.5,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Georgia AOC's public Court Personnel Directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser(
        "manifest",
        help="Describe verified views, filters, and complementary sources",
    )
    add_output_args(manifest)

    search = subparsers.add_parser(
        "search",
        help="Search and page through current directory entries",
    )
    for name, definition in SEARCH_FIELD_DEFINITIONS.items():
        search.add_argument(
            f"--{name.replace('_', '-')}",
            help=f"Native {definition['label']} filter",
        )
    limit_group = search.add_mutually_exclusive_group()
    limit_group.add_argument(
        "--limit",
        type=_positive_int,
        default=DEFAULT_LIMIT,
        help="Maximum records to return in this call",
    )
    limit_group.add_argument(
        "--all",
        action="store_true",
        help="Follow all native result pages",
    )
    search.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Native rows_per_page value; 100 is verified",
    )
    search.add_argument(
        "--cursor",
        help="Continuation cursor returned by a prior matching search",
    )
    search.add_argument(
        "--details",
        action="store_true",
        help="Fetch the published detail view for each returned row",
    )
    _add_runtime_and_output(search)

    detail = subparsers.add_parser(
        "detail",
        help="Read one exact record from the published detail view",
    )
    detail.add_argument("record_id")
    _add_runtime_and_output(detail)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded search-plus-detail source check",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
