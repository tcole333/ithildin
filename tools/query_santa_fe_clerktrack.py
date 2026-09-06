#!/usr/bin/env python3
"""Query Santa Fe County ClerkTrack recorded-document index metadata.

The County Clerk publishes an INDEX/INDEX guest login for index-only research.
This adapter follows the verified ASP.NET WebForms flow, traverses the source's
native pages until exhaustion unless the caller requests a result window, and
never persists ClerkTrack's opaque detail selector.

Detail retrieval starts a fresh guest session, searches the published
instrument number, obtains the selector issued for that result, and verifies
the visible instrument identity before returning the detail metadata.

Examples:
    uv run python tools/query_santa_fe_clerktrack.py search \
        --name "MAYNARD*" --output /tmp/santa-fe-recordings.json
    uv run python tools/query_santa_fe_clerktrack.py search \
        --instrument 1019405 --json
    uv run python tools/query_santa_fe_clerktrack.py detail 1019405 --json
    uv run python tools/query_santa_fe_clerktrack.py probe --json
    uv run python tools/query_santa_fe_clerktrack.py routes --json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from tools.public_records_store import canonical_property_ref
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
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-nm-santa-fe-clerktrack-index"
SOURCE = SOURCE_ID
STATE_CODE = "NM"
COUNTY_GEOID = "35049"
COUNTY_NAME = "Santa Fe County"
OBSERVED_AT = "2026-07-31"

BASE_URL = "https://clerktrackweb.santafecountynm.gov/CTWeb/"
LOGIN_URL = urljoin(BASE_URL, "login.aspx")
MAIN_URL = urljoin(BASE_URL, "main.aspx")
SEARCH_URL = urljoin(BASE_URL, "recsearch.aspx")
RESULTS_URL = urljoin(BASE_URL, "results.aspx")
DETAIL_URL = urljoin(BASE_URL, "viewdetails.aspx")
INDEX_BOOKS_URL = urljoin(BASE_URL, "bksearch.aspx")
OFFICIAL_ACCESS_URL = (
    "https://www.santafecountynm.gov/clerk/divisions/"
    "public-records-access"
)
OFFICIAL_RECORDING_URL = (
    "https://www.santafecountynm.gov/clerk/divisions/recording-faq"
)
ASSESSOR_LAYER_SOURCE_ID = "us-nm-santa-fe-assessor-accounts"
TREASURER_ROUTE_ID = "us-nm-santa-fe-treasurer-paydici"
TREASURER_URL = (
    "https://paydici.com/santa-fe-treasurer-nm/"
    "search/property-tax-search-group"
)

PUBLIC_INDEX_USERNAME = "INDEX"
PUBLIC_INDEX_PASSWORD = "INDEX"
NATIVE_PAGE_SIZE_OBSERVED = 25
EXPECTED_SORT_EXPRESSION = "InstrumentNo ASC"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

PROBE_INSTRUMENT = "1019405"
PROBE_BOOK = "1477"
PROBE_PAGE = "604"
PROBE_RECORDING_DATE = "1998-04-08"
PROBE_DOCUMENT_TYPE = "QUITCLAIM DEED"

CURSOR_PREFIX = "sfc-clerktrack:v2:"
REQUIRED_WEBFORMS_FIELDS = frozenset(
    {"__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"}
)
SEARCH_CONTROL_NAMES = frozenset(
    {
        "txtName",
        "rbNameType",
        "txtDateF",
        "txtDateT",
        "txtInstr",
        "txtBook",
        "txtPage",
        "lstTypes",
        "txtLegal",
        "ac_subdivision",
        "txtLot",
        "txtBlock",
        "txtTract",
        "txtSection",
        "txtTown",
        "txtRange",
        "txtUnit",
        "txtInfo",
        "btnSearch",
    }
)
RESULT_HEADERS = (
    "",
    "Instr #",
    "Book",
    "Page",
    "Rec Date",
    "Document Type",
    "Grantors",
    "Grantees",
    "Legal Description",
    "Legal Information",
)
DETAIL_FIELD_LABELS = (
    "Instrument No",
    "Book",
    "Page",
    "Document Type",
    "Recorded Date",
    "Submitter",
    "Address",
    "Location",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Santa Fe County Clerk ClerkTrack Recorded Documents",
    source_role="recorder_instrument_index",
    base_url=SEARCH_URL,
    dataset_id="clerktrack-recorded-document-index",
    metadata={
        "authority": "Santa Fe County Clerk",
        "jurisdiction_geoid": COUNTY_GEOID,
        "record_identity_key": "instrument_number",
        "access": "county_published_index_guest_login",
        "native_pagination": "WebForms page selector",
        "detail_selector": "opaque retrieval state; never persisted",
        "document_images": "separate official purchase or copy-request route",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=f"{COUNTY_NAME}, New Mexico",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality=COUNTY_NAME,
)
SOURCE_WARNINGS = (
    (
        "Results are County Clerk index and detail metadata, not the recorded "
        "document image."
    ),
    (
        "The opaque ClerkTrack detail selector is retrieval state. The "
        "adapter reacquires it by instrument number in a fresh guest session "
        "and does not return or persist it."
    ),
    (
        "Clerk instruments are independent recorded-event evidence. Assessor "
        "recording fields are cross-source join hints, not a second Clerk "
        "record."
    ),
)

SOURCE_ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route_id": SOURCE_ID,
        "name": "ClerkTrack public recorded-document index",
        "url": SEARCH_URL,
        "authority": "Santa Fe County Clerk",
        "access": "county-published INDEX guest login",
        "record_grain": "one recorded-instrument index row",
        "automation": "implemented",
        "relationship_to_primary": "primary",
        "independent_evidence": True,
    },
    {
        "route_id": "us-nm-santa-fe-clerktrack-detail",
        "name": "ClerkTrack recorded-instrument detail",
        "url": DETAIL_URL,
        "authority": "Santa Fe County Clerk",
        "access": "fresh exact-instrument search followed by opaque selector",
        "record_grain": "one recorded-instrument detail view",
        "automation": "implemented",
        "relationship_to_primary": "same_clerk_instrument_detail",
        "independent_evidence": False,
    },
    {
        "route_id": "us-nm-santa-fe-clerktrack-public-images",
        "name": "ClerkTrack PUBLIC self-service document purchase",
        "url": LOGIN_URL,
        "authority": "Santa Fe County Clerk",
        "access": "county-published PUBLIC login; payment and email required",
        "record_grain": "purchased recorded-document image",
        "automation": "official acquisition complement",
        "relationship_to_primary": "same_clerk_document_artifact",
        "independent_evidence": False,
    },
    {
        "route_id": "us-nm-santa-fe-clerktrack-index-books",
        "name": "ClerkTrack Index Books",
        "url": INDEX_BOOKS_URL,
        "authority": "Santa Fe County Clerk",
        "access": "INDEX guest session",
        "record_grain": "historic grantor or grantee index-book page",
        "automation": "verified complement; not implemented here",
        "relationship_to_primary": "historic_clerk_index_complement",
        "independent_evidence": False,
    },
    {
        "route_id": "us-nm-santa-fe-clerk-copy-request",
        "name": "County Clerk official copy and in-person research route",
        "url": OFFICIAL_ACCESS_URL,
        "authority": "Santa Fe County Clerk",
        "access": "instrument-number request, purchase, or in-person research",
        "record_grain": "official recorded-document copy",
        "automation": "human acquisition complement",
        "relationship_to_primary": "same_clerk_document_artifact",
        "independent_evidence": False,
    },
    {
        "route_id": ASSESSOR_LAYER_SOURCE_ID,
        "name": "Santa Fe County Assessor Accounts layer",
        "url": (
            "https://sfcomaps.santafecountynm.gov/restsvc/rest/services/"
            "LAND/Accounts/MapServer/0"
        ),
        "authority": "Santa Fe County Assessor",
        "access": "anonymous ArcGIS query",
        "record_grain": "assessor parcel-account observation",
        "automation": "implemented separately",
        "relationship_to_primary": "field_matched_assessor_join_hints",
        "independent_evidence": True,
    },
    {
        "route_id": TREASURER_ROUTE_ID,
        "name": "Santa Fe County Treasurer property-tax search",
        "url": TREASURER_URL,
        "authority": "Santa Fe County Treasurer",
        "access": "public Paydici property-tax search",
        "record_grain": "treasurer property-tax account observation",
        "automation": "distinct official complement",
        "relationship_to_primary": "field_matched_distinct_tax_record",
        "independent_evidence": True,
    },
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    return text or None


def _text(element: Tag) -> str:
    return " ".join(element.get_text(" ", strip=True).replace("\xa0", " ").split())


def _path(url: str) -> str:
    return urlparse(url).path.rstrip("/").casefold()


def _iso_date(value: str | None, *, include_time: bool = False) -> str | None:
    text = _clean(value)
    if not text:
        return None
    formats = (
        ("%m/%d/%Y %I:%M:%S %p", True),
        ("%m/%d/%Y", False),
    )
    for format_string, has_time in formats:
        try:
            parsed = datetime.strptime(text, format_string)
        except ValueError:
            continue
        if include_time and has_time:
            return parsed.isoformat(timespec="seconds")
        return parsed.date().isoformat()
    raise ValueError(f"unrecognized ClerkTrack date: {text}")


def _source_date(value: str | None) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError(
            f"date must use YYYY-MM-DD: {text}"
        ) from error
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def _instrument_sort_key(value: str) -> str:
    return value.strip().casefold()


def _hidden_fields(form: Tag) -> dict[str, str]:
    return {
        str(control["name"]): str(control.get("value", ""))
        for control in form.select("input[type=hidden][name]")
    }


def _require_webforms_state(
    hidden_fields: Mapping[str, str],
    *,
    url: str,
) -> None:
    missing = sorted(
        field
        for field in REQUIRED_WEBFORMS_FIELDS
        if not hidden_fields.get(field)
    )
    if missing:
        raise SourceSchemaError(
            "ClerkTrack WebForms state changed",
            url=url,
            details={"missing_fields": missing},
        )


@dataclass(frozen=True)
class DocumentTypeOption:
    value: str
    label: str


@dataclass(frozen=True)
class LoginForm:
    action_url: str
    hidden_fields: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchForm:
    action_url: str
    hidden_fields: Mapping[str, str]
    document_types: tuple[DocumentTypeOption, ...]
    index_through_date: str | None
    index_through_date_raw: str | None
    schema_fingerprint: str
    document_types_fingerprint: str


@dataclass(frozen=True)
class SearchCriteria:
    name: str | None = None
    party_role: str = "Both"
    from_date: str | None = None
    to_date: str | None = None
    instrument: str | None = None
    book: str | None = None
    page: str | None = None
    document_types: tuple[str, ...] = ()
    legal: str | None = None
    subdivision: str | None = None
    lot: str | None = None
    block: str | None = None
    tract: str | None = None
    section: str | None = None
    township: str | None = None
    range_value: str | None = None
    unit: str | None = None
    additional_info: str | None = None

    def __post_init__(self) -> None:
        role = self.party_role.casefold()
        roles = {"both": "Both", "grantor": "Grantor", "grantee": "Grantee"}
        if role not in roles:
            raise ValueError("party role must be both, grantor, or grantee")
        object.__setattr__(self, "party_role", roles[role])
        for field_name in (
            "name",
            "from_date",
            "to_date",
            "instrument",
            "book",
            "page",
            "legal",
            "subdivision",
            "lot",
            "block",
            "tract",
            "section",
            "township",
            "range_value",
            "unit",
            "additional_info",
        ):
            object.__setattr__(
                self,
                field_name,
                _clean(getattr(self, field_name)),
            )
        document_types: list[str] = []
        seen: set[str] = set()
        for value in self.document_types:
            normalized = _clean(value)
            if normalized and normalized.casefold() not in seen:
                seen.add(normalized.casefold())
                document_types.append(normalized)
        object.__setattr__(self, "document_types", tuple(document_types))
        from_source = _source_date(self.from_date)
        to_source = _source_date(self.to_date)
        if from_source and to_source:
            start = datetime.strptime(self.from_date or "", "%Y-%m-%d")
            end = datetime.strptime(self.to_date or "", "%Y-%m-%d")
            if start > end:
                raise ValueError("from date must not be after to date")
        if not any(
            (
                self.name,
                self.from_date,
                self.to_date,
                self.instrument,
                self.book,
                self.page,
                self.document_types,
                self.legal,
                self.subdivision,
                self.lot,
                self.block,
                self.tract,
                self.section,
                self.township,
                self.range_value,
                self.unit,
                self.additional_info,
            )
        ):
            raise ValueError("provide at least one ClerkTrack search selector")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "party_role": self.party_role,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "instrument": self.instrument,
            "book": self.book,
            "page": self.page,
            "document_types": list(self.document_types),
            "legal": self.legal,
            "subdivision": self.subdivision,
            "lot": self.lot,
            "block": self.block,
            "tract": self.tract,
            "section": self.section,
            "township": self.township,
            "range": self.range_value,
            "unit": self.unit,
            "additional_info": self.additional_info,
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.to_dict())


@dataclass(frozen=True)
class IndexRow:
    selector: str
    instrument_number: str
    book: str | None
    page: str | None
    recording_date_raw: str
    recording_date: str
    document_type: str
    grantors_display_raw: str | None
    grantees_display_raw: str | None
    legal_description_raw: str | None
    legal_information_raw: str | None


@dataclass(frozen=True)
class ResultsPage:
    page_number: int
    page_count: int
    total_records: int
    rows: tuple[IndexRow, ...]
    postback_values: Mapping[str, Any]
    search_state: str | None
    sort_expression: str | None
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class SearchCollection:
    rows: tuple[IndexRow, ...]
    total_records: int
    pages_fetched: int
    next_cursor: str | None
    search_form: SearchForm
    results_schema_fingerprint: str | None


@dataclass(frozen=True)
class ResultSnapshot:
    total_records: int
    page_count: int
    first_page_identity_fingerprint: str
    index_through_date: str | None
    results_schema_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "page_count": self.page_count,
            "first_page_identity_fingerprint": (
                self.first_page_identity_fingerprint
            ),
            "index_through_date": self.index_through_date,
            "results_schema_fingerprint": (
                self.results_schema_fingerprint
            ),
        }


@dataclass(frozen=True)
class DetailFields:
    instrument_number: str
    book: str | None
    page: str | None
    document_type: str
    recorded_date_raw: str
    recording_date: str
    recording_datetime_local: str | None
    submitter: str | None
    address: str | None
    location: str | None
    legal_information: tuple[str, ...]
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]
    descriptions: tuple[str, ...]
    schema_fingerprint: str


def parse_login_form(html: str, *, source_url: str = LOGIN_URL) -> LoginForm:
    """Parse the county-published INDEX login form."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#loginform")
    if form is None:
        raise SourceSchemaError(
            "ClerkTrack login form changed",
            url=source_url,
        )
    controls = {str(item.get("name")) for item in form.select("[name]")}
    required = {"txtUser", "txtPwd", "btnLogin"}
    if not required.issubset(controls):
        raise SourceSchemaError(
            "ClerkTrack login controls changed",
            url=source_url,
            details={"missing_controls": sorted(required - controls)},
        )
    page_text = _text(soup)
    if PUBLIC_INDEX_USERNAME not in page_text:
        raise SourceSchemaError(
            "ClerkTrack no longer publishes the INDEX guest route",
            url=source_url,
        )
    hidden = _hidden_fields(form)
    _require_webforms_state(hidden, url=source_url)
    action = urljoin(source_url, str(form.get("action", "")))
    fingerprint = sha256_fingerprint(
        {
            "form_id": "loginform",
            "action_path": _path(action),
            "controls": sorted(controls),
            "hidden_state_fields": sorted(
                field
                for field in hidden
                if field.startswith("__")
            ),
        }
    )
    return LoginForm(action, hidden, fingerprint)


def parse_search_form(
    html: str,
    *,
    source_url: str = SEARCH_URL,
) -> SearchForm:
    """Parse and validate the recording-index search form."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#searchForm")
    if form is None:
        raise SourceSchemaError(
            "ClerkTrack recording search form changed",
            url=source_url,
        )
    controls = {str(item.get("name")) for item in form.select("[name]")}
    missing = sorted(SEARCH_CONTROL_NAMES - controls)
    if missing:
        raise SourceSchemaError(
            "ClerkTrack recording search controls changed",
            url=source_url,
            details={"missing_controls": missing},
        )
    hidden = _hidden_fields(form)
    _require_webforms_state(hidden, url=source_url)
    select = form.select_one("select#lstTypes")
    if select is None or not select.has_attr("multiple"):
        raise SourceSchemaError(
            "ClerkTrack document-type selector changed",
            url=source_url,
        )
    all_option = select.select_one('option[value="-1"][selected]')
    if all_option is None:
        raise SourceSchemaError(
            "ClerkTrack all-document-types default changed",
            url=source_url,
        )
    document_types = tuple(
        DocumentTypeOption(
            value=str(option.get("value", "")),
            label=_text(option),
        )
        for option in select.select("option")
        if str(option.get("value", "")) != "-1" and _text(option)
    )
    if not document_types:
        raise SourceSchemaError(
            "ClerkTrack document-type inventory is empty",
            url=source_url,
        )
    index_label = soup.select_one("#lblIndexDate")
    index_raw = _clean(index_label.get_text(" ", strip=True)) if index_label else None
    index_date = None
    if index_raw:
        match = re.fullmatch(
            r"Last Index Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
            index_raw,
        )
        if not match:
            raise SourceSchemaError(
                "ClerkTrack last-index-date marker changed",
                url=source_url,
                details={"observed": index_raw},
            )
        try:
            index_date = _iso_date(match.group(1))
        except ValueError as error:
            raise SourceSchemaError(
                "ClerkTrack last-index date is invalid",
                url=source_url,
                details={"observed": index_raw},
            ) from error
    action = urljoin(source_url, str(form.get("action", "")))
    schema = sha256_fingerprint(
        {
            "form_id": "searchForm",
            "action_path": _path(action),
            "controls": sorted(controls),
            "document_type_select": {
                "name": "lstTypes",
                "multiple": True,
                "all_value": "-1",
            },
        }
    )
    types_fingerprint = sha256_fingerprint(
        [
            {"value": option.value, "label": option.label}
            for option in document_types
        ]
    )
    return SearchForm(
        action_url=action,
        hidden_fields=hidden,
        document_types=document_types,
        index_through_date=index_date,
        index_through_date_raw=index_raw,
        schema_fingerprint=schema,
        document_types_fingerprint=types_fingerprint,
    )


def _result_selector(row: Tag, *, source_url: str) -> str:
    for cell in row.select("td"):
        onclick = unescape(str(cell.get("onclick", "")))
        match = re.search(
            r"viewdetails\.aspx\?param=([^']+)",
            onclick,
            flags=re.I,
        )
        if match:
            return match.group(1)
    raise SourceSchemaError(
        "ClerkTrack result detail selector changed",
        url=source_url,
    )


def parse_results_page(
    html: str,
    *,
    source_url: str = RESULTS_URL,
    expected_page: int | None = None,
) -> ResultsPage:
    """Parse one native ClerkTrack results page."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#resultForm")
    grid = soup.select_one("table#gvItems")
    if form is None or grid is None:
        raise SourceSchemaError(
            "ClerkTrack result grid changed",
            url=source_url,
        )
    headers = tuple(_text(cell) for cell in grid.select("th"))
    if headers != RESULT_HEADERS:
        raise SourceSchemaError(
            "ClerkTrack result columns changed",
            url=source_url,
            details={
                "expected_headers": list(RESULT_HEADERS),
                "observed_headers": list(headers),
            },
        )
    total_label = soup.select_one("#lblTotalResults")
    total_text = _clean(total_label.get_text(" ", strip=True)) if total_label else None
    match = re.fullmatch(r"([\d,]+)\s+records?\s+found", total_text or "")
    if not match:
        raise SourceSchemaError(
            "ClerkTrack total-result marker changed",
            url=source_url,
            details={"observed": total_text},
        )
    total_records = int(match.group(1).replace(",", ""))
    pager = grid.select_one("select#gvItems_ctl01_ddlPaging")
    if pager is None:
        if total_records > NATIVE_PAGE_SIZE_OBSERVED:
            raise SourceSchemaError(
                "ClerkTrack native page selector changed",
                url=source_url,
            )
        page_number = 1
        page_count = 1
        page_values = [1]
    else:
        page_values = [
            int(str(option.get("value", "")))
            for option in pager.select("option")
            if str(option.get("value", "")).isdigit()
        ]
        selected = pager.select("option[selected]")
        if not page_values or len(selected) != 1:
            raise SourceSchemaError(
                "ClerkTrack native page state changed",
                url=source_url,
            )
        page_number = int(str(selected[0].get("value")))
        page_count = max(page_values)
        if page_values != list(range(1, page_count + 1)):
            raise SourceSchemaError(
                "ClerkTrack native page sequence changed",
                url=source_url,
                details={"page_values": page_values},
            )
    expected_page_count = max(
        1,
        (
            total_records + NATIVE_PAGE_SIZE_OBSERVED - 1
        )
        // NATIVE_PAGE_SIZE_OBSERVED,
    )
    if page_count != expected_page_count:
        raise SourceSchemaError(
            "ClerkTrack native page count does not match its total",
            url=source_url,
            details={
                "total_records": total_records,
                "native_page_size": NATIVE_PAGE_SIZE_OBSERVED,
                "expected_page_count": expected_page_count,
                "observed_page_count": page_count,
            },
        )
    if expected_page is not None and page_number != expected_page:
        raise SourceSchemaError(
            "ClerkTrack page post did not reach the requested page",
            url=source_url,
            details={
                "expected_page": expected_page,
                "observed_page": page_number,
            },
        )
    rows: list[IndexRow] = []
    for row in grid.select('tr[title="Click to view record detail."]'):
        cells = row.select("td")
        if len(cells) != len(RESULT_HEADERS):
            raise SourceSchemaError(
                "ClerkTrack result row width changed",
                url=source_url,
                details={"observed_cells": len(cells)},
            )
        recording_date_raw = _text(cells[4])
        try:
            recording_date = _iso_date(recording_date_raw)
        except ValueError as error:
            raise SourceSchemaError(
                "ClerkTrack result date format changed",
                url=source_url,
                details={"observed": recording_date_raw},
            ) from error
        instrument = _text(cells[1])
        document_type = _text(cells[5])
        if not instrument or not recording_date or not document_type:
            raise SourceSchemaError(
                "ClerkTrack result identity fields are empty",
                url=source_url,
            )
        rows.append(
            IndexRow(
                selector=_result_selector(row, source_url=source_url),
                instrument_number=instrument,
                book=_clean(_text(cells[2])),
                page=_clean(_text(cells[3])),
                recording_date_raw=recording_date_raw,
                recording_date=recording_date,
                document_type=document_type,
                grantors_display_raw=_clean(_text(cells[6])),
                grantees_display_raw=_clean(_text(cells[7])),
                legal_description_raw=_clean(_text(cells[8])),
                legal_information_raw=_clean(_text(cells[9])),
            )
        )
    if not rows:
        raise SourceSchemaError(
            "ClerkTrack result grid has no instrument rows",
            url=source_url,
        )
    expected_rows = min(
        NATIVE_PAGE_SIZE_OBSERVED,
        total_records
        - ((page_number - 1) * NATIVE_PAGE_SIZE_OBSERVED),
    )
    if len(rows) != expected_rows:
        raise SourceSchemaError(
            "ClerkTrack native page is incomplete",
            url=source_url,
            details={
                "total_records": total_records,
                "page_number": page_number,
                "expected_rows": expected_rows,
                "parsed_rows": len(rows),
            },
        )
    instrument_numbers = [row.instrument_number for row in rows]
    if len(set(instrument_numbers)) != len(instrument_numbers):
        raise SourceSchemaError(
            "ClerkTrack native page repeated an instrument identity",
            url=source_url,
            details={"page_number": page_number},
        )
    instrument_sort_keys = [
        _instrument_sort_key(value)
        for value in instrument_numbers
    ]
    if instrument_sort_keys != sorted(instrument_sort_keys):
        raise SourceSchemaError(
            "ClerkTrack native page is not in instrument order",
            url=source_url,
            details={"page_number": page_number},
        )
    hidden = _hidden_fields(form)
    _require_webforms_state(hidden, url=source_url)
    if pager is not None:
        hidden["gvItems$ctl01$ddlPaging"] = str(page_number)
    search_state = _clean(hidden.get("searchsc"))
    sort_expression = _clean(hidden.get("sortexp"))
    if sort_expression != EXPECTED_SORT_EXPRESSION:
        raise SourceSchemaError(
            "ClerkTrack result ordering changed",
            url=source_url,
            details={
                "expected": EXPECTED_SORT_EXPRESSION,
                "observed": sort_expression,
            },
        )
    schema = sha256_fingerprint(
        {
            "form_id": "resultForm",
            "action_path": _path(
                urljoin(source_url, str(form.get("action", "")))
            ),
            "grid_id": "gvItems",
            "headers": list(headers),
            "pager_name": (
                "gvItems$ctl01$ddlPaging"
                if pager is not None
                else None
            ),
            "row_width": len(RESULT_HEADERS),
        }
    )
    return ResultsPage(
        page_number=page_number,
        page_count=page_count,
        total_records=total_records,
        rows=tuple(rows),
        postback_values=hidden,
        search_state=search_state,
        sort_expression=sort_expression,
        schema_fingerprint=schema,
        source_url=source_url,
    )


def parse_no_results(
    html: str,
    *,
    source_url: str = SEARCH_URL,
) -> bool:
    """Return true only for ClerkTrack's explicit no-records marker."""

    soup = BeautifulSoup(html, "html.parser")
    message = soup.select_one("#lblError")
    return (
        _clean(message.get_text(" ", strip=True)) if message else None
    ) == "No records found."


def _direct_child_table(element: Tag, section: Tag) -> Tag | None:
    current: Tag | None = element
    while current is not None and current.parent is not section:
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return current if current is not section else None


def _values_after_header(
    section: Tag,
    label: str,
) -> tuple[str, ...]:
    header = next(
        (
            item
            for item in section.select("span.detailheader")
            if _text(item).rstrip(":").casefold() == label.casefold()
        ),
        None,
    )
    if header is None:
        return ()
    table = _direct_child_table(header, section)
    value_table = table.find_next_sibling("table") if table else None
    if not isinstance(value_table, Tag):
        return ()
    values = []
    for row in value_table.select("tr"):
        cells = row.select("td")
        value = _clean(_text(cells[-1])) if cells else None
        if value:
            values.append(value)
    return tuple(values)


def _legal_values(section: Tag) -> tuple[str, ...]:
    header_row = next(
        (
            item
            for item in section.select("tr.searchseparator")
            if _text(item).casefold() == "legal information"
        ),
        None,
    )
    if header_row is None:
        return ()
    table = _direct_child_table(header_row, section)
    value_table = table.find_next_sibling("table") if table else None
    if not isinstance(value_table, Tag):
        return ()
    values = []
    for row in value_table.select("tr"):
        cells = row.select("td")
        value = _clean(_text(cells[-1])) if cells else None
        if value:
            values.append(value)
    return tuple(values)


def parse_detail_page(
    html: str,
    *,
    source_url: str = DETAIL_URL,
) -> DetailFields:
    """Parse one ClerkTrack recorded-instrument detail view."""

    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#divDocInfo")
    section_one = soup.select_one("#section-1")
    section_two = soup.select_one("#section-2")
    if container is None or section_one is None or section_two is None:
        raise SourceSchemaError(
            "ClerkTrack instrument detail layout changed",
            url=source_url,
        )
    fields: dict[str, str | None] = {}
    for row in section_one.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        label = _clean(_text(cells[1]))
        if not label or not label.endswith(":"):
            continue
        normalized_label = label.rstrip(":")
        if normalized_label in DETAIL_FIELD_LABELS:
            fields[normalized_label] = _clean(_text(cells[3]))
    missing = [
        label
        for label in ("Instrument No", "Document Type", "Recorded Date")
        if not fields.get(label)
    ]
    if missing:
        raise SourceSchemaError(
            "ClerkTrack detail identity fields changed",
            url=source_url,
            details={"missing_fields": missing},
        )
    recorded_raw = str(fields["Recorded Date"])
    try:
        recording_date = _iso_date(recorded_raw)
        recording_datetime = _iso_date(recorded_raw, include_time=True)
    except ValueError as error:
        raise SourceSchemaError(
            "ClerkTrack detail date format changed",
            url=source_url,
            details={"observed": recorded_raw},
        ) from error
    schema = sha256_fingerprint(
        {
            "container": "divDocInfo",
            "sections": ["section-1", "section-2"],
            "record_fields": list(DETAIL_FIELD_LABELS),
            "party_groups": ["Grantors", "Grantees"],
            "additional_group": "Descriptions",
        }
    )
    return DetailFields(
        instrument_number=str(fields["Instrument No"]),
        book=fields.get("Book"),
        page=fields.get("Page"),
        document_type=str(fields["Document Type"]),
        recorded_date_raw=recorded_raw,
        recording_date=str(recording_date),
        recording_datetime_local=recording_datetime,
        submitter=fields.get("Submitter"),
        address=fields.get("Address"),
        location=fields.get("Location"),
        legal_information=_legal_values(section_one),
        grantors=_values_after_header(section_one, "Grantors"),
        grantees=_values_after_header(section_one, "Grantees"),
        descriptions=_values_after_header(section_two, "Descriptions"),
        schema_fingerprint=schema,
    )


def _resolve_document_types(
    requested: Sequence[str],
    available: Sequence[DocumentTypeOption],
) -> list[str]:
    by_label: dict[str, str] = {}
    by_value: dict[str, str] = {}
    for option in available:
        by_label[option.label.casefold()] = option.value
        by_value[option.value] = option.value
    resolved: list[str] = []
    unknown: list[str] = []
    for item in requested:
        value = by_label.get(item.casefold()) or by_value.get(item)
        if value:
            resolved.append(value)
        else:
            unknown.append(item)
    if unknown:
        raise ValueError(
            "unknown ClerkTrack document type: "
            + ", ".join(unknown)
        )
    return resolved


def search_payload(
    form: SearchForm,
    criteria: SearchCriteria,
) -> dict[str, Any]:
    """Build the exact verified recording-index form submission."""

    selected_types = _resolve_document_types(
        criteria.document_types,
        form.document_types,
    )
    payload: dict[str, Any] = dict(form.hidden_fields)
    payload.update(
        {
            "txtName": criteria.name or "",
            "rbNameType": criteria.party_role,
            "txtDateF": _source_date(criteria.from_date),
            "txtDateT": _source_date(criteria.to_date),
            "txtInstr": criteria.instrument or "",
            "txtBook": criteria.book or "",
            "txtPage": criteria.page or "",
            "lstTypes": selected_types or "-1",
            "txtLegal": criteria.legal or "",
            "ac_subdivision": criteria.subdivision or "",
            "txtLot": criteria.lot or "",
            "txtBlock": criteria.block or "",
            "txtTract": criteria.tract or "",
            "txtSection": criteria.section or "",
            "txtTown": criteria.township or "",
            "txtRange": criteria.range_value or "",
            "txtUnit": criteria.unit or "",
            "txtInfo": criteria.additional_info or "",
            "btnSearch": "Search",
        }
    )
    return payload


def _stable_row_identity(row: IndexRow) -> dict[str, Any]:
    return {
        "instrument_number": row.instrument_number,
        "book": row.book,
        "page": row.page,
        "recording_date": row.recording_date,
        "document_type": row.document_type,
    }


def _result_snapshot(
    first_page: ResultsPage,
    search_form: SearchForm,
) -> ResultSnapshot:
    return ResultSnapshot(
        total_records=first_page.total_records,
        page_count=first_page.page_count,
        first_page_identity_fingerprint=sha256_fingerprint(
            [
                _stable_row_identity(row)
                for row in first_page.rows
            ]
        ),
        index_through_date=search_form.index_through_date,
        results_schema_fingerprint=first_page.schema_fingerprint,
    )


def _encode_cursor(
    *,
    criteria_fingerprint: str,
    page: int,
    offset: int,
    snapshot: ResultSnapshot,
) -> str:
    payload = canonical_json(
        {
            "version": 2,
            "query": criteria_fingerprint,
            "page": page,
            "offset": offset,
            "snapshot": snapshot.to_dict(),
        }
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return CURSOR_PREFIX + encoded


def _decode_cursor(
    cursor: str | None,
    *,
    criteria_fingerprint: str,
) -> tuple[int, int, ResultSnapshot | None]:
    if cursor is None:
        return 1, 0, None
    if not cursor.startswith(CURSOR_PREFIX):
        raise ValueError("invalid Santa Fe ClerkTrack cursor")
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid Santa Fe ClerkTrack cursor") from error
    if (
        not isinstance(payload, dict)
        or payload.get("version") != 2
        or payload.get("query") != criteria_fingerprint
    ):
        raise ValueError(
            "Santa Fe ClerkTrack cursor does not match this search"
        )
    page = payload.get("page")
    offset = payload.get("offset")
    snapshot = payload.get("snapshot")
    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or page < 1
        or isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
    ):
        raise ValueError("invalid Santa Fe ClerkTrack cursor position")
    if not isinstance(snapshot, dict):
        raise ValueError("invalid Santa Fe ClerkTrack cursor snapshot")
    total_records = snapshot.get("total_records")
    page_count = snapshot.get("page_count")
    first_page_fingerprint = snapshot.get(
        "first_page_identity_fingerprint"
    )
    index_through_date = snapshot.get("index_through_date")
    results_schema_fingerprint = snapshot.get(
        "results_schema_fingerprint"
    )
    if (
        isinstance(total_records, bool)
        or not isinstance(total_records, int)
        or total_records < 1
        or isinstance(page_count, bool)
        or not isinstance(page_count, int)
        or page_count < 1
        or not isinstance(first_page_fingerprint, str)
        or not first_page_fingerprint
        or (
            index_through_date is not None
            and not isinstance(index_through_date, str)
        )
        or not isinstance(results_schema_fingerprint, str)
        or not results_schema_fingerprint
    ):
        raise ValueError("invalid Santa Fe ClerkTrack cursor snapshot")
    return (
        page,
        offset,
        ResultSnapshot(
            total_records=total_records,
            page_count=page_count,
            first_page_identity_fingerprint=first_page_fingerprint,
            index_through_date=index_through_date,
            results_schema_fingerprint=results_schema_fingerprint,
        ),
    )


class ClerkTrackClient:
    """Persistent-session client for the verified ClerkTrack guest flow."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        request_budget: int | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if request_budget is not None and request_budget <= 0:
            raise ValueError("request budget must be positive")
        self._owns_session = session is None
        self.session = session or system_trust_session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self.request_count = 0
        self.request_budget = request_budget
        self.authenticated = False
        self.last_results_schema_fingerprint: str | None = None

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def __enter__(self) -> ClerkTrackClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if (
            parsed.scheme.casefold() != "https"
            or parsed.hostname != "clerktrackweb.santafecountynm.gov"
        ):
            raise SourceSchemaError(
                "ClerkTrack redirected outside the verified official host",
                url=url,
            )

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        self._validate_url(url)
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise SourceResponseError(
                    "ClerkTrack request budget exhausted",
                    url=url,
                    details={
                        "request_budget": self.request_budget,
                        "requests_made": self.request_count,
                    },
                )
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise TransportError(
                    f"ClerkTrack request failed: {error}",
                    url=url,
                    details={"attempts": attempt},
                ) from error
            final_url = str(getattr(response, "url", url))
            self._validate_url(final_url)
            status_code = int(response.status_code)
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise RateLimitedHTTPError(
                    status_code,
                    url=final_url,
                    response_text=str(getattr(response, "text", "")),
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=final_url,
                    response_text=str(getattr(response, "text", "")),
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=final_url,
                    response_text=str(getattr(response, "text", "")),
                )
            media_type = (
                str(getattr(response, "headers", {}).get("Content-Type", ""))
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            if media_type and media_type not in {
                "text/html",
                "application/xhtml+xml",
            }:
                raise SourceSchemaError(
                    "ClerkTrack returned non-HTML content",
                    url=final_url,
                    details={"content_type": media_type},
                )
            return response
        raise TransportError(
            f"ClerkTrack request failed: {last_error}",
            url=url,
        )

    def login(self) -> LoginForm:
        page = self._request(
            "GET",
            LOGIN_URL,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        form = parse_login_form(str(page.text), source_url=str(page.url))
        payload = dict(form.hidden_fields)
        payload.update(
            {
                "txtUser": PUBLIC_INDEX_USERNAME,
                "txtPwd": PUBLIC_INDEX_PASSWORD,
                "btnLogin": "Login",
            }
        )
        response = self._request(
            "POST",
            form.action_url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://clerktrackweb.santafecountynm.gov",
                "Referer": LOGIN_URL,
            },
            data=payload,
        )
        if _path(str(response.url)) != _path(MAIN_URL):
            raise SourceResponseError(
                "ClerkTrack public INDEX login was not accepted",
                url=str(response.url),
            )
        soup = BeautifulSoup(str(response.text), "html.parser")
        if soup.select_one('a[href="recsearch.aspx"]') is None:
            raise SourceSchemaError(
                "ClerkTrack authenticated landing page changed",
                url=str(response.url),
            )
        self.authenticated = True
        return form

    def search_form(self) -> SearchForm:
        if not self.authenticated:
            self.login()
        response = self._request(
            "GET",
            SEARCH_URL,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        if _path(str(response.url)) != _path(SEARCH_URL):
            raise SourceResponseError(
                "ClerkTrack recording search was not available",
                url=str(response.url),
            )
        return parse_search_form(
            str(response.text),
            source_url=str(response.url),
        )

    def _start_search(
        self,
        criteria: SearchCriteria,
    ) -> tuple[SearchForm, ResultsPage | None]:
        form = self.search_form()
        payload = search_payload(form, criteria)
        response = self._request(
            "POST",
            form.action_url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://clerktrackweb.santafecountynm.gov",
                "Referer": SEARCH_URL,
            },
            data=payload,
        )
        final_path = _path(str(response.url))
        if final_path == _path(RESULTS_URL):
            return form, parse_results_page(
                str(response.text),
                source_url=str(response.url),
                expected_page=1,
            )
        if (
            final_path == _path(SEARCH_URL)
            and parse_no_results(
                str(response.text),
                source_url=str(response.url),
            )
        ):
            return form, None
        raise SourceResponseError(
            "ClerkTrack search returned an unrecognized response",
            url=str(response.url),
        )

    def _page(
        self,
        first: ResultsPage,
        target_page: int,
    ) -> ResultsPage:
        payload = dict(first.postback_values)
        payload["gvItems$ctl01$ddlPaging"] = str(target_page)
        response = self._request(
            "POST",
            RESULTS_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://clerktrackweb.santafecountynm.gov",
                "Referer": RESULTS_URL,
            },
            data=payload,
        )
        page = parse_results_page(
            str(response.text),
            source_url=str(response.url),
            expected_page=target_page,
        )
        if (
            page.total_records != first.total_records
            or page.page_count != first.page_count
            or page.schema_fingerprint != first.schema_fingerprint
            or page.search_state != first.search_state
            or page.sort_expression != first.sort_expression
        ):
            raise SourceSchemaError(
                "ClerkTrack paging changed the search identity or schema",
                url=str(response.url),
                details={
                    "target_page": target_page,
                    "initial_total": first.total_records,
                    "observed_total": page.total_records,
                },
            )
        return page

    def search(
        self,
        criteria: SearchCriteria,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> SearchCollection:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")
        start_page, start_offset, expected_snapshot = _decode_cursor(
            cursor,
            criteria_fingerprint=criteria.fingerprint,
        )
        form, first = self._start_search(criteria)
        if first is None:
            if cursor:
                raise ValueError(
                    "Santa Fe ClerkTrack cursor points into an empty result"
                )
            return SearchCollection(
                rows=(),
                total_records=0,
                pages_fetched=0,
                next_cursor=None,
                search_form=form,
                results_schema_fingerprint=None,
            )
        snapshot = _result_snapshot(first, form)
        if (
            expected_snapshot is not None
            and snapshot != expected_snapshot
        ):
            raise SourceSchemaError(
                "ClerkTrack continuation snapshot changed",
                url=RESULTS_URL,
                details={
                    "expected_snapshot": (
                        expected_snapshot.to_dict()
                    ),
                    "observed_snapshot": snapshot.to_dict(),
                },
            )
        if start_page > first.page_count:
            raise ValueError(
                "Santa Fe ClerkTrack cursor page exceeds this result set"
            )
        seen_instruments: set[str] = set()
        last_sort_key: str | None = None

        def register_page(page: ResultsPage) -> None:
            nonlocal last_sort_key
            page_instruments = {
                row.instrument_number
                for row in page.rows
            }
            repeated = sorted(
                page_instruments.intersection(seen_instruments)
            )
            if repeated:
                raise SourceSchemaError(
                    "ClerkTrack paging repeated instrument identities",
                    url=page.source_url,
                    details={
                        "page_number": page.page_number,
                        "repeated_instruments": repeated,
                    },
                )
            first_sort_key = _instrument_sort_key(
                page.rows[0].instrument_number
            )
            if (
                last_sort_key is not None
                and first_sort_key <= last_sort_key
            ):
                raise SourceSchemaError(
                    "ClerkTrack paging made no forward progress",
                    url=page.source_url,
                    details={"page_number": page.page_number},
                )
            seen_instruments.update(page_instruments)
            last_sort_key = _instrument_sort_key(
                page.rows[-1].instrument_number
            )

        register_page(first)
        current = (
            first
            if start_page == 1
            else self._page(first, start_page)
        )
        if start_page != 1:
            register_page(current)
        pages_fetched = 1 if start_page == 1 else 2
        if start_offset >= len(current.rows):
            raise ValueError(
                "Santa Fe ClerkTrack cursor offset exceeds its native page"
            )
        collected: list[IndexRow] = []
        page_number = start_page
        offset = start_offset
        while True:
            for row_index in range(offset, len(current.rows)):
                row = current.rows[row_index]
                collected.append(row)
                if limit is not None and len(collected) >= limit:
                    if row_index + 1 < len(current.rows):
                        next_page = page_number
                        next_offset = row_index + 1
                    elif page_number < first.page_count:
                        next_page = page_number + 1
                        next_offset = 0
                    else:
                        next_page = 0
                        next_offset = 0
                    next_cursor = (
                        _encode_cursor(
                            criteria_fingerprint=criteria.fingerprint,
                            page=next_page,
                            offset=next_offset,
                            snapshot=snapshot,
                        )
                        if next_page
                        else None
                    )
                    return SearchCollection(
                        rows=tuple(collected),
                        total_records=first.total_records,
                        pages_fetched=pages_fetched,
                        next_cursor=next_cursor,
                        search_form=form,
                        results_schema_fingerprint=(
                            first.schema_fingerprint
                        ),
                    )
            if page_number >= first.page_count:
                break
            page_number += 1
            current = self._page(first, page_number)
            register_page(current)
            pages_fetched += 1
            offset = 0
        if (
            cursor is None
            and limit is None
            and len(collected) != first.total_records
        ):
            raise SourceSchemaError(
                "ClerkTrack exhaustive traversal did not match its total",
                url=RESULTS_URL,
                details={
                    "source_total": first.total_records,
                    "collected_rows": len(collected),
                },
            )
        return SearchCollection(
            rows=tuple(collected),
            total_records=first.total_records,
            pages_fetched=pages_fetched,
            next_cursor=None,
            search_form=form,
            results_schema_fingerprint=first.schema_fingerprint,
        )

    def detail(
        self,
        instrument_number: str,
    ) -> tuple[IndexRow, DetailFields, SearchForm]:
        instrument = _clean(instrument_number)
        if not instrument:
            raise ValueError("instrument number must not be empty")
        criteria = SearchCriteria(instrument=instrument)
        collection = self.search(criteria)
        self.last_results_schema_fingerprint = (
            collection.results_schema_fingerprint
        )
        exact = [
            row
            for row in collection.rows
            if row.instrument_number == instrument
        ]
        if not exact:
            raise LookupError(instrument)
        if len(exact) != 1 or len(collection.rows) != 1:
            raise SourceSchemaError(
                "ClerkTrack exact-instrument search was not unique",
                url=RESULTS_URL,
                details={
                    "instrument_number": instrument,
                    "result_count": len(collection.rows),
                    "exact_count": len(exact),
                },
            )
        listing = exact[0]
        response = self._request(
            "GET",
            DETAIL_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Referer": RESULTS_URL,
            },
            params={"param": listing.selector},
        )
        detail = parse_detail_page(
            str(response.text),
            source_url=str(response.url),
        )
        expected = {
            "instrument_number": listing.instrument_number,
            "book": listing.book,
            "page": listing.page,
            "recording_date": listing.recording_date,
            "document_type": listing.document_type,
        }
        observed = {
            "instrument_number": detail.instrument_number,
            "book": detail.book,
            "page": detail.page,
            "recording_date": detail.recording_date,
            "document_type": detail.document_type,
        }
        if observed != expected:
            raise SourceSchemaError(
                "ClerkTrack detail identity did not match its exact listing",
                url=str(response.url),
                details={"expected": expected, "observed": observed},
            )
        return listing, detail, collection.search_form


def _cross_source_join_keys(row: IndexRow) -> dict[str, Any]:
    return {
        "instrument_number": row.instrument_number,
        "book": row.book,
        "page": row.page,
        "book_page": (
            f"{row.book}/{row.page}"
            if row.book and row.page
            else None
        ),
        "target_assessor_source_id": ASSESSOR_LAYER_SOURCE_ID,
        "relationship": "independent_clerk_record_join_key",
    }


def normalize_index_row(
    row: IndexRow,
    *,
    search_form: SearchForm,
    results_schema_fingerprint: str,
) -> dict[str, Any]:
    """Normalize one source-published recorded-instrument index row."""

    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "recorded_instrument",
            row.instrument_number,
        ),
        "same_record_key": (
            f"US-NM-SANTA-FE:RECORDED-INSTRUMENT:"
            f"{row.instrument_number}"
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_kind": "recorded_instrument_index",
        "record_scope": "county_clerk_recording_index",
        "source_url": SEARCH_URL,
        "official_access_url": OFFICIAL_ACCESS_URL,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "native_instrument_id": row.instrument_number,
        "instrument_number": row.instrument_number,
        "book": row.book,
        "page": row.page,
        "recording_date": row.recording_date,
        "recording_date_raw": row.recording_date_raw,
        "document_type": row.document_type,
        "indexed_party_displays": {
            "grantors_raw": row.grantors_display_raw,
            "grantees_raw": row.grantees_display_raw,
            "parsing_note": (
                "The result grid concatenates source-formatted names; "
                "individual parties are exposed by the detail operation."
            ),
        },
        "legal_description_raw": row.legal_description_raw,
        "legal_information_raw": row.legal_information_raw,
        "cross_source_join_keys": _cross_source_join_keys(row),
        "evidence_role": (
            "independent_county_clerk_recorded_instrument_index"
        ),
        "independent_of_assessor_observation": True,
        "detail_retrieval": {
            "operation": "detail",
            "instrument_number": row.instrument_number,
            "selector_policy": (
                "reacquire_by_exact_instrument_in_fresh_session"
            ),
            "opaque_selector_persisted": False,
        },
        "source_index_through_date": search_form.index_through_date,
        "source_index_through_date_raw": (
            search_form.index_through_date_raw
        ),
        "search_form_schema_fingerprint": (
            search_form.schema_fingerprint
        ),
        "document_types_fingerprint": (
            search_form.document_types_fingerprint
        ),
        "results_schema_fingerprint": results_schema_fingerprint,
        "raw_fields": {
            "instrument_number": row.instrument_number,
            "book": row.book,
            "page": row.page,
            "recording_date": row.recording_date_raw,
            "document_type": row.document_type,
            "grantors": row.grantors_display_raw,
            "grantees": row.grantees_display_raw,
            "legal_description": row.legal_description_raw,
            "legal_information": row.legal_information_raw,
        },
    }


def normalize_detail(
    listing: IndexRow,
    detail: DetailFields,
    *,
    search_form: SearchForm,
) -> dict[str, Any]:
    """Normalize one verified fresh-session detail view."""

    parties = [
        {
            "raw_name": name,
            "role": role,
            "assertion_type": "clerk_recorded_instrument_index",
        }
        for role, names in (
            ("grantor", detail.grantors),
            ("grantee", detail.grantees),
        )
        for name in names
    ]
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "recorded_instrument",
            detail.instrument_number,
        ),
        "same_record_key": (
            f"US-NM-SANTA-FE:RECORDED-INSTRUMENT:"
            f"{detail.instrument_number}"
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_kind": "recorded_instrument_detail",
        "record_scope": "county_clerk_recording_index_detail",
        "source_url": DETAIL_URL,
        "official_access_url": OFFICIAL_ACCESS_URL,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "native_instrument_id": detail.instrument_number,
        "instrument_number": detail.instrument_number,
        "book": detail.book,
        "page": detail.page,
        "recording_date": detail.recording_date,
        "recording_date_raw": detail.recorded_date_raw,
        "recording_datetime_local": detail.recording_datetime_local,
        "recording_datetime_timezone": (
            "not published by the source detail view"
        ),
        "document_type": detail.document_type,
        "submitter": detail.submitter,
        "address": detail.address,
        "location": detail.location,
        "parties": parties,
        "legal_information": list(detail.legal_information),
        "additional_descriptions": list(detail.descriptions),
        "index_listing_displays": {
            "grantors_raw": listing.grantors_display_raw,
            "grantees_raw": listing.grantees_display_raw,
            "legal_description_raw": listing.legal_description_raw,
            "legal_information_raw": listing.legal_information_raw,
        },
        "cross_source_join_keys": _cross_source_join_keys(listing),
        "evidence_role": "same_clerk_instrument_detail",
        "independent_of_assessor_observation": True,
        "independent_corroboration_of_index": False,
        "retrieval_verification": {
            "fresh_session_exact_instrument_search": True,
            "visible_identity_fields_matched": True,
            "verified_fields": [
                "instrument_number",
                "book",
                "page",
                "recording_date",
                "document_type",
            ],
            "opaque_selector_persisted": False,
        },
        "source_index_through_date": search_form.index_through_date,
        "source_index_through_date_raw": (
            search_form.index_through_date_raw
        ),
        "search_form_schema_fingerprint": (
            search_form.schema_fingerprint
        ),
        "document_types_fingerprint": (
            search_form.document_types_fingerprint
        ),
        "detail_schema_fingerprint": detail.schema_fingerprint,
    }


def _criteria_from_args(args: argparse.Namespace) -> SearchCriteria:
    return SearchCriteria(
        name=getattr(args, "name", None),
        party_role=getattr(args, "party_role", "both"),
        from_date=getattr(args, "from_date", None),
        to_date=getattr(args, "to_date", None),
        instrument=getattr(args, "instrument", None),
        book=getattr(args, "book", None),
        page=getattr(args, "page", None),
        document_types=tuple(
            getattr(args, "document_type", None) or ()
        ),
        legal=getattr(args, "legal", None),
        subdivision=getattr(args, "subdivision", None),
        lot=getattr(args, "lot", None),
        block=getattr(args, "block", None),
        tract=getattr(args, "tract", None),
        section=getattr(args, "section", None),
        township=getattr(args, "township", None),
        range_value=getattr(args, "range_value", None),
        unit=getattr(args, "unit", None),
        additional_info=getattr(args, "additional_info", None),
    )


def _build_query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "source_published_grain": (
                    "one County Clerk recorded-instrument index row"
                ),
                "document_image_included": False,
            },
        ),
    )


def _client(args: argparse.Namespace) -> ClerkTrackClient:
    return ClerkTrackClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(
            f"Warning: search log was not updated: {error}",
            file=sys.stderr,
        )


def execute_search(
    args: argparse.Namespace,
    *,
    client: ClerkTrackClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute a recorded-instrument index search."""

    criteria = _criteria_from_args(args)
    query = _build_query(
        "search",
        criteria.to_dict(),
        limit=args.limit,
        cursor=args.cursor,
    )
    active_client = client or _client(args)
    owns_client = client is None
    try:
        collection = active_client.search(
            criteria,
            limit=args.limit,
            cursor=args.cursor,
        )
        records = [
            normalize_index_row(
                row,
                search_form=collection.search_form,
                results_schema_fingerprint=(
                    collection.results_schema_fingerprint or ""
                ),
            )
            for row in collection.rows
        ]
        warnings = SOURCE_WARNINGS
        if collection.next_cursor:
            warnings = (
                *warnings,
                (
                    "The caller-selected result window ended before the "
                    "source result set; use next_cursor to continue."
                ),
            )
            result = PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=collection.next_cursor,
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=warnings,
            )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="selection_or_cursor_invalid",
                    message=str(error),
                    category="query",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
            active_client.close()
    _best_effort_log(query, result)
    return result


def execute_detail(
    args: argparse.Namespace,
    *,
    client: ClerkTrackClient | Any | None = None,
) -> PublicRecordsResult:
    """Reacquire and retrieve one recorded-instrument detail."""

    instrument = _clean(args.instrument)
    query = _build_query(
        args.command,
        {
            "instrument_number": instrument,
            "fresh_session_exact_reacquisition": True,
            "opaque_selector_persisted": False,
        },
    )
    active_client = client or _client(args)
    owns_client = client is None
    try:
        listing, detail, form = active_client.detail(instrument)
        if args.command == "probe":
            observed = {
                "instrument_number": detail.instrument_number,
                "book": detail.book,
                "page": detail.page,
                "recording_date": detail.recording_date,
                "document_type": detail.document_type,
            }
            expected = {
                "instrument_number": PROBE_INSTRUMENT,
                "book": PROBE_BOOK,
                "page": PROBE_PAGE,
                "recording_date": PROBE_RECORDING_DATE,
                "document_type": PROBE_DOCUMENT_TYPE,
            }
            if observed != expected:
                raise SourceSchemaError(
                    "Santa Fe ClerkTrack probe sentinel changed",
                    url=DETAIL_URL,
                    details={"expected": expected, "observed": observed},
                )
        record = normalize_detail(
            listing,
            detail,
            search_form=form,
        )
        result = PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    except LookupError:
        if args.command == "probe":
            result = failure_result(
                query,
                SourceSchemaError(
                    "Santa Fe ClerkTrack probe sentinel is missing",
                    url=SEARCH_URL,
                    details={
                        "instrument_number": PROBE_INSTRUMENT,
                    },
                ),
                warnings=SOURCE_WARNINGS,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                [],
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
                    code="detail_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
            active_client.close()
    _best_effort_log(query, result)
    return result


def route_map() -> dict[str, Any]:
    return {
        "jurisdiction": {
            "county": COUNTY_NAME,
            "state": STATE_CODE,
            "county_geoid": COUNTY_GEOID,
        },
        "observed_at": OBSERVED_AT,
        "primary_adapter_source_id": SOURCE_ID,
        "routes": [dict(route) for route in SOURCE_ROUTES],
        "relationship_rule": (
            "Index and detail are two representations of one Clerk "
            "instrument. Purchased or requested images are the underlying "
            "Clerk artifact. Assessor account fields are separately produced "
            "join hints, not added corroboration of the Clerk instrument."
        ),
    }


def routes_result() -> PublicRecordsResult:
    """Return the verified route lineage through the canonical result contract."""

    query = _build_query(
        "discovery",
        {"selector": "routes"},
    )
    return PublicRecordsResult.success(
        query,
        [route_map()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: ClerkTrackClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute a canonical search, exact detail, probe, or route discovery."""

    if args.command == "search":
        return execute_search(args, client=client)
    if args.command in {"detail", "probe"}:
        return execute_detail(args, client=client)
    if args.command == "routes":
        if client is not None:
            raise ValueError("route discovery does not use a source client")
        return routes_result()
    raise ValueError(f"unsupported Santa Fe ClerkTrack command: {args.command}")


def _emit_routes(args: argparse.Namespace) -> None:
    data = route_map()
    if write_output(
        data,
        args,
        summary="Santa Fe County Clerk recorded-document routes",
        result_count=len(SOURCE_ROUTES),
    ):
        return
    print("Santa Fe County Clerk recorded-document routes")
    for route in SOURCE_ROUTES:
        print(
            f"  {route['route_id']} | {route['access']} | "
            f"{route['relationship_to_primary']}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=(
            f"Santa Fe County ClerkTrack {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    print(
        f"Santa Fe County ClerkTrack {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record['instrument_number']} | "
            f"{record['recording_date']} | "
            f"{record['document_type']}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
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
        help="Minimum delay between source requests",
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="Attempts for transient HTTP failures",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search the Santa Fe County Clerk ClerkTrack "
            "recorded-document index"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search recorded-instrument index fields",
    )
    search.add_argument(
        "--name",
        help="Indexed party name; ClerkTrack supports * wildcards",
    )
    search.add_argument(
        "--party-role",
        choices=("both", "grantor", "grantee"),
        default="both",
    )
    search.add_argument("--from-date", help="Recording date YYYY-MM-DD")
    search.add_argument("--to-date", help="Recording date YYYY-MM-DD")
    search.add_argument("--instrument", help="Instrument number")
    search.add_argument("--book")
    search.add_argument("--page")
    search.add_argument(
        "--document-type",
        action="append",
        help="Exact published document-type label or numeric value; repeatable",
    )
    search.add_argument("--legal", help="Legal description text")
    search.add_argument("--subdivision")
    search.add_argument("--lot")
    search.add_argument("--block")
    search.add_argument("--tract")
    search.add_argument("--section")
    search.add_argument("--township")
    search.add_argument("--range", dest="range_value")
    search.add_argument("--unit")
    search.add_argument(
        "--additional-info",
        help="ClerkTrack additional-information description",
    )
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-selected result window",
    )
    search.add_argument(
        "--cursor",
        help="Continuation cursor from a previous identical search",
    )
    _add_transport_args(search)
    add_output_args(search)

    detail = subparsers.add_parser(
        "detail",
        help="Fresh-session exact instrument lookup and verified detail",
    )
    detail.add_argument("instrument")
    _add_transport_args(detail)
    add_output_args(detail)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the public login, exact search, and detail sentinel",
    )
    probe.set_defaults(instrument=PROBE_INSTRUMENT)
    _add_transport_args(probe)
    add_output_args(probe)

    routes = subparsers.add_parser(
        "routes",
        help="Show verified Clerk and field-matched complementary routes",
    )
    add_output_args(routes)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "routes":
        _emit_routes(args)
        return 0
    try:
        if args.command == "search":
            result = execute_search(args)
        else:
            result = execute_detail(args)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
