#!/usr/bin/env python3
"""Query official Ohio RealAuction sheriff-sale calendars and public listings.

Franklin, Delaware, and Licking Counties use official county tenants of the
same RealAuction application.  The public calendar, auction preview, listing
JSON, and status JSON are anonymous.  Bidding and the separate
``DETAILS&AID=`` view are account functions and are not needed by this adapter.

The native listing endpoint is session-bound to an auction date.  Waiting and
closed/canceled areas use 10-row pages.  Omitting ``--limit`` traverses every
native page.  An explicit limit returns a query- and ordered-membership-bound
cursor; mutable status and amount fields are refreshed on continuation.

Examples:
    uv run python tools/query_ohio_sheriff_sales.py source franklin --json
    uv run python tools/query_ohio_sheriff_sales.py calendar franklin \
        --month 2026-07 --json
    uv run python tools/query_ohio_sheriff_sales.py auctions licking \
        --date 2026-07-30 --json
    uv run python tools/query_ohio_sheriff_sales.py auctions franklin \
        --date 2026-07-10 --case-number 25CV --limit 20 \
        --output /tmp/franklin-sales.json
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
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

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
    )
    from public_records_store import canonical_property_ref


OBSERVED_AT = "2026-07-30"
STATE_CODE = "OH"
NATIVE_PAGE_SIZE = 10
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
CURSOR_PREFIX = "oh-realauction:v1:"

AREA_LABELS = {
    "R": "running",
    "W": "waiting",
    "C": "closed_or_canceled",
}
AREA_CODES = {value: key for key, value in AREA_LABELS.items()}
DEFAULT_AREAS = ("R", "W", "C")
PROBE_SENTINEL_DATES = {
    "franklin": "2026-07-10",
    "delaware": "2026-07-29",
    "licking": "2026-07-30",
}

EXPECTED_LISTING_LABELS = (
    "Case Status",
    "Case #",
    "Parcel ID",
    "Property Address",
    "Appraised Value",
    "Opening Bid",
    "Deposit Requirement",
)
LISTING_SCHEMA_FINGERPRINT = hashlib.sha256(
    canonical_json(
        {
            "platform": "ohio_realauction",
            "listing_labels": EXPECTED_LISTING_LABELS,
            "listing_tokens": [
                "@A",
                "@B",
                "@C",
                "@D",
                "@E",
                "@F",
                "@G",
                "@H",
                "@I",
                "@J",
                "@K",
                "@L",
            ],
            "native_areas": AREA_LABELS,
        }
    ).encode("utf-8")
).hexdigest()

SOURCE_WARNINGS = (
    "A sheriff-sale listing is an auction and case-status observation; verify "
    "the court confirmation and recorded sheriff's deed before treating it as "
    "evidence that title transferred.",
    "Case numbers and parcel identifiers are useful cross-source selectors but "
    "are not the native auction identity; one case may be scheduled more than "
    "once. The stable source identity is the county tenant plus AID.",
)


@dataclass(frozen=True)
class Tenant:
    slug: str
    source_id: str
    name: str
    county_geoid: str
    county_name: str
    base_url: str
    official_info_url: str
    sale_weekday: str
    sale_time: str
    alternatives: tuple[Mapping[str, Any], ...]

    @property
    def index_url(self) -> str:
        return f"{self.base_url}/index.cfm"


TENANTS: Mapping[str, Tenant] = {
    "franklin": Tenant(
        slug="franklin",
        source_id="us-oh-franklin-sheriff-realauction",
        name="Franklin County Official Sheriff SaleAuction",
        county_geoid="39049",
        county_name="Franklin County, Ohio",
        base_url="https://franklin.sheriffsaleauction.ohio.gov",
        official_info_url=(
            "https://sheriff.franklincountyohio.gov/Services/"
            "Real-Estate-Sales"
        ),
        sale_weekday="Friday",
        sale_time="09:00 America/New_York",
        alternatives=(
            {
                "name": "Franklin County Clerk Case Information Online",
                "url": (
                    "https://fcdcfcjs.co.franklin.oh.us/"
                    "CaseInformationOnline/"
                ),
                "relationship": "case_number_to_civil_docket_and_filings",
                "fields": [
                    "case_number",
                    "case_type",
                    "parties",
                    "docket_events",
                ],
                "access_observation": "officially_linked_public_case_index",
            },
            {
                "name": "Franklin County Auditor and Treasurer searches",
                "url": "https://treapropsearch.franklincountyohio.gov/",
                "relationship": "parcel_to_tax_and_assessment_context",
                "fields": [
                    "parcel",
                    "tax_balance",
                    "tax_history",
                    "assessed_value",
                ],
                "access_observation": "officially_linked_anonymous_search",
            },
        ),
    ),
    "delaware": Tenant(
        slug="delaware",
        source_id="us-oh-delaware-sheriff-realauction",
        name="Delaware County Official Sheriff SaleAuction",
        county_geoid="39041",
        county_name="Delaware County, Ohio",
        base_url="https://delaware.sheriffsaleauction.ohio.gov",
        official_info_url=(
            "https://sheriff.co.delaware.oh.us/sheriff-sales/"
        ),
        sale_weekday="Wednesday",
        sale_time="10:00 America/New_York",
        alternatives=(
            {
                "name": "Delaware County Sheriff sale table",
                "url": "https://sheriff.co.delaware.oh.us/sheriff-sales/",
                "relationship": "county_published_sale_history_and_tax_sales",
                "fields": [
                    "sale_date",
                    "address",
                    "recorder_volume_page",
                    "case_number",
                    "appraisal",
                    "deposit",
                    "purchaser",
                    "purchase_price",
                ],
                "access_observation": "anonymous_official_html",
            },
            {
                "name": "Delaware County delinquent land tax notice",
                "url": (
                    "https://auditor.co.delaware.oh.us/wp-content/uploads/"
                    "sites/23/2018/11/delqadvertisinglist.pdf"
                ),
                "relationship": "pre_foreclosure_delinquent_tax_inventory",
                "fields": [
                    "parcel",
                    "owner_name",
                    "legal_description",
                    "delinquent_amount",
                ],
                "access_observation": "anonymous_official_pdf",
            },
            {
                "name": "Delaware County Clerk eServices",
                "url": "https://court.co.delaware.oh.us/eservices/home.page",
                "relationship": "case_number_to_civil_docket",
                "fields": ["case_number", "parties", "docket_events"],
                "access_observation": "officially_linked_case_index",
            },
        ),
    ),
    "licking": Tenant(
        slug="licking",
        source_id="us-oh-licking-sheriff-realauction",
        name="Licking County Official Sheriff SaleAuction",
        county_geoid="39089",
        county_name="Licking County, Ohio",
        base_url="https://licking.sheriffsaleauction.ohio.gov",
        official_info_url=(
            "https://apps.lickingcounty.gov/sheriff/foreclosures/"
        ),
        sale_weekday="Thursday",
        sale_time="10:30 America/New_York",
        alternatives=(
            {
                "name": "Licking County Sheriff foreclosure JSON",
                "url": (
                    "https://apps.lickingcounty.gov/sheriff/foreclosures/"
                    "api/foreclosures/?year={year}"
                ),
                "year_inventory_url": (
                    "https://apps.lickingcounty.gov/sheriff/foreclosures/"
                    "api/saleyears/"
                ),
                "detail_url_template": (
                    "https://apps.lickingcounty.gov/sheriff/foreclosures/"
                    "api/foreclosures/{case_number}"
                ),
                "relationship": "county_archive_and_field_richer_fallback",
                "fields": [
                    "sale_date",
                    "case_number",
                    "address",
                    "parcel",
                    "appraisal",
                    "terms",
                    "sale_type",
                    "deposit",
                    "status",
                    "purchaser",
                    "purchase_price",
                ],
                "access_observation": (
                    "anonymous_official_json; years 2000-2026 observed"
                ),
            },
            {
                "name": "Licking County Common Pleas case records",
                "url": (
                    "https://lickingcounty.gov/depts/clerk/"
                    "records_search.htm"
                ),
                "relationship": "case_number_to_docket_and_pleadings",
                "fields": [
                    "case_number",
                    "parties",
                    "docket_events",
                    "remote_pleadings",
                ],
                "access_observation": "official_remote_case_records_route",
            },
        ),
    ),
}
TENANTS_BY_SOURCE_ID: Mapping[str, Tenant] = {
    tenant.source_id: tenant for tenant in TENANTS.values()
}


class OhioSheriffSaleError(RuntimeError):
    """Base class for a verified source or query failure."""


class OhioSheriffSaleSelectionError(OhioSheriffSaleError):
    """A caller selector or continuation cursor is invalid."""

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


class OhioSheriffSaleTransportError(OhioSheriffSaleError):
    """The official source was unreachable after bounded retries."""


class OhioSheriffSaleHTTPError(OhioSheriffSaleError):
    """The official source returned a non-success HTTP status."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(
            f"Ohio RealAuction returned HTTP {status_code} for {url}"
        )


class OhioSheriffSaleRateLimited(OhioSheriffSaleError):
    """The official source returned HTTP 429."""


class OhioSheriffSaleSourceChanged(OhioSheriffSaleError):
    """A verified HTML or JSON schema changed."""


class OhioSheriffSaleSnapshotChanged(OhioSheriffSaleError):
    """The live auction membership changed during traversal."""


@dataclass(frozen=True)
class TextResponse:
    text: str
    url: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class ListingPage:
    area: str
    page: int
    records: tuple[dict[str, Any], ...]
    auction_ids: tuple[str, ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class AuctionFetch:
    records: tuple[dict[str, Any], ...]
    pages_fetched: Mapping[str, int]
    source_page_counts: Mapping[str, int]
    preview_url: str
    listing_schema_fingerprint: str


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = (
        value.get_text(" ", strip=True)
        if hasattr(value, "get_text")
        else str(value)
    )
    return re.sub(r"\s+", " ", text).strip()


def _parse_iso_date(value: str) -> str:
    candidate = value.strip()
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def _parse_iso_month(value: str) -> str:
    candidate = value.strip()
    try:
        parsed = datetime.strptime(candidate, "%Y-%m")
    except ValueError as error:
        raise argparse.ArgumentTypeError("month must use YYYY-MM") from error
    return parsed.strftime("%Y-%m")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("limit must be positive")
    return parsed


def _money_amount(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if not cleaned:
        return None
    try:
        return format(Decimal(cleaned), "f")
    except InvalidOperation:
        return None


def _source_metadata(tenant: Tenant) -> SourceMetadata:
    return SourceMetadata(
        source_id=tenant.source_id,
        name=tenant.name,
        source_role=(
            "official_county_judicial_and_tax_foreclosure_auction_"
            "calendar_listing_and_outcome_observations"
        ),
        base_url=tenant.base_url,
        dataset_id=f"realauction-ohio-{tenant.slug}",
        metadata={
            "authority": f"{tenant.county_name} Sheriff",
            "operator": "Realauction",
            "platform_family": "realauction_ohio_coldfusion",
            "authentication": {
                "calendar": "none",
                "public_preview": "none",
                "public_listing_json": "none",
                "public_status_json": "none",
                "bidding": "account",
                "separate_aid_detail": "account",
            },
            "native_identity_key": "tenant_and_aid",
            "native_page_size": NATIVE_PAGE_SIZE,
            "observed_at": OBSERVED_AT,
        },
    )


def _jurisdiction(tenant: Tenant) -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=tenant.county_geoid,
        name=tenant.county_name,
        state_code=STATE_CODE,
        county_fips=tenant.county_geoid,
        locality=tenant.county_name.removesuffix(", Ohio"),
    )


def _query(
    tenant: Tenant,
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_metadata(tenant),
        jurisdiction=_jurisdiction(tenant),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "source_page_size": NATIVE_PAGE_SIZE,
                "default_result_cap": None,
            },
        ),
    )


def _endpoint(tenant: Tenant, parameters: Mapping[str, Any]) -> str:
    return f"{tenant.index_url}?{urlencode(parameters)}"


def _month_source_value(month: str) -> str:
    parsed = datetime.strptime(month, "%Y-%m")
    return f"{parsed.month:02d}/01/{parsed.year:04d}"


def _date_source_value(iso_date: str) -> str:
    parsed = date.fromisoformat(iso_date)
    return parsed.strftime("%m/%d/%Y")


def _source_record(tenant: Tenant) -> dict[str, Any]:
    calendar_parameters = {
        "zaction": "USER",
        "zmethod": "CALENDAR",
        "selCalDate": "MM/01/YYYY",
    }
    preview_parameters = {
        "zaction": "AUCTION",
        "Zmethod": "PREVIEW",
        "AUCTIONDATE": "MM/DD/YYYY",
    }
    return {
        "canonical_ref": canonical_property_ref(
            tenant.source_id,
            tenant.county_geoid,
            "source-contract",
            "realauction-ohio-v1",
        ),
        "source_id": tenant.source_id,
        "record_kind": "source_contract",
        "platform_family": "realauction_ohio_coldfusion",
        "county": tenant.county_name,
        "county_geoid": tenant.county_geoid,
        "publisher": f"{tenant.county_name} Sheriff",
        "operator": "Realauction",
        "official_info_url": tenant.official_info_url,
        "observed_at": OBSERVED_AT,
        "sale_schedule": {
            "weekday": tenant.sale_weekday,
            "time": tenant.sale_time,
        },
        "access": {
            "calendar": "anonymous",
            "preview": "anonymous",
            "listing_json": "anonymous",
            "status_json": "anonymous",
            "bidding": "account",
            "separate_aid_detail": "account",
            "observation": (
                "direct requests returned HTTP 200 for all three target "
                "tenants; a generic web crawler returned 403 for two roots"
            ),
        },
        "verification": {
            "observed_at": OBSERVED_AT,
            "sentinel_auction_date": PROBE_SENTINEL_DATES[tenant.slug],
            "routes_exercised": [
                "root_session_bootstrap",
                "monthly_calendar",
                "auction_preview",
                "listing_json",
                "status_json",
            ],
        },
        "endpoints": {
            "calendar": _endpoint(tenant, calendar_parameters),
            "preview": _endpoint(tenant, preview_parameters),
            "listing_json": _endpoint(
                tenant,
                {
                    "zaction": "AUCTION",
                    "Zmethod": "UPDATE",
                    "FNC": "LOAD",
                    "AREA": "{R|W|C}",
                    "PageDir": 0,
                    "doR": 1,
                    "bypassPage": "{page}",
                    "test": 1,
                },
            ),
            "status_json": _endpoint(
                tenant,
                {
                    "zaction": "AUCTION",
                    "ZMETHOD": "UPDATE",
                    "FNC": "UPDATE",
                    "ref": "{comma-separated-AIDs}",
                },
            ),
        },
        "native_identity": {
            "key": "tenant_and_aid",
            "case_number_is_identity": False,
            "reason": "one court case can be scheduled for multiple auctions",
        },
        "native_pagination": {
            "areas": dict(AREA_LABELS),
            "page_size": NATIVE_PAGE_SIZE,
            "page_selector": "bypassPage",
            "page_counts": {
                "waiting": "WM from status JSON",
                "closed_or_canceled": "CM from status JSON",
                "running": "single current area",
            },
            "observed_multi_page_sentinel": {
                "tenant": "franklin",
                "auction_date": "2026-07-10",
                "scheduled_count": 23,
                "closed_page_sizes": [10, 10, 3],
            },
            "continuation_consistency": (
                "query selection and ordered AID membership; status and amount "
                "fields are mutable and are fetched again on continuation"
            ),
        },
        "public_fields": [
            "aid",
            "case_status",
            "case_number",
            "parcel_ids",
            "property_address",
            "city",
            "postal_code",
            "appraised_value",
            "opening_bid",
            "deposit_requirement",
            "scheduled_datetime",
            "auction_status",
            "sold_to_class",
            "sold_amount",
        ],
        "public_field_gaps": [
            "plaintiff",
            "defendant",
            "full_legal_description",
            "court_docket",
            "court_filing_documents",
            "recorded_sheriff_deed",
            "title_status",
            "special_notes_visible_only_in_registered_detail",
        ],
        "official_alternatives_and_complements": [
            dict(item) for item in tenant.alternatives
        ],
    }


def parse_calendar_page(
    html: str,
    *,
    tenant: Tenant,
    requested_month: str,
    source_url: str,
) -> tuple[dict[str, Any], ...]:
    """Parse one official monthly auction calendar."""

    soup = BeautifulSoup(html, "html.parser")
    calendar = soup.select_one(".CALMAIN")
    if calendar is None:
        raise OhioSheriffSaleSourceChanged(
            "auction calendar container is missing"
        )
    headings = [_clean(node) for node in calendar.select(".CALDATE")]
    expected_heading = datetime.strptime(requested_month, "%Y-%m").strftime(
        "%B %Y"
    )
    if not headings or headings[0] != expected_heading:
        raise OhioSheriffSaleSourceChanged(
            "auction calendar month did not match the requested month"
        )

    records: list[dict[str, Any]] = []
    for cell in calendar.select(".CALBOX[dayid]"):
        native_date = _clean(cell.get("dayid"))
        try:
            event_date = datetime.strptime(native_date, "%m/%d/%Y").date()
        except ValueError as error:
            raise OhioSheriffSaleSourceChanged(
                "auction calendar dayid format changed"
            ) from error
        if event_date.strftime("%Y-%m") != requested_month:
            continue
        active_node = cell.select_one(".CALACT")
        scheduled_node = cell.select_one(".CALSCH")
        if active_node is None or scheduled_node is None:
            raise OhioSheriffSaleSourceChanged(
                "auction calendar count fields changed"
            )
        try:
            active_count = int(_clean(active_node))
            scheduled_count = int(_clean(scheduled_node))
        except ValueError as error:
            raise OhioSheriffSaleSourceChanged(
                "auction calendar counts are not integers"
            ) from error
        kind_node = cell.find("b")
        time_node = cell.select_one(".CALTIME")
        event_iso = event_date.isoformat()
        canonical_ref = canonical_property_ref(
            tenant.source_id,
            tenant.county_geoid,
            "sheriff-sale-calendar",
            event_iso,
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": tenant.source_id,
                "record_kind": "sheriff_sale_calendar_event",
                "county_geoid": tenant.county_geoid,
                "auction_date": event_iso,
                "auction_kind": _clean(kind_node) or None,
                "active_count": active_count,
                "scheduled_count": scheduled_count,
                "source_time_label": _clean(time_node) or None,
                "source_url": source_url,
                "access_state": "anonymous",
                "observed_at": OBSERVED_AT,
            }
        )
    return tuple(records)


_LISTING_TOKEN_REPLACEMENTS = (
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
)


def decode_listing_html(value: str) -> str:
    """Expand the compact substitutions applied by the official auction.js."""

    decoded = value
    for token, replacement in _LISTING_TOKEN_REPLACEMENTS:
        decoded = decoded.replace(token, replacement)
    return decoded


def _case_parts(value: str) -> tuple[str, str | None]:
    match = re.fullmatch(r"(.*?)(?:\s+\(([^()]*)\))?", value.strip())
    if match is None:
        return value.strip(), None
    case_number = match.group(1).strip()
    source_sequence = (match.group(2) or "").strip() or None
    return case_number, source_sequence


def _parcel_ids(value: str) -> list[str]:
    return [
        candidate.strip()
        for candidate in re.split(r"\s+\bAND\b\s+|\s*;\s*", value, flags=re.I)
        if candidate.strip()
    ]


def _city_zip(value: str) -> tuple[str | None, str | None]:
    candidate = value.strip()
    if not candidate:
        return None, None
    if "," in candidate:
        city, postal_code = candidate.rsplit(",", 1)
        return city.strip() or None, postal_code.strip() or None
    match = re.fullmatch(r"(.*?)\s+(\d{5}(?:-?\d{4})?)", candidate)
    if match:
        return match.group(1).strip() or None, match.group(2)
    return candidate, None


def parse_listing_payload(
    payload: Mapping[str, Any],
    *,
    tenant: Tenant,
    auction_date: str,
    area: str,
    page: int,
    source_url: str,
) -> ListingPage:
    """Parse one native status-area page returned by ``FNC=LOAD``."""

    if area not in AREA_LABELS:
        raise ValueError(f"unknown native auction area: {area}")
    ret_html = payload.get("retHTML")
    native_rlist = payload.get("rlist")
    if not isinstance(ret_html, str) or not isinstance(native_rlist, str):
        raise OhioSheriffSaleSourceChanged(
            "auction listing JSON keys changed"
        )
    decoded = decode_listing_html(ret_html)
    soup = BeautifulSoup(decoded, "html.parser")
    items = soup.select(".AUCTION_ITEM[aid]")
    records: list[dict[str, Any]] = []
    auction_ids: list[str] = []

    for item in items:
        aid = _clean(item.get("aid"))
        if not aid:
            raise OhioSheriffSaleSourceChanged(
                "auction listing item is missing AID"
            )
        table = item.select_one(".AUCTION_DETAILS table")
        if table is None:
            raise OhioSheriffSaleSourceChanged(
                f"auction {aid} details table is missing"
            )
        labeled: dict[str, str] = {}
        unlabeled_values: list[str] = []
        labels_seen: list[str] = []
        for row in table.select("tr"):
            label = _clean(row.find("th")).removesuffix(":")
            value = _clean(row.find("td"))
            if label:
                labeled[label] = value
                labels_seen.append(label)
            elif value:
                unlabeled_values.append(value)
        missing = [
            label for label in EXPECTED_LISTING_LABELS if label not in labeled
        ]
        if missing:
            raise OhioSheriffSaleSourceChanged(
                "auction listing fields changed; missing "
                + ", ".join(missing)
            )
        case_number, source_case_sequence = _case_parts(labeled["Case #"])
        parcel_ids = _parcel_ids(labeled["Parcel ID"])
        city, postal_code = _city_zip(
            unlabeled_values[0] if unlabeled_values else ""
        )
        canonical_ref = canonical_property_ref(
            tenant.source_id,
            tenant.county_geoid,
            "sheriff-sale-auction",
            aid,
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": tenant.source_id,
                "record_kind": "sheriff_sale_auction",
                "record_scope": "judicial_or_tax_sale_observation",
                "county_geoid": tenant.county_geoid,
                "native_auction_id": aid,
                "identity_kind": "county_tenant_and_aid",
                "auction_date": auction_date,
                "native_area": area,
                "area": AREA_LABELS[area],
                "source_page": page,
                "case_status": labeled["Case Status"] or None,
                "case_number": case_number or None,
                "case_number_raw": labeled["Case #"] or None,
                "source_case_sequence": source_case_sequence,
                "parcel_id_raw": labeled["Parcel ID"] or None,
                "parcel_ids": parcel_ids,
                "property_address": labeled["Property Address"] or None,
                "city": city,
                "postal_code": postal_code,
                "city_postal_raw": (
                    unlabeled_values[0] if unlabeled_values else None
                ),
                "appraised_value_raw": labeled["Appraised Value"] or None,
                "appraised_value_amount": _money_amount(
                    labeled["Appraised Value"]
                ),
                "opening_bid_raw": labeled["Opening Bid"] or None,
                "opening_bid_amount": _money_amount(labeled["Opening Bid"]),
                "deposit_requirement_raw": (
                    labeled["Deposit Requirement"] or None
                ),
                "deposit_requirement_amount": _money_amount(
                    labeled["Deposit Requirement"]
                ),
                "source_url": source_url,
                "access_state": "anonymous",
                "source_field_labels": labels_seen,
                "listing_schema_fingerprint": LISTING_SCHEMA_FINGERPRINT,
            }
        )
        auction_ids.append(aid)

    rlist_ids = tuple(
        candidate.strip()
        for candidate in native_rlist.split(",")
        if candidate.strip()
    )
    if tuple(auction_ids) != rlist_ids:
        raise OhioSheriffSaleSnapshotChanged(
            "listing item order did not match the source rlist"
        )
    return ListingPage(
        area=area,
        page=page,
        records=tuple(records),
        auction_ids=tuple(auction_ids),
        schema_fingerprint=LISTING_SCHEMA_FINGERPRINT,
    )


def _parse_page_count(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, bool):
        raise OhioSheriffSaleSourceChanged(
            f"auction paginator {key} changed type"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise OhioSheriffSaleSourceChanged(
            f"auction paginator {key} changed type"
        ) from error
    if parsed < 0:
        raise OhioSheriffSaleSourceChanged(
            f"auction paginator {key} is negative"
        )
    return parsed


def _source_datetime(value: str) -> str | None:
    candidate = value.strip()
    match = re.fullmatch(
        r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+([AP]M)\s+ET",
        candidate,
        flags=re.I,
    )
    if match is None:
        return None
    parsed = datetime.strptime(
        " ".join(match.groups()[:3]), "%m/%d/%Y %I:%M %p"
    ).replace(tzinfo=ZoneInfo("America/New_York"))
    return parsed.isoformat()


def _derived_status(
    native_area: str,
    status_label: str,
    status_message: str,
) -> str:
    combined = f"{status_label} {status_message}".casefold()
    for label, canonical in (
        ("cancel", "canceled"),
        ("withdraw", "withdrawn"),
        ("reschedul", "rescheduled"),
        ("bankrupt", "bankruptcy"),
        ("unsold", "unsold"),
        ("sold", "sold"),
    ):
        if label in combined:
            return canonical
    if native_area == "R":
        return "running"
    if native_area == "W":
        return "scheduled"
    return "closed_or_canceled"


def parse_update_payload(
    payload: Mapping[str, Any],
    *,
    expected_aids: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Parse dynamic status fields and native page-count metadata."""

    if any(payload.get(key) is True for key in ("RA", "RR", "RW", "RC")):
        raise OhioSheriffSaleSnapshotChanged(
            "auction membership changed while pages were being read"
        )
    adata = payload.get("ADATA")
    if not isinstance(adata, Mapping):
        raise OhioSheriffSaleSourceChanged(
            "auction status JSON is missing ADATA"
        )
    items = adata.get("AITEM")
    if not isinstance(items, list):
        raise OhioSheriffSaleSourceChanged(
            "auction status JSON AITEM changed type"
        )
    by_aid: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise OhioSheriffSaleSourceChanged(
                "auction status item changed type"
            )
        aid = _clean(item.get("AID"))
        if not aid:
            raise OhioSheriffSaleSourceChanged(
                "auction status item is missing AID"
            )
        if aid in by_aid:
            raise OhioSheriffSaleSourceChanged(
                "auction status JSON repeated an AID"
            )
        status_code = _clean(item.get("A"))
        status_label = {
            "A": "Auction Starts",
            "B": "Auction Status",
        }.get(status_code, status_code)
        status_message = _clean(item.get("B"))
        by_aid[aid] = {
            "source_status_label": status_label or None,
            "source_status_message": status_message or None,
            "scheduled_or_status_datetime": _source_datetime(status_message),
            "source_reported_bid_amount_raw": _clean(item.get("P")) or None,
            "source_reported_bid_amount": _money_amount(
                _clean(item.get("P"))
            ),
            "amount_label": _clean(item.get("C")) or None,
            "sold_amount_raw": _clean(item.get("D")) or None,
            "sold_amount": _money_amount(_clean(item.get("D"))),
            "sold_to_label": _clean(item.get("SL")) or None,
            "sold_to_class": _clean(item.get("ST")) or None,
            "bid_history_available": bool(item.get("SBH")),
            "bidding_open_observation": bool(item.get("SP")),
            "source_update_payload": {
                str(key): value
                for key, value in item.items()
                if isinstance(key, str)
                and value is not None
                and isinstance(value, (str, int, float, bool))
            },
        }
    if set(by_aid) != set(expected_aids):
        raise OhioSheriffSaleSnapshotChanged(
            "auction status membership did not match the loaded page"
        )
    page_counts = {
        "W": _parse_page_count(payload, "WM"),
        "C": _parse_page_count(payload, "CM"),
    }
    return by_aid, page_counts


def _overlay_updates(
    records: Sequence[Mapping[str, Any]],
    updates: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for record in records:
        normalized = dict(record)
        aid = str(record["native_auction_id"])
        update = dict(updates.get(aid, {}))
        normalized.update(update)
        normalized["auction_status"] = _derived_status(
            str(record["native_area"]),
            str(update.get("source_status_label") or ""),
            str(update.get("source_status_message") or ""),
        )
        merged.append(normalized)
    return merged


def _selection_payload(
    tenant: Tenant,
    *,
    auction_date: str,
    areas: Sequence[str],
    case_number: str | None,
    parcel: str | None,
    address: str | None,
    auction_id: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": tenant.source_id,
        "county_geoid": tenant.county_geoid,
        "auction_date": auction_date,
        "areas": list(areas),
        "case_number": case_number,
        "parcel": parcel,
        "address": address,
        "auction_id": auction_id,
        "listing_schema_fingerprint": LISTING_SCHEMA_FINGERPRINT,
    }


def _membership_fingerprint(records: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        canonical_json(
            [str(record["native_auction_id"]) for record in records]
        ).encode("utf-8")
    ).hexdigest()


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    raw = canonical_json(payload).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise OhioSheriffSaleSelectionError(
            "invalid_cursor",
            "cursor is not an Ohio RealAuction continuation",
        )
    token = value.removeprefix(CURSOR_PREFIX)
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as error:
        raise OhioSheriffSaleSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping):
        raise OhioSheriffSaleSelectionError(
            "invalid_cursor",
            "cursor payload changed type",
        )
    return payload


def _window_records(
    records: Sequence[Mapping[str, Any]],
    *,
    selection: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    membership = _membership_fingerprint(records)
    selection_fingerprint = hashlib.sha256(
        canonical_json(selection).encode("utf-8")
    ).hexdigest()
    offset = 0
    if cursor:
        payload = _cursor_decode(cursor)
        if payload.get("selection_fingerprint") != selection_fingerprint:
            raise OhioSheriffSaleSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to a different county, date, area, or filter",
            )
        if (
            payload.get("membership_fingerprint") != membership
            or payload.get("total") != len(records)
        ):
            raise OhioSheriffSaleSelectionError(
                "cursor_membership_changed",
                "auction membership changed since the cursor was issued",
            )
        try:
            offset = int(payload["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise OhioSheriffSaleSelectionError(
                "invalid_cursor",
                "cursor offset is invalid",
            ) from error
        if offset < 0 or offset > len(records):
            raise OhioSheriffSaleSelectionError(
                "invalid_cursor",
                "cursor offset is outside the result set",
            )
        expected_anchor = (
            str(records[offset - 1]["native_auction_id"])
            if offset > 0
            else None
        )
        if payload.get("anchor_before") != expected_anchor:
            raise OhioSheriffSaleSelectionError(
                "cursor_membership_changed",
                "auction cursor boundary changed",
            )

    end = len(records) if limit is None else min(offset + limit, len(records))
    window = [dict(record) for record in records[offset:end]]
    next_cursor = None
    if end < len(records):
        next_cursor = _cursor_encode(
            {
                "selection_fingerprint": selection_fingerprint,
                "membership_fingerprint": membership,
                "offset": end,
                "anchor_before": str(
                    records[end - 1]["native_auction_id"]
                ),
                "total": len(records),
            }
        )
    return window, next_cursor


def _matches(
    record: Mapping[str, Any],
    *,
    case_number: str | None,
    parcel: str | None,
    address: str | None,
    auction_id: str | None = None,
) -> bool:
    if auction_id and auction_id.casefold() != str(
        record.get("native_auction_id") or ""
    ).casefold():
        return False
    if case_number and case_number.casefold() not in str(
        record.get("case_number") or ""
    ).casefold():
        return False
    if parcel and parcel.casefold() not in str(
        record.get("parcel_id_raw") or ""
    ).casefold():
        return False
    if address and address.casefold() not in " ".join(
        [
            str(record.get("property_address") or ""),
            str(record.get("city") or ""),
            str(record.get("postal_code") or ""),
        ]
    ).casefold():
        return False
    return True


class OhioRealAuctionClient:
    """Requests-compatible client for the verified Ohio RealAuction contract."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/json;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at = 0.0
        self._bootstrapped: set[str] = set()
        self.request_count = 0

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        tenant: Tenant,
        parameters: Mapping[str, Any],
        *,
        expect_json: bool = False,
        endpoint: str | None = None,
    ) -> TextResponse:
        headers = (
            {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            }
            if expect_json
            else None
        )
        for attempt in range(self.max_retries + 1):
            elapsed = self._clock() - self._last_request_at
            if elapsed < self.minimum_interval:
                self._sleeper(self.minimum_interval - elapsed)
            try:
                self._last_request_at = self._clock()
                self.request_count += 1
                response = self.session.request(
                    "GET",
                    endpoint or tenant.index_url,
                    params=dict(parameters),
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise OhioSheriffSaleTransportError(
                    f"Ohio RealAuction request failed: {error}"
                ) from error
            response_url = str(
                getattr(response, "url", endpoint or tenant.index_url)
            )
            expected_host = (urlparse(tenant.base_url).hostname or "").casefold()
            response_host = (urlparse(response_url).hostname or "").casefold()
            if response_host != expected_host:
                raise OhioSheriffSaleSourceChanged(
                    "Ohio RealAuction response resolved outside the selected "
                    f"official tenant host: {response_host or '<missing>'}"
                )
            status_code = int(response.status_code)
            if (status_code == 429 or status_code >= 500) and (
                attempt < self.max_retries
            ):
                self._sleeper(0.5 * (2**attempt))
                continue
            if status_code == 429:
                raise OhioSheriffSaleRateLimited(
                    "Ohio RealAuction returned HTTP 429"
                )
            if status_code < 200 or status_code >= 300:
                raise OhioSheriffSaleHTTPError(
                    status_code,
                    response_url,
                )
            return TextResponse(
                text=str(response.text),
                url=response_url,
                headers=dict(getattr(response, "headers", {})),
            )
        raise OhioSheriffSaleTransportError(
            "Ohio RealAuction request exhausted retries"
        )

    def bootstrap(self, tenant: Tenant) -> None:
        """Establish the public ColdFusion session used by calendar/list calls."""

        if tenant.slug in self._bootstrapped:
            return
        response = self._request(
            tenant,
            {},
            endpoint=f"{tenant.base_url}/",
        )
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.select_one("#splashMenuBottom") is None:
            raise OhioSheriffSaleSourceChanged(
                "Ohio RealAuction public splash contract changed"
            )
        self._bootstrapped.add(tenant.slug)

    def _json(
        self,
        tenant: Tenant,
        parameters: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], str]:
        response = self._request(tenant, parameters, expect_json=True)
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise OhioSheriffSaleSourceChanged(
                "Ohio RealAuction JSON endpoint returned non-JSON content"
            ) from error
        if not isinstance(payload, Mapping):
            raise OhioSheriffSaleSourceChanged(
                "Ohio RealAuction JSON response changed type"
            )
        return payload, response.url

    def calendar(
        self,
        tenant: Tenant,
        month: str,
    ) -> tuple[dict[str, Any], ...]:
        self.bootstrap(tenant)
        parameters = {
            "zaction": "USER",
            "zmethod": "CALENDAR",
            "selCalDate": _month_source_value(month),
        }
        response = self._request(tenant, parameters)
        return parse_calendar_page(
            response.text,
            tenant=tenant,
            requested_month=month,
            source_url=response.url,
        )

    def _load_page(
        self,
        tenant: Tenant,
        *,
        auction_date: str,
        area: str,
        page: int,
    ) -> ListingPage:
        parameters = {
            "zaction": "AUCTION",
            "Zmethod": "UPDATE",
            "FNC": "LOAD",
            "AREA": area,
            "PageDir": 0,
            "doR": 1,
            "bypassPage": 0 if page == 1 else page,
            "test": 1,
        }
        payload, source_url = self._json(tenant, parameters)
        return parse_listing_payload(
            payload,
            tenant=tenant,
            auction_date=auction_date,
            area=area,
            page=page,
            source_url=source_url,
        )

    def _update(
        self,
        tenant: Tenant,
        auction_ids: Sequence[str],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
        if not auction_ids:
            return {}, {"W": 0, "C": 0}
        parameters = {
            "zaction": "AUCTION",
            "ZMETHOD": "UPDATE",
            "FNC": "UPDATE",
            "ref": ",".join(auction_ids) + ",",
        }
        payload, _source_url = self._json(tenant, parameters)
        return parse_update_payload(payload, expected_aids=auction_ids)

    def auctions(
        self,
        tenant: Tenant,
        auction_date: str,
        *,
        areas: Sequence[str] = DEFAULT_AREAS,
    ) -> AuctionFetch:
        """Fetch all native pages for one county, date, and status selection."""

        self.bootstrap(tenant)
        preview_parameters = {
            "zaction": "AUCTION",
            "Zmethod": "PREVIEW",
            "AUCTIONDATE": _date_source_value(auction_date),
        }
        preview = self._request(tenant, preview_parameters)
        preview_soup = BeautifulSoup(preview.text, "html.parser")
        if (
            preview_soup.select_one(".AuctionNav_Main") is None
            or preview_soup.select_one("#BID_WINDOW_CONTAINER") is None
        ):
            raise OhioSheriffSaleSourceChanged(
                "auction preview contract changed or redirected to the splash page"
            )

        first_pages: list[ListingPage] = []
        for area in areas:
            first_pages.append(
                self._load_page(
                    tenant,
                    auction_date=auction_date,
                    area=area,
                    page=1,
                )
            )
        first_aids = [
            aid for page in first_pages for aid in page.auction_ids
        ]
        first_updates, reported_counts = self._update(tenant, first_aids)

        all_records: list[dict[str, Any]] = []
        pages_fetched = {area: 1 for area in areas}
        source_page_counts = {area: 1 for area in areas}
        for page in first_pages:
            all_records.extend(_overlay_updates(page.records, first_updates))
            if page.area in {"W", "C"}:
                count = reported_counts.get(page.area, 0)
                if page.records and count < 1:
                    raise OhioSheriffSaleSnapshotChanged(
                        f"{AREA_LABELS[page.area]} page count changed"
                    )
                source_page_counts[page.area] = count

        for area in areas:
            if area not in {"W", "C"}:
                continue
            for page_number in range(2, source_page_counts[area] + 1):
                page = self._load_page(
                    tenant,
                    auction_date=auction_date,
                    area=area,
                    page=page_number,
                )
                if not page.records:
                    raise OhioSheriffSaleSnapshotChanged(
                        f"{AREA_LABELS[area]} page {page_number} became empty"
                    )
                updates, _page_counts = self._update(
                    tenant, page.auction_ids
                )
                all_records.extend(_overlay_updates(page.records, updates))
                pages_fetched[area] = page_number

        seen: set[str] = set()
        for record in all_records:
            aid = str(record["native_auction_id"])
            if aid in seen:
                raise OhioSheriffSaleSnapshotChanged(
                    f"auction {aid} appeared on multiple native pages"
                )
            seen.add(aid)
        return AuctionFetch(
            records=tuple(all_records),
            pages_fetched=pages_fetched,
            source_page_counts=source_page_counts,
            preview_url=preview.url,
            listing_schema_fingerprint=LISTING_SCHEMA_FINGERPRINT,
        )


def _source_failure(
    query: PublicRecordsQuery,
    error: OhioSheriffSaleError,
) -> PublicRecordsResult:
    if isinstance(error, OhioSheriffSaleRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "rate_limited"
        category = "rate_limit"
        retryable = True
        details: dict[str, Any] = {}
    elif isinstance(error, OhioSheriffSaleHTTPError):
        status = (
            ResultStatus.RESTRICTED
            if error.status_code in {401, 403}
            else ResultStatus.UNAVAILABLE
        )
        code = f"http_{error.status_code}"
        category = "http"
        retryable = error.status_code >= 500
        details = {
            "status_code": error.status_code,
            "url": error.url,
            "access_characterization": "observed_response_not_policy",
        }
    elif isinstance(error, OhioSheriffSaleTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "transport_error"
        category = "transport"
        retryable = True
        details = {}
    elif isinstance(
        error,
        (OhioSheriffSaleSourceChanged, OhioSheriffSaleSnapshotChanged),
    ):
        status = ResultStatus.SOURCE_CHANGED
        code = (
            "snapshot_changed"
            if isinstance(error, OhioSheriffSaleSnapshotChanged)
            else "source_schema_changed"
        )
        category = "source_schema"
        retryable = isinstance(error, OhioSheriffSaleSnapshotChanged)
        details = {}
    elif isinstance(error, OhioSheriffSaleSelectionError):
        status = ResultStatus.UNAVAILABLE
        code = error.code
        category = "query"
        retryable = False
        details = dict(error.details)
    else:
        status = ResultStatus.UNAVAILABLE
        code = "source_error"
        category = "source"
        retryable = False
        details = {}
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category=category,
                retryable=retryable,
                details=details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _areas_from_args(args: argparse.Namespace) -> tuple[str, ...]:
    selected = getattr(args, "area", None)
    if not selected:
        return DEFAULT_AREAS
    return tuple(AREA_CODES[value] for value in selected)


def _tenant(args: argparse.Namespace) -> Tenant:
    return TENANTS[str(args.county)]


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: OhioRealAuctionClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one standalone Ohio sheriff-sale operation."""

    tenant = _tenant(args)
    operation = args.command
    if operation == "probe" and args.date is None:
        args.date = PROBE_SENTINEL_DATES[tenant.slug]
    parameters: dict[str, Any] = {"county": tenant.slug}
    limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    if operation == "calendar":
        parameters["month"] = args.month
    elif operation == "auctions":
        parameters.update(
            {
                "auction_date": args.date,
                "areas": list(_areas_from_args(args)),
                "case_number": args.case_number,
                "parcel": args.parcel,
                "address": args.address,
                "auction_id": getattr(args, "auction_id", None),
                "completeness": (
                    "all_native_pages"
                    if limit is None
                    else "caller_selected_window_after_complete_traversal"
                ),
            }
        )
    elif operation == "probe":
        parameters.update(
            {
                "auction_date": args.date,
                "month": args.date[:7],
                "routes": [
                    "root_session_bootstrap",
                    "monthly_calendar",
                    "auction_preview",
                    "listing_json",
                    "status_json",
                ],
            }
        )
    query = _query(
        tenant,
        operation,
        parameters=parameters,
        limit=limit,
        cursor=cursor,
    )

    source_client = client or OhioRealAuctionClient(
        timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
        minimum_interval=float(
            getattr(args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL)
        ),
        max_retries=int(getattr(args, "retry_attempts", DEFAULT_MAX_RETRIES)),
    )
    try:
        if operation == "source":
            result = PublicRecordsResult.success(
                query,
                [_source_record(tenant)],
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "calendar":
            records = source_client.calendar(tenant, args.month)
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "probe":
            probe_month = args.date[:7]
            calendar = source_client.calendar(tenant, probe_month)
            calendar_record = next(
                (
                    record
                    for record in calendar
                    if record["auction_date"] == args.date
                ),
                None,
            )
            if calendar_record is None:
                raise OhioSheriffSaleSelectionError(
                    "probe_sentinel_not_in_calendar",
                    (
                        f"{args.date} is not an auction date in the "
                        f"{tenant.county_name} public calendar"
                    ),
                    details={
                        "auction_date": args.date,
                        "calendar_month": probe_month,
                    },
                )
            fetched = source_client.auctions(
                tenant,
                args.date,
                areas=DEFAULT_AREAS,
            )
            if not fetched.records:
                raise OhioSheriffSaleSourceChanged(
                    "probe sentinel calendar entry returned no public listings"
                )
            probe = _source_record(tenant)
            probe["record_kind"] = "source_probe"
            statuses: dict[str, int] = {}
            for record in fetched.records:
                status = str(record.get("auction_status") or "unknown")
                statuses[status] = statuses.get(status, 0) + 1
            probe["probe"] = {
                "month": probe_month,
                "auction_date": args.date,
                "calendar_scheduled_count": calendar_record[
                    "scheduled_count"
                ],
                "listing_count": len(fetched.records),
                "status_counts": statuses,
                "pages_fetched": dict(fetched.pages_fetched),
                "source_page_counts": dict(fetched.source_page_counts),
                "routes_exercised": [
                    "root_session_bootstrap",
                    "monthly_calendar",
                    "auction_preview",
                    "listing_json",
                    "status_json",
                ],
                "status": "available",
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
        else:
            areas = _areas_from_args(args)
            fetched = source_client.auctions(
                tenant,
                args.date,
                areas=areas,
            )
            filtered = [
                dict(record)
                for record in fetched.records
                if _matches(
                    record,
                    case_number=args.case_number,
                    parcel=args.parcel,
                    address=args.address,
                    auction_id=getattr(args, "auction_id", None),
                )
            ]
            selection = _selection_payload(
                tenant,
                auction_date=args.date,
                areas=areas,
                case_number=args.case_number,
                parcel=args.parcel,
                address=args.address,
                auction_id=getattr(args, "auction_id", None),
            )
            window, next_cursor = _window_records(
                filtered,
                selection=selection,
                limit=limit,
                cursor=cursor,
            )
            for record in window:
                record["retrieval"] = {
                    "pages_fetched": dict(fetched.pages_fetched),
                    "source_page_counts": dict(
                        fetched.source_page_counts
                    ),
                    "source_reported_matching_records": len(filtered),
                    "adapter_truncated": next_cursor is not None,
                    "preview_url": fetched.preview_url,
                }
            result = PublicRecordsResult.success(
                query,
                window,
                next_cursor=next_cursor,
                warnings=SOURCE_WARNINGS,
            )
    except OhioSheriffSaleError as error:
        result = _source_failure(query, error)

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        _log(query, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Ohio sheriff sales {args.county} {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Ohio sheriff sales {args.county} {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "sheriff_sale_calendar_event":
            print(
                f"- {record['auction_date']} | "
                f"{record['active_count']}/{record['scheduled_count']} active"
            )
        elif record.get("record_kind") == "sheriff_sale_auction":
            print(
                f"- AID {record['native_auction_id']} | "
                f"{record.get('case_number') or '?'} | "
                f"{record.get('property_address') or '?'} | "
                f"{record.get('auction_status') or '?'}"
            )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Ohio RealAuction sheriff-sale calendars and "
            "anonymous public auction listings"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show the verified tenant contract, fields, gaps, and alternatives",
    )
    source.add_argument("county", choices=sorted(TENANTS))
    add_output_args(source)

    calendar = subparsers.add_parser(
        "calendar",
        help="List official auction dates and active/scheduled counts",
    )
    calendar.add_argument("county", choices=sorted(TENANTS))
    calendar.add_argument("--month", required=True, type=_parse_iso_month)
    add_output_args(calendar)

    auctions = subparsers.add_parser(
        "auctions",
        help="Traverse public auction rows for one official auction date",
    )
    auctions.add_argument("county", choices=sorted(TENANTS))
    auctions.add_argument("--date", required=True, type=_parse_iso_date)
    auctions.add_argument(
        "--area",
        action="append",
        choices=sorted(AREA_CODES),
        help=(
            "Native status area to include; repeat for more than one. "
            "Default: all areas."
        ),
    )
    auctions.add_argument(
        "--case-number",
        help="Keep rows whose case number contains this text",
    )
    auctions.add_argument(
        "--parcel",
        help="Keep rows whose source parcel field contains this text",
    )
    auctions.add_argument(
        "--address",
        help="Keep rows whose address/city/postal text contains this text",
    )
    auctions.add_argument(
        "--auction-id",
        help="Keep the row whose native RealAuction AID matches exactly",
    )
    auctions.add_argument(
        "--limit",
        type=_positive_int,
        help="Return this many rows and a continuation cursor if more remain",
    )
    auctions.add_argument("--cursor", help="Resume a prior bounded query")
    add_output_args(auctions)

    probe = subparsers.add_parser(
        "probe",
        help=(
            "Probe one official tenant through calendar, preview, listing, "
            "and status routes"
        ),
    )
    probe.add_argument("county", choices=sorted(TENANTS))
    probe.add_argument(
        "--date",
        type=_parse_iso_date,
        help=(
            "Auction sentinel date; defaults to a verified county sentinel"
        ),
    )
    add_output_args(probe)
    for command in subparsers.choices.values():
        command.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
        command.add_argument(
            "--minimum-interval",
            type=float,
            default=DEFAULT_MINIMUM_INTERVAL,
        )
        command.add_argument(
            "--retry-attempts",
            type=int,
            default=DEFAULT_MAX_RETRIES,
        )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
