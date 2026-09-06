#!/usr/bin/env python3
"""Query Orange County Superior Court calendars and tentative rulings.

The court publishes two useful anonymous record layers:

* a six-case-type "Cases on Calendar" search with native 50-row paging; and
* rolling civil, family-law, and probate tentative-ruling directories whose
  current artifacts are mostly PDFs.

The calendar's official page says hearings more than six weeks in the future
are not displayed.  That source window is kept separate from the adapter's
50-row transport batches and the caller's optional ``--limit``.  With no
caller limit, every native result page is retrieved.

Examples:
    uv run python tools/query_orange_county_court.py calendar civil \
        --title "Kiani" --output /tmp/orange-calendar.json
    uv run python tools/query_orange_county_court.py ruling-index \
        --division civil --output /tmp/orange-ruling-index.json
    uv run python tools/query_orange_county_court.py ruling civil C44 \
        --download /tmp/c44.pdf --output /tmp/orange-c44.json
    uv run python tools/query_orange_county_court.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

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


COURT_NAME = "Superior Court of California, County of Orange"
COURT_ID = "ca-orange-superior"
COUNTY_FIPS = "06059"
STATE_CODE = "CA"

SOURCE_FAMILY_ID = "us-ca-orange-superior-court-public-records"
CALENDAR_SOURCE_ID = "us-ca-orange-superior-court-calendar"
RULING_SOURCE_IDS = {
    "civil": "us-ca-orange-superior-court-civil-tentative-rulings",
    "family": "us-ca-orange-superior-court-family-tentative-rulings",
    "probate": "us-ca-orange-superior-court-probate-tentative-rulings",
}
CASE_NAME_SOURCE_ID = "us-ca-orange-superior-court-case-name-search"
CASE_PORTALS_SOURCE_ID = "us-ca-orange-superior-court-case-access-portals"
CASE_INDEX_SOURCE_ID = "us-ca-orange-superior-court-permanent-case-index"
CASE_INDEX_PRODUCT_SOURCE_ID = (
    "us-ca-orange-superior-court-case-index-products"
)
PROBATE_NOTES_SOURCE_ID = "us-ca-orange-superior-court-probate-notes"
RECORDS_SOURCE_ID = "us-ca-orange-superior-court-records-and-copies"

COURT_SITE_URL = "https://www.occourts.org"
ONLINE_SERVICES_URL = f"{COURT_SITE_URL}/online-services"
CALENDAR_INFO_URL = f"{ONLINE_SERVICES_URL}/cases-calendar"
CALENDAR_URL = "https://courtcalendar.occourts.org/search.do"
RULING_DIRECTORY_URLS = {
    "civil": (
        f"{ONLINE_SERVICES_URL}/tentative-rulings/"
        "civil-tentative-rulings"
    ),
    "family": (
        f"{ONLINE_SERVICES_URL}/tentative-rulings/"
        "family-law-tentative-rulings"
    ),
    "probate": (
        f"{ONLINE_SERVICES_URL}/tentative-rulings/"
        "probate-tentative-rulings"
    ),
}

CASE_ACCESS_URL = f"{ONLINE_SERVICES_URL}/case-access"
CASE_NAME_SEARCH_URL = "https://namesearch.occourts.org/"
CIVIL_CASE_ACCESS_URL = "https://civilwebshopping.occourts.org/"
CRIMINAL_CASE_ACCESS_URL = "https://visionpublic.occourts.org/"
FAMILY_CASE_ACCESS_URL = "https://fampub.occourts.org/Home.do"
PROBATE_CASE_ACCESS_URL = "https://probatepublic.occourts.org/Home.do"
SMALL_CLAIMS_CASE_ACCESS_URL = "https://smallclaims.occourts.org/Home.do"
CASE_INDEX_URL = "https://courtindex.occourts.org/"
CASE_INDEX_ORDER_URL = f"{ONLINE_SERVICES_URL}/order-case-indexes"
PROBATE_NOTES_URL = "https://ocscefm1.occourts.org/probate-notes"
RECORDS_URL = f"{COURT_SITE_URL}/general-information/records"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
TRANSPORT_PAGE_SIZE = 50
CURSOR_PREFIX = "orange-court-calendar:v1:"
CURSOR_VERSION = 1

CATEGORY_CODES = {
    "civil": "CV",
    "criminal": "CM",
    "family": "FL",
    "probate": "PR",
    "small-claims": "SC",
    "traffic": "TF",
}
CATEGORY_LABELS = {
    "CV": "Civil",
    "CM": "Criminal",
    "FL": "Family Law",
    "PR": "Probate",
    "SC": "Small Claims",
    "TF": "Traffic",
}

EXPECTED_CALENDAR_HEADERS = (
    "Case ID",
    "Title",
    "Location",
    "Dept",
    "Date",
    "Time",
    "Case Type",
    "Type of Hearing",
)
EXPECTED_FORM_FIELDS = frozenset(
    {
        "searchForm.caseType",
        "searchForm.caseNo",
        "searchForm.caseYear",
        "searchForm.title",
        "searchForm.jc",
        "searchForm.dept",
        "searchForm.dateFrom",
        "searchForm.dateTo",
        "searchForm.eventTime",
        "searchForm.numRecordsPerPage",
        "searchForm.action",
    }
)

CALENDAR_WARNINGS = (
    "The calendar is a hearing-discovery source, not the complete register "
    "of actions or a filing-image repository.",
    "The court states that hearings more than six weeks in the future are "
    "not displayed; historical availability follows the native form response.",
)
RULING_WARNINGS = (
    "Tentative-ruling artifacts are rolling publications and may be replaced "
    "when a department posts a newer calendar.",
    "A tentative ruling is not necessarily the final order entered after the "
    "hearing.",
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_FIPS,
    name="Orange County, California",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Orange County",
    metadata={
        "court_id": COURT_ID,
        "court_name": COURT_NAME,
    },
)

CALENDAR_SOURCE = SourceMetadata(
    source_id=CALENDAR_SOURCE_ID,
    name="Orange County Superior Court Cases on Calendar",
    source_role="county_superior_court_hearing_calendar",
    base_url=CALENDAR_URL,
    metadata={
        "authority": COURT_NAME,
        "calendar_information_url": CALENDAR_INFO_URL,
        "authentication": "none",
        "native_case_categories": CATEGORY_LABELS,
        "published_future_window": "six weeks",
        "transport_page_size": TRANSPORT_PAGE_SIZE,
    },
)


class OrangeCourtError(RuntimeError):
    """Base error for one Orange County source operation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: str,
        retryable: bool = False,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.retryable = retryable
        self.status = status
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class OrangeCourtSelectionError(OrangeCourtError):
    """A selector or continuation does not match the source contract."""

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
            category="selection",
            status=ResultStatus.SOURCE_CHANGED,
            details=details,
        )


class OrangeCourtSourceChangedError(OrangeCourtError):
    """An official page no longer matches its verified representation."""

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


@dataclass(frozen=True)
class FetchedResponse:
    """Detached response used by the live and fixture clients."""

    body: bytes
    url: str
    headers: Mapping[str, str]
    status_code: int = 200

    @property
    def text(self) -> str:
        content_type = self.headers.get("Content-Type", "")
        match = re.search(r"charset=([^\s;]+)", content_type, re.I)
        encoding = match.group(1).strip("\"'") if match else "utf-8"
        try:
            return self.body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            return self.body.decode("utf-8", errors="replace")


class OrangeCourtClient:
    """Paced, retrying client for the court's public HTML and PDF routes."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        self._owns_session = session is None
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "Ithildin-OSINT/1.0 public-record research "
            "(https://github.com/)",
        )
        self.session.headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.retry_attempts = retry_attempts
        self._last_request_at = 0.0

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _pace(self) -> None:
        remaining = (
            self.minimum_interval
            - (time.monotonic() - self._last_request_at)
        )
        if remaining > 0:
            time.sleep(remaining)

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FetchedResponse:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            self._pace()
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
            except requests.RequestException as error:
                self._last_request_at = time.monotonic()
                last_error = error
                if attempt < self.retry_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise OrangeCourtError(
                    "orange_court_transport_error",
                    f"Orange County court request failed: {error}",
                    category="transport",
                    retryable=True,
                    details={"url": url, "method": method},
                ) from error

            if response.status_code == 429:
                if attempt < self.retry_attempts:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(float(retry_after or attempt), 30.0)
                    except ValueError:
                        delay = float(attempt)
                    time.sleep(delay)
                    continue
                raise OrangeCourtError(
                    "orange_court_rate_limited",
                    "Orange County court source returned HTTP 429",
                    category="rate_limit",
                    retryable=True,
                    status=ResultStatus.RATE_LIMITED,
                    details={"url": response.url},
                )

            if response.status_code >= 500:
                if attempt < self.retry_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise OrangeCourtError(
                    "orange_court_server_error",
                    (
                        "Orange County court source returned "
                        f"HTTP {response.status_code}"
                    ),
                    category="http",
                    retryable=True,
                    details={
                        "url": response.url,
                        "status_code": response.status_code,
                    },
                )

            if response.status_code >= 400:
                status = (
                    ResultStatus.RESTRICTED
                    if response.status_code in {401, 403}
                    else ResultStatus.UNAVAILABLE
                )
                raise OrangeCourtError(
                    "orange_court_http_error",
                    (
                        "Orange County court source returned "
                        f"HTTP {response.status_code}"
                    ),
                    category="http",
                    retryable=False,
                    status=status,
                    details={
                        "url": response.url,
                        "status_code": response.status_code,
                    },
                )

            return FetchedResponse(
                body=response.content,
                url=response.url,
                headers=dict(response.headers),
                status_code=response.status_code,
            )

        raise AssertionError(
            f"Orange County court request ended without a response: {last_error}"
        )

    def calendar_landing(self) -> FetchedResponse:
        return self._request("GET", CALENDAR_URL)

    def calendar_first(self, form_data: Mapping[str, str]) -> FetchedResponse:
        return self._request("POST", CALENDAR_URL, data=dict(form_data))

    def calendar_page(
        self,
        form_data: Mapping[str, str],
        page: int,
    ) -> FetchedResponse:
        params = dict(form_data)
        params["page"] = str(page)
        return self._request("GET", CALENDAR_URL, params=params)

    def page(self, url: str) -> FetchedResponse:
        return self._request("GET", url)


@dataclass(frozen=True)
class CalendarFormContract:
    """Verified public calendar form fields and source-native defaults."""

    action_url: str
    category_codes: Mapping[str, str]
    default_date_from: str
    default_date_to: str
    page_sizes: tuple[int, ...]
    field_names: tuple[str, ...]
    schema_fingerprint: str

    @property
    def transport_page_size(self) -> int:
        return max(self.page_sizes)


@dataclass(frozen=True)
class CalendarCriteria:
    """Caller selectors in normalized source terms."""

    category: str
    case_id: str | None = None
    case_year: str | None = None
    title: str | None = None
    location: str | None = None
    department: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    hearing_time: str | None = None

    def materialize(
        self,
        contract: CalendarFormContract,
    ) -> CalendarCriteria:
        return replace(
            self,
            date_from=self.date_from or contract.default_date_from,
            date_to=self.date_to or contract.default_date_to,
        )

    def to_parameters(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "category_code": CATEGORY_CODES[self.category],
            "case_id": self.case_id,
            "case_year": self.case_year,
            "title": self.title,
            "location": self.location,
            "department": self.department,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "hearing_time": self.hearing_time,
        }


@dataclass(frozen=True)
class CalendarPage:
    """One native calendar result page."""

    records: tuple[Mapping[str, Any], ...]
    total: int
    display_start: int
    display_end: int
    page_number: int


def _clean(value: Any) -> str | None:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    return text or None


def _iso_date(value: str, *, field_name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise OrangeCourtSelectionError(
            "invalid_calendar_date",
            f"{field_name} must be an ISO date (YYYY-MM-DD)",
            details={"field": field_name, "value": value},
        ) from error


def _source_date_to_iso(value: str) -> str:
    for pattern in ("%b-%d-%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError:
            continue
    raise OrangeCourtSourceChangedError(
        "orange_calendar_date_format_changed",
        f"Orange County calendar date does not match a verified format: {value!r}",
    )


def _iso_to_source_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return parsed.strftime("%b-%d-%Y")


def _normalized_department(value: str) -> str:
    department = re.sub(r"[\s.-]+", "", value.upper())
    match = re.fullmatch(r"CM0*([0-9]+)", department)
    if match:
        return f"CM{int(match.group(1))}"
    return department


def _ruling_source(division: str) -> SourceMetadata:
    return SourceMetadata(
        source_id=RULING_SOURCE_IDS[division],
        name=(
            "Orange County Superior Court "
            f"{division.title()} Tentative Rulings"
        ),
        source_role=(
            "county_superior_court_current_tentative_ruling_publications"
        ),
        base_url=RULING_DIRECTORY_URLS[division],
        metadata={
            "authority": COURT_NAME,
            "division": division,
            "publication_model": "rolling_current_department_artifacts",
        },
    )


def _family_source() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_FAMILY_ID,
        name="Orange County Superior Court Public Record Sources",
        source_role="county_superior_court_public_record_source_family",
        base_url=ONLINE_SERVICES_URL,
        metadata={
            "authority": COURT_NAME,
            "calendar_source_id": CALENDAR_SOURCE_ID,
            "ruling_source_ids": RULING_SOURCE_IDS,
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


def parse_calendar_form(
    html: str,
    *,
    response_url: str = CALENDAR_URL,
) -> CalendarFormContract:
    """Parse and validate the public calendar's native form contract."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="searchForm")
    if form is None:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_form_missing",
            "Orange County calendar page lacks the expected search form",
            details={"url": response_url},
        )

    names = tuple(
        sorted(
            {
                str(element.get("name"))
                for element in form.find_all(["input", "select"])
                if element.get("name")
            }
        )
    )
    missing_fields = sorted(EXPECTED_FORM_FIELDS.difference(names))
    if missing_fields:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_form_fields_changed",
            "Orange County calendar form is missing verified fields",
            details={"missing_fields": missing_fields, "fields": list(names)},
        )

    category_select = form.find("select", id="caseType")
    page_size_select = form.find("select", id="numRecordsPerPage")
    from_input = form.find("input", id="dateFrom")
    to_input = form.find("input", id="dateTo")
    if not category_select or not page_size_select or not from_input or not to_input:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_form_controls_changed",
            "Orange County calendar form controls changed",
        )

    categories: dict[str, str] = {}
    for option in category_select.find_all("option"):
        code = _clean(option.get("value"))
        label = _clean(option.get_text(" ", strip=True))
        if code and label and code != "ALL":
            categories[code] = label
    if categories != CATEGORY_LABELS:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_categories_changed",
            "Orange County calendar category choices changed",
            details={
                "expected": CATEGORY_LABELS,
                "observed": categories,
            },
        )

    page_sizes: list[int] = []
    for option in page_size_select.find_all("option"):
        value = _clean(option.get("value"))
        if value and value.isdigit():
            page_sizes.append(int(value))
    if not page_sizes or TRANSPORT_PAGE_SIZE not in page_sizes:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_page_sizes_changed",
            "Orange County calendar no longer publishes its verified page sizes",
            details={"page_sizes": page_sizes},
        )

    date_from_raw = _clean(from_input.get("value"))
    date_to_raw = _clean(to_input.get("value"))
    if not date_from_raw or not date_to_raw:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_default_dates_missing",
            "Orange County calendar form lacks its source-native date defaults",
        )

    action = _clean(form.get("action")) or CALENDAR_URL
    action_url = urljoin(response_url, action)
    action_url = re.sub(r";jsessionid=[^?]+", "", action_url, flags=re.I)
    schema_payload = {
        "fields": list(names),
        "categories": categories,
        "page_sizes": page_sizes,
        "calendar_headers": EXPECTED_CALENDAR_HEADERS,
    }
    return CalendarFormContract(
        action_url=action_url,
        category_codes=categories,
        default_date_from=_source_date_to_iso(date_from_raw),
        default_date_to=_source_date_to_iso(date_to_raw),
        page_sizes=tuple(page_sizes),
        field_names=names,
        schema_fingerprint=sha256_fingerprint(schema_payload),
    )


def _calendar_form_data(
    criteria: CalendarCriteria,
    contract: CalendarFormContract,
) -> dict[str, str]:
    if criteria.category not in CATEGORY_CODES:
        raise OrangeCourtSelectionError(
            "unknown_calendar_category",
            f"unknown Orange County calendar category: {criteria.category}",
        )
    if not criteria.date_from or not criteria.date_to:
        raise AssertionError("calendar criteria must be materialized")
    date_from = _iso_date(criteria.date_from, field_name="date_from")
    date_to = _iso_date(criteria.date_to, field_name="date_to")
    if date_from > date_to:
        raise OrangeCourtSelectionError(
            "calendar_date_range_reversed",
            "date_from must be on or before date_to",
            details={"date_from": date_from, "date_to": date_to},
        )
    return {
        "searchForm.caseType": CATEGORY_CODES[criteria.category],
        "searchForm.caseNo": criteria.case_id or "",
        "searchForm.caseYear": criteria.case_year or "",
        "searchForm.title": criteria.title or "",
        "searchForm.jc": (criteria.location or "ALL").upper(),
        "searchForm.dept": (criteria.department or "ALL").upper(),
        "searchForm.dateFrom": _iso_to_source_date(date_from),
        "searchForm.dateTo": _iso_to_source_date(date_to),
        "searchForm.eventTime": criteria.hearing_time or "ALL",
        "searchForm.numRecordsPerPage": str(
            contract.transport_page_size
        ),
        "searchForm.action": "Search",
    }


def _calendar_case_parties(case_title: str | None) -> list[dict[str, Any]]:
    if not case_title:
        return []
    parts = re.split(r"\s+v(?:s\.?|\.?)\s+", case_title, maxsplit=1, flags=re.I)
    if len(parts) != 2:
        return []
    return [
        {"name": _clean(parts[0]), "role": "title_side_1"},
        {"name": _clean(parts[1]), "role": "title_side_2"},
    ]


def _calendar_record(
    cells: Mapping[str, str | None],
    *,
    category: str,
    retrieved_at: str,
) -> dict[str, Any]:
    case_number = _clean(cells.get("case_id"))
    if not case_number:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_case_id_missing",
            "Orange County calendar row lacks a case ID",
        )
    hearing_date_raw = _clean(cells.get("date"))
    if not hearing_date_raw:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_hearing_date_missing",
            "Orange County calendar row lacks a hearing date",
            details={"case_number": case_number},
        )
    hearing_date_iso = _source_date_to_iso(hearing_date_raw)
    case_title = _clean(cells.get("title"))
    hearing_time = _clean(cells.get("time"))
    department = _clean(cells.get("department"))
    hearing_type = _clean(cells.get("hearing_type"))
    canonical_ref = (
        "OC-COURT-CALENDAR:"
        + hashlib.sha256(
            canonical_json(
                {
                    "case_number": case_number,
                    "hearing_date": hearing_date_iso,
                    "hearing_time": hearing_time,
                    "department": department,
                    "hearing_type": hearing_type,
                }
            ).encode("utf-8")
        ).hexdigest()
    )
    return {
        "canonical_ref": canonical_ref,
        "source_id": CALENDAR_SOURCE_ID,
        "record_kind": "court_hearing",
        "court": {
            "court_id": COURT_ID,
            "name": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "state_code": STATE_CODE,
        },
        "case": {
            "case_number": case_number,
            "case_title": case_title,
            "case_category": category,
            "case_type": _clean(cells.get("case_type")),
            "title_parties": _calendar_case_parties(case_title),
        },
        "hearing": {
            "date": hearing_date_iso,
            "time": hearing_time,
            "location_code": _clean(cells.get("location")),
            "department": department,
            "hearing_type": hearing_type,
        },
        "native": {
            "case_id": case_number,
            "title": case_title,
            "location": _clean(cells.get("location")),
            "department": department,
            "date": hearing_date_raw,
            "time": hearing_time,
            "case_type": _clean(cells.get("case_type")),
            "hearing_type": hearing_type,
        },
        "source_url": CALENDAR_URL,
        "retrieved_at": retrieved_at,
        "complementary_routes": _case_complementary_routes(case_number),
    }


def parse_calendar_page(
    html: str,
    *,
    category: str,
    retrieved_at: str | None = None,
    page_number: int = 1,
) -> CalendarPage:
    """Parse one native calendar page and its declared total."""

    retrieved_at = retrieved_at or utc_now_iso()
    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text(" ", strip=True) if soup.title else None)
    if not title or "Superior Court of California" not in title:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_page_identity_changed",
            "Orange County calendar response lacks its verified page identity",
        )

    challenge_text = _clean(soup.get_text(" ", strip=True)) or ""
    if re.search(
        r"verify (?:that )?you are human|captcha|access denied",
        challenge_text,
        re.I,
    ):
        raise OrangeCourtError(
            "orange_calendar_verification_page",
            "Orange County calendar returned a verification page",
            category="access",
            status=ResultStatus.HUMAN_REQUIRED,
        )

    validation = soup.select_one(".validationerrorsbox")
    validation_text = _clean(
        validation.get_text(" ", strip=True) if validation else None
    )
    if validation_text:
        raise OrangeCourtSelectionError(
            "orange_calendar_source_validation",
            f"Orange County calendar rejected the query: {validation_text}",
            details={"validation_text": validation_text},
        )

    table = soup.find("table", id="case")
    if table is None:
        empty = soup.select_one(".standardtagempty")
        if empty is not None:
            return CalendarPage(
                records=(),
                total=0,
                display_start=0,
                display_end=0,
                page_number=page_number,
            )
        raise OrangeCourtSourceChangedError(
            "orange_calendar_result_table_missing",
            "Orange County calendar response is neither results nor an empty result",
        )

    headers = tuple(
        _clean(cell.get_text(" ", strip=True)) or ""
        for cell in table.select("thead th")
    )
    if headers != EXPECTED_CALENDAR_HEADERS:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_headers_changed",
            "Orange County calendar result headers changed",
            details={
                "expected": list(EXPECTED_CALENDAR_HEADERS),
                "observed": list(headers),
            },
        )

    class_fields = {
        "col_caseid": "case_id",
        "col_title": "title",
        "col_location": "location",
        "col_dept": "department",
        "col_date": "date",
        "col_time": "time",
        "col_casetype": "case_type",
        "col_hearingtype": "hearing_type",
    }
    records: list[dict[str, Any]] = []
    for row in table.select("tbody tr"):
        cells: dict[str, str | None] = {}
        for class_name, field_name in class_fields.items():
            cell = row.select_one(f".{class_name}")
            if cell is None:
                raise OrangeCourtSourceChangedError(
                    "orange_calendar_row_shape_changed",
                    "Orange County calendar row lacks a verified cell",
                    details={"missing_class": class_name},
                )
            cells[field_name] = _clean(cell.get_text(" ", strip=True))
        records.append(
            _calendar_record(
                cells,
                category=category,
                retrieved_at=retrieved_at,
            )
        )

    banner = soup.select_one(".pagebanner")
    banner_text = _clean(banner.get_text(" ", strip=True) if banner else None)
    if not banner_text:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_page_banner_missing",
            "Orange County calendar result lacks its declared total",
        )

    paged_match = re.fullmatch(
        r"(\d+)\s+items?\s+found,\s+displaying\s+(\d+)\s+to\s+(\d+)\.",
        banner_text,
        re.I,
    )
    all_match = re.fullmatch(
        r"(\d+)\s+items?\s+found,\s+displaying\s+all\s+items?\.",
        banner_text,
        re.I,
    )
    if paged_match:
        total = int(paged_match.group(1))
        display_start = int(paged_match.group(2))
        display_end = int(paged_match.group(3))
    elif all_match:
        total = int(all_match.group(1))
        display_start = 1 if total else 0
        display_end = total
    else:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_page_banner_changed",
            "Orange County calendar result-count text changed",
            details={"banner": banner_text},
        )

    declared_count = max(0, display_end - display_start + 1)
    if total < display_end or len(records) != declared_count:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_page_count_mismatch",
            "Orange County calendar row count differs from its page banner",
            details={
                "total": total,
                "display_start": display_start,
                "display_end": display_end,
                "row_count": len(records),
            },
        )
    return CalendarPage(
        records=tuple(records),
        total=total,
        display_start=display_start,
        display_end=display_end,
        page_number=page_number,
    )


def _calendar_snapshot_marker(
    page: CalendarPage,
    contract: CalendarFormContract,
) -> str:
    return sha256_fingerprint(
        {
            "total": page.total,
            "schema_fingerprint": contract.schema_fingerprint,
            "first_page_records": [
                {
                    "canonical_ref": record["canonical_ref"],
                    "case": record["case"],
                    "hearing": record["hearing"],
                }
                for record in page.records
            ],
        }
    )


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(value: str) -> dict[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise OrangeCourtSelectionError(
            "calendar_cursor_source_mismatch",
            "cursor does not belong to the Orange County calendar source",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as error:
        raise OrangeCourtSelectionError(
            "invalid_calendar_cursor",
            "Orange County calendar cursor is malformed",
        ) from error
    if not isinstance(payload, dict) or payload.get("version") != CURSOR_VERSION:
        raise OrangeCourtSelectionError(
            "invalid_calendar_cursor",
            "Orange County calendar cursor version is not supported",
        )
    return payload


def calendar_search(
    criteria: CalendarCriteria,
    *,
    limit: int | None = None,
    cursor: str | None = None,
    client: OrangeCourtClient | Any | None = None,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Search the calendar, exhausting native pages when limit is omitted."""

    if limit is not None and limit <= 0:
        raise OrangeCourtSelectionError(
            "invalid_calendar_limit",
            "limit must be a positive integer",
        )
    source_client = client or OrangeCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    landing = source_client.calendar_landing()
    contract = parse_calendar_form(
        landing.text,
        response_url=landing.url,
    )
    if contract.transport_page_size != TRANSPORT_PAGE_SIZE:
        raise OrangeCourtSourceChangedError(
            "orange_calendar_transport_size_changed",
            "Orange County calendar transport page size changed",
            details={
                "expected": TRANSPORT_PAGE_SIZE,
                "observed": contract.transport_page_size,
            },
        )

    materialized = criteria.materialize(contract)
    form_data = _calendar_form_data(materialized, contract)
    parameters = materialized.to_parameters()

    continuation = _decode_cursor(cursor) if cursor else None
    if continuation and continuation.get("parameters") != parameters:
        raise OrangeCourtSelectionError(
            "calendar_cursor_query_mismatch",
            "cursor belongs to different Orange County calendar criteria",
            details={
                "cursor_parameters": continuation.get("parameters"),
                "requested_parameters": parameters,
            },
        )
    start_offset = int(continuation.get("offset", 0)) if continuation else 0
    if start_offset < 0:
        raise OrangeCourtSelectionError(
            "invalid_calendar_cursor",
            "Orange County calendar cursor has a negative offset",
        )

    first_response = source_client.calendar_first(form_data)
    first_page = parse_calendar_page(
        first_response.text,
        category=materialized.category,
        retrieved_at=retrieved_at,
        page_number=1,
    )
    marker = _calendar_snapshot_marker(first_page, contract)
    if continuation:
        if (
            continuation.get("schema_fingerprint")
            != contract.schema_fingerprint
            or continuation.get("snapshot_marker") != marker
            or int(continuation.get("source_total", -1)) != first_page.total
        ):
            raise OrangeCourtSelectionError(
                "calendar_cursor_snapshot_changed",
                "Orange County calendar results changed since the cursor was issued",
                details={
                    "cursor_total": continuation.get("source_total"),
                    "current_total": first_page.total,
                },
            )
    if start_offset > first_page.total:
        raise OrangeCourtSelectionError(
            "calendar_cursor_offset_invalid",
            "Orange County calendar cursor offset exceeds the current result set",
            details={"offset": start_offset, "total": first_page.total},
        )

    records: list[Mapping[str, Any]] = []
    next_offset = start_offset
    pages_fetched: set[int] = {1}
    while next_offset < first_page.total:
        if limit is not None and len(records) >= limit:
            break
        page_number = next_offset // TRANSPORT_PAGE_SIZE + 1
        within_page = next_offset % TRANSPORT_PAGE_SIZE
        if page_number == 1:
            page = first_page
        else:
            response = source_client.calendar_page(form_data, page_number)
            page = parse_calendar_page(
                response.text,
                category=materialized.category,
                retrieved_at=retrieved_at,
                page_number=page_number,
            )
            pages_fetched.add(page_number)
            if page.total != first_page.total:
                raise OrangeCourtSourceChangedError(
                    "orange_calendar_total_changed_during_traversal",
                    "Orange County calendar total changed during paging",
                    details={
                        "first_total": first_page.total,
                        "page_total": page.total,
                        "page": page_number,
                    },
                )

        available = list(page.records[within_page:])
        if not available:
            raise OrangeCourtSourceChangedError(
                "orange_calendar_page_progress_stalled",
                "Orange County calendar paging made no forward progress",
                details={
                    "page": page_number,
                    "offset": next_offset,
                    "total": first_page.total,
                },
            )
        if limit is not None:
            available = available[: limit - len(records)]
        records.extend(available)
        next_offset += len(available)

    if len(pages_fetched) > 1 or continuation:
        verification_response = source_client.calendar_first(form_data)
        verification_page = parse_calendar_page(
            verification_response.text,
            category=materialized.category,
            retrieved_at=retrieved_at,
            page_number=1,
        )
        if _calendar_snapshot_marker(verification_page, contract) != marker:
            raise OrangeCourtSourceChangedError(
                "orange_calendar_snapshot_changed_during_traversal",
                "Orange County calendar first page changed during traversal",
            )

    next_cursor = None
    if next_offset < first_page.total:
        next_cursor = _encode_cursor(
            {
                "version": CURSOR_VERSION,
                "parameters": parameters,
                "offset": next_offset,
                "source_total": first_page.total,
                "snapshot_marker": marker,
                "schema_fingerprint": contract.schema_fingerprint,
            }
        )

    query = _query(
        CALENDAR_SOURCE,
        "calendar",
        parameters,
        limit=limit,
        cursor=cursor,
        metadata={
            "bounds": {
                "caller_limit": limit,
                "caller_limit_omitted_means": "exhaust all native pages",
                "transport_page_size": TRANSPORT_PAGE_SIZE,
                "transport_basis": (
                    "maximum value published by the official form"
                ),
                "source_window": (
                    "official page states hearings more than six weeks "
                    "ahead are not displayed"
                ),
                "bounded_probe_rows": None,
            },
            "coverage": {
                "source_total": first_page.total,
                "start_offset": start_offset,
                "next_offset": next_offset,
                "returned": len(records),
                "pages_fetched": sorted(pages_fetched),
            },
            "snapshot": {
                "marker": marker,
                "form_schema_fingerprint": contract.schema_fingerprint,
            },
        },
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        next_cursor=next_cursor,
        raw_artifact_refs=[first_response.url],
        warnings=CALENDAR_WARNINGS,
    )


def parse_ruling_directory(
    html: str,
    *,
    division: str,
    response_url: str,
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    """Parse every current artifact linked by one ruling directory."""

    if division not in RULING_DIRECTORY_URLS:
        raise OrangeCourtSelectionError(
            "unknown_ruling_division",
            f"unknown Orange County ruling division: {division}",
        )
    retrieved_at = retrieved_at or utc_now_iso()
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    heading_text = _clean(heading.get_text(" ", strip=True) if heading else None)
    expected_phrase = {
        "civil": "Civil Tentative Rulings",
        "family": "Family Law Tentative Rulings",
        "probate": "Probate Tentative Rulings",
    }[division]
    if not heading_text or expected_phrase.lower() not in heading_text.lower():
        raise OrangeCourtSourceChangedError(
            "orange_ruling_directory_identity_changed",
            "Orange County ruling directory lacks its verified heading",
            details={
                "division": division,
                "expected": expected_phrase,
                "observed": heading_text,
            },
        )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        artifact_url = urljoin(response_url, str(anchor["href"]))
        parsed = urlparse(artifact_url)
        if parsed.hostname not in {"www.occourts.org", "occourts.org"}:
            continue
        if (
            "/sites/default/files/oc/default/tentative-rulings/"
            not in parsed.path.lower()
            or not re.search(r"\.(?:pdf|html?|txt)$", parsed.path, re.I)
        ):
            continue
        if artifact_url in seen_urls:
            continue
        seen_urls.add(artifact_url)
        label = _clean(anchor.get_text(" ", strip=True))
        if not label:
            raise OrangeCourtSourceChangedError(
                "orange_ruling_artifact_label_missing",
                "Orange County ruling artifact has no department label",
                details={"url": artifact_url, "division": division},
            )
        department_match = re.search(
            r"\bDept\.?\s*([A-Z0-9]+)\b",
            label,
            re.I,
        )
        if not department_match:
            department_match = re.match(r"\s*(CM0*\d+)\b", label, re.I)
        if not department_match:
            raise OrangeCourtSourceChangedError(
                "orange_ruling_department_missing",
                "Orange County ruling artifact label lacks a department",
                details={
                    "division": division,
                    "label": label,
                    "url": artifact_url,
                },
            )
        department = _normalized_department(department_match.group(1))
        judicial_officer = None
        if division == "civil":
            judicial_officer = _clean(
                re.split(r"\s+-\s+Dept\.?", label, maxsplit=1, flags=re.I)[0]
            )
        panel_heading = anchor.find_previous("h3")
        panel = _clean(
            panel_heading.get_text(" ", strip=True)
            if panel_heading
            else None
        )
        canonical_ref = (
            "OC-TENTATIVE-RULING-INDEX:"
            + hashlib.sha256(artifact_url.encode("utf-8")).hexdigest()
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "source_id": RULING_SOURCE_IDS[division],
                "record_kind": "tentative_ruling_artifact_index",
                "court": {
                    "court_id": COURT_ID,
                    "name": COURT_NAME,
                    "county_fips": COUNTY_FIPS,
                    "state_code": STATE_CODE,
                },
                "division": division,
                "panel": panel,
                "department": department,
                "judicial_officer": judicial_officer,
                "label": label,
                "artifact_url": artifact_url,
                "artifact_format": parsed.path.rsplit(".", 1)[-1].lower(),
                "publication_state": "linked_by_current_directory",
                "directory_url": response_url,
                "retrieved_at": retrieved_at,
            }
        )
    return records


def ruling_index(
    *,
    division: str = "all",
    department: str | None = None,
    client: OrangeCourtClient | Any | None = None,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Return current ruling artifacts without imposing a local row cap."""

    if division not in {"all", *RULING_DIRECTORY_URLS}:
        raise OrangeCourtSelectionError(
            "unknown_ruling_division",
            f"unknown Orange County ruling division: {division}",
        )
    source_client = client or OrangeCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    divisions = (
        tuple(RULING_DIRECTORY_URLS)
        if division == "all"
        else (division,)
    )
    records: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    raw_refs: list[str] = []
    for current_division in divisions:
        response = source_client.page(
            RULING_DIRECTORY_URLS[current_division]
        )
        raw_refs.append(response.url)
        parsed = parse_ruling_directory(
            response.text,
            division=current_division,
            response_url=response.url,
            retrieved_at=retrieved_at,
        )
        counts[current_division] = len(parsed)
        records.extend(parsed)

    if department:
        normalized = _normalized_department(department)
        records = [
            record
            for record in records
            if _normalized_department(record["department"]) == normalized
        ]

    source = (
        _family_source()
        if division == "all"
        else _ruling_source(division)
    )
    query = _query(
        source,
        "ruling-index",
        {
            "division": division,
            "department": (
                _normalized_department(department) if department else None
            ),
        },
        metadata={
            "bounds": {
                "caller_limit": None,
                "transport": "one current directory page per division",
                "source_window": "rolling current department publications",
            },
            "directory_counts_before_filter": counts,
        },
    )
    warnings = list(RULING_WARNINGS)
    if counts.get("family") == 0:
        warnings.append(
            "The current family-law directory publishes no ruling artifacts; "
            "older department child pages remain separate archive/discovery "
            "routes."
        )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        raw_artifact_refs=raw_refs,
        warnings=warnings,
    )


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract layout-preserving text from one verified PDF artifact."""

    with tempfile.TemporaryDirectory(prefix="orange-court-pdf-") as temp_dir:
        pdf_path = Path(temp_dir) / "ruling.pdf"
        pdf_path.write_bytes(pdf_bytes)
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError as error:
            raise OrangeCourtError(
                "pdftotext_unavailable",
                "pdftotext is required to extract tentative-ruling text",
                category="local_dependency",
                status=ResultStatus.UNAVAILABLE,
            ) from error
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise OrangeCourtError(
                "orange_ruling_pdf_extraction_failed",
                "pdftotext could not extract the tentative-ruling artifact",
                category="artifact_parse",
                details={"stderr": detail},
            )
        text = completed.stdout.decode("utf-8", errors="replace")
        if not _clean(text):
            raise OrangeCourtSourceChangedError(
                "orange_ruling_pdf_empty_text",
                "Orange County ruling PDF yielded no extractable text",
            )
        return text


def parse_ruling_text(text: str) -> dict[str, Any]:
    """Extract durable header and case identifiers while retaining full text."""

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    department_match = re.search(
        r"\bDepartment\s+([A-Z0-9-]+)\b",
        normalized_text,
        re.I,
    )
    judge_match = re.search(
        r"^\s*(Judge|Commissioner)\s+([^\n]+?)\s*$",
        normalized_text,
        re.I | re.M,
    )
    hearing_match = re.search(
        r"Hearing Date(?:\s+and\s+Time)?\s*:\s*([^\n]+)",
        normalized_text,
        re.I,
    )
    hearing_label = _clean(hearing_match.group(1)) if hearing_match else None
    hearing_date = None
    hearing_time = None
    if hearing_label:
        date_match = re.search(
            r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
            hearing_label,
        )
        if date_match:
            hearing_date = _source_date_to_iso(date_match.group(1))
        time_match = re.search(
            r"\b(\d{1,2}:\d{2}\s*[AP]M)\b",
            hearing_label,
            re.I,
        )
        hearing_time = _clean(time_match.group(1)) if time_match else None

    full_case_pattern = (
        r"\b\d{2}-20\d{2}-\d{8}-[A-Z]{2}-[A-Z]{2}-[A-Z0-9]+\b"
    )
    short_case_pattern = r"\b20\d{2}-\d{8}\b"
    case_numbers: list[str] = []
    seen: set[str] = set()
    full_matches = list(re.finditer(full_case_pattern, normalized_text, re.I))
    for match in full_matches:
        value = match.group(0).upper()
        seen.add(value)
        case_numbers.append(value)
    for match in re.finditer(short_case_pattern, normalized_text, re.I):
        if any(
            match.start() >= full.start() and match.end() <= full.end()
            for full in full_matches
        ):
            continue
        value = match.group(0).upper()
        if value not in seen:
            seen.add(value)
            case_numbers.append(value)

    return {
        "department": (
            _normalized_department(department_match.group(1))
            if department_match
            else None
        ),
        "judicial_officer": (
            _clean(judge_match.group(2)) if judge_match else None
        ),
        "judicial_officer_title": (
            _clean(judge_match.group(1)) if judge_match else None
        ),
        "hearing_label": hearing_label,
        "hearing_date": hearing_date,
        "hearing_time": hearing_time,
        "case_numbers": case_numbers,
        "calendar_case_number_candidates": [
            value if value.startswith("30-") else f"30-{value}"
            for value in case_numbers
        ],
        "text": normalized_text,
        "text_sha256": hashlib.sha256(
            normalized_text.encode("utf-8")
        ).hexdigest(),
    }


def _header_timestamp(headers: Mapping[str, str]) -> str | None:
    raw = headers.get("Last-Modified") or headers.get("last-modified")
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ruling_document(
    division: str,
    department: str,
    *,
    client: OrangeCourtClient | Any | None = None,
    retrieved_at: str | None = None,
    download_path: Path | None = None,
    include_text: bool = True,
    text_extractor: Callable[[bytes], str] = extract_pdf_text,
) -> PublicRecordsResult:
    """Fetch one currently indexed tentative-ruling artifact."""

    if division not in RULING_DIRECTORY_URLS:
        raise OrangeCourtSelectionError(
            "unknown_ruling_division",
            f"unknown Orange County ruling division: {division}",
        )
    source_client = client or OrangeCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    normalized_department = _normalized_department(department)
    directory_response = source_client.page(
        RULING_DIRECTORY_URLS[division]
    )
    directory_records = parse_ruling_directory(
        directory_response.text,
        division=division,
        response_url=directory_response.url,
        retrieved_at=retrieved_at,
    )
    matches = [
        record
        for record in directory_records
        if _normalized_department(record["department"])
        == normalized_department
    ]
    query = _query(
        _ruling_source(division),
        "ruling",
        {
            "division": division,
            "department": normalized_department,
            "include_text": include_text,
        },
        metadata={
            "bounds": {
                "caller_limit": 1,
                "transport": "one directory page and one matched artifact",
                "source_window": "current artifact linked by the directory",
            }
        },
    )
    if not matches:
        return PublicRecordsResult.success(
            query,
            [],
            retrieved_at=retrieved_at,
            raw_artifact_refs=[directory_response.url],
            warnings=RULING_WARNINGS,
        )
    if len(matches) != 1:
        raise OrangeCourtSourceChangedError(
            "orange_ruling_department_ambiguous",
            "Orange County ruling directory repeats a department",
            details={
                "division": division,
                "department": normalized_department,
                "matches": len(matches),
            },
        )

    index_record = matches[0]
    artifact_response = source_client.page(index_record["artifact_url"])
    artifact_bytes = artifact_response.body
    if not artifact_bytes.startswith(b"%PDF-"):
        raise OrangeCourtSourceChangedError(
            "orange_ruling_artifact_not_pdf",
            "Orange County ruling artifact is not a PDF",
            details={
                "url": artifact_response.url,
                "content_type": artifact_response.headers.get("Content-Type"),
                "magic": artifact_bytes[:16].hex(),
            },
        )
    if download_path:
        download_path.parent.mkdir(parents=True, exist_ok=True)
        download_path.write_bytes(artifact_bytes)

    parsed_text: dict[str, Any] = {
        "department": normalized_department,
        "judicial_officer": index_record.get("judicial_officer"),
        "judicial_officer_title": None,
        "hearing_label": None,
        "hearing_date": None,
        "hearing_time": None,
        "case_numbers": [],
        "calendar_case_number_candidates": [],
        "text": None,
        "text_sha256": None,
    }
    if include_text:
        parsed_text = parse_ruling_text(text_extractor(artifact_bytes))
        parsed_department = parsed_text.get("department")
        if (
            parsed_department
            and _normalized_department(parsed_department)
            != normalized_department
        ):
            raise OrangeCourtSourceChangedError(
                "orange_ruling_department_mismatch",
                "Orange County ruling PDF names a different department",
                details={
                    "directory_department": normalized_department,
                    "pdf_department": parsed_department,
                },
            )

    digest = hashlib.sha256(artifact_bytes).hexdigest()
    canonical_ref = f"OC-TENTATIVE-RULING:{digest}"
    record = {
        "canonical_ref": canonical_ref,
        "source_id": RULING_SOURCE_IDS[division],
        "record_kind": "tentative_ruling_document",
        "court": index_record["court"],
        "division": division,
        "panel": index_record.get("panel"),
        "department": normalized_department,
        "judicial_officer": (
            parsed_text.get("judicial_officer")
            or index_record.get("judicial_officer")
        ),
        "judicial_officer_title": parsed_text.get(
            "judicial_officer_title"
        ),
        "hearing": {
            "label": parsed_text.get("hearing_label"),
            "date": parsed_text.get("hearing_date"),
            "time": parsed_text.get("hearing_time"),
        },
        "case_numbers": parsed_text.get("case_numbers", []),
        "calendar_case_number_candidates": parsed_text.get(
            "calendar_case_number_candidates",
            [],
        ),
        "text": parsed_text.get("text"),
        "text_sha256": parsed_text.get("text_sha256"),
        "artifact": {
            "url": artifact_response.url,
            "format": "pdf",
            "sha256": digest,
            "bytes": len(artifact_bytes),
            "content_type": artifact_response.headers.get("Content-Type"),
            "etag": artifact_response.headers.get("ETag"),
            "last_modified": _header_timestamp(
                artifact_response.headers
            ),
            "local_path": str(download_path) if download_path else None,
            "text_extraction": (
                "pdftotext-layout" if include_text else "not_requested"
            ),
        },
        "directory_record": index_record,
        "retrieved_at": retrieved_at,
        "complementary_routes": _case_complementary_routes(None),
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
        raw_artifact_refs=[
            directory_response.url,
            artifact_response.url,
        ],
        warnings=RULING_WARNINGS,
    )


def _case_complementary_routes(
    case_number: str | None,
) -> list[dict[str, Any]]:
    return [
        {
            "source_id": CASE_NAME_SOURCE_ID,
            "source": "Orange County Case Name Search",
            "url": CASE_NAME_SEARCH_URL,
            "access": "free account",
            "adds": "person/business name discovery across case systems",
        },
        {
            "source_id": CASE_INDEX_SOURCE_ID,
            "source": "Orange County Case Index",
            "url": CASE_INDEX_URL,
            "access": "anonymous terms acceptance",
            "adds": "permanent limited case filing index information",
            "case_number": case_number,
        },
        {
            "source_id": CASE_PORTALS_SOURCE_ID,
            "source": "Orange County case-type public portals",
            "url": CASE_ACCESS_URL,
            "access": "anonymous terms acceptance by component",
            "adds": (
                "civil case summaries, registers, and post-2008 documents, "
                "plus criminal/traffic, family, probate, and small-claims "
                "case detail beyond the calendar"
            ),
            "case_number": case_number,
            "components": {
                "civil": CIVIL_CASE_ACCESS_URL,
                "criminal_traffic": CRIMINAL_CASE_ACCESS_URL,
                "family": FAMILY_CASE_ACCESS_URL,
                "probate": PROBATE_CASE_ACCESS_URL,
                "small_claims": SMALL_CLAIMS_CASE_ACCESS_URL,
            },
        },
        {
            "source_id": PROBATE_NOTES_SOURCE_ID,
            "source": "Orange County Probate Notes",
            "url": PROBATE_NOTES_URL,
            "access": "public web application",
            "adds": "examiner notes and probate calendar preparation detail",
        },
        {
            "source_id": RECORDS_SOURCE_ID,
            "source": "Orange County Records and Copy Requests",
            "url": RECORDS_URL,
            "access": "online, in-person, and written routes by case type",
            "adds": (
                "record copies, certification, older records, and retained "
                "files dating as far back as 1898 depending on case type"
            ),
        },
        {
            "source_id": CASE_INDEX_PRODUCT_SOURCE_ID,
            "source": "Orange County Monthly and Legacy Case Index Products",
            "url": CASE_INDEX_ORDER_URL,
            "access": "$50 court order product per index",
            "adds": (
                "plain-text civil/small-claims, criminal/traffic, family, "
                "and probate name-index files, including selected legacy years"
            ),
        },
    ]


def source_records() -> list[dict[str, Any]]:
    """Describe implemented components and useful adjacent official routes."""

    records: list[dict[str, Any]] = [
        {
            "source_id": SOURCE_FAMILY_ID,
            "record_kind": "source_manifest",
            "name": "Orange County Superior Court Public Record Sources",
            "url": ONLINE_SERVICES_URL,
            "implemented_operations": ["sources", "probe"],
            "component_source_ids": [
                CALENDAR_SOURCE_ID,
                *RULING_SOURCE_IDS.values(),
                CASE_NAME_SOURCE_ID,
                CASE_PORTALS_SOURCE_ID,
                CASE_INDEX_SOURCE_ID,
                CASE_INDEX_PRODUCT_SOURCE_ID,
                PROBATE_NOTES_SOURCE_ID,
                RECORDS_SOURCE_ID,
            ],
        },
        {
            "source_id": CALENDAR_SOURCE_ID,
            "record_kind": "source_manifest",
            "name": "Orange County Superior Court Cases on Calendar",
            "url": CALENDAR_URL,
            "implemented_operations": ["calendar", "probe"],
            "coverage": {
                "case_categories": list(CATEGORY_CODES),
                "fields": list(EXPECTED_CALENDAR_HEADERS),
                "published_future_window": "six weeks",
            },
            "bounds": {
                "caller_limit": "optional; omitted exhausts all pages",
                "transport_page_size": TRANSPORT_PAGE_SIZE,
                "server_behavior": (
                    "50 is the largest published selector; an observed "
                    "unsupported value of 500 fell back to 15"
                ),
                "probe": "one calendar form and at most one 50-row page",
            },
        }
    ]
    for division in RULING_DIRECTORY_URLS:
        records.append(
            {
                "source_id": RULING_SOURCE_IDS[division],
                "record_kind": "source_manifest",
                "name": (
                    "Orange County Superior Court "
                    f"{division.title()} Tentative Rulings"
                ),
                "url": RULING_DIRECTORY_URLS[division],
                "implemented_operations": [
                    "ruling-index",
                    "ruling",
                    "probe",
                ],
                "coverage": (
                    "current artifacts linked by the rolling department "
                    "directory"
                ),
                "artifact_formats": ["pdf"],
            }
        )
    records.extend(
        {
            "record_kind": "complementary_source",
            **route,
        }
        for route in _case_complementary_routes(None)
    )
    return records


def probe_sources(
    *,
    client: OrangeCourtClient | Any | None = None,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Run bounded health probes across the implemented source components."""

    source_client = client or OrangeCourtClient()
    retrieved_at = retrieved_at or utc_now_iso()
    landing = source_client.calendar_landing()
    contract = parse_calendar_form(
        landing.text,
        response_url=landing.url,
    )
    criteria = CalendarCriteria(
        category="civil",
        date_from=contract.default_date_from,
        date_to=contract.default_date_from,
    )
    materialized = criteria.materialize(contract)
    form_data = _calendar_form_data(materialized, contract)
    calendar_response = source_client.calendar_first(form_data)
    calendar_page = parse_calendar_page(
        calendar_response.text,
        category="civil",
        retrieved_at=retrieved_at,
    )

    ruling_counts: dict[str, int] = {}
    raw_refs = [landing.url, calendar_response.url]
    for division, url in RULING_DIRECTORY_URLS.items():
        response = source_client.page(url)
        raw_refs.append(response.url)
        ruling_counts[division] = len(
            parse_ruling_directory(
                response.text,
                division=division,
                response_url=response.url,
                retrieved_at=retrieved_at,
            )
        )

    record = {
        "canonical_ref": (
            "OC-COURT-PROBE:"
            + sha256_fingerprint(
                {
                    "form": contract.schema_fingerprint,
                    "calendar_total": calendar_page.total,
                    "ruling_counts": ruling_counts,
                }
            )
        ),
        "source_id": SOURCE_FAMILY_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "calendar": {
            "form_schema_fingerprint": contract.schema_fingerprint,
            "category_count": len(contract.category_codes),
            "categories": contract.category_codes,
            "source_default_date_from": contract.default_date_from,
            "source_default_date_to": contract.default_date_to,
            "transport_page_size": contract.transport_page_size,
            "one_day_civil_total": calendar_page.total,
            "probe_rows_returned": len(calendar_page.records),
        },
        "tentative_rulings": {
            "current_directory_counts": ruling_counts,
            "family_zero_is_valid_current_directory_state": (
                ruling_counts.get("family") == 0
            ),
        },
        "probe_bounds": {
            "calendar_pages": 1,
            "calendar_rows_at_most": TRANSPORT_PAGE_SIZE,
            "ruling_directory_pages": len(RULING_DIRECTORY_URLS),
            "ruling_artifacts_downloaded": 0,
        },
        "retrieved_at": retrieved_at,
    }
    query = _query(
        _family_source(),
        "probe",
        {},
        metadata={
            "bounds": record["probe_bounds"],
            "probe_is_not_full_corpus_enumeration": True,
        },
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
        raw_artifact_refs=raw_refs,
        warnings=(
            *CALENDAR_WARNINGS,
            *RULING_WARNINGS,
        ),
    )


def _failure_result(
    source: SourceMetadata,
    operation: str,
    parameters: Mapping[str, Any],
    error: OrangeCourtError,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        _query(
            source,
            operation,
            parameters,
            limit=limit,
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


def _client_from_args(args: argparse.Namespace) -> OrangeCourtClient:
    return OrangeCourtClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _add_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="minimum seconds between source requests",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="bounded HTTP attempts for transient failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Orange County Superior Court hearing calendars and "
            "tentative rulings"
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    sources_parser = subparsers.add_parser(
        "sources",
        help="Describe implemented and complementary official sources",
    )
    _add_request_args(sources_parser)

    calendar_parser = subparsers.add_parser(
        "calendar",
        aliases=["search"],
        help="Search the Cases on Calendar publication",
    )
    calendar_parser.add_argument(
        "category",
        choices=tuple(CATEGORY_CODES),
    )
    calendar_parser.add_argument("--case-id")
    calendar_parser.add_argument("--case-year")
    calendar_parser.add_argument("--title")
    calendar_parser.add_argument("--location")
    calendar_parser.add_argument("--department")
    calendar_parser.add_argument("--date-from")
    calendar_parser.add_argument("--date-to")
    calendar_parser.add_argument("--hearing-time")
    calendar_parser.add_argument(
        "--limit",
        type=int,
        help="caller result bound; omit to exhaust all native pages",
    )
    calendar_parser.add_argument("--cursor")
    _add_request_args(calendar_parser)

    ruling_index_parser = subparsers.add_parser(
        "ruling-index",
        help="List every current tentative-ruling artifact",
    )
    ruling_index_parser.add_argument(
        "--division",
        choices=("all", *RULING_DIRECTORY_URLS),
        default="all",
    )
    ruling_index_parser.add_argument("--department")
    _add_request_args(ruling_index_parser)

    ruling_parser = subparsers.add_parser(
        "ruling",
        help="Fetch and extract one currently indexed ruling artifact",
    )
    ruling_parser.add_argument(
        "division",
        choices=tuple(RULING_DIRECTORY_URLS),
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
        help="return artifact metadata without running PDF text extraction",
    )
    _add_request_args(ruling_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Run bounded form, one-day calendar, and directory probes",
    )
    _add_request_args(probe_parser)
    return parser


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


def execute(
    args: argparse.Namespace,
    *,
    client: OrangeCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source-family operation and return its canonical envelope."""

    if args.command == "sources":
        return PublicRecordsResult.success(
            _query(_family_source(), "sources", {}),
            source_records(),
            warnings=(
                *CALENDAR_WARNINGS,
                *RULING_WARNINGS,
            ),
        )

    source_client = client or _client_from_args(args)
    owns_client = client is None
    try:
        if args.command in {"calendar", "search"}:
            criteria = CalendarCriteria(
                category=args.category,
                case_id=_clean(args.case_id),
                case_year=_clean(args.case_year),
                title=_clean(args.title),
                location=_clean(args.location),
                department=_clean(args.department),
                date_from=_clean(args.date_from),
                date_to=_clean(args.date_to),
                hearing_time=_clean(args.hearing_time),
            )
            result = calendar_search(
                criteria,
                limit=args.limit,
                cursor=args.cursor,
                client=source_client,
            )
            if log_results:
                _best_effort_log(
                    "calendar",
                    criteria.to_parameters(),
                    result,
                )
        elif args.command == "ruling-index":
            result = ruling_index(
                division=args.division,
                department=args.department,
                client=source_client,
            )
            if log_results:
                _best_effort_log(
                    "ruling-index",
                    {
                        "division": args.division,
                        "department": args.department,
                    },
                    result,
                )
        elif args.command == "ruling":
            result = ruling_document(
                args.division,
                args.department,
                client=source_client,
                download_path=args.download,
                include_text=not args.no_text,
            )
            if log_results:
                _best_effort_log(
                    "ruling",
                    {
                        "division": args.division,
                        "department": args.department,
                    },
                    result,
                )
        elif args.command == "probe":
            result = probe_sources(client=source_client)
        else:
            raise ValueError(f"unknown Orange County court command: {args.command}")
    except OrangeCourtError as error:
        if args.command in {"calendar", "search"}:
            parameters = {
                "category": args.category,
                "case_id": args.case_id,
                "case_year": args.case_year,
                "title": args.title,
                "location": args.location,
                "department": args.department,
                "date_from": args.date_from,
                "date_to": args.date_to,
                "hearing_time": args.hearing_time,
            }
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
                _ruling_source(args.division),
                "ruling",
                {
                    "division": args.division,
                    "department": args.department,
                    "include_text": not args.no_text,
                },
                error,
            )
        else:
            source = (
                _ruling_source(args.division)
                if args.command == "ruling-index"
                and args.division != "all"
                else _family_source()
            )
            result = _failure_result(
                source,
                args.command,
                {},
                error,
            )
    finally:
        if owns_client:
            closer = getattr(source_client, "close", None)
            if callable(closer):
                closer()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    result = execute(args)
    summary = f"Orange County court {args.command} ({result.status.value})"
    _emit(result, args, summary=summary)
    return (
        0
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}
        else 2
    )


if __name__ == "__main__":
    sys.exit(main())
