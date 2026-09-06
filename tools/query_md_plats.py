#!/usr/bin/env python3
"""Query Maryland State Archives PLATS.NET recorded plat records.

PLATS.NET is an anonymous ASP.NET WebForms application.  County search pages
publish the live form contract, a search POST stores criteria in the ASP.NET
session and returns a ``results.aspx`` location, and result continuation uses
the page's ``imgButtonNext`` postback.  Exact ``unit.aspx`` identities are
independently addressable by county, archive qualifier, series, and unit.

The adapter keeps five identities separate:

* the county and archive series/unit record identity;
* the court-facing book/page/plat reference printed on a result;
* the occurrence of that record in one bounded search;
* the search/detail representation observed at retrieval; and
* each compiled PDF, direct scan, or microfilm artifact.

Examples:
    uv run python tools/query_md_plats.py sources --json
    uv run python tools/query_md_plats.py counties --json
    uv run python tools/query_md_plats.py search MO --mode basic \
        --plat 21732 --limit 20 --output /tmp/md-plats.json
    uv run python tools/query_md_plats.py search MO --mode advanced \
        --description "Blair Estate" --sort date_desc --json
    uv run python tools/query_md_plats.py search MO --mode series \
        --qualifier C --series 1136 --unit 1 --json
    uv run python tools/query_md_plats.py plat MO C 1136 1 --json
    uv run python tools/query_md_plats.py download URL DESTINATION --json
    uv run python tools/query_md_plats.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import html as html_lib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

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
        MinimumIntervalRateLimiter,
        RetryPolicy,
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-md-plats"
STATE_CODE = "MD"
STATE_GEOID = "24"
SOURCE_NAME = "Maryland State Archives PLATS.NET"
BASE_URL = "https://plats.msa.maryland.gov"
INDEX_URL = f"{BASE_URL}/pages/index.aspx"
SEARCH_URL_TEMPLATE = f"{BASE_URL}/pages/plats.aspx?cid={{county_code}}"
UNIT_URL = f"{BASE_URL}/pages/unit.aspx"
FAQ_URL = f"{BASE_URL}/pages/faq.aspx"
ADVANCED_GUIDE_URL = (
    f"{BASE_URL}/pages/beginner.aspx?page=Advanced%20Search"
)
MDLANDREC_URL = "https://mdlandrec.net/"
MDP_DOWNLOADS_URL = (
    "https://planning.maryland.gov/MSDC/Pages/9_gam/"
    "district-download-gis-files.aspx"
)
MDP_PARCEL_POINTS_URL = (
    "https://mdgeodata.md.gov/imap/rest/services/"
    "PlanningCadastre/MD_PropertyData/MapServer/0"
)

OUTPUT_SCHEMA_VERSION = "maryland-plats/1.0"
FORM_CONTRACT_VERSION = "md-plats-webforms/1"
CURSOR_VERSION = 1
CURSOR_PREFIX = "md-plats:v1:"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_LIMIT: int | None = None
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

HIDDEN_FIELDS = (
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
)
RESULT_HEADERS = (
    "Date",
    "Description",
    "Reference",
    "Direct Scans",
    "Microfilm Scans",
    "Accession Number",
)
SORT_VALUES = {
    "date_desc": "rdate",
    "date_asc": "date",
    "accession_desc": "racc",
    "accession_asc": "acc",
    "description": "descript",
    "reference": "ref",
}
ARTIFACT_SUFFIXES = frozenset({".pdf", ".tif", ".tiff", ".jpg", ".jpeg"})
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
    "cf-chl-",
)

COUNTY_GEOIDS = {
    "AL": ("24001", "Allegany County"),
    "AA": ("24003", "Anne Arundel County"),
    "BC": ("24510", "Baltimore City"),
    "BA": ("24005", "Baltimore County"),
    "CV": ("24009", "Calvert County"),
    "CA": ("24011", "Caroline County"),
    "CR": ("24013", "Carroll County"),
    "CE": ("24015", "Cecil County"),
    "CH": ("24017", "Charles County"),
    "DO": ("24019", "Dorchester County"),
    "FR": ("24021", "Frederick County"),
    "GA": ("24023", "Garrett County"),
    "HA": ("24025", "Harford County"),
    "HO": ("24027", "Howard County"),
    "KE": ("24029", "Kent County"),
    "MO": ("24031", "Montgomery County"),
    "PG": ("24033", "Prince George's County"),
    "QA": ("24035", "Queen Anne's County"),
    "SM": ("24037", "St. Mary's County"),
    "SO": ("24039", "Somerset County"),
    "TA": ("24041", "Talbot County"),
    "WA": ("24043", "Washington County"),
    "WI": ("24045", "Wicomico County"),
    "WO": ("24047", "Worcester County"),
}

ACCESSION_RE = re.compile(
    r"^\s*MSA\s+(?P<qualifier>[A-Z]+)\s*(?P<series>\d+)"
    r"\s*-\s*(?P<unit>[A-Za-z0-9.-]+)\s*$",
    re.IGNORECASE,
)
UNIT_LINK_RE = re.compile(
    r"""unit\.aspx\?(?P<query>[^"'<>]+)""",
    re.IGNORECASE,
)
JS_TEST_RE = re.compile(
    r"""var\s+test\s*=\s*"(?P<value>(?:\\.|[^"\\])*)"\s*;""",
    re.IGNORECASE,
)
JS_WRITE_RE = re.compile(
    r"""document\.write\("(?P<value>(?:\\.|[^"\\])*)"\)""",
    re.IGNORECASE,
)
RESULT_BANNER_RE = re.compile(
    r"Displaying\s+(?P<start>[\d,]+)\s*-\s*(?P<end>[\d,]+)\s+of\s+"
    r"(?P<with_images>[\d,]+)\s+results\s+with\s+images\s+of\s+"
    r"(?P<total>[\d,]+)\s+total\s+records",
    re.IGNORECASE,
)
RESULT_BANNER_ALL_RE = re.compile(
    r"Displaying\s+(?P<start>[\d,]+)\s*-\s*(?P<end>[\d,]+)\s+of\s+"
    r"(?P<total>[\d,]+)\s+results",
    re.IGNORECASE,
)
SOURCE_DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
PATH_DATE_RE = re.compile(r"^/plats/(?P<date>\d{4}-\d{2}-\d{2})/")


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role="official_recorded_plat_archive",
    base_url=INDEX_URL,
    dataset_id="maryland-state-archives-plats",
    metadata={
        "authority": "Maryland State Archives",
        "coverage": "all 24 Maryland jurisdictions",
        "authentication": "none",
        "transport": {
            "search": "ASP.NET WebForms session and form POST",
            "results": "session-scoped results.aspx representation",
            "continuation": "imgButtonNext postback",
            "detail": "county, qualifier, series, and unit",
        },
        "artifact_formats": ["PDF", "TIFF", "JPEG"],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "A zero-scan result remains a PLATS.NET catalog record; its exact unit "
    "page can still publish date, description, reference, and accession metadata.",
    "PLATS.NET's compiled PDF and each direct or microfilm scan are retained "
    "as separate artifact representations.",
    "MDLandRec deeds and Maryland parcel, CAMA, and sales publications are "
    "separately attributed complements to the recorded plat.",
)

COMPLEMENTARY_SOURCES = (
    {
        "source_id": "us-md-land-records",
        "name": "Maryland Land Records and MDLandRec",
        "url": MDLANDREC_URL,
        "role": "deeds_mortgages_releases_and_recorded_liens",
        "join_keys": ["county", "book_page", "plat_reference"],
    },
    {
        "source_id": "us-md-mdp-parcel-points",
        "name": "Maryland MD iMAP Parcel Points",
        "url": MDP_PARCEL_POINTS_URL,
        "role": "parcel_account_situs_geometry_and_deed_reference",
        "join_keys": ["county", "account_id", "situs", "deed_reference"],
    },
    {
        "source_id": "us-md-mdp-cama-downloads",
        "name": "Maryland MDP Statewide CAMA Downloads",
        "url": MDP_DOWNLOADS_URL,
        "role": "assessment_building_and_land_characteristics",
        "join_keys": ["county", "account_id"],
    },
    {
        "source_id": "us-md-mdp-property-sales-downloads",
        "name": "Maryland MDP Property Sales Downloads",
        "url": MDP_DOWNLOADS_URL,
        "role": "parcel_transfer_and_sale_context",
        "join_keys": ["county", "account_id", "deed_reference"],
    },
)


class MarylandPlatsError(RuntimeError):
    """Source error with shared public-record result semantics."""

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


class MarylandPlatsSelectionError(MarylandPlatsError):
    """A caller selection does not represent one source form operation."""

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
            category="query_selection",
            details=details,
        )


class MarylandPlatsSourceChangedError(MarylandPlatsError):
    """The live HTML no longer matches the probed source contract."""

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


@dataclass(frozen=True)
class CountyRoute:
    code: str
    name: str
    search_url: str

    def to_record(self) -> dict[str, Any]:
        return {
            "source_id": SOURCE_ID,
            "record_kind": "plat_county_route",
            "county_identity": {
                "source_county_code": self.code,
                "source_county_name": self.name,
            },
            "search_url": self.search_url,
        }


@dataclass(frozen=True)
class SeriesRoute:
    county_code: str
    qualifier: str
    series: str
    name: str | None
    coverage_dates: str | None
    source_url: str

    @property
    def accession_prefix(self) -> str:
        return f"{self.qualifier}{self.series}"


@dataclass(frozen=True)
class WebFormsState:
    action_url: str
    hidden_fields: Mapping[str, str]
    control_names: tuple[str, ...]
    counties: tuple[CountyRoute, ...]
    selected_qualifier: str | None
    series_options: tuple[str, ...]
    series_catalog: tuple[SeriesRoute, ...]
    contract_fingerprint: str


@dataclass(frozen=True)
class SearchSelection:
    county_code: str
    mode: str
    book_number: str | None = None
    page_number: str | None = None
    plat_number: str | None = None
    right_of_way_number: str | None = None
    filed_date: str | None = None
    description: str | None = None
    clerk_initials: str | None = None
    qualifier: str | None = None
    series: str | None = None
    unit: str | None = None
    sort: str = "date_desc"
    include_no_images: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "county_code": self.county_code,
            "mode": self.mode,
            "book_number": self.book_number,
            "page_number": self.page_number,
            "plat_number": self.plat_number,
            "right_of_way_number": self.right_of_way_number,
            "filed_date": self.filed_date,
            "description": self.description,
            "clerk_initials": self.clerk_initials,
            "qualifier": self.qualifier,
            "series": self.series,
            "unit": self.unit,
            "sort": self.sort,
            "include_no_images": self.include_no_images,
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.to_dict())


@dataclass(frozen=True)
class ResultsPage:
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    form_action_url: str
    hidden_fields: Mapping[str, str]
    form_values: Mapping[str, str]
    current_page: int
    total_pages: int
    range_start: int
    range_end: int
    image_result_count: int
    total_result_count: int
    include_no_images: bool
    has_next: bool
    next_control_name: str | None
    criteria_label: str
    schema_fingerprint: str


@dataclass(frozen=True)
class CursorState:
    selection_fingerprint: str
    form_contract_fingerprint: str
    target_page: int
    target_offset: int
    anchor_page: int
    anchor_index: int
    anchor_representation_identity: str


@dataclass(frozen=True)
class SearchResult:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    raw_artifact_refs: tuple[str, ...]
    pages_fetched: int
    requests_made: int
    source_image_result_count: int
    source_total_result_count: int
    source_total_pages: int
    form_contract_fingerprint: str
    result_schema_fingerprints: tuple[str, ...]


@dataclass(frozen=True)
class DownloadedArtifact:
    source_url: str
    content: bytes
    media_type: str
    sha256: str
    etag: str | None
    last_modified: str | None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = html_lib.unescape(" ".join(str(value).replace("\xa0", " ").split()))
    return text or None


def _visible_text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    pieces: list[str] = []
    for item in tag.find_all(string=True):
        parent_name = (
            item.parent.name.casefold()
            if item.parent and item.parent.name
            else ""
        )
        if parent_name in {"script", "style"}:
            continue
        cleaned = _clean_text(item)
        if cleaned:
            pieces.append(cleaned)
    return _clean_text(" ".join(pieces))


def _decode_js_string(value: str) -> str:
    try:
        decoded = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        decoded = value.replace(r"\"", '"').replace(r"\\", "\\")
    return html_lib.unescape(str(decoded))


def _script_text(tag: Tag) -> str:
    return "\n".join(script.get_text() for script in tag.find_all("script"))


def _script_test_value(tag: Tag) -> str | None:
    match = JS_TEST_RE.search(_script_text(tag))
    if match is None:
        return None
    return _clean_text(_decode_js_string(match.group("value")))


def _script_writes(tag: Tag) -> tuple[str, ...]:
    values = []
    for match in JS_WRITE_RE.finditer(_script_text(tag)):
        decoded = _decode_js_string(match.group("value"))
        text = BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True)
        cleaned = _clean_text(text)
        if cleaned:
            values.append(cleaned)
    return tuple(values)


def _integer(value: str) -> int:
    return int(value.replace(",", ""))


def _stable_url(value: str) -> str:
    parts = urlsplit(value)
    query = parse_qs(parts.query, keep_blank_values=True)
    query.pop("id", None)
    normalized_query = urlencode(
        [(key, item) for key in sorted(query) for item in query[key]],
        doseq=True,
    )
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, normalized_query, "")
    )


def _official_page_url(value: str, *, expected_path: str | None = None) -> str:
    absolute = urljoin(BASE_URL, value.replace("\\", "/"))
    parts = urlsplit(absolute)
    if parts.scheme != "https" or parts.netloc.casefold() != "plats.msa.maryland.gov":
        raise MarylandPlatsSourceChangedError(
            "unexpected_source_url",
            "PLATS.NET returned a URL outside its official host",
            details={"url": absolute},
        )
    if expected_path is not None and parts.path.casefold() != expected_path.casefold():
        raise MarylandPlatsSourceChangedError(
            "unexpected_source_path",
            "PLATS.NET returned an unexpected official page path",
            details={"url": absolute, "expected_path": expected_path},
        )
    return absolute


def _official_artifact_url(value: str) -> str:
    absolute = _official_page_url(value)
    parts = urlsplit(absolute)
    suffix = Path(parts.path).suffix.casefold()
    if (
        not parts.path.casefold().startswith("/plats/")
        or suffix not in ARTIFACT_SUFFIXES
    ):
        raise MarylandPlatsSelectionError(
            "artifact_url_invalid",
            "Artifact URL is not a published PLATS.NET PDF, TIFF, or JPEG",
            details={"url": absolute},
        )
    return absolute


def _selected_value(select: Tag | None) -> str | None:
    if select is None:
        return None
    option = select.find("option", selected=True) or select.find("option")
    if option is None:
        return None
    return _clean_text(option.get("value"))


def _hidden_fields(form: Tag) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in form.select("input[type='hidden'][name]"):
        name = str(item.get("name"))
        fields[name] = str(item.get("value") or "")
    missing = [name for name in HIDDEN_FIELDS if name not in fields]
    if missing:
        raise MarylandPlatsSourceChangedError(
            "webforms_state_missing",
            "PLATS.NET form is missing required ASP.NET state fields",
            details={"missing": missing},
        )
    return fields


def parse_search_form(html: str, *, source_url: str) -> WebFormsState:
    """Parse one county search page and its exact WebForms controls."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="form1")
    if not isinstance(form, Tag):
        raise MarylandPlatsSourceChangedError(
            "search_form_missing",
            "PLATS.NET county page has no form1 search form",
            details={"source_url": source_url},
        )
    action = _official_page_url(
        urljoin(source_url, str(form.get("action") or source_url)),
        expected_path="/pages/plats.aspx",
    )
    hidden = _hidden_fields(form)
    control_names = tuple(
        sorted(
            {
                str(item.get("name"))
                for item in form.select("[name]")
                if item.get("name")
            }
        )
    )
    counties: list[CountyRoute] = []
    county_select = form.find("select", id="dropdownbar_ddlbarcounties")
    if isinstance(county_select, Tag):
        for option in county_select.find_all("option"):
            code = _clean_text(option.get("value"))
            name = _clean_text(option.get_text(" ", strip=True))
            if not code or code.casefold() == "select" or not name:
                continue
            counties.append(
                CountyRoute(
                    code=code.upper(),
                    name=name,
                    search_url=SEARCH_URL_TEMPLATE.format(
                        county_code=code.upper()
                    ),
                )
            )

    qualifier_select = form.find("select", id="body_ddlqualslct")
    selected_qualifier = _selected_value(qualifier_select)
    series_select = form.find("select", id="body_ddlseriesslct")
    series_options = tuple(
        str(option.get("value"))
        for option in (
            series_select.find_all("option")
            if isinstance(series_select, Tag)
            else ()
        )
        if option.get("value")
    )
    catalog: list[SeriesRoute] = []
    seen_catalog: set[tuple[str, str]] = set()
    for anchor in form.find_all("a", href=True):
        href = str(anchor.get("href"))
        absolute = urljoin(source_url, href)
        parts = urlsplit(absolute)
        if parts.path.casefold() != "/pages/series.aspx":
            continue
        query = parse_qs(parts.query, keep_blank_values=True)
        qualifier = _clean_text((query.get("qualifier") or [None])[0])
        series = _clean_text((query.get("series") or [None])[0])
        if not qualifier or not series:
            continue
        key = (qualifier.upper(), series)
        if key in seen_catalog:
            continue
        seen_catalog.add(key)
        catalog.append(
            SeriesRoute(
                county_code=_clean_text((query.get("cid") or [""])[0])
                or "",
                qualifier=qualifier.upper(),
                series=series,
                name=_clean_text((query.get("seriesname") or [None])[0]),
                coverage_dates=_clean_text((query.get("dates") or [None])[0]),
                source_url=_official_page_url(absolute),
            )
        )

    sort_values: dict[str, list[str]] = {}
    for select_id in ("body_ddlsort", "body_ddlsort3"):
        select = form.find("select", id=select_id)
        sort_values[select_id] = (
            [
                str(option.get("value"))
                for option in select.find_all("option")
                if option.get("value")
            ]
            if isinstance(select, Tag)
            else []
        )
    fingerprint = sha256_fingerprint(
        {
            "version": FORM_CONTRACT_VERSION,
            "action_path": urlsplit(action).path,
            "control_names": list(control_names),
            "hidden_fields": sorted(hidden),
            "qualifier_values": (
                [
                    str(option.get("value"))
                    for option in qualifier_select.find_all("option")
                    if option.get("value")
                ]
                if isinstance(qualifier_select, Tag)
                else []
            ),
            "sort_values": sort_values,
        }
    )
    return WebFormsState(
        action_url=action,
        hidden_fields=hidden,
        control_names=control_names,
        counties=tuple(counties),
        selected_qualifier=(
            selected_qualifier.upper() if selected_qualifier else None
        ),
        series_options=series_options,
        series_catalog=tuple(catalog),
        contract_fingerprint=fingerprint,
    )


def _normalize_accession(value: str) -> tuple[str, str, str, str]:
    match = ACCESSION_RE.fullmatch(value)
    if match is None:
        raise MarylandPlatsSourceChangedError(
            "accession_unrecognized",
            "PLATS.NET result accession no longer matches an archive series/unit",
            details={"accession": value},
        )
    qualifier = match.group("qualifier").upper()
    series = match.group("series")
    unit = match.group("unit")
    return qualifier, series, unit, f"MSA {qualifier}{series}-{unit}"


def _parse_reference(value: str | None) -> dict[str, Any]:
    raw = _clean_text(value)
    parsed: dict[str, Any] = {
        "raw": raw,
        "book_number": None,
        "page_number": None,
        "plat_number": None,
        "box_number": None,
        "right_of_way_plat_number": None,
    }
    if raw is None:
        return parsed
    plat = re.fullmatch(r"Plat(?:\s+No\.?)?\s+(.+)", raw, re.IGNORECASE)
    if plat and not raw.casefold().startswith("plat book"):
        parsed["plat_number"] = _clean_text(plat.group(1))
        return parsed
    box = re.fullmatch(r"Box(?:\s+No\.?)?\s+(.+)", raw, re.IGNORECASE)
    if box:
        parsed["box_number"] = _clean_text(box.group(1))
        return parsed
    row = re.fullmatch(
        r"(?:Right\s+of\s+Way|ROW)(?:\s+Plat)?(?:\s+No\.?)?\s+(.+)",
        raw,
        re.IGNORECASE,
    )
    if row:
        parsed["right_of_way_plat_number"] = _clean_text(row.group(1))
        return parsed
    book_page = re.search(
        r"(?:Book|Liber)\s*[:#]?\s*(?P<book>[A-Za-z0-9.-]+)"
        r".*?(?:Page|Folio|P\.)\s*[:#]?\s*(?P<page>[A-Za-z0-9.-]+)",
        raw,
        re.IGNORECASE,
    )
    if book_page:
        parsed["book_number"] = book_page.group("book")
        parsed["page_number"] = book_page.group("page")
    return parsed


def _source_date(value: str | None) -> dict[str, Any]:
    raw = _clean_text(value)
    iso = None
    if raw and SOURCE_DATE_RE.fullmatch(raw):
        try:
            iso = datetime.strptime(raw, "%Y/%m/%d").date().isoformat()
        except ValueError as error:
            raise MarylandPlatsSourceChangedError(
                "source_date_invalid",
                "PLATS.NET published an invalid calendar date",
                details={"source_date": raw},
            ) from error
    return {"raw": raw, "iso": iso}


def _unit_url(
    county_code: str,
    qualifier: str,
    series: str,
    unit: str,
) -> str:
    parameters = {
        "cid": county_code,
        "qualifier": qualifier,
        "series": series,
        "unit": unit,
    }
    return f"{UNIT_URL}?{urlencode(parameters)}"


def _record_identity(
    county_code: str,
    qualifier: str,
    series: str,
    unit: str,
    accession: str,
) -> tuple[str, dict[str, Any]]:
    native_id = f"{county_code}:{qualifier}{series}-{unit}"
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        STATE_GEOID,
        "recorded-plat",
        native_id,
    )
    identity = {
        "county_code": county_code,
        "archive_qualifier": qualifier,
        "archive_series": series,
        "archive_unit": unit,
        "msa_accession": accession,
    }
    return canonical_ref, identity


def _row_accession(
    cell: Tag,
    *,
    has_published_scans: bool,
) -> tuple[str, str | None]:
    script = _script_text(cell)
    unit_match = UNIT_LINK_RE.search(script)
    link_url = None
    link_accession = None
    if unit_match is not None:
        link_url = urljoin(
            BASE_URL + "/pages/",
            f"unit.aspx?{html_lib.unescape(unit_match.group('query'))}",
        )
        link_query = parse_qs(urlsplit(link_url).query)
        qualifier = _clean_text((link_query.get("qualifier") or [None])[0])
        series = _clean_text((link_query.get("series") or [None])[0])
        unit = _clean_text((link_query.get("unit") or [None])[0])
        if qualifier and series and unit:
            link_accession = f"MSA {qualifier.upper()}{series}-{unit}"
    writes = _script_writes(cell)
    accession_candidate = next(
        (item for item in writes if ACCESSION_RE.fullmatch(item)),
        None,
    )
    accession = (
        (link_accession or accession_candidate)
        if has_published_scans
        else (accession_candidate or link_accession)
    ) or _visible_text(cell)
    if accession is None:
        raise MarylandPlatsSourceChangedError(
            "result_accession_missing",
            "PLATS.NET result row has no archive accession",
        )
    return accession, link_url


def _result_form_state(
    form: Tag,
    *,
    source_url: str,
) -> tuple[str, Mapping[str, str], Mapping[str, str]]:
    action_url = _official_page_url(
        urljoin(source_url, str(form.get("action") or source_url)),
        expected_path="/pages/results.aspx",
    )
    hidden = _hidden_fields(form)
    values: dict[str, str] = {}
    for select in form.find_all("select", attrs={"name": True}):
        value = _selected_value(select)
        if value is not None:
            values[str(select.get("name"))] = value
    for text_input in form.select(
        "input[type='text'][name], input:not([type])[name]"
    ):
        values[str(text_input.get("name"))] = str(
            text_input.get("value") or ""
        )
    checkbox = form.find("input", id="body_ckhide")
    if isinstance(checkbox, Tag) and checkbox.has_attr("checked"):
        values[str(checkbox.get("name"))] = str(
            checkbox.get("value") or "on"
        )
    return action_url, hidden, values


def parse_results_page(
    html: str,
    *,
    source_url: str,
    county_code: str,
    county_name: str,
    selection_fingerprint: str,
) -> ResultsPage:
    """Parse one source-native results page, including JS-rendered row text."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="form1")
    if not isinstance(form, Tag):
        raise MarylandPlatsSourceChangedError(
            "results_form_missing",
            "PLATS.NET results page has no form1",
            details={"source_url": source_url},
        )
    action_url, hidden, form_values = _result_form_state(
        form,
        source_url=source_url,
    )
    banner = form.find(id="body_lblsearchstr")
    banner_text = _visible_text(banner) or ""
    banner_match = RESULT_BANNER_RE.search(banner_text)
    if banner_match:
        range_start = _integer(banner_match.group("start"))
        range_end = _integer(banner_match.group("end"))
        image_count = _integer(banner_match.group("with_images"))
        total_count = _integer(banner_match.group("total"))
    else:
        all_match = RESULT_BANNER_ALL_RE.search(banner_text)
        if all_match:
            range_start = _integer(all_match.group("start"))
            range_end = _integer(all_match.group("end"))
            total_count = _integer(all_match.group("total"))
            image_count = total_count
        elif re.search(r"\b(?:no|0)\s+(?:records|results)\b", banner_text, re.I):
            range_start = 0
            range_end = 0
            image_count = 0
            total_count = 0
        else:
            raise MarylandPlatsSourceChangedError(
                "results_banner_changed",
                "PLATS.NET results summary no longer matches the observed contract",
                details={"banner": banner_text, "source_url": source_url},
            )

    table = form.find("table", id="body_gvResults1_Search")
    records: list[dict[str, Any]] = []
    observed_headers: tuple[str, ...] = ()
    if isinstance(table, Tag):
        header_row = table.find("tr")
        if not isinstance(header_row, Tag):
            raise MarylandPlatsSourceChangedError(
                "results_headers_missing",
                "PLATS.NET result table has no header row",
            )
        observed_headers = tuple(
            _visible_text(header) or ""
            for header in header_row.find_all("th", recursive=False)
        )
        if observed_headers != RESULT_HEADERS:
            raise MarylandPlatsSourceChangedError(
                "results_headers_changed",
                "PLATS.NET result columns changed",
                details={"headers": list(observed_headers)},
            )
        for row_index, row in enumerate(
            header_row.find_next_siblings("tr"),
            start=0,
        ):
            cells = row.find_all("td", recursive=False)
            if len(cells) != len(RESULT_HEADERS):
                raise MarylandPlatsSourceChangedError(
                    "result_row_width_changed",
                    "PLATS.NET result row has an unexpected column count",
                    details={
                        "row_index": row_index,
                        "column_count": len(cells),
                    },
                )
            filed_date = _source_date(
                _script_test_value(cells[0]) or _visible_text(cells[0])
            )
            description_writes = _script_writes(cells[1])
            description = (
                description_writes[0]
                if description_writes
                else _visible_text(cells[1])
            )
            developer_owner = _script_test_value(cells[1])
            reference = _parse_reference(_visible_text(cells[2]))
            direct_scans = _integer(_visible_text(cells[3]) or "0")
            microfilm_scans = _integer(_visible_text(cells[4]) or "0")
            scan_total = direct_scans + microfilm_scans
            accession_raw, scripted_unit_url = _row_accession(
                cells[5],
                has_published_scans=scan_total > 0,
            )
            qualifier, series, unit, accession = _normalize_accession(
                accession_raw
            )
            canonical_ref, identity = _record_identity(
                county_code,
                qualifier,
                series,
                unit,
                accession,
            )
            exact_detail_url = _unit_url(
                county_code,
                qualifier,
                series,
                unit,
            )
            source_result_link = (
                _official_page_url(
                    scripted_unit_url,
                    expected_path="/pages/unit.aspx",
                )
                if scripted_unit_url and scan_total > 0
                else None
            )
            representation_components = {
                "record_identity": identity,
                "filed_date": filed_date,
                "description": description,
                "developer_owner": developer_owner,
                "reference": reference,
                "direct_scans": direct_scans,
                "microfilm_scans": microfilm_scans,
            }
            representation_identity = sha256_fingerprint(
                representation_components
            )
            absolute_position = range_start + row_index
            occurrence_components = {
                "selection_fingerprint": selection_fingerprint,
                "absolute_position": absolute_position,
                "representation_identity": representation_identity,
            }
            occurrence_identity = sha256_fingerprint(occurrence_components)
            records.append(
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "recorded_plat_search_occurrence",
                    "canonical_ref": canonical_ref,
                    "record_identity": identity,
                    "record_identity_fingerprint": sha256_fingerprint(identity),
                    "county": {
                        "source_code": county_code,
                        "source_name": county_name,
                    },
                    "archive_accession": {
                        "raw": accession_raw,
                        "normalized": accession,
                        "qualifier": qualifier,
                        "series": series,
                        "unit": unit,
                    },
                    "filed_date": filed_date,
                    "description": description,
                    "developer_owner": developer_owner,
                    "book_page_plat_reference": reference,
                    "source_result_representation": {
                        "representation_identity": representation_identity,
                        "direct_scan_count": direct_scans,
                        "microfilm_scan_count": microfilm_scans,
                        "published_scan_count": scan_total,
                        "image_availability": (
                            "published_scans"
                            if scan_total > 0
                            else "metadata_only"
                        ),
                        "source_result_detail_link": source_result_link,
                        "exact_detail_url": exact_detail_url,
                    },
                    "result_occurrence": {
                        "occurrence_identity": occurrence_identity,
                        "selection_fingerprint": selection_fingerprint,
                        "absolute_position": absolute_position,
                        "position_on_native_page": row_index,
                    },
                    "complementary_source_ids": [
                        item["source_id"] for item in COMPLEMENTARY_SOURCES
                    ],
                    "provenance": {
                        "source_url": source_url,
                        "stable_source_url": _stable_url(source_url),
                    },
                }
            )
    elif total_count:
        raise MarylandPlatsSourceChangedError(
            "results_table_missing",
            "PLATS.NET reported results without a result table",
            details={"source_url": source_url, "banner": banner_text},
        )

    page_select = form.find("select", id="body_ddlPage")
    current_page = int(_selected_value(page_select) or "1")
    page_values = (
        [
            int(str(option.get("value")))
            for option in page_select.find_all("option")
            if str(option.get("value") or "").isdigit()
        ]
        if isinstance(page_select, Tag)
        else [1]
    )
    total_pages = max(page_values, default=1)
    next_control = form.find(id="body_imgButtonNext")
    if not isinstance(next_control, Tag):
        next_control = form.find(id="body_imgnext2")
    next_control_name = (
        str(next_control.get("name"))
        if isinstance(next_control, Tag) and next_control.get("name")
        else None
    )
    has_next = next_control_name is not None or current_page < total_pages
    checkbox = form.find("input", id="body_ckhide")
    include_no_images = bool(
        isinstance(checkbox, Tag) and checkbox.has_attr("checked")
    )
    criteria_label = banner_text.split("for:", 1)[-1].strip()
    for record in records:
        record["result_occurrence"].update(
            {
                "native_page": current_page,
                "native_page_start": range_start,
                "native_page_end": range_end,
                "source_image_result_count": image_count,
                "source_total_result_count": total_count,
                "source_total_pages": total_pages,
            }
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "parser": "md_plats_results_js_rows_v1",
            "headers": list(observed_headers or RESULT_HEADERS),
            "native_page_capacity": (
                range_end - range_start + 1 if range_start else 0
            ),
            "page_control": (
                "ctl00$body$ddlPage"
                if isinstance(page_select, Tag)
                else None
            ),
            "next_control": next_control_name,
        }
    )
    return ResultsPage(
        records=tuple(records),
        source_url=source_url,
        form_action_url=action_url,
        hidden_fields=hidden,
        form_values=form_values,
        current_page=current_page,
        total_pages=total_pages,
        range_start=range_start,
        range_end=range_end,
        image_result_count=image_count,
        total_result_count=total_count,
        include_no_images=include_no_images,
        has_next=has_next,
        next_control_name=next_control_name,
        criteria_label=criteria_label,
        schema_fingerprint=schema_fingerprint,
    )


def _artifact_identity(
    *,
    record_identity: Mapping[str, Any],
    role: str,
    ordinal: int,
    source_label: str,
    source_filename: str,
) -> str:
    return sha256_fingerprint(
        {
            "record_identity": record_identity,
            "artifact_role": role,
            "ordinal": ordinal,
            "source_label": source_label,
            "source_filename": source_filename,
        }
    )


def _artifact_record(
    *,
    source_url: str,
    role: str,
    ordinal: int,
    source_label: str,
    record_identity: Mapping[str, Any],
) -> dict[str, Any]:
    artifact_url = _official_artifact_url(source_url)
    parts = urlsplit(artifact_url)
    suffix = Path(parts.path).suffix.casefold()
    source_filename = Path(parts.path).name
    path_date_match = PATH_DATE_RE.match(parts.path)
    identity = _artifact_identity(
        record_identity=record_identity,
        role=role,
        ordinal=ordinal,
        source_label=source_label,
        source_filename=source_filename,
    )
    return {
        "artifact_identity": identity,
        "artifact_role": role,
        "ordinal_within_role": ordinal,
        "source_label": source_label,
        "source_filename": source_filename,
        "file_format": suffix.lstrip("."),
        "media_type": MEDIA_TYPES[suffix],
        "source_url": artifact_url,
        "representation_locator": {
            "observed_url": artifact_url,
            "observed_path_date": (
                path_date_match.group("date") if path_date_match else None
            ),
        },
    }


def parse_plat_detail(
    html: str,
    *,
    source_url: str,
    county_code: str,
    expected_qualifier: str | None = None,
    expected_series: str | None = None,
    expected_unit: str | None = None,
) -> dict[str, Any]:
    """Parse an exact unit page, including metadata-only units."""

    soup = BeautifulSoup(html, "html.parser")
    content = soup.find(id="body_unitcontent")
    if not isinstance(content, Tag):
        raise MarylandPlatsSourceChangedError(
            "unit_content_missing",
            "PLATS.NET unit page has no plat detail content",
            details={"source_url": source_url},
        )
    date_text = _visible_text(content.find(id="body_lbldatedata"))
    description = _visible_text(content.find(id="body_lbldescriptdata"))
    reference_text = _visible_text(content.find(id="body_lblrefdata"))
    citation = content.find(id="body_lblmsacitation")
    citation_anchor = (
        citation.find("a", href=True) if isinstance(citation, Tag) else None
    )
    accession_raw = (
        _visible_text(citation_anchor)
        if isinstance(citation_anchor, Tag)
        else _visible_text(citation)
    )
    if accession_raw is None:
        raise MarylandPlatsSourceChangedError(
            "unit_accession_missing",
            "PLATS.NET unit page has no MSA accession",
            details={"source_url": source_url},
        )
    qualifier, series, unit, accession = _normalize_accession(accession_raw)
    expected = {
        "qualifier": (
            expected_qualifier.upper() if expected_qualifier else qualifier
        ),
        "series": expected_series or series,
        "unit": expected_unit or unit,
    }
    observed = {
        "qualifier": qualifier,
        "series": series,
        "unit": unit,
    }
    if expected != observed:
        raise MarylandPlatsSourceChangedError(
            "unit_identity_mismatch",
            "PLATS.NET unit page identity differs from the requested plat",
            details={"expected": expected, "observed": observed},
        )

    canonical_ref, identity = _record_identity(
        county_code.upper(),
        qualifier,
        series,
        unit,
        accession,
    )
    artifacts: list[dict[str, Any]] = []
    iframe = content.find("iframe", id="body_iframePDF")
    if isinstance(iframe, Tag) and iframe.get("src"):
        artifacts.append(
            _artifact_record(
                source_url=str(iframe.get("src")),
                role="compiled_pdf",
                ordinal=1,
                source_label="Compiled PDF",
                record_identity=identity,
            )
        )
    artifact_spans = (
        ("body_lbldsno", "direct_scan"),
        ("body_lblpdffi", "published_pdf"),
        ("body_lblmfno", "microfilm_scan"),
        ("body_lblotherds", "other_scan"),
    )
    for span_id, role in artifact_spans:
        span = content.find(id=span_id)
        if not isinstance(span, Tag):
            continue
        ordinal = 0
        for anchor in span.find_all("a", href=True):
            href = str(anchor.get("href"))
            try:
                artifact_url = _official_artifact_url(href)
            except MarylandPlatsSelectionError:
                continue
            ordinal += 1
            artifacts.append(
                _artifact_record(
                    source_url=artifact_url,
                    role=role,
                    ordinal=ordinal,
                    source_label=_visible_text(anchor) or Path(
                        urlsplit(artifact_url).path
                    ).name,
                    record_identity=identity,
                )
            )

    county_court_label = _visible_text(
        content.find(id="body_lblcntyinfo")
    )
    series_name = _visible_text(content.find(id="body_lblsernameinfo"))
    if series_name and series_name.startswith("(") and series_name.endswith(")"):
        series_name = series_name[1:-1].strip() or None
    guide_url = (
        str(citation_anchor.get("href"))
        if isinstance(citation_anchor, Tag)
        else None
    )
    representation_components = {
        "record_identity": identity,
        "filed_date": _source_date(date_text),
        "description": description,
        "reference": _parse_reference(reference_text),
        "artifact_identities": [
            artifact["artifact_identity"] for artifact in artifacts
        ],
    }
    return {
        "source_id": SOURCE_ID,
        "record_kind": "recorded_plat_detail",
        "canonical_ref": canonical_ref,
        "record_identity": identity,
        "record_identity_fingerprint": sha256_fingerprint(identity),
        "representation_identity": sha256_fingerprint(
            representation_components
        ),
        "county": {
            "source_code": county_code.upper(),
            "court_label": county_court_label,
        },
        "archive_accession": {
            "raw": accession_raw,
            "normalized": accession,
            "qualifier": qualifier,
            "series": series,
            "unit": unit,
            "series_name": series_name,
            "guide_url": guide_url,
        },
        "filed_date": _source_date(date_text),
        "description": description,
        "book_page_plat_reference": _parse_reference(reference_text),
        "image_availability": (
            "published_artifacts" if artifacts else "metadata_only"
        ),
        "published_artifact_count": len(artifacts),
        "artifacts": artifacts,
        "complementary_source_ids": [
            item["source_id"] for item in COMPLEMENTARY_SOURCES
        ],
        "provenance": {
            "source_url": source_url,
            "stable_source_url": _stable_url(source_url),
            "detail_identity_is_session_independent": True,
        },
    }


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "operation": "search",
        "selection": state.selection_fingerprint,
        "form_contract": state.form_contract_fingerprint,
        "target_page": state.target_page,
        "target_offset": state.target_offset,
        "anchor_page": state.anchor_page,
        "anchor_index": state.anchor_index,
        "anchor_representation": state.anchor_representation_identity,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(
    value: str | None,
    *,
    selection_fingerprint: str,
) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise MarylandPlatsSelectionError(
            "cursor_invalid",
            "Cursor is not a Maryland PLATS.NET continuation",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
    ) as error:
        raise MarylandPlatsSelectionError(
            "cursor_invalid",
            "Cursor payload is not valid",
        ) from error
    expected_keys = {
        "v",
        "operation",
        "selection",
        "form_contract",
        "target_page",
        "target_offset",
        "anchor_page",
        "anchor_index",
        "anchor_representation",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise MarylandPlatsSelectionError(
            "cursor_invalid",
            "Cursor payload has an unsupported shape",
        )
    if (
        payload.get("v") != CURSOR_VERSION
        or payload.get("operation") != "search"
    ):
        raise MarylandPlatsSelectionError(
            "cursor_invalid",
            "Cursor version or operation is not supported",
        )
    if payload.get("selection") != selection_fingerprint:
        raise MarylandPlatsSelectionError(
            "cursor_selection_mismatch",
            "Cursor belongs to different PLATS.NET search criteria",
        )
    integer_fields = (
        "target_page",
        "target_offset",
        "anchor_page",
        "anchor_index",
    )
    if any(
        isinstance(payload.get(field), bool)
        or not isinstance(payload.get(field), int)
        for field in integer_fields
    ):
        raise MarylandPlatsSelectionError(
            "cursor_invalid",
            "Cursor page or row offsets are invalid",
        )
    if (
        payload["target_page"] < 1
        or payload["target_offset"] < 0
        or payload["anchor_page"] < 1
        or payload["anchor_index"] < 0
        or not isinstance(payload.get("form_contract"), str)
        or not isinstance(payload.get("anchor_representation"), str)
    ):
        raise MarylandPlatsSelectionError(
            "cursor_invalid",
            "Cursor page, offset, or anchor is invalid",
        )
    return CursorState(
        selection_fingerprint=selection_fingerprint,
        form_contract_fingerprint=payload["form_contract"],
        target_page=payload["target_page"],
        target_offset=payload["target_offset"],
        anchor_page=payload["anchor_page"],
        anchor_index=payload["anchor_index"],
        anchor_representation_identity=payload["anchor_representation"],
    )


def _response_header(response: Any, name: str) -> str | None:
    for key, value in getattr(response, "headers", {}).items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _search_form_payload(
    form: WebFormsState,
    selection: SearchSelection,
) -> dict[str, str]:
    data = dict(form.hidden_fields)
    controls = set(form.control_names)

    def require(*names: str) -> None:
        missing = [name for name in names if name not in controls]
        if missing:
            raise MarylandPlatsSourceChangedError(
                "search_controls_missing",
                "PLATS.NET county page lacks controls for the selected search",
                details={"mode": selection.mode, "missing": missing},
            )

    if selection.mode == "basic":
        if selection.plat_number is not None:
            require("ctl00$body$txtPlatNo", "ctl00$body$btnSearch2")
            data["ctl00$body$txtPlatNo"] = selection.plat_number
            data["ctl00$body$btnSearch2"] = "Search"
        elif selection.right_of_way_number is not None:
            require(
                "ctl00$body$txtRightWayPlat",
                "ctl00$body$btnSearch3",
            )
            data["ctl00$body$txtRightWayPlat"] = (
                selection.right_of_way_number
            )
            data["ctl00$body$btnSearch3"] = "Search"
        else:
            require(
                "ctl00$body$txtBookNo",
                "ctl00$body$txtPageNo",
                "ctl00$body$btnSearch1",
            )
            data["ctl00$body$txtBookNo"] = selection.book_number or ""
            data["ctl00$body$txtPageNo"] = selection.page_number or ""
            data["ctl00$body$btnSearch1"] = "Search"
    elif selection.mode == "advanced":
        require(
            "ctl00$body$txtDate",
            "ctl00$body$txtDescription",
            "ctl00$body$txtadv1bk",
            "ctl00$body$txtadv1pg",
            "ctl00$body$txtNum",
            "ctl00$body$ddlsort",
            "ctl00$body$btnadvsearch1",
        )
        data.update(
            {
                "ctl00$body$txtDate": selection.filed_date or "",
                "ctl00$body$txtDescription": selection.description or "",
                "ctl00$body$txtadv1bk": selection.book_number or "",
                "ctl00$body$txtadv1pg": selection.page_number or "",
                "ctl00$body$txtNum": selection.clerk_initials or "",
                "ctl00$body$ddlsort": SORT_VALUES[selection.sort],
                "ctl00$body$btnadvsearch1": "Search",
            }
        )
    elif selection.mode == "series":
        require(
            "ctl00$body$ddlqualslct",
            "ctl00$body$ddlseriesslct",
            "ctl00$body$txtseriesunit",
            "ctl00$body$ddlsort3",
            "ctl00$body$btnadvsearch3",
        )
        data.update(
            {
                "ctl00$body$ddlqualslct": selection.qualifier or "",
                "ctl00$body$ddlseriesslct": selection.series or "",
                "ctl00$body$txtseriesunit": selection.unit or "",
                "ctl00$body$ddlsort3": SORT_VALUES[selection.sort],
                "ctl00$body$btnadvsearch3": "Search",
            }
        )
    else:
        raise AssertionError(f"unknown search mode: {selection.mode}")
    return data


def _results_location(response: Any, *, county_code: str) -> str:
    location = _response_header(response, "Location")
    if not location:
        soup = BeautifulSoup(str(getattr(response, "text", "")), "html.parser")
        anchor = soup.select_one("h2 a[href*='results.aspx']")
        location = str(anchor.get("href")) if isinstance(anchor, Tag) else None
    if not location:
        raise MarylandPlatsSourceChangedError(
            "search_redirect_missing",
            "PLATS.NET search did not return a results.aspx location",
        )
    absolute = _official_page_url(
        urljoin(BASE_URL, location),
        expected_path="/pages/results.aspx",
    )
    returned_county = _clean_text(
        (parse_qs(urlsplit(absolute).query).get("cid") or [None])[0]
    )
    if returned_county and returned_county.upper() != county_code.upper():
        raise MarylandPlatsSourceChangedError(
            "search_county_mismatch",
            "PLATS.NET search redirected to a different county",
            details={
                "requested_county": county_code,
                "returned_county": returned_county,
            },
        )
    return absolute


class MarylandPlatsClient:
    """Paced, retrying client for the verified PLATS.NET form family."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        referer: str | None = None,
        allow_redirects: bool = False,
        accepted_statuses: frozenset[int] = frozenset({200}),
        expect_html: bool = True,
    ) -> Any:
        headers = {
            "Accept": (
                "text/html,application/xhtml+xml"
                if expect_html
                else "application/pdf,image/tiff,image/jpeg,*/*;q=0.5"
            )
        }
        if referer:
            headers["Referer"] = referer
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    data=dict(data) if data is not None else None,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise MarylandPlatsError(
                        "transport_error",
                        f"PLATS.NET request failed: {error}",
                        category="transport",
                        retryable=True,
                        details={"url": url},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status = int(response.status_code)
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status == 429:
                raise MarylandPlatsError(
                    "source_rate_limited",
                    "PLATS.NET rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="http",
                    retryable=True,
                    details={"url": url, "http_status": status},
                )
            if status in {401, 403}:
                raise MarylandPlatsError(
                    "source_access_denied",
                    "PLATS.NET declined the anonymous request",
                    status=ResultStatus.RESTRICTED,
                    category="source_access",
                    details={"url": url, "http_status": status},
                )
            if status not in accepted_statuses:
                raise MarylandPlatsError(
                    "source_http_error",
                    f"PLATS.NET returned HTTP {status}",
                    category="http",
                    retryable=status >= 500,
                    details={"url": url, "http_status": status},
                )
            if expect_html:
                text = str(getattr(response, "text", ""))
                lowered = text[:250_000].casefold()
                if any(marker in lowered for marker in CHALLENGE_MARKERS):
                    raise MarylandPlatsError(
                        "source_access_challenge",
                        "PLATS.NET returned a browser-verification page",
                        status=ResultStatus.HUMAN_REQUIRED,
                        category="source_access",
                        details={"url": url},
                    )
                redirect_without_body = (
                    300 <= status < 400
                    and _response_header(response, "Location") is not None
                )
                if "<" not in text and not redirect_without_body:
                    raise MarylandPlatsSourceChangedError(
                        "html_response_missing",
                        "PLATS.NET page response did not contain HTML",
                        details={"url": url, "http_status": status},
                    )
            return response
        raise AssertionError("retry loop exhausted")

    def fetch_index_form(self) -> WebFormsState:
        form, _ = self.fetch_county_form("MO")
        return form

    def fetch_county_form(
        self,
        county_code: str,
    ) -> tuple[WebFormsState, str]:
        code = county_code.upper()
        url = SEARCH_URL_TEMPLATE.format(county_code=code)
        response = self._request(
            "GET",
            url,
            allow_redirects=True,
        )
        source_url = str(getattr(response, "url", url))
        form = parse_search_form(str(response.text), source_url=source_url)
        action_county = _clean_text(
            (
                parse_qs(urlsplit(form.action_url).query).get("cid")
                or [None]
            )[0]
        )
        if action_county and action_county.upper() != code:
            raise MarylandPlatsSourceChangedError(
                "county_form_mismatch",
                "PLATS.NET returned a search form for a different county",
                details={
                    "requested_county": code,
                    "form_county": action_county,
                },
            )
        county = next(
            (item for item in form.counties if item.code == code),
            None,
        )
        if county is None:
            raise MarylandPlatsSelectionError(
                "county_not_published",
                "County code is not present in the current PLATS.NET selector",
                details={"county_code": code},
            )
        return form, county.name

    def counties(self) -> tuple[CountyRoute, ...]:
        return self.fetch_index_form().counties

    def _switch_series_qualifier(
        self,
        form: WebFormsState,
        selection: SearchSelection,
    ) -> WebFormsState:
        qualifier = selection.qualifier or ""
        if form.selected_qualifier == qualifier:
            return form
        current_series = form.series_options[0] if form.series_options else ""
        data = dict(form.hidden_fields)
        data.update(
            {
                "__EVENTTARGET": "ctl00$body$ddlqualslct",
                "__EVENTARGUMENT": "",
                "ctl00$body$ddlqualslct": qualifier,
                "ctl00$body$ddlseriesslct": current_series,
                "ctl00$body$txtseriesunit": "",
                "ctl00$body$ddlsort3": SORT_VALUES[selection.sort],
            }
        )
        response = self._request(
            "POST",
            form.action_url,
            data=data,
            referer=form.action_url,
            allow_redirects=False,
            accepted_statuses=frozenset({200}),
        )
        switched = parse_search_form(
            str(response.text),
            source_url=str(getattr(response, "url", form.action_url)),
        )
        if switched.selected_qualifier != qualifier:
            raise MarylandPlatsSourceChangedError(
                "series_qualifier_postback_failed",
                "PLATS.NET did not switch to the selected series qualifier",
                details={
                    "requested": qualifier,
                    "observed": switched.selected_qualifier,
                },
            )
        return switched

    def _fetch_results(
        self,
        results_url: str,
        *,
        referer: str,
        selection: SearchSelection,
        county_name: str,
    ) -> ResultsPage:
        response = self._request(
            "GET",
            results_url,
            referer=referer,
            allow_redirects=False,
            accepted_statuses=frozenset({200, 302}),
        )
        return parse_results_page(
            str(response.text),
            source_url=str(getattr(response, "url", results_url)),
            county_code=selection.county_code,
            county_name=county_name,
            selection_fingerprint=selection.fingerprint,
        )

    def _postback_payload(self, page: ResultsPage) -> dict[str, str]:
        data = dict(page.hidden_fields)
        data.update(page.form_values)
        data["__EVENTTARGET"] = ""
        data["__EVENTARGUMENT"] = ""
        return data

    def _parse_postback_page(
        self,
        response: Any,
        *,
        prior_page: ResultsPage,
        selection: SearchSelection,
        county_name: str,
    ) -> tuple[ResultsPage, int]:
        response_text = str(getattr(response, "text", ""))
        location = _response_header(response, "Location")
        follow_up_requests = 0
        source_url = (
            _official_page_url(
                urljoin(prior_page.source_url, location),
                expected_path="/pages/results.aspx",
            )
            if location
            else str(getattr(response, "url", prior_page.form_action_url))
        )
        if "body_lblsearchstr" not in response_text:
            follow = self._request(
                "GET",
                source_url,
                referer=prior_page.source_url,
                allow_redirects=False,
                accepted_statuses=frozenset({200, 302}),
            )
            follow_up_requests += 1
            response_text = str(follow.text)
            source_url = str(getattr(follow, "url", source_url))
        return (
            parse_results_page(
                response_text,
                source_url=source_url,
                county_code=selection.county_code,
                county_name=county_name,
                selection_fingerprint=selection.fingerprint,
            ),
            follow_up_requests,
        )

    def _include_metadata_rows(
        self,
        page: ResultsPage,
        *,
        selection: SearchSelection,
        county_name: str,
    ) -> tuple[ResultsPage, int]:
        if page.include_no_images:
            return page, 0
        data = self._postback_payload(page)
        data["__EVENTTARGET"] = "ctl00$body$ckhide"
        data["ctl00$body$ckhide"] = "on"
        response = self._request(
            "POST",
            page.form_action_url,
            data=data,
            referer=page.source_url,
            allow_redirects=False,
            accepted_statuses=frozenset({200, 302}),
        )
        updated, follow_ups = self._parse_postback_page(
            response,
            prior_page=page,
            selection=selection,
            county_name=county_name,
        )
        if not updated.include_no_images:
            raise MarylandPlatsSourceChangedError(
                "metadata_toggle_failed",
                "PLATS.NET did not enable records with no images",
            )
        return updated, 1 + follow_ups

    def _next_page(
        self,
        page: ResultsPage,
        *,
        selection: SearchSelection,
        county_name: str,
    ) -> tuple[ResultsPage, int]:
        if not page.has_next:
            raise MarylandPlatsSelectionError(
                "continuation_exhausted",
                "PLATS.NET result set has no next native page",
            )
        if page.next_control_name is None:
            raise MarylandPlatsSourceChangedError(
                "continuation_control_missing",
                (
                    "PLATS.NET reports another result page without a "
                    "next-page control"
                ),
                details={
                    "current_page": page.current_page,
                    "total_pages": page.total_pages,
                },
            )
        data = self._postback_payload(page)
        data[f"{page.next_control_name}.x"] = "12"
        data[f"{page.next_control_name}.y"] = "12"
        response = self._request(
            "POST",
            page.form_action_url,
            data=data,
            referer=page.source_url,
            allow_redirects=False,
            accepted_statuses=frozenset({200, 302}),
        )
        updated, follow_ups = self._parse_postback_page(
            response,
            prior_page=page,
            selection=selection,
            county_name=county_name,
        )
        if updated.current_page != page.current_page + 1:
            raise MarylandPlatsSourceChangedError(
                "continuation_stalled",
                "PLATS.NET next-page postback did not advance exactly one page",
                details={
                    "previous_page": page.current_page,
                    "returned_page": updated.current_page,
                },
            )
        return updated, 1 + follow_ups

    def _initial_search(
        self,
        selection: SearchSelection,
    ) -> tuple[WebFormsState, ResultsPage, str, tuple[str, ...], int]:
        form, county_name = self.fetch_county_form(selection.county_code)
        requests_made = 1
        source_refs = [form.action_url]
        initial_contract = form.contract_fingerprint
        if selection.mode == "series":
            switched_qualifier = (
                form.selected_qualifier != selection.qualifier
            )
            form = self._switch_series_qualifier(form, selection)
            if form.contract_fingerprint != initial_contract:
                raise MarylandPlatsSourceChangedError(
                    "series_form_contract_changed",
                    "PLATS.NET qualifier postback changed the base form contract",
                )
            if selection.series not in form.series_options:
                raise MarylandPlatsSelectionError(
                    "series_not_published",
                    (
                        "Archive series is not present for the selected "
                        "qualifier and county"
                    ),
                    details={
                        "county_code": selection.county_code,
                        "qualifier": selection.qualifier,
                        "series": selection.series,
                    },
                )
            if switched_qualifier:
                requests_made += 1
        payload = _search_form_payload(form, selection)
        response = self._request(
            "POST",
            form.action_url,
            data=payload,
            referer=form.action_url,
            allow_redirects=False,
            accepted_statuses=frozenset({200, 302}),
        )
        requests_made += 1
        results_url = _results_location(
            response,
            county_code=selection.county_code,
        )
        source_refs.append(results_url)
        page = self._fetch_results(
            results_url,
            referer=form.action_url,
            selection=selection,
            county_name=county_name,
        )
        requests_made += 1
        if selection.include_no_images:
            page, extra = self._include_metadata_rows(
                page,
                selection=selection,
                county_name=county_name,
            )
            requests_made += extra
        return (
            form,
            page,
            county_name,
            tuple(source_refs),
            requests_made,
        )

    @staticmethod
    def _verify_anchor(page: ResultsPage, cursor: CursorState) -> None:
        if page.current_page != cursor.anchor_page:
            return
        if cursor.anchor_index >= len(page.records):
            raise MarylandPlatsSelectionError(
                "cursor_anchor_missing",
                "Cursor anchor row is no longer present on its native page",
            )
        record = page.records[cursor.anchor_index]
        representation = record["source_result_representation"][
            "representation_identity"
        ]
        if representation != cursor.anchor_representation_identity:
            raise MarylandPlatsSelectionError(
                "cursor_anchor_changed",
                "Cursor anchor representation changed in the live result set",
            )

    @staticmethod
    def _verify_series_results(
        page: ResultsPage,
        selection: SearchSelection,
    ) -> None:
        if selection.mode != "series":
            return
        expected = {
            "archive_qualifier": selection.qualifier,
            "archive_series": selection.series,
        }
        if selection.unit is not None:
            expected["archive_unit"] = selection.unit

        def matches(
            identity: Mapping[str, Any],
            key: str,
            expected_value: str | None,
        ) -> bool:
            observed_value = identity.get(key)
            if (
                key == "archive_unit"
                and isinstance(observed_value, str)
                and isinstance(expected_value, str)
                and observed_value.isdigit()
                and expected_value.isdigit()
            ):
                return int(observed_value) == int(expected_value)
            return observed_value == expected_value

        for record in page.records:
            identity = record["record_identity"]
            mismatches = {
                key: {
                    "expected": value,
                    "observed": identity.get(key),
                }
                for key, value in expected.items()
                if not matches(identity, key, value)
            }
            if mismatches:
                raise MarylandPlatsSourceChangedError(
                    "series_result_identity_mismatch",
                    (
                        "PLATS.NET returned a record outside the selected "
                        "archive series identity"
                    ),
                    details={"mismatches": mismatches},
                )

    def search(
        self,
        selection: SearchSelection,
        *,
        limit: int | None = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> SearchResult:
        if limit is not None and (
            isinstance(limit, bool) or limit <= 0
        ):
            raise MarylandPlatsSelectionError(
                "limit_invalid",
                "Search limit must be a positive integer",
            )
        cursor_state = _decode_cursor(
            cursor,
            selection_fingerprint=selection.fingerprint,
        )
        form, page, county_name, source_refs, requests_made = (
            self._initial_search(selection)
        )
        self._verify_series_results(page, selection)
        pages_fetched = 1
        fingerprints = [page.schema_fingerprint]
        if (
            cursor_state is not None
            and cursor_state.form_contract_fingerprint
            != form.contract_fingerprint
        ):
            raise MarylandPlatsSelectionError(
                "cursor_form_contract_mismatch",
                "Cursor was created from a different PLATS.NET form contract",
            )
        if cursor_state and cursor_state.target_page > page.total_pages:
            raise MarylandPlatsSelectionError(
                "cursor_page_missing",
                "Cursor target page is outside the live result set",
                details={
                    "target_page": cursor_state.target_page,
                    "total_pages": page.total_pages,
                },
            )

        anchor_verified = cursor_state is None
        target_page = cursor_state.target_page if cursor_state else 1
        while page.current_page < target_page:
            if cursor_state and page.current_page == cursor_state.anchor_page:
                self._verify_anchor(page, cursor_state)
                anchor_verified = True
            page, extra = self._next_page(
                page,
                selection=selection,
                county_name=county_name,
            )
            self._verify_series_results(page, selection)
            requests_made += extra
            pages_fetched += 1
            fingerprints.append(page.schema_fingerprint)
            source_refs += (page.source_url,)
        if cursor_state and page.current_page == cursor_state.anchor_page:
            self._verify_anchor(page, cursor_state)
            anchor_verified = True
        if not anchor_verified:
            raise MarylandPlatsSelectionError(
                "cursor_anchor_page_missing",
                "Cursor anchor page is not reachable before its target page",
            )

        offset = cursor_state.target_offset if cursor_state else 0
        if offset > len(page.records):
            raise MarylandPlatsSelectionError(
                "cursor_offset_missing",
                "Cursor row offset is outside its live native page",
            )
        returned: list[Mapping[str, Any]] = []
        last_page: ResultsPage | None = None
        last_index: int | None = None
        while limit is None or len(returned) < limit:
            while offset < len(page.records) and (
                limit is None or len(returned) < limit
            ):
                returned.append(page.records[offset])
                last_page = page
                last_index = offset
                offset += 1
            if (
                limit is not None
                and len(returned) >= limit
            ) or not page.has_next:
                break
            page, extra = self._next_page(
                page,
                selection=selection,
                county_name=county_name,
            )
            self._verify_series_results(page, selection)
            requests_made += extra
            pages_fetched += 1
            fingerprints.append(page.schema_fingerprint)
            source_refs += (page.source_url,)
            offset = 0

        next_cursor = None
        if (
            returned
            and last_page is not None
            and last_index is not None
            and (offset < len(page.records) or page.has_next)
        ):
            if offset < len(page.records):
                next_target_page = page.current_page
                next_target_offset = offset
            else:
                next_target_page = page.current_page + 1
                next_target_offset = 0
            last_representation = returned[-1][
                "source_result_representation"
            ]["representation_identity"]
            next_cursor = _encode_cursor(
                CursorState(
                    selection_fingerprint=selection.fingerprint,
                    form_contract_fingerprint=form.contract_fingerprint,
                    target_page=next_target_page,
                    target_offset=next_target_offset,
                    anchor_page=last_page.current_page,
                    anchor_index=last_index,
                    anchor_representation_identity=last_representation,
                )
            )
        return SearchResult(
            records=tuple(returned),
            next_cursor=next_cursor,
            raw_artifact_refs=tuple(dict.fromkeys(source_refs)),
            pages_fetched=pages_fetched,
            requests_made=requests_made,
            source_image_result_count=page.image_result_count,
            source_total_result_count=page.total_result_count,
            source_total_pages=page.total_pages,
            form_contract_fingerprint=form.contract_fingerprint,
            result_schema_fingerprints=tuple(dict.fromkeys(fingerprints)),
        )

    def fetch_plat(
        self,
        county_code: str,
        qualifier: str,
        series: str,
        unit: str,
    ) -> dict[str, Any]:
        url = _unit_url(
            county_code.upper(),
            qualifier.upper(),
            series,
            unit,
        )
        response = self._request(
            "GET",
            url,
            allow_redirects=True,
        )
        return parse_plat_detail(
            str(response.text),
            source_url=str(getattr(response, "url", url)),
            county_code=county_code.upper(),
            expected_qualifier=qualifier,
            expected_series=series,
            expected_unit=unit,
        )

    def fetch_artifact(self, source_url: str) -> DownloadedArtifact:
        safe_url = _official_artifact_url(source_url)
        response = self._request(
            "GET",
            safe_url,
            referer=UNIT_URL,
            allow_redirects=True,
            expect_html=False,
        )
        final_url = _official_artifact_url(
            str(getattr(response, "url", safe_url))
        )
        content = bytes(getattr(response, "content", b""))
        suffix = Path(urlsplit(final_url).path).suffix.casefold()
        valid_signature = {
            ".pdf": content.startswith(b"%PDF-"),
            ".tif": content.startswith((b"II*\x00", b"MM\x00*")),
            ".tiff": content.startswith((b"II*\x00", b"MM\x00*")),
            ".jpg": content.startswith(b"\xff\xd8\xff"),
            ".jpeg": content.startswith(b"\xff\xd8\xff"),
        }[suffix]
        if not content or not valid_signature:
            raise MarylandPlatsSourceChangedError(
                "artifact_signature_invalid",
                "PLATS.NET artifact content does not match its published format",
                details={
                    "url": final_url,
                    "size_bytes": len(content),
                    "suffix": suffix,
                },
            )
        content_type = (
            (_response_header(response, "Content-Type") or MEDIA_TYPES[suffix])
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        return DownloadedArtifact(
            source_url=final_url,
            content=content,
            media_type=content_type,
            sha256=hashlib.sha256(content).hexdigest(),
            etag=_response_header(response, "ETag"),
            last_modified=_response_header(response, "Last-Modified"),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _source_manifest() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "official_routes": {
            "landing": INDEX_URL,
            "county_search_template": SEARCH_URL_TEMPLATE,
            "exact_unit": UNIT_URL,
            "faq": FAQ_URL,
            "advanced_search_guide": ADVANCED_GUIDE_URL,
        },
        "operations": {
            "sources": (
                "show source, transport, identities, and separately "
                "attributed complementary routes"
            ),
            "counties": "discover the current 24 county/city source codes",
            "search": {
                "basic": [
                    "book_and_page",
                    "plat_or_box_number",
                    "right_of_way_plat",
                ],
                "advanced": [
                    "filing_date",
                    "description",
                    "book_or_plat_number",
                    "page_number",
                    "clerk_initials",
                    "sort",
                ],
                "series": [
                    "archive_qualifier",
                    "archive_series",
                    "archive_unit",
                    "sort",
                ],
                "continuation": "source-native WebForms next-page postback",
                "omitted_limit": "complete source-reported result set",
            },
            "plat": (
                "fetch an exact county/qualifier/series/unit detail, including "
                "metadata-only units"
            ),
            "download": "download and hash one source-published artifact URL",
            "probe": (
                "verify county selector, exact series search, exact unit "
                "detail, and one published artifact"
            ),
        },
        "identity": {
            "record": [
                "county_code",
                "archive_qualifier",
                "archive_series",
                "archive_unit",
            ],
            "court_reference": (
                "raw source reference with book, page, plat, box, and "
                "right-of-way fields parsed only when explicitly labeled"
            ),
            "search_occurrence": [
                "search_criteria_fingerprint",
                "absolute_source_position",
                "representation_identity",
            ],
            "representation": [
                "filed_date",
                "description",
                "developer_owner",
                "reference",
                "direct_scan_count",
                "microfilm_scan_count",
            ],
            "artifact": [
                "record_identity",
                "artifact_role",
                "ordinal_within_role",
                "source_label",
                "source_filename",
            ],
        },
        "transport_observation": {
            "form_family": "ASP.NET WebForms",
            "search_redirect": "session-scoped results.aspx location",
            "observed_native_page_capacity": 300,
            "next_page_control": "ctl00$body$imgButtonNext",
            "exact_detail_without_search_session": True,
            "metadata_only_detail_observed": True,
        },
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
    }


def _required_text(value: str | None, field_name: str) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise MarylandPlatsSelectionError(
            "selection_missing",
            f"{field_name} must not be empty",
            details={"field": field_name},
        )
    return cleaned


def _county_code(value: str) -> str:
    code = _required_text(value, "county").upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise MarylandPlatsSelectionError(
            "county_code_invalid",
            "PLATS.NET county code must be the two-letter source code",
            details={"county_code": code},
        )
    return code


def _series_token(value: str, field_name: str) -> str:
    token = _required_text(value, field_name)
    if not re.fullmatch(r"[A-Za-z0-9.-]+", token):
        raise MarylandPlatsSelectionError(
            "archive_identity_invalid",
            f"{field_name} contains characters outside the source identity",
            details={"field": field_name, "value": token},
        )
    return token


def _search_selection(args: argparse.Namespace) -> SearchSelection:
    county = _county_code(args.county)
    mode = args.mode
    values = {
        "book_number": _clean_text(args.book),
        "page_number": _clean_text(args.page),
        "plat_number": _clean_text(args.plat),
        "right_of_way_number": _clean_text(args.right_of_way),
        "filed_date": _clean_text(args.date),
        "description": _clean_text(args.description),
        "clerk_initials": _clean_text(args.clerk_initials),
        "qualifier": (
            _clean_text(args.qualifier).upper()
            if _clean_text(args.qualifier)
            else None
        ),
        "series": _clean_text(args.series),
        "unit": _clean_text(args.unit),
    }
    if mode == "basic":
        basic_groups = [
            values["book_number"] is not None,
            values["plat_number"] is not None,
            values["right_of_way_number"] is not None,
        ]
        if sum(basic_groups) != 1:
            raise MarylandPlatsSelectionError(
                "basic_selection_invalid",
                (
                    "Basic search requires exactly one of --book, --plat, "
                    "or --right-of-way"
                ),
            )
        if (
            values["page_number"] is not None
            and values["book_number"] is None
        ):
            raise MarylandPlatsSelectionError(
                "basic_page_without_book",
                "Basic --page is paired with --book",
            )
        unexpected = [
            key
            for key in (
                "filed_date",
                "description",
                "clerk_initials",
                "qualifier",
                "series",
                "unit",
            )
            if values[key] is not None
        ]
        if unexpected:
            raise MarylandPlatsSelectionError(
                "basic_fields_conflict",
                "Basic search received fields from another source search form",
                details={"fields": unexpected},
            )
    elif mode == "advanced":
        if not any(
            values[key] is not None
            for key in (
                "filed_date",
                "description",
                "book_number",
                "page_number",
                "clerk_initials",
            )
        ):
            raise MarylandPlatsSelectionError(
                "advanced_selection_empty",
                "Advanced search requires at least one published search field",
            )
        if values["filed_date"] is not None:
            try:
                datetime.strptime(values["filed_date"], "%Y/%m/%d")
            except ValueError as error:
                raise MarylandPlatsSelectionError(
                    "advanced_date_invalid",
                    "Advanced search date must use the source's YYYY/MM/DD form",
                    details={"value": values["filed_date"]},
                ) from error
        unexpected = [
            key
            for key in (
                "plat_number",
                "right_of_way_number",
                "qualifier",
                "series",
                "unit",
            )
            if values[key] is not None
        ]
        if unexpected:
            raise MarylandPlatsSelectionError(
                "advanced_fields_conflict",
                "Advanced search received fields from another source search form",
                details={"fields": unexpected},
            )
    elif mode == "series":
        if values["qualifier"] not in {"C", "S"}:
            raise MarylandPlatsSelectionError(
                "series_qualifier_invalid",
                "Series search qualifier must be C or S as published by PLATS.NET",
            )
        if values["series"] is None:
            raise MarylandPlatsSelectionError(
                "series_missing",
                "Series search requires --series",
            )
        values["series"] = _series_token(values["series"], "series")
        if values["unit"] is not None:
            values["unit"] = _series_token(values["unit"], "unit")
        unexpected = [
            key
            for key in (
                "book_number",
                "page_number",
                "plat_number",
                "right_of_way_number",
                "filed_date",
                "description",
                "clerk_initials",
            )
            if values[key] is not None
        ]
        if unexpected:
            raise MarylandPlatsSelectionError(
                "series_fields_conflict",
                "Series search received fields from another source search form",
                details={"fields": unexpected},
            )
    else:
        raise MarylandPlatsSelectionError(
            "search_mode_invalid",
            "Unknown PLATS.NET search mode",
            details={"mode": mode},
        )
    return SearchSelection(
        county_code=county,
        mode=mode,
        sort=args.sort,
        include_no_images=bool(args.include_no_images),
        **values,
    )


def _query(
    *,
    operation: str,
    parameters: Mapping[str, Any],
    requested_limit: int | None = None,
    cursor: str | None = None,
    execution_metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={
                "adapter_schema": OUTPUT_SCHEMA_VERSION,
                **dict(execution_metadata or {}),
            },
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: MarylandPlatsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _client_from_args(args: argparse.Namespace) -> MarylandPlatsClient:
    return MarylandPlatsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: MarylandPlatsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one command and return the shared public-record envelope."""

    query: PublicRecordsQuery | None = None
    source_client = client
    own_client = client is None
    try:
        if args.command == "sources":
            query = _query(operation="sources", parameters={})
            result = PublicRecordsResult.success(
                query,
                [_source_manifest()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            source_client = source_client or _client_from_args(args)
            if args.command == "counties":
                query = _query(operation="counties", parameters={})
                counties = source_client.counties()
                county_codes = [county.code for county in counties]
                if len(county_codes) != 24 or len(set(county_codes)) != 24:
                    raise MarylandPlatsSourceChangedError(
                        "county_selector_changed",
                        (
                            "PLATS.NET county selector no longer contains "
                            "24 distinct jurisdictions"
                        ),
                        details={
                            "observed_count": len(county_codes),
                            "distinct_count": len(set(county_codes)),
                        },
                    )
                result = PublicRecordsResult.success(
                    query,
                    [county.to_record() for county in counties],
                    raw_artifact_refs=[
                        SEARCH_URL_TEMPLATE.format(county_code="MO")
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "search":
                selection = _search_selection(args)
                query = _query(
                    operation="search",
                    parameters=selection.to_dict(),
                    requested_limit=args.limit,
                    cursor=args.cursor,
                )
                search = source_client.search(
                    selection,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                execution_metadata: dict[str, Any] = {
                    "form_contract_fingerprint": (
                        search.form_contract_fingerprint
                    ),
                    "result_schema_fingerprints": list(
                        search.result_schema_fingerprints
                    ),
                    "native_pages_fetched": search.pages_fetched,
                    "requests_made": search.requests_made,
                    "return_bound": (
                        "caller_selected"
                        if args.limit is not None
                        else "complete_source_reported_result_set"
                    ),
                    "source_total_result_count": (
                        search.source_total_result_count
                    ),
                    "source_image_result_count": (
                        search.source_image_result_count
                    ),
                    "source_total_pages": search.source_total_pages,
                }
                query = _query(
                    operation="search",
                    parameters=selection.to_dict(),
                    requested_limit=args.limit,
                    cursor=args.cursor,
                    execution_metadata=execution_metadata,
                )
                result = PublicRecordsResult.success(
                    query,
                    search.records,
                    next_cursor=search.next_cursor,
                    raw_artifact_refs=search.raw_artifact_refs,
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "plat":
                county = _county_code(args.county)
                qualifier = _required_text(
                    args.qualifier,
                    "qualifier",
                ).upper()
                if qualifier not in {"C", "S"}:
                    raise MarylandPlatsSelectionError(
                        "plat_qualifier_invalid",
                        "Plat qualifier must be C or S",
                    )
                series = _series_token(args.series, "series")
                unit = _series_token(args.unit, "unit")
                parameters = {
                    "county_code": county,
                    "qualifier": qualifier,
                    "series": series,
                    "unit": unit,
                }
                query = _query(operation="plat", parameters=parameters)
                record = source_client.fetch_plat(
                    county,
                    qualifier,
                    series,
                    unit,
                )
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[
                        record["provenance"]["source_url"],
                        *[
                            artifact["source_url"]
                            for artifact in record["artifacts"]
                        ],
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "download":
                safe_url = _official_artifact_url(args.url)
                parameters = {
                    "source_url": safe_url,
                    "destination": str(args.destination),
                }
                query = _query(
                    operation="download",
                    parameters=parameters,
                )
                artifact = source_client.fetch_artifact(safe_url)
                args.destination.parent.mkdir(parents=True, exist_ok=True)
                args.destination.write_bytes(artifact.content)
                native_id = sha256_fingerprint(
                    {"source_url": artifact.source_url}
                )
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "plat_artifact_download",
                    "canonical_ref": canonical_property_ref(
                        SOURCE_ID,
                        STATE_GEOID,
                        "plat-artifact",
                        native_id,
                    ),
                    "source_artifact_locator_identity": native_id,
                    "source_url": artifact.source_url,
                    "local_path": str(args.destination),
                    "media_type": artifact.media_type,
                    "size_bytes": len(artifact.content),
                    "content_sha256": artifact.sha256,
                    "etag": artifact.etag,
                    "last_modified": artifact.last_modified,
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[
                        artifact.source_url,
                        str(args.destination),
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                parameters = {
                    "county_code": "MO",
                    "qualifier": "C",
                    "series": "1136",
                    "unit": "1",
                }
                query = _query(operation="probe", parameters=parameters)
                counties = source_client.counties()
                county_codes = [county.code for county in counties]
                if len(county_codes) != 24 or len(set(county_codes)) != 24:
                    raise MarylandPlatsSourceChangedError(
                        "county_selector_changed",
                        (
                            "PLATS.NET county selector no longer contains "
                            "24 distinct jurisdictions"
                        ),
                        details={
                            "observed_count": len(county_codes),
                            "distinct_count": len(set(county_codes)),
                        },
                    )
                probe_selection = SearchSelection(
                    county_code="MO",
                    mode="series",
                    qualifier="C",
                    series="1136",
                    unit="1",
                )
                search = source_client.search(probe_selection, limit=1)
                if not search.records:
                    raise MarylandPlatsSourceChangedError(
                        "probe_result_missing",
                        "PLATS.NET probe series search returned no sample plat",
                    )
                detail = source_client.fetch_plat("MO", "C", "1136", "1")
                search_identity = search.records[0]["record_identity"]
                if search_identity != detail["record_identity"]:
                    raise MarylandPlatsSourceChangedError(
                        "probe_identity_mismatch",
                        (
                            "PLATS.NET probe search and exact detail returned "
                            "different archive identities"
                        ),
                        details={
                            "search_identity": search_identity,
                            "detail_identity": detail["record_identity"],
                        },
                    )
                compiled_pdf = next(
                    (
                        item
                        for item in detail["artifacts"]
                        if item["artifact_role"] == "compiled_pdf"
                    ),
                    None,
                )
                if compiled_pdf is None:
                    raise MarylandPlatsSourceChangedError(
                        "probe_pdf_missing",
                        "PLATS.NET probe unit has no compiled PDF",
                    )
                artifact = source_client.fetch_artifact(
                    compiled_pdf["source_url"]
                )
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "county_count": len(counties),
                    "sample_record_identity": detail["record_identity"],
                    "sample_search_representation_identity": search.records[
                        0
                    ]["source_result_representation"][
                        "representation_identity"
                    ],
                    "form_contract_fingerprint": (
                        search.form_contract_fingerprint
                    ),
                    "result_schema_fingerprints": list(
                        search.result_schema_fingerprints
                    ),
                    "detail_representation_identity": detail[
                        "representation_identity"
                    ],
                    "published_artifact_count": detail[
                        "published_artifact_count"
                    ],
                    "compiled_pdf": {
                        "source_url": artifact.source_url,
                        "media_type": artifact.media_type,
                        "size_bytes": len(artifact.content),
                        "sha256": artifact.sha256,
                    },
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[
                        SEARCH_URL_TEMPLATE.format(county_code="MO"),
                        *search.raw_artifact_refs,
                        detail["provenance"]["source_url"],
                        artifact.source_url,
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                raise AssertionError(f"unknown command: {args.command}")
    except MarylandPlatsError as error:
        query = query or _query(
            operation=args.command,
            parameters={"command": args.command},
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        )
        result = _failure(query, error)
    finally:
        if own_client and source_client is not None:
            source_client.close()

    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Maryland State Archives PLATS.NET recorded plats"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Show source identity, transport, and complementary routes",
    )
    _add_runtime_and_output(sources)

    counties = subparsers.add_parser(
        "counties",
        help="Discover current PLATS.NET county codes",
    )
    _add_runtime_and_output(counties)

    search = subparsers.add_parser(
        "search",
        help="Run one source-native basic, advanced, or series search",
    )
    search.add_argument("county", help="Two-letter PLATS.NET county code")
    search.add_argument(
        "--mode",
        choices=("basic", "advanced", "series"),
        required=True,
    )
    search.add_argument("--book")
    search.add_argument("--page")
    search.add_argument("--plat")
    search.add_argument("--right-of-way")
    search.add_argument("--date", help="Source filing date in YYYY/MM/DD form")
    search.add_argument("--description")
    search.add_argument("--clerk-initials")
    search.add_argument("--qualifier", choices=("C", "S"))
    search.add_argument("--series")
    search.add_argument("--unit")
    search.add_argument(
        "--sort",
        choices=tuple(SORT_VALUES),
        default="date_desc",
    )
    search.add_argument(
        "--include-no-images",
        action="store_true",
        help="Enable the source's metadata-only result rows",
    )
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help=(
            "Caller-selected return bound; omitted traverses the complete "
            "source-reported result set"
        ),
    )
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    plat = subparsers.add_parser(
        "plat",
        help="Fetch one exact county/archive series/unit detail",
    )
    plat.add_argument("county")
    plat.add_argument("qualifier", choices=("C", "S"))
    plat.add_argument("series")
    plat.add_argument("unit")
    _add_runtime_and_output(plat)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one source-published plat artifact",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify form, search, detail, and artifact surfaces",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    handled = write_output(
        payload,
        args,
        summary=f"{SOURCE_ID} {args.command}",
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
    )
    if not handled:
        print(json.dumps(payload, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
