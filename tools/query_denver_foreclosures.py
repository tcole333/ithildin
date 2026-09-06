#!/usr/bin/env python3
"""Query Denver Public Trustee GTS foreclosure records and documents.

The official portal is an ASP.NET WebForms application. Search pagination,
case selection, detail tabs, and document retrieval must stay in one persistent
session because the selected foreclosure is stored server-side.

Examples:
    uv run python tools/query_denver_foreclosures.py search \
        --foreclosure-number 2026-000418 --output /tmp/denver-fc.json
    uv run python tools/query_denver_foreclosures.py search \
        --grantor "Santa Fe Drive" --limit 25 --json
    uv run python tools/query_denver_foreclosures.py search \
        --show-all --limit 100 --json
    uv run python tools/query_denver_foreclosures.py detail 2026-000418 --json
    uv run python tools/query_denver_foreclosures.py documents \
        2026-000418 --json
    uv run python tools/query_denver_foreclosures.py download \
        2026-000418 DOCUMENT_ID --destination /tmp/document.pdf --json
    uv run python tools/query_denver_foreclosures.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

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
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_property_ref
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
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-co-denver-public-trustee-gts"
STATE_CODE = "CO"
COUNTY_GEOID = "08031"
BASE_URL = "https://denvergov.org"
SEARCH_PATH = "/foreclosuresearch/default"
DETAIL_PATH = "/foreclosuresearch/foreclosure"
DOCUMENT_PATH = "/foreclosuresearch/docviewer"
SEARCH_URL = (
    f"{BASE_URL}{SEARCH_PATH}?AspxAutoDetectCookieSupport=1"
)
DETAIL_URL = f"{BASE_URL}{DETAIL_PATH}"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_PROBE_FORECLOSURE = "2026-000418"
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

FORM_PREFIX = "ctl00$ctl00$MainContent$CustomContentPlaceHolder$"
SEARCH_FIELDS = {
    "foreclosure_number": f"{FORM_PREFIX}txtForeclosureNumber",
    "grantor": f"{FORM_PREFIX}txtGrantorsName",
    "owner": f"{FORM_PREFIX}txtOwersName",
    "zip_code": f"{FORM_PREFIX}txtZipCode",
    "street": f"{FORM_PREFIX}txtStreet",
    "subdivision": f"{FORM_PREFIX}txtSubdivision",
    "status": f"{FORM_PREFIX}ddStatus",
    "ned_from": f"{FORM_PREFIX}txtNedDate1",
    "ned_to": f"{FORM_PREFIX}txtNedDate2",
    "sold_from": f"{FORM_PREFIX}txtSoldDate1",
    "sold_to": f"{FORM_PREFIX}txtSoldDate2",
    "sale_from": f"{FORM_PREFIX}txtCurrentScheduledSaleDateFrom",
    "sale_to": f"{FORM_PREFIX}txtCurrentScheduledSaleDateTo",
    "expedited": f"{FORM_PREFIX}ddlExpedited",
}
SEARCH_BUTTON = f"{FORM_PREFIX}btnSearch"
SHOW_ALL_BUTTON = f"{FORM_PREFIX}btnShowAll"
EXPECTED_SEARCH_HEADERS = (
    "FC #",
    "Grantor",
    "Street",
    "Zip",
    "Subdivision",
    "Balance Due",
    "Sale Date",
)
EXPECTED_DETAIL_SECTIONS = (
    "Address",
    "Bankruptcy",
    "Basics",
    "Cure",
    "Deed",
    "Law Firm",
    "Mailings",
    "Publications",
    "Lienor Redemption",
    "Sale Information",
    "Withdrawal",
    "View Documents",
)
REQUIRED_HIDDEN_FIELDS = frozenset(
    {"__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"}
)
FORECLOSURE_NUMBER_RE = re.compile(r"^\d{4}-\d{5,8}$")
POSTBACK_RE = re.compile(r"__doPostBack\('([^']*)','([^']*)'\)")
CURSOR_RE = re.compile(
    r"^denver-gts:v1:page:(?P<page>\d+):offset:(?P<offset>\d+):"
    r"(?P<fingerprint>[0-9a-f]{12})$"
)

SOURCE_WARNINGS = (
    "A scheduled foreclosure sale or source status is not evidence that the "
    "sale occurred; use the deed, recorder, and sale fields for that question.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Denver Public Trustee GTS Foreclosure Search",
    source_role="county_public_trustee_foreclosure_cases_and_documents",
    base_url=SEARCH_URL,
    dataset_id="denver-public-trustee-gts",
    metadata={
        "authority": "City and County of Denver Clerk and Recorder",
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "authentication": "none",
        "platform_family": "gts_aspnet_webforms",
        "persistent_session_required": True,
        "native_identity_key": "public_trustee_number",
        "native_pagination": "webforms_postback",
        "document_route": DOCUMENT_PATH,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Denver County, Colorado",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Denver",
)


class DenverForeclosureSelectionError(ValueError):
    """A caller selector or cursor is invalid for the official source."""

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
class SearchForm:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    status_values: tuple[str, ...]
    expedited_values: tuple[str, ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class ForeclosureSearchRow:
    foreclosure_number: str
    grantor: str | None
    street: str | None
    zip_code: str | None
    subdivision: str | None
    balance_due_raw: str | None
    sale_date_raw: str | None
    detail_target: str
    source_page: int


@dataclass(frozen=True)
class SearchPage:
    html: str
    url: str
    action_url: str
    total_results: int
    current_page: int
    rows: tuple[ForeclosureSearchRow, ...]
    next_target: str | None
    schema_fingerprint: str


@dataclass(frozen=True)
class DetailGroup:
    heading: str
    fields: tuple[tuple[str, str | None], ...]
    tables: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "fields": [
                {"label": label, "value": value}
                for label, value in self.fields
            ],
            "tables": [dict(table) for table in self.tables],
        }


@dataclass(frozen=True)
class ForeclosureDocument:
    native_document_id: str
    native_filename: str
    source_url: str
    source_size_label: str | None
    source_size_bytes: int | None
    source_modified_at: str | None
    source_extension: str | None

    def to_dict(self, foreclosure_number: str) -> dict[str, Any]:
        canonical_ref = canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "foreclosure-document",
            f"{foreclosure_number}:{self.native_document_id}",
        )
        return {
            "canonical_ref": canonical_ref,
            "evidence_ref": canonical_ref,
            "source_id": SOURCE_ID,
            "record_kind": "document_artifact",
            "native_document_id": self.native_document_id,
            "identity_kind": "foreclosure_number_and_source_filename_sha256",
            "native_filename": self.native_filename,
            "source_url": self.source_url,
            "source_size_label": self.source_size_label,
            "source_size_bytes": self.source_size_bytes,
            "source_modified_at": self.source_modified_at,
            "source_extension": self.source_extension,
            "access_state": "public",
            "authentication": "none",
            "certification_status": "uncertified",
            "parent_foreclosure_number": foreclosure_number,
        }


@dataclass(frozen=True)
class DetailPage:
    html: str
    url: str
    foreclosure_number: str
    navigation: Mapping[str, str]
    groups: tuple[DetailGroup, ...]
    documents: tuple[ForeclosureDocument, ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class ForeclosureDetail:
    index_row: ForeclosureSearchRow
    sections: Mapping[str, DetailPage]

    @property
    def documents(self) -> tuple[ForeclosureDocument, ...]:
        page = self.sections.get("View Documents")
        return page.documents if page is not None else ()


@dataclass(frozen=True)
class DownloadedDocument:
    content: bytes
    source_url: str
    media_type: str
    filename: str | None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    normalized = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    return normalized or None


def _official_url(value: str, *, base: str = BASE_URL) -> str:
    parsed = urlparse(urljoin(base, value))
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in {
        "denvergov.org",
        "www.denvergov.org",
    }:
        raise SourceSchemaError(
            "Denver Public Trustee response left the official HTTPS host",
            url=base,
            details={"observed_host": hostname or None},
        )
    return urlunparse(("https", parsed.netloc, parsed.path, "", parsed.query, ""))


def _require_path(url: str, expected_path: str) -> str:
    safe_url = _official_url(url)
    if urlparse(safe_url).path.rstrip("/").casefold() != (
        expected_path.rstrip("/").casefold()
    ):
        raise SourceSchemaError(
            "Denver Public Trustee route changed",
            url=safe_url,
            details={
                "expected_path": expected_path,
                "observed_path": urlparse(safe_url).path,
            },
        )
    return safe_url


def _postback(href: str, *, url: str) -> tuple[str, str]:
    match = POSTBACK_RE.search(href)
    if not match or not match.group(1):
        raise SourceSchemaError(
            "Denver Public Trustee postback target is missing",
            url=url,
        )
    return match.group(1), match.group(2)


def _hidden_fields(soup: BeautifulSoup, *, url: str) -> dict[str, str]:
    values = {
        str(node.get("name")): str(node.get("value", ""))
        for node in soup.select('input[type="hidden"][name]')
    }
    missing = REQUIRED_HIDDEN_FIELDS - values.keys()
    if missing:
        raise SourceSchemaError(
            "Denver Public Trustee form state changed",
            url=url,
            details={"missing_hidden_field_names": sorted(missing)},
        )
    return values


def _form_action(
    soup: BeautifulSoup,
    *,
    base_url: str,
    expected_path: str,
) -> str:
    form = soup.select_one("form[method]")
    if not isinstance(form, Tag) or str(form.get("method", "")).casefold() != "post":
        raise SourceSchemaError(
            "Denver Public Trustee POST form is missing",
            url=base_url,
        )
    action = _official_url(str(form.get("action", "")), base=base_url)
    return _require_path(action, expected_path)


def _selected_controls(html: str, *, url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    controls = _hidden_fields(soup, url=url)
    for node in soup.select("input[name]"):
        kind = str(node.get("type", "text")).casefold()
        if kind in {"hidden", "submit", "button", "reset", "image", "file"}:
            continue
        if kind in {"checkbox", "radio"} and not node.has_attr("checked"):
            continue
        controls[str(node["name"])] = str(node.get("value", ""))
    for node in soup.select("select[name]"):
        selected = node.select_one("option[selected]") or node.select_one("option")
        controls[str(node["name"])] = (
            str(selected.get("value", "")) if selected is not None else ""
        )
    return controls


def parse_search_form(html: str, source_url: str) -> SearchForm:
    """Parse and validate the anonymous search form without exposing state."""
    safe_url = _require_path(source_url, SEARCH_PATH)
    soup = BeautifulSoup(html, "html.parser")
    hidden = _hidden_fields(soup, url=safe_url)
    action_url = _form_action(
        soup,
        base_url=safe_url,
        expected_path=SEARCH_PATH,
    )
    missing_fields = [
        field_name
        for field_name in SEARCH_FIELDS.values()
        if soup.select_one(f'[name="{field_name}"]') is None
    ]
    if missing_fields:
        raise SourceSchemaError(
            "Denver Public Trustee search controls changed",
            url=safe_url,
            details={"missing_control_names": missing_fields},
        )
    if soup.select_one(f'[name="{SEARCH_BUTTON}"]') is None:
        raise SourceSchemaError(
            "Denver Public Trustee search button changed",
            url=safe_url,
        )
    if soup.select_one(f'[name="{SHOW_ALL_BUTTON}"]') is None:
        raise SourceSchemaError(
            "Denver Public Trustee Show All button changed",
            url=safe_url,
        )
    status_values = tuple(
        str(option.get("value", ""))
        for option in soup.select(f'[name="{SEARCH_FIELDS["status"]}"] option')
    )
    expedited_values = tuple(
        str(option.get("value", ""))
        for option in soup.select(
            f'[name="{SEARCH_FIELDS["expedited"]}"] option'
        )
    )
    if not status_values or set(expedited_values) != {"-1", "0", "1"}:
        raise SourceSchemaError(
            "Denver Public Trustee search options changed",
            url=safe_url,
        )
    declared = {
        "form_path": SEARCH_PATH,
        "method": "post",
        "search_fields": sorted(SEARCH_FIELDS),
        "hidden_field_names": sorted(REQUIRED_HIDDEN_FIELDS),
        "status_values": list(status_values),
        "expedited_values": list(expedited_values),
    }
    return SearchForm(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        status_values=status_values,
        expedited_values=expedited_values,
        schema_fingerprint=schema_fingerprint(declared),
    )


def _parse_source_date(value: str | None) -> str | None:
    if value is None:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return value


def _parse_source_datetime(value: str | None) -> str | None:
    if value is None:
        return None
    for date_format in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
    ):
        try:
            return datetime.strptime(value, date_format).isoformat()
        except ValueError:
            continue
    return value


def _money(value: str | None) -> dict[str, str] | None:
    if value is None:
        return None
    candidate = value.replace("$", "").replace(",", "").strip()
    try:
        amount = Decimal(candidate)
    except InvalidOperation:
        return {"raw": value}
    return {"amount": format(amount, "f"), "currency": "USD", "raw": value}


def _source_size(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.fullmatch(r"([\d.]+)\s*([kmgt]?)", value.strip(), re.I)
    if not match:
        return None
    multiplier = {
        "": 1,
        "k": 1024,
        "m": 1024**2,
        "g": 1024**3,
        "t": 1024**4,
    }[match.group(2).casefold()]
    return int(Decimal(match.group(1)) * multiplier)


def _document_id(foreclosure_number: str, filename: str) -> str:
    return hashlib.sha256(
        f"{foreclosure_number}\0{filename}".encode()
    ).hexdigest()


def parse_search_page(html: str, source_url: str) -> SearchPage:
    """Parse one native search page and its next-page WebForms target."""
    safe_url = _require_path(source_url, SEARCH_PATH)
    soup = BeautifulSoup(html, "html.parser")
    action_url = _form_action(
        soup,
        base_url=safe_url,
        expected_path=SEARCH_PATH,
    )
    _hidden_fields(soup, url=safe_url)
    result_label = _clean(soup.select_one("[id$='_SearchResultsLabel']"))
    count_match = re.search(
        r"search returned\s+([\d,]+)\s+records?",
        result_label or "",
        re.I,
    )
    if not count_match:
        raise SourceSchemaError(
            "Denver Public Trustee result count marker changed",
            url=safe_url,
        )
    total = int(count_match.group(1).replace(",", ""))
    table = soup.select_one("[id$='_gvSearchResults']")
    if total == 0:
        if table is not None and table.select("td"):
            raise SourceSchemaError(
                "Denver Public Trustee reported zero results with rows",
                url=safe_url,
            )
        return SearchPage(
            html=html,
            url=safe_url,
            action_url=action_url,
            total_results=0,
            current_page=1,
            rows=(),
            next_target=None,
            schema_fingerprint=schema_fingerprint(
                {
                    "headers": list(EXPECTED_SEARCH_HEADERS),
                    "valid_empty": True,
                    "pager": "webforms_numeric",
                }
            ),
        )
    if not isinstance(table, Tag):
        raise SourceSchemaError(
            "Denver Public Trustee result table is missing",
            url=safe_url,
        )
    header_nodes = table.select("tr th")
    headers = tuple(_clean(node) or "" for node in header_nodes)
    if headers != EXPECTED_SEARCH_HEADERS:
        raise SourceSchemaError(
            "Denver Public Trustee result columns changed",
            url=safe_url,
            details={
                "expected_headers": list(EXPECTED_SEARCH_HEADERS),
                "observed_headers": list(headers),
            },
        )
    current_node = soup.select_one(
        "nav[aria-label='results pagination'] a[aria-current='page']"
    )
    current_text = _clean(current_node)
    if current_text is None:
        current_page = 1
    elif current_text.isdigit():
        current_page = int(current_text)
    else:
        raise SourceSchemaError(
            "Denver Public Trustee current-page marker changed",
            url=safe_url,
        )
    rows: list[ForeclosureSearchRow] = []
    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != len(EXPECTED_SEARCH_HEADERS):
            raise SourceSchemaError(
                "Denver Public Trustee result row width changed",
                url=safe_url,
                details={"observed_cell_count": len(cells)},
            )
        link = cells[0].select_one("a[href*='__doPostBack']")
        foreclosure_number = _clean(link)
        if not isinstance(link, Tag) or foreclosure_number is None:
            raise SourceSchemaError(
                "Denver Public Trustee result identity link changed",
                url=safe_url,
            )
        if not FORECLOSURE_NUMBER_RE.fullmatch(foreclosure_number):
            raise SourceSchemaError(
                "Denver Public Trustee returned an invalid foreclosure number",
                url=safe_url,
                details={"observed_identity": foreclosure_number},
            )
        target, _argument = _postback(str(link.get("href", "")), url=safe_url)
        values = [_clean(cell) for cell in cells]
        rows.append(
            ForeclosureSearchRow(
                foreclosure_number=foreclosure_number,
                grantor=values[1],
                street=values[2],
                zip_code=values[3],
                subdivision=values[4],
                balance_due_raw=values[5],
                sale_date_raw=values[6],
                detail_target=target,
                source_page=current_page,
            )
        )
    if not rows:
        raise SourceSchemaError(
            "Denver Public Trustee reported results without rows",
            url=safe_url,
        )
    next_target = None
    top_pager = soup.select_one(
        "nav[id$='_TopPagerNav'][aria-label='results pagination']"
    )
    pager_root = top_pager if isinstance(top_pager, Tag) else soup
    for link in pager_root.select("a[href*='__doPostBack']"):
        label = _clean(link)
        if label != str(current_page + 1):
            continue
        next_target, _argument = _postback(
            str(link.get("href", "")),
            url=safe_url,
        )
        break
    if len(rows) < total and next_target is None and current_page == 1:
        raise SourceSchemaError(
            "Denver Public Trustee pagination controls are missing",
            url=safe_url,
        )
    declared = {
        "headers": list(headers),
        "row_fields": list(ForeclosureSearchRow.__dataclass_fields__),
        "pager": "webforms_numeric_sliding_window",
    }
    return SearchPage(
        html=html,
        url=safe_url,
        action_url=action_url,
        total_results=total,
        current_page=current_page,
        rows=tuple(rows),
        next_target=next_target,
        schema_fingerprint=schema_fingerprint(declared),
    )


def _detail_navigation(soup: BeautifulSoup, *, url: str) -> dict[str, str]:
    navigation: dict[str, str] = {}
    for link in soup.select("nav a[href*='__doPostBack']"):
        label = _clean(link)
        if label is None:
            continue
        target, _argument = _postback(str(link.get("href", "")), url=url)
        navigation[label] = target
    missing = set(EXPECTED_DETAIL_SECTIONS) - navigation.keys()
    if missing:
        raise SourceSchemaError(
            "Denver Public Trustee detail navigation changed",
            url=url,
            details={"missing_section_labels": sorted(missing)},
        )
    return navigation


def _nearest_heading(node: Tag, container: Tag) -> str:
    heading = node.find_previous(["h2", "h3"])
    if isinstance(heading, Tag) and heading in container.descendants:
        return _clean(heading) or "Details"
    return "Details"


def _detail_groups(container: Tag) -> tuple[DetailGroup, ...]:
    headings = [
        _clean(node)
        for node in container.select("h2, h3")
        if _clean(node) is not None
    ]
    group_names = list(dict.fromkeys(headings)) or ["Details"]
    fields: dict[str, list[tuple[str, str | None]]] = {
        heading: [] for heading in group_names
    }
    tables: dict[str, list[Mapping[str, Any]]] = {
        heading: [] for heading in group_names
    }
    for term in container.select("dt"):
        label = _clean(term)
        definition = term.find_next_sibling("dd")
        if label is None:
            continue
        group = _nearest_heading(term, container)
        fields.setdefault(group, []).append((label, _clean(definition)))
    for table in container.select("table"):
        group = _nearest_heading(table, container)
        headers = tuple(_clean(node) or "" for node in table.select("thead th"))
        if not headers:
            first_row = table.select_one("tr")
            headers = (
                tuple(_clean(node) or "" for node in first_row.select("th"))
                if isinstance(first_row, Tag)
                else ()
            )
        row_values = []
        for row in table.select("tbody tr") or table.select("tr"):
            values = [_clean(node) for node in row.find_all("td", recursive=False)]
            if values:
                row_values.append(values)
        tables.setdefault(group, []).append(
            {"headers": list(headers), "rows": row_values}
        )
    all_groups = list(dict.fromkeys([*group_names, *fields, *tables]))
    return tuple(
        DetailGroup(
            heading=heading,
            fields=tuple(fields.get(heading, ())),
            tables=tuple(tables.get(heading, ())),
        )
        for heading in all_groups
    )


def _detail_documents(
    container: Tag,
    *,
    foreclosure_number: str,
    source_url: str,
) -> tuple[ForeclosureDocument, ...]:
    documents: list[ForeclosureDocument] = []
    seen: set[str] = set()
    for row in container.select("table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        link = cells[1].select_one("a[href*='docviewer?fn=']")
        if not isinstance(link, Tag):
            continue
        display_filename = _clean(link)
        if display_filename is None:
            raise SourceSchemaError(
                "Denver Public Trustee document filename is missing",
                url=source_url,
            )
        href = _official_url(str(link.get("href", "")), base=source_url)
        if urlparse(href).path.casefold() != DOCUMENT_PATH.casefold():
            raise SourceSchemaError(
                "Denver Public Trustee document route changed",
                url=source_url,
            )
        parameters = parse_qs(urlparse(href).query)
        native_filename = _clean((parameters.get("fn") or [None])[0])
        if native_filename is None:
            raise SourceSchemaError(
                "Denver Public Trustee document filename parameter changed",
                url=source_url,
            )
        if native_filename != display_filename:
            raise SourceSchemaError(
                "Denver Public Trustee document identity disagrees with its label",
                url=source_url,
                details={
                    "native_filename": native_filename,
                    "display_filename": display_filename,
                },
            )
        document_id = _document_id(foreclosure_number, native_filename)
        if document_id in seen:
            continue
        seen.add(document_id)
        suffix = Path(native_filename).suffix.casefold() or None
        size_label = _clean(cells[2])
        documents.append(
            ForeclosureDocument(
                native_document_id=document_id,
                native_filename=native_filename,
                source_url=href,
                source_size_label=size_label,
                source_size_bytes=_source_size(size_label),
                source_modified_at=_parse_source_datetime(_clean(cells[3])),
                source_extension=suffix,
            )
        )
    return tuple(documents)


def parse_detail_page(html: str, source_url: str) -> DetailPage:
    """Parse one WebForms detail section without returning session state."""
    safe_url = _require_path(source_url, DETAIL_PATH)
    soup = BeautifulSoup(html, "html.parser")
    _form_action(soup, base_url=safe_url, expected_path=DETAIL_PATH)
    _hidden_fields(soup, url=safe_url)
    text = _clean(soup) or ""
    number_match = re.search(
        r"Public Trustee Number:\s*(\d{4}-\d{5,8})",
        text,
        re.I,
    )
    if not number_match:
        raise SourceSchemaError(
            "Denver Public Trustee detail identity is missing",
            url=safe_url,
        )
    foreclosure_number = number_match.group(1)
    navigation = _detail_navigation(soup, url=safe_url)
    content = soup.select_one("section[aria-live]")
    if not isinstance(content, Tag):
        raise SourceSchemaError(
            "Denver Public Trustee detail content changed",
            url=safe_url,
        )
    groups = _detail_groups(content)
    documents = _detail_documents(
        content,
        foreclosure_number=foreclosure_number,
        source_url=safe_url,
    )
    declared = {
        "navigation": list(navigation),
        "groups": [
            {
                "heading": group.heading,
                "field_labels": [label for label, _value in group.fields],
                "table_headers": [
                    table.get("headers", []) for table in group.tables
                ],
            }
            for group in groups
        ],
        "document_fields": list(ForeclosureDocument.__dataclass_fields__),
    }
    return DetailPage(
        html=html,
        url=safe_url,
        foreclosure_number=foreclosure_number,
        navigation=navigation,
        groups=groups,
        documents=documents,
        schema_fingerprint=schema_fingerprint(declared),
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
    value = _response_header(response, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class DenverForeclosureClient:
    """Retrying, rate-limited, persistent-session WebForms client."""

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
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf",
            "Accept-Language": "en-US,en;q=0.8",
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
        referer: str | None = None,
    ) -> Any:
        safe_url = _official_url(url)
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            request_headers = dict(self.headers)
            if referer is not None:
                request_headers["Referer"] = _official_url(referer)
                request_headers["Origin"] = BASE_URL
            try:
                response = self.session.request(
                    method,
                    safe_url,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for redirect in [*getattr(response, "history", ()), response]:
                _official_url(str(getattr(redirect, "url", safe_url)))
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            if status == 429:
                raise RateLimitedHTTPError(status, url=safe_url)
            if status in {401, 403}:
                raise RestrictedHTTPError(status, url=safe_url)
            if status in {404, 410}:
                raise SourceChangedHTTPError(status, url=safe_url)
            if status < 200 or status >= 300:
                raise HTTPStatusError(status, url=safe_url)
            return response
        raise TransportError(
            "Denver Public Trustee request failed",
            url=safe_url,
            details={"error": str(last_error or "retry exhausted")},
        )

    def _get_form(self) -> SearchForm:
        response = self._request("GET", SEARCH_URL)
        content_type = (_response_header(response, "content-type") or "").casefold()
        if content_type and "html" not in content_type:
            raise SourceSchemaError(
                "Denver Public Trustee search returned non-HTML content",
                url=SEARCH_URL,
                details={"content_type": content_type},
            )
        return parse_search_form(
            str(response.text),
            str(getattr(response, "url", SEARCH_URL)),
        )

    def _post_html(
        self,
        *,
        page_html: str,
        page_url: str,
        action_url: str,
        controls: Mapping[str, str] | None = None,
        event_target: str | None = None,
        event_argument: str = "",
        submit_name: str | None = None,
        submit_value: str = "",
    ) -> tuple[str, str]:
        data = _selected_controls(page_html, url=page_url)
        data.update(controls or {})
        if event_target is not None:
            data["__EVENTTARGET"] = event_target
            data["__EVENTARGUMENT"] = event_argument
        if submit_name is not None:
            data[submit_name] = submit_value
        response = self._request(
            "POST",
            action_url,
            data=data,
            referer=page_url,
        )
        content_type = (_response_header(response, "content-type") or "").casefold()
        if content_type and "html" not in content_type:
            raise SourceSchemaError(
                "Denver Public Trustee postback returned non-HTML content",
                url=action_url,
                details={"content_type": content_type},
            )
        return str(response.text), str(getattr(response, "url", action_url))

    def start_search(
        self,
        criteria: Mapping[str, str],
        *,
        show_all: bool,
        form: SearchForm | None = None,
    ) -> SearchPage:
        form = form or self._get_form()
        if criteria.get("status") not in {None, "", *form.status_values}:
            raise DenverForeclosureSelectionError(
                "invalid_status",
                "the requested foreclosure status is not offered by the source",
                details={"status": criteria.get("status")},
            )
        controls = {
            SEARCH_FIELDS[key]: value
            for key, value in criteria.items()
            if key in SEARCH_FIELDS
        }
        html, url = self._post_html(
            page_html=form.html,
            page_url=form.url,
            action_url=form.action_url,
            controls=controls,
            submit_name=SHOW_ALL_BUTTON if show_all else SEARCH_BUTTON,
            submit_value="Show All" if show_all else "Search",
        )
        return parse_search_page(html, url)

    def next_page(self, page: SearchPage) -> SearchPage:
        if page.next_target is None:
            raise DenverForeclosureSelectionError(
                "cursor_past_end",
                "cursor points beyond the final source page",
            )
        html, url = self._post_html(
            page_html=page.html,
            page_url=page.url,
            action_url=page.action_url,
            event_target=page.next_target,
        )
        next_page = parse_search_page(html, url)
        if next_page.current_page != page.current_page + 1:
            raise SourceSchemaError(
                "Denver Public Trustee pagination did not advance",
                url=page.url,
                details={
                    "previous_page": page.current_page,
                    "observed_page": next_page.current_page,
                },
            )
        if next_page.total_results != page.total_results:
            raise SourceSchemaError(
                "Denver Public Trustee result total changed during pagination",
                url=page.url,
                details={
                    "previous_total": page.total_results,
                    "observed_total": next_page.total_results,
                },
            )
        return next_page

    def search(
        self,
        criteria: Mapping[str, str],
        *,
        show_all: bool,
        limit: int | None,
        cursor: str | None,
    ) -> tuple[
        list[ForeclosureSearchRow],
        str | None,
        SearchPage,
        int,
    ]:
        target_page, target_offset = _parse_cursor(
            cursor,
            criteria,
            show_all=show_all,
        )
        page = self.start_search(criteria, show_all=show_all)
        rows_before_target = 0
        while page.current_page < target_page:
            rows_before_target += len(page.rows)
            page = self.next_page(page)
        if page.current_page != target_page:
            raise DenverForeclosureSelectionError(
                "cursor_past_end",
                "cursor points beyond the final source page",
            )
        if target_offset > len(page.rows):
            raise DenverForeclosureSelectionError(
                "cursor_past_page",
                "cursor offset points beyond its source page",
                details={
                    "page": target_page,
                    "offset": target_offset,
                    "row_count": len(page.rows),
                },
            )
        if target_offset == len(page.rows) and page.next_target is not None:
            rows_before_target += len(page.rows)
            page = self.next_page(page)
            target_offset = 0

        selected: list[ForeclosureSearchRow] = []
        seen: dict[str, ForeclosureSearchRow] = {}
        current_offset = target_offset
        while True:
            for row in page.rows[current_offset:]:
                prior = seen.get(row.foreclosure_number)
                if prior is not None:
                    raise SourceSchemaError(
                        "Denver Public Trustee repeated an identity during pagination",
                        url=page.url,
                        details={"foreclosure_number": row.foreclosure_number},
                    )
                seen[row.foreclosure_number] = row
                if limit is not None and len(selected) >= limit:
                    break
                selected.append(row)
                current_offset += 1
                if limit is not None and len(selected) >= limit:
                    break
            if limit is not None and len(selected) >= limit:
                break
            if page.next_target is None:
                break
            page = self.next_page(page)
            current_offset = 0

        next_cursor = None
        if limit is not None and len(selected) >= limit:
            if current_offset < len(page.rows):
                next_cursor = _cursor(
                    criteria,
                    show_all=show_all,
                    page=page.current_page,
                    offset=current_offset,
                )
            elif page.next_target is not None:
                next_cursor = _cursor(
                    criteria,
                    show_all=show_all,
                    page=page.current_page + 1,
                    offset=0,
                )
        if next_cursor is None and page.next_target is None:
            consumed = rows_before_target + target_offset + len(selected)
            if consumed != page.total_results:
                raise SourceSchemaError(
                    "Denver Public Trustee traversal did not reconcile to the source total",
                    url=page.url,
                    details={
                        "source_total": page.total_results,
                        "consumed_records": consumed,
                    },
                )
        return selected, next_cursor, page, rows_before_target + target_offset

    def _find_foreclosure(
        self,
        foreclosure_number: str,
    ) -> tuple[ForeclosureSearchRow, SearchPage] | None:
        criteria = {"foreclosure_number": foreclosure_number}
        page = self.start_search(criteria, show_all=False)
        while True:
            exact = [
                row
                for row in page.rows
                if row.foreclosure_number.casefold()
                == foreclosure_number.casefold()
            ]
            if len(exact) > 1:
                raise SourceSchemaError(
                    "Denver Public Trustee returned duplicate exact identities",
                    url=page.url,
                    details={"foreclosure_number": foreclosure_number},
                )
            if exact:
                return exact[0], page
            if page.next_target is None:
                return None
            page = self.next_page(page)

    def detail(self, foreclosure_number: str) -> ForeclosureDetail | None:
        located = self._find_foreclosure(foreclosure_number)
        if located is None:
            return None
        index_row, search_page = located
        html, url = self._post_html(
            page_html=search_page.html,
            page_url=search_page.url,
            action_url=search_page.action_url,
            event_target=index_row.detail_target,
        )
        page = parse_detail_page(html, url)
        if page.foreclosure_number != foreclosure_number:
            raise SourceSchemaError(
                "Denver Public Trustee opened a different foreclosure detail",
                url=page.url,
                details={
                    "requested": foreclosure_number,
                    "observed": page.foreclosure_number,
                },
            )
        sections: dict[str, DetailPage] = {"Address": page}
        current = page
        for label in page.navigation:
            if label == "Address":
                continue
            html, url = self._post_html(
                page_html=current.html,
                page_url=current.url,
                action_url=DETAIL_URL,
                event_target=current.navigation[label],
            )
            current = parse_detail_page(html, url)
            if current.foreclosure_number != foreclosure_number:
                raise SourceSchemaError(
                    "Denver Public Trustee detail identity changed between sections",
                    url=current.url,
                )
            sections[label] = current
        return ForeclosureDetail(index_row=index_row, sections=sections)

    def download(self, source_url: str) -> DownloadedDocument:
        safe_url = _require_path(source_url, DOCUMENT_PATH)
        response = self._request("GET", safe_url, referer=DETAIL_URL)
        content = bytes(response.content)
        content_type = (
            _response_header(response, "content-type") or ""
        ).split(";", 1)[0].strip().casefold()
        if content_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "Denver Public Trustee document route did not return a PDF",
                url=safe_url,
                details={"content_type": content_type or None},
            )
        disposition = _response_header(response, "content-disposition") or ""
        filename_match = re.search(
            r"filename\*?=(?:UTF-8''|)(?:\"([^\"]+)\"|([^;]+))",
            disposition,
            re.I,
        )
        filename = (
            (filename_match.group(1) or filename_match.group(2)).strip()
            if filename_match
            else None
        )
        return DownloadedDocument(
            content=content,
            source_url=str(getattr(response, "url", safe_url)),
            media_type="application/pdf",
            filename=filename,
        )

    def probe(self, foreclosure_number: str) -> dict[str, Any]:
        form = self._get_form()
        show_all_page = self.start_search({}, show_all=True, form=form)
        detail = self.detail(foreclosure_number)
        if detail is None:
            raise SourceSchemaError(
                "Denver Public Trustee probe foreclosure is missing",
                url=SEARCH_URL,
                details={"foreclosure_number": foreclosure_number},
            )
        schema_fingerprints = {
            "form": form.schema_fingerprint,
            "search": show_all_page.schema_fingerprint,
            **{
                label: page.schema_fingerprint
                for label, page in detail.sections.items()
            },
        }
        return {
            "canonical_ref": canonical_property_ref(
                SOURCE_ID,
                COUNTY_GEOID,
                "source-health",
                f"probe:{foreclosure_number}",
            ),
            "source_id": SOURCE_ID,
            "record_kind": "source_health_check",
            "native_document_id": f"probe:{foreclosure_number}",
            "source_url": SEARCH_URL,
            "foreclosure_number": foreclosure_number,
            "persistent_session_required": True,
            "form_action": urlparse(form.action_url).path,
            "form_method": "post",
            "search_fields": list(SEARCH_FIELDS),
            "status_option_count": len(form.status_values) - 1,
            "source_reported_total_results": show_all_page.total_results,
            "native_page_size": len(show_all_page.rows),
            "detail_sections": list(detail.sections),
            "document_count": len(detail.documents),
            "schema_fingerprints": schema_fingerprints,
            "schema_fingerprint": sha256_fingerprint(schema_fingerprints),
        }


def _criteria_from_args(args: argparse.Namespace) -> tuple[dict[str, str], bool]:
    criteria: dict[str, str] = {}
    for key in SEARCH_FIELDS:
        value = getattr(args, key, None)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            criteria[key] = normalized
    if "expedited" in criteria:
        criteria["expedited"] = {
            "either": "-1",
            "no": "0",
            "yes": "1",
        }.get(criteria["expedited"].casefold(), criteria["expedited"])
    for key in (
        "ned_from",
        "ned_to",
        "sold_from",
        "sold_to",
        "sale_from",
        "sale_to",
    ):
        value = criteria.get(key)
        if value is None:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as error:
            raise DenverForeclosureSelectionError(
                "invalid_date",
                f"--{key.replace('_', '-')} must use YYYY-MM-DD",
                details={"field": key, "value": value},
            ) from error
    show_all = bool(getattr(args, "show_all", False))
    if show_all and criteria:
        raise DenverForeclosureSelectionError(
            "conflicting_search_selection",
            "--show-all cannot be combined with search criteria",
        )
    if not show_all and not criteria:
        raise DenverForeclosureSelectionError(
            "search_criteria_required",
            "provide at least one search criterion or --show-all",
        )
    return criteria, show_all


def _validate_foreclosure_number(value: str) -> str:
    normalized = value.strip()
    if not FORECLOSURE_NUMBER_RE.fullmatch(normalized):
        raise DenverForeclosureSelectionError(
            "invalid_foreclosure_number",
            "foreclosure number must use the source format YYYY-NNNNNN",
            details={"value": normalized},
        )
    return normalized


def _cursor_fingerprint(
    criteria: Mapping[str, str],
    *,
    show_all: bool,
) -> str:
    return sha256_fingerprint(
        {"criteria": dict(sorted(criteria.items())), "show_all": show_all}
    )[:12]


def _parse_cursor(
    cursor: str | None,
    criteria: Mapping[str, str],
    *,
    show_all: bool,
) -> tuple[int, int]:
    if cursor is None:
        return 1, 0
    match = CURSOR_RE.fullmatch(cursor)
    if not match:
        raise DenverForeclosureSelectionError(
            "invalid_cursor",
            "cursor is not a Denver Public Trustee continuation cursor",
        )
    if match.group("fingerprint") != _cursor_fingerprint(
        criteria,
        show_all=show_all,
    ):
        raise DenverForeclosureSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to a different foreclosure search",
        )
    page = int(match.group("page"))
    offset = int(match.group("offset"))
    if page < 1 or offset < 0:
        raise DenverForeclosureSelectionError(
            "invalid_cursor",
            "cursor contains an invalid source position",
        )
    return page, offset


def _cursor(
    criteria: Mapping[str, str],
    *,
    show_all: bool,
    page: int,
    offset: int,
) -> str:
    return (
        f"denver-gts:v1:page:{page}:offset:{offset}:"
        f"{_cursor_fingerprint(criteria, show_all=show_all)}"
    )


def _case_ref(foreclosure_number: str) -> str:
    return canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "foreclosure-case",
        foreclosure_number,
    )


def _jurisdiction_payload() -> dict[str, Any]:
    return {
        "geoid": COUNTY_GEOID,
        "name": "Denver County, Colorado",
        "state_code": STATE_CODE,
        "county_fips": COUNTY_GEOID,
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_system": "Denver Public Trustee GTS foreclosure portal",
        "record_scope": (
            "public-trustee foreclosure workflow, debt, sale, reception-number, "
            "and public source-document fields"
        ),
        "complementary_join_fields": [
            "street_address",
            "zip_code",
            "legal_description",
            "reception_number",
            "foreclosure_number",
        ],
    }


def normalize_search_row(
    row: ForeclosureSearchRow,
    *,
    schema_value: str,
) -> dict[str, Any]:
    canonical_ref = _case_ref(row.foreclosure_number)
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "record_kind": "foreclosure_case",
        "record_scope": "index",
        "native_id": row.foreclosure_number,
        "native_foreclosure_number": row.foreclosure_number,
        "foreclosure_number": row.foreclosure_number,
        "identity_kind": "public_trustee_number",
        "jurisdiction": _jurisdiction_payload(),
        "grantor_names_raw": row.grantor,
        "property": {
            "street_address": row.street,
            "zip_code": row.zip_code,
            "subdivision": row.subdivision,
        },
        "balance_due": _money(row.balance_due_raw),
        "scheduled_sale_date": _parse_source_date(row.sale_date_raw),
        "scheduled_sale_date_raw": row.sale_date_raw,
        "native_status": None,
        "source_url": SEARCH_URL,
        "detail_access": {
            "source_url": DETAIL_URL,
            "persistent_session_required": True,
            "access_state": "public",
        },
        "documents": [],
        "source_page": row.source_page,
        "source_scope": _source_scope(),
        "schema_fingerprint": schema_value,
    }


def _group_fields(
    detail: ForeclosureDetail,
    section_label: str,
    heading: str,
) -> dict[str, str | None]:
    page = detail.sections.get(section_label)
    if page is None:
        return {}
    for group in page.groups:
        if group.heading.casefold() == heading.casefold():
            return {label: value for label, value in group.fields}
    return {}


def _party(role: str, raw_name: str | None) -> dict[str, Any] | None:
    if raw_name is None:
        return None
    return {"role": role, "raw_name": raw_name}


def normalize_detail(
    detail: ForeclosureDetail,
    *,
    documents_only: bool = False,
) -> dict[str, Any]:
    fingerprints = {
        label: page.schema_fingerprint
        for label, page in detail.sections.items()
    }
    record = normalize_search_row(
        detail.index_row,
        schema_value=sha256_fingerprint(fingerprints),
    )
    property_fields = _group_fields(detail, "Address", "Property")
    owner_fields = _group_fields(detail, "Address", "Current Owner")
    basics = _group_fields(detail, "Basics", "Basics")
    deed_of_trust = _group_fields(detail, "Basics", "Deed of Trust")
    loan = _group_fields(detail, "Basics", "Loan Information")
    deed = _group_fields(detail, "Deed", "Deed")
    withdrawal = _group_fields(detail, "Withdrawal", "Withdrawal")
    law_firm = _group_fields(detail, "Law Firm", "Law Firm")
    sale_heading = next(
        (
            group.heading
            for group in detail.sections["Sale Information"].groups
            if group.heading.startswith("Sale Information")
        ),
        "Sale Information",
    )
    sale = _group_fields(detail, "Sale Information", sale_heading)
    documents = [
        document.to_dict(detail.index_row.foreclosure_number)
        for document in detail.documents
    ]
    if documents_only:
        return {
            **record,
            "record_scope": "documents",
            "documents": documents,
            "document_count": len(documents),
            "detail_schema_fingerprints": fingerprints,
        }

    recorded_instruments = []
    instrument_candidates = (
        ("notice_of_election_and_demand", basics.get("NED Reception #"), basics.get("NED Recorded Date")),
        ("deed_of_trust", deed_of_trust.get("Reception #"), deed_of_trust.get("Recorded Date")),
        ("public_trustee_deed", deed.get("Reception Number"), deed.get("Recorded Date")),
        ("withdrawal", withdrawal.get("Withdrawn Reception Number"), withdrawal.get("Withdrawn Date")),
        (
            "voided_withdrawal",
            withdrawal.get("Voided Withdrawal Reception Number"),
            withdrawal.get("Voided Withdrawal Date"),
        ),
    )
    for instrument_kind, reception_number, recorded_date in instrument_candidates:
        if reception_number:
            recorded_instruments.append(
                {
                    "instrument_kind": instrument_kind,
                    "reception_number": reception_number,
                    "recorded_date": _parse_source_date(recorded_date),
                    "recorded_date_raw": recorded_date,
                }
            )
    parties = [
        party
        for party in (
            _party("current_owner", owner_fields.get("Name")),
            _party("borrower_grantor", loan.get("Grantor (Borrower)")),
            _party("current_holder", loan.get("Current Holder")),
            _party(
                "original_beneficiary",
                loan.get("Grantee (Original Beneficiary)"),
            ),
            _party("foreclosure_law_firm", law_firm.get("Name")),
            _party("foreclosure_law_firm_contact", law_firm.get("Contact")),
        )
        if party is not None
    ]
    record.update(
        {
            "record_scope": "detail",
            "property": {
                **record["property"],
                "address_raw": property_fields.get("Address"),
                "subdivision": (
                    property_fields.get("Subdivision")
                    or record["property"].get("subdivision")
                ),
                "legal_description": property_fields.get("Legal Description"),
                "agricultural_raw": property_fields.get("Agricultural"),
            },
            "current_owner": {
                "raw_name": owner_fields.get("Name"),
                "address_raw": owner_fields.get("Address"),
            },
            "parties": parties,
            "dates": {
                "ned_recorded_date": _parse_source_date(
                    basics.get("NED Recorded Date")
                ),
                "originally_scheduled_sale_date": _parse_source_date(
                    basics.get("Originally Scheduled Sale Date")
                ),
                "currently_scheduled_sale_date": _parse_source_date(
                    basics.get("Currently Scheduled Sale Date")
                ),
                "file_received_date": _parse_source_date(
                    basics.get("Date File Received")
                ),
                "file_created_date": _parse_source_date(
                    basics.get("Date File Created")
                ),
                "date_sold": _parse_source_date(sale.get("Date Sold")),
            },
            "loan": {
                "type": loan.get("Type"),
                "original_principal_balance": _money(
                    loan.get("Original Principal Balance")
                ),
                "outstanding_principal_balance": _money(
                    loan.get("Outstanding Principal Balance")
                ),
                "outstanding_balance_as_of": _parse_source_date(
                    loan.get("Outstanding Principal Balance As Of Date")
                ),
                "interest_rate_raw": loan.get("Interest Rate"),
                "interest_type": loan.get("Interest Type"),
                "current_holder": loan.get("Current Holder"),
                "original_beneficiary": loan.get(
                    "Grantee (Original Beneficiary)"
                ),
                "borrower_grantor": loan.get("Grantor (Borrower)"),
            },
            "sale": {
                "scheduled_date": _parse_source_date(
                    basics.get("Currently Scheduled Sale Date")
                ),
                "holder_bid_amount": _money(
                    _group_fields(
                        detail,
                        "Sale Information",
                        "Initial Holder's Bid Information",
                    ).get("Amount")
                ),
                "successful_bid": _money(sale.get("Successful Bid at Sale")),
                "deficiency": _money(sale.get("Deficiency at Sale")),
                "overbid": _money(sale.get("Overbid at Sale")),
                "source_fields": sale,
            },
            "recorded_instruments": recorded_instruments,
            "law_firm": law_firm,
            "documents": documents,
            "document_count": len(documents),
            "source_sections": {
                label: [group.to_dict() for group in page.groups]
                for label, page in detail.sections.items()
            },
            "detail_schema_fingerprints": fingerprints,
        }
    )
    return record


def build_query(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            key: getattr(args, key, None)
            for key in SEARCH_FIELDS
            if getattr(args, key, None) is not None
        }
        parameters["show_all"] = bool(args.show_all)
        requested_limit = args.limit
        cursor = args.cursor
    elif args.command in {"detail", "documents", "download"}:
        parameters = {"foreclosure_number": args.foreclosure_number}
        if args.command == "download":
            parameters.update(
                {
                    "document_id": args.document_id,
                    "destination": str(args.destination),
                }
            )
    elif args.command == "probe":
        parameters = {"foreclosure_number": args.foreclosure_number}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={"access_decision": dict(access_decision or {})},
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
        decision = dict(error.decision)
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
                code="catalog_unavailable",
                message=str(error),
                category="access",
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
                details=dict(decision),
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: DenverForeclosureSelectionError,
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


def _execute_command(
    args: argparse.Namespace,
    client: DenverForeclosureClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "search":
        criteria, show_all = _criteria_from_args(args)
        rows, next_cursor, page, _skipped = client.search(
            criteria,
            show_all=show_all,
            limit=args.limit,
            cursor=args.cursor,
        )
        records = [
            normalize_search_row(row, schema_value=page.schema_fingerprint)
            for row in rows
        ]
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command in {"detail", "documents", "download"}:
        foreclosure_number = _validate_foreclosure_number(
            args.foreclosure_number
        )
        detail = client.detail(foreclosure_number)
        if detail is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        if args.command == "detail":
            return PublicRecordsResult.success(
                query,
                [normalize_detail(detail)],
                warnings=SOURCE_WARNINGS,
            )
        if args.command == "documents":
            return PublicRecordsResult.success(
                query,
                [normalize_detail(detail, documents_only=True)],
                warnings=SOURCE_WARNINGS,
            )
        document = next(
            (
                item
                for item in detail.documents
                if item.native_document_id == args.document_id
            ),
            None,
        )
        if document is None:
            raise DenverForeclosureSelectionError(
                "document_not_found",
                "document ID is not present on the selected foreclosure",
                details={
                    "foreclosure_number": foreclosure_number,
                    "document_id": args.document_id,
                },
            )
        downloaded = client.download(document.source_url)
        destination = Path(args.destination).expanduser()
        if destination.exists() and not args.overwrite:
            raise DenverForeclosureSelectionError(
                "destination_exists",
                "destination exists; pass --overwrite to replace it",
                details={"destination": str(destination)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(downloaded.content)
        record = document.to_dict(foreclosure_number)
        record.update(
            {
                "retrieved_filename": downloaded.filename,
                "mime_type": downloaded.media_type,
                "size": len(downloaded.content),
                "sha256": hashlib.sha256(downloaded.content).hexdigest(),
                "storage_path": str(destination.resolve()),
                "source_url": downloaded.source_url,
            }
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=(str(destination.resolve()),),
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        foreclosure_number = _validate_foreclosure_number(
            args.foreclosure_number
        )
        return PublicRecordsResult.success(
            query,
            [client.probe(foreclosure_number)],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: DenverForeclosureClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source operation through the shared public-record contract."""
    provisional_query = build_query(args, access_decision=access_decision)
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
        result = _access_failure(provisional_query, error)
        if log_results:
            log_search(
                canonical_json(provisional_query.to_dict()),
                SOURCE_ID,
                None,
            )
        return result
    query = build_query(args, access_decision=decision)
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    limits = decision.get("limits") or {}
    catalog_interval = float(limits.get("minimum_interval_seconds") or 0)
    source_client = client or DenverForeclosureClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        rate_limiter=MinimumIntervalRateLimiter(
            max(args.minimum_interval, catalog_interval)
        ),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except DenverForeclosureSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
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
        summary=f"Denver Public Trustee {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Denver Public Trustee {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "foreclosure_case":
            print(
                f"  {record.get('foreclosure_number') or '?'} | "
                f"{record.get('scheduled_sale_date') or '?'} | "
                f"{record.get('grantor_names_raw') or '?'}"
            )
        elif record.get("record_kind") == "document_artifact":
            print(
                f"  {record.get('native_document_id') or '?'} | "
                f"{record.get('native_filename') or '?'}"
            )
        else:
            print(
                f"  probe | {record.get('source_reported_total_results')} "
                f"records | {record.get('native_page_size')} per page"
            )
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


def _add_case_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("foreclosure_number")
    _add_runtime_and_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Denver Public Trustee foreclosure portal"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search foreclosure cases with native WebForms pagination",
    )
    search.add_argument("--foreclosure-number")
    search.add_argument("--grantor")
    search.add_argument("--owner")
    search.add_argument("--zip-code")
    search.add_argument("--street")
    search.add_argument("--subdivision")
    search.add_argument("--status")
    search.add_argument("--ned-from")
    search.add_argument("--ned-to")
    search.add_argument("--sold-from")
    search.add_argument("--sold-to")
    search.add_argument("--sale-from")
    search.add_argument("--sale-to")
    search.add_argument(
        "--expedited",
        choices=("either", "no", "yes"),
    )
    search.add_argument(
        "--show-all",
        action="store_true",
        help="Use the source's Show All operation",
    )
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-selected ceiling; omitted follows all source pages",
    )
    search.add_argument(
        "--cursor",
        help="Query-bound continuation cursor from a previous result",
    )
    _add_runtime_and_output(search)

    detail = subparsers.add_parser(
        "detail",
        help="Fetch every verified detail section for one foreclosure",
    )
    _add_case_selector(detail)

    documents = subparsers.add_parser(
        "documents",
        help="List public source documents for one foreclosure",
    )
    _add_case_selector(documents)

    download = subparsers.add_parser(
        "download",
        help="Download one listed document as returned by the source",
    )
    download.add_argument("foreclosure_number")
    download.add_argument("document_id")
    download.add_argument("--destination", type=Path, required=True)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify form, pagination, detail, and document-list contracts",
    )
    probe.add_argument(
        "--foreclosure-number",
        default=DEFAULT_PROBE_FORECLOSURE,
    )
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
