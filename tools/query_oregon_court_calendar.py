#!/usr/bin/env python3
"""Query Oregon's official Circuit and Tax Court calendar.

The Oregon Judicial Department publishes the calendar through a Tyler
PublicAccess session.  A query requires three source-native steps: load the
location directory, select a location, and submit the ASP.NET search form.

Examples:
    uv run python tools/query_oregon_court_calendar.py locations --json
    uv run python tools/query_oregon_court_calendar.py judicial-officers \
        --location Deschutes --output /tmp/oregon-judges.json
    uv run python tools/query_oregon_court_calendar.py search \
        --location Deschutes --after 2026-07-29 --before 2026-07-29 \
        --output /tmp/oregon-calendar.json
    uv run python tools/query_oregon_court_calendar.py search \
        --location "Tax Court" --case-number TC-MD-240001R
    uv run python tools/query_oregon_court_calendar.py search \
        --location Multnomah --business-name "Example LLC"
    uv run python tools/query_oregon_court_calendar.py probe \
        --location Deschutes --output /tmp/oregon-calendar-probe.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse
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
        sha256_fingerprint,
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
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-or-circuit-tax-court-calendars"
STATE_CODE = "OR"
STATE_GEOID = "41"
BASE_URL = "https://publicaccess.courts.oregon.gov/PublicAccess/"
LANDING_URL = urljoin(BASE_URL, "default.aspx")
SEARCH_URL = urljoin(BASE_URL, "Search.aspx?ID=900")
RESULTS_URL = urljoin(BASE_URL, "CourtCalendarSearchResults.aspx")
HELP_URL = (
    "https://www.courts.oregon.gov/services/online/Documents/"
    "OJCIN/OECI/PA_QRefG_Calendars.pdf"
)

DOCUMENTED_RESULT_CEILING = 400
LIVE_OBSERVED_RETURNED_ROWS = 550
MAXIMUM_FORWARD_DATE_WINDOW_DAYS = 90
MAXIMUM_DATE_WINDOW_DAYS = MAXIMUM_FORWARD_DATE_WINDOW_DAYS
CURSOR_PREFIX = "orcal:v1:"
CURSOR_VERSION = 1

EXPECTED_SEARCH_MODES = {
    "0": "Case",
    "1": "Party or Defendant Name",
    "2": "Attorney",
    "3": "Judicial Officer",
    "5": "Date Range",
}
EXPECTED_RESULT_HEADERS = frozenset(
    {
        "Date",
        "Case Number",
        "Judicial Officer",
        "Time",
        "Type",
        "Style",
        "Physical Location",
        "Hearing Type",
    }
)
CATEGORY_CODES = {
    "criminal": ("CR", "chkDtRangeCriminal", "chkCriminal"),
    "civil": ("CV", "chkDtRangeCivil", "chkCivil"),
    "family": ("FAM", "chkDtRangeFamily", "chkFamily"),
    "probate": ("PR", "chkDtRangeProbate", "chkProbate"),
}

COUNTY_GEOIDS = {
    "baker": "41001",
    "benton": "41003",
    "clackamas": "41005",
    "clatsop": "41007",
    "columbia": "41009",
    "coos": "41011",
    "crook": "41013",
    "curry": "41015",
    "deschutes": "41017",
    "douglas": "41019",
    "gilliam": "41021",
    "grant": "41023",
    "harney": "41025",
    "hood river": "41027",
    "jackson": "41029",
    "jefferson": "41031",
    "josephine": "41033",
    "klamath": "41035",
    "lake": "41037",
    "lane": "41039",
    "lincoln": "41041",
    "linn": "41043",
    "malheur": "41045",
    "marion": "41047",
    "morrow": "41049",
    "multnomah": "41051",
    "polk": "41053",
    "sherman": "41055",
    "tillamook": "41057",
    "umatilla": "41059",
    "umatilla-hermiston": "41059",
    "union": "41061",
    "wallowa": "41063",
    "wasco": "41065",
    "washington": "41067",
    "wheeler": "41069",
    "yamhill": "41071",
}

COMPLEMENTARY_OFFICIAL_ROUTES = (
    {
        "source_id": "us-or-appellate-record-search",
        "name": "Oregon Appellate Record Search",
        "role": "Supreme Court and Court of Appeals cases, dockets, and events",
        "url": "https://trportal.courts.oregon.gov/portal/home",
    },
    {
        "source_id": "us-or-ojd-free-circuit-tax-record-search",
        "name": "Oregon Free Circuit and Tax Court Record Search",
        "role": "limited Circuit and Tax Court case and event metadata",
        "url": "https://webportal.courts.oregon.gov/portal/Home/Dashboard/29",
    },
    {
        "source_id": "us-or-ojcin",
        "name": "Oregon Judicial Case Information Network",
        "role": "Register of Actions and broader case-record access",
        "url": (
            "https://www.courts.oregon.gov/services/online/Pages/ojcin-signup.aspx"
        ),
    },
    {
        "source_id": "us-or-ojd-case-record-request",
        "name": "Oregon Judicial Department Case Record Request",
        "role": "official case copies and audio requests",
        "url": (
            "https://orjudicial.workflowcloud.com/forms/"
            "d322e429-d0f1-4dae-b2eb-8d24f59abd35"
        ),
    },
    {
        "source_id": "us-or-ojd-statewide-data-request",
        "name": "Oregon Statewide and Administrative Data Request",
        "role": "compiled statewide and administrative court data",
        "url": "https://courtsoregon.govqa.us/WEBAPP/_rs/",
    },
)

SOURCE_WARNINGS = (
    "The source form accepts current/future dates, limits one inclusive "
    "calendar interval to 90 days, and limits the end date to that forward "
    "window.",
    "OJD's calendar guide documents display of the first 400 results. "
    "An exact-400 response is reported as partial with partition hints.",
    "The live portal has also returned more than 400 rows and an explicit "
    "too-many-matches marker in one response; the adapter preserves returned "
    "rows, reports that guide/live fact, and marks the result partial.",
    "The source says schedules may change and should be checked again on the "
    "day of the event.",
    "The source omits calendar information for some case classes, including "
    "adoption, juvenile, mental-health, and VAWA-protected matters.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Oregon Circuit and Tax Court Calendars",
    source_role="trial_and_tax_court_hearing_calendar",
    base_url=LANDING_URL,
    dataset_id="oregon-ecourt-publicaccess-calendar",
    metadata={
        "authority": "Oregon Judicial Department",
        "operator": "Oregon Judicial Department through Tyler PublicAccess",
        "coverage": "Oregon Circuit Courts and Oregon Tax Court",
        "state_code": STATE_CODE,
        "authentication": "anonymous_session",
        "platform_family": "tyler_publicaccess_calendar",
        "official_quick_guide_url": HELP_URL,
        "documented_result_ceiling": DOCUMENTED_RESULT_CEILING,
        "live_observed_returned_rows": LIVE_OBSERVED_RETURNED_ROWS,
        "result_limit_semantics": (
            "guide_claim_and_live_observation_are_reported_separately"
        ),
        "maximum_forward_date_window_days": (MAXIMUM_FORWARD_DATE_WINDOW_DAYS),
        "maximum_date_window_days": MAXIMUM_DATE_WINDOW_DAYS,
        "complementary_source_ids": [
            route["source_id"] for route in COMPLEMENTARY_OFFICIAL_ROUTES
        ],
    },
)


@dataclass(frozen=True)
class OregonCalendarLocation:
    """One source-native location selector from the official landing page."""

    name: str
    native_value: str
    node_ids: tuple[str, ...]

    @property
    def county_geoid(self) -> str | None:
        return COUNTY_GEOIDS.get(self.name.casefold())

    @property
    def court_level(self) -> str:
        if self.name.casefold() == "tax court":
            return "tax"
        if self.name.casefold() == "all locations":
            return "circuit_and_tax"
        return "circuit"

    @property
    def court_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.casefold()).strip("-")
        if self.court_level == "tax":
            return "or-tax-court"
        if self.court_level == "circuit_and_tax":
            return "or-statewide-circuit-tax-calendar"
        return f"or-circuit-{slug}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "native_value": self.native_value,
            "node_ids": list(self.node_ids),
            "county_geoid": self.county_geoid,
            "court_level": self.court_level,
            "court_id": self.court_id,
        }


@dataclass(frozen=True)
class OregonJudicialOfficer:
    """One source-native judicial-officer selector."""

    native_id: str
    display_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "native_id": self.native_id,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class OregonCalendarLanding:
    """Validated official landing-page metadata."""

    locations: tuple[OregonCalendarLocation, ...]
    appellate_links: Mapping[str, str]
    restriction_notice: str
    schema_fingerprint: str


@dataclass(frozen=True)
class OregonCalendarSearchForm:
    """Validated same-session ASP.NET search form."""

    location: OregonCalendarLocation
    hidden_fields: Mapping[str, str]
    search_modes: Mapping[str, str]
    judicial_officers: tuple[OregonJudicialOfficer, ...]
    maximum_date_window_days: int
    forward_only: bool
    schema_fingerprint: str


@dataclass(frozen=True)
class OregonCalendarHearing:
    """One source-native hearing row."""

    case_number: str
    case_type: str | None
    caption: str
    judge: str | None
    physical_location: str | None
    hearing_date: str
    hearing_time: str | None
    hearing_type: str
    status_icons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "case_type": self.case_type,
            "caption": self.caption,
            "judge": self.judge,
            "physical_location": self.physical_location,
            "hearing_date": self.hearing_date,
            "hearing_time": self.hearing_time,
            "hearing_type": self.hearing_type,
            "status_icons": list(self.status_icons),
        }


@dataclass(frozen=True)
class OregonCalendarResults:
    """One complete source response before local result paging."""

    location_name: str
    rows: tuple[OregonCalendarHearing, ...]
    reported_count: int
    request_parameters: Mapping[str, str]
    schema_fingerprint: str
    alerts: tuple[str, ...] = ()

    @property
    def documented_ceiling_reached(self) -> bool:
        return self.reported_count == DOCUMENTED_RESULT_CEILING

    @property
    def exceeds_documented_ceiling(self) -> bool:
        return self.reported_count > DOCUMENTED_RESULT_CEILING

    @property
    def native_truncation_detected(self) -> bool:
        return any(
            "too many matches to display" in alert.casefold() for alert in self.alerts
        )


@dataclass(frozen=True)
class OregonCalendarBatch:
    """Location, form, submitted fields, and parsed results for one search."""

    location: OregonCalendarLocation
    form: OregonCalendarSearchForm
    payload: Mapping[str, str]
    results: OregonCalendarResults


@dataclass(frozen=True)
class OregonCalendarRequest:
    """A validated selection representable by the source form."""

    mode: str
    date_after: date
    date_before: date
    categories: tuple[str, ...]
    case_number: str | None = None
    party_first_name: str | None = None
    party_last_name: str | None = None
    party_middle_name: str | None = None
    business_name: str | None = None
    attorney_first_name: str | None = None
    attorney_last_name: str | None = None
    attorney_middle_name: str | None = None
    attorney_bar_number: str | None = None
    judicial_officer: str | None = None
    exact_name: bool = False
    soundex: bool = True

    def identity_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "date_after": self.date_after.isoformat(),
            "date_before": self.date_before.isoformat(),
            "categories": list(self.categories),
            "case_number": self.case_number,
            "party_first_name": self.party_first_name,
            "party_last_name": self.party_last_name,
            "party_middle_name": self.party_middle_name,
            "business_name": self.business_name,
            "attorney_first_name": self.attorney_first_name,
            "attorney_last_name": self.attorney_last_name,
            "attorney_middle_name": self.attorney_middle_name,
            "attorney_bar_number": self.attorney_bar_number,
            "judicial_officer": self.judicial_officer,
            "exact_name": self.exact_name,
            "soundex": self.soundex,
        }


@dataclass(frozen=True)
class CursorState:
    """Opaque continuation state bound to query and ordered result identity."""

    query_fingerprint: str
    snapshot_fingerprint: str
    offset: int
    anchor: str


class OregonCalendarSelectionError(ValueError):
    """A selector or cursor cannot be represented safely."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query_selection",
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
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ValueError(f"Oregon calendar {field_name} must not be blank")
    return normalized


def _schema_error(
    message: str,
    *,
    url: str,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=url, details=details)


def _cell_lines(cell: Tag) -> list[str]:
    return [
        normalized
        for value in cell.stripped_strings
        if (normalized := _text(value)) is not None
    ]


def _nested_row_lines(cell: Tag) -> list[str]:
    nested = cell.find("table")
    if not isinstance(nested, Tag):
        return _cell_lines(cell)
    lines: list[str] = []
    for row in nested.find_all("tr", recursive=False):
        value = _text(row.get_text(" ", strip=True))
        if value is not None:
            lines.append(value)
    return lines


def parse_landing_html(html: str) -> OregonCalendarLanding:
    """Parse and validate the official location directory."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if "Oregon eCourt Circuit Court Calendars" not in page_text:
        raise _schema_error(
            "Oregon calendar landing-page identity changed",
            url=LANDING_URL,
        )
    selector = soup.select_one("select#sbxControlID2")
    if not isinstance(selector, Tag):
        raise _schema_error(
            "Oregon calendar landing page lacks its location selector",
            url=LANDING_URL,
        )

    locations: list[OregonCalendarLocation] = []
    seen_names: set[str] = set()
    seen_values: set[str] = set()
    for option in selector.find_all("option"):
        name = _text(option.get_text(" ", strip=True))
        native_value = _text(option.get("value"))
        if name is None or native_value is None:
            continue
        node_ids = tuple(
            value.strip() for value in native_value.split(",") if value.strip()
        )
        if not node_ids or any(not value.isdigit() for value in node_ids):
            raise _schema_error(
                "Oregon calendar location selector contains an invalid node ID",
                url=LANDING_URL,
                details={"location": name, "native_value": native_value},
            )
        if name.casefold() in seen_names or native_value in seen_values:
            raise _schema_error(
                "Oregon calendar location selector contains duplicate identity",
                url=LANDING_URL,
                details={"location": name, "native_value": native_value},
            )
        seen_names.add(name.casefold())
        seen_values.add(native_value)
        locations.append(
            OregonCalendarLocation(
                name=name,
                native_value=native_value,
                node_ids=node_ids,
            )
        )
    if not locations or "all locations" not in seen_names:
        raise _schema_error(
            "Oregon calendar location directory is empty or lacks statewide scope",
            url=LANDING_URL,
            details={"location_count": len(locations)},
        )

    appellate_links: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(LANDING_URL, str(anchor.get("href")))
        path = urlparse(href).path.casefold()
        if path.endswith("/coadocket"):
            appellate_links["court_of_appeals_calendar"] = href
        elif path.endswith("/sclist"):
            appellate_links["supreme_court_calendar"] = href
    if set(appellate_links) != {
        "court_of_appeals_calendar",
        "supreme_court_calendar",
    }:
        raise _schema_error(
            "Oregon calendar landing page lacks its appellate calendar routes",
            url=LANDING_URL,
            details={"observed_links": appellate_links},
        )

    notice_match = re.search(
        r"(Due to federal or state law or policy,.*?"
        r"Violence Against Women Act \(VAWA\)\.)",
        page_text,
        flags=re.IGNORECASE,
    )
    if notice_match is None:
        raise _schema_error(
            "Oregon calendar landing page lacks its coverage notice",
            url=LANDING_URL,
        )
    restriction_notice = _required_text(
        notice_match.group(1),
        "coverage notice",
    )
    schema = schema_fingerprint(
        inferred_schema([location.to_dict() for location in locations])
    )
    return OregonCalendarLanding(
        locations=tuple(locations),
        appellate_links=appellate_links,
        restriction_notice=restriction_notice,
        schema_fingerprint=schema,
    )


def _resolve_location(
    landing: OregonCalendarLanding,
    selector: str | None,
) -> OregonCalendarLocation:
    requested = _text(selector) or "All Locations"
    by_name = {location.name.casefold(): location for location in landing.locations}
    if requested.casefold() in by_name:
        return by_name[requested.casefold()]
    by_value = {location.native_value: location for location in landing.locations}
    if requested in by_value:
        return by_value[requested]
    matches = [
        location for location in landing.locations if requested in location.node_ids
    ]
    if len(matches) == 1:
        return matches[0]
    raise OregonCalendarSelectionError(
        "unknown_location",
        f"Unknown Oregon calendar location: {requested}",
        details={
            "requested": requested,
            "available_locations": [location.name for location in landing.locations],
        },
    )


def parse_search_form_html(
    html: str,
    *,
    location: OregonCalendarLocation,
) -> OregonCalendarSearchForm:
    """Parse the selected-location ASP.NET form and source constraints."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if "Oregon eCourt Circuit Court Calendars" not in page_text:
        raise _schema_error(
            "Oregon calendar search-form identity changed",
            url=SEARCH_URL,
        )
    form = soup.select_one("form#SearchParameters")
    if not isinstance(form, Tag):
        raise _schema_error(
            "Oregon calendar response lacks SearchParameters form",
            url=SEARCH_URL,
        )
    action_url = urljoin(SEARCH_URL, str(form.get("action") or ""))
    parsed_action = urlparse(action_url)
    if (
        parsed_action.path.casefold() != urlparse(SEARCH_URL).path.casefold()
        or parsed_action.query.casefold() != "id=900"
        or str(form.get("method") or "").casefold() != "post"
    ):
        raise _schema_error(
            "Oregon calendar search form action or method changed",
            url=SEARCH_URL,
            details={
                "action": action_url,
                "method": form.get("method"),
            },
        )

    hidden_fields: dict[str, str] = {}
    for field in form.select("input[type=hidden][name]"):
        hidden_fields[str(field.get("name"))] = str(field.get("value") or "")
    required_hidden = {
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "NodeID",
        "NodeDesc",
    }
    missing = sorted(required_hidden - hidden_fields.keys())
    if missing:
        raise _schema_error(
            "Oregon calendar search form lacks ASP.NET session fields",
            url=SEARCH_URL,
            details={"missing_fields": missing},
        )
    if (
        hidden_fields["NodeID"] != location.native_value
        or hidden_fields["NodeDesc"].casefold() != location.name.casefold()
    ):
        raise _schema_error(
            "Oregon calendar search form returned another location",
            url=SEARCH_URL,
            details={
                "requested_location": location.to_dict(),
                "observed_node_id": hidden_fields["NodeID"],
                "observed_node_desc": hidden_fields["NodeDesc"],
            },
        )

    search_by = form.select_one("select#SearchBy")
    if not isinstance(search_by, Tag):
        raise _schema_error(
            "Oregon calendar search form lacks Search By selector",
            url=SEARCH_URL,
        )
    search_modes = {
        str(option.get("value")): _required_text(
            option.get_text(" ", strip=True),
            "search mode",
        )
        for option in search_by.find_all("option")
        if option.get("value") is not None
    }
    for mode_id, label in EXPECTED_SEARCH_MODES.items():
        if search_modes.get(mode_id, "").casefold() != label.casefold():
            raise _schema_error(
                "Oregon calendar search modes changed",
                url=SEARCH_URL,
                details={
                    "expected_modes": EXPECTED_SEARCH_MODES,
                    "observed_modes": search_modes,
                },
            )

    officer_select = form.select_one("select#cboJudOffc")
    if not isinstance(officer_select, Tag):
        raise _schema_error(
            "Oregon calendar search form lacks judicial-officer selector",
            url=SEARCH_URL,
        )
    officers = tuple(
        OregonJudicialOfficer(
            native_id=_required_text(option.get("value"), "judicial officer ID"),
            display_name=_required_text(
                option.get_text(" ", strip=True),
                "judicial officer name",
            ),
        )
        for option in officer_select.find_all("option")
        if _text(option.get("value")) is not None
    )
    if not officers:
        raise _schema_error(
            "Oregon calendar judicial-officer directory is empty",
            url=SEARCH_URL,
        )

    script_text = "\n".join(
        str(script.string or script.get_text(" ", strip=True))
        for script in soup.find_all("script")
    )
    window_match = re.search(
        r"MaxCalendarSearchDays\s*=\s*(\d+)",
        script_text,
    )
    if window_match is None:
        raise _schema_error(
            "Oregon calendar form lacks its date-window declaration",
            url=SEARCH_URL,
        )
    observed_window = int(window_match.group(1))
    if observed_window != MAXIMUM_DATE_WINDOW_DAYS:
        raise _schema_error(
            "Oregon calendar date-window declaration changed",
            url=SEARCH_URL,
            details={
                "expected_days": MAXIMUM_DATE_WINDOW_DAYS,
                "observed_days": observed_window,
            },
        )
    forward_only = (
        "cannot be prior to today's date" in script_text
        and "day(s) in the future" in script_text
    )
    if not forward_only:
        raise _schema_error(
            "Oregon calendar forward-date validation changed",
            url=SEARCH_URL,
        )

    form_schema = {
        "hidden_fields": sorted(hidden_fields),
        "search_modes": search_modes,
        "judicial_officer_shape": (
            inferred_schema([officer.to_dict() for officer in officers])
        ),
        "maximum_date_window_days": observed_window,
        "forward_only": forward_only,
    }
    return OregonCalendarSearchForm(
        location=location,
        hidden_fields=hidden_fields,
        search_modes=search_modes,
        judicial_officers=officers,
        maximum_date_window_days=observed_window,
        forward_only=forward_only,
        schema_fingerprint=schema_fingerprint(form_schema),
    )


def _results_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table"):
        rows = table.find_all("tr", recursive=False)
        if not rows:
            continue
        first_cells = rows[0].find_all(["td", "th"], recursive=False)
        if len(first_cells) != 1:
            continue
        header_text = set(_cell_lines(first_cells[0]))
        joined = " ".join(header_text)
        if all(value in joined for value in EXPECTED_RESULT_HEADERS):
            return table
    return None


def parse_results_html(html: str) -> OregonCalendarResults:
    """Parse an authoritative calendar result or authoritative empty page."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if "Calendar Search Results" not in page_text:
        raise _schema_error(
            "Oregon calendar result-page identity changed",
            url=RESULTS_URL,
        )
    count_match = re.search(
        r"Record Count:\s*([\d,]+)",
        page_text,
        flags=re.IGNORECASE,
    )
    if count_match is None:
        raise _schema_error(
            "Oregon calendar result page lacks its record count",
            url=RESULTS_URL,
        )
    reported_count = int(count_match.group(1).replace(",", ""))

    location_match = re.search(
        r"Location\s*:\s*(.+?)\s+Help(?:\s|$)",
        page_text,
        flags=re.IGNORECASE,
    )
    if location_match is None:
        raise _schema_error(
            "Oregon calendar result page lacks selected location",
            url=RESULTS_URL,
        )
    location_name = _required_text(
        location_match.group(1),
        "result location",
    )

    form = soup.select_one("form#SearchParameters")
    if not isinstance(form, Tag):
        raise _schema_error(
            "Oregon calendar result page lacks replay parameters",
            url=RESULTS_URL,
        )
    form_action = urljoin(RESULTS_URL, str(form.get("action") or ""))
    if urlparse(form_action).path.casefold() != urlparse(RESULTS_URL).path.casefold():
        raise _schema_error(
            "Oregon calendar result replay action changed",
            url=RESULTS_URL,
            details={"action": form_action},
        )
    request_parameters = {
        str(field.get("name")): str(field.get("value") or "")
        for field in form.select("input[name]")
    }

    table = _results_table(soup)
    if not isinstance(table, Tag):
        raise _schema_error(
            "Oregon calendar result table is missing",
            url=RESULTS_URL,
        )
    direct_rows = table.find_all("tr", recursive=False)
    rows: list[OregonCalendarHearing] = []
    alerts: list[str] = []
    empty_message = False
    for index, row in enumerate(direct_rows[1:]):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 1:
            message = _text(cells[0].get_text(" ", strip=True))
            if message and "No cases matched" in message:
                empty_message = True
                continue
            if message and "too many matches to display" in message.casefold():
                alerts.append(message.strip("- "))
                continue
        if len(cells) != 4:
            raise _schema_error(
                "Oregon calendar result row width changed",
                url=RESULTS_URL,
                details={
                    "row_index": index,
                    "cell_count": len(cells),
                },
            )

        case_lines = _nested_row_lines(cells[0])
        judge_lines = _nested_row_lines(cells[2])
        hearing_lines = _nested_row_lines(cells[3])
        if not case_lines or len(hearing_lines) < 3:
            raise _schema_error(
                "Oregon calendar result row lacks required hearing fields",
                url=RESULTS_URL,
                details={
                    "row_index": index,
                    "case_lines": case_lines,
                    "hearing_lines": hearing_lines,
                },
            )
        caption_lines = _cell_lines(cells[1])
        caption = "\n".join(caption_lines)
        if not caption:
            raise _schema_error(
                "Oregon calendar result row lacks case style",
                url=RESULTS_URL,
                details={"row_index": index},
            )
        status_icons = tuple(
            value
            for image in cells[0].find_all("img")
            if (value := _text(image.get("alt"))) is not None
        )
        rows.append(
            OregonCalendarHearing(
                case_number=_required_text(case_lines[0], "case number"),
                case_type=_text(case_lines[1] if len(case_lines) > 1 else None),
                caption=caption,
                judge=_text(judge_lines[0] if judge_lines else None),
                physical_location=_text(
                    judge_lines[1] if len(judge_lines) > 1 else None
                ),
                hearing_date=_required_text(
                    hearing_lines[0],
                    "hearing date",
                ),
                hearing_time=_text(hearing_lines[1]),
                hearing_type=_required_text(
                    " ".join(hearing_lines[2:]),
                    "hearing type",
                ),
                status_icons=status_icons,
            )
        )

    if reported_count == 0 and not empty_message:
        raise _schema_error(
            "Oregon calendar zero-result response lacks its empty marker",
            url=RESULTS_URL,
        )
    if reported_count != len(rows):
        raise _schema_error(
            "Oregon calendar record count does not match parsed rows",
            url=RESULTS_URL,
            details={
                "reported_count": reported_count,
                "parsed_rows": len(rows),
            },
        )
    schema_seed: Sequence[Mapping[str, Any]]
    if rows:
        schema_seed = [row.to_dict() for row in rows]
    else:
        schema_seed = [
            {
                "case_number": "",
                "case_type": None,
                "caption": "",
                "judge": None,
                "physical_location": None,
                "hearing_date": "",
                "hearing_time": None,
                "hearing_type": "",
                "status_icons": [],
            }
        ]
    return OregonCalendarResults(
        location_name=location_name,
        rows=tuple(rows),
        reported_count=reported_count,
        request_parameters=request_parameters,
        schema_fingerprint=schema_fingerprint(inferred_schema(schema_seed)),
        alerts=tuple(alerts),
    )


def _checked_html(response: Any, *, url: str) -> str:
    status_code = int(getattr(response, "status_code", 0))
    text = getattr(response, "text", "")
    body = text if isinstance(text, str) else str(text)
    if status_code == 429:
        raise RateLimitedHTTPError(status_code, url=url, response_text=body)
    if status_code in {401, 403}:
        raise RestrictedHTTPError(status_code, url=url, response_text=body)
    if status_code == 451:
        raise TermsBlockedHTTPError(status_code, url=url, response_text=body)
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(status_code, url=url, response_text=body)
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(status_code, url=url, response_text=body)
    headers = getattr(response, "headers", {})
    content_type = ""
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).casefold() == "content-type":
                content_type = str(value).casefold()
                break
    if content_type and "html" not in content_type:
        raise _schema_error(
            "Oregon calendar returned a non-HTML response",
            url=url,
            details={"content_type": content_type},
        )
    return body


def _oregon_today() -> date:
    return datetime.now(ZoneInfo("America/Los_Angeles")).date()


def _resolve_officer(
    form: OregonCalendarSearchForm,
    selector: str,
) -> OregonJudicialOfficer:
    requested = _required_text(selector, "judicial officer selector")
    matches = [
        officer
        for officer in form.judicial_officers
        if officer.native_id == requested
        or officer.display_name.casefold() == requested.casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    raise OregonCalendarSelectionError(
        "unknown_judicial_officer",
        f"Unknown Oregon calendar judicial officer: {requested}",
        details={"requested": requested},
    )


def _source_date(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def _build_search_payload(
    form: OregonCalendarSearchForm,
    request: OregonCalendarRequest,
) -> dict[str, str]:
    payload = dict(form.hidden_fields)
    category_codes = ",".join(
        CATEGORY_CODES[category][0] for category in request.categories
    )
    payload.update(
        {
            "CaseStatusType": "0",
            "DateSettingOnAfter": _source_date(request.date_after),
            "DateSettingOnBefore": _source_date(request.date_before),
            "StatusType": "true",
            "AllStatusTypes": "true",
            "CaseCategories": category_codes,
            "SearchSubmit": "Search",
        }
    )
    for category in request.categories:
        _, date_field, judge_field = CATEGORY_CODES[category]
        payload[date_field] = "on"
        payload[judge_field] = "on"
    if request.exact_name:
        payload["ExactName"] = "on"
    if request.soundex:
        payload["UseSoundex"] = "on"

    if request.mode == "date_range":
        payload.update(
            {
                "SearchBy": "5",
                "SearchType": "DATERANGE",
                "SearchMode": "DATERANGE",
                "NameTypeKy": "",
                "BaseConnKy": "",
            }
        )
    elif request.mode == "case":
        payload.update(
            {
                "SearchBy": "0",
                "SearchType": "CASE",
                "SearchMode": "CASENUMBER",
                "CourtCaseSearchValue": request.case_number or "",
                "NameTypeKy": "",
                "BaseConnKy": "",
            }
        )
    elif request.mode == "party":
        payload.update(
            {
                "SearchBy": "1",
                "SearchType": "PARTY",
                "SearchMode": "NAME",
                "NameTypeKy": "ALIAS",
                "BaseConnKy": "DF",
                "LastName": request.party_last_name or "",
                "FirstName": request.party_first_name or "",
                "MiddleName": request.party_middle_name or "",
                "RequireFirstName": "True",
            }
        )
    elif request.mode == "business":
        payload.update(
            {
                "SearchBy": "1",
                "SearchType": "PARTY",
                "SearchMode": "BUSINESSNAME",
                "NameTypeKy": "DBA",
                "BaseConnKy": "DF",
                "LastName": request.business_name or "",
                "FirstName": "",
                "MiddleName": "",
            }
        )
    elif request.mode == "attorney":
        payload.update(
            {
                "SearchBy": "2",
                "SearchType": "PARTY",
                "SearchMode": "NAME",
                "NameTypeKy": "ALIAS",
                "BaseConnKy": "AT",
                "LastName": request.attorney_last_name or "",
                "FirstName": request.attorney_first_name or "",
                "MiddleName": request.attorney_middle_name or "",
                "RequireFirstName": "True",
            }
        )
    elif request.mode == "attorney_bar":
        payload.update(
            {
                "SearchBy": "2",
                "SearchType": "PARTY",
                "SearchMode": "BARNUMBER",
                "NameTypeKy": "ALIAS",
                "BaseConnKy": "AT",
                "LastName": request.attorney_bar_number or "",
                "FirstName": "",
                "MiddleName": "",
            }
        )
    elif request.mode == "judicial_officer":
        officer = _resolve_officer(form, request.judicial_officer or "")
        payload.update(
            {
                "SearchBy": "3",
                "SearchType": "JUDOFFC",
                "SearchMode": "JUDOFFC",
                "NameTypeKy": "",
                "BaseConnKy": "",
                "cboJudOffc": officer.native_id,
            }
        )
    else:
        raise OregonCalendarSelectionError(
            "unsupported_search_mode",
            f"Unsupported Oregon calendar search mode: {request.mode}",
        )
    return payload


class OregonCourtCalendarClient:
    """Same-session client for Oregon's Tyler PublicAccess calendar."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = 30.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
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

    def _get(self, url: str) -> str:
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TransportError(
                "Oregon calendar GET failed",
                url=url,
                details={"error": str(error)},
            ) from error
        return _checked_html(response, url=url)

    def _post(
        self,
        url: str,
        payload: Mapping[str, str],
        *,
        referer: str,
    ) -> str:
        try:
            response = self.session.post(
                url,
                data=dict(payload),
                headers={**self.headers, "Referer": referer},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TransportError(
                "Oregon calendar POST failed",
                url=url,
                details={"error": str(error)},
            ) from error
        return _checked_html(response, url=url)

    def landing(self) -> OregonCalendarLanding:
        return parse_landing_html(self._get(LANDING_URL))

    def open_search(
        self,
        location: OregonCalendarLocation,
    ) -> OregonCalendarSearchForm:
        html = self._post(
            SEARCH_URL,
            {
                "NodeID": location.native_value,
                "NodeDesc": location.name,
            },
            referer=LANDING_URL,
        )
        return parse_search_form_html(html, location=location)

    def directory(
        self,
        *,
        location_selector: str | None,
    ) -> tuple[
        OregonCalendarLanding,
        OregonCalendarLocation,
        OregonCalendarSearchForm,
    ]:
        landing = self.landing()
        location = _resolve_location(landing, location_selector)
        return landing, location, self.open_search(location)

    def search(
        self,
        *,
        location_selector: str | None,
        request: OregonCalendarRequest,
    ) -> OregonCalendarBatch:
        landing = self.landing()
        location = _resolve_location(landing, location_selector)
        form = self.open_search(location)
        payload = _build_search_payload(form, request)
        results = parse_results_html(
            self._post(
                SEARCH_URL,
                payload,
                referer=SEARCH_URL,
            )
        )
        if results.location_name.casefold() != location.name.casefold():
            raise _schema_error(
                "Oregon calendar results belong to another location",
                url=RESULTS_URL,
                details={
                    "requested_location": location.name,
                    "result_location": results.location_name,
                },
            )
        return OregonCalendarBatch(
            location=location,
            form=form,
            payload=payload,
            results=results,
        )

    def probe(
        self,
        *,
        location_selector: str | None,
    ) -> tuple[OregonCalendarLanding, OregonCalendarBatch]:
        today = _oregon_today()
        request = OregonCalendarRequest(
            mode="date_range",
            date_after=today,
            date_before=today,
            categories=tuple(CATEGORY_CODES),
        )
        landing = self.landing()
        location = _resolve_location(landing, location_selector)
        form = self.open_search(location)
        payload = _build_search_payload(form, request)
        results = parse_results_html(
            self._post(SEARCH_URL, payload, referer=SEARCH_URL)
        )
        if results.location_name.casefold() != location.name.casefold():
            raise _schema_error(
                "Oregon calendar probe returned another location",
                url=RESULTS_URL,
            )
        return (
            landing,
            OregonCalendarBatch(
                location=location,
                form=form,
                payload=payload,
                results=results,
            ),
        )


def _parse_iso_date(value: str | None, field_name: str) -> date | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError as error:
        raise OregonCalendarSelectionError(
            "invalid_date",
            f"{field_name} must be an ISO calendar date",
            details={"field": field_name, "value": normalized},
        ) from error


def _search_request(args: argparse.Namespace) -> OregonCalendarRequest:
    date_after = _parse_iso_date(getattr(args, "date_after", None), "--after")
    date_before = _parse_iso_date(getattr(args, "date_before", None), "--before")
    if date_after is None and date_before is None:
        date_after = date_before = _oregon_today()
    elif date_after is None:
        date_after = date_before
    elif date_before is None:
        date_before = date_after
    assert date_after is not None and date_before is not None
    if date_before < date_after:
        raise OregonCalendarSelectionError(
            "invalid_date_range",
            "--before must not precede --after",
            details={
                "date_after": date_after.isoformat(),
                "date_before": date_before.isoformat(),
            },
        )
    window_days = (date_before - date_after).days + 1
    if window_days > MAXIMUM_DATE_WINDOW_DAYS:
        raise OregonCalendarSelectionError(
            "date_range_exceeds_source_window",
            "The source form accepts at most a 90-day inclusive date interval",
            details={
                "date_after": date_after.isoformat(),
                "date_before": date_before.isoformat(),
                "requested_window_days": window_days,
                "source_maximum_days": MAXIMUM_DATE_WINDOW_DAYS,
            },
        )
    today = _oregon_today()
    if date_after < today:
        raise OregonCalendarSelectionError(
            "date_range_precedes_source_window",
            "The source form does not accept a start date before today",
            details={
                "date_after": date_after.isoformat(),
                "source_today": today.isoformat(),
            },
        )
    maximum_end = today + timedelta(days=MAXIMUM_FORWARD_DATE_WINDOW_DAYS - 1)
    if date_before > maximum_end:
        raise OregonCalendarSelectionError(
            "date_range_exceeds_forward_window",
            "The source form does not accept an end date beyond its "
            "90-day forward window",
            details={
                "date_before": date_before.isoformat(),
                "source_today": today.isoformat(),
                "maximum_end_date": maximum_end.isoformat(),
                "source_maximum_days": (MAXIMUM_FORWARD_DATE_WINDOW_DAYS),
            },
        )

    categories = tuple(
        dict.fromkeys(getattr(args, "categories", None) or tuple(CATEGORY_CODES))
    )
    unknown_categories = sorted(set(categories) - CATEGORY_CODES.keys())
    if unknown_categories:
        raise OregonCalendarSelectionError(
            "unknown_case_category",
            "Unknown Oregon calendar case category",
            details={"unknown_categories": unknown_categories},
        )

    case_number = _text(getattr(args, "case_number", None))
    party_first = _text(getattr(args, "party_first_name", None))
    party_last = _text(getattr(args, "party_last_name", None))
    party_middle = _text(getattr(args, "party_middle_name", None))
    business_name = _text(getattr(args, "business_name", None))
    attorney_first = _text(getattr(args, "attorney_first_name", None))
    attorney_last = _text(getattr(args, "attorney_last_name", None))
    attorney_middle = _text(getattr(args, "attorney_middle_name", None))
    attorney_bar = _text(getattr(args, "attorney_bar_number", None))
    officer = _text(getattr(args, "judicial_officer", None))

    selectors = {
        "case": case_number is not None,
        "party": party_first is not None or party_last is not None,
        "business": business_name is not None,
        "attorney": attorney_first is not None or attorney_last is not None,
        "attorney_bar": attorney_bar is not None,
        "judicial_officer": officer is not None,
    }
    selected = [name for name, present in selectors.items() if present]
    if len(selected) > 1:
        raise OregonCalendarSelectionError(
            "multiple_search_modes",
            "The source form accepts one search mode at a time",
            details={"selected_modes": selected},
        )
    if selectors["party"] and (party_first is None or party_last is None):
        raise OregonCalendarSelectionError(
            "incomplete_party_name",
            "The source calendar requires first and last name for person search",
        )
    if selectors["attorney"] and (attorney_first is None or attorney_last is None):
        raise OregonCalendarSelectionError(
            "incomplete_attorney_name",
            "The source calendar requires first and last name for attorney search",
        )
    mode = selected[0] if selected else "date_range"
    return OregonCalendarRequest(
        mode=mode,
        date_after=date_after,
        date_before=date_before,
        categories=categories,
        case_number=case_number,
        party_first_name=party_first,
        party_last_name=party_last,
        party_middle_name=party_middle,
        business_name=business_name,
        attorney_first_name=attorney_first,
        attorney_last_name=attorney_last,
        attorney_middle_name=attorney_middle,
        attorney_bar_number=attorney_bar,
        judicial_officer=officer,
        exact_name=bool(getattr(args, "exact_name", False)),
        soundex=bool(getattr(args, "soundex", True)),
    )


def _event_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"Oregon calendar hearing has unparseable date {value!r}"
        ) from error


def _event_time(value: str | None) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for pattern in ("%I:%M %p", "%I %p"):
        try:
            return (
                datetime.strptime(
                    normalized.upper(),
                    pattern,
                )
                .time()
                .isoformat()
            )
        except ValueError:
            continue
    raise ValueError(f"Oregon calendar hearing has unparseable time {normalized!r}")


def _court_payload(location: OregonCalendarLocation) -> dict[str, Any]:
    name = (
        "Oregon Circuit and Tax Court Calendar"
        if location.court_level == "circuit_and_tax"
        else (
            "Oregon Tax Court"
            if location.court_level == "tax"
            else f"{location.name} County Circuit Court"
        )
    )
    return {
        "court_id": location.court_id,
        "native_court_id": location.native_value,
        "name": name,
        "state_code": STATE_CODE,
        "county_geoid": location.county_geoid,
        "court_level": location.court_level,
        "official_url": LANDING_URL,
    }


def _source_scope(results: OregonCalendarResults) -> dict[str, Any]:
    return {
        "record_type": "hearing_calendar",
        "fields": [
            "case_number",
            "case_type",
            "caption",
            "judge",
            "physical_location",
            "hearing_date",
            "hearing_time",
            "hearing_type",
            "status_icons",
        ],
        "documented_result_ceiling": DOCUMENTED_RESULT_CEILING,
        "live_observed_returned_rows": LIVE_OBSERVED_RETURNED_ROWS,
        "maximum_forward_date_window_days": (MAXIMUM_FORWARD_DATE_WINDOW_DAYS),
        "maximum_date_window_days": MAXIMUM_DATE_WINDOW_DAYS,
        "forward_only": True,
        "past_dates_available": False,
        "observed_result_count": results.reported_count,
        "documented_ceiling_reached": results.documented_ceiling_reached,
        "native_truncation_detected": results.native_truncation_detected,
        "source_alerts": list(results.alerts),
        "live_response_exceeded_documented_ceiling": (
            results.exceeds_documented_ceiling
        ),
        "complementary_official_routes": list(COMPLEMENTARY_OFFICIAL_ROUTES),
    }


def _hearing_entry(
    row: OregonCalendarHearing,
    *,
    location: OregonCalendarLocation,
) -> dict[str, Any]:
    event_date = _event_date(row.hearing_date)
    event_time = _event_time(row.hearing_time)
    identity_basis = {
        "court_location": location.native_value,
        "case_number": row.case_number.casefold(),
        "event_date": event_date,
        "event_time": event_time or "",
        "hearing_type": row.hearing_type.casefold(),
    }
    digest = hashlib.sha256(canonical_json(identity_basis).encode("utf-8")).hexdigest()
    native_status = ", ".join(row.status_icons) or None
    return {
        "native_entry_id": f"calendar-hearing:{digest}",
        "identity_kind": "source_fields_sha256",
        "identity_basis": identity_basis,
        "event_code": "HEARING",
        "event_type": "hearing",
        "raw_text": row.hearing_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "source_event_date_raw": row.hearing_date,
        "source_event_time_raw": row.hearing_time,
        "location": row.physical_location,
        "judge": row.judge,
        "status": native_status,
        "native_status": native_status,
        "status_icons": list(row.status_icons),
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def normalize_cases(batch: OregonCalendarBatch) -> list[dict[str, Any]]:
    """Group hearing rows into ingestible case records."""

    grouped: dict[str, list[OregonCalendarHearing]] = {}
    for row in batch.results.rows:
        grouped.setdefault(row.case_number.casefold(), []).append(row)

    records: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = grouped[key]
        raw_case_number = sorted(
            {row.case_number for row in rows},
            key=lambda value: (value.casefold(), value),
        )[0]
        captions = sorted(
            {row.caption for row in rows},
            key=lambda value: (value.casefold(), value),
        )
        case_types = sorted(
            {row.case_type for row in rows if row.case_type},
            key=lambda value: (value.casefold(), value),
        )
        entry_groups: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            entry = _hearing_entry(row, location=batch.location)
            base_id = entry["native_entry_id"]
            raw_fingerprint = sha256_fingerprint(entry["raw"])
            entry_groups.setdefault(base_id, {})[raw_fingerprint] = entry
        entries_by_id: dict[str, dict[str, Any]] = {}
        for base_id, variants in entry_groups.items():
            if len(variants) == 1:
                entries_by_id[base_id] = next(iter(variants.values()))
                continue
            for variant_fingerprint, entry in variants.items():
                variant_id = f"{base_id}:variant:{variant_fingerprint}"
                entry["native_entry_id"] = variant_id
                entry["identity_kind"] = "source_stable_fields_with_variant_sha256"
                entry["variant_basis"] = {
                    "raw_row_sha256": variant_fingerprint,
                }
                entries_by_id[variant_id] = entry
        entries = sorted(
            entries_by_id.values(),
            key=lambda entry: (
                entry["event_date"],
                entry["event_time"] or "",
                (entry["location"] or "").casefold(),
                (entry["judge"] or "").casefold(),
                entry["raw_text"].casefold(),
                entry["native_entry_id"],
            ),
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    batch.location.court_id,
                    raw_case_number,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "case",
                "court": _court_payload(batch.location),
                "raw_case_number": raw_case_number,
                "display_case_number": raw_case_number,
                "source_internal_id": None,
                "caption": captions[0],
                "caption_variants": captions,
                "case_type": case_types[0] if case_types else None,
                "case_type_variants": case_types,
                "filing_date": None,
                "status": None,
                "access_state": "public",
                "certified_record": False,
                "source_url": LANDING_URL,
                "parties": [],
                "docket_entries": entries,
                "documents": [],
                "source_scope": _source_scope(batch.results),
                "search_metadata": {
                    "location": batch.location.to_dict(),
                    "request_parameters": dict(batch.results.request_parameters),
                    "submitted_search_fields": {
                        key: value
                        for key, value in batch.payload.items()
                        if key
                        not in {
                            "__VIEWSTATE",
                            "__VIEWSTATEGENERATOR",
                            "__EVENTVALIDATION",
                        }
                    },
                    "source_total_hearings": batch.results.reported_count,
                    "source_total_cases": len(grouped),
                },
                "schema_fingerprint": batch.results.schema_fingerprint,
                "raw": {
                    "hearing_rows": [
                        row.to_dict()
                        for row in sorted(
                            rows,
                            key=lambda value: (
                                _event_date(value.hearing_date),
                                _event_time(value.hearing_time) or "",
                                (value.physical_location or "").casefold(),
                                (value.judge or "").casefold(),
                                value.hearing_type.casefold(),
                            ),
                        )
                    ]
                },
            }
        )
    return records


def _location_record(
    location: OregonCalendarLocation,
    *,
    landing: OregonCalendarLanding,
) -> dict[str, Any]:
    return {
        "canonical_ref": (
            f"ORCOURT-CALENDAR-LOCATION:{sha256_fingerprint(location.to_dict())}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "court_calendar_location",
        "source_url": LANDING_URL,
        "location": location.to_dict(),
        "court": _court_payload(location),
        "appellate_calendar_links": dict(landing.appellate_links),
        "complementary_official_routes": list(COMPLEMENTARY_OFFICIAL_ROUTES),
        "schema_fingerprint": landing.schema_fingerprint,
    }


def _officer_record(
    officer: OregonJudicialOfficer,
    *,
    location: OregonCalendarLocation,
    form: OregonCalendarSearchForm,
) -> dict[str, Any]:
    return {
        "canonical_ref": (f"ORCOURT-JUDICIAL-OFFICER:{officer.native_id}"),
        "source_id": SOURCE_ID,
        "record_kind": "judicial_officer",
        "source_url": SEARCH_URL,
        "native_officer_id": officer.native_id,
        "display_name": officer.display_name,
        "selected_location": location.to_dict(),
        "directory_scope": "source_search_selector",
        "schema_fingerprint": form.schema_fingerprint,
        "raw": officer.to_dict(),
    }


def _probe_record(
    landing: OregonCalendarLanding,
    batch: OregonCalendarBatch,
) -> dict[str, Any]:
    return {
        "canonical_ref": (f"ORCOURT-CALENDAR-PROBE:{batch.location.court_id}"),
        "source_id": SOURCE_ID,
        "record_kind": "probe",
        "source_url": LANDING_URL,
        "location": batch.location.to_dict(),
        "checks": {
            "anonymous_cookie_handshake": True,
            "location_directory_count": len(landing.locations),
            "search_modes": dict(batch.form.search_modes),
            "judicial_officer_count": len(batch.form.judicial_officers),
            "maximum_date_window_days": (batch.form.maximum_date_window_days),
            "maximum_forward_date_window_days": (batch.form.maximum_date_window_days),
            "forward_only": batch.form.forward_only,
            "result_table": True,
            "reported_result_count": batch.results.reported_count,
            "parsed_result_count": len(batch.results.rows),
            "documented_result_ceiling": DOCUMENTED_RESULT_CEILING,
            "live_observed_returned_rows": LIVE_OBSERVED_RETURNED_ROWS,
            "native_truncation_detected": (batch.results.native_truncation_detected),
            "source_alerts": list(batch.results.alerts),
            "live_response_exceeded_documented_ceiling": (
                batch.results.exceeds_documented_ceiling
            ),
        },
        "request_parameters": dict(batch.results.request_parameters),
        "appellate_calendar_links": dict(landing.appellate_links),
        "complementary_official_routes": list(COMPLEMENTARY_OFFICIAL_ROUTES),
        "coverage_notice": landing.restriction_notice,
        "schema_fingerprints": {
            "landing": landing.schema_fingerprint,
            "form": batch.form.schema_fingerprint,
            "results": batch.results.schema_fingerprint,
        },
    }


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source_id": SOURCE_ID,
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
        raise OregonCalendarSelectionError(
            "invalid_cursor",
            "Oregon calendar cursor has an unknown prefix",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise OregonCalendarSelectionError(
            "invalid_cursor",
            "Oregon calendar cursor is malformed",
        ) from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or payload.get("source_id") != SOURCE_ID
        or not isinstance(payload.get("q"), str)
        or not isinstance(payload.get("snapshot"), str)
        or not isinstance(payload.get("anchor"), str)
        or isinstance(payload.get("offset"), bool)
        or not isinstance(payload.get("offset"), int)
        or payload["offset"] <= 0
    ):
        raise OregonCalendarSelectionError(
            "invalid_cursor",
            "Oregon calendar cursor fields are invalid",
        )
    return CursorState(
        query_fingerprint=payload["q"],
        snapshot_fingerprint=payload["snapshot"],
        offset=payload["offset"],
        anchor=payload["anchor"],
    )


def _identity_snapshot(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_fingerprint(
        [
            {
                "case": record.get("canonical_ref"),
                "hearings": [
                    entry.get("native_entry_id")
                    for entry in record.get("docket_entries", [])
                ],
            }
            for record in records
        ]
    )


def _paginate_records(
    records: Sequence[Mapping[str, Any]],
    *,
    query_identity: Mapping[str, Any],
    limit: int | None,
    cursor_value: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise OregonCalendarSelectionError(
            "invalid_limit",
            "Oregon calendar result limit must be a positive integer",
        )
    query_fingerprint = sha256_fingerprint(query_identity)
    snapshot_fingerprint = _identity_snapshot(records)
    cursor = _decode_cursor(cursor_value)
    offset = 0
    if cursor is not None:
        if cursor.query_fingerprint != query_fingerprint:
            raise OregonCalendarSelectionError(
                "cursor_query_mismatch",
                "Oregon calendar cursor belongs to another query",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        if cursor.snapshot_fingerprint != snapshot_fingerprint:
            raise OregonCalendarSelectionError(
                "cursor_snapshot_changed",
                "Oregon calendar results changed since the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
                details={
                    "cursor_snapshot": cursor.snapshot_fingerprint,
                    "current_snapshot": snapshot_fingerprint,
                },
            )
        offset = cursor.offset
        if offset >= len(records):
            raise OregonCalendarSelectionError(
                "cursor_offset_out_of_range",
                "Oregon calendar cursor is beyond the current result set",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        previous = records[offset - 1] if offset else None
        if (
            not isinstance(previous, Mapping)
            or previous.get("canonical_ref") != cursor.anchor
        ):
            raise OregonCalendarSelectionError(
                "cursor_anchor_changed",
                "Oregon calendar cursor boundary no longer matches",
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
                query_fingerprint=query_fingerprint,
                snapshot_fingerprint=snapshot_fingerprint,
                offset=end,
                anchor=anchor,
            )
        )
    return selected, next_cursor


def _raw_query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in (
        "location",
        "date_after",
        "date_before",
        "categories",
        "case_number",
        "party_first_name",
        "party_last_name",
        "party_middle_name",
        "business_name",
        "attorney_first_name",
        "attorney_last_name",
        "attorney_middle_name",
        "attorney_bar_number",
        "judicial_officer",
        "exact_name",
        "soundex",
    ):
        if hasattr(args, name):
            value = getattr(args, name)
            if value is not None:
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
    *,
    request: OregonCalendarRequest | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    parameters = (
        {
            "location": getattr(args, "location", None) or "All Locations",
            **request.identity_payload(),
        }
        if request is not None
        else _raw_query_parameters(args)
    )
    raw_limit = getattr(args, "limit", None)
    requested_limit = (
        raw_limit
        if isinstance(raw_limit, int)
        and not isinstance(raw_limit, bool)
        and raw_limit > 0
        else None
    )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Oregon",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
            metadata={
                "access_decision": _decision_metadata(access_decision),
            },
        ),
    )


def _default_access_decision() -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "allowed": True,
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
        "limits": {
            "maximum_forward_date_window_days": (MAXIMUM_FORWARD_DATE_WINDOW_DAYS),
            "maximum_date_window_days": MAXIMUM_DATE_WINDOW_DAYS,
        },
    }


def _access_failure(
    query: PublicRecordsQuery,
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
                    decision.get("reason_code") or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Oregon calendar acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _access_mismatch(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="catalog_decision_source_mismatch",
                message="Access decision belongs to another source component",
                category="access",
                retryable=False,
                details={
                    "decision_source_id": decision.get("source_id"),
                    "query_source_id": SOURCE_ID,
                },
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: OregonCalendarSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _result_warnings(results: OregonCalendarResults) -> tuple[str, ...]:
    warnings = list(SOURCE_WARNINGS)
    warnings.extend(f"Source alert: {alert}" for alert in results.alerts)
    if results.exceeds_documented_ceiling:
        warnings.append(
            f"The live response returned {results.reported_count} rows, "
            f"exceeding the documented {DOCUMENTED_RESULT_CEILING}-result "
            "display ceiling; all rows returned by the source were preserved."
        )
    return tuple(warnings)


def _calendar_result(
    query: PublicRecordsQuery,
    batch: OregonCalendarBatch,
    *,
    request: OregonCalendarRequest,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsResult:
    records = normalize_cases(batch)
    selected, next_cursor = _paginate_records(
        records,
        query_identity={
            "source_id": SOURCE_ID,
            "operation": "search",
            "location": batch.location.to_dict(),
            "request": request.identity_payload(),
        },
        limit=limit,
        cursor_value=cursor,
    )
    warnings = _result_warnings(batch.results)
    if (
        batch.results.documented_ceiling_reached
        or batch.results.native_truncation_detected
    ):
        explicit_truncation = batch.results.native_truncation_detected
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code=(
                        "source_result_truncation_detected"
                        if explicit_truncation
                        else "documented_source_result_ceiling_reached"
                    ),
                    message=(
                        "The source explicitly reported too many matches to display"
                        if explicit_truncation
                        else (
                            "The response is exactly the OJD guide's "
                            "documented 400-result display ceiling"
                        )
                    ),
                    category="completeness",
                    retryable=False,
                    details={
                        "documented_result_ceiling": (DOCUMENTED_RESULT_CEILING),
                        "observed_result_count": (batch.results.reported_count),
                        "source_alerts": list(batch.results.alerts),
                        "explicit_source_truncation": explicit_truncation,
                        "partition_hints": [
                            "narrow location",
                            "use one-day date slices",
                            "split case categories",
                            "use judicial-officer searches",
                        ],
                    },
                )
            ],
            records=selected,
            next_cursor=next_cursor,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
        warnings=warnings,
    )


def _execute_command(
    args: argparse.Namespace,
    client: OregonCourtCalendarClient | Any,
    query: PublicRecordsQuery,
    *,
    request: OregonCalendarRequest | None,
) -> PublicRecordsResult:
    command = args.command
    if command == "locations":
        landing = client.landing()
        records = [
            _location_record(location, landing=landing)
            for location in landing.locations
        ]
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )

    if command == "judicial-officers":
        _, location, form = client.directory(
            location_selector=getattr(args, "location", None)
        )
        records = [
            _officer_record(
                officer,
                location=location,
                form=form,
            )
            for officer in sorted(
                form.judicial_officers,
                key=lambda value: (
                    value.display_name.casefold(),
                    value.native_id,
                ),
            )
        ]
        selected, next_cursor = _paginate_records(
            records,
            query_identity={
                "source_id": SOURCE_ID,
                "operation": command,
                "location": location.to_dict(),
            },
            limit=getattr(args, "limit", None),
            cursor_value=getattr(args, "cursor", None),
        )
        return PublicRecordsResult.success(
            query,
            selected,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )

    if command == "search":
        assert request is not None
        batch = client.search(
            location_selector=getattr(args, "location", None),
            request=request,
        )
        return _calendar_result(
            query,
            batch,
            request=request,
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        )

    if command == "probe":
        landing, batch = client.probe(location_selector=getattr(args, "location", None))
        record = _probe_record(landing, batch)
        warnings = _result_warnings(batch.results)
        if (
            batch.results.documented_ceiling_reached
            or batch.results.native_truncation_detected
        ):
            explicit_truncation = batch.results.native_truncation_detected
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [
                    PublicRecordsError(
                        code=(
                            "source_result_truncation_detected"
                            if explicit_truncation
                            else "documented_source_result_ceiling_reached"
                        ),
                        message=(
                            "The source explicitly reported too many matches "
                            "to display"
                            if explicit_truncation
                            else (
                                "The probe response is exactly the OJD "
                                "guide's documented 400-result display "
                                "ceiling"
                            )
                        ),
                        category="completeness",
                        retryable=False,
                        details={
                            "documented_result_ceiling": (
                                DOCUMENTED_RESULT_CEILING
                            ),
                            "observed_result_count": (
                                batch.results.reported_count
                            ),
                            "source_alerts": list(batch.results.alerts),
                            "explicit_source_truncation": (
                                explicit_truncation
                            ),
                        },
                    )
                ],
                records=[record],
                warnings=warnings,
            )
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=warnings,
        )
    raise ValueError(f"unsupported Oregon calendar command: {command}")


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
    except Exception:
        pass


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: OregonCourtCalendarClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Oregon calendar operation with injectable source access."""

    decision = (
        dict(access_decision)
        if access_decision is not None
        else _default_access_decision()
    )
    request: OregonCalendarRequest | None = None
    selection_error: OregonCalendarSelectionError | None = None
    raw_limit = getattr(args, "limit", None)
    if raw_limit is not None and (
        isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or raw_limit <= 0
    ):
        selection_error = OregonCalendarSelectionError(
            "invalid_limit",
            "Oregon calendar result limit must be a positive integer",
        )
    if args.command == "search":
        try:
            request = _search_request(args)
        except OregonCalendarSelectionError as error:
            if selection_error is None:
                selection_error = error
    query = build_query(
        args,
        request=request,
        access_decision=decision,
    )

    decision_source = decision.get("source_id")
    if decision_source is not None and decision_source != SOURCE_ID:
        result = _access_mismatch(query, decision)
        if log_results:
            _best_effort_log(query, result)
        return result
    if not decision.get("allowed", False):
        result = _access_failure(query, decision)
        if log_results:
            _best_effort_log(query, result)
        return result
    if selection_error is not None:
        result = _selection_failure(query, selection_error)
        if log_results:
            _best_effort_log(query, result)
        return result

    source_client = client or OregonCourtCalendarClient(
        timeout=float(getattr(args, "timeout", 30.0))
    )
    owns_client = client is None
    try:
        result = _execute_command(
            args,
            source_client,
            query,
            request=request,
        )
    except OregonCalendarSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
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
        _best_effort_log(query, result)
    return result


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
    *,
    output_writer: Callable[..., bool] = write_output,
) -> None:
    payload = result.to_dict()
    if output_writer(
        payload,
        args,
        summary=f"Oregon court calendar {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Oregon court calendar {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        kind = record.get("record_kind")
        if kind == "case":
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{len(record.get('docket_entries') or [])} hearing(s) | "
                f"{record.get('caption') or '?'}"
            )
        elif kind == "court_calendar_location":
            print(f"  {record['location']['name']}")
        elif kind == "judicial_officer":
            print(f"  {record.get('native_officer_id')} | {record.get('display_name')}")
        else:
            print(
                f"  probe | {record.get('checks', {}).get('parsed_result_count')} rows"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    add_output_args(parser)


def _add_location(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--location",
        default="All Locations",
        help="Official location label or native node ID",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query Oregon's official Circuit and Tax Court hearing calendar")
    )
    sub = parser.add_subparsers(dest="command", required=True)

    locations = sub.add_parser(
        "locations",
        help="List official Circuit and Tax Court calendar locations",
    )
    _add_common(locations)

    officers = sub.add_parser(
        "judicial-officers",
        help="List the source-native judicial-officer search directory",
    )
    _add_location(officers)
    officers.add_argument("--limit", type=int)
    officers.add_argument("--cursor")
    _add_common(officers)

    search = sub.add_parser(
        "search",
        help="Search calendar hearings using one official source selector",
    )
    _add_location(search)
    search.add_argument("--after", dest="date_after")
    search.add_argument("--before", dest="date_before")
    search.add_argument(
        "--category",
        dest="categories",
        action="append",
        choices=tuple(CATEGORY_CODES),
        help="Repeat to select source case categories; defaults to all",
    )
    search.add_argument("--case-number")
    search.add_argument("--party-first-name")
    search.add_argument("--party-last-name")
    search.add_argument("--party-middle-name")
    search.add_argument("--business-name")
    search.add_argument("--attorney-first-name")
    search.add_argument("--attorney-last-name")
    search.add_argument("--attorney-middle-name")
    search.add_argument("--attorney-bar-number")
    search.add_argument(
        "--judicial-officer",
        help="Exact display name or source-native judicial-officer ID",
    )
    search.add_argument("--exact-name", action="store_true")
    search.add_argument(
        "--soundex",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    search.add_argument(
        "--limit",
        type=int,
        help="Local case page size; omitted returns all source rows",
    )
    search.add_argument("--cursor")
    _add_common(search)

    probe = sub.add_parser(
        "probe",
        help="Verify landing, form, and authoritative result contracts",
    )
    _add_location(probe)
    _add_common(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
