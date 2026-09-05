#!/usr/bin/env python3
"""Query Connecticut Superior Court Civil/Family public case information.

Examples:
    uv run python tools/query_connecticut_civil_family.py search EPSTEIN \
        --match exact --output /tmp/ct-party.json
    uv run python tools/query_connecticut_civil_family.py case \
        FBT-CV-26-6159214-S --output /tmp/ct-case.json
    uv run python tools/query_connecticut_civil_family.py document 32503295 \
        --docket FBT-CV-26-6159214-S \
        --pdf-output /tmp/complaint.pdf --output /tmp/complaint.json
    uv run python tools/query_connecticut_civil_family.py routes --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

try:
    from curl_cffi import requests as curl_requests
    from curl_cffi.requests.exceptions import (
        RequestException as CurlRequestException,
    )
except ImportError:  # Covered by a classified runtime failure.
    curl_requests = None
    CurlRequestException = None

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
        SourceSchemaError,
        TransportError,
        failure_result,
        schema_fingerprint,
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
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceSchemaError,
        TransportError,
        failure_result,
        schema_fingerprint,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-ct-superior-court-civil-family-case-lookup"
COURT_ID = "ct-superior-court"
BASE_URL = "https://civilinquiry.jud.ct.gov/"
PARTY_SEARCH_URL = urljoin(BASE_URL, "PartySearch.aspx")
LOAD_DOCKET_URL = urljoin(BASE_URL, "LoadDocket.aspx")
CASE_DETAIL_URL = urljoin(BASE_URL, "CaseDetail/PublicCaseDetail.aspx")
CASE_HISTORY_URL = urljoin(BASE_URL, "CaseDetail/PublicCaseHistory.aspx")
NOTICES_URL = urljoin(BASE_URL, "CaseDetail/PublicNotices.aspx")
DOCUMENT_URL = urljoin(
    BASE_URL,
    "DocumentInquiry/DocumentInquiry.aspx",
)
DIRECTORY_URL = "https://www.jud.ct.gov/jud2.htm"
DISPLAY_GUIDE_URL = urljoin(
    BASE_URL,
    "Understanding%20Display%20of%20Case%20Information.pdf",
)
BULK_DESCRIPTION_URL = (
    "https://www.jud.ct.gov/publicdata/BulkDataCivilFamilyCases.pdf"
)
CLERK_DIRECTORY_URL = "https://www.jud.ct.gov/directory/directory/clerk.htm"
EXPECTED_HOST = "civilinquiry.jud.ct.gov"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
SOURCE_DISPLAY_SLICE_SIZE = 50
CURSOR_VERSION = 1
SENTINEL_LAST_NAME = "EPSTEIN"
SENTINEL_DOCKET = "FBT-CV-26-6159214-S"
SENTINEL_PARTY_NUMBER = "D-01"
SENTINEL_DOCUMENT_NUMBER = "32503295"
PROBE_EXPECTED_REQUESTS = 5

PARTY_RESULT_HEADERS = (
    "Party Name",
    "Case Name",
    "Docket No.",
    "Court Location",
    "Pty No.",
    "Self- Rep.",
)
PARTY_GRID_ID = "ctl00_ContentPlaceHolder1_gvPartyResults"
PARTY_RECORDS_ID = "ctl00_ContentPlaceHolder1_lblRecords"
PARTY_ERROR_ID = "ctl00_ContentPlaceHolder1_lblError"
CASE_PARTIES_GRID_SUFFIX = "CaseDetailParties1_gvParties"
CASE_DOCUMENTS_GRID_SUFFIX = "CaseDetailDocuments1_gvDocuments"
CASE_EVENTS_GRID_SUFFIX = "CaseDetailEdisonSchedule1_gvCourtDates"
HISTORY_GRID_ID = "ctl00_ContentPlaceHolder1_dgTransferHistory"
NOTICES_GRID_ID = "ctl00_ContentPlaceHolder1_gvNotices"

MATCH_VALUES = {
    "exact": "Is Equal To",
    "starts_with": "Starts With",
    "contains": "Contains",
    "soundex": "Soundex",
}
SORT_VALUES = {
    "party_name": "party_name",
    "court_location": "court_loc, party_name",
}
DOCKET_RE = re.compile(
    r"^(?P<location>[A-Z0-9]{3})(?P<category>[A-Z]{2})"
    r"(?P<year>\d{2})(?P<number>\d{7})(?P<suffix>[A-Z])$"
)
RECORD_RANGE_RE = re.compile(
    r"(?P<start>\d+)\s*-\s*(?P<end>\d+)\s+of\s+(?P<total>\d+)",
    re.IGNORECASE,
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Connecticut Superior Court Civil/Family Case Look-up",
    source_role="state_trial_court_case_lookup",
    base_url=BASE_URL,
    dataset_id="ct-superior-civil-family-case-lookup",
    metadata={
        "authority": "Connecticut Judicial Branch",
        "state_code": "CT",
        "authentication": "none",
        "platform_family": "aspnet_webforms",
        "publisher_document_identifier": "DocumentNo",
        "party_search_result_grain": "party occurrence",
        "bulk_complement_url": BULK_DESCRIPTION_URL,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="US-CT",
    name="Connecticut",
    state_code="CT",
    metadata={
        "court": "Connecticut Superior Court",
        "case_categories": ["Civil", "Family"],
    },
)


class ConnecticutSelectionError(ValueError):
    """A caller selector is invalid for the verified source contract."""

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


class ConnecticutSourceChanged(SourceSchemaError):
    """The official portal no longer matches the verified contract."""

    code = "connecticut_source_changed"

    def __init__(
        self,
        code: str,
        message: str,
        *,
        url: str = BASE_URL,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, url=url, details=details)
        self.code = code


class ConnecticutTransportUnavailable(TransportError):
    """The portal-specific libcurl transport is unavailable."""

    code = "connecticut_transport_unavailable"


class ConnecticutRequestBudgetExceeded(TransportError):
    """A bounded source probe exhausted its native request allowance."""

    code = "connecticut_request_budget_exceeded"


@dataclass(frozen=True)
class PartySearchForm:
    action_url: str
    payload: Mapping[str, str]
    locations: frozenset[str]
    categories: frozenset[str]
    case_types: frozenset[str]
    match_values: frozenset[str]
    sort_values: frozenset[str]
    schema_fingerprint: str


@dataclass(frozen=True)
class PartyResultPage:
    rows: tuple[Mapping[str, Any], ...]
    displayed_start: int | None
    displayed_end: int | None
    source_reported_count: int
    has_pager: bool
    schema_fingerprint: str | None
    authoritative_no_results: bool = False

    @property
    def source_slice_unresolved(self) -> bool:
        return (
            not self.authoritative_no_results
            and len(self.rows) == SOURCE_DISPLAY_SLICE_SIZE
            and self.displayed_start == 1
            and self.displayed_end == SOURCE_DISPLAY_SLICE_SIZE
            and self.source_reported_count == SOURCE_DISPLAY_SLICE_SIZE
            and not self.has_pager
        )


@dataclass(frozen=True)
class CaseBundle:
    record: Mapping[str, Any]
    child_errors: tuple[PublicRecordsHTTPError, ...] = ()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _optional(value: Any) -> str | None:
    cleaned = _clean(value)
    return cleaned or None


def _text(item: Tag | None) -> str:
    return _clean(item.get_text(" ", strip=True) if item is not None else "")


def _date_iso(value: str | None) -> str | None:
    if not value:
        return None
    for pattern in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _strip_label(value: str | None, label: str) -> str | None:
    cleaned = _optional(value)
    if cleaned is None:
        return None
    prefix = f"{label}:"
    if cleaned.casefold().startswith(prefix.casefold()):
        return _optional(cleaned[len(prefix) :])
    return cleaned


def normalize_docket(value: str) -> str:
    """Return the durable, hyphenated Connecticut docket identity."""

    compact = re.sub(r"[^A-Z0-9]", "", _clean(value).upper())
    match = DOCKET_RE.fullmatch(compact)
    if match is None:
        raise ConnecticutSelectionError(
            "invalid_docket",
            "docket must contain a three-character location, two-character "
            "category, two-digit year, seven-digit number, and suffix",
            details={"docket": _clean(value)},
        )
    return (
        f"{match.group('location')}-{match.group('category')}-"
        f"{match.group('year')}-{match.group('number')}-"
        f"{match.group('suffix')}"
    )


def compact_docket(value: str) -> str:
    return normalize_docket(value).replace("-", "")


def _court_id(docket: str) -> str:
    location = normalize_docket(docket).split("-", 1)[0].casefold()
    return f"{COURT_ID}-{location}"


def _case_ref(docket: str) -> str:
    normalized = normalize_docket(docket)
    return canonical_court_ref(
        SOURCE_ID,
        _court_id(normalized),
        normalized,
        "case",
    )


def _child_ref(docket: str, kind: str, publisher_id: str) -> str:
    normalized = normalize_docket(docket)
    return canonical_court_ref(
        SOURCE_ID,
        _court_id(normalized),
        normalized,
        kind,
        publisher_id,
    )


def _derived_child_ref(docket: str, kind: str, fields: Sequence[Any]) -> str:
    identity = sha256_fingerprint([_clean(value) for value in fields])
    return _child_ref(docket, kind, f"derived-{identity}")


def _suffix_item(soup: BeautifulSoup | Tag, suffix: str) -> Tag | None:
    return soup.select_one(f'[id$="{suffix}"]')


def _validate_official_url(url: str, *, label: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme.casefold() != "https"
        or (parsed.hostname or "").casefold() != EXPECTED_HOST
    ):
        raise ConnecticutSourceChanged(
            "unexpected_source_route",
            f"{label} left the verified Connecticut Judicial Branch host",
            url=url,
            details={
                "scheme": parsed.scheme,
                "host": parsed.hostname,
                "path": parsed.path,
            },
        )


def _content_type(response: Any) -> str:
    headers = getattr(response, "headers", {})
    value = headers.get("Content-Type") or headers.get("content-type") or ""
    return str(value).split(";", 1)[0].strip().casefold()


def _require_html(response: Any, *, label: str) -> BeautifulSoup:
    url = str(getattr(response, "url", ""))
    _validate_official_url(url, label=label)
    media_type = _content_type(response)
    if media_type not in {"text/html", "application/xhtml+xml"}:
        raise ConnecticutSourceChanged(
            "response_media_type_changed",
            f"{label} did not return HTML",
            url=url,
            details={"content_type": media_type},
        )
    return BeautifulSoup(str(response.text), "html.parser")


def _form_values(form: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for control in form.select("input[name]"):
        name = str(control["name"])
        input_type = str(control.get("type", "text")).casefold()
        if input_type in {"submit", "button", "image", "file"}:
            continue
        if input_type in {"checkbox", "radio"} and not control.has_attr("checked"):
            continue
        values[name] = str(control.get("value", ""))
    for control in form.select("select[name]"):
        option = control.select_one("option[selected]") or control.select_one(
            "option:not([disabled])"
        )
        if option is not None:
            values[str(control["name"])] = str(option.get("value", ""))
    return values


def _select_values(form: Tag, name: str) -> frozenset[str]:
    select = form.select_one(f'select[name="{name}"]')
    if select is None:
        return frozenset()
    return frozenset(
        str(option.get("value", ""))
        for option in select.select("option")
        if not option.has_attr("disabled")
    )


def _input_values(form: Tag, name: str) -> frozenset[str]:
    return frozenset(
        str(item.get("value", ""))
        for item in form.select(f'input[name="{name}"]')
    )


def parse_party_search_form(html: str, *, source_url: str) -> PartySearchForm:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#aspnetForm")
    if form is None:
        raise ConnecticutSourceChanged(
            "party_search_form_missing",
            "Connecticut party search no longer exposes the WebForms form",
            url=source_url,
        )
    required_names = {
        "ctl00$ContentPlaceHolder1$txtLastName",
        "ctl00$ContentPlaceHolder1$txtFirstName",
        "ctl00$ContentPlaceHolder1$ddlLocation",
        "ctl00$ContentPlaceHolder1$ddlCaseCategory",
        "ctl00$ContentPlaceHolder1$ddlCaseType",
        "ctl00$ContentPlaceHolder1$ddlSortOrder",
        "ctl00$ContentPlaceHolder1$rblLastNameSearchType",
        "ctl00$ContentPlaceHolder1$btnSubmit",
        "__VIEWSTATE",
        "__EVENTVALIDATION",
    }
    observed_names = {
        str(control["name"]) for control in form.select("[name]")
    }
    missing = sorted(required_names - observed_names)
    if missing:
        raise ConnecticutSourceChanged(
            "party_search_controls_changed",
            "Connecticut party search controls changed",
            url=source_url,
            details={"missing_controls": missing},
        )
    action_url = urljoin(source_url, str(form.get("action", "")))
    _validate_official_url(action_url, label="party search form action")
    locations = _select_values(
        form,
        "ctl00$ContentPlaceHolder1$ddlLocation",
    )
    categories = _select_values(
        form,
        "ctl00$ContentPlaceHolder1$ddlCaseCategory",
    )
    case_types = _select_values(
        form,
        "ctl00$ContentPlaceHolder1$ddlCaseType",
    )
    sort_values = _select_values(
        form,
        "ctl00$ContentPlaceHolder1$ddlSortOrder",
    )
    match_values = _input_values(
        form,
        "ctl00$ContentPlaceHolder1$rblLastNameSearchType",
    )
    required_options = {
        "locations": ("ALL", locations),
        "categories": ("ALL", categories),
        "case_types": ("All", case_types),
        "sort": ("party_name", sort_values),
        "match": ("Is Equal To", match_values),
    }
    missing_options = [
        f"{label}:{value}"
        for label, (value, options) in required_options.items()
        if value not in options
    ]
    if missing_options:
        raise ConnecticutSourceChanged(
            "party_search_options_changed",
            "Connecticut party search default options changed",
            url=source_url,
            details={"missing_options": missing_options},
        )
    schema = {
        "control_names": sorted(observed_names),
        "location_values": sorted(locations),
        "category_values": sorted(categories),
        "case_type_values": sorted(case_types),
        "sort_values": sorted(sort_values),
        "match_values": sorted(match_values),
    }
    return PartySearchForm(
        action_url=action_url,
        payload=_form_values(form),
        locations=locations,
        categories=categories,
        case_types=case_types,
        match_values=match_values,
        sort_values=sort_values,
        schema_fingerprint=sha256_fingerprint(schema),
    )


def build_party_search_payload(
    form: PartySearchForm,
    *,
    last_name: str,
    first_name: str | None = None,
    match: str = "exact",
    location: str = "ALL",
    category: str = "ALL",
    case_type: str = "All",
    sort: str = "party_name",
) -> dict[str, str]:
    last = _clean(last_name)
    if not last:
        raise ConnecticutSelectionError(
            "last_name_required",
            "party search requires a last name",
        )
    try:
        match_value = MATCH_VALUES[match]
    except KeyError as exc:
        raise ConnecticutSelectionError(
            "invalid_match_type",
            f"unknown party-name match type: {match}",
        ) from exc
    try:
        sort_value = SORT_VALUES[sort]
    except KeyError as exc:
        raise ConnecticutSelectionError(
            "invalid_sort",
            f"unknown party search sort: {sort}",
        ) from exc
    selectors = (
        ("location", location, form.locations),
        ("category", category, form.categories),
        ("case_type", case_type, form.case_types),
        ("match", match_value, form.match_values),
        ("sort", sort_value, form.sort_values),
    )
    for label, value, options in selectors:
        if value not in options:
            raise ConnecticutSelectionError(
                f"invalid_{label}",
                f"{label} is not present in the live Connecticut form",
                details={"value": value, "available": sorted(options)},
            )
    payload = dict(form.payload)
    payload.update(
        {
            "ctl00$ContentPlaceHolder1$txtLastName": last,
            "ctl00$ContentPlaceHolder1$txtFirstName": _clean(first_name),
            "ctl00$ContentPlaceHolder1$ddlLocation": location,
            "ctl00$ContentPlaceHolder1$ddlCaseCategory": category,
            "ctl00$ContentPlaceHolder1$ddlCaseType": case_type,
            "ctl00$ContentPlaceHolder1$ddlSortOrder": sort_value,
            "ctl00$ContentPlaceHolder1$rblLastNameSearchType": match_value,
            "ctl00$ContentPlaceHolder1$btnSubmit": "Search",
        }
    )
    return payload


def _table_headers(table: Tag) -> tuple[str, ...]:
    return tuple(_text(cell) for cell in table.select("th"))


def _direct_cells(row: Tag) -> list[Tag]:
    return list(row.find_all("td", recursive=False))


def _schema_for_table(table: Tag) -> dict[str, Any]:
    rows = []
    for row in table.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if cells:
            rows.append(
                {
                    "cell_count": len(cells),
                    "link_paths": sorted(
                        {
                            urlsplit(str(link.get("href", ""))).path
                            for link in row.select("a[href]")
                            if not str(link.get("href", "")).startswith(
                                "javascript:"
                            )
                        }
                    ),
                }
            )
    return {
        "headers": list(_table_headers(table)),
        "row_shapes": sorted(
            {
                (row["cell_count"], tuple(row["link_paths"]))
                for row in rows
            }
        ),
    }


def parse_party_results(html: str, *, source_url: str) -> PartyResultPage:
    """Parse a published party-occurrence slice or authoritative empty."""

    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.title)
    if title != "Party Name Search Results":
        raise ConnecticutSourceChanged(
            "party_results_title_changed",
            "Connecticut party search returned an unexpected page",
            url=source_url,
            details={"title": title},
        )
    error = soup.select_one(f"#{PARTY_ERROR_ID}")
    error_text = _text(error)
    grid = soup.select_one(f"#{PARTY_GRID_ID}")
    if grid is None:
        if error_text and "not found" in error_text.casefold():
            return PartyResultPage(
                rows=(),
                displayed_start=None,
                displayed_end=None,
                source_reported_count=0,
                has_pager=False,
                schema_fingerprint=None,
                authoritative_no_results=True,
            )
        raise ConnecticutSourceChanged(
            "party_results_grid_missing",
            "Connecticut party search results grid is missing",
            url=source_url,
            details={"error_text": error_text},
        )
    headers = _table_headers(grid)
    if headers != PARTY_RESULT_HEADERS:
        raise ConnecticutSourceChanged(
            "party_results_columns_changed",
            "Connecticut party search result columns changed",
            url=source_url,
            details={
                "expected": list(PARTY_RESULT_HEADERS),
                "observed": list(headers),
            },
        )
    rows: list[Mapping[str, Any]] = []
    for row in grid.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if not cells:
            continue
        if len(cells) != len(PARTY_RESULT_HEADERS):
            raise ConnecticutSourceChanged(
                "party_result_row_shape_changed",
                "Connecticut party result row has an unexpected cell count",
                url=source_url,
                details={"cell_count": len(cells)},
            )
        docket_link = cells[2].select_one("a[href]")
        if docket_link is None:
            raise ConnecticutSourceChanged(
                "party_result_docket_link_missing",
                "Connecticut party result has no docket link",
                url=source_url,
            )
        try:
            docket = normalize_docket(_text(docket_link))
        except ConnecticutSelectionError as exc:
            raise ConnecticutSourceChanged(
                "party_result_docket_changed",
                "Connecticut party result contains an unexpected docket",
                url=source_url,
                details={"docket": _text(docket_link)},
            ) from exc
        case_url = urljoin(source_url, str(docket_link.get("href", "")))
        _validate_official_url(case_url, label="party result docket link")
        party_number = _text(cells[4])
        if not party_number:
            raise ConnecticutSourceChanged(
                "party_result_number_missing",
                "Connecticut party result has no publisher party number",
                url=source_url,
                details={"docket": docket},
            )
        rows.append(
            {
                "party_name": _text(cells[0]),
                "case_name": _text(cells[1]),
                "docket": docket,
                "court_location": _text(cells[3]),
                "publisher_party_number": party_number,
                "self_represented_raw": _optional(_text(cells[5])),
                "case_url": case_url,
            }
        )
    records_label = soup.select_one(f"#{PARTY_RECORDS_ID}")
    records_text = _text(records_label)
    range_match = RECORD_RANGE_RE.search(records_text)
    if range_match is None:
        raise ConnecticutSourceChanged(
            "party_result_count_changed",
            "Connecticut party result range is missing or changed",
            url=source_url,
            details={"records_label": records_text},
        )
    start = int(range_match.group("start"))
    end = int(range_match.group("end"))
    reported = int(range_match.group("total"))
    if start != 1 or end < start or len(rows) != end - start + 1:
        raise ConnecticutSourceChanged(
            "party_result_count_mismatch",
            "Connecticut party result rows do not match the displayed range",
            url=source_url,
            details={
                "displayed_start": start,
                "displayed_end": end,
                "source_reported_count": reported,
                "parsed_rows": len(rows),
            },
        )
    pager = grid.select_one(
        "tr[class*=Pager], td[class*=Pager], "
        "a[href*='Page$'], a[href*='Page%24']"
    )
    return PartyResultPage(
        rows=tuple(rows),
        displayed_start=start,
        displayed_end=end,
        source_reported_count=reported,
        has_pager=pager is not None,
        schema_fingerprint=schema_fingerprint(
            {
                "table": _schema_for_table(grid),
                "range_label_pattern": "start-end of reported",
            }
        ),
    )


def _publisher_id_from_url(url: str, key: str) -> str | None:
    values = parse_qs(urlsplit(url).query).get(key)
    if not values:
        return None
    return _optional(values[0])


def _parse_appearance(row: Tag) -> list[dict[str, Any]]:
    appearances: list[dict[str, Any]] = []
    for info in row.select('[id$="lblAppearanceInfo1"]'):
        container = info.find_parent("tr") or info.parent
        label = _text(container.select_one('[id$="lblAppearanceTitle"]'))
        detail = _text(info)
        date_text = _strip_label(
            _text(container.select_one('[id$="lblAppearanceInfo2"]')),
            "File Date",
        )
        juris_number = None
        display_name = detail
        address = None
        attorney_match = re.match(
            r"^(?P<name>.*?)\s+\((?P<juris>\d+)\)\s*(?P<address>.*)$",
            detail,
        )
        if attorney_match:
            display_name = _clean(attorney_match.group("name"))
            juris_number = attorney_match.group("juris")
            address = _optional(attorney_match.group("address"))
        appearances.append(
            {
                "appearance_type": label.rstrip(":") or None,
                "display_name_or_address": detail or None,
                "display_name": display_name or None,
                "publisher_juris_number": juris_number,
                "address_raw": address,
                "file_date_raw": date_text,
                "file_date": _date_iso(date_text),
            }
        )
    return appearances


def _parse_parties(soup: BeautifulSoup, *, docket: str) -> list[dict[str, Any]]:
    grid = _suffix_item(soup, CASE_PARTIES_GRID_SUFFIX)
    if grid is None:
        raise ConnecticutSourceChanged(
            "case_parties_grid_missing",
            "Connecticut case detail has no party grid",
            url=CASE_DETAIL_URL,
            details={"docket": docket},
        )
    expected_headers = ("Party", "Party Details", "No Fee Party", "Category")
    headers = _table_headers(grid)
    if headers != expected_headers:
        raise ConnecticutSourceChanged(
            "case_parties_columns_changed",
            "Connecticut case party columns changed",
            url=CASE_DETAIL_URL,
            details={"expected": expected_headers, "observed": headers},
        )
    parties: list[dict[str, Any]] = []
    for row in grid.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if not cells:
            continue
        if len(cells) != 4:
            raise ConnecticutSourceChanged(
                "case_party_row_shape_changed",
                "Connecticut case party row has an unexpected cell count",
                url=CASE_DETAIL_URL,
                details={"docket": docket, "cell_count": len(cells)},
            )
        number = _text(row.select_one('[id$="lblPlaintDefPartyNo"]'))
        name = _text(row.select_one('[id$="lblPtyPartyName"]'))
        if not number or not name:
            raise ConnecticutSourceChanged(
                "case_party_identity_missing",
                "Connecticut case party row lacks its publisher identity",
                url=CASE_DETAIL_URL,
                details={"docket": docket},
            )
        parties.append(
            {
                "canonical_ref": _child_ref(docket, "party", number),
                "publisher_party_number": number,
                "name": name,
                "party_details": _optional(_text(cells[1])),
                "no_fee_party_raw": _optional(_text(cells[2])),
                "category": _optional(_text(cells[3])),
                "appearance_status": (
                    _optional(_text(row.select_one('[id$="lblNonAppearing"]')))
                ),
                "appearances": _parse_appearance(row),
            }
        )
    if not parties:
        raise ConnecticutSourceChanged(
            "case_parties_empty",
            "Connecticut case party grid contains no parties",
            url=CASE_DETAIL_URL,
            details={"docket": docket},
        )
    return parties


def _parse_docket_entries(
    soup: BeautifulSoup,
    *,
    docket: str,
    source_url: str,
) -> list[dict[str, Any]]:
    grid = _suffix_item(soup, CASE_DOCUMENTS_GRID_SUFFIX)
    if grid is None:
        raise ConnecticutSourceChanged(
            "case_documents_grid_missing",
            "Connecticut case detail has no motions/pleadings/documents grid",
            url=source_url,
            details={"docket": docket},
        )
    expected_headers = (
        "Entry No",
        "File Date",
        "Filed By",
        "Description",
        "Arguable",
    )
    headers = _table_headers(grid)
    if headers != expected_headers:
        raise ConnecticutSourceChanged(
            "case_documents_columns_changed",
            "Connecticut motions/pleadings/documents columns changed",
            url=source_url,
            details={"expected": expected_headers, "observed": headers},
        )
    entries: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for row in grid.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if not cells:
            continue
        if len(cells) != 5:
            raise ConnecticutSourceChanged(
                "case_document_row_shape_changed",
                "Connecticut docket-entry row has an unexpected cell count",
                url=source_url,
                details={"docket": docket, "cell_count": len(cells)},
            )
        entry_number = _optional(_text(cells[0]))
        file_date_raw = _optional(_text(cells[1]))
        filed_by = _optional(
            _text(row.select_one('[id$="lblFiledBy"]')) or _text(cells[2])
        )
        link = row.select_one('[id$="hlnkDocument"][href]')
        description_item = link or row.select_one('[id$="lblDocumentText"]')
        description = _optional(_text(description_item))
        if description is None:
            description = _optional(_text(cells[3]))
        document_url = (
            urljoin(source_url, str(link.get("href", "")))
            if link is not None
            else None
        )
        document_number = (
            _publisher_id_from_url(document_url, "DocumentNo")
            if document_url
            else None
        )
        if document_url:
            _validate_official_url(
                document_url,
                label="case filing document link",
            )
        if document_url and not document_number:
            raise ConnecticutSourceChanged(
                "document_identifier_missing",
                "Connecticut filing link has no DocumentNo",
                url=source_url,
                details={"docket": docket, "document_url": document_url},
            )
        if document_number:
            canonical_ref = _child_ref(
                docket,
                "document",
                document_number,
            )
            identity_basis = "publisher_document_number"
        elif entry_number:
            canonical_ref = _child_ref(
                docket,
                "docket_entry",
                entry_number,
            )
            identity_basis = "publisher_entry_number"
        else:
            canonical_ref = _derived_child_ref(
                docket,
                "docket_entry",
                (
                    file_date_raw,
                    filed_by,
                    description,
                    _text(cells[4]),
                ),
            )
            identity_basis = "published_field_tuple"
        if canonical_ref in seen_refs:
            raise ConnecticutSourceChanged(
                "duplicate_docket_entry_identity",
                "Connecticut case detail repeated a child identity",
                url=source_url,
                details={
                    "docket": docket,
                    "canonical_ref": canonical_ref,
                },
            )
        seen_refs.add(canonical_ref)
        entries.append(
            {
                "canonical_ref": canonical_ref,
                "identity_basis": identity_basis,
                "publisher_entry_number": entry_number,
                "publisher_document_number": document_number,
                "file_date_raw": file_date_raw,
                "file_date": _date_iso(file_date_raw),
                "filed_by": filed_by,
                "description": description,
                "additional_description": _optional(
                    _text(row.select_one('[id$="lblAddDesc"]'))
                ),
                "result": _strip_label(
                    _text(row.select_one('[id$="lblResult"]')),
                    "RESULT",
                ),
                "notes": _optional(
                    _text(row.select_one('[id$="lblNotes"]'))
                ),
                "scram": _optional(
                    _text(row.select_one('[id$="lblScram"]'))
                ),
                "lsr": _optional(_text(row.select_one('[id$="lblLSR"]'))),
                "arguable_raw": _optional(_text(cells[4])),
                "document_available": document_number is not None,
                "document_url": document_url,
            }
        )
    return entries


def _parse_scheduled_events(
    soup: BeautifulSoup,
    *,
    docket: str,
    source_url: str,
) -> tuple[list[dict[str, Any]], str | None]:
    grid = _suffix_item(soup, CASE_EVENTS_GRID_SUFFIX)
    if grid is None:
        raise ConnecticutSourceChanged(
            "case_events_grid_missing",
            "Connecticut case detail has no scheduled-events grid",
            url=source_url,
            details={"docket": docket},
        )
    expected_headers = ("#", "Date", "Time", "Event Description", "Status")
    headers = _table_headers(grid)
    if headers != expected_headers:
        raise ConnecticutSourceChanged(
            "case_events_columns_changed",
            "Connecticut scheduled-event columns changed",
            url=source_url,
            details={"expected": expected_headers, "observed": headers},
        )
    events: list[dict[str, Any]] = []
    for row in grid.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if not cells:
            continue
        row_text = " ".join(_text(cell) for cell in cells)
        if "no events scheduled" in row_text.casefold():
            continue
        if len(cells) != 5:
            raise ConnecticutSourceChanged(
                "case_event_row_shape_changed",
                "Connecticut scheduled-event row has an unexpected cell count",
                url=source_url,
                details={"docket": docket, "cell_count": len(cells)},
            )
        publisher_number = _text(cells[0])
        if not publisher_number:
            raise ConnecticutSourceChanged(
                "case_event_number_missing",
                "Connecticut scheduled event has no publisher event number",
                url=source_url,
                details={"docket": docket},
            )
        date_raw = _optional(_text(cells[1]))
        events.append(
            {
                "canonical_ref": _child_ref(
                    docket,
                    "scheduled_event",
                    publisher_number,
                ),
                "publisher_event_number": publisher_number,
                "date_raw": date_raw,
                "date": _date_iso(date_raw),
                "time_raw": _optional(_text(cells[2])),
                "description": _optional(_text(cells[3])),
                "status": _optional(_text(cells[4])),
            }
        )
    heading = grid.find_previous(
        string=re.compile(r"Scheduled Court Dates as of", re.IGNORECASE)
    )
    as_of_match = re.search(
        r"Scheduled Court Dates as of\s+(\d{1,2}/\d{1,2}/\d{4})",
        _clean(heading),
        re.IGNORECASE,
    )
    as_of_raw = as_of_match.group(1) if as_of_match else None
    return events, as_of_raw


def parse_case_detail(
    html: str,
    *,
    requested_docket: str,
    source_url: str,
) -> dict[str, Any]:
    """Parse the case, parties, docket entries, documents, and events."""

    requested = normalize_docket(requested_docket)
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.title)
    if not title.startswith("Case Detail -"):
        raise ConnecticutSourceChanged(
            "case_detail_title_changed",
            "Connecticut docket lookup returned an unexpected page",
            url=source_url,
            details={"title": title, "requested_docket": requested},
        )
    docket_item = _suffix_item(soup, "CaseDetailHeader1_lblDocketNo")
    observed_raw = _text(docket_item)
    try:
        observed = normalize_docket(observed_raw)
    except ConnecticutSelectionError as exc:
        raise ConnecticutSourceChanged(
            "case_detail_docket_changed",
            "Connecticut case detail has an unexpected docket value",
            url=source_url,
            details={"docket": observed_raw},
        ) from exc
    if observed != requested:
        raise ConnecticutSourceChanged(
            "case_detail_docket_mismatch",
            "Connecticut docket lookup returned a different case",
            url=source_url,
            details={"requested": requested, "observed": observed},
        )
    caption = _text(
        _suffix_item(soup, "CaseDetailHeader1_lblCaseCaption")
    )
    case_type_header = _strip_label(
        _text(_suffix_item(soup, "CaseDetailHeader1_lblCaseType")),
        "Case Type",
    )
    file_date_raw = _strip_label(
        _text(_suffix_item(soup, "CaseDetailHeader1_lblFileDate")),
        "File Date",
    )
    return_date_raw = _strip_label(
        _text(_suffix_item(soup, "CaseDetailHeader1_lblReturnDate")),
        "Return Date",
    )
    if not caption or not case_type_header or not file_date_raw:
        raise ConnecticutSourceChanged(
            "case_detail_header_incomplete",
            "Connecticut case detail header is incomplete",
            url=source_url,
            details={"docket": requested},
        )
    docket_entries = _parse_docket_entries(
        soup,
        docket=requested,
        source_url=source_url,
    )
    scheduled_events, schedule_as_of_raw = _parse_scheduled_events(
        soup,
        docket=requested,
        source_url=source_url,
    )
    updated_match = re.search(
        r"Information Updated as of:\s*(\d{1,2}/\d{1,2}/\d{4})",
        _clean(soup.get_text(" ")),
        re.IGNORECASE,
    )
    updated_raw = updated_match.group(1) if updated_match else None
    prefix_suffix = _optional(
        _text(_suffix_item(soup, "CaseDetailHeader1_lblPrefixSuffix"))
    )
    case_type_description = _optional(
        _text(_suffix_item(soup, "CaseDetailBasicInfo1_lblBasicCaseType"))
    )
    location = _optional(
        _text(_suffix_item(soup, "CaseDetailBasicInfo1_lblBasicLocation"))
    )
    parties = _parse_parties(soup, docket=requested)
    record = {
        "canonical_ref": _case_ref(requested),
        "source_id": SOURCE_ID,
        "record_kind": "connecticut_superior_court_case",
        "docket": requested,
        "source_docket_raw": observed_raw,
        "source_docket_compact": compact_docket(requested),
        "caption": caption,
        "prefix_suffix_raw": prefix_suffix,
        "case_type_code": case_type_header,
        "case_type_description": case_type_description,
        "case_category": requested.split("-")[1],
        "file_date_raw": file_date_raw,
        "file_date": _date_iso(file_date_raw),
        "return_date_raw": return_date_raw,
        "return_date": _date_iso(return_date_raw),
        "court": {
            "court_id": _court_id(requested),
            "name": "Connecticut Superior Court",
            "location_code": requested.split("-", 1)[0],
            "location": location,
            "state_code": "CT",
        },
        "property_address_raw": _optional(
            _text(
                _suffix_item(
                    soup,
                    "CaseDetailBasicInfo1_lblPropertyAddress",
                )
            )
        ),
        "list_type": _optional(
            _text(
                _suffix_item(
                    soup,
                    "CaseDetailBasicInfo1_lblBasicListType",
                )
            )
        ),
        "trial_list_claim": _optional(
            _text(
                _suffix_item(
                    soup,
                    "CaseDetailBasicInfo1_lblKeyTrialList",
                )
            )
        ),
        "last_action_date_raw": _optional(
            _text(
                _suffix_item(
                    soup,
                    "CaseDetailBasicInfo1_lblBasicLastAction",
                )
            )
        ),
        "disposition": {
            "date_raw": _optional(
                _text(
                    _suffix_item(
                        soup,
                        "CaseDetailBasicInfo1_lblBasicDispositionDate",
                    )
                )
            ),
            "description": _optional(
                _text(
                    _suffix_item(
                        soup,
                        "CaseDetailBasicInfo1_lblBasicDisposition",
                    )
                )
            ),
            "judge_or_magistrate": _optional(
                _text(
                    _suffix_item(
                        soup,
                        "CaseDetailBasicInfo1_lblBasicDispJudge",
                    )
                )
            ),
        },
        "parties": parties,
        "docket_entries": docket_entries,
        "filing_documents": [
            entry
            for entry in docket_entries
            if entry["publisher_document_number"] is not None
        ],
        "scheduled_events": scheduled_events,
        "schedule_as_of_raw": schedule_as_of_raw,
        "schedule_as_of": _date_iso(schedule_as_of_raw),
        "information_updated_as_of_raw": updated_raw,
        "information_updated_as_of": _date_iso(updated_raw),
        "history": None,
        "notices": None,
        "source_url": source_url,
        "display_guide_url": DISPLAY_GUIDE_URL,
        "lineage": {
            "case_detail": "same court case record",
            "filing_documents": (
                "underlying filed artifacts linked from this court case"
            ),
            "independent_corroboration": False,
        },
        "schema_fingerprint": schema_fingerprint(
            {
                "parties": _schema_for_table(
                    _suffix_item(soup, CASE_PARTIES_GRID_SUFFIX)
                ),
                "docket_entries": _schema_for_table(
                    _suffix_item(soup, CASE_DOCUMENTS_GRID_SUFFIX)
                ),
                "scheduled_events": _schema_for_table(
                    _suffix_item(soup, CASE_EVENTS_GRID_SUFFIX)
                ),
            }
        ),
    }
    disposition_date_raw = record["disposition"]["date_raw"]
    record["disposition"]["date"] = _date_iso(disposition_date_raw)
    last_action_raw = record["last_action_date_raw"]
    record["last_action_date"] = _date_iso(last_action_raw)
    return record


def parse_case_history(
    html: str,
    *,
    docket: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Parse published case-transfer history."""

    normalized = normalize_docket(docket)
    soup = BeautifulSoup(html, "html.parser")
    error = _text(
        soup.select_one(
            "#ctl00_ContentPlaceHolder1_lblPageErrorMessages"
        )
    )
    grid = soup.select_one(f"#{HISTORY_GRID_ID}")
    if grid is None:
        if "no transfer history for" in error.casefold():
            return []
        raise ConnecticutSourceChanged(
            "case_history_grid_missing",
            "Connecticut case history lacks a grid or empty marker",
            url=source_url,
            details={"docket": normalized, "message": error},
        )
    expected_headers = ("Transferred From", "Transferred To", "Transfer Date")
    headers = _table_headers(grid)
    if headers != expected_headers:
        raise ConnecticutSourceChanged(
            "case_history_columns_changed",
            "Connecticut transfer-history columns changed",
            url=source_url,
            details={"expected": expected_headers, "observed": headers},
        )
    history: list[dict[str, Any]] = []
    for row in grid.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if not cells:
            continue
        if len(cells) != 3:
            raise ConnecticutSourceChanged(
                "case_history_row_shape_changed",
                "Connecticut transfer-history row shape changed",
                url=source_url,
                details={"cell_count": len(cells)},
            )
        from_docket = normalize_docket(_text(cells[0]))
        to_docket = normalize_docket(_text(cells[1]))
        date_raw = _optional(_text(cells[2]))
        history.append(
            {
                "canonical_ref": _derived_child_ref(
                    normalized,
                    "transfer_event",
                    (from_docket, to_docket, date_raw),
                ),
                "identity_basis": "published_transfer_field_tuple",
                "transferred_from_docket": from_docket,
                "transferred_to_docket": to_docket,
                "transfer_date_raw": date_raw,
                "transfer_date": _date_iso(date_raw),
            }
        )
    return history


def parse_notices(
    html: str,
    *,
    docket: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Parse case notices while preserving the publisher eNID and PSID."""

    normalized = normalize_docket(docket)
    soup = BeautifulSoup(html, "html.parser")
    empty = _text(
        soup.select_one("#ctl00_ContentPlaceHolder1_lblNoNotices")
    )
    grid = soup.select_one(f"#{NOTICES_GRID_ID}")
    if grid is None:
        if "no notices for" in empty.casefold():
            return []
        raise ConnecticutSourceChanged(
            "case_notices_grid_missing",
            "Connecticut notices lack a grid or empty marker",
            url=source_url,
            details={"docket": normalized, "message": empty},
        )
    expected_headers = ("Published Date", "Notice Content", "Action")
    headers = _table_headers(grid)
    if headers != expected_headers:
        raise ConnecticutSourceChanged(
            "case_notices_columns_changed",
            "Connecticut case-notice columns changed",
            url=source_url,
            details={"expected": expected_headers, "observed": headers},
        )
    notices: list[dict[str, Any]] = []
    for row in grid.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        if not cells:
            continue
        if len(cells) != 3:
            raise ConnecticutSourceChanged(
                "case_notice_row_shape_changed",
                "Connecticut case-notice row shape changed",
                url=source_url,
                details={"cell_count": len(cells)},
            )
        link = cells[2].select_one("a[href]")
        if link is None:
            raise ConnecticutSourceChanged(
                "case_notice_link_missing",
                "Connecticut case notice lacks its full-notice link",
                url=source_url,
            )
        notice_url = urljoin(source_url, str(link.get("href", "")))
        _validate_official_url(notice_url, label="case notice link")
        enid = _publisher_id_from_url(notice_url, "eNID")
        psid = _publisher_id_from_url(notice_url, "PSID")
        if not enid:
            raise ConnecticutSourceChanged(
                "case_notice_identifier_missing",
                "Connecticut case notice link has no eNID",
                url=source_url,
                details={"notice_url": notice_url},
            )
        date_raw = _optional(_text(cells[0]))
        notices.append(
            {
                "canonical_ref": _child_ref(
                    normalized,
                    "notice",
                    enid,
                ),
                "publisher_notice_id": enid,
                "publisher_publication_set_id": psid,
                "published_date_raw": date_raw,
                "published_date": _date_iso(date_raw),
                "content_preview": _optional(_text(cells[1])),
                "action_label": _optional(_text(link)),
                "notice_handler": Path(urlsplit(notice_url).path).name,
                "full_notice_url": notice_url,
            }
        )
    return notices


class ConnecticutCivilFamilyClient:
    """Portal client using a source-local, injectable libcurl session."""

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
            raise ValueError("request_budget must be positive when supplied")
        self._owns_session = session is None
        if session is None:
            if curl_requests is None:
                raise ConnecticutTransportUnavailable(
                    "curl-cffi is required for the Connecticut court portal "
                    "because the standard repository requests transport cannot "
                    "complete this host's TLS handshake",
                    url=BASE_URL,
                    details={"dependency": "curl-cffi>=0.13.0"},
                )
            session = curl_requests.Session(impersonate="chrome")
        self.session = session
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "Accept-Language": "en-US,en;q=0.9",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/136.0 Safari/537.36"
                    ),
                }
            )
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.retry_policy = RetryPolicy(
            max_attempts=retry_attempts,
        )
        self.sleeper = sleeper
        self.request_budget = request_budget
        self.request_count = 0

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def __enter__(self) -> ConnecticutCivilFamilyClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        referer: str | None = None,
    ) -> Any:
        _validate_official_url(url, label="request")
        headers = {"Referer": referer} if referer else None
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise ConnecticutRequestBudgetExceeded(
                    "Connecticut source request budget was exhausted",
                    url=url,
                    details={
                        "request_budget": self.request_budget,
                        "request_count": self.request_count,
                    },
                )
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except Exception as exc:
                if (
                    CurlRequestException is not None
                    and isinstance(exc, CurlRequestException)
                ):
                    last_error = exc
                    if attempt < self.retry_policy.max_attempts:
                        self.sleeper(self.retry_policy.delay(attempt))
                        continue
                    raise TransportError(
                        "Connecticut court portal request failed",
                        url=url,
                        details={
                            "error_type": type(exc).__name__,
                            "attempts": attempt,
                        },
                    ) from exc
                raise
            status = int(response.status_code)
            if status in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    retry_after = None
                    retry_value = (
                        response.headers.get("Retry-After")
                        or response.headers.get("retry-after")
                    )
                    if retry_value:
                        try:
                            retry_after = float(retry_value)
                        except (TypeError, ValueError):
                            retry_after = None
                    self.sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                if status == 429:
                    raise RateLimitedHTTPError(status, url=str(response.url))
                raise HTTPStatusError(status, url=str(response.url))
            if status in {401, 403}:
                raise RestrictedHTTPError(status, url=str(response.url))
            if status < 200 or status >= 300:
                response_text = str(getattr(response, "text", ""))
                raise HTTPStatusError(
                    status,
                    url=str(response.url),
                    response_text=response_text,
                )
            return response
        raise TransportError(
            "Connecticut court portal request failed",
            url=url,
            details={"error_type": type(last_error).__name__},
        )

    def search_parties(
        self,
        *,
        last_name: str,
        first_name: str | None = None,
        match: str = "exact",
        location: str = "ALL",
        category: str = "ALL",
        case_type: str = "All",
        sort: str = "party_name",
    ) -> tuple[PartySearchForm, PartyResultPage]:
        landing = self._request("GET", PARTY_SEARCH_URL)
        _require_html(landing, label="party search landing")
        form = parse_party_search_form(
            str(landing.text),
            source_url=str(landing.url),
        )
        payload = build_party_search_payload(
            form,
            last_name=last_name,
            first_name=first_name,
            match=match,
            location=location,
            category=category,
            case_type=case_type,
            sort=sort,
        )
        result = self._request(
            "POST",
            form.action_url,
            data=payload,
            referer=PARTY_SEARCH_URL,
        )
        _require_html(result, label="party search results")
        return form, parse_party_results(
            str(result.text),
            source_url=str(result.url),
        )

    def fetch_case_detail(self, docket: str) -> dict[str, Any]:
        normalized = normalize_docket(docket)
        response = self._request(
            "GET",
            LOAD_DOCKET_URL,
            params={"DocketNo": normalized},
        )
        _require_html(response, label="case detail")
        expected_path = "/CaseDetail/PublicCaseDetail.aspx"
        if urlsplit(str(response.url)).path.casefold() != expected_path.casefold():
            raise ConnecticutSourceChanged(
                "case_detail_route_changed",
                "Connecticut docket lookup did not reach the case-detail route",
                url=str(response.url),
                details={"requested_docket": normalized},
            )
        return parse_case_detail(
            str(response.text),
            requested_docket=normalized,
            source_url=str(response.url),
        )

    def fetch_history(self, docket: str) -> list[dict[str, Any]]:
        normalized = normalize_docket(docket)
        detail_url = f"{CASE_DETAIL_URL}?{urlencode({'DocketNo': compact_docket(normalized)})}"
        response = self._request(
            "GET",
            CASE_HISTORY_URL,
            params={"DocketNo": compact_docket(normalized)},
            referer=detail_url,
        )
        _require_html(response, label="case history")
        return parse_case_history(
            str(response.text),
            docket=normalized,
            source_url=str(response.url),
        )

    def fetch_notices(self, docket: str) -> list[dict[str, Any]]:
        normalized = normalize_docket(docket)
        detail_url = f"{CASE_DETAIL_URL}?{urlencode({'DocketNo': compact_docket(normalized)})}"
        response = self._request(
            "GET",
            NOTICES_URL,
            params={"DocketNo": compact_docket(normalized)},
            referer=detail_url,
        )
        _require_html(response, label="case notices")
        return parse_notices(
            str(response.text),
            docket=normalized,
            source_url=str(response.url),
        )

    def fetch_case_bundle(self, docket: str) -> CaseBundle:
        record = self.fetch_case_detail(docket)
        errors: list[PublicRecordsHTTPError] = []
        for key, fetcher in (
            ("history", self.fetch_history),
            ("notices", self.fetch_notices),
        ):
            try:
                record[key] = fetcher(record["docket"])
            except PublicRecordsHTTPError as error:
                errors.append(error)
        return CaseBundle(
            record=record,
            child_errors=tuple(errors),
        )

    def fetch_document(self, document_number: str) -> dict[str, Any]:
        normalized = _clean(document_number)
        if not normalized.isdigit():
            raise ConnecticutSelectionError(
                "invalid_document_number",
                "DocumentNo must contain digits only",
                details={"document_number": normalized},
            )
        response = self._request(
            "GET",
            DOCUMENT_URL,
            params={"DocumentNo": normalized},
        )
        url = str(response.url)
        _validate_official_url(url, label="filing document")
        media_type = _content_type(response)
        content = bytes(response.content)
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise ConnecticutSourceChanged(
                "document_response_changed",
                "Connecticut DocumentNo did not return a PDF",
                url=url,
                details={
                    "content_type": media_type,
                    "magic": content[:12].hex(),
                },
            )
        returned_number = _publisher_id_from_url(url, "DocumentNo")
        if returned_number != normalized:
            raise ConnecticutSourceChanged(
                "document_number_mismatch",
                "Connecticut returned a different DocumentNo",
                url=url,
                details={
                    "requested": normalized,
                    "observed": returned_number,
                },
            )
        disposition = (
            response.headers.get("Content-Disposition")
            or response.headers.get("content-disposition")
        )
        return {
            "publisher_document_number": normalized,
            "source_url": url,
            "content_type": media_type,
            "content_disposition": _optional(disposition),
            "byte_length": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "content": content,
        }


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
                "party_search_grain": "one published party occurrence",
                "case_identity": "normalized full docket",
                "same_name_identity_status": (
                    "unresolved discovery candidate"
                ),
            },
        ),
    )


def _cursor_binding(parameters: Mapping[str, Any]) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": "party_search",
            "parameters": parameters,
        }
    )


def _encode_cursor(
    *,
    parameters: Mapping[str, Any],
    offset: int,
    snapshot: str,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "binding": _cursor_binding(parameters),
        "offset": offset,
        "snapshot": snapshot,
        "scope": "adapter_window_within_reacquired_source_display_slice",
    }
    return base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str,
    *,
    parameters: Mapping[str, Any],
    snapshot: str,
    row_count: int,
) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnecticutSelectionError(
            "invalid_cursor",
            "party-search cursor is malformed",
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("version") != CURSOR_VERSION
        or payload.get("binding") != _cursor_binding(parameters)
        or payload.get("scope")
        != "adapter_window_within_reacquired_source_display_slice"
    ):
        raise ConnecticutSelectionError(
            "cursor_query_mismatch",
            "party-search cursor belongs to a different query or scope",
        )
    if payload.get("snapshot") != snapshot:
        raise ConnecticutSelectionError(
            "cursor_snapshot_changed",
            "Connecticut party-search displayed slice changed before resume",
        )
    offset = payload.get("offset")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or offset >= row_count
    ):
        raise ConnecticutSelectionError(
            "cursor_offset_invalid",
            "party-search cursor offset is outside the displayed slice",
        )
    return offset


def _normalize_party_occurrence(
    row: Mapping[str, Any],
    *,
    page: PartyResultPage,
    form: PartySearchForm,
) -> dict[str, Any]:
    docket = str(row["docket"])
    party_number = str(row["publisher_party_number"])
    return {
        "canonical_ref": _child_ref(docket, "party", party_number),
        "case_canonical_ref": _case_ref(docket),
        "source_id": SOURCE_ID,
        "record_kind": "party_search_occurrence",
        "party_name": row["party_name"],
        "publisher_party_number": party_number,
        "case_name": row["case_name"],
        "docket": docket,
        "court_location": row["court_location"],
        "self_represented_raw": row["self_represented_raw"],
        "case_url": row["case_url"],
        "identity_resolution": {
            "status": "unresolved_same_name_candidate",
            "reason": (
                "A party-name occurrence is a discovery pivot; the source "
                "does not establish that it is the intended person."
            ),
        },
        "source_display": {
            "source_reported_count": page.source_reported_count,
            "displayed_start": page.displayed_start,
            "displayed_end": page.displayed_end,
            "has_pager": page.has_pager,
            "completeness": (
                "unresolved_source_display_slice"
                if page.source_slice_unresolved
                else "source_reported_complete"
            ),
        },
        "schema_fingerprints": {
            "search_form": form.schema_fingerprint,
            "party_results": page.schema_fingerprint,
        },
        "lineage": {
            "relationship_to_case_detail": "same court case record",
            "independent_corroboration": False,
        },
    }


def _selection_failure(
    query: PublicRecordsQuery,
    error: ConnecticutSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="selection",
                retryable=False,
                details=error.details,
            )
        ],
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


def search_parties(
    *,
    last_name: str,
    first_name: str | None = None,
    match: str = "exact",
    location: str = "ALL",
    category: str = "ALL",
    case_type: str = "All",
    sort: str = "party_name",
    limit: int | None = None,
    cursor: str | None = None,
    client: ConnecticutCivilFamilyClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one source-native party search without an implicit local cap."""

    if limit is not None and (isinstance(limit, bool) or limit <= 0):
        raise ValueError("limit must be positive when supplied")
    parameters = {
        "last_name": _clean(last_name),
        "first_name": _optional(first_name),
        "match": match,
        "location": location,
        "category": category,
        "case_type": case_type,
        "sort": sort,
    }
    query = _build_query(
        "party_search",
        parameters,
        limit=limit,
        cursor=cursor,
    )
    try:
        active_client = client or ConnecticutCivilFamilyClient()
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    owns_client = client is None
    try:
        form, page = active_client.search_parties(
            last_name=parameters["last_name"],
            first_name=parameters["first_name"],
            match=match,
            location=location,
            category=category,
            case_type=case_type,
            sort=sort,
        )
        if page.authoritative_no_results:
            result = PublicRecordsResult.success(query, [])
            _best_effort_log(query, result)
            return result
        normalized = [
            _normalize_party_occurrence(
                row,
                page=page,
                form=form,
            )
            for row in page.rows
        ]
        snapshot = sha256_fingerprint(
            [
                {
                    "docket": row["docket"],
                    "party_number": row["publisher_party_number"],
                    "party_name": row["party_name"],
                    "case_name": row["case_name"],
                }
                for row in page.rows
            ]
        )
        offset = (
            _decode_cursor(
                cursor,
                parameters=parameters,
                snapshot=snapshot,
                row_count=len(normalized),
            )
            if cursor
            else 0
        )
        stop = len(normalized) if limit is None else min(
            offset + limit,
            len(normalized),
        )
        records = normalized[offset:stop]
        next_cursor = (
            _encode_cursor(
                parameters=parameters,
                offset=stop,
                snapshot=snapshot,
            )
            if stop < len(normalized)
            else None
        )
        errors: list[PublicRecordsError] = []
        if page.source_slice_unresolved:
            errors.append(
                PublicRecordsError(
                    code="source_display_slice",
                    message=(
                        "The portal displayed 50 party occurrences without "
                        "publishing a pager or a count beyond that slice."
                    ),
                    category="source_completeness",
                    retryable=False,
                    details={
                        "displayed_rows": len(page.rows),
                        "source_reported_label": (
                            f"{page.displayed_start}-{page.displayed_end} "
                            f"of {page.source_reported_count}"
                        ),
                        "source_display_slice_size": (
                            SOURCE_DISPLAY_SLICE_SIZE
                        ),
                        "bulk_complement_url": BULK_DESCRIPTION_URL,
                    },
                )
            )
        if next_cursor is not None:
            errors.append(
                PublicRecordsError(
                    code="caller_selected_slice",
                    message=(
                        "The caller-selected limit stopped within the "
                        "portal's displayed slice."
                    ),
                    category="query_bounds",
                    retryable=False,
                    details={
                        "returned_offset": offset,
                        "next_offset": stop,
                        "displayed_rows": len(normalized),
                        "cursor_scope": (
                            "adapter window within the same reacquired "
                            "source display slice"
                        ),
                        "publisher_continuation_beyond_slice": False,
                    },
                )
            )
        if errors:
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=records,
                next_cursor=next_cursor,
                warnings=(
                    "Every same-name row remains an unresolved discovery "
                    "candidate until separately resolved.",
                ),
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=(
                    "Every same-name row remains an unresolved discovery "
                    "candidate until separately resolved.",
                ),
            )
        _best_effort_log(query, result)
        return result
    except ConnecticutSelectionError as error:
        result = _selection_failure(query, error)
        _best_effort_log(query, result)
        return result
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
        _best_effort_log(query, result)
        return result
    finally:
        if owns_client:
            active_client.close()


def lookup_case(
    docket: str,
    *,
    client: ConnecticutCivilFamilyClient | Any | None = None,
) -> PublicRecordsResult:
    normalized = normalize_docket(docket)
    query = _build_query(
        "case",
        {"docket": normalized},
    )
    try:
        active_client = client or ConnecticutCivilFamilyClient()
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    owns_client = client is None
    try:
        bundle = active_client.fetch_case_bundle(normalized)
        if bundle.child_errors:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [error.to_contract_error() for error in bundle.child_errors],
                records=[bundle.record],
                warnings=(
                    "Case detail was retrieved, but at least one child page "
                    "was unavailable.",
                ),
            )
        return PublicRecordsResult.success(query, [bundle.record])
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    finally:
        if owns_client:
            active_client.close()


def retrieve_document(
    document_number: str,
    *,
    pdf_output: str | Path,
    docket: str | None = None,
    client: ConnecticutCivilFamilyClient | Any | None = None,
) -> PublicRecordsResult:
    normalized_document = _clean(document_number)
    normalized_docket = normalize_docket(docket) if docket else None
    query = _build_query(
        "document",
        {
            "publisher_document_number": normalized_document,
            "docket": normalized_docket,
        },
    )
    try:
        active_client = client or ConnecticutCivilFamilyClient()
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    owns_client = client is None
    try:
        filing_metadata = None
        if normalized_docket:
            case_record = active_client.fetch_case_detail(normalized_docket)
            matches = [
                item
                for item in case_record["filing_documents"]
                if item["publisher_document_number"]
                == normalized_document
            ]
            if len(matches) != 1:
                return _selection_failure(
                    query,
                    ConnecticutSelectionError(
                        "document_not_linked_from_docket",
                        "DocumentNo is not uniquely linked from the supplied "
                        "docket detail",
                        details={
                            "docket": normalized_docket,
                            "publisher_document_number": normalized_document,
                            "matches": len(matches),
                        },
                    ),
                )
            filing_metadata = matches[0]
        artifact = active_client.fetch_document(normalized_document)
        output_path = Path(pdf_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(artifact.pop("content"))
        record = {
            "canonical_ref": (
                _child_ref(
                    normalized_docket,
                    "document",
                    normalized_document,
                )
                if normalized_docket
                else None
            ),
            "source_id": SOURCE_ID,
            "record_kind": "connecticut_case_filing_pdf",
            "docket": normalized_docket,
            **artifact,
            "artifact_path": str(output_path),
            "filing_metadata": filing_metadata,
            "lineage": {
                "relationship": "underlying court-filed artifact",
                "independent_corroboration_of_case_index": False,
            },
        }
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[str(output_path)],
        )
    except ConnecticutSelectionError as error:
        return _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    finally:
        if owns_client:
            active_client.close()


def source_routes() -> PublicRecordsResult:
    query = _build_query("routes", {})
    records = [
        {
            "route_id": "party_search",
            "name": "Civil/Family party-name search",
            "url": PARTY_SEARCH_URL,
            "record_or_artifact": "published party occurrence",
            "implemented": True,
            "relationship": "primary discovery route",
            "selectors": [
                "last name",
                "first name",
                "name match mode",
                "court location",
                "case category",
                "case type",
            ],
        },
        {
            "route_id": "case_detail",
            "name": "Civil/Family docket lookup",
            "url": LOAD_DOCKET_URL,
            "record_or_artifact": (
                "case metadata, parties, appearances, docket entries, "
                "scheduled events, transfer history, and notices"
            ),
            "implemented": True,
            "relationship": "expanded view of the same court case",
        },
        {
            "route_id": "filing_document",
            "name": "Civil/Family DocumentInquiry",
            "url": DOCUMENT_URL,
            "record_or_artifact": "PDF filed in the selected case",
            "implemented": True,
            "publisher_identifier": "DocumentNo",
            "relationship": "underlying artifact linked from case detail",
        },
        {
            "route_id": "civil_family_bulk",
            "name": "Civil/Family bulk case data",
            "url": BULK_DESCRIPTION_URL,
            "record_or_artifact": (
                "pending and disposed Civil/Family case data"
            ),
            "implemented": False,
            "access_mode": "publisher fee and enrollment",
            "published_fields": [
                "basic case information",
                "important case dates",
                "party and appearance information",
                "motions and pleadings",
                "companion cases",
            ],
            "electronic_documents_included": False,
            "relationship": (
                "field-matched comprehensive complement to the portal's "
                "interactive display"
            ),
            "independent_corroboration": False,
        },
        {
            "route_id": "clerk_offices",
            "name": "Superior Court clerk offices",
            "url": CLERK_DIRECTORY_URL,
            "record_or_artifact": (
                "court-of-record assistance and copies for records not "
                "published through the interactive display"
            ),
            "implemented": False,
            "relationship": "human acquisition complement",
        },
    ]
    return PublicRecordsResult.success(query, records)


def execute(
    args: argparse.Namespace,
    *,
    client: ConnecticutCivilFamilyClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute the source adapter without writing output."""

    if args.command == "routes":
        return source_routes()
    if args.command == "search":
        return search_parties(
            last_name=args.last_name,
            first_name=getattr(args, "first_name", None),
            match=getattr(args, "match", "exact"),
            location=getattr(args, "location", "ALL"),
            category=getattr(args, "category", "ALL"),
            case_type=getattr(args, "case_type", "All"),
            sort=getattr(args, "sort", "party_name"),
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            client=client,
        )
    if args.command == "case":
        return lookup_case(args.docket, client=client)
    if args.command == "document":
        return retrieve_document(
            args.document_number,
            pdf_output=args.pdf_output,
            docket=getattr(args, "docket", None),
            client=client,
        )
    if args.command == "probe":
        return probe_source(client=client)
    raise ValueError(f"unsupported Connecticut operation: {args.command}")


def probe_source(
    *,
    client: ConnecticutCivilFamilyClient | Any | None = None,
) -> PublicRecordsResult:
    query = _build_query(
        "probe",
        {
            "last_name": SENTINEL_LAST_NAME,
            "docket": SENTINEL_DOCKET,
            "party_number": SENTINEL_PARTY_NUMBER,
        },
    )
    try:
        active_client = client or ConnecticutCivilFamilyClient()
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    owns_client = client is None
    try:
        form, page = active_client.search_parties(
            last_name=SENTINEL_LAST_NAME,
            match="exact",
        )
        sentinel_hits = [
            row
            for row in page.rows
            if row["docket"] == SENTINEL_DOCKET
            and row["publisher_party_number"] == SENTINEL_PARTY_NUMBER
        ]
        if len(sentinel_hits) != 1:
            raise ConnecticutSourceChanged(
                "probe_party_sentinel_changed",
                "Connecticut exact-name search no longer contains the "
                "verified docket/party sentinel",
                url=PARTY_SEARCH_URL,
                details={
                    "docket": SENTINEL_DOCKET,
                    "party_number": SENTINEL_PARTY_NUMBER,
                    "matches": len(sentinel_hits),
                },
            )
        if not page.source_slice_unresolved:
            raise ConnecticutSourceChanged(
                "probe_source_slice_changed",
                "Connecticut exact-name sentinel no longer matches the "
                "verified 50-row no-pager display contract",
                url=PARTY_SEARCH_URL,
                details={
                    "rows": len(page.rows),
                    "displayed_start": page.displayed_start,
                    "displayed_end": page.displayed_end,
                    "source_reported_count": page.source_reported_count,
                    "has_pager": page.has_pager,
                },
            )
        bundle = active_client.fetch_case_bundle(SENTINEL_DOCKET)
        case = bundle.record
        document_matches = [
            item
            for item in case["filing_documents"]
            if item["publisher_document_number"]
            == SENTINEL_DOCUMENT_NUMBER
        ]
        if len(document_matches) != 1:
            raise ConnecticutSourceChanged(
                "probe_document_sentinel_changed",
                "Connecticut sentinel case no longer links the verified "
                "complaint DocumentNo",
                url=case["source_url"],
                details={
                    "document_number": SENTINEL_DOCUMENT_NUMBER,
                    "matches": len(document_matches),
                },
            )
        record = {
            "source_id": SOURCE_ID,
            "party_search": {
                "last_name": SENTINEL_LAST_NAME,
                "displayed_rows": len(page.rows),
                "source_reported_count": page.source_reported_count,
                "source_display_slice_unresolved": (
                    page.source_slice_unresolved
                ),
                "form_schema_fingerprint": form.schema_fingerprint,
                "results_schema_fingerprint": page.schema_fingerprint,
            },
            "sentinel": {
                "docket": SENTINEL_DOCKET,
                "publisher_party_number": SENTINEL_PARTY_NUMBER,
                "publisher_document_number": (
                    SENTINEL_DOCUMENT_NUMBER
                ),
                "case_type_code": case["case_type_code"],
                "file_date": case["file_date"],
            },
            "child_pages": {
                "history_retrieved": case["history"] is not None,
                "notices_retrieved": case["notices"] is not None,
            },
        }
        if bundle.child_errors:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [error.to_contract_error() for error in bundle.child_errors],
                records=[record],
            )
        return PublicRecordsResult.success(query, [record])
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    finally:
        if owns_client:
            active_client.close()


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
        help="minimum seconds between source requests",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="attempts for retryable HTTP responses",
    )


def _client_from_args(args: argparse.Namespace) -> ConnecticutCivilFamilyClient:
    return ConnecticutCivilFamilyClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser(
        "search",
        help="search published party occurrences",
    )
    search_parser.add_argument("last_name")
    search_parser.add_argument("--first-name")
    search_parser.add_argument(
        "--match",
        choices=tuple(MATCH_VALUES),
        default="exact",
    )
    search_parser.add_argument("--location", default="ALL")
    search_parser.add_argument("--category", default="ALL")
    search_parser.add_argument("--case-type", default="All")
    search_parser.add_argument(
        "--sort",
        choices=tuple(SORT_VALUES),
        default="party_name",
    )
    search_parser.add_argument("--limit", type=int)
    search_parser.add_argument(
        "--cursor",
        help=(
            "resume an adapter window within the same reacquired 50-row "
            "source display slice; never continues beyond that slice"
        ),
    )
    _add_transport_args(search_parser)
    add_output_args(search_parser)

    case_parser = subparsers.add_parser(
        "case",
        help="retrieve one exact docket and its published child pages",
    )
    case_parser.add_argument("docket")
    _add_transport_args(case_parser)
    add_output_args(case_parser)

    document_parser = subparsers.add_parser(
        "document",
        help="retrieve one filing PDF by publisher DocumentNo",
    )
    document_parser.add_argument("document_number")
    document_parser.add_argument(
        "--docket",
        help="optionally verify that the case detail links this DocumentNo",
    )
    document_parser.add_argument(
        "--pdf-output",
        required=True,
        metavar="FILE",
        help="write the filing PDF to FILE",
    )
    _add_transport_args(document_parser)
    add_output_args(document_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="verify stable party, docket, and child-record contracts",
    )
    _add_transport_args(probe_parser)
    add_output_args(probe_parser)

    routes_parser = subparsers.add_parser(
        "routes",
        help="show implemented and complementary official routes",
    )
    add_output_args(routes_parser)
    return parser


def _emit_result(
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
    try:
        if args.command == "routes":
            result = source_routes()
            summary = "Connecticut Civil/Family official routes"
        else:
            client = _client_from_args(args)
            try:
                if args.command == "search":
                    result = search_parties(
                        last_name=args.last_name,
                        first_name=args.first_name,
                        match=args.match,
                        location=args.location,
                        category=args.category,
                        case_type=args.case_type,
                        sort=args.sort,
                        limit=args.limit,
                        cursor=args.cursor,
                        client=client,
                    )
                    summary = (
                        "Connecticut Civil/Family party search "
                        f"{args.last_name!r}"
                    )
                elif args.command == "case":
                    result = lookup_case(args.docket, client=client)
                    summary = (
                        "Connecticut Civil/Family case "
                        f"{args.docket}"
                    )
                elif args.command == "document":
                    result = retrieve_document(
                        args.document_number,
                        docket=args.docket,
                        pdf_output=args.pdf_output,
                        client=client,
                    )
                    summary = (
                        "Connecticut filing DocumentNo "
                        f"{args.document_number}"
                    )
                else:
                    result = probe_source(client=client)
                    summary = "Connecticut Civil/Family source probe"
            finally:
                client.close()
    except ConnecticutSelectionError as error:
        parser.error(str(error))
    except PublicRecordsHTTPError as error:
        query = _build_query(args.command, {})
        result = failure_result(query, error)
        summary = f"Connecticut Civil/Family {args.command}"
    _emit_result(result, args, summary=summary)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
