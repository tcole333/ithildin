#!/usr/bin/env python3
"""Query the official Franklin County, Ohio Probate Court case index.

The Probate Court publishes a modern search landing page that delegates to a
legacy NetData index.  The NetData indexes are ordered browse windows with
source-native forward/backward keys.  This adapter follows the forward keys to
source exhaustion unless the caller requests a bounded window with ``--limit``;
bounded windows return an opaque cursor that preserves the exact NetData page
and row position.

Examples:
    uv run python tools/query_ohio_franklin_probate.py source --json
    uv run python tools/query_ohio_franklin_probate.py name "SMITH, JOHN" \
        --limit 80 --output /tmp/franklin-probate-name.json
    uv run python tools/query_ohio_franklin_probate.py number 617503 --json
    uv run python tools/query_ohio_franklin_probate.py case 617503 --json
    uv run python tools/query_ohio_franklin_probate.py docket 617503 \
        --output /tmp/franklin-probate-docket.json
    uv run python tools/query_ohio_franklin_probate.py probe --json
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
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup, Tag

try:
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
except ImportError:
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-oh-franklin-probate-netdata"
SOURCE_NAME = "Franklin County Probate Court General Case Search"
COURT_ID = "oh-franklin-county-probate-court"
COURT_NAME = "Franklin County Probate Court"
STATE_CODE = "OH"
COUNTY_FIPS = "39049"
OBSERVED_AT = "2026-07-31"

LANDING_URL = (
    "https://probate.franklincountyohio.gov/"
    "Record-Search/General-Case-Search"
)
CERTIFIED_RECORDS_URL = (
    "https://probate.franklincountyohio.gov/Departments/Certified-Records"
)
NETDATA_BASE_URL = "https://probatesearch.franklincountyohio.gov/netdata/"
NETDATA_HOST = "probatesearch.franklincountyohio.gov"
LANDING_HOST = "probate.franklincountyohio.gov"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 3
CURSOR_PREFIX = "ohio-franklin-probate:v1:"
CURSOR_VERSION = 1
PROBE_CASE_NUMBER = "617503"

# The official landing currently accepts a conventional curl HTTP profile and
# rejects a Chrome-shaped requests profile with an Akamai 403. NetData accepts
# the same curl profile, so both official hosts can use one deterministic path.
USER_AGENT = "curl/8.7.1"

INDEX_ROUTES = {
    "name": "PBCNameInx.ndm/input",
    "number": "PBCNumbInx.ndm/input",
    "opened": "PBODateInx.ndm/input",
    "type": "PBCTypeInx.ndm/input",
    "attorney": "PBAttyInx.ndm/input",
    "fiduciary": "PBFidyInx.ndm/input",
}

CASE_TYPES: Mapping[str, Mapping[str, str]] = {
    "E": {"source_value": "E ", "label": "Estate"},
    "C": {"source_value": "C ", "label": "Civil"},
    "T": {"source_value": "T ", "label": "Trust"},
    "GA": {"source_value": "GA", "label": "Adult Guardianship"},
    "GM": {"source_value": "GM", "label": "Minor Guardianship"},
    "M": {"source_value": "M ", "label": "Miscellaneous"},
    "ST": {"source_value": "ST", "label": "Sentinal Trusts"},
}

DETAIL_ROUTE_TYPES = {
    "/netdata/pbcasetypee.ndm/estate_detail": "E",
    "/netdata/pbcasetypec.ndm/civil_detail": "C",
    "/netdata/pbcasetypet.ndm/trust_detail": "T",
    "/netdata/pbcasetypem.ndm/misc_detail": "M",
    "/netdata/pbcasetypestg.ndm/input": "ST",
}

SOURCE_WARNINGS = (
    "The NetData name, attorney, fiduciary, open-date, and type indexes are "
    "ordered browse indexes. Returned rows preserve the source window and "
    "should not be treated as exact-name matches without comparing the row.",
    "The court says online case-search records are current as of the previous "
    "day; weekday backup activity is normally between 10 PM and 2 AM and may "
    "also occur on weekends.",
    "The online index is not a certified copy. The Probate Court provides "
    "separate certified-record and copy-request channels.",
    "Status values are retained as the source's native codes rather than "
    "expanded without the court's status-code artifact.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role=(
        "county_probate_case_index_detail_docket_fiduciary_and_attorney"
    ),
    base_url=LANDING_URL,
    dataset_id="franklin-county-probate-netdata",
    metadata={
        "authority": "Franklin County Probate Court",
        "county_fips": COUNTY_FIPS,
        "platform_family": "franklin_county_netdata",
        "authentication": "none",
        "native_page_size_observed": 40,
        "native_pagination": "forward_and_backward_lexicographic_keys",
        "certified_records_url": CERTIFIED_RECORDS_URL,
        "observed_at": OBSERVED_AT,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_FIPS,
    name="Franklin County, Ohio",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Franklin County",
)


class FranklinProbateError(RuntimeError):
    """A transport, source-schema, paging, or caller-selection failure."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class FranklinProbateSelectionError(FranklinProbateError):
    """A caller selector or cursor cannot be represented by NetData."""

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
            details=details,
        )


class FranklinProbateSourceChanged(FranklinProbateError):
    """The official page no longer matches the verified source structure."""

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


class FranklinProbatePartialCollection(RuntimeError):
    """A later native page failed after one or more rows were collected."""

    def __init__(
        self,
        error: FranklinProbateError,
        *,
        records: Sequence[Mapping[str, Any]],
        next_cursor: str,
        pages_fetched: int,
    ) -> None:
        super().__init__(str(error))
        self.error = error
        self.records = tuple(records)
        self.next_cursor = next_cursor
        self.pages_fetched = pages_fetched


@dataclass(frozen=True)
class IndexPage:
    """One validated native NetData browse window."""

    source_url: str
    headers: tuple[str, ...]
    records: tuple[Mapping[str, Any], ...]
    next_url: str | None
    previous_url: str | None
    source_total_raw: str | None
    page_fingerprint: str


@dataclass(frozen=True)
class IndexCollection:
    """A caller window collected across one or more native pages."""

    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    pages_fetched: int
    native_pages_exhausted: bool


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _nullable(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = " ".join(str(value).split())
    return candidate or None


def _nonblank(value: str) -> str:
    candidate = " ".join(value.split())
    if not candidate:
        raise argparse.ArgumentTypeError("value must not be blank")
    return candidate


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _case_number(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(r"\d{1,6}", candidate):
        raise FranklinProbateSelectionError(
            "invalid_case_number",
            "Franklin Probate case number must contain one to six digits",
            details={"case_number": value},
        )
    return candidate


def _case_suffix(value: str | None) -> str:
    candidate = (value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{0,2}", candidate):
        raise FranklinProbateSelectionError(
            "invalid_case_suffix",
            "Franklin Probate case suffix must contain at most two letters or digits",
            details={"case_suffix": value},
        )
    return candidate


def _fiduciary_number(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(r"\d{1,2}", candidate):
        raise FranklinProbateSelectionError(
            "invalid_fiduciary_number",
            "Fiduciary number must contain one or two digits",
            details={"fiduciary_number": value},
        )
    return candidate.zfill(2)


def _attorney_number(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(r"\d{1,7}", candidate):
        raise FranklinProbateSelectionError(
            "invalid_attorney_number",
            "Attorney number must contain one to seven digits",
            details={"attorney_number": value},
        )
    return candidate.zfill(7)


def _open_date(value: str) -> str:
    candidate = value.strip()
    parsed: datetime | None = None
    for pattern in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(candidate, pattern)
            break
        except ValueError:
            continue
    if parsed is None:
        raise FranklinProbateSelectionError(
            "invalid_open_date",
            "Open date must use YYYY-MM-DD or MM/DD/YYYY",
            details={"open_date": value},
        )
    return parsed.strftime("%Y-%m-%d")


def _case_type(value: str) -> str:
    candidate = value.strip().upper()
    if candidate not in CASE_TYPES:
        raise FranklinProbateSelectionError(
            "invalid_case_type",
            "Unsupported Franklin Probate case type",
            details={
                "case_type": value,
                "available_case_types": sorted(CASE_TYPES),
            },
        )
    return candidate


def _case_subtype(value: str | None) -> str:
    candidate = (value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{0,2}", candidate):
        raise FranklinProbateSelectionError(
            "invalid_case_subtype",
            "Case subtype must contain at most two letters or digits",
            details={"case_subtype": value},
        )
    return candidate


def _fixed_two(value: str) -> str:
    if not value:
        return ";;"
    if len(value) == 1:
        return f"{value};"
    return value


def _case_selector(case_number: str, suffix: str = "") -> str:
    """Return NetData's fixed-width case + two-character suffix selector."""

    return f"{case_number}{_fixed_two(suffix)}"


def _person_selector(
    case_number: str,
    suffix: str,
    fiduciary_number: str,
) -> str:
    """Return case + suffix + fiduciary-row selector with literal fillers."""

    return f"{_case_selector(case_number, suffix)}{fiduciary_number}"


def _official_url(
    href: str,
    *,
    base_url: str = NETDATA_BASE_URL,
    require_netdata: bool = True,
) -> str:
    joined = urljoin(base_url, href.strip())
    parts = urlsplit(joined)
    host = (parts.hostname or "").lower()
    if host not in {NETDATA_HOST, LANDING_HOST}:
        raise FranklinProbateSourceChanged(
            "unexpected_link_host",
            "Franklin Probate page linked to an unexpected host",
            details={"href": href, "resolved_url": joined},
        )
    if require_netdata and (
        host != NETDATA_HOST or not parts.path.lower().startswith("/netdata/")
    ):
        raise FranklinProbateSourceChanged(
            "unexpected_netdata_link",
            "Franklin Probate continuation or record link left NetData",
            details={"href": href, "resolved_url": joined},
        )
    return urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))


def _index_url(operation: str, expression: str) -> str:
    route = INDEX_ROUTES[operation]
    encoded = quote(expression, safe=";!=,*")
    return f"{urljoin(NETDATA_BASE_URL, route)}?string={encoded}"


def _detail_url(route: str, selector: str) -> str:
    # NetData treats percent-encoded semicolons as data. Keep fixed-width
    # delimiter semicolons literal in the URL sent to the source.
    return f"{urljoin(NETDATA_BASE_URL, route)}?caseno={selector}"


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_fips": COUNTY_FIPS,
        "court_level": "county",
        "division": "probate",
    }


def _source_record() -> dict[str, Any]:
    routes = [
        {
            "operation": operation,
            "method": "GET",
            "url": urljoin(NETDATA_BASE_URL, route),
            "pagination": "native_forward_key",
        }
        for operation, route in INDEX_ROUTES.items()
    ]
    routes.extend(
        [
            {
                "operation": "case",
                "method": "GET",
                "route_family": "case_type_specific_detail",
            },
            {
                "operation": "docket",
                "method": "GET",
                "url": urljoin(NETDATA_BASE_URL, "PBDocket.ndm/input"),
            },
            {
                "operation": "fiduciaries",
                "method": "GET",
                "url": urljoin(NETDATA_BASE_URL, "PBFidy.ndm/input"),
            },
            {
                "operation": "fiduciary-detail",
                "method": "GET",
                "url": urljoin(
                    NETDATA_BASE_URL,
                    "PBFidDetail.ndm/FID_DETAIL",
                ),
            },
            {
                "operation": "attorney-detail",
                "method": "GET",
                "url": urljoin(
                    NETDATA_BASE_URL,
                    "PBAttyDetail.ndm/ATTY_DETAIL",
                ),
            },
            {
                "operation": "attorney-profile",
                "method": "GET",
                "url": urljoin(
                    NETDATA_BASE_URL,
                    "PBAttyForm.ndm/ATTY_FORM",
                ),
            },
        ]
    )
    return {
        "record_kind": "source_capabilities",
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "court": _court_payload(),
        "landing_url": LANDING_URL,
        "certified_records_url": CERTIFIED_RECORDS_URL,
        "netdata_base_url": NETDATA_BASE_URL,
        "observed_at": OBSERVED_AT,
        "records_current_as_of": "previous_day",
        "published_backup_window": "weekdays 10 PM to 2 AM; random weekends",
        "case_types": {
            code: details["label"] for code, details in CASE_TYPES.items()
        },
        "routes": routes,
        "paging": {
            "native_page_size_observed": 40,
            "default": "follow_source_forward_keys_to_exhaustion",
            "caller_window": (
                "--limit returns an opaque page-and-row continuation cursor"
            ),
        },
        "selector_grammar": {
            "case_detail": "case_number + fixed_two_character_suffix",
            "person_detail": (
                "case_number + fixed_two_character_suffix + fiduciary_number"
            ),
            "blank_fixed_width_character": ";",
            "transport_note": "selector semicolons remain literal",
        },
    }


def parse_landing_page(html: str, *, source_url: str = LANDING_URL) -> dict[str, Any]:
    """Parse the official landing's published search methods and notices."""

    soup = BeautifulSoup(html, "html.parser")
    selector = soup.find("select", attrs={"name": "searchMethod"})
    if not isinstance(selector, Tag):
        raise FranklinProbateSourceChanged(
            "landing_search_methods_missing",
            "Franklin Probate landing no longer publishes its search-method selector",
            details={"url": source_url},
        )
    methods = [
        {
            "value": str(option.get("value") or ""),
            "label": _text(option),
        }
        for option in selector.find_all("option")
    ]
    forms: list[dict[str, Any]] = []
    method_values = {method["value"] for method in methods}
    for form in soup.find_all("form"):
        form_id = str(form.get("id") or "")
        if form_id not in method_values:
            continue
        fields: list[dict[str, Any]] = []
        for field in form.find_all(["input", "select"]):
            name = str(field.get("name") or "")
            if not name:
                continue
            fields.append(
                {
                    "name": name,
                    "element": field.name,
                    "type": str(field.get("type") or "") or None,
                }
            )
        action_raw = str(form.get("action") or "")
        forms.append(
            {
                "id": form_id,
                "method": str(form.get("method") or "get").upper(),
                "action_raw": action_raw or None,
                "action_url": (
                    _official_url(
                        action_raw,
                        base_url=source_url,
                        require_netdata=False,
                    )
                    if action_raw
                    else None
                ),
                "fields": fields,
            }
        )
    notices = []
    for paragraph in soup.find_all("p"):
        text = _text(paragraph)
        lowered = text.lower()
        if "current as of the previous" in lowered or "routine back up" in lowered:
            notices.append(text)
    return {
        "record_kind": "source_landing",
        "source_id": SOURCE_ID,
        "source_url": source_url,
        "title": _text(soup.title),
        "search_methods": methods,
        "forms": forms,
        "notices": notices,
    }


def _direct_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr", recursive=False) if isinstance(row, Tag)]


def _direct_cells(row: Tag) -> list[Tag]:
    return [
        cell
        for cell in row.find_all(["th", "td"], recursive=False)
        if isinstance(cell, Tag)
    ]


def _find_index_table(soup: BeautifulSoup, operation: str) -> tuple[Tag, tuple[str, ...]]:
    if operation == "attorney":
        required = ("Attorney Name", "Attorney Number")
    elif operation == "fiduciary":
        required = ("Case Number", "Fiduciary", "Type", "Subtype")
    else:
        required = ("Case Number", "Case Name", "Type", "SubType")
    candidates: list[tuple[int, Tag, tuple[str, ...]]] = []
    for table in soup.find_all("table"):
        rows = _direct_rows(table)
        for row in rows:
            cells = _direct_cells(row)
            headers = tuple(_text(cell) for cell in cells if cell.name == "th")
            if headers[: len(required)] == required:
                candidates.append((len(rows), table, headers))
                break
    if not candidates:
        raise FranklinProbateSourceChanged(
            "index_table_missing",
            "Franklin Probate index table no longer matches the verified headers",
            details={"operation": operation},
        )
    _, table, headers = max(candidates, key=lambda item: item[0])
    return table, headers


def _case_parts(display: str, detail_url: str | None) -> tuple[str, str]:
    normalized = " ".join(display.split())
    match = re.match(r"^(?P<number>\d{1,6})(?:\s+(?P<suffix>[A-Z0-9]{1,2}))?$", normalized)
    if match:
        return match.group("number"), match.group("suffix") or ""
    if detail_url:
        query = urlsplit(detail_url).query
        selector_match = re.search(r"(?:^|&)caseno=(\d{1,6})([A-Z0-9;]{0,2})", query)
        if selector_match:
            suffix = selector_match.group(2).replace(";", "")
            return selector_match.group(1), suffix
    return normalized, ""


def _type_code_from_detail_url(detail_url: str | None, case_type: str) -> str | None:
    if not detail_url:
        return None
    path = urlsplit(detail_url).path.lower()
    if path in DETAIL_ROUTE_TYPES:
        return DETAIL_ROUTE_TYPES[path]
    if path == "/netdata/pbcasetypeg.ndm/guard_detail":
        upper = case_type.upper()
        if "ADULT" in upper:
            return "GA"
        if "MINOR" in upper:
            return "GM"
    return None


def _navigation_url(
    soup: BeautifulSoup,
    *,
    source_url: str,
    direction: str,
) -> str | None:
    matches: set[str] = set()
    needle = direction.lower()
    query_key = "stringf=" if direction == "next" else "stringb="
    for anchor in soup.find_all("a", href=True):
        text = _text(anchor).lower()
        href = str(anchor.get("href") or "")
        if needle not in text or query_key not in href.lower():
            continue
        matches.add(_official_url(href, base_url=source_url))
    if len(matches) > 1:
        raise FranklinProbateSourceChanged(
            "ambiguous_navigation",
            "Franklin Probate page exposed multiple distinct navigation links",
            details={
                "direction": direction,
                "source_url": source_url,
                "links": sorted(matches),
            },
        )
    return next(iter(matches), None)


def _common_case_record(
    headers: Sequence[str],
    cells: Sequence[Tag],
    *,
    source_url: str,
    operation: str,
    position: int,
) -> dict[str, Any]:
    values = [_text(cell) for cell in cells]
    source_row = dict(zip(headers, values, strict=False))
    first_link = cells[0].find("a", href=True)
    href_raw = str(first_link.get("href")) if isinstance(first_link, Tag) else None
    detail_url = (
        _official_url(href_raw, base_url=source_url) if href_raw else None
    )
    case_number, suffix = _case_parts(values[0], detail_url)
    case_type = values[2] if len(values) > 2 else ""
    record = {
        "record_kind": "probate_case_index",
        "source_id": SOURCE_ID,
        "court": _court_payload(),
        "case_number": case_number,
        "case_suffix": suffix or None,
        "case_number_display_raw": values[0],
        "case_name": _nullable(values[1] if len(values) > 1 else ""),
        "case_type": _nullable(case_type),
        "case_type_code": _type_code_from_detail_url(detail_url, case_type),
        "case_subtype": _nullable(values[3] if len(values) > 3 else ""),
        "status_code": _nullable(values[4] if len(values) > 4 else ""),
        "opened_date_raw": _nullable(values[5] if len(values) > 5 else ""),
        "closed_date_raw": _nullable(values[6] if len(values) > 6 else ""),
        "detail_href_raw": href_raw,
        "detail_url": detail_url,
        "source_url": source_url,
        "source_page_position": position,
        "source_row": source_row,
        "discovery_operation": operation,
    }
    if operation == "fiduciary":
        record.update(
            {
                "fiduciary_name": _nullable(values[1] if len(values) > 1 else ""),
                "case_name": _nullable(values[7] if len(values) > 7 else ""),
                "attorney_name": _nullable(values[8] if len(values) > 8 else ""),
            }
        )
    if case_number:
        canonical_number = f"{case_number}{suffix}"
        record["source_native_id"] = _case_selector(case_number, suffix)
        record["canonical_ref"] = canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            canonical_number,
        )
    return record


def _attorney_index_record(
    cells: Sequence[Tag],
    *,
    source_url: str,
    position: int,
) -> dict[str, Any]:
    values = [_text(cell) for cell in cells]
    first_link = cells[0].find("a", href=True)
    href_raw = str(first_link.get("href")) if isinstance(first_link, Tag) else None
    profile_url = (
        _official_url(href_raw, base_url=source_url) if href_raw else None
    )
    attorney_number = _nullable(values[1] if len(values) > 1 else "")
    return {
        "record_kind": "probate_attorney_index",
        "source_id": SOURCE_ID,
        "court": _court_payload(),
        "attorney_name": _nullable(values[0] if values else ""),
        "attorney_number": attorney_number,
        "source_native_id": attorney_number,
        "attorney_profile_href_raw": href_raw,
        "attorney_profile_url": profile_url,
        "source_url": source_url,
        "source_page_position": position,
        "source_row": {
            "Attorney Name": values[0] if values else "",
            "Attorney Number": values[1] if len(values) > 1 else "",
        },
        "discovery_operation": "attorney",
    }


def parse_index_page(
    html: str,
    *,
    source_url: str,
    operation: str,
) -> IndexPage:
    """Parse one source-native index page and retain its navigation keys."""

    if operation not in INDEX_ROUTES:
        raise FranklinProbateSelectionError(
            "invalid_index_operation",
            "Unknown Franklin Probate index operation",
            details={"operation": operation},
        )
    soup = BeautifulSoup(html, "html.parser")
    table, headers = _find_index_table(soup, operation)
    records: list[Mapping[str, Any]] = []
    header_seen = False
    for row in _direct_rows(table):
        cells = _direct_cells(row)
        row_headers = tuple(_text(cell) for cell in cells if cell.name == "th")
        if row_headers:
            if row_headers == headers:
                header_seen = True
            continue
        if not header_seen or not cells:
            continue
        if operation == "attorney":
            if len(cells) < 2 or not re.fullmatch(r"\d{7}", _text(cells[1])):
                continue
            records.append(
                _attorney_index_record(
                    cells,
                    source_url=source_url,
                    position=len(records) + 1,
                )
            )
            continue
        expected_cells = 9 if operation == "fiduciary" else 7
        if len(cells) != expected_cells:
            continue
        values = [_text(cell) for cell in cells]
        if (
            operation == "number"
            and len(values) == 7
            and values[1].upper() == "CASE IS NOT FOUND"
            and not any(values[2:])
        ):
            continue
        if not re.match(r"^\d{1,6}(?:\s+[A-Z0-9]{1,2})?$", _text(cells[0])):
            continue
        records.append(
            _common_case_record(
                headers,
                cells,
                source_url=source_url,
                operation=operation,
                position=len(records) + 1,
            )
        )
    total_match = re.search(r"Total\s+Records:\s*([\d,]+)", _text(table), re.I)
    total_raw = total_match.group(1) if total_match else None
    page_payload = {
        "headers": headers,
        "records": [dict(record) for record in records],
    }
    return IndexPage(
        source_url=source_url,
        headers=headers,
        records=tuple(records),
        next_url=_navigation_url(soup, source_url=source_url, direction="next"),
        previous_url=_navigation_url(
            soup,
            source_url=source_url,
            direction="prev",
        ),
        source_total_raw=total_raw,
        page_fingerprint=_hash(page_payload),
    )


def _field_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _field_table(soup: BeautifulSoup) -> tuple[Tag, list[dict[str, str]], dict[str, Any]]:
    candidates: list[tuple[int, Tag, list[dict[str, str]]]] = []
    for table in soup.find_all("table"):
        rows: list[dict[str, str]] = []
        for row in _direct_rows(table):
            cells = _direct_cells(row)
            th = [cell for cell in cells if cell.name == "th"]
            td = [cell for cell in cells if cell.name == "td"]
            if len(th) != 1 or len(td) != 1:
                continue
            label = _text(th[0])
            if label:
                rows.append({"label": label, "value": _text(td[0])})
        if rows:
            candidates.append((len(rows), table, rows))
    if not candidates:
        raise FranklinProbateSourceChanged(
            "detail_fields_missing",
            "Franklin Probate detail page no longer exposes label/value fields",
        )
    _, table, rows = max(candidates, key=lambda item: item[0])
    fields: dict[str, Any] = {}
    for row in rows:
        label = row["label"]
        value = row["value"]
        if label not in fields:
            fields[label] = value
        elif isinstance(fields[label], list):
            fields[label].append(value)
        else:
            fields[label] = [fields[label], value]
    return table, rows, fields


def _first_field(fields: Mapping[str, Any], *labels: str) -> str | None:
    for label in labels:
        value = fields.get(label)
        if isinstance(value, str):
            return _nullable(value)
        if isinstance(value, list) and value:
            return _nullable(str(value[0]))
    return None


def _detail_links(table: Tag, source_url: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in table.find_all("a", href=True):
        label = _text(anchor)
        href_raw = str(anchor.get("href") or "")
        if not label or not href_raw or "/netdata/" not in href_raw.lower():
            continue
        key = (label, href_raw)
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "label": label,
                "href_raw": href_raw,
                "url": _official_url(href_raw, base_url=source_url),
            }
        )
    return links


def parse_detail_page(
    html: str,
    *,
    source_url: str,
    record_kind: str = "probate_case",
) -> dict[str, Any] | None:
    """Parse a case, fiduciary, attorney, or attorney-profile detail page."""

    soup = BeautifulSoup(html, "html.parser")
    raw_lower = html.lower()
    if "case is not found" in raw_lower or "not on file" in raw_lower:
        return None
    table, field_rows, fields = _field_table(soup)
    case_number_raw = _first_field(fields, "Case Number / Suffix")
    case_number: str | None = None
    suffix: str | None = None
    if case_number_raw:
        match = re.match(r"^(\d{1,6})(?:\s+([A-Z0-9]{1,2}))?$", case_number_raw)
        if match:
            case_number = match.group(1)
            suffix = match.group(2)
    record: dict[str, Any] = {
        "record_kind": record_kind,
        "source_id": SOURCE_ID,
        "court": _court_payload(),
        "source_url": source_url,
        "fields": fields,
        "source_rows": field_rows,
        "links": _detail_links(table, source_url),
    }
    if case_number:
        source_native_id = _case_selector(case_number, suffix or "")
        record.update(
            {
                "case_number": case_number,
                "case_suffix": suffix,
                "case_number_display_raw": case_number_raw,
                "source_native_id": source_native_id,
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    f"{case_number}{suffix or ''}",
                    "case" if record_kind == "probate_case" else record_kind,
                ),
            }
        )
    if record_kind == "probate_case":
        record.update(
            {
                "case_name": _first_field(fields, "Case Name"),
                "case_type": _first_field(fields, "Case Type"),
                "case_type_code": _type_code_from_detail_url(
                    source_url,
                    _first_field(fields, "Case Type") or "",
                ),
                "case_subtype": _first_field(fields, "Case Subtype", "Case Sub Type"),
                "aka_raw": _first_field(fields, "AKA"),
                "date_opened_raw": _first_field(fields, "Date Opened"),
                "date_closed_raw": _first_field(fields, "Date Closed"),
                "bond_amount_raw": _first_field(fields, "Bond Amount"),
                "related_cases_raw": [
                    row["value"]
                    for row in field_rows
                    if row["label"].startswith("Related Case/Sfx")
                    and row["value"]
                    and row["value"].upper() != "N/A"
                ],
            }
        )
    elif record_kind == "probate_fiduciary_detail":
        fiduciary_number = _first_field(fields, "Fiduciary Number")
        record.update(
            {
                "fiduciary_number": fiduciary_number,
                "fiduciary_title_code": _first_field(fields, "Fiduciary Title"),
                "fiduciary_title": _first_field(fields, "Title Description"),
                "fiduciary_name": _first_field(
                    fields,
                    "Estate Fiduciaries Name",
                    "Name",
                ),
            }
        )
        if case_number and fiduciary_number:
            person_native_id = _person_selector(
                case_number,
                suffix or "",
                fiduciary_number,
            )
            record["source_native_id"] = person_native_id
            record["canonical_ref"] = canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                f"{case_number}{suffix or ''}",
                "fiduciary",
                person_native_id,
            )
    elif record_kind in {"probate_attorney_detail", "probate_attorney_profile"}:
        attorney_number = _first_field(fields, "Attorney Number")
        record.update(
            {
                "attorney_number": attorney_number,
                "attorney_name": _first_field(fields, "Attorney Name"),
            }
        )
        if record_kind == "probate_attorney_profile":
            record["source_native_id"] = attorney_number
    return record


def _find_exact_table(soup: BeautifulSoup, headers: tuple[str, ...]) -> Tag:
    candidates: list[tuple[int, Tag]] = []
    for table in soup.find_all("table"):
        rows = _direct_rows(table)
        for row in rows:
            row_headers = tuple(
                _text(cell)
                for cell in _direct_cells(row)
                if cell.name == "th"
            )
            if row_headers == headers:
                candidates.append((len(rows), table))
                break
    if not candidates:
        raise FranklinProbateSourceChanged(
            "record_table_missing",
            "Franklin Probate record table no longer matches the verified headers",
            details={"expected_headers": list(headers)},
        )
    return max(candidates, key=lambda item: item[0])[1]


DOCKET_HEADERS = ("Date", "Code", "Description", "Reference", "Receipt", "Cost")


def _joined_lines(rows: Sequence[Mapping[str, str]], key: str) -> str | None:
    values = [row[key] for row in rows if row.get(key)]
    return " ".join(values) or None


def parse_docket_page(
    html: str,
    *,
    source_url: str,
    case_number: str,
    case_suffix: str = "",
) -> list[dict[str, Any]]:
    """Parse logical docket entries while preserving every physical row."""

    soup = BeautifulSoup(html, "html.parser")
    if "CASE IS NOT FOUND" in _text(soup).upper():
        return []
    table = _find_exact_table(soup, DOCKET_HEADERS)
    physical_rows: list[dict[str, str]] = []
    header_seen = False
    for row in _direct_rows(table):
        cells = _direct_cells(row)
        row_headers = tuple(_text(cell) for cell in cells if cell.name == "th")
        if row_headers:
            header_seen = row_headers == DOCKET_HEADERS
            continue
        if not header_seen or len(cells) != len(DOCKET_HEADERS):
            continue
        values = [_text(cell) for cell in cells]
        if not any(values):
            continue
        physical_rows.append(
            {
                "date": values[0],
                "code": values[1],
                "description": values[2],
                "reference": values[3],
                "receipt": values[4],
                "cost": values[5],
                "row_color": str(row.get("bgcolor") or "").lower(),
            }
        )

    groups: list[dict[str, Any]] = []
    for source_row in physical_rows:
        is_primary = bool(source_row["date"] or source_row["code"])
        is_summary = source_row["description"].strip().upper() == "DEPOSIT REMAINING"
        previous = groups[-1] if groups else None
        is_continuation = (
            not is_primary
            and not is_summary
            and previous is not None
            and previous["record_kind"] == "probate_docket_entry"
            and previous["row_color"] == source_row["row_color"]
        )
        if is_continuation:
            previous["source_rows"].append(source_row)
            continue
        groups.append(
            {
                "record_kind": (
                    "probate_docket_entry" if is_primary else "probate_docket_summary"
                ),
                "row_color": source_row["row_color"],
                "source_rows": [source_row],
            }
        )

    records: list[dict[str, Any]] = []
    canonical_number = f"{case_number}{case_suffix}"
    for position, group in enumerate(groups, start=1):
        source_rows = group["source_rows"]
        row_fingerprint = _hash(source_rows)[:16]
        source_native_id = (
            f"{_case_selector(case_number, case_suffix)}:"
            f"{position}:{row_fingerprint}"
        )
        record = {
            "record_kind": group["record_kind"],
            "source_id": SOURCE_ID,
            "court": _court_payload(),
            "case_number": case_number,
            "case_suffix": case_suffix or None,
            "canonical_case_ref": canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                canonical_number,
            ),
            "source_position": position,
            "source_native_id": source_native_id,
            "date_raw": _nullable(source_rows[0]["date"]),
            "code": _nullable(source_rows[0]["code"]),
            "description": _joined_lines(source_rows, "description"),
            "description_lines": [
                row["description"] for row in source_rows if row["description"]
            ],
            "reference_raw": _joined_lines(source_rows, "reference"),
            "receipt_raw": _joined_lines(source_rows, "receipt"),
            "cost_raw": _joined_lines(source_rows, "cost"),
            "source_rows": source_rows,
            "source_url": source_url,
        }
        record["canonical_ref"] = canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            canonical_number,
            group["record_kind"],
            source_native_id,
        )
        records.append(record)
    return records


FIDUCIARY_HEADERS = (
    "Fiduciary No.",
    "Estate Fiduciaries",
    "Title",
    "Title Description",
    "Appt Date",
    "Term Date",
    "Date Case Closed",
    "Attorney Number",
    "Attorney Name",
)


def parse_fiduciaries_page(
    html: str,
    *,
    source_url: str,
    case_number: str,
    case_suffix: str = "",
) -> list[dict[str, Any]]:
    """Parse the case's fiduciary/attorney rows and corrected detail links."""

    soup = BeautifulSoup(html, "html.parser")
    if "CASE IS NOT FOUND" in _text(soup).upper():
        return []
    table = _find_exact_table(soup, FIDUCIARY_HEADERS)
    records: list[dict[str, Any]] = []
    header_seen = False
    for row in _direct_rows(table):
        cells = _direct_cells(row)
        row_headers = tuple(_text(cell) for cell in cells if cell.name == "th")
        if row_headers:
            header_seen = row_headers == FIDUCIARY_HEADERS
            continue
        if not header_seen or len(cells) != len(FIDUCIARY_HEADERS):
            continue
        values = [_text(cell) for cell in cells]
        if not re.fullmatch(r"\d{1,2}", values[0]):
            continue
        fid_number = values[0].zfill(2)
        selector = _person_selector(case_number, case_suffix, fid_number)
        fid_link = cells[0].find("a", href=True)
        attorney_link = cells[7].find("a", href=True)
        source_row = dict(zip(FIDUCIARY_HEADERS, values, strict=True))
        records.append(
            {
                "record_kind": "probate_fiduciary",
                "source_id": SOURCE_ID,
                "court": _court_payload(),
                "case_number": case_number,
                "case_suffix": case_suffix or None,
                "canonical_case_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    f"{case_number}{case_suffix}",
                ),
                "source_native_id": selector,
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    f"{case_number}{case_suffix}",
                    "fiduciary",
                    selector,
                ),
                "fiduciary_number": fid_number,
                "fiduciary_name": _nullable(values[1]),
                "title_code": _nullable(values[2]),
                "title_description": _nullable(values[3]),
                "appointment_date_raw": _nullable(values[4]),
                "termination_date_raw": _nullable(values[5]),
                "case_closed_date_raw": _nullable(values[6]),
                "attorney_number": _nullable(values[7]),
                "attorney_name": _nullable(values[8]),
                "fiduciary_detail_href_raw": (
                    str(fid_link.get("href")) if isinstance(fid_link, Tag) else None
                ),
                "fiduciary_detail_url": _detail_url(
                    "PBFidDetail.ndm/FID_DETAIL",
                    selector,
                ),
                "attorney_detail_href_raw": (
                    str(attorney_link.get("href"))
                    if isinstance(attorney_link, Tag)
                    else None
                ),
                "attorney_detail_url": _detail_url(
                    "PBAttyDetail.ndm/ATTY_DETAIL",
                    selector,
                ),
                "source_row": source_row,
                "source_url": source_url,
            }
        )
    return records


def _cursor_encode(
    *,
    operation: str,
    criteria: str,
    page_url: str,
    row_offset: int,
    page_fingerprint: str,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "operation": operation,
        "criteria": criteria,
        "page_url": page_url,
        "row_offset": row_offset,
        "page_fingerprint": page_fingerprint,
    }
    encoded = base64.urlsafe_b64encode(canonical_json(payload).encode()).decode()
    return CURSOR_PREFIX + encoded.rstrip("=")


def _cursor_decode(
    cursor: str,
    *,
    operation: str,
    criteria: str,
    initial_url: str,
) -> Mapping[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise FranklinProbateSelectionError(
            "invalid_cursor",
            "Continuation is not a Franklin Probate cursor",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(decoded)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise FranklinProbateSelectionError(
            "invalid_cursor",
            "Franklin Probate cursor is malformed",
        ) from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("version") != CURSOR_VERSION
        or payload.get("source_id") != SOURCE_ID
        or payload.get("operation") != operation
        or payload.get("criteria") != criteria
        or not isinstance(payload.get("page_url"), str)
        or not isinstance(payload.get("row_offset"), int)
        or payload["row_offset"] < 0
        or not isinstance(payload.get("page_fingerprint"), str)
    ):
        raise FranklinProbateSelectionError(
            "cursor_query_mismatch",
            "Franklin Probate cursor does not belong to this query",
        )
    page_url = _official_url(str(payload["page_url"]))
    if urlsplit(page_url).path.lower() != urlsplit(initial_url).path.lower():
        raise FranklinProbateSelectionError(
            "cursor_route_mismatch",
            "Franklin Probate cursor points to a different index route",
        )
    return {**dict(payload), "page_url": page_url}


class FranklinProbateClient:
    """Rate-limited HTTP client for the official landing and NetData host."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_RETRIES
        )
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self.request_count = 0

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _get(self, url: str) -> tuple[str, str]:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "*/*",
                    },
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise FranklinProbateError(
                    "transport_error",
                    "Could not reach Franklin Probate",
                    category="transport",
                    retryable=True,
                    details={"url": url, "error": str(error)},
                ) from error
            status = int(response.status_code)
            if status in self.retry_policy.retry_statuses and attempt < self.retry_policy.max_attempts:
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status == 429:
                raise FranklinProbateError(
                    "rate_limited",
                    "Franklin Probate rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status},
                )
            if status in {401, 403}:
                raise FranklinProbateError(
                    "access_restricted",
                    "Franklin Probate restricted the anonymous request",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status},
                )
            if status >= 400:
                raise FranklinProbateError(
                    "http_status",
                    f"Franklin Probate returned HTTP {status}",
                    category="http",
                    retryable=status >= 500,
                    details={"url": url, "status_code": status},
                )
            final_url = str(getattr(response, "url", url) or url)
            final_parts = urlsplit(final_url)
            if (final_parts.hostname or "").lower() not in {
                NETDATA_HOST,
                LANDING_HOST,
            }:
                raise FranklinProbateSourceChanged(
                    "unexpected_redirect",
                    "Franklin Probate redirected to an unexpected host",
                    details={"requested_url": url, "final_url": final_url},
                )
            return str(response.text), _official_url(
                final_url,
                require_netdata=(urlsplit(url).hostname == NETDATA_HOST),
            )
        raise FranklinProbateError(
            "transport_error",
            "Could not reach Franklin Probate",
            category="transport",
            retryable=True,
            details={"url": url, "error": str(last_error)},
        )

    def landing(self) -> dict[str, Any]:
        html, final_url = self._get(LANDING_URL)
        return parse_landing_page(html, source_url=final_url)

    def index_page(self, operation: str, url: str) -> IndexPage:
        html, final_url = self._get(url)
        return parse_index_page(
            html,
            source_url=final_url,
            operation=operation,
        )

    def detail(self, url: str, *, record_kind: str) -> dict[str, Any] | None:
        html, final_url = self._get(url)
        return parse_detail_page(
            html,
            source_url=final_url,
            record_kind=record_kind,
        )

    def docket(
        self,
        case_number: str,
        suffix: str,
    ) -> list[dict[str, Any]]:
        url = _detail_url("PBDocket.ndm/input", _case_selector(case_number, suffix))
        html, final_url = self._get(url)
        return parse_docket_page(
            html,
            source_url=final_url,
            case_number=case_number,
            case_suffix=suffix,
        )

    def fiduciaries(
        self,
        case_number: str,
        suffix: str,
    ) -> list[dict[str, Any]]:
        url = _detail_url("PBFidy.ndm/input", _case_selector(case_number, suffix))
        html, final_url = self._get(url)
        return parse_fiduciaries_page(
            html,
            source_url=final_url,
            case_number=case_number,
            case_suffix=suffix,
        )


def collect_index(
    client: FranklinProbateClient | Any,
    *,
    operation: str,
    initial_url: str,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> IndexCollection:
    """Collect a caller window while preserving native forward navigation."""

    criteria = _hash(
        {
            "operation": operation,
            "parameters": dict(parameters),
            "initial_url": initial_url,
        }
    )
    continuation = (
        _cursor_decode(
            cursor,
            operation=operation,
            criteria=criteria,
            initial_url=initial_url,
        )
        if cursor
        else None
    )
    current_url = str(continuation["page_url"]) if continuation else initial_url
    row_offset = int(continuation["row_offset"]) if continuation else 0
    expected_fingerprint = (
        str(continuation["page_fingerprint"]) if continuation else None
    )
    records: list[Mapping[str, Any]] = []
    pages_fetched = 0
    seen_urls: set[str] = set()
    last_page: IndexPage | None = None

    while True:
        if current_url in seen_urls:
            raise FranklinProbateSourceChanged(
                "pagination_loop",
                "Franklin Probate returned a repeated forward page",
                details={"url": current_url, "operation": operation},
            )
        seen_urls.add(current_url)
        try:
            page = client.index_page(operation, current_url)
        except FranklinProbateError as error:
            if records and last_page is not None:
                resume_cursor = _cursor_encode(
                    operation=operation,
                    criteria=criteria,
                    page_url=last_page.source_url,
                    row_offset=len(last_page.records),
                    page_fingerprint=last_page.page_fingerprint,
                )
                raise FranklinProbatePartialCollection(
                    error,
                    records=records,
                    next_cursor=resume_cursor,
                    pages_fetched=pages_fetched,
                ) from error
            raise
        pages_fetched += 1
        last_page = page
        if expected_fingerprint and page.page_fingerprint != expected_fingerprint:
            raise FranklinProbateSourceChanged(
                "cursor_page_changed",
                "Franklin Probate page changed since the continuation was issued",
                details={"url": current_url, "operation": operation},
            )
        if row_offset > len(page.records):
            raise FranklinProbateSourceChanged(
                "cursor_offset_changed",
                "Franklin Probate continuation row is beyond the current page",
                details={
                    "url": current_url,
                    "row_offset": row_offset,
                    "page_records": len(page.records),
                },
            )
        for index in range(row_offset, len(page.records)):
            records.append(page.records[index])
            if limit is not None and len(records) == limit:
                next_offset = index + 1
                has_more = next_offset < len(page.records) or page.next_url is not None
                next_cursor = None
                if has_more:
                    next_cursor = _cursor_encode(
                        operation=operation,
                        criteria=criteria,
                        page_url=page.source_url,
                        row_offset=next_offset,
                        page_fingerprint=page.page_fingerprint,
                    )
                return IndexCollection(
                    records=tuple(records),
                    next_cursor=next_cursor,
                    pages_fetched=pages_fetched,
                    native_pages_exhausted=not has_more,
                )
        if page.next_url is None:
            return IndexCollection(
                records=tuple(records),
                next_cursor=None,
                pages_fetched=pages_fetched,
                native_pages_exhausted=True,
            )
        current_url = page.next_url
        row_offset = 0
        expected_fingerprint = None


def _query(
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
        ),
    )


def _index_spec(args: argparse.Namespace) -> tuple[str, dict[str, Any], str]:
    operation = args.command
    if operation in {"name", "attorney", "fiduciary"}:
        term = _nonblank(args.term)
        parameters = {"term": term}
        return operation, parameters, _index_url(operation, term)
    if operation == "number":
        case_number = _case_number(args.case_number)
        suffix = _case_suffix(args.suffix)
        parameters = {"case_number": case_number, "case_suffix": suffix or None}
        return operation, parameters, _index_url(
            operation,
            f"{case_number}!={suffix}",
        )
    if operation == "opened":
        open_date = _open_date(args.open_date)
        source_value = datetime.strptime(open_date, "%Y-%m-%d").strftime("%Y%m%d")
        parameters = {"open_date": open_date}
        return operation, parameters, _index_url(operation, source_value)
    if operation == "type":
        case_type = _case_type(args.case_type)
        subtype = _case_subtype(args.subtype)
        source_type = CASE_TYPES[case_type]["source_value"]
        if not subtype:
            expression = source_type
        elif len(subtype) == 1:
            expression = f"{source_type};{subtype}"
        else:
            expression = f"{source_type}{subtype}"
        parameters = {
            "case_type": case_type,
            "case_subtype": subtype or None,
        }
        return operation, parameters, _index_url(operation, expression)
    raise FranklinProbateSelectionError(
        "invalid_index_operation",
        "Command is not a Franklin Probate discovery index",
        details={"command": operation},
    )


def _matching_number_rows(
    records: Sequence[Mapping[str, Any]],
    *,
    case_number: str,
    suffix: str,
) -> list[dict[str, Any]]:
    return [
        dict(record)
        for record in records
        if record.get("case_number") == case_number
        and (not suffix or record.get("case_suffix") == suffix)
    ]


def _failure(
    query: PublicRecordsQuery,
    error: FranklinProbateError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
) -> PublicRecordsResult:
    status = ResultStatus.PARTIAL if records else error.status
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        records=records,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: FranklinProbateClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one CLI operation and return the shared public-record envelope."""

    source_client = client or FranklinProbateClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )
    query = _query(args.command, {})
    try:
        if args.command == "source":
            query = _query("source", {})
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "landing":
            query = _query("landing", {})
            result = PublicRecordsResult.success(
                query,
                [source_client.landing()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command in INDEX_ROUTES:
            operation, parameters, initial_url = _index_spec(args)
            query = _query(
                operation,
                parameters,
                limit=args.limit,
                cursor=args.cursor,
            )
            collection = collect_index(
                source_client,
                operation=operation,
                initial_url=initial_url,
                parameters=parameters,
                limit=args.limit,
                cursor=args.cursor,
            )
            records = [dict(record) for record in collection.records]
            if operation == "number":
                records = _matching_number_rows(
                    records,
                    case_number=str(parameters["case_number"]),
                    suffix=str(parameters["case_suffix"] or ""),
                )
            for record in records:
                record["result_window"] = {
                    "native_pages_fetched": collection.pages_fetched,
                    "native_pages_exhausted": collection.native_pages_exhausted,
                    "caller_limit": args.limit,
                }
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=collection.next_cursor,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "case":
            case_number = _case_number(args.case_number)
            suffix = _case_suffix(args.suffix)
            parameters = {"case_number": case_number, "case_suffix": suffix or None}
            query = _query("case", parameters)
            number_url = _index_url("number", f"{case_number}!={suffix}")
            collection = collect_index(
                source_client,
                operation="number",
                initial_url=number_url,
                parameters=parameters,
            )
            index_rows = _matching_number_rows(
                collection.records,
                case_number=case_number,
                suffix=suffix,
            )
            records: list[Mapping[str, Any]] = []
            for index_row in index_rows:
                detail_url = index_row.get("detail_url")
                if not isinstance(detail_url, str):
                    raise FranklinProbateSourceChanged(
                        "case_detail_link_missing",
                        "Franklin Probate exact-number row lacks a case-detail link",
                        details={"case_number": case_number, "source_row": index_row},
                    )
                detail = source_client.detail(detail_url, record_kind="probate_case")
                if detail is None:
                    continue
                detail["discovery"] = index_row
                records.append(detail)
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command in {"docket", "fiduciaries"}:
            case_number = _case_number(args.case_number)
            suffix = _case_suffix(args.suffix)
            parameters = {"case_number": case_number, "case_suffix": suffix or None}
            query = _query(args.command, parameters)
            records = (
                source_client.docket(case_number, suffix)
                if args.command == "docket"
                else source_client.fiduciaries(case_number, suffix)
            )
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command in {"fiduciary-detail", "attorney-detail"}:
            case_number = _case_number(args.case_number)
            suffix = _case_suffix(args.suffix)
            fid_number = _fiduciary_number(args.fiduciary_number)
            parameters = {
                "case_number": case_number,
                "case_suffix": suffix or None,
                "fiduciary_number": fid_number,
            }
            query = _query(args.command, parameters)
            route = (
                "PBFidDetail.ndm/FID_DETAIL"
                if args.command == "fiduciary-detail"
                else "PBAttyDetail.ndm/ATTY_DETAIL"
            )
            record_kind = (
                "probate_fiduciary_detail"
                if args.command == "fiduciary-detail"
                else "probate_attorney_detail"
            )
            selector = _person_selector(case_number, suffix, fid_number)
            detail = source_client.detail(
                _detail_url(route, selector),
                record_kind=record_kind,
            )
            if detail is not None:
                detail.update(
                    {
                        "case_number": case_number,
                        "case_suffix": suffix or None,
                        "fiduciary_number": fid_number,
                        "source_native_id": selector,
                        "canonical_case_ref": canonical_court_ref(
                            SOURCE_ID,
                            COURT_ID,
                            f"{case_number}{suffix}",
                        ),
                        "canonical_ref": canonical_court_ref(
                            SOURCE_ID,
                            COURT_ID,
                            f"{case_number}{suffix}",
                            record_kind,
                            selector,
                        ),
                    }
                )
            result = PublicRecordsResult.success(
                query,
                [detail] if detail else [],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "attorney-profile":
            attorney_number = _attorney_number(args.attorney_number)
            query = _query(
                "attorney-profile",
                {"attorney_number": attorney_number},
            )
            url = (
                urljoin(NETDATA_BASE_URL, "PBAttyForm.ndm/ATTY_FORM")
                + "?string="
                + attorney_number
            )
            detail = source_client.detail(
                url,
                record_kind="probate_attorney_profile",
            )
            result = PublicRecordsResult.success(
                query,
                [detail] if detail else [],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            query = _query("probe", {"sentinel_case_number": PROBE_CASE_NUMBER})
            landing = source_client.landing()
            number_url = _index_url("number", f"{PROBE_CASE_NUMBER}!=")
            page = source_client.index_page("number", number_url)
            matches = _matching_number_rows(
                page.records,
                case_number=PROBE_CASE_NUMBER,
                suffix="",
            )
            if not matches or not isinstance(matches[0].get("detail_url"), str):
                raise FranklinProbateSourceChanged(
                    "probe_case_missing",
                    "Franklin Probate sentinel case is absent from exact-number search",
                )
            detail = source_client.detail(
                str(matches[0]["detail_url"]),
                record_kind="probate_case",
            )
            if detail is None:
                raise FranklinProbateSourceChanged(
                    "probe_case_detail_missing",
                    "Franklin Probate sentinel detail is unavailable",
                )
            docket = source_client.docket(PROBE_CASE_NUMBER, "")
            fiduciaries = source_client.fiduciaries(PROBE_CASE_NUMBER, "")
            if not docket or not fiduciaries:
                raise FranklinProbateSourceChanged(
                    "probe_related_records_missing",
                    "Franklin Probate sentinel lacks its known docket or fiduciaries",
                )
            fid_number = str(fiduciaries[0]["fiduciary_number"])
            selector = _person_selector(PROBE_CASE_NUMBER, "", fid_number)
            fid_detail = source_client.detail(
                _detail_url("PBFidDetail.ndm/FID_DETAIL", selector),
                record_kind="probate_fiduciary_detail",
            )
            attorney_detail = source_client.detail(
                _detail_url("PBAttyDetail.ndm/ATTY_DETAIL", selector),
                record_kind="probate_attorney_detail",
            )
            if fid_detail is None or attorney_detail is None:
                raise FranklinProbateSourceChanged(
                    "probe_person_detail_missing",
                    "Franklin Probate sentinel person detail is unavailable",
                )
            probe = {
                "record_kind": "source_probe",
                "source_id": SOURCE_ID,
                "status": "available",
                "sentinel_case_number": PROBE_CASE_NUMBER,
                "sentinel_case_name": detail.get("case_name"),
                "sentinel_status_code": matches[0].get("status_code"),
                "sentinel_docket_records": len(docket),
                "sentinel_fiduciaries": len(fiduciaries),
                "sentinel_fiduciary_number": fid_number,
                "sentinel_attorney_number": attorney_detail.get("attorney_number"),
                "landing_search_methods": len(landing["search_methods"]),
                "routes_exercised": [
                    "official_landing",
                    "exact_case_number",
                    "case_type_detail",
                    "docket",
                    "fiduciaries",
                    "fiduciary_detail",
                    "attorney_detail",
                ],
                "request_count": source_client.request_count,
                "literal_person_selector": selector,
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise FranklinProbateSelectionError(
                "unknown_command",
                "Unknown Franklin Probate command",
                details={"command": args.command},
            )
    except FranklinProbatePartialCollection as partial:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [partial.error.to_contract_error()],
            records=partial.records,
            next_cursor=partial.next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    except FranklinProbateError as error:
        result = _failure(query, error)
    finally:
        if client is None:
            source_client.close()
    return result


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_RETRIES,
    )


def _add_window_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Return this many rows and emit a source-page continuation if more remain",
    )
    parser.add_argument(
        "--cursor",
        help="Resume a prior query-bound NetData page-and-row continuation",
    )


def _add_case_selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("case_number")
    parser.add_argument("--suffix", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Franklin County Probate Court's official case index"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show verified routes, selector grammar, and source boundaries",
    )
    add_output_args(source)

    landing = subparsers.add_parser(
        "landing",
        help="Fetch the official landing's current methods and notices",
    )
    add_output_args(landing)

    for command, help_text in (
        ("name", "Browse the case-name index from a source-native name key"),
        ("attorney", "Browse the attorney-name index"),
        ("fiduciary", "Browse cases by fiduciary name"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("term", type=_nonblank)
        _add_window_args(child)
        add_output_args(child)

    number = subparsers.add_parser(
        "number",
        help="Look up an exact case number and optional suffix",
    )
    _add_case_selector_args(number)
    _add_window_args(number)
    add_output_args(number)

    opened = subparsers.add_parser(
        "opened",
        help="Browse cases opened on a source-native date",
    )
    opened.add_argument("open_date")
    _add_window_args(opened)
    add_output_args(opened)

    case_type = subparsers.add_parser(
        "type",
        help="Browse a case type and optional subtype",
    )
    case_type.add_argument("case_type", choices=sorted(CASE_TYPES))
    case_type.add_argument("--subtype", default="")
    _add_window_args(case_type)
    add_output_args(case_type)

    case = subparsers.add_parser(
        "case",
        help="Resolve exact-number results to type-specific case detail",
    )
    _add_case_selector_args(case)
    add_output_args(case)

    docket = subparsers.add_parser(
        "docket",
        help="Fetch a case docket with wrapped source rows retained",
    )
    _add_case_selector_args(docket)
    add_output_args(docket)

    fiduciaries = subparsers.add_parser(
        "fiduciaries",
        help="Fetch a case's fiduciaries and linked attorneys",
    )
    _add_case_selector_args(fiduciaries)
    add_output_args(fiduciaries)

    for command, help_text in (
        ("fiduciary-detail", "Fetch one case fiduciary detail row"),
        ("attorney-detail", "Fetch the attorney linked to one fiduciary row"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        _add_case_selector_args(child)
        child.add_argument("fiduciary_number")
        add_output_args(child)

    attorney_profile = subparsers.add_parser(
        "attorney-profile",
        help="Fetch an attorney profile by source attorney number",
    )
    attorney_profile.add_argument("attorney_number")
    add_output_args(attorney_profile)

    probe = subparsers.add_parser(
        "probe",
        help="Exercise landing, exact case, detail, docket, and person routes",
    )
    add_output_args(probe)

    for command in subparsers.choices.values():
        _add_transport_args(command)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Franklin Probate {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Franklin Probate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("case_number")
            or record.get("attorney_number")
            or record.get("record_kind")
        )
        name = (
            record.get("case_name")
            or record.get("attorney_name")
            or record.get("description")
        )
        print(f"- {label}" + (f" | {name}" if name else ""))
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
